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
