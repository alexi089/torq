from tests.test_quotes import QUOTE, setup_request


def auth(user):
    return {"Authorization": f"Bearer {user['token']}"}


async def completed_job(client, make_user, make_shop_user):
    driver, (shop,), req = await setup_request(client, make_user, make_shop_user)
    q = (
        await client.post(f"/v1/requests/{req['id']}/quotes", json=QUOTE, headers=auth(shop))
    ).json()
    await client.post(f"/v1/quotes/{q['id']}/accept", headers=auth(driver))
    await client.post(f"/v1/requests/{req['id']}/complete", headers=auth(shop))
    return driver, shop, req


async def test_review_completed_request_updates_shop_rating(client, make_user, make_shop_user, db):
    driver, shop, req = await completed_job(client, make_user, make_shop_user)
    resp = await client.post(
        f"/v1/requests/{req['id']}/review",
        json={"stars": 4, "tags": ["fast", "friendly"], "comment": "solid"},
        headers=auth(driver),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["shop_id"] == shop["shop_id"] and body["stars"] == 4
    rating = await db.fetchrow(
        "select rating_avg, rating_count from public.shops where id = $1", shop["shop_id"]
    )
    assert float(rating["rating_avg"]) == 4.0 and rating["rating_count"] == 1


async def test_second_review_is_409(client, make_user, make_shop_user):
    driver, shop, req = await completed_job(client, make_user, make_shop_user)
    first = {"stars": 4, "tags": [], "comment": None}
    await client.post(f"/v1/requests/{req['id']}/review", json=first, headers=auth(driver))
    resp = await client.post(f"/v1/requests/{req['id']}/review", json=first, headers=auth(driver))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_review_before_completed_is_409(client, make_user, make_shop_user):
    driver, (shop,), req = await setup_request(client, make_user, make_shop_user)
    resp = await client.post(
        f"/v1/requests/{req['id']}/review", json={"stars": 5, "tags": []}, headers=auth(driver)
    )
    assert resp.status_code == 409


async def test_tags_limits(client, make_user, make_shop_user):
    driver, shop, req = await completed_job(client, make_user, make_shop_user)
    too_many = {"stars": 5, "tags": [f"t{i}" for i in range(11)]}
    assert (
        await client.post(f"/v1/requests/{req['id']}/review", json=too_many, headers=auth(driver))
    ).status_code == 422
    too_long = {"stars": 5, "tags": ["x" * 41]}
    assert (
        await client.post(f"/v1/requests/{req['id']}/review", json=too_long, headers=auth(driver))
    ).status_code == 422
