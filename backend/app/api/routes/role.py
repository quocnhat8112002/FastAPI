from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, func
from typing import Any
from uuid import UUID

from app.models import Role, RoleCreate, RoleUpdate, RolesPublic, RolePublic
from app.api.deps import SessionDep, get_current_active_superuser
from app import crud

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get(
    "/",
    response_model=RolesPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def read_roles(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve all roles (superuser only).
    """
    count_statement = select(func.count()).select_from(Role)
    count = session.exec(count_statement).one()

    roles = crud.get_roles(session, skip=skip, limit=limit)
    return RolesPublic(data=roles, count=count)


@router.get(
    "/{role_id}",
    response_model=RolePublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def read_role(role_id: UUID, session: SessionDep) -> Any:
    """
    Get a role by ID (superuser only).
    """
    role = crud.get_role(session, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role không tồn tại")
    return role


@router.post(
    "/",
    response_model=RolePublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_active_superuser)],
)
def create_role(*, session: SessionDep, role_in: RoleCreate) -> Any:
    """
    Create a new role (superuser only).
    """
    return crud.create_role(session, role_in)


@router.put(
    "/{role_id}",
    response_model=RolePublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def update_role(
    *,
    role_id: UUID,
    session: SessionDep,
    role_in: RoleUpdate,
) -> Any:
    """
    Update a role (superuser only).
    """
    db_role = crud.get_role(session, role_id)
    if not db_role:
        raise HTTPException(status_code=404, detail="Role không tồn tại")
    return crud.update_role(session, db_role, role_in)


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_role(*, role_id: UUID, session: SessionDep) -> None:
    """
    Delete a role (superuser only).
    """
    db_role = crud.get_role(session, role_id)
    if not db_role:
        raise HTTPException(status_code=404, detail="Role không tồn tại")
    crud.delete_role(session, db_role)
