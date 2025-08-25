import io
import logging
from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID
import uuid

import pandas as pd
from fastapi import APIRouter, Form, Path, UploadFile, File, Depends, HTTPException, Query, logger, status, Request
from sqlalchemy import func, delete
from sqlmodel import select

from app import crud
from app.models import DetalEcoRetreat, DetalEcoRetreatCreate, DetalEcoRetreatPublic, DetalEcoRetreatResponse, DetalEcoRetreatUpdate, Ecopark, EcoparkCreate, EcoparkUpdate, EcoparkPublic
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

logger = logging.getLogger(__name__)


ECO_PARK_TOPIC_ONE = 'ecopark/192.168.100.101/request/one'
ECO_PARK_TOPIC_ALL = 'ecopark/192.168.100.101/request/all'
ECO_PARK_TOPIC_EFF = 'ecopark/192.168.100.101/request/eff'

PROJECT_FOLDER = "EcoRetreat"
STATIC_URL_PREFIX = "/api/v1/static"

router = APIRouter(prefix="/ecopark", tags=["ecopark"])

# --- CÁCH CHUẨN ĐỂ XÁC ĐỊNH ĐƯỜNG DẪN VẬT LÝ TUYỆT ĐỐI ---
# Đi từ vị trí của file ecopark.py
# PPath(__file__).resolve() là đường dẫn tuyệt đối đến ecopark.py
# .parent là thư mục cha (backend/app/api/routes/)
# .parent.parent là thư mục cha của thư mục cha (backend/app/api/)
# .parent.parent.parent là thư mục cha của thư mục cha của thư mục cha (backend/app/)
APP_ROOT_DIR = PPath(__file__).resolve().parent.parent.parent # Đường dẫn đến thư mục 'app'

# Đường dẫn vật lý đến thư mục 'static' trong thư mục 'app'
# Ví dụ: backend/app/static/
PHYSICAL_STATIC_DIR = APP_ROOT_DIR / "static"

# Đường dẫn vật lý đầy đủ đến thư mục đích cuối cùng: backend/app/static/EcoRetreat/CHITIET/
ECO_RETREAT_DETAIL_UPLOAD_DIR = PHYSICAL_STATIC_DIR / "EcoRetreat" / "CHITIET"


# --- KIỂM TRA VÀ TẠO THƯ MỤC NẾU CHƯA TỒN TẠI ---
try:
    ECO_RETREAT_DETAIL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Upload directory ensured: {ECO_RETREAT_DETAIL_UPLOAD_DIR.resolve()}")
except Exception as e:
    logger.critical(f"FAILED TO CREATE UPLOAD DIRECTORY '{ECO_RETREAT_DETAIL_UPLOAD_DIR.resolve()}': {e}")
    raise RuntimeError(f"Cannot initialize upload directory: {e}")

# --- ĐỊNH NGHĨA HÀM TẠO URL ẢNH (PHẢI KHỚP VỚI CẤU HÌNH MOUNT TRONG MAIN.PY) ---
# Vì bạn mount "/api/v1/static" đến thư mục vật lý "backend/app/static"
# thì đường dẫn con trong URL phải là từ thư mục "static" trở đi.
def build_flat_image_detal_url(request: Request, filename: str) -> str:
    # Tiền tố mount của bạn: "/api/v1/static"
    # Tiếp theo là đường dẫn con bên trong thư mục 'static' nơi ảnh được lưu
    return f"{request.url.scheme}://{request.url.netloc}/api/v1/static/EcoRetreat/CHITIET/{filename}"


def build_flat_image_url(request: Request, picture_name: Optional[str]) -> Optional[str]:
    if not picture_name:
        return None
    base = str(request.base_url).rstrip("/")
    return f"{base}{STATIC_URL_PREFIX}/{PROJECT_FOLDER}/{picture_name}.png"


