"""
Chart utility functions for converting chart overlay data formats.
"""

def convert_chart_points_to_line_segments(points, duration_seconds):
    """
    Convert point-based chart data to line segments for chart rendering.
    
    Args:
        points: List of point dictionaries with 'time' and 'price' keys
        duration_seconds: Duration of each line segment in seconds (should match candle timeframe)
        
    Returns:
        List of segment dictionaries with 'startTime', 'endTime', and 'value' keys
    """
    segments = []
    for point in points:
        # Extract timestamp and price from point
        start_time = point["time"]
        price_value = point["price"]
        
        # Create line segment spanning the specified duration
        end_time = start_time + duration_seconds
        
        segment = {
            "startTime": start_time,
            "endTime": end_time, 
            "value": price_value
        }
        segments.append(segment)
    
    return segments


def filter_zones_by_type(zones, zone_type):
    """
    Filter zones by their type (support or resistance).
    
    Args:
        zones: List of zone dictionaries
        zone_type: Type to filter for ('support' or 'resistance')
        
    Returns:
        List of zones matching the specified type
    """
    return [z for z in zones if z.get("type") == zone_type]


def prepare_chart_data_for_frontend(overlay_data, timeframe_seconds):
    """
    Prepare chart overlay data for frontend consumption.
    
    Args:
        overlay_data: Raw overlay data from ChartOverlayManager
        timeframe_seconds: Duration for zone segments based on timeframe
        
    Returns:
        Dictionary with properly formatted chart data
    """
    # Separate support and resistance zones
    zones = overlay_data["zones"]
    support_zones = filter_zones_by_type(zones, "support")
    resistance_zones = filter_zones_by_type(zones, "resistance")
    
    # Convert point-based zones to line segments
    support_segments = convert_chart_points_to_line_segments(support_zones, timeframe_seconds)
    resistance_segments = convert_chart_points_to_line_segments(resistance_zones, timeframe_seconds)
    
    return {
        "support_segments": support_segments,
        "resistance_segments": resistance_segments,
        "ema_points": overlay_data["ema"],
        "markers": overlay_data["markers"],
        "order_boxes": overlay_data["orderBoxes"],
        "trades": overlay_data["trades"]
    }
