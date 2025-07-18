import uuid
from typing import Any, List, Optional
from datetime import datetime

from fastapi import HTTPException
from sqlmodel import Session, select, col

from app.core.security import get_password_hash, verify_password
from app.models import (
    User, UserCreate, UserUpdate,
    System, SystemCreate, SystemUpdate,
    Role, RoleCreate, RoleUpdate,
    ProjectList, ProjectCreate, ProjectUpdate,
    UserProjectRole, UserProjectRoleCreate,
    Request, RequestCreate, RequestUpdate,
    Ecopark, EcoparkCreate, EcoparkUpdate
)

# ========== USER CRUD ==========

def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_user = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> User:
    user_data = user_in.model_dump(exclude_unset=True)
    if "password" in user_data:
        password = user_data.pop("password")
        user_data["hashed_password"] = get_password_hash(password)
    # Lấy rank từ System nếu có system_id
    if "system_id" in user_data:
        system_id = user_data.pop("system_id")
        system = session.get(System, system_id)
        if not system:
            raise HTTPException(status_code=404, detail="System role không tồn tại")
        db_user.system_rank = system.rank_total

    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user

def authenticate(*, session: Session, email: str, password: str) -> Optional[User]:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user or not verify_password(password, db_user.hashed_password):
        return None
    return db_user

# ========== SYSTEM CRUD ==========
def create_system(*, session: Session, system_in: SystemCreate) -> System:
    db_system = System.model_validate(system_in)
    session.add(db_system)
    session.commit()
    session.refresh(db_system)
    return db_system

def update_system(*, session: Session, db_system: System, system_in: SystemUpdate) -> System:
    update_data = system_in.model_dump(exclude_unset=True)
    db_system.sqlmodel_update(update_data)
    session.add(db_system)
    session.commit()
    session.refresh(db_system)
    return db_system

def get_system(*, session: Session, system_id: uuid.UUID) -> Optional[System]:
    return session.get(System, system_id)

def get_all_systems(*, session: Session, skip: int = 0, limit: int = 100) -> List[System]:
    statement = select(System).offset(skip).limit(limit)
    return session.exec(statement).all()

def delete_system(*, session: Session, db_system: System) -> System:
    session.delete(db_system)
    session.commit()
    return db_system

# ========== ROLE CRUD ==========

def create_role(*, session: Session, role_in: RoleCreate) -> Role:
    db_role = Role.model_validate(role_in)
    session.add(db_role)
    session.commit()
    session.refresh(db_role)
    return db_role

def update_role(*, session: Session, db_role: Role, role_in: RoleUpdate) -> Role:
    update_data = role_in.model_dump(exclude_unset=True)
    db_role.sqlmodel_update(update_data)
    session.add(db_role)
    session.commit()
    session.refresh(db_role)
    return db_role

def get_role_by_name(*, session: Session, name: str) -> Optional[Role]:
    statement = select(Role).where(Role.name == name)
    return session.exec(statement).first()

def get_role(*, session: Session, role_id: uuid.UUID) -> Optional[Role]:
    return session.get(Role, role_id)

def get_roles(*, session: Session, skip: int = 0, limit: int = 100) -> List[Role]:
    statement = select(Role).offset(skip).limit(limit)
    return session.exec(statement).all()

def delete_role(*, session: Session, db_role: Role) -> Role:
    session.delete(db_role)
    session.commit()
    return db_role

# ========== PROJECT LIST CRUD ==========

def create_project_list(*, session: Session, project_in: ProjectCreate) -> ProjectList:
    db_project = ProjectList.model_validate(project_in)
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    return db_project

def update_project_list(*, session: Session, db_project: ProjectList, project_in: ProjectUpdate) -> ProjectList:
    update_data = project_in.model_dump(exclude_unset=True)
    db_project.sqlmodel_update(update_data)
    session.add(db_project)
    session.commit()
    session.refresh(db_project)
    return db_project

def get_project_list(*, session: Session, project_id: uuid.UUID) -> Optional[ProjectList]:
    return session.get(ProjectList, project_id)

def get_all_project_lists(*, session: Session, skip: int = 0, limit: int = 100) -> List[ProjectList]:
    statement = select(ProjectList).offset(skip).limit(limit)
    return session.exec(statement).all()

