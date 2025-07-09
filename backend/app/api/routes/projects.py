from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, func

from app import crud
from app.models import (
    ProjectList,
    ProjectCreate,
    ProjectUpdate,
    ProjectPublic,
    ProjectsPublic,
)
from app.api.deps import (
    SessionDep,
    get_current_user,
    verify_rank_in_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=ProjectsPublic)
def read_projects(
    *,
    session: SessionDep,
    current_user=Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
) -> Any:
    """
    Retrieve all projects (superuser gets all, others get only accessible ones).
    """
    if current_user.is_superuser:
        count_stmt = select(func.count()).select_from(ProjectList)
        count = session.exec(count_stmt).one()
        projects = crud.get_all_project_lists(session, skip=skip, limit=limit)
    else:
        projects, count = crud.get_accessible_project_lists(session, user_id=current_user.id, skip=skip, limit=limit)

    return ProjectsPublic(data=projects, count=count)


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
    return crud.create_project_list(db=session, project_in=project_in)


@router.put(
    "/{project_id}",
    response_model=ProjectPublic,
    dependencies=[Depends(verify_rank_in_project(min_rank=2))]
)
def update_project(
    *,
    session: SessionDep,
    project_id: UUID,
    project_in: ProjectUpdate
) -> Any:
    """
    Update an existing project (rank <= 2 or superuser).
    """
    db_project = crud.get_project_list(db=session, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project không tồn tại")

    return crud.update_project_list(db=session, db_project=db_project, project_update=project_in)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_rank_in_project(min_rank=2))]
)
def delete_project(
    *,
    session: SessionDep,
    project_id: UUID
) -> None:
    """
    Delete a project (rank <= 2 or superuser).
    """
    db_project = crud.get_project_list(db=session, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project không tồn tại")

    crud.delete_project_list(db=session, db_project=db_project)
