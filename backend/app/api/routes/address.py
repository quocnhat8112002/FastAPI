# from typing import List, Any
# from fastapi import APIRouter, Depends, HTTPException, status
# from sqlmodel import  select, func
# from app import crud
# from app.models import (
#     AdministrativeRegionCreate,
#     AdministrativeRegionUpdate,
#     AdministrativeRegionPublic,
#     AdministrativeRegionsPublic,
#     AdministrativeRegionList
# )

# from app.api.deps import (
#     SessionDep,
#     get_current_user,
#     verify_rank_in_project,
#     CurrentUser,
#     verify_system_rank_in
# )

# router = APIRouter(prefix="/regions", tags=["Vùng Hành chính"])

# @router.get("/", response_model=AdministrativeRegionsPublic)
# def get_all_regions_endpoint(
#     session: Session = Depends(get_session), skip: int = 0, limit: int = 100
# ) -> Any:
#     """Lấy danh sách tất cả các vùng hành chính."""
#     count = session.exec(select(func.count()).select_from(AdministrativeRegionList)).one()
#     regions = session.exec(select(AdministrativeRegionList).offset(skip).limit(limit)).all()
#     return AdministrativeRegionsPublic(data=regions, count=count)

# @router.get("/{region_id}", response_model=AdministrativeRegionPublic)
# def get_region_endpoint(
#     *, session: Session = Depends(get_session), region_id: int
# ) -> Any:
#     """Lấy một vùng hành chính theo ID."""
#     region = session.get(AdministrativeRegionList, region_id)
#     if not region:
#         raise HTTPException(status_code=404, detail="Không tìm thấy vùng hành chính.")
#     return region

# @router.post("/", response_model=AdministrativeRegionPublic, status_code=status.HTTP_201_CREATED)
# def create_region_endpoint(
#     *, session: Session = Depends(get_session), region_in: AdministrativeRegionCreate
# ) -> Any:
#     """Tạo một vùng hành chính mới."""
#     region = AdministrativeRegionList.model_validate(region_in)
#     session.add(region)
#     session.commit()
#     session.refresh(region)
#     return region

# @router.put("/{region_id}", response_model=AdministrativeRegionPublic)
# def update_region_endpoint(
#     *, session: Session = Depends(get_session), region_id: int, region_in: AdministrativeRegionUpdate
# ) -> Any:
#     """Cập nhật một vùng hành chính."""
#     db_region = session.get(AdministrativeRegionList, region_id)
#     if not db_region:
#         raise HTTPException(status_code=404, detail="Không tìm thấy vùng hành chính.")
    
#     update_data = region_in.model_dump(exclude_unset=True)
#     db_region.sqlmodel_update(update_data)
#     session.add(db_region)
#     session.commit()
#     session.refresh(db_region)
#     return db_region

# @router.delete("/{region_id}", status_code=status.HTTP_204_NO_CONTENT)
# def delete_region_endpoint(
#     *, session: Session = Depends(get_session), region_id: int
# ) -> None:
#     """Xóa một vùng hành chính."""
#     db_region = session.get(AdministrativeRegionList, region_id)
#     if not db_region:
#         raise HTTPException(status_code=404, detail="Không tìm thấy vùng hành chính.")
#     session.delete(db_region)
#     session.commit()


# @router.get("/", response_model=AdministrativeUnitsPublic)
# def get_all_units_endpoint(
#     session: Session = Depends(get_session), skip: int = 0, limit: int = 100
# ) -> Any:
#     """Lấy danh sách tất cả các đơn vị hành chính."""
#     count = session.exec(select(func.count()).select_from(AdministrativeUnitList)).one()
#     units = session.exec(select(AdministrativeUnitList).offset(skip).limit(limit)).all()
#     return AdministrativeUnitsPublic(data=units, count=count)

# @router.get("/{unit_id}", response_model=AdministrativeUnitPublic)
# def get_unit_endpoint(
#     *, session: Session = Depends(get_session), unit_id: int
# ) -> Any:
#     """Lấy một đơn vị hành chính theo ID."""
#     unit = session.get(AdministrativeUnitList, unit_id)
#     if not unit:
#         raise HTTPException(status_code=404, detail="Không tìm thấy đơn vị hành chính.")
#     return unit

# @router.post("/", response_model=AdministrativeUnitPublic, status_code=status.HTTP_201_CREATED)
# def create_unit_endpoint(
#     *, session: Session = Depends(get_session), unit_in: AdministrativeUnitCreate
# ) -> Any:
#     """Tạo một đơn vị hành chính mới."""
#     unit = AdministrativeUnitList.model_validate(unit_in)
#     session.add(unit)
#     session.commit()
#     session.refresh(unit)
#     return unit

# @router.put("/{unit_id}", response_model=AdministrativeUnitPublic)
# def update_unit_endpoint(
#     *, session: Session = Depends(get_session), unit_id: int, unit_in: AdministrativeUnitUpdate
# ) -> Any:
#     """Cập nhật một đơn vị hành chính."""
#     db_unit = session.get(AdministrativeUnitList, unit_id)
#     if not db_unit:
#         raise HTTPException(status_code=404, detail="Không tìm thấy đơn vị hành chính.")
    
#     update_data = unit_in.model_dump(exclude_unset=True)
#     db_unit.sqlmodel_update(update_data)
#     session.add(db_unit)
#     session.commit()
#     session.refresh(db_unit)
#     return db_unit

