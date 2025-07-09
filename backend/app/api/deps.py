from collections.abc import Generator
from typing import Annotated, Tuple
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Path, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import TokenPayload, User, UserProjectRole, Role

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

# ================== Superuser Check ==================
def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Chưa được xác thực")
    return current_user

# ================== Active User Check ==================
def get_current_active_user(current_user: CurrentUser) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Tài khoản bị vô hiệu hoá")
    return current_user


# ================== User's Role In Project ==================
def get_current_user_role_in_project(
    project_id: UUID, 
    session: SessionDep,
    current_user: CurrentUser
) -> Tuple[User, UUID, int]:  # User, role_id, rank
    result = session.exec(
        select(UserProjectRole.role_id, Role.rank)
        .join(Role, Role.id == UserProjectRole.role_id)
        .where(
            UserProjectRole.user_id == current_user.id,
            UserProjectRole.project_id == project_id
        )
    ).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập dự án này.",
        )

    role_id, rank = result
    return current_user, project_id, rank

ProjectAccessInfo = Annotated[Tuple[User, UUID, int], Depends(get_current_user_role_in_project)]

# ================== Rank Check Middleware ==================
def verify_rank_in_project(min_rank: int):
    def checker(info: ProjectAccessInfo) -> Tuple[User, UUID, int]:
        current_user, role_id, rank = info
        if rank > min_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bạn cần quyền có rank <= {min_rank} để thực hiện hành động này.",
            )
        return current_user, role_id, rank
    return checker