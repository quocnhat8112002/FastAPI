from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID
import uuid

import pandas as pd
from fastapi import APIRouter, Form, Path, UploadFile, File, Depends, HTTPException, Query, status, Request
from sqlalchemy import func
from sqlmodel import select

from app import crud
from app.models import DetalEcoRetreatCreate, DetalEcoRetreatPublic, DetalEcoRetreatUpdate, Ecopark, EcoparkCreate, EcoparkUpdate, EcoparkPublic
from app.api.deps import get_current_user, SessionDep, verify_rank_in_project
from app import crud
from app.api import deps
import json
import os
import re
from fastapi.staticfiles import StaticFiles
from app.core.mqtt import publish
from pathlib import Path as PPath

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
STATIC_URL_PREFIX = "/api/v1/static"

router = APIRouter(prefix="/ecopark", tags=["ecopark"])


def build_flat_image_url(request: Request, picture_name: Optional[str]) -> Optional[str]:
    if not picture_name:
        return None
    base = str(request.base_url).rstrip("/")
    return f"{base}{STATIC_URL_PREFIX}/{PROJECT_FOLDER}/{picture_name}.png"


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
                building_type_vi=row.get("building_type_vi") if not pd.isna(row.get("building_type_vi")) else None,
                building_type_en=row.get("building_type_en") if not pd.isna(row.get("building_type_en")) else None,
                amenity_type_vi=row.get("amenity_type_vi") if not pd.isna(row.get("amenity_type_vi")) else None,
                amenity_type_en=row.get("amenity_type_en") if not pd.isna(row.get("amenity_type_en")) else None,
                zone_name_vi=row.get("zone_name_vi") if not pd.isna(row.get("zone_name_vi")) else None,
                zone_name_en=row.get("zone_name_en") if not pd.isna(row.get("zone_name_en")) else None,
                zone=row.get("zone") if not pd.isna(row.get("zone")) else None,
                amenity=row.get("amenity") if not pd.isna(row.get("amenity")) else None,
                direction_vi=row.get("direction_vi") if not pd.isna(row.get("direction_vi")) else None,
                bedroom=row.get("bedroom") if not pd.isna(row.get("bedroom")) else None,
                price=int(row["price"]) if not pd.isna(row.get("price")) else None,
                status_vi=row.get("status_vi") if not pd.isna(row.get("status_vi")) else None,
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
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (e.g., 'vi' or 'en')"),
    ) -> Any:
    """
    Trả về danh sách giá trị không trùng lặp của các trường lọc trong Ecopark.
    """
    def clean_values(column_for_lang: Any, numerical_column: Optional[Any] = None): 
        invalids = {"", " ", "NaN", "nan", "null", "None", "N", "-", "--"}
        
        if numerical_column is not None:
            column_to_query = numerical_column
        else:
            column_to_query = column_for_lang

        query_results = session.exec(select(column_to_query).distinct()).all()
        results = [r for r in query_results if r is not None and str(r).strip() not in invalids]
        
        if numerical_column is not None: 
            try:
                return sorted([int(r) for r in results]) 
            except ValueError:
                return sorted(results)
        return sorted(results)

    status_col = Ecopark.status_vi if lang == 'vi' else Ecopark.status_en
    direction_col = Ecopark.direction_vi if lang == 'vi' else Ecopark.direction_en
    building_type_col = Ecopark.building_type_vi if lang == 'vi' else Ecopark.building_type_en
    zone_name_col = Ecopark.zone_name_vi if lang == 'vi' else Ecopark.zone_name_en
    amenity_type_col = Ecopark.amenity_type_vi if lang == 'vi' else Ecopark.amenity_type_en

    return {
        "status": clean_values(status_col),
        "price": clean_values(None, Ecopark.price), 
        "bedroom": clean_values(None, Ecopark.bedroom), 
        "direction": clean_values(direction_col),
        "building_type": clean_values(building_type_col),
        "zone_name": clean_values(zone_name_col),
        "amenity_type": clean_values(amenity_type_col),
    }


