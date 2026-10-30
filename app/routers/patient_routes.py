from pathlib import Path
import random
import uuid
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import (
    User, UserRole, DoctorProfile, Service,
    Appointment, AppointmentStatus, Payment, PaymentStatus, MedicalRecord, SmsLog
)
from app.auth import get_current_user, require_roles
from app.services.paymongo_service import paymongo_service
from app.services.semaphore_service import semaphore_service
from app.services.google_calendar_service import google_calendar_service
from app.services.cloudinary_service import cloudinary_service

router = APIRouter(prefix="/patient", tags=["Patient Portal"])
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/dashboard", response_class=HTMLResponse)
async def patient_dashboard(
    request: Request,
    current_user: User = Depends(require_roles(UserRole.PATIENT, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    appointments = (
        db.query(Appointment)
        .filter(Appointment.patient_id == current_user.id)
        .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc())
        .all()
    )
    records = (
        db.query(MedicalRecord)
        .filter(MedicalRecord.patient_id == current_user.id)
        .order_by(MedicalRecord.uploaded_at.desc())
        .all()
    )

    total_booked = len(appointments)
    total_completed = sum(1 for a in appointments if a.status == AppointmentStatus.COMPLETED)
    total_paid = sum(a.consultation_fee for a in appointments if a.payment_status == PaymentStatus.PAID)

    return templates.TemplateResponse(
        request=request,
        name="patient/dashboard.html",
        context={
            "current_user": current_user,
            "appointments": appointments,
            "records": records,
            "total_booked": total_booked,
            "total_completed": total_completed,
            "total_paid": total_paid,
            "settings": settings
        }
    )

@router.get("/book", response_class=HTMLResponse)
async def book_appointment_page(
    request: Request,
    doctor_id: int = None,
    current_user: User = Depends(require_roles(UserRole.PATIENT, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    doctors = db.query(DoctorProfile).filter(DoctorProfile.is_available == True).all()
    services = db.query(Service).filter(Service.is_active == True).all()

    return templates.TemplateResponse(
        request=request,
        name="patient/book_appointment.html",
        context={
            "current_user": current_user,
            "doctors": doctors,
            "services": services,
            "selected_doctor_id": doctor_id,
            "today": date.today().isoformat(),
            "settings": settings
        }
    )

@router.post("/book")
async def book_appointment_submit(
    request: Request,
    doctor_id: int = Form(...),
    service_id: int = Form(None),
    appointment_date: str = Form(...),
    appointment_time: str = Form(...),
    patient_notes: str = Form(""),
    current_user: User = Depends(require_roles(UserRole.PATIENT, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    doctor = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    service = None
    consultation_fee = doctor.consultation_fee
    if service_id:
        service = db.query(Service).filter(Service.id == service_id).first()
        if service:
            consultation_fee = service.base_price

    parsed_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
    appt_code = f"CS-{date.today().year}-{random.randint(1000, 9999)}"

    # Google Calendar link (API 3)
    calendar_link = google_calendar_service.generate_calendar_link(
        appointment_code=appt_code,
        doctor_name=doctor.user.full_name,
        specialization=doctor.specialization,
        appointment_date=parsed_date,
        appointment_time=appointment_time,
        clinic_room=doctor.clinic_room,
        patient_notes=patient_notes
    )

    appointment = Appointment(
        appointment_code=appt_code,
        patient_id=current_user.id,
        doctor_id=doctor.id,
        service_id=service.id if service else None,
        appointment_date=parsed_date,
        appointment_time=appointment_time,
        status=AppointmentStatus.PENDING,
        payment_status=PaymentStatus.UNPAID,
        consultation_fee=consultation_fee,
        patient_notes=patient_notes,
        google_calendar_link=calendar_link,
        google_calendar_event_id=f"evt_{appt_code.lower()}"
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    # API 1: Generate PayMongo Checkout Session
    paymongo_res = await paymongo_service.create_checkout_session(
        appointment_code=appt_code,
        amount=consultation_fee,
        patient_name=current_user.full_name,
        patient_email=current_user.email,
        doctor_name=doctor.user.full_name,
        success_url=f"{settings.APP_URL}/patient/appointments/{appointment.id}",
        cancel_url=f"{settings.APP_URL}/patient/appointments/{appointment.id}"
    )

    payment = Payment(
        appointment_id=appointment.id,
        paymongo_checkout_id=paymongo_res.get("id"),
        paymongo_checkout_url=paymongo_res.get("checkout_url"),
        amount=consultation_fee,
        currency="PHP",
        status=PaymentStatus.PENDING,
        payment_method="paymongo"
    )
    db.add(payment)
    db.commit()

    # API 2: Dispatch Semaphore SMS notification
    sms_message = (
        f"Hi {current_user.full_name}, your CareSync clinic appointment {appt_code} "
        f"with Dr. {doctor.user.full_name} ({doctor.specialization}) on {appointment_date} at {appointment_time} "
        f"is received! Consultation Fee: PHP {consultation_fee:,.2f}. Thank you!"
    )
    await semaphore_service.send_sms(
        recipient_phone=current_user.phone_number or "09171234567",
        message=sms_message,
        recipient_name=current_user.full_name,
        db=db
    )

    return RedirectResponse(
        url=f"/patient/appointments/{appointment.id}?booked=true",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.get("/appointments/{appointment_id}", response_class=HTMLResponse)
async def appointment_detail(
    request: Request,
    appointment_id: int,
    booked: bool = False,
    paid: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Authorize: Patient owner, Doctor owner, or Admin
    if current_user.role == UserRole.PATIENT and appointment.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    if current_user.role == UserRole.DOCTOR and appointment.doctor.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Fetch related SMS logs
    sms_logs = (
        db.query(SmsLog)
        .filter(SmsLog.message.contains(appointment.appointment_code))
        .order_by(SmsLog.sent_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="patient/appointment_detail.html",
        context={
            "current_user": current_user,
            "appointment": appointment,
            "booked": booked,
            "paid": paid,
            "sms_logs": sms_logs,
            "settings": settings
        }
    )

@router.get("/paymongo-simulator", response_class=HTMLResponse)
async def paymongo_simulator_page(
    request: Request,
    code: str = "",
    amount: float = 500.0,
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.appointment_code == code).first()
    return templates.TemplateResponse(
        request=request,
        name="patient/paymongo_simulator.html",
        context={
            "appointment": appointment,
            "code": code,
            "amount": amount,
            "settings": settings
        }
    )

@router.post("/paymongo-simulator/confirm")
async def paymongo_simulator_confirm(
    request: Request,
    code: str = Form(...),
    payment_method: str = Form("gcash"),
    reference_number: str = Form(""),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.appointment_code == code).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.payment_status = PaymentStatus.PAID
    appointment.status = AppointmentStatus.CONFIRMED

    if appointment.payment:
        appointment.payment.status = PaymentStatus.PAID
        appointment.payment.payment_method = payment_method
        appointment.payment.paid_at = datetime.utcnow()
        appointment.payment.paymongo_payment_id = reference_number or f"pay_sim_{uuid.uuid4().hex[:10]}"

    db.commit()

    # API 2: Send Semaphore SMS Payment Receipt
    receipt_sms = (
        f"Payment Received! PHP {appointment.consultation_fee:,.2f} for CareSync Appt {appointment.appointment_code} "
        f"via {payment_method.upper()}. Status: CONFIRMED. Doctor: Dr. {appointment.doctor.user.full_name}. Thank you!"
    )
    await semaphore_service.send_sms(
        recipient_phone=appointment.patient.phone_number or "09171234567",
        message=receipt_sms,
        recipient_name=appointment.patient.full_name,
        db=db
    )

    return RedirectResponse(
        url=f"/patient/appointments/{appointment.id}?paid=true",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.get("/records", response_class=HTMLResponse)
async def medical_records_page(
    request: Request,
    current_user: User = Depends(require_roles(UserRole.PATIENT, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    records = (
        db.query(MedicalRecord)
        .filter(MedicalRecord.patient_id == current_user.id)
        .order_by(MedicalRecord.uploaded_at.desc())
        .all()
    )
    appointments = (
        db.query(Appointment)
        .filter(Appointment.patient_id == current_user.id)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="patient/records.html",
        context={
            "current_user": current_user,
            "records": records,
            "appointments": appointments,
            "settings": settings
        }
    )

@router.post("/records/upload")
async def upload_medical_record(
    request: Request,
    title: str = Form(...),
    document_type: str = Form("Lab Result"),
    appointment_id: str = Form(""),
    notes: str = Form(""),
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.PATIENT, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    # API 5: Cloudinary Upload
    upload_res = await cloudinary_service.upload_file(file=file, folder="caresync_medical_records")
    
    parsed_appt_id = int(appointment_id) if appointment_id and appointment_id.isdigit() else None

    record = MedicalRecord(
        patient_id=current_user.id,
        appointment_id=parsed_appt_id,
        title=title.strip(),
        document_type=document_type,
        file_url=upload_res.get("secure_url"),
        cloudinary_public_id=upload_res.get("public_id"),
        file_format=upload_res.get("format"),
        notes=notes.strip() if notes else None
    )
    db.add(record)
    db.commit()

    return RedirectResponse(url="/patient/records?uploaded=true", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/records/{record_id}/delete")
async def delete_medical_record(
    record_id: int,
    current_user: User = Depends(require_roles(UserRole.PATIENT, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    record = db.query(MedicalRecord).filter(MedicalRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if current_user.role != UserRole.ADMIN and record.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    db.delete(record)
    db.commit()
    return RedirectResponse(url="/patient/records?deleted=true", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/appointments/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: int,
    current_user: User = Depends(require_roles(UserRole.PATIENT, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if current_user.role != UserRole.ADMIN and appointment.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    appointment.status = AppointmentStatus.CANCELLED
    db.commit()

    # Semaphore SMS Cancellation Notification
    await semaphore_service.send_sms(
        recipient_phone=appointment.patient.phone_number or "09171234567",
        message=f"Notice: Your CareSync appointment {appointment.appointment_code} has been cancelled.",
        recipient_name=appointment.patient.full_name,
        db=db
    )

    return RedirectResponse(url=f"/patient/appointments/{appointment_id}", status_code=status.HTTP_303_SEE_OTHER)
