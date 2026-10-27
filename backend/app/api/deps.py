from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import User
from app.core.security import decode_token

security = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided."
        )
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token."
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing user identifier."
        )
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated."
        )
    return user

def require_role(allowed_role: str):
    """Dependency factory enforcing specific role access."""
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role.upper() != allowed_role.upper():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {allowed_role.upper()}"
            )
        return user
    return role_checker

def require_roles(allowed_roles: list[str]):
    """Dependency factory enforcing membership in any of the allowed roles."""
    def roles_checker(user: User = Depends(get_current_user)) -> User:
        upper_roles = [r.upper() for r in allowed_roles]
        if user.role.upper() not in upper_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role in: {', '.join(upper_roles)}"
            )
        return user
    return roles_checker

def get_current_parent_user(user: User = Depends(require_role("PARENT"))) -> User:
    return user

def get_current_family_user(user: User = Depends(require_role("FAMILY"))) -> User:
    return user

def get_current_care_circle_user(user: User = Depends(require_roles(["FAMILY", "GUARDIAN", "CAREGIVER"]))) -> User:
    return user

