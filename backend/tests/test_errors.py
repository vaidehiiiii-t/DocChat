from app.errors import AppError


def test_unknown_route_returns_404_json(client):
    res = client.get("/api/definitely-not-a-real-endpoint-12345")
    assert res.status_code == 404
    data = res.get_json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "message" in data["error"]
    assert isinstance(data["error"]["details"], dict)


def test_method_not_allowed_returns_json(client):
    # /api/health only allows GET
    res = client.post("/api/health")
    assert res.status_code == 405
    data = res.get_json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_custom_app_error(app, client):
    @app.route("/api/test-custom-error")
    def trigger_error():
        raise AppError(
            "Something custom broke", code="CUSTOM_CODE", status_code=418, details={"field": "test"}
        )

    res = client.get("/api/test-custom-error")
    assert res.status_code == 418
    data = res.get_json()
    assert data["error"]["code"] == "CUSTOM_CODE"
    assert data["error"]["message"] == "Something custom broke"
    assert data["error"]["details"] == {"field": "test"}
