from fastapi import APIRouter

from app.api.routes import login, private, users, utils, projects, role, req, UserProjectRole, system, ecopark
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(projects.router)
api_router.include_router(role.router)
api_router.include_router(req.router)
api_router.include_router(UserProjectRole.router)
api_router.include_router(system.router)
api_router.include_router(ecopark.router)
# api_router.include_router(address.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
