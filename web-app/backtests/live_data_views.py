"""
Django views for live data API
"""
import json
import os
from pathlib import Path
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from .runner.live_data_manager import LiveDataManager
import traceback

def cors_json_response(data, status=200):
    """Helper function to add CORS headers to JSON responses"""
    response = JsonResponse(data, status=status)
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

def cors_response(data, status=200):
    """Helper function to add CORS headers to any response"""
    if isinstance(data, str):
        response = HttpResponse(data, status=status)
    else:
        response = JsonResponse(data, status=status)
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

def live_data_serve(request, uuid):
    """Serve the unified JSON data file for a specific UUID"""
    try:
        # Try multiple possible paths for different environments
        possible_paths = [
            # Windows path (where live runner creates files)
            Path(__file__).resolve().parent.parent / "var" / "live" / str(uuid) / "data.json",
            # Mac/Linux path (fallback)
            Path(__file__).resolve().parent.parent.parent / "var" / "live" / str(uuid) / "data.json",
            # Alternative Windows path
            Path(__file__).resolve().parent.parent.parent.parent / "web-app" / "var" / "live" / str(uuid) / "data.json",
        ]
        
        data_file = None
        for path in possible_paths:
            if path.exists():
                data_file = path
                break
        
        if data_file is None:
            # Return error with all attempted paths for debugging
            attempted_paths = [str(p) for p in possible_paths]
            return cors_json_response({
                "error": "Data file not found", 
                "uuid": str(uuid), 
                "attempted_paths": attempted_paths
            }, status=404)
        
        print(f"DEBUG: Found data file at: {data_file}")
        
        # Serve the JSON file
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        return cors_json_response(data)
        
    except Exception as e:
        print(f"DEBUG: Error in live_data_serve: {e}")
        import traceback
        traceback.print_exc()
        return cors_json_response({"error": str(e), "uuid": str(uuid)}, status=500)

def live_data_summary(request, uuid):
    """Get summary of live data for a specific UUID"""
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        data_file = project_root / "var" / "live" / str(uuid) / "data.json"
        
        if not data_file.exists():
            return cors_json_response({"error": "Data file not found", "uuid": str(uuid)}, status=404)
        
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        summary = {
            "uuid": str(uuid),
            "symbol": data.get("metadata", {}).get("symbol", "Unknown"),
            "timeframe": data.get("metadata", {}).get("timeframe", "Unknown"),
            "last_updated": data.get("metadata", {}).get("last_updated", 0),
            "candles_count": len(data.get("candles", [])),
            "support_zones_count": len(data.get("zones", {}).get("supportSegments", [])),
            "resistance_zones_count": len(data.get("zones", {}).get("resistanceSegments", [])),
            "ema_points_count": len(data.get("ema", [])),
            "markers_count": len(data.get("chart_data", {}).get("markers", {}).get("points", [])),
            "breakouts_count": len(data.get("extensions", {}).get("breakouts", [])),
            "events_count": len(data.get("extensions", {}).get("events", [])),
            "custom_indicators": list(data.get("extensions", {}).get("custom_indicators", {}).keys()),
            "file_size": data_file.stat().st_size
        }
        
        return cors_json_response(summary)
        
    except Exception as e:
        return cors_json_response({"error": str(e), "uuid": str(uuid)}, status=500)

def live_data_extension(request, uuid, extension_type):
    """Get specific extension data for a UUID"""
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        data_file = project_root / "var" / "live" / str(uuid) / "data.json"
        
        if not data_file.exists():
            return cors_json_response({"error": "Data file not found", "uuid": str(uuid)}, status=404)
        
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        extensions = data.get("extensions", {})
        if extension_type not in extensions:
            return cors_json_response({"error": f"Extension '{extension_type}' not found", "uuid": str(uuid)}, status=404)
        
        return cors_json_response(extensions[extension_type])
        
    except Exception as e:
        return cors_json_response({"error": str(e), "uuid": str(uuid)}, status=500)

