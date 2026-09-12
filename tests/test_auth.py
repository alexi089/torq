import os
import time
import uuid

import jwt

from tests.tokens import _load_key, mint_token


async def _me(client, token: str):
    return await client.patch(
        "/v1/me", json={"full_name": "x"}, headers={"Authorization": f"Bearer {token}"}
    )


def _mint_with_iat(sub: str, iat_delta_s: int, exp_delta_s: int = 3600) -> str:
    # mint_token doesn't expose iat, so build claims inline (real key/kid,
    # correct iss/aud/exp) to test clock-skew tolerance specifically.
    kid, key = _load_key()
    now = int(time.time())
    claims = {
        "sub": sub,
        "aud": "authenticated",
        "iss": os.environ["SUPABASE_URL"] + "/auth/v1",
        "iat": now + iat_delta_s,
        "exp": now + exp_delta_s,
        "role": "authenticated",
        "session_id": str(uuid.uuid4()),
    }
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": kid})


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


async def test_small_future_iat_is_accepted(client, make_user):
    # tolerate container/client clock skew: a token minted ~2s ahead of this
    # host's clock (e.g. the GoTrue container's clock) must still be honored.
    user = await make_user()
    token = _mint_with_iat(user["id"], iat_delta_s=2)
    resp = await _me(client, token)
    assert resp.status_code == 200


async def test_large_future_iat_is_401(client, make_user):
    # skew tolerance is bounded: an iat far in the future is still rejected.
    user = await make_user()
    token = _mint_with_iat(user["id"], iat_delta_s=60)
    resp = await _me(client, token)
    assert resp.status_code == 401


async def test_real_supabase_token_works(client, make_user):
    user = await make_user()
    resp = await _me(client, user["token"])
    assert resp.status_code == 200


async def test_shop_route_without_shop_is_403(client, make_user):
    user = await make_user()
    resp = await client.patch(
        "/v1/shops/me",
        json={"is_online": True},
        headers={"Authorization": f"Bearer {user['token']}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
