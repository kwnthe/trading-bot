# Trading Bot FastAPI

FastAPI trading bot backend for automated trading and backtesting.

## Features

- **Type Safety**: Full Pydantic validation
- **Performance**: Async/await throughout
- **Documentation**: Auto-generated OpenAPI docs
- **Testing**: Better async testing support
- **Deployment**: Single file deployment option

- **REST API**: Complete trading bot API endpoints
- **WebSocket Support**: Real-time chart streaming and live trading updates
- **File-based Storage**: No database required
- **Async Support**: High-performance async/await throughout
- **CORS Support**: Configured for frontend integration

## Quick Start

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your configuration
```

### Running the Server

```bash
# Development
python main.py

# Or with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Backtest Operations
- `GET /api/params` - Get parameter definitions
- `GET /api/strategies` - Get available strategies
- `POST /api/run` - Run a backtest
- `GET /api/jobs/{job_id}/status` - Get job status
- `GET /api/jobs/{job_id}/result` - Get job results

### Live Trading
- `GET /api/live/active` - Get active session
- `POST /api/live/run` - Start live trading
- `GET /api/live/{session_id}/status` - Get session status
- `GET /api/live/{session_id}/snapshot` - Get session snapshot
- `POST /api/live/{session_id}/stop` - Stop live trading

### Live Data
- `GET /api/live/{uuid}/data` - Get live data JSON
- `GET /api/live/{uuid}/summary` - Get data summary
- `GET /api/live/{uuid}/extensions/{type}` - Get extension data
- `GET /api/live/sessions` - List all sessions
- `POST /api/live/{uuid}/cleanup` - Clean old data
- `POST /api/live/{uuid}/add_marker` - Add chart marker

### Presets
- `GET /api/presets` - List presets
- `POST /api/presets` - Save preset
- `GET /api/presets/{name}` - Get preset
- `DELETE /api/presets/{name}` - Delete preset

## WebSocket

### Connection
```
ws://localhost:8000/ws/live/{session_id}
```

### Message Types

**From Server:**
- `connection_established` - Initial connection
- `chart_update` - Chart overlay updates
- `status_update` - Trading status changes
- `error` - Error messages

**To Server:**
- `ping` - Keep-alive
- `subscribe` - Subscribe to data types

### Example Messages

```javascript
// Client sends ping
{
  "type": "ping"
}

// Server responds
{
  "type": "pong",
  "timestamp": "2024-01-01T12:00:00Z"
}

// Chart update
{
  "type": "chart_update",
  "session_id": "abc-123",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "zones": [...],
    "ema": [...],
    "markers": [...]
  }
}
```

## Project Structure

```
fastapi-app/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── app/
│   ├── api/
│   │   ├── __init__.py    # API router setup
│   │   ├── backtests.py   # Backtest endpoints
│   │   ├── live_data.py   # Live data endpoints
│   │   └── deps.py        # Dependencies and utilities
│   ├── core/
│   │   └── config.py      # Configuration settings
│   ├── models/
│   │   └── schemas.py     # Pydantic models
│   ├── services/
│   │   ├── params.py      # Parameter definitions
│   │   ├── job_store.py   # Job management
│   │   ├── live_store.py  # Live session management
│   │   ├── presets_store.py # Preset management
│   │   └── live_data_manager.py # Live data handling
│   └── websocket/
│       ├── __init__.py    # WebSocket router
│       ├── connection_manager.py # Connection management
│       └── handlers.py    # WebSocket handlers
└── tests/                 # Unit tests
```

## Development

### Running Tests
```bash
pytest
pytest --cov=app  # With coverage
```

### Code Style
```bash
# Install development dependencies
pip install black flake8 mypy

# Format code
black app/

# Lint
flake8 app/

# Type check
mypy app/
```

## Configuration

Key environment variables:

- `DEBUG` - Enable debug mode (default: True)
- `SECRET_KEY` - FastAPI secret key
- `DEFAULT_TIMEFRAME` - Default trading timeframe (default: H1)
- `DEFAULT_SYMBOLS` - Default trading symbols (default: XAGUSD)
- `WS_HEARTBEAT_INTERVAL` - WebSocket heartbeat interval (default: 30)

## Deployment

### Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Systemd Service
```ini
[Unit]
Description=Trading Bot FastAPI
After=network.target

[Service]
User=tradingbot
WorkingDirectory=/opt/trading-bot/fastapi-app
Environment=PATH=/opt/trading-bot/fastapi-app/venv/bin
ExecStart=/opt/trading-bot/fastapi-app/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

### Common Issues

1. **Port already in use**: Change port in command or kill existing process
2. **Permission errors**: Check file permissions for var/ directory
3. **WebSocket connection fails**: Check firewall and CORS settings
4. **Live trading not starting**: Verify MT5 configuration

### Debug Mode

Enable debug mode in `.env`:
```
DEBUG=True
```

This will provide:
- Detailed error messages
- Auto-reload on code changes
- Debug logging

## License

Same as the original project.