@router.post("/{project_id}/upload", response_model=dict, dependencies=[Depends(get_current_active_superuser)],)
def upload_excel(
    *,
    session: SessionDep,
    project_id: UUID = Path(..., description="ID của dự án (chỉ dùng cho mục đích định tuyến/ủy quyền, không lưu vào Ecopark)"),
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    # 1. Kiểm tra định dạng file
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file định dạng .xlsx")

    # 2. Đọc file Excel từ sheet "ECO PARK"
    try:
        # THAY ĐỔI TẠI ĐÂY: Thêm sheet_name='ECO PARK'
        df = pd.read_excel(file.file, sheet_name='ECO PARK')
        
        # Đảm bảo cột 'port' tồn tại trong Excel
        if 'port' not in df.columns:
            raise HTTPException(status_code=400, detail="Sheet 'ECO PARK' trong file Excel phải chứa cột 'port'.")
    except ValueError as ve:
        # Bắt lỗi nếu sheet 'ECO PARK' không tồn tại
        raise HTTPException(status_code=400, detail=f"Không tìm thấy sheet 'ECO PARK' trong file Excel. Vui lòng kiểm tra tên sheet: {ve}")
    except Exception as e:
        # Bắt các lỗi chung khi đọc file (ví dụ: file bị hỏng, định dạng sai)
        raise HTTPException(status_code=400, detail=f"Không thể đọc file Excel. Vui lòng kiểm tra định dạng và nội dung: {e}")

    processed_count = 0
    failed_count = 0
    errors = []

    # 3. Duyệt qua từng hàng và xử lý
    for index, row in df.iterrows():
        row_number_in_excel = index + 2 # +2 để tính hàng header và index 0 của pandas thành số hàng trong Excel
        
        try:
            row_port: Optional[int] = None
            if "port" in row and not pd.isna(row["port"]):
                try:
                    row_port = int(row["port"])
                except ValueError:
                    errors.append(f"Hàng {row_number_in_excel}: Cột 'port' ('{row['port']}') không phải là số nguyên hợp lệ.")
                    failed_count += 1
                    continue
            
            if row_port is None:
                errors.append(f"Hàng {row_number_in_excel}: Cột 'port' bị thiếu hoặc giá trị rỗng.")
                failed_count += 1
                continue

            ecopark_data = EcoparkCreate(
                port=row_port,
                building_name=row.get("building_name") if "building_name" in row and not pd.isna(row.get("building_name")) else None,
                picture_name=row.get("picture_name") if "picture_name" in row and not pd.isna(row.get("picture_name")) else None,
                building_type_vi=row.get("building_type_vi") if "building_type_vi" in row and not pd.isna(row.get("building_type_vi")) else None,
                building_type_en=row.get("building_type_en") if "building_type_en" in row and not pd.isna(row.get("building_type_en")) else None,
                amenity_type_vi=row.get("amenity_type_vi") if "amenity_type_vi" in row and not pd.isna(row.get("amenity_type_vi")) else None,
                amenity_type_en=row.get("amenity_type_en") if "amenity_type_en" in row and not pd.isna(row.get("amenity_type_en")) else None,
                zone_name_vi=row.get("zone_name_vi") if "zone_name_vi" in row and not pd.isna(row.get("zone_name_vi")) else None,
                zone_name_en=row.get("zone_name_en") if "zone_name_en" in row and not pd.isna(row.get("zone_name_en")) else None,
                zone=row.get("zone") if "zone" in row and not pd.isna(row.get("zone")) else None,
                amenity=row.get("amenity") if "amenity" in row and not pd.isna(row.get("amenity")) else None,
                direction_vi=row.get("direction_vi") if "direction_vi" in row and not pd.isna(row.get("direction_vi")) else None,
                
                bedroom=int(row["bedroom"]) if "bedroom" in row and not pd.isna(row.get("bedroom")) else None,
                price=int(row["price"]) if "price" in row and not pd.isna(row.get("price")) else None,
                
                status_vi=row.get("status_vi") if "status_vi" in row and not pd.isna(row.get("status_vi")) else None,
                direction_en=row.get("direction_en") if "direction_en" in row and not pd.isna(row.get("direction_en")) else None,
                status_en=row.get("status_en") if "status_en" in row and not pd.isna(row.get("status_en")) else None,
                description_vi=row.get("description_vi") if "description_vi" in row and not pd.isna(row.get("description_vi")) else None,
                description_en=row.get("description_en") if "description_en" in row and not pd.isna(row.get("description_en")) else None,
            )

            existing_ecopark = crud.get_by_port(session=session, port=row_port)

            if existing_ecopark:
                ecopark_update_data = EcoparkUpdate(**ecopark_data.dict(exclude={"port"}))
                crud.update_ecopark(session=session, db_ecopark=existing_ecopark, ecopark_in=ecopark_update_data)
            else:
                crud.create_ecopark(session=session, ecopark_in=ecopark_data)
            
            processed_count += 1

        except Exception as e:
            errors.append(f"Hàng {row_number_in_excel} (Port: {row.get('port', 'N/A')}): Lỗi - {e}")
            failed_count += 1

    if failed_count > 0:
        return {
            "message": f"Đã xử lý file Excel. Thành công: {processed_count}, Thất bại: {failed_count}.",
            "errors": errors,
            "status": "partial_success" if processed_count > 0 else "failed"
        }
    else:
        return {
            "message": f"Đã xử lý file Excel thành công. Tổng số bản ghi được xử lý: {processed_count}.",
            "status": "success"
        }


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
    ids = [r.port for r in results if r.port]

    if ids:
        publish("ecopark_topic_one", {"channels": ids, "value": 1})

    items_for_response = []
    translatable_display_fields = ["zone_name", "building_type", "amenity_type", "direction", "status", "description"]
    for r in results:
        item_dict = r.model_dump() 
    
        processed_item = {}
        processed_item['port'] = item_dict.get('port')
        processed_item['building_name'] = item_dict.get('building_name')
        processed_item['picture_name'] = item_dict.get('picture_name')
        processed_item['zone'] = item_dict.get('zone')
        processed_item['amenity'] = item_dict.get('amenity')
        processed_item['bedroom'] = item_dict.get('bedroom')
        processed_item['price'] = item_dict.get('price')
        
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
    filters: Dict[str, str],
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
        ids = [r.port for r in results if r.port]
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
        image_url = f"{str(request.base_url).rstrip('/')}/api/v1/static/EcoRetreat/{image_name}"
        
        translated_item["image_url"] = image_url
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

@router.put(
    "/add_multiple_images/{port}", # Tên endpoint gợi ý
    response_model=List[DetalEcoRetreatPublic],
    status_code=status.HTTP_201_CREATED,
    summary="Tải lên và thêm nhiều hình ảnh chi tiết cho một 'building'",
    description="Cho phép tải lên nhiều file ảnh và mô tả tương ứng. Số lượng file ảnh và số lượng mô tả (tiếng Việt/Anh) phải khớp nhau. Mô tả có thể để trống."
)
async def add_multiple_detal_images_for_building(
    *,
    port: int = Path(..., description=" Căn hộ mà các ảnh này thuộc về (tương ứng với Ecopark)"), 
    session: SessionDep,
    request: Request,
    files: List[UploadFile] = File(..., description="Các file ảnh cần tải lên (chỉ JPG/JPEG và PNG)"),
    description_vi: Optional[List[str]] = Form(None, description="Danh sách mô tả tiếng Việt cho mỗi ảnh (tương ứng thứ tự)"),
    description_en: Optional[List[str]] = Form(None, description="Danh sách mô tả tiếng Anh cho mỗi ảnh (tương ứng thứ tự)"),
    lang: str = Query("en", regex="^(vi|en)$", description="Ngôn ngữ mặc định cho mô tả trong phản hồi"),
) -> List[DetalEcoRetreatPublic]:
    logger.info(f"Received request to upload multiple images for building: '{port}'")
    logger.info(f"Number of files received: {len(files)}")

    num_files = len(files)

    if description_vi is None:
        description_vi = [None] * num_files
    if description_en is None:
        description_en = [None] * num_files

    if not (len(description_vi) == num_files and len(description_en) == num_files):
        logger.warning("Mismatch in number of files and descriptions provided.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số lượng file ảnh, mô tả tiếng Việt và mô tả tiếng Anh phải khớp nhau."
        )

    results: List[DetalEcoRetreatPublic] = []
    error_details = []

    for i, file in enumerate(files):
        current_description_vi = description_vi[i]
        current_description_en = description_en[i]

        logger.info(f"Processing file {i+1}/{num_files}: '{file.filename}'")
        logger.info(f"  Desc VI: '{current_description_vi}', Desc EN: '{current_description_en}'")

        # --- Kiểm tra loại file ---
        allowed_mime_types = ["image/jpeg", "image/png"]
        if file.content_type not in allowed_mime_types:
            error_details.append(
                f"File '{file.filename}' (index {i}): Loại file không hợp lệ. Chỉ chấp nhận JPG/JPEG và PNG."
            )
            logger.warning(f"Invalid file type for '{file.filename}': {file.content_type}")
            continue

        # --- Tạo tên file duy nhất và đường dẫn lưu trữ ---
        file_extension = PPath(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = ECO_RETREAT_DETAIL_UPLOAD_DIR / unique_filename

        logger.info(f"  Generated unique filename: {unique_filename}")
        logger.info(f"  Attempting to save file to: {file_path.resolve()}")

        # --- Lưu file vào hệ thống ---
        try:
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            logger.info(f"  File '{unique_filename}' saved SUCCESSFULLY to '{file_path.resolve()}'.")
        except Exception as e:
            error_details.append(
                f"File '{file.filename}' (index {i}): Không thể lưu file do lỗi hệ thống: {e}"
            )
            logger.exception(f"  FAILED to save file '{file.filename}' to '{file_path.resolve()}'. An error occurred:")
            continue

        detal_create_data = DetalEcoRetreatCreate(
            port=port, 
            picture=unique_filename,
            description_vi=current_description_vi,
            description_en=current_description_en
        )
        logger.info(f"  DetalEcoRetreatCreate object prepared with picture='{unique_filename}'.")
        try:
            db_detal = crud.create_detal_eco_retreat_record(session, detal_create_data)
            logger.info(f"  Database record created successfully with ID: {db_detal.id}, picture name: {db_detal.picture}")

            # --- Chuẩn bị phản hồi cho từng ảnh ---
            detal_public = DetalEcoRetreatPublic.model_validate(db_detal)
            detal_public.image_url = build_flat_image_detal_url(request, db_detal.picture)
            logger.info(f"  Generated image URL for response: {detal_public.image_url}")

            chosen_description = getattr(db_detal, f'description_{lang}', None)
            if chosen_description is None:
                chosen_description = db_detal.description_en

            detal_public.description = chosen_description
            results.append(detal_public)

        except Exception as e:
            error_details.append(
                f"File '{file.filename}' (index {i}): Lỗi khi tạo bản ghi database: {e}"
            )
            logger.exception(f"  FAILED to create database record for '{unique_filename}'. An error occurred:")
            continue

    if error_details:
        logger.error(f"Completed processing with {len(error_details)} errors and {len(results)} successes.")
        if not results: # Nếu không có ảnh nào được xử lý thành công
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Không có ảnh nào được xử lý thành công. Chi tiết lỗi: {error_details}")
        else:
            logger.warning(f"Some files failed to process. Details: {error_details}")

    logger.info(f"API request finished successfully. Processed {len(results)} files.")
    return results

@router.patch("/{ecopark_id}", response_model=Ecopark)
def update_ecopark_details(
    *,
    session: SessionDep,
    ecopark_id: UUID,
    ecopark_in: EcoparkUpdate,
    current_user: Any = Depends(get_current_active_user),
) -> Any:
    """
    Cập nhật thông tin chi tiết của một bản ghi Ecopark theo ID.
    Chỉ cập nhật những trường được cung cấp (động).
    """
    db_ecopark = crud.get(session=session, ecopark_id=ecopark_id)
    if not db_ecopark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bản ghi Ecopark."
        )
    update_data = ecopark_in.model_dump(exclude_unset=True)

    # Nếu trường 'port' có trong request body và nó khác với port hiện tại
    if "port" in update_data and update_data["port"] != db_ecopark.port:
        existing_ecopark = crud.get_by_port(session=session, port=update_data["port"])
        if existing_ecopark:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Port {update_data['port']} đã tồn tại trong hệ thống."
            )

    updated_ecopark = crud.update_ecopark(
        session=session,
        db_ecopark=db_ecopark,
        ecopark_in=ecopark_in
    )
    
    return updated_ecopark

