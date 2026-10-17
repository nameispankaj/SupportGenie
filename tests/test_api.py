from fastapi.testclient import TestClient

from supportgenie.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}


def test_dashboard_endpoint() -> None:
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["total_tickets"] >= 1
    assert "tickets_by_urgency" in body


def test_tickets_list_pagination_filter_and_sort() -> None:
    response = client.get("/api/tickets", params={"page": 1, "page_size": 2, "sort_by": "ticket_id", "sort_dir": "asc"})
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) <= 2

    filtered = client.get("/api/tickets", params={"status": "Open"})
    assert filtered.status_code == 200
    assert all((item["status"] or "").lower().find("open") >= 0 for item in filtered.json()["items"])


def test_tickets_list_rejects_unsafe_sort_column() -> None:
    response = client.get("/api/tickets", params={"sort_by": "drop table"})
    assert response.status_code == 400


def test_ticket_detail_history_analyze_and_note() -> None:
    detail = client.get("/api/tickets/TKT-1001")
    assert detail.status_code == 200

    history = client.get("/api/tickets/TKT-1001/history")
    assert history.status_code == 200

    analysis = client.post("/api/tickets/TKT-1001/analyze")
    assert analysis.status_code == 200
    payload = analysis.json()
    assert payload["ticket_category"] == "Product Bug"
    assert payload["handling_level"] == "Bug/PBI"

    note = client.post("/api/tickets/TKT-1001/notes", json={"note": "Requested crash logs from customer"})
    assert note.status_code == 201

    updated_history = client.get("/api/tickets/TKT-1001/history")
    assert any("Requested crash logs" in item["message"] for item in updated_history.json()["history"])


def test_ticket_not_found() -> None:
    response = client.get("/api/tickets/NOPE")
    assert response.status_code == 404
