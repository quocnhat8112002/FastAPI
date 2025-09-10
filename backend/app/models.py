from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr
from sqlmodel import BigInteger, SQLModel, Field

from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

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
    name: Optional[str] = None
    rank_total: int
    description: Optional[str] = None

class SystemCreate(SystemBase):
    pass

class SystemUpdate(SystemBase):
    pass

class System(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: Optional[str] = None
    rank_total: int
    description: Optional[str] = None

class SystemPublic(SystemBase):
    id: uuid.UUID

class SystemsPublic(SQLModel):
    data: list[SystemPublic]
    count: int


# === PROJECT ===

class ProjectBase(SQLModel):
    name_vi: Optional[str] = None
    name_en: Optional[str] = None
    address_vi: Optional[str] = None
    address_en: Optional[str] = None
    type_vi: Optional[str] = None
    type_en: Optional[str] = None
    investor_vi: Optional[str] = None
    investor_en: Optional[str] = None
    picture: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(SQLModel):
    name: Optional[str] = None
    address: Optional[str] = None
    type: Optional[str] = None
    investor: Optional[str] = None
    picture: Optional[str] = None


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
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    project_id: uuid.UUID = Field(foreign_key="projectlist.id", index=True)
    role_id: uuid.UUID = Field(foreign_key="role.id", index=True)


class UserProjectRoleCreate(SQLModel):
    user_id: uuid.UUID
    project_id: uuid.UUID
    role_id: uuid.UUID


class UserProjectRoleUpdate(SQLModel):
    role_id: Optional[uuid.UUID] = None


class UserProjectRolePublic(SQLModel):
    id: uuid.UUID
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
    request_message_vi: Optional[str] = None
    request_message_en: Optional[str] = None
    response_message_vi: Optional[str] = None
    response_message_en: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(VN_TZ))
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


# ----------------------------------------------------
# AdministrativeRegion - Vùng Hành chính
# ----------------------------------------------------
class AdministrativeRegionBase(SQLModel):
    name_vi: str = Field(max_length=255)
    name_en: str = Field(max_length=255)
    code_name: Optional[str] = Field(default=None, max_length=255)
    code_name_en: Optional[str] = Field(default=None, max_length=255)

class AdministrativeRegionCreate(AdministrativeRegionBase):
    pass

class AdministrativeRegionUpdate(SQLModel):
    name_vi: Optional[str] = None
    name_en: Optional[str] = None
    code_name: Optional[str] = None
    code_name_en: Optional[str] = None

class AdministrativeRegionList(AdministrativeRegionBase, table=True):
    id: int = Field(primary_key=True)

class AdministrativeRegionPublic(AdministrativeRegionBase):
    id: int

class AdministrativeRegionsPublic(SQLModel):
    data: List[AdministrativeRegionPublic]
    count: int

# ----------------------------------------------------
# AdministrativeUnit - Đơn vị Hành chính
# ----------------------------------------------------
class AdministrativeUnitBase(SQLModel):
    full_name_vi: Optional[str] = Field(default=None, max_length=255)
    full_name_en: Optional[str] = Field(default=None, max_length=255)
    short_name_vi: Optional[str] = Field(default=None, max_length=255)
    short_name_en: Optional[str] = Field(default=None, max_length=255)
    code_name: Optional[str] = Field(default=None, max_length=255)
    code_name_en: Optional[str] = Field(default=None, max_length=255)

class AdministrativeUnitCreate(AdministrativeUnitBase):
    pass

class AdministrativeUnitUpdate(SQLModel):
    full_name_vi: Optional[str] = None
    full_name_en: Optional[str] = None
    short_name_vi: Optional[str] = None
    short_name_en: Optional[str] = None
    code_name: Optional[str] = None
    code_name_en: Optional[str] = None

class AdministrativeUnitList(AdministrativeUnitBase, table=True):
    id: int = Field(primary_key=True)

class AdministrativeUnitPublic(AdministrativeUnitBase):
    id: int

class AdministrativeUnitsPublic(SQLModel):
    data: List[AdministrativeUnitPublic]
    count: int

