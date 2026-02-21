from fastapi import APIRouter
from . import backtests, live_data

api_router = APIRouter()

# Include all API routes
api_router.include_router(backtests.router, tags=["backtests"])
api_router.include_router(live_data.router, tags=["live-data"])