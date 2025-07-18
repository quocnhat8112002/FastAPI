import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
import os

from app.api.main import api_router
from app.core.config import settings
from app.core.mqtt import get_mqtt_client, mqtt_client


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"

# ✅ MQTT Lifespan handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # MQTT startup
    get_mqtt_client()
    yield
    # MQTT shutdown
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Mount static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/api/v1/static", StaticFiles(directory=STATIC_DIR), name="static")

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )



app.include_router(api_router, prefix=settings.API_V1_STR)
