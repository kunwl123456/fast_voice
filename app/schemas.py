from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    display_name: str = Field(default="", max_length=100)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    is_admin: bool


class RenameIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=72)


class ApiKeyOut(BaseModel):
    api_key: str
    api_secret: str


class CreditAccountOut(BaseModel):
    project_id: int
    balance: int


class CreditTxOut(BaseModel):
    id: int
    tx_type: str
    amount: int
    ref_type: str
    ref_id: str
    note: str
    created_at: str


class AdminAdjustCreditsIn(BaseModel):
    project_id: int
    amount: int  # positive or negative
    note: str = ""


class VoiceOut(BaseModel):
    id: int
    name: str
    description: str
    is_public: bool
    preview_audio_url: str = ""


class VoiceUpdateIn(BaseModel):
    description: str | None = None
    is_public: bool | None = None


class TTSCreatIn(BaseModel):
    voice_id: int
    text: str


class JobOut(BaseModel):
    id: int
    status: str
    error: str = ""


class TTSJobOut(JobOut):
    voice_id: int
    text_utf8_bytes: int
    cost_credits: int
    output_audio_url: str = ""


class CloneCreateOut(JobOut):
    voice_name: str


class CloneJobOut(JobOut):
    voice_name: str
    result_voice_id: int | None = None