# ----------------------------------------------------
# Province - Tỉnh/Thành phố
# ----------------------------------------------------
class ProvinceBase(SQLModel):
    name_vi: str = Field(max_length=255)
    name_en: Optional[str] = Field(default=None, max_length=255)
    full_name_vi: str = Field(max_length=255)
    full_name_en: Optional[str] = Field(default=None, max_length=255)
    code_name: Optional[str] = Field(default=None, max_length=255)
    administrative_unit_id: Optional[int] = Field(default=None, foreign_key="administrativeunitlist.id")

class ProvinceCreate(ProvinceBase):
    pass

class ProvinceUpdate(ProvinceBase):
    pass

class ProvinceList(ProvinceBase, table=True):
    code: str = Field(primary_key=True, max_length=20)

class ProvincePublic(ProvinceBase):
    code: str

class ProvincesPublic(SQLModel):
    data: List[ProvincePublic]
    count: int

# ----------------------------------------------------
# Ward - Phường/Xã
# ----------------------------------------------------
class WardBase(SQLModel):
    name_vi: str = Field(max_length=255)
    name_en: Optional[str] = Field(default=None, max_length=255)
    full_name_vi: Optional[str] = Field(default=None, max_length=255)
    full_name_en: Optional[str] = Field(default=None, max_length=255)
    code_name: Optional[str] = Field(default=None, max_length=255)
    province_code: Optional[str] = Field(default=None, foreign_key="provincelist.code")
    administrative_unit_id: Optional[int] = Field(default=None, foreign_key="administrativeunitlist.id")

class WardCreate(WardBase):
    pass

class WardUpdate(WardBase):
    pass

class WardList(WardBase, table=True):
    code: str = Field(primary_key=True, max_length=20)

class WardPublic(WardBase):
    code: str

class WardsPublic(SQLModel):
    data: List[WardPublic]
    count: int
    
# ============================== DU AN: ECO_RETREAT========================== ===

class EcoparkBase(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    port: int = Field(index=True, unique=True)
    building_name: Optional[str] = None
    picture_name: Optional[str] = None
    building_type_vi: Optional[str] = None
    building_type_en: Optional[str] = None
    amenity_type_vi: Optional[str] = None
    amenity_type_en: Optional[str] = None
    zone_name_vi: Optional[str] = None
    zone_name_en: Optional[str] = None
    zone: Optional[str] = None
    amenity: Optional[str] = None
    direction_vi: Optional[str] = None
    bedroom: Optional[int] = None
    price: Optional[int] = None
    status_vi: Optional[str] = None
    direction_en: Optional[str] = None
    status_en: Optional[str] = None
    description_vi: Optional[str] = None
    description_en: Optional[str] = None

class EcoparkCreate(EcoparkBase):
    port: int

class EcoparkUpdate(EcoparkBase):
    id: Optional[uuid.UUID] = None 
    port: Optional[int] = None

class EcoparkPublic(EcoparkBase):
    pass 

class Ecopark(EcoparkBase, table=True):
    price: Optional[int] = Field(default=None, sa_type=BigInteger)

# === Detal Eco Retreat ===
class DetalEcoRetreatBase(SQLModel):
    port: int = Field(foreign_key="ecopark.port", index=True)

    picture: str
    description_vi: Optional[str] = None
    description_en: Optional[str] = None

class DetalEcoRetreatCreate(DetalEcoRetreatBase):
    port: int

class DetalEcoRetreatUpdate(SQLModel):
    picture: Optional[str] 
    description_vi: Optional[str] 
    description_en: Optional[str] 

class DetalEcoRetreat(DetalEcoRetreatBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    

class DetalEcoRetreatPublic(SQLModel):
    id: uuid.UUID
    port: int
    picture: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None

class DetalEcoRetreatResponse(BaseModel):
    """
    Schema phản hồi cho danh sách các ảnh chi tiết có phân trang.
    Bao gồm danh sách các đối tượng ảnh và tổng số lượng.
    """
    items: List[DetalEcoRetreatPublic]  
    total: int                         
