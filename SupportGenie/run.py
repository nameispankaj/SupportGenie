"""
Single-command startup script for SupportGenie.
Usage:
    python run.py

Starts the FastAPI application using Uvicorn.
Does NOT create, drop, reset, or seed the SQL Server database.
"""

import uvicorn
from supportgenie.config import get_settings


def main() -> None:
    settings = get_settings()
    print("=" * 68)
    print("Starting SupportGenie — Email & Support Ticket Management System")
    print(f"URL:              http://{settings.app_host}:{settings.app_port}")
    print(f"Support Console:  http://{settings.app_host}:{settings.app_port}/support")
    print(f"Email Console:    http://{settings.app_host}:{settings.app_port}/email")
    print(f"API Docs:         http://{settings.app_host}:{settings.app_port}/docs")
    print(f"Health Check:     http://{settings.app_host}:{settings.app_port}/health/db")
    print("=" * 68)
    uvicorn.run(
        "supportgenie.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )


if __name__ == "__main__":
    main()
