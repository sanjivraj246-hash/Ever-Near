from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import User
from app.schemas.schemas import (
    UserRegister, UserLogin, TokenResponse, UserProfileResponse,
    GoogleAuthRequest, GoogleAccountLinkRequest,
    ForgotPinRequest, ForgotPinResetRequest, ForgotPinResponse
)
from app.services.auth_service import AuthService
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse)
def register(req: UserRegister, db: Session = Depends(get_db)):
    """Registers a new user (Parent or Family) with hashed PIN and role-specific profile."""
    return AuthService.register_user(db, req)

@router.post("/login", response_model=TokenResponse)
def login(req: UserLogin, db: Session = Depends(get_db)):
    """Authenticates phone and 6-digit PIN using salted bcrypt, returning a signed JWT."""
    return AuthService.login_user(db, req)

@router.get("/me", response_model=UserProfileResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetches profile for currently authenticated JWT subject."""
    return AuthService.get_user_profile(db, current_user)

@router.post("/logout")
def logout():
    """Invalidates client session."""
    return {"message": "Logged out successfully"}

@router.get("/google/config")
def get_google_config():
    """Returns Google OAuth configuration and readiness status."""
    return AuthService.get_google_auth_config()

@router.post("/google")
def google_auth(req: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Verifies Google ID token, finds or registers user, and returns JWT session."""
    return AuthService.google_auth(db, req)

@router.post("/google/link", response_model=TokenResponse)
def link_google(req: GoogleAccountLinkRequest, db: Session = Depends(get_db)):
    """Securely links a verified Google account to an existing mobile + PIN account."""
    return AuthService.link_google_account(db, req)

@router.post("/forgot-pin/request", response_model=ForgotPinResponse)
def forgot_pin_request(req: ForgotPinRequest, db: Session = Depends(get_db)):
    """Generates a secure 15-minute PIN recovery code."""
    return AuthService.request_forgot_pin(db, req)

@router.post("/forgot-pin/reset", response_model=TokenResponse)
def forgot_pin_reset(req: ForgotPinResetRequest, db: Session = Depends(get_db)):
    """Verifies recovery code and resets user PIN, returning authenticated session."""
    return AuthService.reset_forgot_pin(db, req)
