from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.config import settings
from app.database import get_db
from app.models import (
    User, UserRole, DoctorProfile, Service,
    Appointment, AppointmentStatus, Payment, PaymentStatus, MedicalRecord, SmsLog
)
from app.auth import require_roles, get_password_hash
from app.services.semaphore_service import semaphore_service
from app.services.paymongo_service import paymongo_service
from app.services.google_calendar_service import google_calendar_service

router = APIRouter(prefix="/admin", tags=["Admin Portal"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    total_patients = db.query(User).filter(User.role == UserRole.PATIENT).count()
    total_doctors = db.query(DoctorProfile).count()
    total_appointments = db.query(Appointment).count()
    
    # Revenue from paid appointments
    total_revenue = db.query(func.sum(Appointment.consultation_fee)).filter(
        Appointment.payment_status == PaymentStatus.PAID
    ).scalar() or 0.0

    pending_appointments = db.query(Appointment).filter(Appointment.status == AppointmentStatus.PENDING).count()
    confirmed_appointments = db.query(Appointment).filter(Appointment.status == AppointmentStatus.CONFIRMED).count()
    completed_appointments = db.query(Appointment).filter(Appointment.status == AppointmentStatus.COMPLETED).count()
    cancelled_appointments = db.query(Appointment).filter(Appointment.status == AppointmentStatus.CANCELLED).count()

    total_sms_sent = db.query(SmsLog).count()
    total_records_stored = db.query(MedicalRecord).count()

    recent_appointments = (
        db.query(Appointment)
        .order_by(Appointment.created_at.desc())
        .limit(8)
        .all()
    )

    recent_payments = (
        db.query(Payment)
        .order_by(Payment.created_at.desc())
        .limit(6)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context={
            "current_user": current_user,
            "total_patients": total_patients,
            "total_doctors": total_doctors,
            "total_appointments": total_appointments,
            "total_revenue": total_revenue,
            "pending_appointments": pending_appointments,
            "confirmed_appointments": confirmed_appointments,
            "completed_appointments": completed_appointments,
            "cancelled_appointments": cancelled_appointments,
            "total_sms_sent": total_sms_sent,
            "total_records_stored": total_records_stored,
            "recent_appointments": recent_appointments,
            "recent_payments": recent_payments,
            "settings": settings
        }
    )

# ----------------- DOCTORS CRUD -----------------
@router.get("/doctors", response_class=HTMLResponse)
async def admin_doctors_list(
    request: Request,
    created: bool = False,
    deleted: bool = False,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    doctors = db.query(DoctorProfile).all()
    return templates.TemplateResponse(
        request=request,
        name="admin/doctors.html",
        context={
            "current_user": current_user,
            "doctors": doctors,
            "created": created,
            "deleted": deleted,
            "settings": settings
        }
    )

@router.post("/doctors/create")
async def admin_create_doctor(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    phone_number: str = Form(...),
    specialization: str = Form(...),
    license_number: str = Form(""),
    consultation_fee: float = Form(500.0),
    clinic_room: str = Form("Room 101"),
    schedule_days: str = Form("Monday to Friday"),
    schedule_hours: str = Form("09:00 AM - 05:00 PM"),
    bio: str = Form(""),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(User.email == email.strip().lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    user = User(
        email=email.strip().lower(),
        hashed_password=get_password_hash(password),
        full_name=full_name.strip(),
        phone_number=phone_number.strip(),
        role=UserRole.DOCTOR
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    doc_profile = DoctorProfile(
        user_id=user.id,
        specialization=specialization.strip(),
        license_number=license_number.strip(),
        consultation_fee=consultation_fee,
        clinic_room=clinic_room.strip(),
        schedule_days=schedule_days.strip(),
        schedule_hours=schedule_hours.strip(),
        bio=bio.strip(),
        is_available=True
    )
    db.add(doc_profile)
    db.commit()

    return RedirectResponse(url="/admin/doctors?created=true", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/doctors/{doctor_id}/delete")
async def admin_delete_doctor(
    doctor_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    doctor = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Delete associated user (cascades)
    user = doctor.user
    db.delete(user)
    db.commit()
    return RedirectResponse(url="/admin/doctors?deleted=true", status_code=status.HTTP_303_SEE_OTHER)

# ----------------- SERVICES CRUD -----------------
@router.get("/services", response_class=HTMLResponse)
async def admin_services_list(
    request: Request,
    created: bool = False,
    deleted: bool = False,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    services = db.query(Service).all()
    return templates.TemplateResponse(
        request=request,
        name="admin/services.html",
        context={
            "current_user": current_user,
            "services": services,
            "created": created,
            "deleted": deleted,
            "settings": settings
        }
    )

@router.post("/services/create")
async def admin_create_service(
    request: Request,
    name: str = Form(...),
    category: str = Form("General"),
    description: str = Form(""),
    base_price: float = Form(500.0),
    duration_minutes: int = Form(30),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    service = Service(
        name=name.strip(),
        category=category.strip(),
        description=description.strip(),
        base_price=base_price,
        duration_minutes=duration_minutes,
        is_active=True
    )
    db.add(service)
    db.commit()
    return RedirectResponse(url="/admin/services?created=true", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/services/{service_id}/delete")
async def admin_delete_service(
    service_id: int,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    db.delete(service)
    db.commit()
    return RedirectResponse(url="/admin/services?deleted=true", status_code=status.HTTP_303_SEE_OTHER)

# ----------------- APPOINTMENTS CRUD -----------------
@router.get("/appointments", response_class=HTMLResponse)
async def admin_appointments_list(
    request: Request,
    status_filter: str = "ALL",
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    query = db.query(Appointment)
    if status_filter != "ALL":
        query = query.filter(Appointment.status == status_filter)
    appointments = query.order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="admin/appointments.html",
        context={
            "current_user": current_user,
            "appointments": appointments,
            "status_filter": status_filter,
            "settings": settings
        }
    )

@router.post("/appointments/{appointment_id}/update-status")
async def admin_update_appointment_status(
    appointment_id: int,
    status_val: str = Form(...),
    payment_status_val: str = Form(...),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.status = AppointmentStatus(status_val)
    appointment.payment_status = PaymentStatus(payment_status_val)
    
    if appointment.payment:
        appointment.payment.status = PaymentStatus(payment_status_val)
        if payment_status_val == "PAID" and not appointment.payment.paid_at:
            appointment.payment.paid_at = datetime.utcnow()

    db.commit()

    # Semaphore SMS on admin override
    await semaphore_service.send_sms(
        recipient_phone=appointment.patient.phone_number or "09171234567",
        message=f"CareSync Admin Notice: Appointment {appointment.appointment_code} status is now {status_val}. Payment: {payment_status_val}.",
        recipient_name=appointment.patient.full_name,
        db=db
    )

    return RedirectResponse(url="/admin/appointments?updated=true", status_code=status.HTTP_303_SEE_OTHER)

# ----------------- PAYMONGO PAYMENTS -----------------
@router.get("/payments", response_class=HTMLResponse)
async def admin_payments_list(
    request: Request,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    payments = db.query(Payment).order_by(Payment.created_at.desc()).all()
    total_collected = sum(p.amount for p in payments if p.status == PaymentStatus.PAID)

    return templates.TemplateResponse(
        request=request,
        name="admin/payments.html",
        context={
            "current_user": current_user,
            "payments": payments,
            "total_collected": total_collected,
            "settings": settings
        }
    )

# ----------------- SEMAPHORE SMS LOGS -----------------
@router.get("/sms-logs", response_class=HTMLResponse)
async def admin_sms_logs(
    request: Request,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    logs = db.query(SmsLog).order_by(SmsLog.sent_at.desc()).limit(100).all()
    return templates.TemplateResponse(
        request=request,
        name="admin/sms_logs.html",
        context={
            "current_user": current_user,
            "logs": logs,
            "settings": settings
        }
    )

# ----------------- 5-API STATUS & HEALTH TESTER -----------------
@router.get("/api-status", response_class=HTMLResponse)
async def admin_api_status(
    request: Request,
    test_result: str = None,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    api_statuses = [
        {
            "name": "PayMongo Payment Gateway",
            "category": "Payments & Billing (Sandbox / Live)",
            "configured": settings.is_paymongo_configured,
            "mode": "Live Production" if settings.is_paymongo_configured else "Sandbox Simulator",
            "endpoint": settings.PAYMONGO_BASE_URL,
            "docs": "https://developers.paymongo.com",
            "icon": "credit-card"
        },
        {
            "name": "Semaphore SMS Gateway",
            "category": "Mobile SMS Notifications (Philippines)",
            "configured": settings.is_semaphore_configured,
            "mode": "Live Gateway" if settings.is_semaphore_configured else "Sandbox Mock Logger",
            "endpoint": "https://api.semaphore.co/api/v4/messages",
            "docs": "https://semaphore.co/docs",
            "icon": "message-square"
        },
        {
            "name": "Google Calendar API",
            "category": "Calendar Scheduling & Sync",
            "configured": settings.is_google_calendar_configured,
            "mode": "Live API & Universal Deep Link" if settings.is_google_calendar_configured else "Universal Deep Link Sync",
            "endpoint": "https://www.googleapis.com/calendar/v3",
            "docs": "https://developers.google.com/calendar",
            "icon": "calendar"
        },
        {
            "name": "Google OAuth 2.0",
            "category": "Authentication & Social Sign-In",
            "configured": settings.is_google_oauth_configured,
            "mode": "Google Cloud Console Live" if settings.is_google_oauth_configured else "Interactive OAuth Mock Simulator",
            "endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
            "docs": "https://developers.google.com/identity/protocols/oauth2",
            "icon": "lock"
        },
        {
            "name": "Cloudinary Document Storage",
            "category": "Medical Documents & ID Storage",
            "configured": settings.is_cloudinary_configured,
            "mode": "Cloudinary Cloud CDN" if settings.is_cloudinary_configured else "Local Sandbox Storage (/static/uploads)",
            "endpoint": f"https://api.cloudinary.com/v1_1/{settings.CLOUDINARY_CLOUD_NAME or 'default'}",
            "docs": "https://cloudinary.com/documentation",
            "icon": "cloud"
        }
    ]

    return templates.TemplateResponse(
        request=request,
        name="admin/api_status.html",
        context={
            "current_user": current_user,
            "api_statuses": api_statuses,
            "test_result": test_result,
            "settings": settings
        }
    )

@router.post("/api-status/test-sms")
async def admin_test_sms(
    request: Request,
    phone: str = Form("09171234567"),
    message: str = Form("CareSync API Test: System is operating smoothly!"),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    res = await semaphore_service.send_sms(
        recipient_phone=phone,
        message=message,
        recipient_name="Admin Test",
        db=db
    )
    return RedirectResponse(
        url=f"/admin/api-status?test_result=SMS+Dispatched:+{res.get('status')}",
        status_code=status.HTTP_303_SEE_OTHER
    )
