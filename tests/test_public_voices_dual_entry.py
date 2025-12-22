def test_public_voices_available_on_console_and_openapi(client):
    # Both endpoints should be reachable without extra auth (public list)
    r1 = client.get("/console/voices/public")
    assert r1.status_code == 200, r1.text
    assert isinstance(r1.json(), list)

    r2 = client.get("/openapi/voices/public")
    assert r2.status_code == 200, r2.text
    assert isinstance(r2.json(), list)


