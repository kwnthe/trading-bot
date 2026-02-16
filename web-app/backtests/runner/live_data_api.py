#!/usr/bin/env python3
"""
API endpoints for serving live data JSON files
"""
import json
import os
from pathlib import Path
from flask import Blueprint, jsonify, send_file
from typing import Dict, Any

# Create Blueprint
live_data_bp = Blueprint('live_data', __name__, url_prefix='/api/live')

@live_data_bp.route('/<uuid>/data')
def get_live_data(uuid: str):
    """Serve the unified JSON data file for a specific UUID"""
    try:
        data_file = Path(__file__).resolve().parent.parent.parent / "var" / "live" / uuid / "data.json"
        
        if not data_file.exists():
            return jsonify({"error": "Data file not found", "uuid": uuid}), 404
        
        return send_file(data_file, mimetype='application/json')
        
    except Exception as e:
        return jsonify({"error": str(e), "uuid": uuid}), 500

@live_data_bp.route('/<uuid>/summary')
def get_live_summary(uuid: str):
    """Get summary of live data for a specific UUID"""
    try:
        data_file = Path(__file__).resolve().parent.parent.parent / "var" / "live" / uuid / "data.json"
        
        if not data_file.exists():
            return jsonify({"error": "Data file not found", "uuid": uuid}), 404
        
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        summary = {
            "uuid": uuid,
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
        
        return jsonify(summary)
        
    except Exception as e:
        return jsonify({"error": str(e), "uuid": uuid}), 500

@live_data_bp.route('/<uuid>/extensions/<extension_type>')
def get_extension_data(uuid: str, extension_type: str):
    """Get specific extension data for a UUID"""
    try:
        data_file = Path(__file__).resolve().parent.parent.parent / "var" / "live" / uuid / "data.json"
        
        if not data_file.exists():
            return jsonify({"error": "Data file not found", "uuid": uuid}), 404
        
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        extensions = data.get("extensions", {})
        if extension_type not in extensions:
            return jsonify({"error": f"Extension '{extension_type}' not found", "uuid": uuid}), 404
        
        return jsonify(extensions[extension_type])
        
    except Exception as e:
        return jsonify({"error": str(e), "uuid": uuid}), 500

@live_data_bp.route('/sessions')
def list_live_sessions():
    """List all active live data sessions"""
    try:
        live_dir = Path(__file__).resolve().parent.parent.parent / "var" / "live"
        
        if not live_dir.exists():
            return jsonify({"sessions": []})
        
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
        
        return jsonify({"sessions": sessions})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@live_data_bp.route('/<uuid>/cleanup', methods=['POST'])
def cleanup_old_data(uuid: str):
    """Clean up old data for a specific UUID"""
    try:
        from web_app.backtests.runner.live_data_manager import LiveDataManager
        
        # Load existing data to get symbol and timeframe
        data_file = Path(__file__).resolve().parent.parent.parent / "var" / "live" / uuid / "data.json"
        
        if not data_file.exists():
            return jsonify({"error": "Data file not found", "uuid": uuid}), 404
        
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        symbol = data.get("metadata", {}).get("symbol", "Unknown")
        timeframe = data.get("metadata", {}).get("timeframe", "H1")
        
        # Create manager and cleanup
        manager = LiveDataManager(symbol, timeframe)
        manager.uuid = uuid
        manager.data_file = data_file
        manager.load()
        manager.cleanup_old_data(max_age_hours=24)
        
        return jsonify({"message": "Cleanup completed", "uuid": uuid})
        
    except Exception as e:
        return jsonify({"error": str(e), "uuid": uuid}), 500

@live_data_bp.route('/<uuid>/add_marker', methods=['POST'])
def add_marker(uuid: str):
    """Add a marker to the live data"""
    try:
        from web_app.backtests.runner.live_data_manager import LiveDataManager
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        required_fields = ["time", "value", "marker_type"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Load existing data
        data_file = Path(__file__).resolve().parent.parent.parent / "var" / "live" / uuid / "data.json"
        
        if not data_file.exists():
            return jsonify({"error": "Data file not found", "uuid": uuid}), 404
        
        symbol_data = json.load(data_file)
        symbol = symbol_data.get("metadata", {}).get("symbol", "Unknown")
        timeframe = symbol_data.get("metadata", {}).get("timeframe", "H1")
        
        # Create manager and add marker
        manager = LiveDataManager(symbol, timeframe)
        manager.uuid = uuid
        manager.data_file = data_file
        manager.load()
        
        manager.add_marker(
            time=data["time"],
            value=data["value"],
            marker_type=data["marker_type"],
            metadata=data.get("metadata", {})
        )
        
        manager.save()
        
        return jsonify({"message": "Marker added successfully", "uuid": uuid})
        
    except Exception as e:
        return jsonify({"error": str(e), "uuid": uuid}), 500

# Note: Need to import request for the add_marker endpoint
from flask import request
