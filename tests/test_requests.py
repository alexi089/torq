"""Fan-out geometry: driver at downtown Montreal. Distances via offsets:
~0.0145 degrees latitude ~= 1 mile. Shops are placed by miles-north offsets."""

DRIVER_AT = {"lat": 45.5017, "lng": -73.5673}
MI = 0.0145  # degrees latitude per mile (approx; fine at these tolerances)


def auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


async def make_request(client, user, vehicle_id, *, radius=10, mode="roadside", photos=None):
    if photos is None:
        photos = [
            {"slot": "engine_bay", "storage_path": f"{user['id']}/engine.jpg"},
            {"slot": "dashboard", "storage_path": f"{user['id']}/dash.jpg"},
            {"slot": "wide", "storage_path": f"{user['id']}/wide.jpg"},
        ]
    return await client.post(
        "/v1/requests",
        json={
            "vehicle_id": vehicle_id,
            "mode": mode,
            "issue": "wont_start",
            "location": DRIVER_AT,
            "search_radius_mi": radius,
            "photos": photos,
        },
        headers=auth(user),
    )


async def make_vehicle(client, user):
    resp = await client.post(
        "/v1/vehicles",
        json={"year": 2014, "make": "Honda", "model": "Civic"},
        headers=auth(user),
    )
    return resp.json()["id"]


async def test_fanout_dual_radius_and_online(client, make_user, make_shop_user, db):
    driver = await make_user()
    vehicle_id = await make_vehicle(client, driver)
    # in driver radius (10mi) AND its own alert radius covers the driver -> notified
    hit = await make_shop_user(DRIVER_AT["lat"] + 5 * MI, DRIVER_AT["lng"], alert_radius_mi=10)
    # inside driver radius but its own alert radius too small -> NOT notified
    deaf = await make_shop_user(DRIVER_AT["lat"] + 5 * MI, DRIVER_AT["lng"], alert_radius_mi=2)
    # covers the driver with its alert radius but outside driver search radius -> NOT notified
    far = await make_shop_user(DRIVER_AT["lat"] + 20 * MI, DRIVER_AT["lng"], alert_radius_mi=30)
    # perfect match but offline -> NOT notified
    offline = await make_shop_user(
        DRIVER_AT["lat"] + 5 * MI, DRIVER_AT["lng"], alert_radius_mi=10, online=False
    )

    resp = await make_request(client, driver, vehicle_id, radius=10)
    assert resp.status_code == 201
    body = resp.json()
    assert body["notified_count"] == 1
    notified = await db.fetch(
        "select shop_id from public.request_notifications where request_id = $1", body["id"]
    )
    assert [r["shop_id"] for r in notified] == [hit["shop_id"]]
    assert deaf["shop_id"] != hit["shop_id"] and far and offline  # explicit non-use guard


async def test_roadside_gets_ttl_planned_does_not(client, make_user):
    driver = await make_user()
    vehicle_id = await make_vehicle(client, driver)
    roadside = (await make_request(client, driver, vehicle_id, mode="roadside")).json()
    assert roadside["expires_at"] is not None
    planned = (await make_request(client, driver, vehicle_id, mode="planned")).json()
    assert planned["expires_at"] is None


async def test_photos_must_cover_all_three_slots(client, make_user):
    driver = await make_user()
    vehicle_id = await make_vehicle(client, driver)
    two = [
        {"slot": "engine_bay", "storage_path": f"{driver['id']}/e.jpg"},
        {"slot": "dashboard", "storage_path": f"{driver['id']}/d.jpg"},
    ]
    resp = await make_request(client, driver, vehicle_id, photos=two)
    assert resp.status_code == 422


async def test_photo_path_must_be_own_prefix_no_traversal(client, make_user):
    driver = await make_user()
    vehicle_id = await make_vehicle(client, driver)
    for bad in ("someone-else/x.jpg", f"{driver['id']}/../x.jpg", f"{driver['id']}/"):
        photos = [
            {"slot": "engine_bay", "storage_path": bad},
            {"slot": "dashboard", "storage_path": f"{driver['id']}/d.jpg"},
            {"slot": "wide", "storage_path": f"{driver['id']}/w.jpg"},
        ]
        resp = await make_request(client, driver, vehicle_id, photos=photos)
        assert resp.status_code == 422, bad


async def test_archived_vehicle_is_409(client, make_user):
    driver = await make_user()
    vehicle_id = await make_vehicle(client, driver)
    await client.post(f"/v1/vehicles/{vehicle_id}/archive", headers=auth(driver))
    resp = await make_request(client, driver, vehicle_id)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_state"


async def test_someone_elses_vehicle_is_404(client, make_user):
    driver, other = await make_user(), await make_user()
    vehicle_id = await make_vehicle(client, other)
    resp = await make_request(client, driver, vehicle_id)
    assert resp.status_code == 404


async def test_cancel_from_open(client, make_user):
    driver = await make_user()
    vehicle_id = await make_vehicle(client, driver)
    req = (await make_request(client, driver, vehicle_id)).json()
    resp = await client.post(f"/v1/requests/{req['id']}/cancel", headers=auth(driver))
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_cancel_twice_is_409(client, make_user):
    driver = await make_user()
    vehicle_id = await make_vehicle(client, driver)
    req = (await make_request(client, driver, vehicle_id)).json()
    await client.post(f"/v1/requests/{req['id']}/cancel", headers=auth(driver))
    resp = await client.post(f"/v1/requests/{req['id']}/cancel", headers=auth(driver))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_state"


async def test_seen_marks_once(client, make_user, make_shop_user, db):
    driver = await make_user()
    vehicle_id = await make_vehicle(client, driver)
    shop = await make_shop_user(DRIVER_AT["lat"], DRIVER_AT["lng"])
    req = (await make_request(client, driver, vehicle_id)).json()
    first = await client.post(f"/v1/requests/{req['id']}/seen", headers=auth(shop))
    assert first.status_code == 204
    seen1 = await db.fetchval(
        "select seen_at from public.request_notifications where request_id=$1 and shop_id=$2",
        req["id"],
        shop["shop_id"],
    )
    second = await client.post(f"/v1/requests/{req['id']}/seen", headers=auth(shop))
    assert second.status_code == 204
    seen2 = await db.fetchval(
        "select seen_at from public.request_notifications where request_id=$1 and shop_id=$2",
        req["id"],
        shop["shop_id"],
    )
    assert seen1 == seen2  # idempotent


async def test_seen_without_notification_is_404(client, make_user, make_shop_user):
    driver = await make_user()
    vehicle_id = await make_vehicle(client, driver)
    # shop far away and small radius -> not notified
    shop = await make_shop_user(DRIVER_AT["lat"] + 20 * MI, DRIVER_AT["lng"], alert_radius_mi=2)
    req = (await make_request(client, driver, vehicle_id)).json()
    resp = await client.post(f"/v1/requests/{req['id']}/seen", headers=auth(shop))
    assert resp.status_code == 404
