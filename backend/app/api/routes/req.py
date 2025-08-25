import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select
from uuid import UUID
from typing import Any, Dict, List
from datetime import datetime

from app.models import (
    Request,
    Request as RequestModel,
    RequestCreate,
    RequestUpdate,
    RequestPublic,
    Role,
    UserProjectRoleCreate
)
from app.api.deps import (
    SessionDep,
    ProjectAccessInfo,
    CurrentUser,
    get_current_active_user,
    get_current_user,
    get_current_active_superuser,
    verify_system_rank_in
)
from app.models import User
import app.crud as crud

router = APIRouter(prefix="/req", tags=["Request"])

def translate_request_item(item_dict: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """
    Dịch các trường tin nhắn trong một request item dựa trên ngôn ngữ yêu cầu.
    """
    item_dict['request_message'] = item_dict.get(f'request_message_{lang}')
    if item_dict['request_message'] is None:
        item_dict['request_message'] = item_dict.get('request_message_en') # Mặc định là tiếng Anh nếu không có bản dịch
    
    item_dict['response_message'] = item_dict.get(f'response_message_{lang}')
    if item_dict['response_message'] is None:
        item_dict['response_message'] = item_dict.get('response_message_en') 

    for key in list(item_dict.keys()):
        if key.endswith('_vi') or key.endswith('_en'):
            del item_dict[key]
            
    return item_dict

@router.get("/{request_id}", response_model=RequestPublic)
def get_request_by_id(
    session: SessionDep,
    project_info: ProjectAccessInfo,
    request_id: uuid.UUID,
    current_user=Depends(get_current_active_user),
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (ví dụ: 'vi' hoặc 'en')"),
) -> Any:
    """
    Lấy một Request cụ thể theo ID, có kiểm tra quyền hạn.
    """
    user, project_id, user_rank = project_info
        
    if current_user.is_superuser:
        request_obj = session.get(Request, request_id)
        if request_obj and request_obj.project_id == project_id:
            request_dict = request_obj.model_dump()
            return translate_request_item(request_dict, lang)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy yêu cầu này trong dự án."
            )

    stmt = (
        select(Request)
        .join(Role, Request.role_id == Role.id)
        .where(
            Request.id == request_id,
            Request.project_id == project_id,
            Role.rank > user_rank
        )
    )
    request_obj = session.exec(stmt).first()

    if not request_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy yêu cầu này hoặc bạn không có quyền xem."
        )
    request_dict = request_obj.model_dump()
    return translate_request_item(request_dict, lang)

@router.get("/", response_model=RequestPublic)
def get_requests_by_project(
    session: SessionDep,
    project_info: ProjectAccessInfo,
    current_user=Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (ví dụ: 'vi' hoặc 'en')"),
):
    user, project_id, user_rank = project_info

    if current_user.is_superuser:
        stmt = (
            select(Request)
            .where(Request.project_id == project_id)
            .offset(skip)
            .limit(limit)
        )
        requests = session.exec(stmt).all()
        total = session.exec(
            select(Request.id).where(Request.project_id == project_id)
        ).all()
        return RequestPublic(data=requests, count=len(total))

    stmt = (
        select(Request)
        .join(Role, Request.role_id == Role.id)
        .where(
            Request.project_id == project_id,
            Role.rank > user_rank
        )
        .offset(skip)
        .limit(limit)
    )
    requests = session.exec(stmt).all()
    total = session.exec(
        select(Request.id)
        .join(Role, Request.role_id == Role.id)
        .where(
            Request.project_id == project_id,
            Role.rank > user_rank
        )
    ).all()

    translated_requests = []
    for req_obj in requests:
        req_dict = req_obj.model_dump() 
        translated_req_dict = translate_request_item(req_dict, lang)
        translated_requests.append(translated_req_dict)

    return RequestPublic(data=translated_requests, count=total)

