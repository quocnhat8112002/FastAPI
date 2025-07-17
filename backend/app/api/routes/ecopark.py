from typing import Annotated, Any, List, Optional
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Path, UploadFile, File, Depends, HTTPException, Query, status, Request
from sqlalchemy import func
from sqlmodel import select

from app import crud
from app.models import Ecopark, EcoparkCreate, EcoparkUpdate, EcoparkPublic
from app.api.deps import get_current_user, SessionDep, verify_rank_in_project
from app import crud
from app.api import deps
import json
import os
import re
from fastapi.staticfiles import StaticFiles
from app.core.mqtt import publish

from app.api.deps import (
    SessionDep,
    ProjectAccessInfo,
    CurrentUser,
    get_current_active_user,
    get_current_user,
    get_current_active_superuser,
    verify_system_rank_in
)

ECO_PARK_TOPIC_ONE = 'ecopark/192.168.100.101/request/one'
ECO_PARK_TOPIC_ALL = 'ecopark/192.168.100.101/request/all'
ECO_PARK_TOPIC_EFF = 'ecopark/192.168.100.101/request/eff'

PROJECT_FOLDER = "EcoRetreat"
STATIC_URL_PREFIX = "/static"

router = APIRouter(prefix="/ecopark", tags=["ecopark"])

def build_flat_image_url(request: Request, picture_name: Optional[str]) -> Optional[str]:
    if not picture_name:
        return None
    base = str(request.base_url).rstrip("/")
    return f"{base}{STATIC_URL_PREFIX}/{PROJECT_FOLDER}/{picture_name}.png"

@router.get("/", response_model=list[EcoparkPublic], dependencies=[Depends(get_current_active_superuser)])
def list_ecoparks(
    session: SessionDep,
    project_id: UUID = Query(...),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    data, _ = crud.get_all_ecoparks(session, project_id=project_id, skip=skip, limit=limit)
    return data


@router.post("/", response_model=EcoparkPublic, status_code=201, dependencies=[Depends(get_current_active_superuser)])
def create_ecopark(
    *,
    session: SessionDep,
    ecopark_in: EcoparkCreate
) -> Any:
    return crud.create_ecopark(session=session, ecopark_in=ecopark_in)


@router.put("/{ecopark_id}", response_model=EcoparkPublic, dependencies=[Depends(get_current_active_superuser)])
def update_ecopark(
    *,
    session: SessionDep,
    ecopark_id: int,
    ecopark_in: EcoparkUpdate
) -> Any:
    db_ecopark = crud.get_ecopark(session, ecopark_id)
    if not db_ecopark:
        raise HTTPException(status_code=404, detail="Không tìm thấy ecopark")
    return crud.update_ecopark(session, db_ecopark, ecopark_in)


@router.delete("/{ecopark_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(get_current_active_superuser)])
def delete_ecopark(
    *,
    session: SessionDep,
    ecopark_id: int,
) -> None:
    db_ecopark = crud.get_ecopark(session, ecopark_id)
    if not db_ecopark:
        raise HTTPException(status_code=404, detail="Không tìm thấy ecopark")
    crud.delete_ecopark(session, db_ecopark)


@router.post("/{project_id}/upload", response_model=dict, dependencies=[Depends(get_current_active_superuser)],)
def upload_excel(
    *,
    session: SessionDep,
    project_id: UUID = Path(...),
    file: UploadFile = File(...),
) -> dict:
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ .xlsx")

    df = pd.read_excel(file.file)

    for _, row in df.iterrows():
        try:
            row_id = int(row["id"]) if not pd.isna(row["id"]) else None
            ecopark_data = EcoparkCreate(
                id=row_id,
                project_id=project_id,
                building_name=row.get("building_name") if not pd.isna(row.get("building_name")) else None,
                picture_name=row.get("picture_name") if not pd.isna(row.get("picture_name")) else None,
                building_type=row.get("building_type") if not pd.isna(row.get("building_type")) else None,
                building_type_en=row.get("building_type_en") if not pd.isna(row.get("building_type_en")) else None,
                amenity_type=row.get("amenity_type") if not pd.isna(row.get("amenity_type")) else None,
                amenity_type_en=row.get("amenity_type_en") if not pd.isna(row.get("amenity_type_en")) else None,
                zone_name=row.get("zone_name") if not pd.isna(row.get("zone_name")) else None,
                zone_name_en=row.get("zone_name_en") if not pd.isna(row.get("zone_name_en")) else None,
                zone=row.get("zone") if not pd.isna(row.get("zone")) else None,
                amenity=row.get("amenity") if not pd.isna(row.get("amenity")) else None,
                direction=row.get("direction") if not pd.isna(row.get("direction")) else None,
                bedroom=row.get("bedroom") if not pd.isna(row.get("bedroom")) else None,
                price=int(row["price"]) if not pd.isna(row.get("price")) else None,
                status=row.get("status") if not pd.isna(row.get("status")) else None,
                direction_en=row.get("direction_en") if not pd.isna(row.get("direction_en")) else None,
                status_en=row.get("status_en") if not pd.isna(row.get("status_en")) else None,
            )


            if row_id:
                existing = crud.get_ecopark(session, row_id)
                if existing and existing.project_id == project_id:
                    crud.update_ecopark(session, existing, ecopark_data)
                else:
                    crud.create_ecopark(session, ecopark_data)
            else:
                crud.create_ecopark(session, ecopark_data)

        except Exception as e:
            # Có thể log e nếu cần
            continue

    return {"message": "Đã xử lý file Excel thành công."}


@router.get(
    "/{project_id}/filter_options",
    status_code=status.HTTP_200_OK,
    response_model=dict,
)
def get_filter_options(
    *,
    session: SessionDep,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))]
    ) -> Any:
    """
    Trả về danh sách giá trị không trùng lặp của các trường lọc trong Ecopark.
    """
    def clean_values(column):
        invalids = {"", " ", "NaN", "nan", "null", "None", "N", "-", "--"}
        query = session.exec(select(column).distinct()).all()
        results = [r for (r,) in query if r is not None and str(r).strip() not in invalids]
        return sorted(results)

    return {
        "status": clean_values(Ecopark.status),
        "price": clean_values(Ecopark.price, is_numeric=True),
        "bedroom": clean_values(Ecopark.bedroom, is_numeric=True),
        "direction": clean_values(Ecopark.direction),
        "building_type": clean_values(Ecopark.building_type),
        "zone_name": clean_values(Ecopark.zone_name),
        "amenity_type": clean_values(Ecopark.amenity_type),
    }

