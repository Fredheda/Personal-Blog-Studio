"""Who is calling: the roles in the principal header the platform injects.

Container Apps validates the token and passes its claims as the Base64 JSON
header `X-MS-CLIENT-PRINCIPAL`; an outside request cannot set it. The platform
does not check roles, so this module does. The app must run with platform
authentication enabled (`platform.enabled: true`, pinned by the infra tests):
without it the header would be client-controlled.
"""

import base64
import binascii
import json

from fastapi import Request

ROLE_CLAIM_TYPES = {
    "roles",
    "role",
    "http://schemas.microsoft.com/ws/2008/06/identity/claims/role",
}
PRINCIPAL_HEADER = "X-MS-CLIENT-PRINCIPAL"


class ApiError(Exception):
    def __init__(self, status: int, title: str, detail: str | None = None) -> None:
        super().__init__(title)
        self.status, self.title, self.detail = status, title, detail


def roles_from_principal(header: str | None) -> set[str]:
    if not header:
        raise ApiError(401, "Unauthorized", "a valid bearer token is required")
    try:
        data = json.loads(base64.b64decode(header, validate=True))
    except (binascii.Error, ValueError):
        raise ApiError(
            401, "Unauthorized", "a valid bearer token is required"
        ) from None
    claims = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(claims, list):
        raise ApiError(401, "Unauthorized", "a valid bearer token is required")
    return {
        claim["val"]
        for claim in claims
        if isinstance(claim, dict)
        and claim.get("typ") in ROLE_CLAIM_TYPES
        and isinstance(claim.get("val"), str)
    }


def require_role(request: Request) -> None:
    roles = roles_from_principal(request.headers.get(PRINCIPAL_HEADER))
    if request.app.state.required_role not in roles:
        raise ApiError(403, "Forbidden", "the caller is not approved for this API")
