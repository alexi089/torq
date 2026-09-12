async def test_patch_me_updates_and_returns_profile(client, make_user):
    user = await make_user(full_name="Before")
    resp = await client.patch(
        "/v1/me",
        json={"full_name": "After", "phone": "+15145551234"},
        headers={"Authorization": f"Bearer {user['token']}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "After"
    assert body["phone"] == "+15145551234"
    assert body["id"] == user["id"]


async def test_patch_me_empty_body_is_422(client, make_user):
    user = await make_user()
    resp = await client.patch(
        "/v1/me", json={}, headers={"Authorization": f"Bearer {user['token']}"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_delete_me_removes_user_and_anonymizes(client, make_user, make_shop_user, db):
    from tests.test_quotes import setup_request

    def auth(u):
        return {"Authorization": f"Bearer {u['token']}"}

    driver, (shop,), req = await setup_request(client, make_user, make_shop_user)
    await client.post(f"/v1/requests/{req['id']}/cancel", headers=auth(driver))  # clear the guard
    resp = await client.request("DELETE", "/v1/me", headers=auth(driver))
    assert resp.status_code == 204
    assert await db.fetchval("select count(*) from auth.users where id = $1", driver["id"]) == 0
    surviving = await db.fetchrow("select driver_id from public.requests where id = $1", req["id"])
    assert surviving is not None and surviving["driver_id"] is None  # anonymized, kept


async def test_delete_me_with_open_request_is_409(client, make_user):
    def auth(u):
        return {"Authorization": f"Bearer {u['token']}"}

    driver = await make_user()
    vid = (
        await client.post(
            "/v1/vehicles",
            json={"year": 2014, "make": "Honda", "model": "Civic"},
            headers=auth(driver),
        )
    ).json()["id"]
    await client.post(
        "/v1/requests",
        json={
            "vehicle_id": vid,
            "mode": "planned",
            "issue": "brakes",
            "location": {"lat": 45.5, "lng": -73.6},
            "search_radius_mi": 10,
            "photos": [
                {"slot": "engine_bay", "storage_path": f"{driver['id']}/e.jpg"},
                {"slot": "dashboard", "storage_path": f"{driver['id']}/d.jpg"},
                {"slot": "wide", "storage_path": f"{driver['id']}/w.jpg"},
            ],
        },
        headers=auth(driver),
    )
    resp = await client.request("DELETE", "/v1/me", headers=auth(driver))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_state"


async def test_delete_me_shop_holding_accepted_quote_is_409(client, make_user, make_shop_user):
    from tests.test_quotes import QUOTE, setup_request

    def auth(u):
        return {"Authorization": f"Bearer {u['token']}"}

    driver, (shop,), req = await setup_request(client, make_user, make_shop_user)
    q = (
        await client.post(f"/v1/requests/{req['id']}/quotes", json=QUOTE, headers=auth(shop))
    ).json()
    await client.post(f"/v1/quotes/{q['id']}/accept", headers=auth(driver))
    resp = await client.request("DELETE", "/v1/me", headers=auth(shop))
    assert resp.status_code == 409


async def test_delete_me_upstream_transport_failure_is_502(client, make_user, monkeypatch):
    import httpx

    async def boom(self, *args, **kwargs):
        raise httpx.ConnectError("boom")

    # Mock only at the external boundary: the admin API call itself.
    monkeypatch.setattr(httpx.AsyncClient, "delete", boom)

    driver = await make_user()
    resp = await client.request(
        "DELETE", "/v1/me", headers={"Authorization": f"Bearer {driver['token']}"}
    )
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "upstream_error"
