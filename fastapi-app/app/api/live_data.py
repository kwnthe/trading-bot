import json
from pathlib import Path
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.models.schemas import (
    LiveDataSummary, LiveDataSessions, MarkerRequest, APIResponse
)
from app.services.live_data_manager import (
    LiveDataManager, get_all_live_sessions, get_live_data_manager
)
from app.core.config import settings

router = APIRouter()


def cors_json_response(data: Any, status_code: int = 200) -> JSONResponse:
    """Helper function to add CORS headers to JSON responses"""
    response = JSONResponse(content=data, status_code=status_code)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


@router.get("/live/{uuid}/data")
async def live_data_serve(uuid: str) -> JSONResponse:
    """Serve the unified JSON data file for a specific UUID"""
    try:
        # Try multiple possible paths for different environments
        possible_paths = [
            # Windows path (where live runner creates files)
            settings.LIVE_DIR / uuid / "data.json",
            # Alternative paths for compatibility
            settings.BASE_DIR / "web-app" / "var" / "live" / uuid / "data.json",
        ]
        
        data_file = None
        for path in possible_paths:
            if path.exists():
                data_file = path
                break
        
        if data_file is None:
            attempted_paths = [str(p) for p in possible_paths]
            return cors_json_response({
                "error": "Data file not found", 
                "uuid": uuid, 
                "attempted_paths": attempted_paths
            }, status_code=404)
        
        print(f"DEBUG: Found data file at: {data_file}")
        
        # Serve the JSON file
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        return cors_json_response(data)
        
    except Exception as e:
        print(f"DEBUG: Error in live_data_serve: {e}")
        import traceback
        traceback.print_exc()
        return cors_json_response({"error": str(e), "uuid": uuid}, status_code=500)


@router.get("/live/{uuid}/summary")
async def live_data_summary(uuid: str) -> LiveDataSummary:
    """Get summary of live data for a specific UUID"""
    try:
        manager = get_live_data_manager(uuid)
        if manager is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data file not found for UUID: {uuid}"
            )
        
        summary_data = manager.get_summary()
        return LiveDataSummary(**summary_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/live/{uuid}/extensions/{extension_type}")
async def live_data_extension(uuid: str, extension_type: str) -> JSONResponse:
    """Get specific extension data for a UUID"""
    try:
        manager = get_live_data_manager(uuid)
        if manager is None:
            return cors_json_response({
                "error": "Data file not found", 
                "uuid": uuid
            }, status_code=404)
        
        extensions = manager.data.get("extensions", {})
        if extension_type not in extensions:
            return cors_json_response({
                "error": f"Extension '{extension_type}' not found", 
                "uuid": uuid
            }, status_code=404)
        
        return cors_json_response(extensions[extension_type])
        
    except Exception as e:
        return cors_json_response({"error": str(e), "uuid": uuid}, status_code=500)


@router.get("/live/sessions")
async def live_data_sessions() -> LiveDataSessions:
    """List all active live data sessions"""
    try:
        sessions_data = get_all_live_sessions()
        sessions = [LiveDataSession(**session) for session in sessions_data]
        return LiveDataSessions(sessions=sessions)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/live/{uuid}/cleanup")
async def live_data_cleanup(uuid: str) -> APIResponse:
    """Clean up old data for a specific UUID"""
    try:
        manager = get_live_data_manager(uuid)
        if manager is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data file not found for UUID: {uuid}"
            )
        
        removed_count = manager.cleanup_old_data(max_age_hours=24)
        
        return APIResponse(
            ok=True, 
            message=f"Cleanup completed for UUID {uuid}. Removed {removed_count} old data points."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/live/{uuid}/add_marker")
async def live_data_add_marker(uuid: str, request: MarkerRequest) -> APIResponse:
    """Add a marker to the live data"""
    try:
        manager = get_live_data_manager(uuid)
        if manager is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data file not found for UUID: {uuid}"
            )
        
        manager.add_marker(
            time=request.time,
            value=request.value,
            marker_type=request.marker_type,
            metadata=request.metadata
        )
        
        manager.save()
        
        return APIResponse(
            ok=True, 
            message=f"Marker added successfully to UUID {uuid}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