def delete_project_list(*, session: Session, db_project: ProjectList) -> ProjectList:
    session.delete(db_project)
    session.commit()
    return db_project

# ========== USER PROJECT ROLE CRUD ==========

def add_user_to_project_role(*, session: Session, user_project_role_in: UserProjectRoleCreate) -> UserProjectRole:
    db_upr = UserProjectRole.model_validate(user_project_role_in)
    session.add(db_upr)
    session.commit()
    session.refresh(db_upr)
    return db_upr

# Kiểm tra user có đang có bất kỳ vai trò nào trong project hay không
def get_user_project_role_by_user_project(
    *, session: Session, user_id: uuid.UUID, project_id: uuid.UUID
) -> Optional[UserProjectRole]:
    statement = select(UserProjectRole).where(
        col(UserProjectRole.user_id) == user_id,
        col(UserProjectRole.project_id) == project_id
    )
    return session.exec(statement).first()

# Kiểm tra một vai trò cụ thể (role_id) có tồn tại không
def get_user_project_role(*, session: Session, user_id: uuid.UUID, project_id: uuid.UUID, role_id: uuid.UUID) -> Optional[UserProjectRole]:
    statement = select(UserProjectRole).where(
        col(UserProjectRole.user_id) == user_id,
        col(UserProjectRole.project_id) == project_id,
        col(UserProjectRole.role_id) == role_id
    )
    return session.exec(statement).first()

def delete_user_project_role(*, session: Session, db_upr: UserProjectRole) -> UserProjectRole:
    session.delete(db_upr)
    session.commit()
    return db_upr

# ========== REQUEST CRUD ==========

def create_request(
    *,
    session: Session,
    request_in: RequestCreate,
    requester_id: uuid.UUID,
    project_id: uuid.UUID  
) -> Request:
    db_request = Request.model_validate(
        request_in,
        update={
            "requester_id": requester_id,
            "project_id": project_id, 
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
    )
    session.add(db_request)
    session.commit()
    session.refresh(db_request)
    return db_request

def update_request(
    *,
    session: Session,
    db_request: Request,
    request_in: RequestUpdate,
    approver_id: uuid.UUID
) -> Request:
    update_data = request_in.model_dump(exclude_unset=True)
    update_data["approver_id"] = approver_id
    update_data["updated_at"] = datetime.utcnow()
    if "response_message" not in update_data:
        update_data["response_message"] = db_request.response_message

    db_request.sqlmodel_update(update_data)
    session.add(db_request)
    session.commit()
    session.refresh(db_request)
    return db_request

def get_request(*, session: Session, request_id: uuid.UUID) -> Optional[Request]:
    return session.get(Request, request_id)

def delete_request(*, session: Session, db_request: Request) -> Request:
    session.delete(db_request)
    session.commit()
    return db_request

# ============================== P. ECO_RETREAT========================== ===
def get_ecopark(session: Session, ecopark_id: int) -> Optional[Ecopark]:
    return session.get(Ecopark, ecopark_id)


def get_all_ecoparks(session: Session, project_id: str, skip: int = 0, limit: int = 100):
    statement = select(Ecopark).where(Ecopark.project_id == project_id).offset(skip).limit(limit)
    results = session.exec(statement).all()

    count_stmt = select(Ecopark).where(Ecopark.project_id == project_id)
    total = session.exec(count_stmt).count()
    return results, total


def create_ecopark(session: Session, ecopark_in: EcoparkCreate) -> Ecopark:
    ecopark = Ecopark.model_validate(ecopark_in)
    session.add(ecopark)
    session.commit()
    session.refresh(ecopark)
    return ecopark


def update_ecopark(session: Session, db_ecopark: Ecopark, ecopark_in: EcoparkUpdate) -> Ecopark:
    update_data = ecopark_in.model_dump(exclude_unset=True)
    db_ecopark.sqlmodel_update(update_data)
    session.add(db_ecopark)
    session.commit()
    session.refresh(db_ecopark)
    return db_ecopark


def delete_ecopark(session: Session, db_ecopark: Ecopark) -> Ecopark:
    session.delete(db_ecopark)
    session.commit()
    return db_ecopark