# @router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
# def delete_unit_endpoint(
#     *, session: Session = Depends(get_session), unit_id: int
# ) -> None:
#     """Xóa một đơn vị hành chính."""
#     db_unit = session.get(AdministrativeUnitList, unit_id)
#     if not db_unit:
#         raise HTTPException(status_code=404, detail="Không tìm thấy đơn vị hành chính.")
#     session.delete(db_unit)
#     session.commit()


# @router.get("/", response_model=ProvincesPublic)
# def get_all_provinces_endpoint(
#     session: Session = Depends(get_session), skip: int = 0, limit: int = 100
# ) -> Any:
#     """Lấy danh sách tất cả các tỉnh/thành phố."""
#     count = session.exec(select(func.count()).select_from(ProvinceList)).one()
#     provinces = session.exec(select(ProvinceList).offset(skip).limit(limit)).all()
#     return ProvincesPublic(data=provinces, count=count)

# @router.get("/{province_code}", response_model=ProvincePublic)
# def get_province_endpoint(
#     *, session: Session = Depends(get_session), province_code: str
# ) -> Any:
#     """Lấy một tỉnh/thành phố theo mã code."""
#     province = session.get(ProvinceList, province_code)
#     if not province:
#         raise HTTPException(status_code=404, detail="Không tìm thấy tỉnh/thành phố.")
#     return province

# @router.post("/", response_model=ProvincePublic, status_code=status.HTTP_201_CREATED)
# def create_province_endpoint(
#     *, session: Session = Depends(get_session), province_in: ProvinceCreate
# ) -> Any:
#     """Tạo một tỉnh/thành phố mới."""
#     province = ProvinceList.model_validate(province_in)
#     session.add(province)
#     session.commit()
#     session.refresh(province)
#     return province

# @router.put("/{province_code}", response_model=ProvincePublic)
# def update_province_endpoint(
#     *, session: Session = Depends(get_session), province_code: str, province_in: ProvinceUpdate
# ) -> Any:
#     """Cập nhật một tỉnh/thành phố."""
#     db_province = session.get(ProvinceList, province_code)
#     if not db_province:
#         raise HTTPException(status_code=404, detail="Không tìm thấy tỉnh/thành phố.")
    
#     update_data = province_in.model_dump(exclude_unset=True)
#     db_province.sqlmodel_update(update_data)
#     session.add(db_province)
#     session.commit()
#     session.refresh(db_province)
#     return db_province

# @router.delete("/{province_code}", status_code=status.HTTP_204_NO_CONTENT)
# def delete_province_endpoint(
#     *, session: Session = Depends(get_session), province_code: str
# ) -> None:
#     """Xóa một tỉnh/thành phố."""
#     db_province = session.get(ProvinceList, province_code)
#     if not db_province:
#         raise HTTPException(status_code=404, detail="Không tìm thấy tỉnh/thành phố.")
#     session.delete(db_province)
#     session.commit()


# @router.get("/", response_model=WardsPublic)
# def get_all_wards_endpoint(
#     session: Session = Depends(get_session), skip: int = 0, limit: int = 100
# ) -> Any:
#     """Lấy danh sách tất cả các phường/xã."""
#     count = session.exec(select(func.count()).select_from(WardList)).one()
#     wards = session.exec(select(WardList).offset(skip).limit(limit)).all()
#     return WardsPublic(data=wards, count=count)

# @router.get("/{ward_code}", response_model=WardPublic)
# def get_ward_endpoint(
#     *, session: Session = Depends(get_session), ward_code: str
# ) -> Any:
#     """Lấy một phường/xã theo mã code."""
#     ward = session.get(WardList, ward_code)
#     if not ward:
#         raise HTTPException(status_code=404, detail="Không tìm thấy phường/xã.")
#     return ward

# @router.post("/", response_model=WardPublic, status_code=status.HTTP_201_CREATED)
# def create_ward_endpoint(
#     *, session: Session = Depends(get_session), ward_in: WardCreate
# ) -> Any:
#     """Tạo một phường/xã mới."""
#     ward = WardList.model_validate(ward_in)
#     session.add(ward)
#     session.commit()
#     session.refresh(ward)
#     return ward

# @router.put("/{ward_code}", response_model=WardPublic)
# def update_ward_endpoint(
#     *, session: Session = Depends(get_session), ward_code: str, ward_in: WardUpdate
# ) -> Any:
#     """Cập nhật một phường/xã."""
#     db_ward = session.get(WardList, ward_code)
#     if not db_ward:
#         raise HTTPException(status_code=404, detail="Không tìm thấy phường/xã.")
    
#     update_data = ward_in.model_dump(exclude_unset=True)
#     db_ward.sqlmodel_update(update_data)
#     session.add(db_ward)
#     session.commit()
#     session.refresh(db_ward)
#     return db_ward

# @router.delete("/{ward_code}", status_code=status.HTTP_204_NO_CONTENT)
# def delete_ward_endpoint(
#     *, session: Session = Depends(get_session), ward_code: str
# ) -> None:
#     """Xóa một phường/xã."""
#     db_ward = session.get(WardList, ward_code)
#     if not db_ward:
#         raise HTTPException(status_code=404, detail="Không tìm thấy phường/xã.")
#     session.delete(db_ward)
#     session.commit()