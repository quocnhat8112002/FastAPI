import uuid
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import pytz

from fastapi import HTTPException
from sqlalchemy import  func
from sqlmodel import Session, delete, select, col

from app.core.security import get_password_hash, verify_password
from app.models import (
    DetalEcoRetreat, DetalEcoRetreatCreate, DetalEcoRetreatUpdate, User, UserCreate, UserUpdate,
    System, SystemCreate, SystemUpdate,
    Role, RoleCreate, RoleUpdate,
    ProjectList, ProjectCreate, ProjectUpdate,
    UserProjectRole, UserProjectRoleCreate,
    Request, RequestCreate, RequestUpdate,
    Ecopark, EcoparkCreate, EcoparkUpdate,
    AdministrativeRegionCreate, AdministrativeRegionUpdate, AdministrativeRegionList,
    AdministrativeUnitCreate, AdministrativeUnitUpdate, AdministrativeUnitList,
    ProvinceCreate, ProvinceUpdate, ProvinceList,
    WardCreate, WardUpdate, WardList
)

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

def now_vn():
    return datetime.now(VN_TZ)

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

def update_project_list(*, session: Session, db_project: ProjectList, update_data: dict) -> ProjectList:
    """
    Cập nhật project hiện có trong database bằng một dictionary dữ liệu.
    - db_project: đối tượng ProjectList cần cập nhật
    - update_data: dictionary chứa dữ liệu đã được ánh xạ
    """
    for key, value in update_data.items():
        if value is not None:
            setattr(db_project, key, value)
            
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
def get_user_project_role_by_id(session: Session, id: uuid.UUID) -> Optional[UserProjectRole]:
    """
    Lấy một bản ghi UserProjectRole bằng ID của nó.
    """
    return session.get(UserProjectRole, id)

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
    now = datetime.now(VN_TZ)
    db_request = Request.model_validate(
        request_in,
        update={
            "requester_id": requester_id,
            "project_id": project_id, 
            "status": "pending",
            "created_at": now_vn(),
            "updated_at": now_vn(),
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
    request_in: dict,
    approver_id: uuid.UUID
) -> Request:
    update_data = request_in
    update_data["approver_id"] = approver_id
    update_data["updated_at"] = now_vn()

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

# ============================== DU AN ECO_RETREAT========================== ===
def get(*, session: Session, ecopark_id: uuid.UUID) -> Optional[Ecopark]:
        """
        Lấy một bản ghi Ecopark dựa trên ID (UUID) của nó.
        """
        return session.get(Ecopark, ecopark_id)

def get_by_port(*, session: Session, port: int) -> Optional[Ecopark]:
    """
    Lấy một bản ghi Ecopark dựa trên số port của nó.
    """
    statement = select(Ecopark).where(Ecopark.port == port)
    return session.exec(statement).first()

def get_all_ecopark(*, session: Session, skip: int = 0, limit: int = 100) -> List[Ecopark]:
    """
    Lấy tất cả các bản ghi Ecopark với tùy chọn phân trang.
    """
    statement = select(Ecopark).offset(skip).limit(limit)
    return session.exec(statement).all()

def get_ecopark_count(*, session: Session) -> int:
    """
    Lấy tổng số lượng bản ghi Ecopark trong database.
    """
    # Sử dụng func.count() để đếm số bản ghi một cách hiệu quả
    statement = select(func.count()).select_from(Ecopark)
    return session.exec(statement).one()

def create_ecopark(*, session: Session, ecopark_in: EcoparkCreate) -> Ecopark:
    ecopark = Ecopark.model_validate(ecopark_in)
    session.add(ecopark)
    session.commit()
    session.refresh(ecopark)
    return ecopark


def update_ecopark(*, session: Session, db_ecopark: Ecopark, ecopark_in: EcoparkUpdate) -> Ecopark:
    update_data = ecopark_in.model_dump(exclude_unset=True)
    db_ecopark.sqlmodel_update(update_data)
    session.add(db_ecopark)
    session.commit()
    session.refresh(db_ecopark)
    return db_ecopark


def delete_ecopark(*, session: Session, db_ecopark: Ecopark) -> Ecopark:
    session.delete(db_ecopark)
    session.commit()
    return db_ecopark

# ----------------------------------------------------
# CRUD for AdministrativeRegion
# ----------------------------------------------------
def create_region(*, session: Session, region_in: AdministrativeRegionCreate) -> AdministrativeRegionList:
    """Tạo một vùng hành chính mới."""
    db_region = AdministrativeRegionList.model_validate(region_in)
    session.add(db_region)
    session.commit()
    session.refresh(db_region)
    return db_region

def update_region(*, session: Session, db_region: AdministrativeRegionList, region_in: AdministrativeRegionUpdate) -> AdministrativeRegionList:
    """Cập nhật một vùng hành chính."""
    update_data = region_in.model_dump(exclude_unset=True)
    db_region.sqlmodel_update(update_data)
    session.add(db_region)
    session.commit()
    session.refresh(db_region)
    return db_region

def get_region(*, session: Session, region_id: int) -> Optional[AdministrativeRegionList]:
    """Lấy một vùng hành chính theo ID."""
    return session.get(AdministrativeRegionList, region_id)

def get_all_regions(*, session: Session, skip: int = 0, limit: int = 100) -> List[AdministrativeRegionList]:
    """Lấy tất cả các vùng hành chính."""
    statement = select(AdministrativeRegionList).offset(skip).limit(limit)
    return session.exec(statement).all()

def delete_region(*, session: Session, db_region: AdministrativeRegionList) -> AdministrativeRegionList:
    """Xóa một vùng hành chính."""
    session.delete(db_region)
    session.commit()
    return db_region

# ----------------------------------------------------
# CRUD for AdministrativeUnit
# ----------------------------------------------------
def create_unit(*, session: Session, unit_in: AdministrativeUnitCreate) -> AdministrativeUnitList:
    """Tạo một đơn vị hành chính mới."""
    db_unit = AdministrativeUnitList.model_validate(unit_in)
    session.add(db_unit)
    session.commit()
    session.refresh(db_unit)
    return db_unit

def update_unit(*, session: Session, db_unit: AdministrativeUnitList, unit_in: AdministrativeUnitUpdate) -> AdministrativeUnitList:
    """Cập nhật một đơn vị hành chính."""
    update_data = unit_in.model_dump(exclude_unset=True)
    db_unit.sqlmodel_update(update_data)
    session.add(db_unit)
    session.commit()
    session.refresh(db_unit)
    return db_unit

def get_unit(*, session: Session, unit_id: int) -> Optional[AdministrativeUnitList]:
    """Lấy một đơn vị hành chính theo ID."""
    return session.get(AdministrativeUnitList, unit_id)

def get_all_units(*, session: Session, skip: int = 0, limit: int = 100) -> List[AdministrativeUnitList]:
    """Lấy tất cả các đơn vị hành chính."""
    statement = select(AdministrativeUnitList).offset(skip).limit(limit)
    return session.exec(statement).all()

def delete_unit(*, session: Session, db_unit: AdministrativeUnitList) -> AdministrativeUnitList:
    """Xóa một đơn vị hành chính."""
    session.delete(db_unit)
    session.commit()
    return db_unit

# ----------------------------------------------------
# CRUD for Province
# ----------------------------------------------------
def create_province(*, session: Session, province_in: ProvinceCreate) -> ProvinceList:
    """Tạo một tỉnh/thành phố mới."""
    db_province = ProvinceList.model_validate(province_in)
    session.add(db_province)
    session.commit()
    session.refresh(db_province)
    return db_province

def update_province(*, session: Session, db_province: ProvinceList, province_in: ProvinceUpdate) -> ProvinceList:
    """Cập nhật một tỉnh/thành phố."""
    update_data = province_in.model_dump(exclude_unset=True)
    db_province.sqlmodel_update(update_data)
    session.add(db_province)
    session.commit()
    session.refresh(db_province)
    return db_province

def get_province(*, session: Session, province_code: str) -> Optional[ProvinceList]:
    """Lấy một tỉnh/thành phố theo mã code."""
    return session.get(ProvinceList, province_code)

def get_all_provinces(*, session: Session, skip: int = 0, limit: int = 100) -> List[ProvinceList]:
    """Lấy tất cả các tỉnh/thành phố."""
    statement = select(ProvinceList).offset(skip).limit(limit)
    return session.exec(statement).all()

def delete_province(*, session: Session, db_province: ProvinceList) -> ProvinceList:
    """Xóa một tỉnh/thành phố."""
    session.delete(db_province)
    session.commit()
    return db_province

# ----------------------------------------------------
# CRUD for Ward
# ----------------------------------------------------
def create_ward(*, session: Session, ward_in: WardCreate) -> WardList:
    """Tạo một phường/xã mới."""
    db_ward = WardList.model_validate(ward_in)
    session.add(db_ward)
    session.commit()
    session.refresh(db_ward)
    return db_ward

def update_ward(*, session: Session, db_ward: WardList, ward_in: WardUpdate) -> WardList:
    """Cập nhật một phường/xã."""
    update_data = ward_in.model_dump(exclude_unset=True)
    db_ward.sqlmodel_update(update_data)
    session.add(db_ward)
    session.commit()
    session.refresh(db_ward)
    return db_ward

def get_ward(*, session: Session, ward_code: str) -> Optional[WardList]:
    """Lấy một phường/xã theo mã code."""
    return session.get(WardList, ward_code)

def get_all_wards(*, session: Session, skip: int = 0, limit: int = 100) -> List[WardList]:
    """Lấy tất cả các phường/xã."""
    statement = select(WardList).offset(skip).limit(limit)
    return session.exec(statement).all()

def delete_ward(*, session: Session, db_ward: WardList) -> WardList:
    """Xóa một phường/xã."""
    session.delete(db_ward)
    session.commit()
    return db_ward

# ============================== DETAL ECO_RETREAT========================== ===
def get_detal_eco_retreat_by_id(session: Session, detal_id: uuid.UUID) -> Optional[DetalEcoRetreat]:
    """
    Lấy một bản ghi DetalEcoRetreat theo ID.
    """
    return session.get(DetalEcoRetreat, detal_id)

def get_detal_eco_retreats_by_ids(session: Session, detal_ids: List[uuid.UUID]) -> List[DetalEcoRetreat]:
    """
    Lấy danh sách các bản ghi DetalEcoRetreat dựa trên danh sách ID.
    """
    if not detal_ids:
        return []
    statement = select(DetalEcoRetreat).where(DetalEcoRetreat.id.in_(detal_ids))
    return session.exec(statement).all()

def get_detal_by_port_and_picture(session: Session, port: int, picture_name: str) -> Optional[DetalEcoRetreat]:
    statement = select(DetalEcoRetreat).where(
        DetalEcoRetreat.port == port,
        DetalEcoRetreat.picture == picture_name
    )
    result = session.exec(statement).first()
    return result

def get_all_detal_eco_retreats_by_ports(
    session: Session, 
    port: List[int], # Nhận một danh sách các số port
    skip: int = 0, 
    limit: int = 100
) -> Tuple[List[DetalEcoRetreat], int]:
    """
    Truy xuất danh sách tất cả các hình ảnh chi tiết thuộc về một hoặc nhiều 'port' cụ thể.
    """
    if not port:
        return [], 0 # Nếu danh sách ports rỗng, trả về kết quả rỗng

    # Xây dựng câu lệnh SELECT để lọc theo nhiều ports bằng toán tử IN
    statement = select(DetalEcoRetreat).where(DetalEcoRetreat.port.in_(port))
    
    # Lấy tổng số lượng (để phân trang)
    count_statement = select(func.count()).where(DetalEcoRetreat.port.in_(port))
    total_count = session.exec(count_statement).one()

    # Áp dụng skip và limit
    statement = statement.offset(skip).limit(limit)
    
    db_detals = session.exec(statement).all()
    return db_detals, total_count



def create_detal_eco_retreat_record(session: Session, detal_in: DetalEcoRetreatCreate) -> DetalEcoRetreat:
    """
    Tạo một bản ghi DetalEcoRetreat mới.
    Yêu cầu ít nhất một trong description_vi hoặc description_en phải có giá trị.
    """

    detal_obj = DetalEcoRetreat.model_validate(detal_in)
    session.add(detal_obj)
    session.commit()
    session.refresh(detal_obj)
    return detal_obj


def update_detal_eco_retreat_record(
    session: Session, 
    db_detal: DetalEcoRetreat, 
    update_data: Dict[str, Any] # <-- Hàm này giờ nhận một dictionary
) -> DetalEcoRetreat:
    """
    Cập nhật một bản ghi DetalEcoRetreat hiện có từ một dictionary update_data.
    Chỉ cập nhật những trường có trong update_data.
    Yêu cầu ít nhất một trong description_vi hoặc description_en phải có giá trị (sau khi cập nhật).
    """
    # sqlmodel_update sẽ chỉ cập nhật các trường có trong update_data.
    # Nếu một trường không có trong update_data, nó sẽ không bị thay đổi.
    db_detal.sqlmodel_update(update_data)
    
    # Tạo bản sao tạm thời để kiểm tra sau khi áp dụng update_data
    temp_detal = db_detal.model_copy() 

    # KIỂM TRA MÔ TẢ: Đảm bảo ít nhất một mô tả được cung cấp sau khi cập nhật
    if not temp_detal.description_vi and not temp_detal.description_en:
        raise ValueError("Sau khi cập nhật, phải có ít nhất một mô tả (tiếng Việt hoặc tiếng Anh).")

    session.add(db_detal)
    session.commit()
    session.refresh(db_detal)
    return db_detal


def delete_detal_eco_retreat_record(session: Session, db_detal: DetalEcoRetreat) -> DetalEcoRetreat:
    """
    Xóa một bản ghi DetalEcoRetreat.
    """
    session.delete(db_detal)
    session.commit()
    return db_detal

def delete_detal_eco_retreat_records_by_ids(session: Session, detal_ids: List[uuid.UUID]) -> int:
    """
    Xóa nhiều bản ghi DetalEcoRetreat dựa trên danh sách ID.
    Trả về số lượng bản ghi đã xóa.
    """
    if not detal_ids:
        return 0
    
    # Sử dụng lệnh DELETE để xóa hàng loạt
    statement = delete(DetalEcoRetreat).where(DetalEcoRetreat.id.in_(detal_ids))
    
    result = session.exec(statement)
    session.commit()
    return result.rowcount # Trả về số dòng đã bị ảnh hưởng (số bản ghi đã xóa)