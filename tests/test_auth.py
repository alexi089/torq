import uuid

import pytest

from tests.tokens import mint_token


async def _me(client, token: str):
    return await client.patch(
        "/v1/me", json={"full_name": "x"}, headers={"Authorization": f"Bearer {token}"}
    )


async def test_missing_token_is_401(client):
    resp = await client.patch("/v1/me", json={"full_name": "x"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_garbage_token_is_401(client):
    resp = await _me(client, "not-a-jwt")
    assert resp.status_code == 401


async def test_expired_token_is_401(client, make_user):
    user = await make_user()
    resp = await _me(client, mint_token(user["id"], exp_delta_s=-60))
    assert resp.status_code == 401


async def test_bad_issuer_is_401(client, make_user):
    user = await make_user()
    resp = await _me(client, mint_token(user["id"], iss="https://evil.example/auth/v1"))
    assert resp.status_code == 401


async def test_bad_audience_is_401(client, make_user):
    user = await make_user()
    resp = await _me(client, mint_token(user["id"], aud="anon"))
    assert resp.status_code == 401


async def test_unknown_kid_is_401(client, make_user):
    user = await make_user()
    resp = await _me(client, mint_token(user["id"], kid=str(uuid.uuid4())))
    assert resp.status_code == 401


async def test_non_uuid_sub_is_401(client):
    resp = await _me(client, mint_token("not-a-uuid"))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_real_supabase_token_works(client, make_user):
    user = await make_user()
    resp = await _me(client, user["token"])
    assert resp.status_code == 200


@pytest.mark.xfail(reason="route lands in task 9", strict=True)
async def test_shop_route_without_shop_is_403(client, make_user):
    user = await make_user()
    resp = await client.patch(
        "/v1/shops/me",
        json={"is_online": True},
        headers={"Authorization": f"Bearer {user['token']}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