@router.get(
    "/image/{detal_id}", 
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
    "/by_ports", # Đổi URL để phản ánh việc tìm kiếm theo NHIỀU ports
    response_model=DetalEcoRetreatResponse,
    summary="Đọc tất cả hình ảnh chi tiết cho nhiều 'port' cụ thể của 1 building_name" # Cập nhật summary
)
def read_detal_images_by_ports( # Đổi tên hàm cho rõ ràng
    *,
    session: SessionDep,
    request: Request,
    port: List[int] = Query(..., description="Danh sách các số 'port' để lọc hình ảnh. Ví dụ: ?ports=8080&ports=8081"), # Thay đổi từ Path sang Query và List[int]
    skip: int = 0,
    limit: int = 100,
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ cho mô tả"),
) -> DetalEcoRetreatResponse:
    """
    Truy xuất danh sách tất cả các hình ảnh chi tiết thuộc về nhiều 'port' cụ thể.
    """
    # Gọi hàm CRUD mới để lấy dữ liệu theo danh sách ports
    db_detals, total = crud.get_all_detal_eco_retreats_by_ports(session=session, port=port, skip=skip, limit=limit)
    
    response_items = [] 
    for db_detal in db_detals:
        detal_public = DetalEcoRetreatPublic.model_validate(db_detal)
        detal_public.image_url = build_flat_image_detal_url(request, db_detal.picture)

        chosen_description = getattr(db_detal, f'description_{lang}', None)
        if chosen_description is None:
            chosen_description = db_detal.description_en # Fallback về tiếng Anh
        detal_public.description = chosen_description
        
        response_items.append(detal_public)

    return DetalEcoRetreatResponse(items=response_items, total=total)

