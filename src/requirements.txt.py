# Core runtime
pyside6==6.7.2          # QML UI (Milestone 5)
pyqt6==6.7.0            # Optional compatibility
qt-material==2.14       # Future theme support

# API + server (Milestone 4)
fastapi==0.110.0
uvicorn==0.29.0
pydantic==2.7.1

# Task + async support
anyio==4.3.0
httpx==0.27.0

# Data + persistence
python-dotenv==1.0.1
orjson==3.10.0          # Fast JSON for persistence
tinydb==4.8.0           # Lightweight DB for Milestone 3–4

# Observability
loguru==0.7.2

# Agents (Weather + News)
feedparser==6.0.11      # News agent (RSS parsing)
requests==2.31.0        # Weather + News HTTP (Milestone 4 upgrade)

# OneNote Agent (local simulation)
markdown==3.6           # Optional formatting for OneNote pages

# Testing
pytest==8.2.0
pytest-asyncio==0.23.5

# Typing + linting
mypy==1.10.0
ruff==0.4.2
