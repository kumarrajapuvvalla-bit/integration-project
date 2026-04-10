"""auth.py — JWT token issuance and verification.

In production, replace SECRET_KEY with a secret from AWS Secrets Manager / Vault.
Tokens are HS256-signed JWTs with a configurable TTL.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

# ── Config ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_TTL_MINUTES", "30"))

# Simulated user store — in production this would be a database lookup
FAKE_USERS: dict[str, str] = {
    "ops-service": "secret123",
    "flight-gateway": "gatewaypass",
}

bearer_scheme = HTTPBearer(auto_error=True)


# ── Models ────────────────────────────────────────────────────────────────────
class TokenRequest(BaseModel):
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ── Token creation ────────────────────────────────────────────────────────────
def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ── Token verification dependency ───────────────────────────────────────────────
def get_current_client(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """FastAPI dependency — validates Bearer JWT and returns the client_id."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_id: str = payload.get("sub", "")
        if not client_id:
            raise JWTError("missing sub")
        return client_id
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
