def auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


SHOP = {
    "name": "Marco's Garage",
    "phone": "+15145550000",
    "address": "1 Rue Test, Montreal",
    "location": {"lat": 45.5017, "lng": -73.5673},
    "alert_radius_mi": 10,
}


async def test_create_shop(client, make_user):
    user = await make_user()
    resp = await client.post("/v1/shops", json=SHOP, headers=auth(user))
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_online"] is False
    assert body["rating_avg"] is None and body["rating_count"] == 0
    assert abs(body["location"]["lat"] - 45.5017) < 1e-6
    assert abs(body["location"]["lng"] - -73.5673) < 1e-6


async def test_second_shop_is_409(client, make_user):
    user = await make_user()
    assert (await client.post("/v1/shops", json=SHOP, headers=auth(user))).status_code == 201
    resp = await client.post("/v1/shops", json=SHOP, headers=auth(user))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_alert_radius_out_of_bounds_is_422(client, make_user):
    user = await make_user()
    resp = await client.post("/v1/shops", json=dict(SHOP, alert_radius_mi=31), headers=auth(user))
    assert resp.status_code == 422


async def test_patch_shop_me_toggles_online(client, make_user):
    user = await make_user()
    await client.post("/v1/shops", json=SHOP, headers=auth(user))
    resp = await client.patch("/v1/shops/me", json={"is_online": True}, headers=auth(user))
    assert resp.status_code == 200
    assert resp.json()["is_online"] is True


async def test_patch_shop_me_without_shop_is_403(client, make_user):
    user = await make_user()
    resp = await client.patch("/v1/shops/me", json={"is_online": True}, headers=auth(user))
    assert resp.status_code == 403


async def test_make_shop_user_fixture_creates_online_shop(make_shop_user, db):
    shop_user = await make_shop_user(45.5, -73.5)
    assert shop_user["shop_id"] > 0
    row = await db.fetchrow(
        "select is_online from public.shops where id = $1", shop_user["shop_id"]
    )
    assert row is not None
    assert row["is_online"] is True
