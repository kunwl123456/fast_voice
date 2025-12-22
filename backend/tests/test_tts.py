def test_tts_placeholder(client):
    resp = client.post("/api/tts/generate", json={"text": "hello"})
    assert resp.status_code == 501
    data = resp.get_json()
    assert "待实现" in data["message"]

