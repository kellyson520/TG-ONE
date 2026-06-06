from web_admin import fastapi_app


def test_default_cors_origins_are_not_wildcard(monkeypatch):
    monkeypatch.setattr(fastapi_app.settings, "WEB_CORS_ALLOWED_ORIGINS", [])
    monkeypatch.setattr(fastapi_app.settings, "WEB_PORT", 9000)
    monkeypatch.setattr(fastapi_app.settings, "WEB_HOST", "0.0.0.0")

    origins = fastapi_app._get_cors_allowed_origins()

    assert "*" not in origins
    assert "http://127.0.0.1:9000" in origins
    assert "http://localhost:9000" in origins


def test_configured_cors_origins_are_used(monkeypatch):
    monkeypatch.setattr(
        fastapi_app.settings,
        "WEB_CORS_ALLOWED_ORIGINS",
        ["https://admin.example.com", "*", "https://admin.example.com"],
    )

    origins = fastapi_app._get_cors_allowed_origins()

    assert origins == ["https://admin.example.com", "*"]