# 2. ✅ POST - tạo request (chỉ được yêu cầu role có rank >= 3)
@router.post(
    "/{project_id}",
    response_model=RequestPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(verify_system_rank_in([1, 2])) # Phân biệt user có quyền yêu cầu với user thường
    ],
)
def create_request(
    project_id: UUID,
    request_data: RequestCreate,
    session: SessionDep,
    current_user: CurrentUser,
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (ví dụ: 'vi' hoặc 'en')"),
):
    role = session.get(Role, request_data.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Vai trò không tồn tại")

    # Chỉ được yêu cầu role có rank >= 3
    if role.rank < 3:
        raise HTTPException(
            status_code=403,
            detail="Chỉ được yêu cầu các vai trò có rank >= 3 (thấp quyền hơn)",
        )
    created_request_obj = crud.create_request(
        session=session,
        request_in=request_data,
        requester_id=current_user.id,
        project_id=project_id  
    )

    translated_created_request_dict = translate_request_item(created_request_obj.model_dump(), lang)
    return RequestPublic(data=[translated_created_request_dict], count=1)

# 3. ✅ PUT - cập nhật trạng thái (chỉ xử lý nếu request có rank < mình)
@router.put(
    "/{project_id}/{request_id}",
    response_model=RequestPublic,
    dependencies=[Depends(get_current_active_user)],
)
def update_request_status(
    project_id: UUID,
    request_id: UUID,
    update_data: RequestUpdate,
    session: SessionDep,
    info: ProjectAccessInfo,
    lang: str = Query("en", regex="^(vi|en)$", description="Mã ngôn ngữ (ví dụ: 'vi' hoặc 'en')"),
):
    current_user, access_project_id, current_rank = info

    db_request = crud.get_request(session=session, request_id=request_id)
    if not db_request:
        raise HTTPException(status_code=404, detail="Request không tồn tại")

    if not current_user.is_superuser and db_request.project_id != project_id:
        raise HTTPException(status_code=403, detail="Không đúng phạm vi dự án")

    role = session.get(Role, db_request.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Vai trò không tồn tại")

    if not current_user.is_superuser and role.rank <= current_rank:
        raise HTTPException(
            status_code=403,
            detail="Chỉ được duyệt request có rank thấp hơn bạn",
        )
    # Tùy chọn: Nếu không truyền message, tạo thông điệp mặc định
    if not update_data.response_message_vi and not update_data.response_message_en:
        if update_data.status == "approved":
            update_data.response_message_vi = "Yêu cầu đã được duyệt"
            update_data.response_message_en = "Request has been approved"
        else: # "rejected"
            update_data.response_message_vi = "Yêu cầu bị từ chối"
            update_data.response_message_en = "Request has been rejected"

    updated = crud.update_request(
        session=session,
        db_request=db_request,
        request_in=update_data,
        approver_id=current_user.id,
    )

    # Nếu đồng ý → cập nhật UserProjectRole
    if update_data.status == "approved":
        existing = crud.get_user_project_role_by_user_project(
            session=session,
            user_id=updated.requester_id,
            project_id=project_id,
        )
        if existing:
            crud.delete_user_project_role(session=session, db_upr=existing)

        crud.add_user_to_project_role(
            session=session,
            user_project_role_in=UserProjectRoleCreate(
                user_id=updated.requester_id,
                project_id=project_id,
                role_id=updated.role_id,
            )
        )

    translated_updated_request_dict = translate_request_item(updated.model_dump(), lang)

    return RequestPublic(data=[translated_updated_request_dict], count=1)


# 4. ✅ DELETE - chỉ admin được phép xoá request
@router.delete(
    "/{project_id}/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_request(
    project_id: UUID,
    request_id: UUID,
    session: SessionDep,
    info: ProjectAccessInfo,
):
    current_user, access_project_id, _ = info

    # Kiểm tra người dùng có đang thuộc project này không
    if project_id != access_project_id:
        raise HTTPException(status_code=403, detail="Không đúng phạm vi dự án")

    db_request = crud.get_request(session=session, request_id=request_id)
    if not db_request:
        raise HTTPException(status_code=404, detail="Request không tồn tại")

    # Kiểm tra request đó có thực sự thuộc project không
    if db_request.project_id != project_id:
        raise HTTPException(status_code=403, detail="Request không thuộc project này")

    crud.delete_request(session=session, db_request=db_request)