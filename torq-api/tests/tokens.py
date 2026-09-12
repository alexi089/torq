import json
import os
import time
import uuid
from typing import cast

import jwt
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from jwt.algorithms import ECAlgorithm


def _load_key() -> tuple[str, EllipticCurvePrivateKey]:
    with open(os.environ["SIGNING_KEYS_PATH"]) as f:
        data = json.load(f)
    k = data["keys"][0] if isinstance(data, dict) else data[0]
    # the JWK carries the private component ("d"), so from_jwk returns an
    # EllipticCurvePrivateKey at runtime; its static type is the broader
    # AllowedECKeys union (private | public), so narrow it for jwt.encode
    key = cast(EllipticCurvePrivateKey, ECAlgorithm(ECAlgorithm.SHA256).from_jwk(json.dumps(k)))
    return k["kid"], key


def mint_token(
    sub: str,
    *,
    iss: str | None = None,
    aud: str = "authenticated",
    exp_delta_s: int = 3600,
    kid: str | None = None,
) -> str:
    real_kid, key = _load_key()
    now = int(time.time())
    claims = {
        "sub": sub,
        "aud": aud,
        "iss": iss or os.environ["SUPABASE_URL"] + "/auth/v1",
        "iat": now,
        "exp": now + exp_delta_s,
        "role": "authenticated",
        "session_id": str(uuid.uuid4()),
    }
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": kid or real_kid})
