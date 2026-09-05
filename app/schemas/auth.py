"""/auth/* 요청 스키마 (API 명세 §3).

비밀번호 길이는 여기서 검사하지 않는다. 명세가 `400 WEAK_PASSWORD`(details 없음)를 요구하므로
서비스 계층에서 던진다. 여기서 min_length 를 걸면 VALIDATION_ERROR 로 나간다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr = Field(max_length=254)
    password: str
    nickname: str = Field(min_length=1, max_length=20)


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
