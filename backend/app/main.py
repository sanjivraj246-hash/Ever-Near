import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.websocket import ws_manager
from app.db.session import engine, Base, SessionLocal
from app.database.seed import init_db
from app.api import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ever_near.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and run migration engine
    logger.info("Initializing database tables and verifying schema...")
    try:
        from app.db.migrate import run_migrations
        run_migrations(engine)
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        init_db(db)
        db.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization note: {e}")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Privacy-First Elderly Care & Routine Intelligence Full-Stack Platform",
    lifespan=lifespan
)

# 8. CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 9. API Error Handling (User-safe, zero technical stack trace leakage)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = " -> ".join([str(loc) for loc in err.get("loc", []) if loc != "body"])
        errors.append(f"{field}: {err.get('msg', 'Invalid input')}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Request validation failed. Please check your submitted details.", "errors": errors},
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )

# Health endpoints
@app.get("/health", tags=["Health"])
@app.get(f"{settings.API_V1_PREFIX}/health", tags=["Health"])
def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME, "version": settings.VERSION}

# Real-time WebSocket endpoint
@app.websocket("/ws/notifications/{user_id}")
async def websocket_notifications(
    websocket: WebSocket,
    user_id: int,
    role: str = Query("PARENT")
):
    await ws_manager.connect(websocket, user_id=user_id, role=role)
    logger.info(f"WebSocket connected: User {user_id} with role {role}")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type": "pong"}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id=user_id, role=role)
        logger.info(f"WebSocket disconnected: User {user_id}")
    except Exception as e:
        ws_manager.disconnect(websocket, user_id=user_id, role=role)
        logger.warning(f"WebSocket error for User {user_id}: {e}")

# Unified API Structure:
# Registers all domain routers cleanly under /api prefix and root prefix
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(api_router)

# Root Audit Logs endpoint (Step 14)
@app.get("/audit-logs", tags=["Audit Logs"])
@app.get(f"{settings.API_V1_PREFIX}/audit-logs", tags=["Audit Logs"])
def get_audit_logs_root():
    from app.db.session import SessionLocal
    from app.models.entities import AuditLog
    db = SessionLocal()
    try:
        logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(30).all()
        return [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "target_resource": log.target_resource,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "details": log.details,
                "ip_address": log.ip_address
            }
            for log in logs
        ]
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
