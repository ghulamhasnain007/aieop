"""
Auth primitives (FR-001). Replaces the Phase-0 dev-mode header stub with
a real password + JWT flow. See app.api.deps for how this plugs into
request-time role resolution.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

from app.config.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
