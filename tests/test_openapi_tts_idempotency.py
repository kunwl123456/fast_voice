import hashlib
import hmac
import json
import time


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sign(secret: str, method: str, path: str, query: str, body_sha: str, ts: str, nonce: str) -> str:
    canonical = "\n".join([method.upper(), path, query or "", body_sha, ts, nonce])
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _login(client, email: str, password: str) -> str:
    r = client.post("/console/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_openapi_tts_idempotency_and_nonce(client):
    # create user
    r = client.post("/console/auth/register", json={"email": "u2@example.com", "password": "pass1234", "display_name": "u2"})
    assert r.status_code == 200, r.text

    user_token = _login(client, "u2@example.com", "pass1234")
    admin_token = _login(client, "admin@example.com", "admin12345")

    # get project credits (for project_id)
    r = client.get("/console/projects/default/credits", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 200, r.text
    project_id = r.json()["project_id"]

    # admin add credits
    r = client.post(
        "/console/admin/credits/adjust",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"project_id": project_id, "amount": 10000, "note": "test"},
    )
    assert r.status_code == 200, r.text

    # rotate api key to obtain secret
    r = client.post("/console/projects/default/api-keys/rotate", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 200, r.text
    api_key = r.json()["api_key"]
    api_secret = r.json()["api_secret"]

    # create a public voice via clone (sync fallback in test env)
    files = [("files", ("a.wav", b"dummy", "audio/wav"))]
    r = client.post(
        "/console/clone/jobs?voice_name=v1&is_public=true",
        headers={"Authorization": f"Bearer {user_token}"},
        files=files,
    )
    assert r.status_code == 200, r.text
    clone_job_id = r.json()["id"]
    r = client.get(f"/console/clone/jobs/{clone_job_id}", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 200, r.text
    voice_id = r.json()["result_voice_id"]
    assert voice_id is not None

    path = "/openapi/tts/jobs"
    body = {"voice_id": voice_id, "text": "hello"}
    raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ts = str(int(time.time()))
    nonce = "n1"
    sig = _sign(api_secret, "POST", path, "", _sha256_hex(raw), ts, nonce)

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Signature": sig,
        "Idempotency-Key": "idem-1",
    }

    r1 = client.post(path, content=raw, headers=headers)
    assert r1.status_code == 200, r1.text
    job_id_1 = r1.json()["id"]

    # idempotency: same key -> same job id (nonce must change)
    ts2 = str(int(time.time()))
    nonce2 = "n2"
    sig2 = _sign(api_secret, "POST", path, "", _sha256_hex(raw), ts2, nonce2)
    headers2 = dict(headers)
    headers2.update({"X-Timestamp": ts2, "X-Nonce": nonce2, "X-Signature": sig2})
    r2 = client.post(path, content=raw, headers=headers2)
    assert r2.status_code == 200, r2.text
    assert r2.json()["id"] == job_id_1

    # replay nonce should fail
    r3 = client.post(path, content=raw, headers=headers)  # reuse nonce n1
    assert r3.status_code == 401
    assert r3.json()["detail"] == "replayed_nonce"


