def test_list_voices(client):
    resp = client.get("/api/discovery/voices")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "voices" in data and len(data["voices"]) >= 1


def test_voice_detail(client):
    # 使用示例 ID
    resp = client.get("/api/discovery/voices/voice-1")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == "voice-1"


def test_bookmark(client):
    resp = client.post("/api/discovery/bookmark", json={"voice_model_id": "voice-1"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True