@router.post(
    "/{project_id}/filter",
    response_model=list[EcoparkPublic],
)
def filter_ecopark_by_json(
    *,
    request: Request,
    session: SessionDep,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    payload: dict
) -> Any:
    """
    Lọc ecopark theo điều kiện động từ JSON.
    """
    query = select(Ecopark)
    conditions = []

    min_price = payload.get("min_price")
    max_price = payload.get("max_price")

    try:
        if min_price is not None:
            conditions.append(Ecopark.price >= int(min_price))
        if max_price is not None:
            conditions.append(Ecopark.price <= int(max_price))
    except ValueError:
        raise HTTPException(status_code=400, detail="min_price and max_price must be numeric")

    skip_price_filter = "min_price" in payload or "max_price" in payload

    for key, value in payload.items():
        if not value or key in ["min_price", "max_price"]:
            continue

        if not hasattr(Ecopark, key):
            raise HTTPException(status_code=400, detail=f"Invalid filter field: {key}")

        col = getattr(Ecopark, key)

        if key == "price" and not skip_price_filter:
            if isinstance(value, str) and "-" in value:
                try:
                    min_val, max_val = map(int, value.split("-"))
                    conditions.append(Ecopark.price >= min_val)
                    conditions.append(Ecopark.price <= max_val)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid price range format")
            else:
                try:
                    conditions.append(col == int(value))
                except ValueError:
                    raise HTTPException(status_code=400, detail="Price must be numeric")
        elif key == "bedroom":
            conditions.append(col == int(value))
        else:
            conditions.append(col == str(value))

    results = session.exec(query.where(*conditions)).all()
    ids = [r.id for r in results if r.id]

    if ids:
        publish(ECO_PARK_TOPIC_ONE, {"channels": ids, "value": 1})

    return [EcoparkPublic.model_validate(r).model_dump() for r in results]

def search_and_publish(
    session: SessionDep,
    request: Request,
    filters: dict[str, str],
) -> list[Ecopark]:
    try:
        conditions = []
        for field, raw_value in filters.items():
            if not hasattr(Ecopark, field):
                raise HTTPException(status_code=400, detail=f"Invalid field: {field}")

            col = getattr(Ecopark, field)

            value: Any = raw_value.strip()

            # Tự động ép kiểu
            if field.endswith("_id"):
                try:
                    value = UUID(value)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid UUID for field {field}")
            elif value.isdigit():
                value = int(value)
            elif value.lower() in ("true", "false"):
                value = value.lower() == "true"

            # LIKE hoặc bằng
            if isinstance(value, str):
                conditions.append(col.ilike(f"%{value}%"))
            else:
                conditions.append(col == value)

        stmt = select(Ecopark).where(*conditions)
        results = session.exec(stmt).all()

        # MQTT publish nếu có kết quả
        ids = [r.id for r in results if r.id]
        if ids:
            publish(ECO_PARK_TOPIC_ONE, {"channels": ids, "value": 1})

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")
    
