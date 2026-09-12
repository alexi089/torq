import asyncio

DRIVER_AT = {"lat": 45.5017, "lng": -73.5673}


def auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


QUOTE = {"price_min_cents": 8000, "price_max_cents": 12000, "eta_minutes": 45, "message": "Can do."}


async def setup_request(client, make_user, make_shop_user, n_shops=1):
    driver = await make_user()
    vid = (
        await client.post(
            "/v1/vehicles",
            json={"year": 2014, "make": "Honda", "model": "Civic"},
            headers=auth(driver),
        )
    ).json()["id"]
    shops = [await make_shop_user(DRIVER_AT["lat"], DRIVER_AT["lng"]) for _ in range(n_shops)]
    req = (
        await client.post(
            "/v1/requests",
            json={
                "vehicle_id": vid,
                "mode": "roadside",
                "issue": "battery",
                "location": DRIVER_AT,
                "search_radius_mi": 10,
                "photos": [
                    {"slot": "engine_bay", "storage_path": f"{driver['id']}/e.jpg"},
                    {"slot": "dashboard", "storage_path": f"{driver['id']}/d.jpg"},
                    {"slot": "wide", "storage_path": f"{driver['id']}/w.jpg"},
                ],
            },
            headers=auth(driver),
        )
    ).json()
    return driver, shops, req


async def test_shop_quotes_open_request(client, make_user, make_shop_user):
    driver, (shop,), req = await setup_request(client, make_user, make_shop_user)
    resp = await client.post(f"/v1/requests/{req['id']}/quotes", json=QUOTE, headers=auth(shop))
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending" and body["shop_id"] == shop["shop_id"]


async def test_second_quote_same_shop_is_409_conflict(client, make_user, make_shop_user):
    driver, (shop,), req = await setup_request(client, make_user, make_shop_user)
    await client.post(f"/v1/requests/{req['id']}/quotes", json=QUOTE, headers=auth(shop))
    resp = await client.post(f"/v1/requests/{req['id']}/quotes", json=QUOTE, headers=auth(shop))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_unnotified_shop_gets_404(client, make_user, make_shop_user):
    driver, _, req = await setup_request(client, make_user, make_shop_user)
    outsider = await make_shop_user(DRIVER_AT["lat"] + 1.0, DRIVER_AT["lng"], alert_radius_mi=2)
    resp = await client.post(f"/v1/requests/{req['id']}/quotes", json=QUOTE, headers=auth(outsider))
    assert resp.status_code == 404


async def test_quote_on_cancelled_request_is_409(client, make_user, make_shop_user):
    driver, (shop,), req = await setup_request(client, make_user, make_shop_user)
    await client.post(f"/v1/requests/{req['id']}/cancel", headers=auth(driver))
    resp = await client.post(f"/v1/requests/{req['id']}/quotes", json=QUOTE, headers=auth(shop))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_state"


async def test_price_max_below_min_is_422(client, make_user, make_shop_user):
    driver, (shop,), req = await setup_request(client, make_user, make_shop_user)
    bad = dict(QUOTE, price_max_cents=1)
    resp = await client.post(f"/v1/requests/{req['id']}/quotes", json=bad, headers=auth(shop))
    assert resp.status_code == 422


async def test_accept_flow(client, make_user, make_shop_user, db):
    driver, shops, req = await setup_request(client, make_user, make_shop_user, n_shops=2)
    q1 = (
        await client.post(f"/v1/requests/{req['id']}/quotes", json=QUOTE, headers=auth(shops[0]))
    ).json()
    q2 = (
        await client.post(f"/v1/requests/{req['id']}/quotes", json=QUOTE, headers=auth(shops[1]))
    ).json()
    resp = await client.post(f"/v1/quotes/{q1['id']}/accept", headers=auth(driver))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["accepted_quote_id"] == q1["id"]
    assert body["accepted_quote"]["status"] == "accepted"
    q2_status = await db.fetchval("select status from public.quotes where id = $1", q2["id"])
    assert q2_status == "rejected"


async def test_accept_by_non_owner_is_404(client, make_user, make_shop_user):
    driver, (shop,), req = await setup_request(client, make_user, make_shop_user)
    q = (
        await client.post(f"/v1/requests/{req['id']}/quotes", json=QUOTE, headers=auth(shop))
    ).json()
    stranger = await make_user()
    resp = await client.post(f"/v1/quotes/{q['id']}/accept", headers=auth(stranger))
    assert resp.status_code == 404


async def test_concurrent_accepts_one_winner(client, make_user, make_shop_user, db):
    driver, shops, req = await setup_request(client, make_user, make_shop_user, n_shops=2)
    q1 = (
        await client.post(f"/v1/requests/{req['id']}/quotes", json=QUOTE, headers=auth(shops[0]))
    ).json()
    q2 = (
        await client.post(f"/v1/requests/{req['id']}/quotes", json=QUOTE, headers=auth(shops[1]))
    ).json()
    r1, r2 = await asyncio.gather(
        client.post(f"/v1/quotes/{q1['id']}/accept", headers=auth(driver)),
        client.post(f"/v1/quotes/{q2['id']}/accept", headers=auth(driver)),
        return_exceptions=False,
    )
    codes = sorted([r1.status_code, r2.status_code])
    assert codes == [200, 409]
    accepted = await db.fetchval(
        "select count(*) from public.quotes where request_id = $1 and status = 'accepted'",
        req["id"],
    )
    assert accepted == 1
