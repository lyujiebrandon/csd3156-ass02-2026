"""
Cognito JWT verification for the EC2 FastAPI backend.
Replaces API Gateway's Cognito Authorizer.
"""
import os
import time
import requests
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwk, jwt
from jose.utils import base64url_decode

REGION = os.environ["AWS_REGION"]
USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
CLIENT_ID = os.environ["COGNITO_CLIENT_ID"]
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"

_jwks_cache: dict = {}
_jwks_fetched_at: float = 0
JWKS_TTL = 3600  # re-fetch JWKS once per hour

security = HTTPBearer()


def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    if not _jwks_cache or (time.time() - _jwks_fetched_at) > JWKS_TTL:
        resp = requests.get(JWKS_URL, timeout=5)
        resp.raise_for_status()
        _jwks_cache = {k["kid"]: k for k in resp.json()["keys"]}
        _jwks_fetched_at = time.time()
    return _jwks_cache


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    FastAPI dependency — verifies the Cognito JWT and returns the decoded claims.
    Usage:  async def route(claims: dict = Depends(verify_token)):
    """
    token = credentials.credentials
    try:
        headers = jwt.get_unverified_headers(token)
        kid = headers.get("kid")
        if not kid:
            raise HTTPException(status_code=401, detail="Token missing kid header")

        jwks = _get_jwks()
        if kid not in jwks:
            raise HTTPException(status_code=401, detail="Token kid not found in JWKS")

        public_key = jwk.construct(jwks[kid])
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=ISSUER,
        )
        return claims
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc
