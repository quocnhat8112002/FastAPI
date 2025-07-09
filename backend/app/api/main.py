from fastapi import APIRouter

from app.api.routes import login, private, users, utils, projects, role, req, UserProjectRole
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(projects.router)
api_router.include_router(role.router)
api_router.include_router(req.router)
api_router.include_router(UserProjectRole.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