@router.put(
    "/update_image/{detal_id}", 
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

    detal_update_data = {} 

    if description_vi is not None: # Nếu mô tả tiếng Việt được cung cấp
        detal_update_data["description_vi"] = description_vi
    if description_en is not None: # Nếu mô tả tiếng Anh được cung cấp
        detal_update_data["description_en"] = description_en

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
            with open(new_file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Không thể lưu file mới '{file.filename}' do lỗi hệ thống: {e}"
            )
        
        # 4. Cập nhật tên ảnh mới vào dữ liệu update
        detal_update_data["picture"] = new_picture_name
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
    
    # Lấy mô tả theo ngôn ngữ được yêu cầu
    chosen_description = getattr(db_detal, f'description_{lang}', None)
    if chosen_description is None:
        chosen_description = db_detal.description_en # Fallback về tiếng Anh nếu ngôn ngữ yêu cầu không có

    detal_public.description = chosen_description

    return detal_public

@router.delete(
    "/bulk_delete", # Endpoint mới để xóa nhiều
    response_model=Dict[str, str],
    summary="Xóa nhiều hình ảnh chi tiết theo ID",
    description="Xóa nhiều bản ghi hình ảnh DetalEcoRetreat và các file ảnh vật lý liên quan khỏi cơ sở dữ liệu."
)
def bulk_delete_detal_images_by_ids(
    *,
    session: SessionDep,
    detal_ids: List[uuid.UUID] = Query(..., description="Danh sách các ID của hình ảnh chi tiết cần xóa"),
) -> Dict[str, str]:
    """
    Xóa nhiều bản ghi DetalEcoRetreat cùng lúc, bao gồm việc xóa các file ảnh vật lý.
    """
    if not detal_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp ít nhất một ID để xóa."
        )

    # Lấy tất cả các bản ghi từ DB dựa trên danh sách ID được cung cấp
    db_detals_to_delete = crud.get_detal_eco_retreats_by_ids(session, detal_ids)
    
    # Kiểm tra xem có ID nào không tìm thấy không
    found_ids = {str(d.id) for d in db_detals_to_delete}
    missing_ids = [str(id_) for id_ in detal_ids if str(id_) not in found_ids]

    if missing_ids:
        # Nếu có ID không tìm thấy, bạn có thể chọn:
        # 1. Báo lỗi và không xóa gì cả.
        # 2. Xóa những cái tìm thấy và báo lỗi về những cái không tìm thấy.
        # Ở đây, tôi chọn phương án 2: vẫn tiếp tục xóa những cái tìm thấy và báo cáo những cái bị thiếu.
        print(f"Cảnh báo: Không tìm thấy các ID sau để xóa: {missing_ids}")
        # Bạn có thể trả về một thông báo chi tiết hơn nếu muốn

    pictures_to_delete = [d.picture for d in db_detals_to_delete if d.picture]

    # Xóa các bản ghi khỏi cơ sở dữ liệu
    # Hàm CRUD mới sẽ đảm bảo chỉ xóa những bản ghi đã tìm thấy.
    deleted_count = crud.delete_detal_eco_retreat_records_by_ids(session, [d.id for d in db_detals_to_delete])

    # Xóa các file vật lý
    files_deleted_count = 0
    files_failed_to_delete = []

    for picture_name in pictures_to_delete:
        file_path_to_delete = ECO_RETREAT_DETAIL_UPLOAD_DIR / picture_name
        if file_path_to_delete.is_file():
            try:
                os.remove(file_path_to_delete)
                files_deleted_count += 1
                print(f"Đã xóa file vật lý: {file_path_to_delete}")
            except OSError as e:
                print(f"Lỗi khi xóa file vật lý '{file_path_to_delete}': {e}")
                files_failed_to_delete.append(picture_name)
        else:
            print(f"Cảnh báo: File '{file_path_to_delete}' không tồn tại để xóa.")

    message = f"Đã xóa thành công {deleted_count} bản ghi hình ảnh chi tiết."
    if missing_ids:
        message += f" Các ID không tìm thấy: {', '.join(missing_ids)}."
    if files_failed_to_delete:
        message += f" Không thể xóa được {len(files_failed_to_delete)} file ảnh: {', '.join(files_failed_to_delete)}."

    return {"message": message}


