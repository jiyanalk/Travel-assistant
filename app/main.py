from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.trip_ws import router as trip_ws_router
from api.routes.user import router as user_router
from app.config import get_settings
from db.session import init_db


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Travel Planning Agent MVP powered by FastAPI and LangGraph.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+|192\.168\.\d+\.\d+):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(trip_ws_router, tags=["trip-websocket"])
app.include_router(user_router, prefix="/api/users", tags=["users"])
