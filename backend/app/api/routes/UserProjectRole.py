from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlmodel import select
from uuid import UUID
from typing import Dict, List, Any, Optional

from app.models import (
    ProjectList,
    ProjectsPublic,
    User,
    UserProjectRole,
    UserProjectRoleCreate,
    UserProjectRoleUpdate,
    UserProjectRolePublic,
    Role,
)
from app.api.deps import (
    CurrentUser,
    get_current_user,
    get_current_active_superuser,
    get_current_active_user,
    ProjectAccessInfo,
    SessionDep,
    verify_system_rank_in,
)
import app.crud as crud

router = APIRouter(prefix="/UserProjectRole", tags=["UserProjectRole"])

PROJECT_FOLDER = "DUAN"
STATIC_URL_PREFIX = "/api/v1/static"


def build_flat_image_url(request: Request, picture: Optional[str]) -> Optional[str]:
    if not picture:
        return None
    base = str(request.base_url).rstrip("/")
    return f"{base}{STATIC_URL_PREFIX}/{PROJECT_FOLDER}/{picture}.jpg"



@router.get(
    "/assignments",
    response_model=List[Dict[str, Any]],
    dependencies=[
        Depends(get_current_user),
        Depends(verify_system_rank_in([1, 2])) # Chỉ cho phép superuser và admin (rank 1, 2) truy cập
    ]
)
def read_all_user_project_assignments(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (e.g., 'vi' or 'en')"),
) -> Any:
    """
    Đọc tất cả các bản phân quyền user-project-role.
    Chỉ cho phép superuser hoặc người có quyền admin hệ thống.
    Thông tin dự án được hiển thị theo ngôn ngữ được chỉ định.
    """

    statement = select(UserProjectRole, User, ProjectList, Role).join(User).join(ProjectList).join(Role)
    
    results = session.exec(statement).all()

    assignments = []
    for user_project_role, user, project, role in results:
        assignment_info = {
            "user_id": user.id,
            "user_email": user.email,
            "project_id": project.id,
            "project_name": getattr(project, f'name_{lang}', None), # Ánh xạ tên dự án theo ngôn ngữ
            "role_id": role.id,
            "role_name": role.name,
            "role_rank": role.rank,
        }
        assignments.append(assignment_info)

    return assignments

@router.get(
    "/{project_id}",
    response_model=List[UserProjectRolePublic],
    dependencies=[Depends(get_current_active_user)],
)
def read_user_project_roles(
    project_id: UUID,
    session: SessionDep,
    info: ProjectAccessInfo,
) -> Any:
    current_user, _, current_rank = info

    user_roles = crud.get_user_project_role(session=session, project_id=project_id)

    if current_user.is_superuser:
        return user_roles

    return [upr for upr in user_roles if upr.role.rank >= current_rank]


@router.post(
    "/{project_id}",
    response_model=UserProjectRolePublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_active_user)],
)
def assign_user_to_project(
    project_id: UUID,
    user_project_role_in: UserProjectRoleCreate,
    session: SessionDep,
    info: ProjectAccessInfo,
) -> Any:
    current_user, _, current_rank = info

    if current_user.is_superuser:
        return crud.add_user_to_project_role(session=session, user_project_role_in=user_project_role_in)

    target_role = crud.get_role(session=session, role_id=user_project_role_in.role_id)
    if not target_role or target_role.rank < current_rank:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn chỉ được phân quyền vai trò thấp hơn quyền của mình."
        )

    return crud.add_user_to_project_role(session=session, user_project_role_in=user_project_role_in)


@router.put(
    "/{user_id}/{project_id}/{old_role_id}",
    response_model=UserProjectRolePublic,
    dependencies=[Depends(get_current_active_user)],
)
def update_user_role_in_project(
    user_id: UUID,
    project_id: UUID,
    old_role_id: UUID,
    update_data: UserProjectRoleUpdate,
    session: SessionDep,
    info: ProjectAccessInfo,
) -> Any:
    current_user, _, current_rank = info

    old_record = crud.get_user_project_role(session=session, user_id=user_id, project_id=project_id, role_id=old_role_id)
    if not old_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy phân quyền")

    if current_user.is_superuser:
        crud.delete_user_project_role(session=session, db_upr=old_record)
        return crud.add_user_to_project_role(session=session, user_project_role_in=UserProjectRoleCreate(
            user_id=user_id,
            project_id=project_id,
            role_id=update_data.role_id,
        ))

    if old_record.role.rank <= current_rank:
        raise HTTPException(status_code=403, detail="Không được sửa người có quyền cao hơn hoặc bằng")

    new_role = crud.get_role(session=session, role_id=update_data.role_id)
    if not new_role or new_role.rank >= current_rank:
        raise HTTPException(status_code=403, detail="Bạn chỉ được gán vai trò thấp hơn bạn")

    # Xoá + thêm mới (vì dùng 3 trường làm primary key)
    crud.delete_user_project_role(session=session, db_upr=old_record)
    return crud.add_user_to_project_role(session=session, user_project_role_in=UserProjectRoleCreate(
        user_id=user_id,
        project_id=project_id,
        role_id=update_data.role_id,
    ))


@router.delete(
    "/{user_id}/{project_id}/{role_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_active_user)],
)
def remove_user_from_project(
    user_id: UUID,
    project_id: UUID,
    role_id: UUID,
    session: SessionDep,
    info: ProjectAccessInfo,
) -> dict:
    current_user, _, current_rank = info

    user_role = crud.get_user_project_role(session=session, user_id=user_id, project_id=project_id, role_id=role_id)
    if not user_role:
        raise HTTPException(status_code=404, detail="Không tìm thấy phân quyền")

    if current_user.is_superuser or user_role.role.rank > current_rank:
        crud.delete_user_project_role(session=session, db_upr=user_role)
        return {"message": "Xóa phân quyền thành công"}

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bạn chỉ được xoá người có vai trò thấp hơn mình."
    )