@router.post(
    "/{project_id}/filter",
    response_model=List[Dict[str, Any]],
)
def filter_ecopark_by_json(
    *,
    request: Request,
    session: SessionDep,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    payload: Dict[str, Any],
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (e.g., 'vi' or 'en')"),
) -> List[Dict[str, Any]]:
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
        if not value or key in ["min_price", "max_price", "lang"]:
            continue

        translatable_filter_fields = ["status", "direction", "building_type", "zone_name", "amenity_type", "description"]
        
        if key in translatable_filter_fields:
            col_name = f"{key}_{lang}" 
        else:
            col_name = key 

        if not hasattr(Ecopark, col_name):
            raise HTTPException(status_code=400, detail=f"Invalid filter field: {key} for language {lang}")

        col = getattr(Ecopark, col_name)

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
            conditions.append(getattr(Ecopark, key) == int(value)) 
        else:
            conditions.append(col == str(value))

    results = session.exec(query.where(*conditions)).all()
    ids = [r.id for r in results if r.id]

    if ids:
        publish("ecopark_topic_one", {"channels": ids, "value": 1})

    items_for_response = []
    translatable_display_fields = ["zone_name", "building_type", "amenity_type", "direction", "status", "description"]
    for r in results:
        item_dict = r.model_dump() 
    
        processed_item = {}
        processed_item['id'] = item_dict.get('id')
        processed_item['building_name'] = item_dict.get('building_name')
        processed_item['picture_name'] = item_dict.get('picture_name')
        processed_item['zone'] = item_dict.get('zone')
        processed_item['amenity'] = item_dict.get('amenity')
        processed_item['bedroom'] = item_dict.get('bedroom')
        processed_item['price'] = item_dict.get('price')
        processed_item['project_id'] = item_dict.get('project_id')
        
        for field_name in translatable_display_fields:
            chosen_value = item_dict.get(f'{field_name}_{lang}')
            if chosen_value is None:
                chosen_value = item_dict.get(f'{field_name}_en')
            processed_item[field_name] = chosen_value

        processed_item['image_url'] = build_flat_image_url(request, processed_item.get('picture_name'))
        items_for_response.append(processed_item)

    return items_for_response

def search_and_publish(
    session: SessionDep,
    request: Request,
    filters: dict[str, str],
) -> List[Dict[str, Any]]:
    try:
        conditions = []
        for field, raw_value in filters.items():
            if not hasattr(Ecopark, field):
                raise HTTPException(status_code=400, detail=f"Invalid filter field: {field}")

            col = getattr(Ecopark, field)
            value: Any = raw_value.strip()

            if field.endswith("_id"):
                try:
                    value = UUID(value)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid UUID for field {field}")
            elif value.isdigit():
                value = int(value)
            elif value.lower() in ("true", "false"):
                value = value.lower() == "true"

            if isinstance(value, str):
                conditions.append(col.ilike(f"%{value}%"))
            else:
                conditions.append(col == value)

        stmt = select(Ecopark).where(*conditions)
        results = session.exec(stmt).all() 

        # Gửi dữ liệu MQTT nếu có kết quả
        ids = [r.id for r in results if r.id]
        if ids:
            publish(ECO_PARK_TOPIC_ONE, {"channels": ids, "value": 1})

        processed_results = [item.model_dump() for item in results]

        return processed_results

    except HTTPException:
        raise
    except Exception as e:
        print(f"Lỗi trong search_and_publish: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi tìm kiếm: {str(e)}")
    
@router.get(
    "/{project_id}/amenity/{amenity}",
    response_model=Dict[str, Any],
)
def ecopark_search_by_amenity(
    *,
    session: SessionDep,
    request: Request,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    amenity: str,
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (ví dụ: 'vi' hoặc 'en')"),
) -> Any:
    filters = {
        'amenity': amenity,
        'project_id': str(project_id)
    }
    
    results: List[Dict[str, Any]] = search_and_publish(session, request, filters)
    items_for_response = []
    for r in results:
        ecopark_public_item = EcoparkPublic(**r) 

        translated_item = ecopark_public_item.model_dump() 
        translated_item['zone_name'] = translated_item.get(f'zone_name_{lang}')
        translated_item['building_type'] = translated_item.get(f'building_type_{lang}')
        translated_item['amenity_type'] = translated_item.get(f'amenity_type_{lang}')
        translated_item['direction'] = translated_item.get(f'direction_{lang}')
        translated_item['status'] = translated_item.get(f'status_{lang}')
        for key in list(translated_item.keys()):
            if key.endswith('_vi') or key.endswith('_en'):
                del translated_item[key]

        items_for_response.append(translated_item) 

    image_url = f"{str(request.base_url).rstrip('/')}/static/EcoRetreat/he_thong_tien_ich.png"

    return {
        "items": items_for_response, 
        "image_url": image_url
    }

