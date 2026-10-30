from typing import List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import (
    User, UserRole, DoctorProfile, Service,
    Appointment, AppointmentStatus, Payment, PaymentStatus, SmsLog
)
from app.schemas import (
    DoctorProfileResponse, ServiceResponse,
    AppointmentCreate, AppointmentResponse, AppointmentUpdateStatus,
    SmsLogResponse
)
from app.auth import get_current_user, require_roles
from app.services.paymongo_service import paymongo_service
from app.services.semaphore_service import semaphore_service
from app.services.google_calendar_service import google_calendar_service

router = APIRouter(prefix="/api", tags=["REST API"])

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }

@router.get("/system/status")
async def api_status_summary():
    """Summary of the 5 Integrated External APIs"""
    return {
        "apis": {
            "paymongo": {
                "name": "PayMongo Sandbox/Live Gateway",
                "configured": settings.is_paymongo_configured,
                "mode": "LIVE" if settings.is_paymongo_configured else "SANDBOX_SIMULATOR"
            },
            "semaphore": {
                "name": "Semaphore SMS Gateway",
                "configured": settings.is_semaphore_configured,
                "mode": "LIVE" if settings.is_semaphore_configured else "SANDBOX_MOCK"
            },
            "google_calendar": {
                "name": "Google Calendar API",
                "configured": settings.is_google_calendar_configured,
                "mode": "LIVE" if settings.is_google_calendar_configured else "DIRECT_DEEP_LINK"
            },
            "google_oauth": {
                "name": "Google OAuth 2.0",
                "configured": settings.is_google_oauth_configured,
                "mode": "LIVE" if settings.is_google_oauth_configured else "MOCK_SIMULATOR"
            },
            "cloudinary": {
                "name": "Cloudinary Storage",
                "configured": settings.is_cloudinary_configured,
                "mode": "LIVE" if settings.is_cloudinary_configured else "LOCAL_STORAGE"
            }
        }
    }

@router.get("/doctors", response_model=List[DoctorProfileResponse])
async def get_doctors(db: Session = Depends(get_db)):
    return db.query(DoctorProfile).filter(DoctorProfile.is_available == True).all()

@router.get("/services", response_model=List[ServiceResponse])
async def get_services(db: Session = Depends(get_db)):
    return db.query(Service).filter(Service.is_active == True).all()

@router.post("/appointments", response_model=AppointmentResponse)
async def create_appointment_api(
    appt: AppointmentCreate,
    current_user: User = Depends(require_roles(UserRole.PATIENT, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    doctor = db.query(DoctorProfile).filter(DoctorProfile.id == appt.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    consultation_fee = doctor.consultation_fee
    if appt.service_id:
        srv = db.query(Service).filter(Service.id == appt.service_id).first()
        if srv:
            consultation_fee = srv.base_price

    appt_code = f"CS-{date.today().year}-{datetime.utcnow().microsecond % 10000:04d}"
    calendar_link = google_calendar_service.generate_calendar_link(
        appointment_code=appt_code,
        doctor_name=doctor.user.full_name,
        specialization=doctor.specialization,
        appointment_date=appt.appointment_date,
        appointment_time=appt.appointment_time,
        patient_notes=appt.patient_notes
    )

    new_appt = Appointment(
        appointment_code=appt_code,
        patient_id=current_user.id,
        doctor_id=doctor.id,
        service_id=appt.service_id,
        appointment_date=appt.appointment_date,
        appointment_time=appt.appointment_time,
        status=AppointmentStatus.PENDING,
        payment_status=PaymentStatus.UNPAID,
        consultation_fee=consultation_fee,
        patient_notes=appt.patient_notes,
        google_calendar_link=calendar_link
    )
    db.add(new_appt)
    db.commit()
    db.refresh(new_appt)

    # API 1: PayMongo session
    pay_res = await paymongo_service.create_checkout_session(
        appointment_code=appt_code,
        amount=consultation_fee,
        patient_name=current_user.full_name,
        patient_email=current_user.email,
        doctor_name=doctor.user.full_name,
        success_url=f"{settings.APP_URL}/patient/appointments/{new_appt.id}",
        cancel_url=f"{settings.APP_URL}/patient/appointments/{new_appt.id}"
    )

    payment = Payment(
        appointment_id=new_appt.id,
        paymongo_checkout_id=pay_res.get("id"),
        paymongo_checkout_url=pay_res.get("checkout_url"),
        amount=consultation_fee,
        status=PaymentStatus.PENDING
    )
    db.add(payment)
    db.commit()

    # API 2: Semaphore SMS
    await semaphore_service.send_sms(
        recipient_phone=current_user.phone_number or "09171234567",
        message=f"CareSync: Appointment {appt_code} created with Dr. {doctor.user.full_name}. Fee: PHP {consultation_fee:,.2f}.",
        recipient_name=current_user.full_name,
        db=db
    )

    return new_appt

@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment_api(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if current_user.role == UserRole.PATIENT and appointment.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return appointment

@router.patch("/appointments/{appointment_id}/status", response_model=AppointmentResponse)
async def update_appointment_status_api(
    appointment_id: int,
    data: AppointmentUpdateStatus,
    current_user: User = Depends(require_roles(UserRole.DOCTOR, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.status = data.status
    if data.doctor_diagnosis:
        appointment.doctor_diagnosis = data.doctor_diagnosis
    if data.doctor_prescription:
        appointment.doctor_prescription = data.doctor_prescription

    db.commit()
    db.refresh(appointment)

    # API 2: Semaphore SMS
    await semaphore_service.send_sms(
        recipient_phone=appointment.patient.phone_number or "09171234567",
        message=f"CareSync Appt {appointment.appointment_code} status updated to {data.status.value}.",
        recipient_name=appointment.patient.full_name,
        db=db
    )

    return appointment

@router.post("/sms/send")
async def send_sms_api(
    number: str,
    message: str,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    res = await semaphore_service.send_sms(
        recipient_phone=number,
        message=message,
        recipient_name="API Dispatch",
        db=db
    )
    return res

@router.get("/sms/logs", response_model=List[SmsLogResponse])
async def get_sms_logs_api(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    return db.query(SmsLog).order_by(SmsLog.sent_at.desc()).limit(50).all()
