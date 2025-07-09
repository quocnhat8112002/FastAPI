from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from uuid import UUID
from typing import List, Any

from app.models import (
    UserProjectRole,
    UserProjectRoleCreate,
    UserProjectRoleUpdate,
    UserProjectRolePublic,
    Role,
)
from app.api.deps import (
    get_current_user,
    get_current_active_superuser,
    ProjectAccessInfo,
    SessionDep,
)
import app.crud as crud

router = APIRouter(prefix="/UserProjectRole", tags=["UserProjectRole"])


@router.get(
    "/{project_id}",
    response_model=List[UserProjectRolePublic],
    dependencies=[Depends(get_current_user)],
)
def read_user_project_roles(
    project_id: UUID,
    session: SessionDep,
    info: ProjectAccessInfo,
) -> Any:
    current_user, _, current_rank = info

    user_roles = crud.get_project_users_roles(session=session, project_id=project_id)

    if current_user.is_superuser:
        return user_roles

    return [upr for upr in user_roles if upr.role.rank >= current_rank]


@router.post(
    "/",
    response_model=UserProjectRolePublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_user)],
)
def assign_user_to_project(
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
    dependencies=[Depends(get_current_user)],
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

    old_record = crud.get_user_project_role(session, user_id, project_id, old_role_id)
    if not old_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy phân quyền")

    if current_user.is_superuser:
        crud.delete_user_project_role(session, user_id, project_id, old_role_id)
        return crud.add_user_to_project_role(session, user_project_role_in=UserProjectRoleCreate(
            user_id=user_id,
            project_id=project_id,
            role_id=update_data.role_id,
        ))

    if old_record.role.rank <= current_rank:
        raise HTTPException(status_code=403, detail="Không được sửa người có quyền cao hơn hoặc bằng")

    new_role = crud.get_role(session, update_data.role_id)
    if not new_role or new_role.rank >= current_rank:
        raise HTTPException(status_code=403, detail="Bạn chỉ được gán vai trò thấp hơn bạn")

    # Xoá + thêm mới (vì dùng 3 trường làm primary key)
    crud.delete_user_project_role(session, user_id, project_id, old_role_id)
    return crud.add_user_to_project_role(session, user_project_role_in=UserProjectRoleCreate(
        user_id=user_id,
        project_id=project_id,
        role_id=update_data.role_id,
    ))


@router.delete(
    "/{user_id}/{project_id}/{role_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_user)],
)
def remove_user_from_project(
    user_id: UUID,
    project_id: UUID,
    role_id: UUID,
    session: SessionDep,
    info: ProjectAccessInfo,
) -> dict:
    current_user, _, current_rank = info

    user_role = crud.get_user_project_role(session, user_id, project_id, role_id)
    if not user_role:
        raise HTTPException(status_code=404, detail="Không tìm thấy phân quyền")

    if current_user.is_superuser or user_role.role.rank > current_rank:
        crud.delete_user_project_role(session, user_id, project_id, role_id)
        return {"message": "Xóa phân quyền thành công"}

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Bạn chỉ được xoá người có vai trò thấp hơn mình."
    )