# @router.delete(
#     "/clear-all-detal-eco-retreat-records",
#     status_code=status.HTTP_200_OK,
#     summary="Xóa TẤT CẢ các bản ghi DetalEcoRetreat (KHÔNG xóa file ảnh vật lý)",
#     description="**Cảnh báo: Hành động này sẽ xóa vĩnh viễn tất cả các bản ghi trong bảng 'detalecoretreat' khỏi cơ sở dữ liệu. Các file ảnh vật lý trên hệ thống file sẽ KHÔNG bị xóa.** Chỉ dành cho superuser.",
#     response_model=Dict[str, Any],
#     dependencies=[Depends(get_current_active_superuser)]
# )
# async def clear_all_detal_eco_retreat_records(
#     session: SessionDep,
# ) -> Dict[str, Any]:
#     logger.warning("Attempting to delete ALL DetalEcoRetreat records (files will NOT be deleted).")

#     try:
#         # Lấy số lượng bản ghi hiện có trước khi xóa (tùy chọn, để báo cáo)
#         count_statement = select(DetalEcoRetreat)
#         initial_count = len(session.exec(count_statement).all())

#         if initial_count == 0:
#             logger.info("No DetalEcoRetreat records found to delete.")
#             return {
#                 "message": "Không có bản ghi DetalEcoRetreat nào để xóa.",
#                 "deleted_db_records": 0
#             }

#         # Xóa tất cả các bản ghi trong bảng DetalEcoRetreat
#         # Sử dụng câu lệnh DELETE trực tiếp
#         delete_statement = delete(DetalEcoRetreat)
#         result = session.exec(delete_statement)
#         deleted_rows = result.rowcount # Lấy số lượng hàng bị ảnh hưởng (số lượng bản ghi đã xóa)

#         session.commit() # Commit giao dịch

#         logger.info(f"Finished clearing DetalEcoRetreat data. Deleted {deleted_rows} DB records.")

#         return {
#             "message": "Đã xóa thành công tất cả các bản ghi DetalEcoRetreat.",
#             "deleted_db_records": deleted_rows
#         }

#     except Exception as e:
#         session.rollback() # Rollback nếu có bất kỳ lỗi nào xảy ra trong quá trình
#         logger.exception("An error occurred while clearing DetalEcoRetreat records:")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Lỗi hệ thống khi xóa bản ghi DetalEcoRetreat: {e}."
#         )

