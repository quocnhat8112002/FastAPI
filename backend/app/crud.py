import uuid
from typing import Any, List, Optional
from datetime import datetime

from sqlmodel import Session, select, col

from app.core.security import get_password_hash, verify_password
from app.models import (
    User, UserCreate, UserUpdate,
    Role, RoleCreate, RoleUpdate,
    ProjectList, ProjectCreate, ProjectUpdate,
    UserProjectRole, UserProjectRoleCreate,
    Request, RequestCreate, RequestUpdate
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

def create_request(*, session: Session, request_in: RequestCreate, requester_id: uuid.UUID) -> Request:
    db_request = Request.model_validate(
        request_in, update={"requester_id": requester_id}
    )
    session.add(db_request)
    session.commit()
    session.refresh(db_request)
    return db_request

def update_request(*, session: Session, db_request: Request, request_in: RequestUpdate, approver_id: uuid.UUID) -> Request:
    update_data = request_in.model_dump(exclude_unset=True)
    update_data["approver_id"] = approver_id
    update_data["updated_at"] = datetime.utcnow()
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
