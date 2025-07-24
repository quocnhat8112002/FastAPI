from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import HttpUrl
from sqlmodel import select, func

from app import crud
from app.models import (
    ProjectList,
    ProjectCreate,
    ProjectUpdate,
    ProjectPublic,
    ProjectsPublic,
    Role,
    UserProjectRole,
)
from app.api.deps import (
    SessionDep,
    get_current_user,
    verify_rank_in_project,
    CurrentUser,
    verify_system_rank_in
)

router = APIRouter(prefix="/projects", tags=["projects"])

PROJECT_FOLDER = "DUAN"
STATIC_URL_PREFIX = "/static"


def build_flat_image_url(request: Request, picture: Optional[str]) -> Optional[str]:
    if not picture:
        return None
    base = str(request.base_url).rstrip("/")
    return f"{base}{STATIC_URL_PREFIX}/{PROJECT_FOLDER}/{picture}.jpg"


@router.get("/",
        dependencies=[
            Depends(get_current_user), 
            Depends(verify_system_rank_in([1, 2, 3, 4, 5, 6])) # Kiểm tra system_rank, với 1 là rank của superuser
        ])
def read_projects(
    *,
    session: SessionDep,
    current_user: CurrentUser, 
    request: Request,
    skip: int = 0,
    limit: int = 100,
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (e.g., 'vi' or 'en')"),
) -> Dict[str, Any]:
    """
    Lấy tất cả các dự án và rank của người dùng hiện tại đối với từng dự án.
    Nếu người dùng chưa được gán rank cho dự án cụ thể, rank sẽ là null.
    """

    projects_from_db: List[ProjectList] = []
    count: int = 0

    count_stmt = select(func.count()).select_from(ProjectList)
    count = session.exec(count_stmt).one()
    projects_from_db = crud.get_all_project_lists(session=session, skip=skip, limit=limit)

    user_project_ranks: Dict[UUID, int] = {}
    
    if not current_user.is_superuser:
        project_ids_in_list = [project.id for project in projects_from_db]
        
        if project_ids_in_list: 
            user_project_roles_results = session.exec(
                select(UserProjectRole.project_id, UserProjectRole.role_id)
                .where(UserProjectRole.user_id == current_user.id)
                .where(UserProjectRole.project_id.in_(project_ids_in_list))
            ).all()

            role_ids_to_lookup = list(set([role_id for project_id, role_id in user_project_roles_results]))

            role_id_to_rank: Dict[UUID, int] = {}
            if role_ids_to_lookup:
                ranks_from_roles = session.exec(
                    select(Role.id, Role.rank)
                    .where(Role.id.in_(role_ids_to_lookup))
                ).all()
                for role_id, rank in ranks_from_roles:
                    role_id_to_rank[role_id] = rank
            
            for project_id, role_id in user_project_roles_results:
                if role_id in role_id_to_rank:
                    user_project_ranks[project_id] = role_id_to_rank[role_id]

    items_for_response = [] 
    for project_obj in projects_from_db:
        translated_item = project_obj.model_dump() 

        translated_item['name'] = translated_item.get(f'name_{lang}')
        translated_item['type'] = translated_item.get(f'type_{lang}')
        translated_item['address'] = translated_item.get(f'address_{lang}')
        translated_item['investor'] = translated_item.get(f'investor_{lang}')

        # Xóa các khóa gốc (_vi, _en) sau khi đã dịch
        for key in list(translated_item.keys()):
            if key.endswith('_vi') or key.endswith('_en'):
                del translated_item[key]

        image_name_from_db = getattr(project_obj, 'picture', None)
        translated_item['image_url'] = build_flat_image_url(request, image_name_from_db)
        
        if current_user.is_superuser:
            translated_item['rank'] = 1 
        else:
            translated_item['rank'] = user_project_ranks.get(project_obj.id, None) 

        items_for_response.append(translated_item)

    return {
        "data": items_for_response,
        "count": count
    }

@router.post("/", response_model=ProjectPublic, status_code=201)
def create_project(
    *,
    session: SessionDep,
    current_user=Depends(get_current_user),
    project_in: ProjectCreate,
) -> Any:
    """
    Create a new project (superuser or user with rank <= 2).
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Chỉ admin hệ thống mới được tạo project.")
    return crud.create_project_list(session=session, project_in=project_in)


@router.put(
    "/{project_id}",
    response_model=ProjectPublic,
    dependencies=[Depends(verify_rank_in_project([1, 2, 3]))]
)
def update_project(
    *,
    session: SessionDep,
    project_id: UUID,
    project_in: ProjectUpdate
) -> Any:
    """
    Update an existing project (rank or superuser).
    """
    db_project = crud.get_project_list(session=session, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project không tồn tại")

    return crud.update_project_list(session=session, db_project=db_project, project_in=project_in)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(verify_rank_in_project([1, 2, 3])), # Kiểm tra quyền trong dự án
    ],
)
def delete_project(
    *,
    session: SessionDep,
    project_id: UUID
) -> None:
    """
    Delete a project (rank or superuser).
    """
    db_project = crud.get_project_list(session=session, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project không tồn tại")

    crud.delete_project_list(session=session, db_project=db_project)
