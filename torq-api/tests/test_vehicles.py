from datetime import datetime


def auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


VEHICLE = {"year": 2014, "make": "Honda", "model": "Civic", "mileage": 180000}


async def test_create_vehicle(client, make_user):
    user = await make_user()
    resp = await client.post("/v1/vehicles", json=VEHICLE, headers=auth(user))
    assert resp.status_code == 201
    body = resp.json()
    assert body["owner_id"] == user["id"]
    assert body["year"] == 2014
    assert body["archived_at"] is None


async def test_create_vehicle_future_year_is_422(client, make_user):
    user = await make_user()
    bad = dict(VEHICLE, year=datetime.now().year + 2)
    resp = await client.post("/v1/vehicles", json=bad, headers=auth(user))
    assert resp.status_code == 422


async def test_patch_vehicle(client, make_user):
    user = await make_user()
    created = (await client.post("/v1/vehicles", json=VEHICLE, headers=auth(user))).json()
    resp = await client.patch(
        f"/v1/vehicles/{created['id']}", json={"mileage": 181000}, headers=auth(user)
    )
    assert resp.status_code == 200
    assert resp.json()["mileage"] == 181000


async def test_patch_someone_elses_vehicle_is_404(client, make_user):
    owner, thief = await make_user(), await make_user()
    created = (await client.post("/v1/vehicles", json=VEHICLE, headers=auth(owner))).json()
    resp = await client.patch(
        f"/v1/vehicles/{created['id']}", json={"mileage": 1}, headers=auth(thief)
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_archive_is_idempotent(client, make_user):
    user = await make_user()
    created = (await client.post("/v1/vehicles", json=VEHICLE, headers=auth(user))).json()
    first = await client.post(f"/v1/vehicles/{created['id']}/archive", headers=auth(user))
    second = await client.post(f"/v1/vehicles/{created['id']}/archive", headers=auth(user))
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["archived_at"] == second.json()["archived_at"]


async def test_archived_vehicle_still_editable(client, make_user):
    user = await make_user()
    created = (await client.post("/v1/vehicles", json=VEHICLE, headers=auth(user))).json()
    await client.post(f"/v1/vehicles/{created['id']}/archive", headers=auth(user))
    resp = await client.patch(
        f"/v1/vehicles/{created['id']}", json={"engine": "1.8L"}, headers=auth(user)
    )
    assert resp.status_code == 200