@router.get(
    "/{project_id}/amenity/{amenity}/{amenity_type_path}",
    response_model=List[Dict[str, Any]], 
)
def ecopark_search_by_amenity_and_type(
    *,
    session: SessionDep,
    request: Request,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    amenity: str,
    amenity_type_path: str,
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (e.g., 'vi' or 'en')"),
) -> List[Dict[str, Any]]:
    filters = {
        f'amenity_type_{lang}': amenity_type_path,
        'project_id': str(project_id)
    }

    results: List[Dict[str, Any]] = search_and_publish(session, request, filters)

    items_for_response = []
    for r in results:
        ecopark_public_item = EcoparkPublic(**r)
        translated_item = ecopark_public_item.model_dump()
        
        translated_item['zone_name'] = translated_item.get(f'zone_name_{lang}')
        translated_item['building_type'] = translated_item.get(f'building_type_{lang}')
        translated_item['amenity_type'] = translated_item.get(f'amenity_type_{lang}')
        translated_item['direction'] = translated_item.get(f'direction_{lang}')
        translated_item['status'] = translated_item.get(f'status_{lang}')

        for key in list(translated_item.keys()):
            if key.endswith('_vi') or key.endswith('_en'):
                del translated_item[key]
        
        translated_item["image_url"] = build_flat_image_url(request, translated_item.get('picture_name'))
        items_for_response.append(translated_item)

    return items_for_response

@router.get(
    "/{project_id}/zone/{zone_param}",
    response_model=List[Dict[str, Any]], 
)
def ecopark_search_by_zone(
    *,
    session: SessionDep,
    request: Request,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    zone_param: str,
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (e.g., 'vi' or 'en')"),
) -> List[Dict[str, Any]]:
    filters = {
        'zone': zone_param, 
        'project_id': str(project_id)
    }

    results: List[Dict[str, Any]] = search_and_publish(session, request, filters)

    base_url = str(request.base_url).rstrip("/")
    default_image_url = f"{base_url}/static/EcoRetreat/pk.png"

    items_for_response = []
    for r in results:
        ecopark_public_item = EcoparkPublic(**r)
        translated_item = ecopark_public_item.model_dump()
        
        translated_item['zone_name'] = translated_item.get(f'zone_name_{lang}')
        translated_item['building_type'] = translated_item.get(f'building_type_{lang}')
        translated_item['amenity_type'] = translated_item.get(f'amenity_type_{lang}')
        translated_item['direction'] = translated_item.get(f'direction_{lang}')
        translated_item['status'] = translated_item.get(f'status_{lang}')

        for key in list(translated_item.keys()):
            if key.endswith('_vi') or key.endswith('_en'):
                del translated_item[key]
        
        translated_item["image_url"] = build_flat_image_url(request, translated_item.get('picture_name')) or default_image_url
        items_for_response.append(translated_item)

    return items_for_response

def extract_zone_number(zone_name_str: str) -> str:
    match = re.search(r"Phân\s*Khu\s*(\d+)", zone_name_str, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"Zone\s*(\d+)", zone_name_str, re.IGNORECASE) 
    return match.group(1) if match else ""

def normalize_building_type(building_type_str: str) -> str:
    mapping = {
        "Biệt Thự Đơn Lập": "don_lap",
        "Biệt Thự Song Lập": "song_lap",
        "Shophouse": "shophouse",
        "Townhouse": "townhouse",
        "Residences": "residences",
        "Detached Villa": "don_lap",
        "Semi-Detached Villa": "song_lap",
    }
    return mapping.get(building_type_str.strip(), "unknown")

