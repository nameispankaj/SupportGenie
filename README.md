# SupportGenie

SupportGenie is a Python/FastAPI prototype for AI-assisted support ticket analysis across an L1/L2/Scrum/DevOps workflow.

## Features

- Health endpoint: `GET /health`
- Ticket analysis endpoint: `POST /ticket-analysis`
- Accepts existing ticket ID or manual issue description
- Enforces tenant isolation and per-ticket authorization for ticket lookups
- Classifies into exactly one category:
  - Product Bug
  - Data Issue
  - Configuration Issue
  - Permission Issue
  - Integration Issue
  - Expected Behaviour
  - Change Request
  - Insufficient Information
- Returns likely root cause, possible resolution, verified evidence, hypotheses, confidence, missing information, clarifying questions, and L1/L2/Bug-PBI recommendation
- Demo-safe synthetic repository and read-only data access pattern

## Project structure

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
    agent_orchestration.py
    analysis_service.py
    rag_service.py
  data/synthetic_tickets.py
tests/
requirements.txt
.env.example
```

## Windows local setup

1. Install Python 3.11+.
2. Open PowerShell in repository root.
3. Create virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
4. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
5. Copy environment template:
   ```powershell
   Copy-Item .env.example .env
   ```
6. Run API:
   ```powershell
   uvicorn supportgenie.main:app --reload
   ```
7. Run web UI:
   ```powershell
   streamlit run supportgenie/ui/app.py
   ```

## API usage

### Health check

```http
GET /health
```

### Ticket analysis

```http
POST /ticket-analysis
X-Tenant-Id: tenant-acme
X-User-Id: alice
Content-Type: application/json

{"ticket_id": "TKT-1001"}
```

or

```json
{"issue_description": "Salesforce integration API returns 401 during sync."}
```

## Demo mode and planned integrations

The app starts in **demo mode** by default (`SUPPORTGENIE_DEMO_MODE=true`) and uses synthetic tickets instead of live SQL Server.

UI defaults (optional):

- `SUPPORTGENIE_UI_DEFAULT_TENANT_ID` (default `tenant-acme`)
- `SUPPORTGENIE_UI_DEFAULT_USER_ID` (default `alice`)

Planned production integrations:

1. **Microsoft Agent Framework orchestration**
   - Integrate supported Microsoft Agent Framework package versions in your environment.
   - Keep orchestration in `supportgenie/services/agent_orchestration.py`.
2. **Azure AI Foundry model calls**
   - Configure Foundry endpoint and API key in environment variables.
   - Add provider-specific client setup in analysis/orchestration service.
3. **Azure AI Search RAG retrieval**
   - Replace `RAGService` stub with Azure AI Search index queries.
4. **Authorized SQL Server access**
   - Replace synthetic repository with read-only SQL implementation.
   - Continue enforcing tenant isolation and authorization in repository layer.

## Security notes

- Never commit real credentials, connection strings, or customer data.
- Keep secrets in `.env` (local only) or secure secret stores.
- Do not allow arbitrary model-generated SQL.
- Do not perform production-changing actions (ticket closure, permissions changes, Azure DevOps writes) without explicit authorization.

## Tests

Run:

```bash
pytest -q
```
