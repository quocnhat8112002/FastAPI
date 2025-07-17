from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, func
from typing import Any
from uuid import UUID

from app.models import (
    System,
    SystemCreate,
    SystemUpdate,
    SystemPublic,
    SystemsPublic
)
from app.api.deps import SessionDep, get_current_active_superuser

router = APIRouter(prefix="/system", tags=["system"])

@router.get(
    "/",
    response_model=SystemsPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def read_system_roles(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    count = session.exec(select(func.count()).select_from(System)).one()
    roles = session.exec(select(System).offset(skip).limit(limit)).all()
    return SystemsPublic(data=roles, count=count)

@router.get(
    "/{system_id}",
    response_model=SystemPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def read_system_role(system_id: UUID, session: SessionDep) -> Any:
    role = session.get(System, system_id)
    if not role:
        raise HTTPException(status_code=404, detail="System role không tồn tại")
    return role

@router.post(
    "/",
    response_model=SystemPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_active_superuser)],
)
def create_system_role(*, session: SessionDep, role_in: SystemCreate) -> Any:
    role = System(**role_in.dict())
    session.add(role)
    session.commit()
    session.refresh(role)
    return role

@router.put(
    "/{system_id}",
    response_model=SystemPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def update_system_role(
    *,
    system_id: UUID,
    session: SessionDep,
    role_in: SystemUpdate
) -> Any:
    role = session.get(System, system_id)
    if not role:
        raise HTTPException(status_code=404, detail="System role không tồn tại")

    update_data = role_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(role, key, value)

    session.add(role)
    session.commit()
    session.refresh(role)
    return role

@router.delete(
    "/{system_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_system_role(*, system_id: UUID, session: SessionDep) -> None:
    role = session.get(System, system_id)
    if not role:
        raise HTTPException(status_code=404, detail="System role không tồn tại")
    session.delete(role)
    session.commit()


