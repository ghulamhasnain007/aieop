"""
FR-001 (auth) note: this is a DEV-MODE STUB, not a security boundary.

For the FYP's initial scope, callers pass an `X-User-Role` header to
simulate different roles while the RBAC/agent-permission layer is being
built and tested. Replace `get_current_role` with real JWT verification
(see app.config.settings.jwt_secret) before anything resembling a
production deployment - this stub trusts a client-supplied header.
"""
from fastapi import Header

from app.models.entities import Role


def get_current_role(x_user_role: str = Header(default="developer")) -> Role:
    try:
        return Role(x_user_role)
    except ValueError:
        return Role.viewer