@router.get(
    "/{project_id}/zone/{zone_param}/{zone_name_path}",
    response_model=List[Dict[str, Any]], 
)
def ecopark_search_by_zone_and_name(
    *,
    session: SessionDep,
    request: Request,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    zone_param: str,
    zone_name_path: str,
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (e.g., 'vi' or 'en')"),
) -> List[Dict[str, Any]]:
    filters = {
        'zone': zone_param,
        f'zone_name_{lang}': zone_name_path, 
        'project_id': str(project_id)
    }
    results: List[Dict[str, Any]] = search_and_publish(session, request, filters)

    items_for_response = []
    for r in results:
        ecopark_public_item = EcoparkPublic(**r)
        translated_item = ecopark_public_item.model_dump()
        
        translated_item['zone_name'] = translated_item.get(f'zone_name_{lang}')
        translated_item['building_type'] = translated_item.get(f'building_type_{lang}')
        translated_item['amenity_type'] = translated_item.get(f'amenity_type_{lang}')
        translated_item['direction'] = translated_item.get(f'direction_{lang}')
        translated_item['status'] = translated_item.get(f'status_{lang}')

        for key in list(translated_item.keys()):
            if key.endswith('_vi') or key.endswith('_en'):
                del translated_item[key]
        
        zone_number = extract_zone_number(zone_name_path)
        filename = f"pk_{zone_number}.png" if zone_number else "pk.png"
        image_url = f"{str(request.base_url).rstrip('/')}/static/EcoRetreat/{filename}"
        
        translated_item["image_url"] = build_flat_image_url(request, translated_item.get('picture_name')) or image_url
        items_for_response.append(translated_item)

    return items_for_response

@router.get(
    "/{project_id}/zone/{zone_param}/{zone_name_path}/{building_type_path}",
    response_model=List[Dict[str, Any]],
)
def ecopark_search_by_zone_name_type(
    *,
    session: SessionDep,
    request: Request,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    zone_param: str,
    zone_name_path: str,
    building_type_path: str,
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (e.g., 'vi' or 'en')"),
) -> List[Dict[str, Any]]:
    filters = {
        'zone': zone_param,
        f'zone_name_{lang}': zone_name_path,
        f'building_type_{lang}': building_type_path,
        'project_id': str(project_id)
    }

    results: List[Dict[str, Any]] = search_and_publish(session, request, filters)

    items_for_response = []
    for r in results:
        ecopark_public_item = EcoparkPublic(**r)
        translated_item = ecopark_public_item.model_dump()
        translated_item['zone_name'] = translated_item.get(f'zone_name_{lang}')
        translated_item['building_type'] = translated_item.get(f'building_type_{lang}')
        translated_item['amenity_type'] = translated_item.get(f'amenity_type_{lang}')
        translated_item['direction'] = translated_item.get(f'direction_{lang}')
        translated_item['status'] = translated_item.get(f'status_{lang}')

        for key in list(translated_item.keys()):
            if key.endswith('_vi') or key.endswith('_en'):
                del translated_item[key]
        
        zone_number = extract_zone_number(zone_name_path)
        building_code = normalize_building_type(building_type_path)
        image_name = f"{zone_number}_{building_code}.png" if zone_number and building_code != "unknown" else "pk.png"
        image_url = f"{str(request.base_url).rstrip('/')}/static/EcoRetreat/{image_name}"
        
        translated_item["image_url"] = build_flat_image_url(request, translated_item.get('picture_name')) or image_url
        items_for_response.append(translated_item)

    return items_for_response

@router.get(
    "/{project_id}/zone/{zone_param}/{zone_name_path}/{building_type_path}/{building_name_param}",
    response_model=List[Dict[str, Any]], 
)
def ecopark_search_by_full_path(
    *,
    session: SessionDep,
    request: Request,
    project_id: UUID = Path(...),
    info: Annotated[ProjectAccessInfo, Depends(verify_rank_in_project([1, 2, 3]))],
    zone_param: str,
    zone_name_path: str,
    building_type_path: str,
    building_name_param: str,
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (e.g., 'vi' or 'en')"),
) -> List[Dict[str, Any]]:
    filters = {
        'zone': zone_param,
        f'zone_name_{lang}': zone_name_path,
        f'building_type_{lang}': building_type_path,
        'building_name': building_name_param,
        'project_id': str(project_id)
    }

    results: List[Dict[str, Any]] = search_and_publish(session, request, filters)

    items_for_response = []
    for r in results:
        ecopark_public_item = EcoparkPublic(**r)
        translated_item = ecopark_public_item.model_dump()
        translated_item['zone_name'] = translated_item.get(f'zone_name_{lang}')
        translated_item['building_type'] = translated_item.get(f'building_type_{lang}')
        translated_item['amenity_type'] = translated_item.get(f'amenity_type_{lang}')
        translated_item['direction'] = translated_item.get(f'direction_{lang}')
        translated_item['status'] = translated_item.get(f'status_{lang}')

        for key in list(translated_item.keys()):
            if key.endswith('_vi') or key.endswith('_en'):
                del translated_item[key]
        
        translated_item["image_url"] = build_flat_image_url(request, translated_item.get('picture_name'))
        items_for_response.append(translated_item)

    return items_for_response

