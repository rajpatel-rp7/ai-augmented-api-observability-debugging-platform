from fastapi.testclient import TestClient


def test_create_and_list_services(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/services",
        json={
            "name": "payment-service",
            "display_name": "Payment Service",
            "environment": "staging",
            "owner_team": "payments",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "payment-service"
    assert created["environment"] == "staging"

    list_response = client.get("/api/v1/services")
    assert list_response.status_code == 200
    services = list_response.json()
    assert len(services) == 1
    assert services[0]["id"] == created["id"]


def test_duplicate_service_name_returns_conflict(client: TestClient) -> None:
    payload = {
        "name": "order-service",
        "display_name": "Order Service",
    }
    assert client.post("/api/v1/services", json=payload).status_code == 201
    conflict = client.post("/api/v1/services", json=payload)
    assert conflict.status_code == 409


def test_update_and_delete_service(client: TestClient) -> None:
    created = client.post(
        "/api/v1/services",
        json={"name": "notification-service", "display_name": "Notification Service"},
    ).json()

    updated = client.patch(
        f"/api/v1/services/{created['id']}",
        json={"display_name": "Notifications", "owner_team": "platform"},
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Notifications"
    assert updated.json()["owner_team"] == "platform"

    deleted = client.delete(f"/api/v1/services/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/services/{created['id']}").status_code == 404
