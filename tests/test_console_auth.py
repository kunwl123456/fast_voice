def test_register_login_me(client):
    r = client.post(
        "/console/auth/register",
        json={"email": "u1@example.com", "password": "pass1234", "display_name": "u1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "u1@example.com"

    r = client.post("/console/auth/login", json={"email": "u1@example.com", "password": "pass1234"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    r = client.get("/console/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert r.json()["display_name"] == "u1"