##########------------- DETAL Eco Retreat------------- #####################
STATIC_DIR = PPath("static")
ECO_RETREAT_DETAIL_UPLOAD_DIR = STATIC_DIR / "EcoRetreat" / "CHITIET"
# Đảm bảo thư mục tồn tại
ECO_RETREAT_DETAIL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def build_flat_image_detal_url(request: Request, picture_name: Optional[str]) -> Optional[str]:
    if picture_name:
        base_url = str(request.base_url).rstrip('/')
        return f"{base_url}/static/EcoRetreat/CHITIET/{picture_name}"
    return None

@router.put(
    "/{building_name}/images",
    response_model=List[DetalEcoRetreatPublic],
    status_code=status.HTTP_201_CREATED, 
    summary="Tải lên và thêm nhiều hình ảnh chi tiết cho một 'building' (chỉ JPG/PNG)",
    description="Cho phép người dùng tải lên 1 hoặc nhiều file ảnh có định dạng **JPG/JPEG** hoặc **PNG**, "
)
async def upload_and_add_detal_images_for_building(
    *,
    building_name: str = Path(..., description="Tên 'building' mà các ảnh này thuộc về (chuỗi text bất kỳ)"),
    session: SessionDep,
    request: Request,
    files: List[UploadFile] = File(..., description="Các file ảnh cần tải lên (chỉ JPG/JPEG và PNG)"),
    descriptions_vi: Optional[List[str]] = Form(None, description="Danh sách mô tả tiếng Việt cho từng ảnh (theo thứ tự file)"),
    descriptions_en: Optional[List[str]] = Form(None, description="Danh sách mô tả tiếng Anh cho từng ảnh (theo thứ tự file)"),
    lang: str = Query("en", regex="^(vi|en)$", description="Ngôn ngữ mặc định cho mô tả trong phản hồi"),
) -> List[DetalEcoRetreatPublic]:
    """
    Xử lý việc tải lên nhiều ảnh và tạo bản ghi DetalEcoRetreat tương ứng.
    Mỗi file ảnh sẽ được lưu trữ với một tên duy nhất (UUID) và tạo một bản ghi mới trong DB.
    """
    num_files = len(files)
    # --- Kiểm tra số lượng mô tả khớp với số lượng file ---
    if descriptions_vi and len(descriptions_vi) != num_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số lượng mô tả tiếng Việt không khớp với số lượng file ảnh được tải lên."
        )
    if descriptions_en and len(descriptions_en) != num_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số lượng mô tả tiếng Anh không khớp với số lượng file ảnh được tải lên."
        )
    created_detals_public = []
    for i, file in enumerate(files):
        allowed_mime_types = ["image/jpeg", "image/png"]
        if file.content_type not in allowed_mime_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Loại file không hợp lệ cho '{file.filename}'. Chỉ chấp nhận JPG/JPEG và PNG."
            )
        # --- Tạo tên file duy nhất và đường dẫn lưu trữ ---
        file_extension = PPath(file.filename).suffix 
        unique_filename = f"{uuid.uuid4()}{file_extension}" 
        file_path = ECO_RETREAT_DETAIL_UPLOAD_DIR / unique_filename

        # --- Lưu file vào hệ thống ---
        try:
            ECO_RETREAT_DETAIL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True) 
            with open(file_path, "wb") as buffer:
                content = await file.read() 
                buffer.write(content)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Không thể lưu file '{file.filename}' do lỗi hệ thống: {e}"
            )

        description_vi = descriptions_vi[i] if descriptions_vi and i < len(descriptions_vi) else None
        description_en = descriptions_en[i] if descriptions_en and i < len(descriptions_en) else None
        
        detal_create_data = DetalEcoRetreatCreate(
            building=building_name, 
            picture=unique_filename, 
            description_vi=description_vi,
            description_en=description_en
        )
        db_detal = crud.create_detal_eco_retreat_record(session, detal_create_data)

        detal_public = DetalEcoRetreatPublic.model_validate(db_detal)
        detal_public.image_url = build_flat_image_detal_url(request, db_detal.picture) 

        chosen_description = getattr(db_detal, f'description_{lang}', None)
        if chosen_description is None:
            chosen_description = db_detal.description_en 
        detal_public.description = chosen_description

        created_detals_public.append(detal_public)

    return created_detals_public

