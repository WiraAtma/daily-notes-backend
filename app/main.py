import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api import ai, auth, notes, uploads
from app.core.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(notes.router)
app.include_router(uploads.router)
app.include_router(ai.router)

@app.get("/")
async def welcome():
    return {
        "message": "Welcome to Daily Notes API",
        "status": "success",
    }

@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    logger.error("Database operation failed", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable"},
    )
