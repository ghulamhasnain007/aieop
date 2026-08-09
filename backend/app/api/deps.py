"""
Request-time auth resolution (FR-001, FR-021).

get_current_role() is what every RBAC-gated endpoint depends on. It:

  1. Prefers a real JWT (issued by POST /api/auth/login) when the caller
     sends one - this is the only path in a non-development deployment.
  2. Falls back to the X-User-Role dev header ONLY when
     settings.environment == "development" AND no bearer token was sent.
     This keeps the dashboard/demo/test flow simple (no login step
     required to click around locally) while a real deployment
     (ENVIRONMENT=production) always requires a valid token - there is
     no header bypass once ENVIRONMENT is not "development".

get_current_user() is for endpoints that need the actual user record
(e.g. /api/auth/me) and always requires a valid token, in every
environment - it never falls back to the dev header, since "who is this"
isn't something a role header can answer.
"""
from fastapi import Depends, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.entities import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(
    token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = _decode_token(token)
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_role(
    token: str | None = Depends(oauth2_scheme),
    x_user_role: str | None = Header(default=None),
) -> Role:
    if token:
        payload = _decode_token(token)
        try:
            return Role(payload.get("role", "viewer"))
        except ValueError:
            return Role.viewer

    if settings.environment == "development":
        if x_user_role:
            try:
                return Role(x_user_role)
            except ValueError:
                return Role.viewer
        return Role.developer

    raise HTTPException(status_code=401, detail="Authentication required")

