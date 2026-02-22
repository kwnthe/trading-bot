from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
from pathlib import Path

from app.api import api_router
from app.websocket import websocket_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("FastAPI trading bot API starting up...")
    yield
    # Shutdown
    print("FastAPI trading bot API shutting down...")


app = FastAPI(
    title="Trading Bot API",
    description="FastAPI replacement for Django trading bot backend",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")
app.include_router(websocket_router)

# Static files (if needed for any remaining static content)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    return {"message": "Trading Bot API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.DEBUG else False
    )
