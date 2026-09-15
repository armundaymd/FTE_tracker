import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from auth.security import ACCESS_TOKEN_TYPE, JWTError, decode_token

# tokenUrl is only used by FastAPI's docs UI to build the "Authorize" form.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str
    role: str
    physician_id: Optional[uuid.UUID]

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def owns_physician(self, physician_id: uuid.UUID) -> bool:
        """For the future 'provider' role: True if this user's own record is `physician_id`."""
        return self.physician_id is not None and self.physician_id == physician_id


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> CurrentUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise unauthorized

    try:
        payload = decode_token(token)
    except JWTError:
        raise unauthorized

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise unauthorized

    user_id = payload.get("sub")
    if user_id is None:
        raise unauthorized

    physician_id_raw = payload.get("physician_id")
    return CurrentUser(
        id=uuid.UUID(user_id),
        email=payload.get("email", ""),
        role=payload.get("role", "viewer"),
        physician_id=uuid.UUID(physician_id_raw) if physician_id_raw else None,
    )


def require_role(*allowed_roles: str):
    """
    Dependency factory for future use, e.g. Depends(require_role("admin")).
    Not applied to any route yet — enforcing role checks on existing endpoints
    is a separate, deliberate follow-up, not part of standing up login itself.
    """

    async def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return _check
