from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import EmailStr
from sqlmodel import BigInteger, SQLModel, Field


# === USER ===

# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = False
    is_superuser: bool = False
    full_name: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)

# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)


# Properties to receive via API on update
class UserUpdate(UserBase):
    email: Optional[EmailStr] = Field(default=None, max_length=255)  # type: ignore
    password: Optional[str] = Field(default=None, min_length=8, max_length=40)
    system_id: Optional[uuid.UUID] = None

class UserUpdateMe(SQLModel):
    full_name: Optional[str] = Field(default=None, max_length=255)
    email: Optional[EmailStr] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)


# Password change schema
class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    creation_time: datetime = Field(default_factory=datetime.utcnow)
    role_assignment_time: Optional[datetime] = None
    last_login: Optional[datetime] = None
    last_logout: Optional[datetime] = None
    system_rank: Optional[int] = Field(default=None)

# Return schema
class UserPublic(UserBase):
    id: uuid.UUID
    creation_time: datetime
    last_login: Optional[datetime] = None
    last_logout: Optional[datetime] = None
    system_rank: Optional[int] = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int

# === SYSTEM ===
class SystemBase(SQLModel):
    rank_total: int
    description: Optional[str] = None

class SystemCreate(SystemBase):
    pass

class SystemUpdate(SystemBase):
    pass

class System(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rank_total: int
    description: Optional[str] = None

class SystemPublic(SystemBase):
    id: uuid.UUID

class SystemsPublic(SQLModel):
    data: list[SystemPublic]
    count: int


# === PROJECT ===

class ProjectBase(SQLModel):
    name: str
    address: Optional[str] = None
    type: Optional[str] = None
    investor: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(ProjectBase):
    pass


class ProjectList(ProjectBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class ProjectPublic(ProjectBase):
    id: uuid.UUID


class ProjectsPublic(SQLModel):
    data: list[ProjectPublic]
    count: int


# === ROLE ===

class RoleBase(SQLModel):
    name: str
    rank: int
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(SQLModel):
    name: Optional[str] = None
    rank: Optional[int] = None
    description: Optional[str] = None


class Role(RoleBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class RolePublic(RoleBase):
    id: uuid.UUID


class RolesPublic(SQLModel):
    data: list[RolePublic]
    count: int


# === USER-PROJECT-ROLE ===

class UserProjectRole(SQLModel, table=True):
    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projectlist.id", primary_key=True)
    role_id: uuid.UUID = Field(foreign_key="role.id", primary_key=True)


class UserProjectRoleCreate(SQLModel):
    user_id: uuid.UUID
    project_id: uuid.UUID
    role_id: uuid.UUID


class UserProjectRoleUpdate(SQLModel):
    role_id: Optional[uuid.UUID] = None


class UserProjectRolePublic(SQLModel):
    user_id: uuid.UUID
    project_id: uuid.UUID
    role_id: uuid.UUID


# === REQUEST ===

class RequestStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Request(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    project_id: uuid.UUID = Field(foreign_key="projectlist.id", index=True)
    role_id: uuid.UUID = Field(foreign_key="role.id", index=True)
    requester_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    approver_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id", nullable=True)
    status: RequestStatus = Field(default=RequestStatus.pending)
    request_message: Optional[str] = None
    response_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class RequestCreate(SQLModel):
    role_id: uuid.UUID
    request_message: Optional[str] = None


class RequestUpdate(SQLModel):
    status: Optional[RequestStatus] = None
    response_message: Optional[str] = None
    approver_id: Optional[uuid.UUID] = None


class RequestPublic(SQLModel):
    id: uuid.UUID
    project_id: uuid.UUID
    role_id: uuid.UUID
    requester_id: uuid.UUID
    approver_id: Optional[uuid.UUID] = None
    status: RequestStatus
    request_message: Optional[str] = None
    response_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class RequestsPublic(SQLModel):
    data: list[RequestPublic]
    count: int


# === AUTH / COMMON SCHEMAS ===

class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: Optional[str] = None
    is_active: bool | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)


class Message(SQLModel):
    message: str


# ============================== P. ECO_RETREAT========================== ===

class EcoparkBase(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    building_name: Optional[str]
    picture_name: Optional[str]
    building_type_vi: Optional[str]
    building_type_en: Optional[str]
    amenity_type_vi: Optional[str]
    amenity_type_en: Optional[str]
    zone_name_vi: Optional[str]
    zone_name_en: Optional[str]
    zone: Optional[str]
    amenity: Optional[str]
    direction_vi: Optional[str]
    bedroom: Optional[int]
    price: Optional[int]
    status_vi: Optional[str]
    direction_en: Optional[str]
    status_en: Optional[str]

class EcoparkCreate(EcoparkBase):
    project_id: uuid.UUID

class EcoparkUpdate(EcoparkBase):
    pass

class EcoparkPublic(EcoparkBase):
    id: int
    project_id: uuid.UUID

class Ecopark(EcoparkBase, table=True):
    price: Optional[int] = Field(default=None, sa_type=BigInteger)
    project_id: uuid.UUID = Field(foreign_key="projectlist.id") 