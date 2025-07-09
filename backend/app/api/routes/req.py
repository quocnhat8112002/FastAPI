from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select
from uuid import UUID
from typing import List
from datetime import datetime

from app.models import (
    Request,
    Request as RequestModel,
    RequestCreate,
    RequestUpdate,
    RequestPublic,
    Role,
)
from app.api.deps import (
    SessionDep,
    ProjectAccessInfo,
    get_current_active_user,
    get_current_user
)
from app.models import User
import app.crud as crud

router = APIRouter(prefix="/req", tags=["Request"])


@router.get("/", response_model=RequestPublic)
def get_requests_by_project(
    session: SessionDep,
    project_info: ProjectAccessInfo,
    current_user=Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
):
    user, project_id, user_rank = project_info

    # Nếu là superuser thì truy vấn tất cả request trong project
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

    # Nếu là user thường → chỉ xem các request xin cấp quyền có role.rank > user.rank
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

    return RequestPublic(data=requests, count=len(total))

# 2. ✅ POST - tạo request (chỉ được yêu cầu role có rank >= 3)
@router.post(
    "/",
    response_model=RequestPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_active_user)],
)
def create_request(
    request_data: RequestCreate,
    session: SessionDep,
    info: ProjectAccessInfo,
):
    current_user, _, _ = info

    role = session.get(Role, request_data.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Vai trò không tồn tại")

    if role.rank < 3:
        raise HTTPException(
            status_code=403,
            detail="Chỉ được yêu cầu các vai trò có rank >= 3 (thấp quyền hơn)",
        )

    new_request = RequestModel(
        **request_data.dict(),
        requester_id=current_user.id,
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    session.add(new_request)
    session.commit()
    session.refresh(new_request)
    return new_request


# 3. ✅ PUT - cập nhật trạng thái (chỉ xử lý nếu request có rank < mình)
@router.put(
    "/{request_id}",
    response_model=RequestPublic,
    dependencies=[Depends(get_current_active_user)],
)
def update_request_status(
    request_id: UUID,
    update_data: RequestUpdate,
    session: SessionDep,
    info: ProjectAccessInfo,
):
    current_user, project_id, current_rank = info

    db_request = session.get(RequestModel, request_id)
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

    db_request.status = update_data.status
    db_request.response_message = update_data.response_message
    db_request.approver_id = current_user.id
    db_request.updated_at = datetime.utcnow()

    session.add(db_request)
    session.commit()
    session.refresh(db_request)
    return db_request


# 4. ✅ DELETE - chỉ admin được phép xoá request
@router.delete(
    "/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_active_user)],
)
def delete_request(
    request_id: UUID,
    session: SessionDep,
    info: ProjectAccessInfo,
):
    current_user, _, _ = info

    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Chỉ admin được phép xoá request")

    db_request = session.get(RequestModel, request_id)
    if not db_request:
        raise HTTPException(status_code=404, detail="Request không tồn tại")

    session.delete(db_request)
    session.commit()
