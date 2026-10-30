from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from app.models import UserRole, AppointmentStatus, PaymentStatus

# User Schemas
class UserBase(BaseModel):
    email: str
    full_name: str
    phone_number: Optional[str] = None
    role: UserRole = UserRole.PATIENT

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(UserBase):
    id: int
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Doctor Profile Schemas
class DoctorProfileCreate(BaseModel):
    specialization: str
    license_number: Optional[str] = None
    bio: Optional[str] = None
    consultation_fee: float = 500.0
    clinic_room: Optional[str] = "Room 101"
    schedule_days: Optional[str] = "Monday to Friday"
    schedule_hours: Optional[str] = "09:00 AM - 05:00 PM"
    is_available: bool = True

class DoctorProfileResponse(DoctorProfileCreate):
    id: int
    user_id: int
    user: Optional[UserResponse] = None

    class Config:
        from_attributes = True

# Service Schemas
class ServiceCreate(BaseModel):
    name: str
    category: Optional[str] = "General"
    description: Optional[str] = None
    base_price: float = 500.0
    duration_minutes: int = 30
    is_active: bool = True

class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    base_price: Optional[float] = None
    duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None

class ServiceResponse(ServiceCreate):
    id: int

    class Config:
        from_attributes = True

# Appointment Schemas
class AppointmentCreate(BaseModel):
    doctor_id: int
    service_id: Optional[int] = None
    appointment_date: date
    appointment_time: str
    patient_notes: Optional[str] = None

class AppointmentUpdateStatus(BaseModel):
    status: AppointmentStatus
    doctor_diagnosis: Optional[str] = None
    doctor_prescription: Optional[str] = None

class AppointmentReschedule(BaseModel):
    appointment_date: date
    appointment_time: str

class AppointmentResponse(BaseModel):
    id: int
    appointment_code: str
    patient_id: int
    doctor_id: int
    service_id: Optional[int] = None
    appointment_date: date
    appointment_time: str
    status: AppointmentStatus
    payment_status: PaymentStatus
    consultation_fee: float
    patient_notes: Optional[str] = None
    doctor_diagnosis: Optional[str] = None
    doctor_prescription: Optional[str] = None
    google_calendar_link: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Payment Schemas
class PaymentCreate(BaseModel):
    appointment_id: int
    amount: float
    payment_method: Optional[str] = "paymongo"

class PaymentResponse(BaseModel):
    id: int
    appointment_id: int
    paymongo_checkout_url: Optional[str] = None
    amount: float
    currency: str
    status: PaymentStatus
    payment_method: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Medical Record Schemas
class MedicalRecordResponse(BaseModel):
    id: int
    patient_id: int
    appointment_id: Optional[int] = None
    title: str
    document_type: str
    file_url: str
    file_format: Optional[str] = None
    notes: Optional[str] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True

# SMS Log Schemas
class SmsLogResponse(BaseModel):
    id: int
    recipient_phone: str
    recipient_name: Optional[str] = None
    message: str
    provider: str
    status: str
    sent_at: datetime

    class Config:
        from_attributes = True
