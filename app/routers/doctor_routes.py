from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import (
    User, UserRole, DoctorProfile,
    Appointment, AppointmentStatus, PaymentStatus, MedicalRecord, SmsLog
)
from app.auth import require_roles
from app.services.semaphore_service import semaphore_service

router = APIRouter(prefix="/doctor", tags=["Doctor Portal"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def doctor_dashboard(
    request: Request,
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == current_user.id).first()
    if not profile and current_user.role == UserRole.ADMIN:
        # Admin viewing doctor dashboard
        profile = db.query(DoctorProfile).first()

    if not profile:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    today = date.today()
    all_appointments = (
        db.query(Appointment)
        .filter(Appointment.doctor_id == profile.id)
        .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.asc())
        .all()
    )

    today_appointments = [a for a in all_appointments if a.appointment_date == today]
    pending_count = sum(1 for a in all_appointments if a.status == AppointmentStatus.PENDING)
    completed_count = sum(1 for a in all_appointments if a.status == AppointmentStatus.COMPLETED)
    total_earnings = sum(a.consultation_fee for a in all_appointments if a.payment_status == PaymentStatus.PAID)

    return templates.TemplateResponse(
        request=request,
        name="doctor/dashboard.html",
        context={
            "current_user": current_user,
            "profile": profile,
            "today_appointments": today_appointments,
            "all_appointments": all_appointments[:10],
            "pending_count": pending_count,
            "completed_count": completed_count,
            "total_earnings": total_earnings,
            "settings": settings
        }
    )

@router.get("/appointments", response_class=HTMLResponse)
async def doctor_appointments_list(
    request: Request,
    status_filter: str = "ALL",
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == current_user.id).first()
    if not profile and current_user.role == UserRole.ADMIN:
        profile = db.query(DoctorProfile).first()

    query = db.query(Appointment).filter(Appointment.doctor_id == profile.id)
    if status_filter != "ALL":
        query = query.filter(Appointment.status == status_filter)

    appointments = query.order_by(Appointment.appointment_date.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="doctor/appointments.html",
        context={
            "current_user": current_user,
            "profile": profile,
            "appointments": appointments,
            "status_filter": status_filter,
            "settings": settings
        }
    )

@router.get("/appointments/{appointment_id}", response_class=HTMLResponse)
async def doctor_appointment_detail(
    request: Request,
    appointment_id: int,
    updated: bool = False,
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    patient_records = (
        db.query(MedicalRecord)
        .filter(MedicalRecord.patient_id == appointment.patient_id)
        .order_by(MedicalRecord.uploaded_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="doctor/appointment_detail.html",
        context={
            "current_user": current_user,
            "appointment": appointment,
            "patient_records": patient_records,
            "updated": updated,
            "settings": settings
        }
    )

@router.post("/appointments/{appointment_id}/update")
async def doctor_update_appointment(
    request: Request,
    appointment_id: int,
    status_val: str = Form(...),
    doctor_diagnosis: str = Form(""),
    doctor_prescription: str = Form(""),
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    old_status = appointment.status
    appointment.status = AppointmentStatus(status_val)
    if doctor_diagnosis:
        appointment.doctor_diagnosis = doctor_diagnosis.strip()
    if doctor_prescription:
        appointment.doctor_prescription = doctor_prescription.strip()

    db.commit()

    # Semaphore SMS Notification (API 2)
    sms_text = (
        f"CareSync Update: Dr. {appointment.doctor.user.full_name} has updated appointment {appointment.appointment_code}. "
        f"Status: {appointment.status.value}. Please log in to view prescription/diagnosis."
    )
    await semaphore_service.send_sms(
        recipient_phone=appointment.patient.phone_number or "09171234567",
        message=sms_text,
        recipient_name=appointment.patient.full_name,
        db=db
    )

    return RedirectResponse(
        url=f"/doctor/appointments/{appointment_id}?updated=true",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.get("/profile", response_class=HTMLResponse)
async def doctor_profile_page(
    request: Request,
    saved: bool = False,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    db: Session = Depends(get_db)
):
    profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == current_user.id).first()
    return templates.TemplateResponse(
        request=request,
        name="doctor/profile.html",
        context={
            "current_user": current_user,
            "profile": profile,
            "saved": saved,
            "settings": settings
        }
    )

@router.post("/profile")
async def doctor_profile_update(
    request: Request,
    specialization: str = Form(...),
    license_number: str = Form(""),
    consultation_fee: float = Form(500.0),
    clinic_room: str = Form("Room 101"),
    schedule_days: str = Form("Monday to Friday"),
    schedule_hours: str = Form("09:00 AM - 05:00 PM"),
    bio: str = Form(""),
    is_available: bool = Form(False),
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    db: Session = Depends(get_db)
):
    profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == current_user.id).first()
    if not profile:
        profile = DoctorProfile(user_id=current_user.id, specialization=specialization)
        db.add(profile)

    profile.specialization = specialization.strip()
    profile.license_number = license_number.strip()
    profile.consultation_fee = consultation_fee
    profile.clinic_room = clinic_room.strip()
    profile.schedule_days = schedule_days.strip()
    profile.schedule_hours = schedule_hours.strip()
    profile.bio = bio.strip()
    profile.is_available = is_available

    db.commit()
    return RedirectResponse(url="/doctor/profile?saved=true", status_code=status.HTTP_303_SEE_OTHER)
