from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_config_returns_product_info() -> None:
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["product"] == "Vulcan OmniPro 220"
    assert "mig" in data["processes"]
    assert "120v" in data["voltages"]


def test_cors_allows_local_dev_ports() -> None:
    response = client.options(
        "/api/products",
        headers={
            "Origin": "http://127.0.0.1:3003",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3003"
