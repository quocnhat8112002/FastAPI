from typing import Annotated, Any, Dict, List, Optional
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