@router.get(
    "/{detal_id}", 
    response_model=DetalEcoRetreatPublic,
    summary="Đọc thông tin một hình ảnh chi tiết theo ID"
)
def read_detal_image_by_id(
    *,
    session: SessionDep,
    request: Request,
    detal_id: uuid.UUID = Path(..., description="ID của hình ảnh chi tiết DetalEcoRetreat"),
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ cho mô tả"),
) -> DetalEcoRetreatPublic:
    """
    Truy xuất thông tin chi tiết của một bản ghi hình ảnh DetalEcoRetreat dựa trên ID duy nhất của nó.
    """
    db_detal = crud.get_detal_eco_retreat_by_id(session, detal_id)
    if not db_detal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hình ảnh chi tiết không tìm thấy.")

    detal_public = DetalEcoRetreatPublic.model_validate(db_detal)
    detal_public.image_url = build_flat_image_detal_url(request, db_detal.picture)
    
    chosen_description = getattr(db_detal, f'description_{lang}', None)
    if chosen_description is None:
        chosen_description = db_detal.description_en
    detal_public.description = chosen_description
    
    return detal_public


@router.get(
    "/by-building/{building_name}", 
    response_model=List[DetalEcoRetreatPublic],
    summary="Đọc tất cả hình ảnh chi tiết cho một 'building'"
)
def read_all_detal_images_for_building(
    *,
    session: SessionDep,
    request: Request,
    building_name: str = Path(..., description="Tên 'building' để lọc hình ảnh"),
    skip: int = 0,
    limit: int = 100,
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ cho mô tả"),
) -> List[DetalEcoRetreatPublic]:
    """
    Truy xuất danh sách tất cả các hình ảnh chi tiết thuộc về một 'building' cụ thể.
    """
    db_detals, total = crud.get_all_detal_eco_retreats_by_building(session, building_name=building_name, skip=skip, limit=limit)
    
    response_list = []
    for db_detal in db_detals:
        detal_public = DetalEcoRetreatPublic.model_validate(db_detal)
        detal_public.image_url = build_flat_image_detal_url(request, db_detal.picture)

        chosen_description = getattr(db_detal, f'description_{lang}', None)
        if chosen_description is None:
            chosen_description = db_detal.description_en
        detal_public.description = chosen_description
        
        response_list.append(detal_public)
    
    return response_list # Bạn có thể thêm "total" vào header hoặc trong một đối tượng wrapper nếu cần