def live_data_sessions(request):
    """List all active live data sessions"""
    try:
        # Try multiple possible paths for different environments
        possible_live_dirs = [
            # Windows path (where live runner creates files)
            Path(__file__).resolve().parent.parent / "var" / "live",
            # Mac/Linux path (fallback)
            Path(__file__).resolve().parent.parent.parent / "var" / "live",
            # Alternative Windows path
            Path(__file__).resolve().parent.parent.parent.parent / "web-app" / "var" / "live",
        ]
        
        live_dir = None
        for path in possible_live_dirs:
            if path.exists():
                live_dir = path
                break
        
        if live_dir is None:
            return cors_json_response({"sessions": [], "attempted_paths": [str(p) for p in possible_live_dirs]})
        
        print(f"DEBUG: Found live directory at: {live_dir}")
        
        sessions = []
        for uuid_dir in live_dir.iterdir():
            if uuid_dir.is_dir():
                data_file = uuid_dir / "data.json"
                if data_file.exists():
                    try:
                        with open(data_file, 'r') as f:
                            data = json.load(f)
                        
                        session_info = {
                            "uuid": uuid_dir.name,
                            "symbol": data.get("metadata", {}).get("symbol", "Unknown"),
                            "timeframe": data.get("metadata", {}).get("timeframe", "Unknown"),
                            "last_updated": data.get("metadata", {}).get("last_updated", 0),
                            "created_at": data.get("metadata", {}).get("created_at", 0),
                            "file_size": data_file.stat().st_size
                        }
                        sessions.append(session_info)
                    except:
                        continue
        
        # Sort by last_updated (most recent first)
        sessions.sort(key=lambda x: x["last_updated"], reverse=True)
        
        return cors_json_response({"sessions": sessions})
        
    except Exception as e:
        return cors_json_response({"error": str(e)}, status=500)

@require_http_methods(["POST"])
@csrf_exempt
def live_data_cleanup(request, uuid):
    """Clean up old data for a specific UUID"""
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        data_file = project_root / "var" / "live" / str(uuid) / "data.json"
        
        if not data_file.exists():
            return cors_json_response({"error": "Data file not found", "uuid": str(uuid)}, status=404)
        
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        symbol = data.get("metadata", {}).get("symbol", "Unknown")
        timeframe = data.get("metadata", {}).get("timeframe", "H1")
        
        # Create manager and cleanup
        manager = LiveDataManager(symbol, timeframe)
        manager.uuid = str(uuid)
        manager.data_file = data_file
        manager.load()
        manager.cleanup_old_data(max_age_hours=24)
        
        return cors_json_response({"message": "Cleanup completed", "uuid": str(uuid)})
        
    except Exception as e:
        return cors_json_response({"error": str(e), "uuid": str(uuid)}, status=500)

@require_http_methods(["POST"])
@csrf_exempt
def live_data_add_marker(request, uuid):
    """Add a marker to the live data"""
    try:
        # Parse JSON body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return cors_json_response({"error": "Invalid JSON in request body"}, status=400)
        
        required_fields = ["time", "value", "marker_type"]
        for field in required_fields:
            if field not in data:
                return cors_json_response({"error": f"Missing required field: {field}"}, status=400)
        
        # Load existing data
        project_root = Path(__file__).resolve().parent.parent.parent
        data_file = project_root / "var" / "live" / str(uuid) / "data.json"
        
        if not data_file.exists():
            return cors_json_response({"error": "Data file not found", "uuid": str(uuid)}, status=404)
        
        symbol_data = json.load(data_file)
        symbol = symbol_data.get("metadata", {}).get("symbol", "Unknown")
        timeframe = symbol_data.get("metadata", {}).get("timeframe", "H1")
        
        # Create manager and add marker
        manager = LiveDataManager(symbol, timeframe)
        manager.uuid = str(uuid)
        manager.data_file = data_file
        manager.load()
        
        manager.add_marker(
            time=data["time"],
            value=data["value"],
            marker_type=data["marker_type"],
            metadata=data.get("metadata", {})
        )
        
        manager.save()
        
        return cors_json_response({"message": "Marker added successfully", "uuid": str(uuid)})
        
    except Exception as e:
        return cors_json_response({"error": str(e), "uuid": str(uuid)}, status=500)
