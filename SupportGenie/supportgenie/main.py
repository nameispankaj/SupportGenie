"""
Main FastAPI application entrypoint for SupportGenie.
Configures static files, Jinja2 HTML templates, API routers, and health check endpoints.
"""

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from supportgenie import __version__
from supportgenie.api.email_routes import router as email_router
from supportgenie.api.ticket_routes import router as ticket_router
from supportgenie.config import get_settings
from supportgenie.database import db_manager

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="SupportGenie — Email and AI-Assisted Support Ticket Management System",
    description=(
        "Local support desk web application connecting to SQL Server (JotDeskBuddy_Test) "
        "with a Gmail-inspired Email interface and rule-based NLP ticket analysis."
    ),
    version=__version__,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app.include_router(ticket_router)
app.include_router(email_router)


@app.get("/health", tags=["Health"])
def health_check() -> Dict[str, Any]:
    """
    Application health endpoint.
    Confirms the FastAPI process is running. Does NOT claim SQL Server is connected;
    use /health/db to verify database connectivity.
    """
    cfg = get_settings()
    return {
        "status": "ok",
        "application": "SupportGenie",
        "version": __version__,
        "smtp_configured": cfg.is_smtp_configured,
        "database_check_endpoint": "/health/db",
        "note": "Application process is healthy. Call GET /health/db to verify SQL Server connectivity.",
    }


@app.get("/health/db", tags=["Health"])
def database_health_check() -> JSONResponse:
    """
    Database connectivity endpoint.
    Tests the pyodbc connection to SQL Server and checks that dbo.Tickets and dbo.Clients exist,
    without exposing server names, usernames, or passwords.
    """
    status_info = db_manager.check_connectivity()
    http_code = 200 if status_info.get("connected") and status_info.get("schema_valid") else 503
    return JSONResponse(status_code=http_code, content=status_info)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root_page(request: Request) -> HTMLResponse:
    """Render the Support Ticket Management interface as the default landing page."""
    cfg = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="support.html",
        context={
            "active_page": "support",
            "default_associate_id": cfg.default_associate_id,
            "default_associate_name": cfg.default_associate_name,
        },
    )


@app.get("/support", response_class=HTMLResponse, include_in_schema=False)
def support_page(request: Request) -> HTMLResponse:
    """Render the Support Ticket Management page."""
    cfg = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="support.html",
        context={
            "active_page": "support",
            "default_associate_id": cfg.default_associate_id,
            "default_associate_name": cfg.default_associate_name,
        },
    )


@app.get("/email", response_class=HTMLResponse, include_in_schema=False)
def email_page(request: Request) -> HTMLResponse:
    """Render the Gmail-inspired Email interface."""
    cfg = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="email.html",
        context={
            "active_page": "email",
            "support_team_email": cfg.support_team_email,
            "smtp_configured": cfg.is_smtp_configured,
            "default_associate_id": cfg.default_associate_id,
            "default_associate_name": cfg.default_associate_name,
        },
    )