@router.get(
    "/{project_id}/amenity/{amenity}",
    response_model=dict,
)
def ecopark_search_by_amenity(
    *,
    session: SessionDep,
    request: Request,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    amenity: str,
) -> Any:
    results = search_and_publish(session, request, {
        'amenity': amenity,
        'project_id': str(project_id)
    })

    items = [EcoparkPublic.model_validate(r) for r in results]
    image_url = f"{str(request.base_url).rstrip('/')}/static/EcoRetreat/he_thong_tien_ich.png"

    return {
        "items": items,
        "image_url": image_url
    }

@router.get(
    "/{project_id}/amenity/{amenity}/{amenity_type}",
)
def ecopark_search_by_amenity_and_type(
    *,
    session: SessionDep,
    request: Request,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    amenity: str,
    amenity_type: str,
) -> Any:
    results = search_and_publish(session, request, {
        'amenity': amenity,
        'amenity_type': amenity_type,
        'project_id': str(project_id)
    })

    return [
        {
            **EcoparkPublic.model_validate(r).model_dump(),
            "image_url": build_flat_image_url(request, r.picture_name)
        }
        for r in results
    ]

@router.get(
    "/{project_id}/zone/{zone}",
)
def ecopark_search_by_zone(
    *,
    session: SessionDep,
    request: Request,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    zone: str,
) -> Any:
    results = search_and_publish(session, request,{
        'zone': zone,
        'project_id': str(project_id)
    })

    base_url = str(request.base_url).rstrip("/")
    default_image_url = f"{base_url}/static/EcoRetreat/pk.png"

    return [
        {
            **EcoparkPublic.model_validate(r).model_dump(),
            "image_url": build_flat_image_url(request, r.picture_name)
        }
        for r in results
    ]

def extract_zone_number(zone_name: str) -> str:
    match = re.search(r"Phân\s*Khu\s*(\d+)", zone_name, re.IGNORECASE)
    return match.group(1) if match else ""

def normalize_building_type(building_type: str) -> str:
    mapping = {
        "Biệt Thự Đơn Lập": "don_lap",
        "Biệt Thự Song Lập": "song_lap",
        "Shophouse": "shophouse",
        "Townhouse": "townhouse",
        "Residences": "residences",
    }
    return mapping.get(building_type.strip(), "unknown")

@router.get(
    "/{project_id}/zone/{zone}/{zone_name}",
)
def ecopark_search_by_zone_and_name(
    *,
    session: SessionDep,
    request: Request,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    zone: str,
    zone_name: str,
) -> Any:
    results = search_and_publish(session, request, {
        'zone': zone,
        'zone_name': zone_name,
        'project_id': str(project_id)
    })

    zone_number = extract_zone_number(zone_name)
    filename = f"pk_{zone_number}.png" if zone_number else "pk.png"
    image_url = f"{str(request.base_url).rstrip('/')}/static/EcoRetreat/{filename}"

    return [
        {
            **EcoparkPublic.model_validate(r).model_dump(),
            "image_url": image_url
        }
        for r in results
    ]

@router.get(
    "/{project_id}/zone/{zone}/{zone_name}/{building_type}",
)
def ecopark_search_by_zone_name_type(
    *,
    session: SessionDep,
    request: Request,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    zone: str,
    zone_name: str,
    building_type: str,
) -> Any:
    results = search_and_publish(session, request, {
        'zone': zone,
        'zone_name': zone_name,
        'building_type': building_type,
        'project_id': str(project_id)
    })

    zone_number = extract_zone_number(zone_name)
    building_code = normalize_building_type(building_type)
    image_name = f"{zone_number}_{building_code}.png" if zone_number and building_code != "unknown" else "pk.png"
    image_url = f"{str(request.base_url).rstrip('/')}/static/EcoRetreat/{image_name}"

    return [
        {
            **EcoparkPublic.model_validate(r).model_dump(),
            "image_url": image_url
        }
        for r in results
    ]

@router.get(
    "/{project_id}/zone/{zone}/{zone_name}/{building_type}/{building_name}",
)
def ecopark_search_by_full_path(
    *,
    session: SessionDep,
    request: Request,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    zone: str,
    zone_name: str,
    building_type: str,
    building_name: str,
) -> Any:
    results = search_and_publish(session, request, {
        'zone': zone,
        'zone_name': zone_name,
        'building_type': building_type,
        'building_name': building_name,
        'project_id': str(project_id)
    })

    base_url = str(request.base_url).rstrip("/")
    folder = "EcoRetreat"

    return [
        {
            **EcoparkPublic.model_validate(r).model_dump(),
            "image_url": build_flat_image_url(request, r.picture_name)
        }
        for r in results
    ]