@router.put(
    "/{detal_id}", 
    response_model=DetalEcoRetreatPublic,
    summary="Cập nhật thông tin và/hoặc thay thế ảnh của một hình ảnh chi tiết",
    description="Cập nhật các trường (mô tả, tên building) cho một bản ghi hình ảnh DetalEcoRetreat cụ thể. "
                "Có thể tùy chọn tải lên một file ảnh mới để thay thế ảnh hiện có. "
                "**Chỉ chấp nhận ảnh JPG/JPEG và PNG.** "
                "**Yêu cầu: Sau khi cập nhật, bản ghi phải có ít nhất một mô tả (tiếng Việt hoặc tiếng Anh).**"
)
async def update_detal_image_by_id(
    *,
    session: SessionDep,
    request: Request,
    detal_id: uuid.UUID = Path(..., description="ID của hình ảnh chi tiết cần cập nhật"),
    file: Optional[UploadFile] = File(None, description="File ảnh mới (JPG/PNG) để thay thế ảnh hiện có"),
    building: Optional[str] = Form(None, description="Tên 'building' mới cho ảnh (tùy chọn)"),
    description_vi: Optional[str] = Form(None, description="Mô tả tiếng Việt mới cho ảnh (tùy chọn)"),
    description_en: Optional[str] = Form(None, description="Mô tả tiếng Anh mới cho ảnh (tùy chọn)"),
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ cho mô tả trong phản hồi"),
) -> DetalEcoRetreatPublic:
    """
    Cập nhật một bản ghi DetalEcoRetreat, bao gồm khả năng thay thế file ảnh và cập nhật mô tả.
    """
    db_detal = crud.get_detal_eco_retreat_by_id(session, detal_id)
    if not db_detal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hình ảnh chi tiết không tìm thấy.")

    detal_update_data = DetalEcoRetreatUpdate(
        building=building,
        description_vi=description_vi,
        description_en=description_en
    )

    old_picture_name = db_detal.picture
    new_picture_name = None

    # --- Xử lý file ảnh mới nếu được cung cấp ---
    if file:
        allowed_mime_types = ["image/jpeg", "image/png"]
        if file.content_type not in allowed_mime_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Loại file không hợp lệ cho '{file.filename}'. Chỉ chấp nhận JPG/JPEG và PNG."
            )

        file_extension = PPath(file.filename).suffix
        new_picture_name = f"{uuid.uuid4()}{file_extension}"
        new_file_path = ECO_RETREAT_DETAIL_UPLOAD_DIR / new_picture_name

        try:
            ECO_RETREAT_DETAIL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True) 
            with open(new_file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Không thể lưu file mới '{file.filename}' do lỗi hệ thống: {e}"
            )
        
        # 4. Cập nhật tên ảnh mới vào dữ liệu update
        detal_update_data.picture = new_picture_name
        # 5. Xóa file ảnh cũ nếu có
        if old_picture_name:
            old_file_path = ECO_RETREAT_DETAIL_UPLOAD_DIR / old_picture_name
            if old_file_path.is_file():
                try:
                    os.remove(old_file_path)
                    print(f"Đã xóa file cũ: {old_file_path}")
                except OSError as e:
                    print(f"Lỗi khi xóa file cũ '{old_file_path}': {e}") # Log lỗi, không chặn request

    try:
        db_detal = crud.update_detal_eco_retreat_record(session, db_detal, detal_update_data)
    except ValueError as e:
        # Nếu có lỗi về mô tả (tiếng Việt/Anh bị thiếu)
        # Đồng thời, nếu đã lưu file mới, hãy cố gắng xóa nó để tránh rác
        if new_picture_name:
            if (ECO_RETREAT_DETAIL_UPLOAD_DIR / new_picture_name).is_file():
                try:
                    os.remove(ECO_RETREAT_DETAIL_UPLOAD_DIR / new_picture_name)
                    print(f"Đã xóa file mới do lỗi DB rollback: {new_picture_name}")
                except OSError as rollback_e:
                    print(f"Lỗi khi rollback xóa file mới: {rollback_e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    # --- Chuẩn bị dữ liệu trả về ---
    detal_public = DetalEcoRetreatPublic.model_validate(db_detal)
    detal_public.image_url = build_flat_image_detal_url(request, db_detal.picture)
    
    chosen_description = getattr(db_detal, f'description_{lang}', None)
    if chosen_description is None:
        chosen_description = db_detal.description_en
    detal_public.description = chosen_description

    return detal_public



@router.delete(
    "/{detal_id}", 
    response_model=Dict[str, str],
    summary="Xóa một hình ảnh chi tiết theo ID"
)
def delete_detal_image_by_id(
    *,
    session: SessionDep,
    detal_id: uuid.UUID = Path(..., description="ID của hình ảnh chi tiết cần xóa"),
) -> Dict[str, str]:
    """
    Xóa một bản ghi hình ảnh DetalEcoRetreat khỏi cơ sở dữ liệu.
    Lưu ý: API này không tự động xóa file ảnh vật lý trên server.
    """
    db_detal = crud.get_detal_eco_retreat_by_id(session, detal_id)
    if not db_detal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hình ảnh chi tiết không tìm thấy.")

    crud.delete_detal_eco_retreat_record(session, db_detal)
    
    # Tùy chọn: Xóa file vật lý. Hãy cẩn thận khi triển khai.
    # if db_detal.picture:
    #     file_to_delete = ECO_RETREAT_DETAIL_UPLOAD_DIR / db_detal.picture
    #     if file_to_delete.is_file():
    #         try:
    #             os.remove(file_to_delete)
    #         except OSError as e:
    #             print(f"Lỗi khi xóa file {file_to_delete}: {e}") # Log lỗi, không raise
    
    return {"message": "Hình ảnh chi tiết đã được xóa thành công."}