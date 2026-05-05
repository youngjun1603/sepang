"""JWT 인증 미들웨어"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.core.config import settings

bearer = HTTPBearer()

class CurrentUser:
    def __init__(self, id: str, role: str, shop_id: str = None):
        self.id      = id
        self.role    = role
        self.shop_id = shop_id

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer)
) -> CurrentUser:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "access":
            raise ValueError("Invalid token type")
        return CurrentUser(id=payload["sub"], role=payload["role"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

def require_role(*roles: str):
    async def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="권한이 없습니다")
        return user
    return checker
