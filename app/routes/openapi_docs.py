from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/openapi", tags=["openapi-docs"])


@router.get("/docs/guide")
def openapi_guide():
    """
    V1：OpenAPI 接入说明（签名/幂等/异步任务）。
    """
    return {
        "auth": {
            "type": "APIKey + Secret HMAC-SHA256 signature",
            "headers": [
                "X-API-Key",
                "X-Timestamp (unix seconds)",
                "X-Nonce",
                "X-Signature (hex)",
                "Idempotency-Key (required for POST /openapi/tts/jobs and POST /openapi/clone/jobs)",
            ],
            "canonical_string": "METHOD\\nPATH\\nQUERY\\nBODY_SHA256\\nTIMESTAMP\\nNONCE",
            "note": "QUERY 使用原始 querystring；BODY_SHA256 为请求体原始 bytes 的 sha256 hex。",
        },
        "async": {
            "tts_create": "POST /openapi/tts/jobs -> {id,status}",
            "tts_get": "GET /openapi/tts/jobs/{id} -> {status,output_audio_url}",
            "clone_create": "POST /openapi/clone/jobs (multipart files) -> {id,status}",
            "clone_get": "GET /openapi/clone/jobs/{id} -> {status,result_voice_id}",
        },
        "errors": {
            "401": ["invalid_api_key", "invalid_signature", "invalid_timestamp", "replayed_nonce"],
            "402": ["insufficient_credits"],
            "404": ["job_not_found", "voice_not_found"],
        },
    }


