from app.config import parse_cors_origins


async def test_healthz_ok(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_healthz_no_cors_header_when_origins_unset(client):
    resp = await client.get("/healthz", headers={"Origin": "https://example.com"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


def test_parse_cors_origins_empty_string_yields_no_origins():
    assert parse_cors_origins("") == []


def test_parse_cors_origins_two_origins():
    assert parse_cors_origins("https://a.com, https://b.com") == [
        "https://a.com",
        "https://b.com",
    ]
