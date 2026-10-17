# SupportGenie (Phase 1)

SupportGenie is a FastAPI + vanilla HTML/CSS/JS support ticket analysis app for L1/L2/Bug-PBI triage.

## Schema inspection findings (authoritative SQL scripts)

Searched repository for:
- `SupportGenie_Full_Test_Database.sql`
- `SupportGenie_Existing_Database_Seed_Data.sql`

Result: **files are not present in this repository clone**.

Because scripts were unavailable, no authoritative extraction of actual tables, columns, PK/FK, or identity definitions was possible from source SQL files. The backend therefore uses:
- Demo mode synthetic data by default.
- Live SQL mode with explicit, environment-configurable table/column mappings.
- Runtime schema checks via `INFORMATION_SCHEMA.COLUMNS` before query execution.

### Conflict with requested model
Requested strict schema-driven implementation from those scripts; this could not be fully completed because the scripts were absent. No schema was invented as authoritative; assumptions are explicitly configurable in `.env`.

## Features

- `GET /health`
- `GET /api/dashboard`
- `GET /api/tickets` (server-side paging/filter/sort)
- `GET /api/tickets/{ticket_id}`
- `GET /api/tickets/{ticket_id}/history`
- `POST /api/tickets/{ticket_id}/analyze`
- `POST /api/tickets/{ticket_id}/notes` (Phase 1 in-memory note capture)
- Deterministic NLP classification into exactly 8 categories.

## Project layout

```text
supportgenie/
  api/routes.py
  config.py
  main.py
  schemas.py
  db/
    factory.py
    models.py
    repository.py
  services/
    analysis_service.py
  data/synthetic_tickets.py
  frontend/
    index.html
    styles.css
    app.js
tests/
```

## Windows PowerShell setup (Python 3.12)

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

## SQL Server ODBC driver

Install Microsoft ODBC Driver 18 for SQL Server (Windows), then confirm:

```powershell
python -c "import pyodbc; print(pyodbc.drivers())"
```

## Configure `.env`

### Demo mode (default)

```env
SUPPORTGENIE_DEMO_MODE=true
```

### Live SQL mode

```env
SUPPORTGENIE_DEMO_MODE=false
SQL_SERVER_HOST=your-server
SQL_SERVER_DATABASE=JotDeskBuddy_Test
SQL_SERVER_AUTH_MODE=sql
SQL_SERVER_USERNAME=...
SQL_SERVER_PASSWORD=...
```

For Windows integrated auth:

```env
SQL_SERVER_AUTH_MODE=windows
```

Also update `SUPPORTGENIE_*_TABLE` and `SUPPORTGENIE_*_COLUMN` values to match your actual schema.

## Verify SQL connectivity

```powershell
python -c "from supportgenie.db.factory import get_ticket_repository; print(get_ticket_repository().health())"
```

## Run backend

```powershell
uvicorn supportgenie.main:app --host 127.0.0.1 --port 8000 --reload
```

- Open Swagger docs: `http://127.0.0.1:8000/docs`
- Open UI: `http://127.0.0.1:8000/`

## Frontend notes

The frontend is plain HTML/CSS/JS and uses only API responses (no fake AI chat).
Includes:
- Dashboard metrics
- Ticket list with filters + pagination
- Ticket detail/history view
- Analyze Ticket workflow
- Copy analysis action
- Loading/error/empty states
- Record note action via backend

## Testing

```powershell
pytest -q
```

## CORS

Allowed frontend origin is controlled by:

```env
SUPPORTGENIE_FRONTEND_ORIGIN=http://127.0.0.1:5500
```

## Troubleshooting

- **Import error for pyodbc**: ensure ODBC driver is installed and venv active.
- **DB connectivity error**: verify host, auth mode, credentials, firewall.
- **Schema unavailable**: update configured table/column mapping to real names.
- **CORS blocked**: set `SUPPORTGENIE_FRONTEND_ORIGIN` to frontend URL.
- **No data in live mode**: verify mapping columns exist in `INFORMATION_SCHEMA.COLUMNS`.

## Security

- Credentials are environment-only; never commit `.env`.
- SQL queries use parameter binding for user inputs.
- Sort/filter fields are validated and restricted.
- API returns sanitized operational errors.

## Phase 2 compatibility

Analysis logic is isolated in `supportgenie/services/analysis_service.py`, so a future Azure AI Search / Azure AI Foundry / Agent Framework implementation can replace the analysis backend while keeping frontend contracts stable.

## Note on persistence/migrations

No schema migration is applied in Phase 1. If persistent analysis records are required, add a separate reviewed migration script outside this implementation.
