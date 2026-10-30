from pathlib import Path
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User, UserRole, DoctorProfile
from app.auth import (
    verify_password, get_password_hash, create_access_token,
    get_optional_current_user
)
from app.services.google_oauth_service import google_oauth_service

router = APIRouter(prefix="", tags=["Authentication"])
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, success: str = None, user=Depends(get_optional_current_user)):
    if user:
        if user.role == UserRole.ADMIN:
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        elif user.role == UserRole.DOCTOR:
            return RedirectResponse(url="/doctor/dashboard", status_code=303)
        return RedirectResponse(url="/patient/dashboard", status_code=303)

    google_auth_url = google_oauth_service.get_authorization_url(
        redirect_uri=f"{settings.APP_URL}/auth/google/callback"
    )
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "error": error,
            "success": success,
            "google_auth_url": google_auth_url,
            "settings": settings
        }
    )

@router.post("/login")
async def login_submit(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "Invalid email or password",
                "google_auth_url": google_oauth_service.get_authorization_url(f"{settings.APP_URL}/auth/google/callback"),
                "settings": settings
            },
            status_code=400
        )

    if not user.is_active:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": "This account is inactive. Please contact support.",
                "google_auth_url": google_oauth_service.get_authorization_url(f"{settings.APP_URL}/auth/google/callback"),
                "settings": settings
            },
            status_code=403
        )

    token = create_access_token(data={"sub": user.email, "role": user.role.value, "id": user.id})
    
    redirect_target = "/patient/dashboard"
    if user.role == UserRole.ADMIN:
        redirect_target = "/admin/dashboard"
    elif user.role == UserRole.DOCTOR:
        redirect_target = "/doctor/dashboard"

    res = RedirectResponse(url=redirect_target, status_code=status.HTTP_303_SEE_OTHER)
    res.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, max_age=86400, samesite="lax")
    return res

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None, user=Depends(get_optional_current_user)):
    if user:
        return RedirectResponse(url="/patient/dashboard", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context={"error": error, "settings": settings}
    )

@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    full_name: str = Form(...),
    phone_number: str = Form(...),
    role: str = Form("PATIENT"),
    specialization: str = Form("General Medicine"),
    consultation_fee: float = Form(500.0),
    db: Session = Depends(get_db)
):
    if password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={"error": "Passwords do not match", "settings": settings},
            status_code=400
        )

    existing = db.query(User).filter(User.email == email.strip().lower()).first()
    if existing:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={"error": "An account with this email already exists", "settings": settings},
            status_code=400
        )

    assigned_role = UserRole.DOCTOR if role.upper() == "DOCTOR" else UserRole.PATIENT

    new_user = User(
        email=email.strip().lower(),
        hashed_password=get_password_hash(password),
        full_name=full_name.strip(),
        phone_number=phone_number.strip(),
        role=assigned_role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if assigned_role == UserRole.DOCTOR:
        doc_profile = DoctorProfile(
            user_id=new_user.id,
            specialization=specialization.strip(),
            consultation_fee=consultation_fee,
            bio=f"Certified {specialization} practitioner at CareSync Clinic."
        )
        db.add(doc_profile)
        db.commit()

    token = create_access_token(data={"sub": new_user.email, "role": new_user.role.value, "id": new_user.id})
    target = "/doctor/dashboard" if assigned_role == UserRole.DOCTOR else "/patient/dashboard"
    res = RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)
    res.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, max_age=86400, samesite="lax")
    return res

@router.get("/auth/google")
async def auth_google():
    auth_url = google_oauth_service.get_authorization_url(
        redirect_uri=f"{settings.APP_URL}/auth/google/callback"
    )
    return RedirectResponse(url=auth_url)

@router.get("/auth/google/mock", response_class=HTMLResponse)
async def auth_google_mock(request: Request, state: str = "login"):
    """
    Interactive Google OAuth Sandbox Simulator.
    Allows testing Google Sign-In with 1-click preset test accounts.
    """
    return templates.TemplateResponse(
        request=request,
        name="auth/google_mock.html",
        context={
            "state": state,
            "settings": settings
        }
    )

@router.get("/auth/google/callback")
async def auth_google_callback(
    request: Request,
    code: str = None,
    mock_email: str = None,
    mock_name: str = None,
    mock_role: str = "PATIENT",
    db: Session = Depends(get_db)
):
    profile = None
    if mock_email:
        # From Google Mock Simulator
        profile = {
            "google_id": f"g_mock_{int(hash(mock_email) % 1000000)}",
            "email": mock_email.strip().lower(),
            "full_name": mock_name or "Google User",
            "avatar_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop"
        }
    elif code:
        profile = await google_oauth_service.exchange_code_for_user(
            code=code,
            redirect_uri=f"{settings.APP_URL}/auth/google/callback"
        )

    if not profile or not profile.get("email"):
        return RedirectResponse(url="/login?error=Google+authentication+failed", status_code=303)

    user = db.query(User).filter(User.email == profile["email"]).first()
    if not user:
        # Create user via Google OAuth
        assigned_role = UserRole.PATIENT
        if mock_role == "DOCTOR":
            assigned_role = UserRole.DOCTOR
        elif mock_role == "ADMIN":
            assigned_role = UserRole.ADMIN

        user = User(
            email=profile["email"],
            full_name=profile["full_name"],
            phone_number="09171234567",
            role=assigned_role,
            google_id=profile.get("google_id"),
            avatar_url=profile.get("avatar_url")
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        if assigned_role == UserRole.DOCTOR:
            doc_profile = DoctorProfile(
                user_id=user.id,
                specialization="General Consultation",
                consultation_fee=500.0,
                bio="Google Verified Clinic Physician."
            )
            db.add(doc_profile)
            db.commit()
    else:
        # Update google id & avatar
        if not user.google_id and profile.get("google_id"):
            user.google_id = profile["google_id"]
        if profile.get("avatar_url"):
            user.avatar_url = profile["avatar_url"]
        db.commit()

    token = create_access_token(data={"sub": user.email, "role": user.role.value, "id": user.id})
    target = "/patient/dashboard"
    if user.role == UserRole.ADMIN:
        target = "/admin/dashboard"
    elif user.role == UserRole.DOCTOR:
        target = "/doctor/dashboard"

    res = RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)
    res.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, max_age=86400, samesite="lax")
    return res

@router.get("/logout")
async def logout():
    res = RedirectResponse(url="/login?success=You+have+been+logged+out", status_code=status.HTTP_303_SEE_OTHER)
    res.delete_cookie(key="access_token")
    return res
