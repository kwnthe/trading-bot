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

# Add WebSocket CORS middleware manually
@app.middleware("http")
async def add_websocket_cors(request, call_next):
    if request.url.path.startswith("/ws/"):
        origin = request.headers.get("origin")
        # Allow WebSocket connections from any origin in development
        if origin:
            # This is a WebSocket preflight request
            if request.method == "GET":
                response = await call_next(request)
                response.headers["Access-Control-Allow-Origin"] = "*"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Upgrade, Connection, Sec-WebSocket-Key, Sec-WebSocket-Version, Sec-WebSocket-Protocol"
                return response
    return await call_next(request)

# Include API routes
app.include_router(api_router, prefix="/api")
app.include_router(websocket_router)

# Serve React app
react_build_dir = Path(__file__).parent.parent / "react-app" / "dist"
if react_build_dir.exists():
    app.mount("/", StaticFiles(directory=str(react_build_dir), html=True), name="react")
else:
    # Static files (fallback)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    return {"message": "Trading Bot API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("WebSocket test successful!")
    await websocket.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.DEBUG else False
    )
