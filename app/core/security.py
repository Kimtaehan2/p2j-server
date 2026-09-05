"""비밀번호 해시와 JWT (API 명세 v1 §1.6·§14.9).

- 비밀번호: bcrypt (cost 12). 72바이트 초과 입력은 스키마에서 막는다.
- access 토큰: JWT HS256, 30분. payload 는 sub(user_id)·type·jti·iat·exp 만.
- refresh 토큰: JWT 가 아니라 **무작위 불투명 문자열**. DB `refresh_tokens.token_hash` 에
  SHA-256 해시만 저장한다 (ERD §3.2). 원문이 유출돼도 DB 만으로는 세션을 탈취할 수 없다.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.errors import TokenExpired, Unauthorized
from app.core.time import now_utc

BCRYPT_ROUNDS = 12
ACCESS_TOKEN_TYPE = "access"


# ---- 비밀번호 -------------------------------------------------------------------


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # 손상된 해시. 실패로 처리하고 원인은 로그로 확인한다.
        return False


# ---- access 토큰 ----------------------------------------------------------------


def create_access_token(user_id: int, *, now: datetime | None = None) -> tuple[str, int]:
    """(토큰, expires_in 초). expires_in 은 로그인 응답의 `expires_in` 에 그대로 넣는다."""
    settings = get_settings()
    issued = now or now_utc()
    ttl = settings.jwt_access_ttl_seconds
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "jti": uuid.uuid4().hex,
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=ttl)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, ttl


def decode_access_token(token: str) -> int:
    """user_id 를 돌려준다. 만료는 TOKEN_EXPIRED, 그 외 문제는 UNAUTHORIZED (§1.3)."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpired() from exc
    except jwt.InvalidTokenError as exc:
        raise Unauthorized() from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise Unauthorized()
    try:
        return int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise Unauthorized() from exc


# ---- refresh 토큰 ----------------------------------------------------------------


def generate_refresh_token() -> tuple[str, str, datetime]:
    """(원문, 해시, 만료 시각). 원문은 클라이언트에게만 주고 서버는 해시만 저장한다."""
    raw = secrets.token_urlsafe(48)
    expires_at = now_utc() + timedelta(days=get_settings().jwt_refresh_ttl_days)
    return raw, hash_refresh_token(raw), expires_at


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
