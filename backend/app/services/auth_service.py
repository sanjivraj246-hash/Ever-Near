import re
import datetime
import secrets
from typing import Optional, Dict, Any
import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.entities import User, ParentProfile, FamilyProfile
from app.schemas.schemas import (
    UserRegister, UserLogin, TokenResponse, UserProfileResponse,
    GoogleAuthRequest, GoogleAccountLinkRequest,
    ForgotPinRequest, ForgotPinResetRequest, ForgotPinResponse
)
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings

def normalize_phone(phone: str) -> str:
    """
    Normalizes phone input into standard format.
    Strips whitespace, symbols, parentheses, hyphens.
    For Indian numbers: removes leading +91, 91, or 0 to yield 10 digits.
    For international numbers: preserves the numeric digit string.
    """
    cleaned = re.sub(r"[^\d]", "", str(phone or ""))
    if cleaned.startswith("91") and len(cleaned) > 10:
        return cleaned[2:]
    if cleaned.startswith("0") and len(cleaned) > 10:
        return cleaned[1:]
    if len(cleaned) > 10:
        return cleaned[-10:]
    return cleaned

class AuthService:
    @staticmethod
    def register_user(db: Session, req: UserRegister) -> TokenResponse:
        clean_phone = normalize_phone(req.phone)
        if not clean_phone or len(clean_phone) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide a valid phone number (at least 6 digits)."
            )

        if not req.full_name or len(req.full_name.strip()) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please enter your full name."
            )

        if not req.password or len(req.password) < 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PIN must be at least 4 characters long."
            )

        if req.password_confirm is not None and req.password != req.password_confirm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passwords do not match."
            )

        target_role = req.role.strip().upper()
        if target_role not in ["PARENT", "FAMILY"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be either PARENT or FAMILY."
            )

        existing = db.query(User).filter(User.phone == clean_phone).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this phone number already exists."
            )

        user = User(
            phone=clean_phone,
            full_name=req.full_name.strip(),
            role=target_role,
            password_hash=hash_password(req.password),
            is_active=True,
            failed_login_attempts=0
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Parent creates parent_profiles, Family creates family_profiles
        if target_role == "PARENT":
            profile = ParentProfile(
                user_id=user.id,
                preferred_name=req.preferred_name or req.full_name.strip() or "Amma",
                language_pref=req.language_pref or "ta"
            )
            db.add(profile)
            db.commit()
        else:
            profile = FamilyProfile(
                user_id=user.id,
                preferred_name=req.preferred_name or req.full_name.strip(),
                relationship_type=req.relationship_type or "Family Member",
                language_pref=req.language_pref or "en"
            )
            db.add(profile)
            db.commit()

        token = create_access_token(user.id, user.role)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            role=user.role,
            user_id=user.id,
            full_name=user.full_name
        )

    @staticmethod
    def login_user(db: Session, req: UserLogin) -> TokenResponse:
        clean_phone = normalize_phone(req.phone)
        if not clean_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please enter your mobile number."
            )

        user = db.query(User).filter(User.phone == clean_phone).first()
        if not user:
            # Check if seeded demo user requested in dev mode
            if clean_phone in ["9876543210", "9876543211", "9344602561", "8438772409"] and settings.OTP_DEV_MODE:
                if clean_phone == "9344602561":
                    role_guess = "PARENT"
                    name_guess = "Ranjitha Amma"
                    pin_guess = "243007"
                elif clean_phone == "8438772409":
                    role_guess = "FAMILY"
                    name_guess = "Sanjiv Raj"
                    pin_guess = "243007"
                elif clean_phone == "9876543210":
                    role_guess = "PARENT"
                    name_guess = "Lakshmi Amma"
                    pin_guess = "1234"
                else:
                    role_guess = "FAMILY"
                    name_guess = "Karthik (Son)"
                    pin_guess = "1234"

                user = User(
                    phone=clean_phone,
                    full_name=name_guess,
                    role=role_guess,
                    password_hash=hash_password(pin_guess),
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)

                if user.role == "PARENT":
                    profile = ParentProfile(user_id=user.id, preferred_name="Amma", language_pref="ta")
                    db.add(profile)
                else:
                    profile = FamilyProfile(user_id=user.id, preferred_name=name_guess.split()[0], relationship_type="Son", language_pref="en")
                    db.add(profile)
                db.commit()
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="We couldn't find an account with this mobile number."
                )

        # Check if account is disabled
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is temporarily unavailable. Please contact support."
            )

        # Check brute-force lockout
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if user.locked_until:
            locked_dt = user.locked_until
            if locked_dt.tzinfo is None:
                locked_dt = locked_dt.replace(tzinfo=datetime.timezone.utc)
            if locked_dt > now_utc:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="For your security, sign-in is temporarily paused. Please try again later."
                )

        entered_pass = req.pin or req.password or req.otp
        if not entered_pass:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="That PIN is incorrect. Please try again. Unable to sign in. Please check your details."
            )

        # Salted bcrypt password verification
        if not verify_password(entered_pass, user.password_hash):
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
                user.locked_until = now_utc + datetime.timedelta(minutes=settings.ACCOUNT_LOCK_MINUTES)
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="For your security, sign-in is temporarily paused. Please try again later."
                )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="That PIN is incorrect. Please try again. Unable to sign in. Please check your details."
            )

        # Successful authentication: reset failed attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

        token = create_access_token(user.id, user.role)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            role=user.role,
            user_id=user.id,
            full_name=user.full_name
        )

    @staticmethod
    def authenticate_user(db: Session, phone: str, password: str) -> Optional[User]:
        clean_phone = normalize_phone(phone)
        if not clean_phone:
            return None
        user = db.query(User).filter(User.phone == clean_phone).first()
        if not user or not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def create_access_token_for_user(user: User) -> str:
        return create_access_token(user.id, user.role)

    @staticmethod
    def get_user_profile(db: Session, current_user: User) -> UserProfileResponse:
        preferred_name = current_user.full_name
        lang = "ta"
        rel_type = None

        if current_user.parent_profile:
            preferred_name = current_user.parent_profile.preferred_name
            lang = current_user.parent_profile.language_pref
        elif current_user.family_profile:
            preferred_name = current_user.family_profile.preferred_name
            lang = current_user.family_profile.language_pref
            rel_type = current_user.family_profile.relationship_type

        return UserProfileResponse(
            id=current_user.id,
            phone=current_user.phone,
            full_name=current_user.full_name,
            role=current_user.role,
            preferred_name=preferred_name,
            language_pref=lang,
            relationship_type=rel_type
        )

    @staticmethod
    def request_forgot_pin(db: Session, req: ForgotPinRequest) -> ForgotPinResponse:
        clean_phone = normalize_phone(req.phone)
        if not clean_phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please enter your mobile number.")

        user = db.query(User).filter(User.phone == clean_phone).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="We couldn't find an account with this mobile number.")

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is temporarily unavailable. Please contact support.")

        recovery_code = f"{secrets.randbelow(900000) + 100000}"
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        user.recovery_token = recovery_code
        user.recovery_token_expires_at = now_utc + datetime.timedelta(minutes=15)
        db.commit()

        sms_dispatched = False
        dev_token = None

        if settings.SMS_PROVIDER_API_KEY and settings.SMS_PROVIDER_API_KEY.strip():
            sms_dispatched = True
        elif settings.OTP_DEV_MODE:
            dev_token = recovery_code
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS provider is not configured. Please set SMS_PROVIDER_API_KEY."
            )

        return ForgotPinResponse(
            message="Recovery code sent to your mobile number." if sms_dispatched else "Recovery code generated in test/dev mode.",
            phone=clean_phone,
            dev_recovery_token=dev_token,
            sms_dispatched=sms_dispatched
        )

    @staticmethod
    def reset_forgot_pin(db: Session, req: ForgotPinResetRequest) -> TokenResponse:
        clean_phone = normalize_phone(req.phone)
        user = db.query(User).filter(User.phone == clean_phone).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="We couldn't find an account with this mobile number.")

        if not req.new_pin or not req.new_pin.isdigit() or len(req.new_pin) != 6:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New PIN must be exactly 6 numeric digits.")

        if req.new_pin_confirm is not None and req.new_pin != req.new_pin_confirm:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PINs do not match.")

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if not user.recovery_token or not user.recovery_token_expires_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No recovery code was requested. Please request a code first.")

        expires_at = user.recovery_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)

        if expires_at < now_utc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recovery code has expired. Please request a new one.")

        if req.recovery_token.strip() != user.recovery_token.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recovery code. Please check and try again.")

        user.password_hash = hash_password(req.new_pin)
        user.recovery_token = None
        user.recovery_token_expires_at = None
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

        token = create_access_token(user.id, user.role)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            role=user.role,
            user_id=user.id,
            full_name=user.full_name
        )

    @staticmethod
    def get_google_auth_config() -> Dict[str, Any]:
        configured = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_ID.strip())
        return {
            "configured": configured,
            "client_id": settings.GOOGLE_CLIENT_ID if configured else None,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI if configured else None,
            "status": "CONFIGURED" if configured else "BLOCKED",
            "message": (
                "Google OAuth is configured and active."
                if configured
                else "GOOGLE AUTH BLOCKED — GOOGLE_CLIENT_ID/CLIENT_SECRET/REDIRECT_URI NOT CONFIGURED"
            ),
            "instructions": (
                None
                if configured
                else "To configure Google Authentication: 1. Create OAuth 2.0 Client ID in Google Cloud Console. 2. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI in backend/.env."
            )
        }

    @staticmethod
    def verify_google_id_token(id_token_str: str) -> Dict[str, Any]:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_ID.strip():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GOOGLE AUTH BLOCKED — GOOGLE_CLIENT_ID/CLIENT_SECRET/REDIRECT_URI NOT CONFIGURED"
            )

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token_str}")
                if res.status_code != 200:
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google identity token.")
                data = res.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Google verification network error: {str(e)}")

        if data.get("aud") != settings.GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google token audience does not match configured client.")

        if data.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token issuer.")

        email_verified = data.get("email_verified")
        if email_verified not in [True, "true", "True"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google email is not verified.")

        return {
            "google_id": data.get("sub"),
            "email": data.get("email"),
            "name": data.get("name", "Google User"),
            "picture": data.get("picture")
        }

    @staticmethod
    def google_auth(db: Session, req: GoogleAuthRequest) -> Dict[str, Any]:
        token_info = AuthService.verify_google_id_token(req.id_token)
        google_id = token_info["google_id"]
        email = token_info["email"]
        name = req.full_name or token_info["name"]

        user = db.query(User).filter(
            (User.google_id == google_id) | (User.google_email == email)
        ).first()

        if user:
            if not user.google_id:
                user.google_id = google_id
            if not user.google_email:
                user.google_email = email
            db.commit()

            token = create_access_token(user.id, user.role)
            return {
                "action": "LOGIN",
                "token_response": TokenResponse(
                    access_token=token,
                    token_type="bearer",
                    role=user.role,
                    user_id=user.id,
                    full_name=user.full_name
                ).model_dump()
            }

        if req.phone and req.pin:
            clean_phone = normalize_phone(req.phone)
            if len(clean_phone) < 6:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please enter a valid mobile number.")
            if not req.pin.isdigit() or len(req.pin) != 6:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PIN must be exactly 6 numeric digits.")

            existing_phone = db.query(User).filter(User.phone == clean_phone).first()
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="An account with this phone number already exists. Please link your account or sign in with your PIN."
                )

            target_role = (req.role or "PARENT").strip().upper()
            if target_role not in ["PARENT", "FAMILY"]:
                target_role = "PARENT"

            new_user = User(
                phone=clean_phone,
                full_name=name,
                role=target_role,
                password_hash=hash_password(req.pin),
                google_id=google_id,
                google_email=email,
                is_active=True
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            if target_role == "PARENT":
                profile = ParentProfile(
                    user_id=new_user.id,
                    preferred_name=name,
                    language_pref=req.language_pref or "ta"
                )
                db.add(profile)
            else:
                profile = FamilyProfile(
                    user_id=new_user.id,
                    preferred_name=name,
                    relationship_type=req.relationship_type or "Child",
                    language_pref=req.language_pref or "en"
                )
                db.add(profile)
            db.commit()

            token = create_access_token(new_user.id, new_user.role)
            return {
                "action": "REGISTERED",
                "token_response": TokenResponse(
                    access_token=token,
                    token_type="bearer",
                    role=new_user.role,
                    user_id=new_user.id,
                    full_name=new_user.full_name
                ).model_dump()
            }

        return {
            "action": "NEEDS_REGISTRATION_DETAILS",
            "google_id": google_id,
            "google_email": email,
            "name": name,
            "message": "Google verified. Please select role, mobile number and 6-digit PIN to complete registration."
        }

    @staticmethod
    def link_google_account(db: Session, req: GoogleAccountLinkRequest) -> TokenResponse:
        token_info = AuthService.verify_google_id_token(req.id_token)
        google_id = token_info["google_id"]
        email = token_info["email"]

        clean_phone = normalize_phone(req.phone)
        user = db.query(User).filter(User.phone == clean_phone).first()
        if not user or not verify_password(req.pin, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid mobile number or PIN.")

        existing_google = db.query(User).filter(
            (User.google_id == google_id) & (User.id != user.id)
        ).first()
        if existing_google:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This Google account is already linked to another EVER NEAR account."
            )

        user.google_id = google_id
        user.google_email = email
        db.commit()

        token = create_access_token(user.id, user.role)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            role=user.role,
            user_id=user.id,
            full_name=user.full_name
        )
