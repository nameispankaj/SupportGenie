from fastapi.testclient import TestClient

from supportgenie.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ticket_analysis_by_ticket_id_success() -> None:
    response = client.post(
        "/ticket-analysis",
        headers={"X-Tenant-Id": "tenant-acme", "X-User-Id": "alice"},
        json={"ticket_id": "TKT-1001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "Product Bug"
    assert body["context"]["ticket_id"] == "TKT-1001"
    assert len(body["verified_evidence"]) > 0


def test_ticket_analysis_enforces_tenant_isolation() -> None:
    response = client.post(
        "/ticket-analysis",
        headers={"X-Tenant-Id": "tenant-beta", "X-User-Id": "alice"},
        json={"ticket_id": "TKT-1001"},
    )
    assert response.status_code == 403


def test_ticket_analysis_manual_input() -> None:
    response = client.post(
        "/ticket-analysis",
        headers={"X-Tenant-Id": "tenant-acme", "X-User-Id": "alice"},
        json={"issue_description": "Need a new feature to add export button for reports"},
    )
    assert response.status_code == 200
    assert response.json()["category"] == "Change Request"


def test_all_required_categories_exist_in_synthetic_data() -> None:
    response = client.post(
        "/ticket-analysis",
        headers={"X-Tenant-Id": "tenant-acme", "X-User-Id": "alice"},
        json={"ticket_id": "TKT-1002"},
    )
    assert response.status_code == 200

    categories = {
        "Product Bug",
        "Data Issue",
        "Configuration Issue",
        "Permission Issue",
        "Integration Issue",
        "Expected Behaviour",
        "Change Request",
        "Insufficient Information",
    }

    observed = set()
    test_matrix = [
        ("tenant-acme", "alice", "TKT-1001"),
        ("tenant-acme", "alice", "TKT-1002"),
        ("tenant-acme", "alice", "TKT-1003"),
        ("tenant-acme", "alice", "TKT-1004"),
        ("tenant-beta", "bob", "TKT-1005"),
        ("tenant-beta", "bob", "TKT-1006"),
        ("tenant-beta", "bob", "TKT-1007"),
        ("tenant-acme", "alice", "TKT-1008"),
    ]

    for tenant, user, ticket_id in test_matrix:
        result = client.post(
            "/ticket-analysis",
            headers={"X-Tenant-Id": tenant, "X-User-Id": user},
            json={"ticket_id": ticket_id},
        )
        assert result.status_code == 200
        observed.add(result.json()["category"])

    assert observed == categories
