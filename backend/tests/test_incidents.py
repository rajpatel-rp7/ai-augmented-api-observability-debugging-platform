from fastapi.testclient import TestClient


def _create_service(client: TestClient, name: str) -> dict:
    response = client.post(
        "/api/v1/services",
        json={"name": name, "display_name": name.replace("-", " ").title()},
    )
    assert response.status_code == 201
    return response.json()


def test_create_incident_with_affected_services(client: TestClient) -> None:
    payment = _create_service(client, "payment-service")
    order = _create_service(client, "order-service")

    response = client.post(
        "/api/v1/incidents",
        json={
            "title": "Payment Processing Failure",
            "severity": "high",
            "summary": "Elevated latency and database timeouts",
            "affected_service_ids": [payment["id"], order["id"]],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Payment Processing Failure"
    assert body["status"] == "open"
    assert {service["name"] for service in body["affected_services"]} == {
        "payment-service",
        "order-service",
    }


def test_list_incidents_can_filter_by_status(client: TestClient) -> None:
    _create_service(client, "payment-service")
    client.post(
        "/api/v1/incidents",
        json={"title": "Open incident", "severity": "medium"},
    )
    created = client.post(
        "/api/v1/incidents",
        json={"title": "Resolved incident", "severity": "low", "status": "resolved"},
    ).json()

    open_only = client.get("/api/v1/incidents", params={"status": "open"})
    assert open_only.status_code == 200
    assert len(open_only.json()) == 1
    assert open_only.json()[0]["title"] == "Open incident"

    resolved = client.patch(
        f"/api/v1/incidents/{created['id']}",
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolved_at"] is not None


def test_incident_rejects_unknown_service_ids(client: TestClient) -> None:
    response = client.post(
        "/api/v1/incidents",
        json={
            "title": "Bad linkage",
            "affected_service_ids": ["00000000-0000-0000-0000-000000000001"],
        },
    )
    assert response.status_code == 400
