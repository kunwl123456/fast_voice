def test_login_requires_email(client):
    resp = client.post("/api/auth/login", json={})
    assert resp.status_code == 400


def test_login_success(client):
    resp = client.post("/api/auth/login", json={"email": "a@b.com"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["token"] == "demo-token"

