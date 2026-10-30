import enum
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean, 
    DateTime, Date, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from app.database import Base

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    DOCTOR = "DOCTOR"
    PATIENT = "PATIENT"

class AppointmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"

class PaymentStatus(str, enum.Enum):
    UNPAID = "UNPAID"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(150), nullable=False)
    phone_number = Column(String(50), nullable=True)
    role = Column(SAEnum(UserRole), default=UserRole.PATIENT, nullable=False)
    avatar_url = Column(String(500), nullable=True)
    google_id = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    doctor_profile = relationship("DoctorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    appointments_as_patient = relationship("Appointment", back_populates="patient", foreign_keys="Appointment.patient_id")
    medical_records = relationship("MedicalRecord", back_populates="patient", cascade="all, delete-orphan")

    @property
    def display_avatar_url(self) -> str:
        if not self.avatar_url:
            return ""
        url = self.avatar_url
        for prefix in ("http://127.0.0.1:8000", "http://localhost:8000"):
            if url.startswith(prefix):
                return url[len(prefix):]
        return url

class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    specialization = Column(String(100), nullable=False)
    license_number = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    consultation_fee = Column(Float, default=500.0)
    clinic_room = Column(String(50), default="Room 101")
    schedule_days = Column(String(150), default="Monday to Friday")
    schedule_hours = Column(String(100), default="09:00 AM - 05:00 PM")
    is_available = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="doctor_profile")
    appointments = relationship("Appointment", back_populates="doctor", cascade="all, delete-orphan")

class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    category = Column(String(100), default="General")
    description = Column(Text, nullable=True)
    base_price = Column(Float, default=500.0)
    duration_minutes = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)

    appointments = relationship("Appointment", back_populates="service")

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    appointment_code = Column(String(30), unique=True, index=True, nullable=False)
    patient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="SET NULL"), nullable=True)
    appointment_date = Column(Date, nullable=False)
    appointment_time = Column(String(20), nullable=False)
    status = Column(SAEnum(AppointmentStatus), default=AppointmentStatus.PENDING, nullable=False)
    payment_status = Column(SAEnum(PaymentStatus), default=PaymentStatus.UNPAID, nullable=False)
    consultation_fee = Column(Float, default=500.0)
    patient_notes = Column(Text, nullable=True)
    doctor_diagnosis = Column(Text, nullable=True)
    doctor_prescription = Column(Text, nullable=True)
    
    # API 3: Google Calendar integration fields
    google_calendar_event_id = Column(String(255), nullable=True)
    google_calendar_link = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship("User", back_populates="appointments_as_patient", foreign_keys=[patient_id])
    doctor = relationship("DoctorProfile", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    payment = relationship("Payment", back_populates="appointment", uselist=False, cascade="all, delete-orphan")
    medical_records = relationship("MedicalRecord", back_populates="appointment")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # API 1: PayMongo fields
    paymongo_checkout_id = Column(String(255), nullable=True)
    paymongo_checkout_url = Column(String(500), nullable=True)
    paymongo_payment_id = Column(String(255), nullable=True)
    
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="PHP")
    status = Column(SAEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    payment_method = Column(String(50), default="paymongo")
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    appointment = relationship("Appointment", back_populates="payment")

class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(200), nullable=False)
    document_type = Column(String(100), default="Lab Result")
    
    # API 5: Cloudinary storage fields
    file_url = Column(String(500), nullable=False)
    cloudinary_public_id = Column(String(255), nullable=True)
    file_format = Column(String(50), nullable=True)
    
    notes = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("User", back_populates="medical_records")
    appointment = relationship("Appointment", back_populates="medical_records")

    @property
    def display_file_url(self) -> str:
        if not self.file_url:
            return ""
        url = self.file_url
        for prefix in ("http://127.0.0.1:8000", "http://localhost:8000"):
            if url.startswith(prefix):
                return url[len(prefix):]
        return url

    @property
    def is_image(self) -> bool:
        fmt = (self.file_format or "").lower()
        if fmt in ("jpg", "jpeg", "png", "webp", "gif", "svg"):
            return True
        url = (self.file_url or "").lower()
        return any(url.endswith(f".{ext}") for ext in ("jpg", "jpeg", "png", "webp", "gif", "svg"))

    @property
    def is_pdf(self) -> bool:
        fmt = (self.file_format or "").lower()
        url = (self.file_url or "").lower()
        return fmt == "pdf" or url.endswith(".pdf")

class SmsLog(Base):
    __tablename__ = "sms_logs"

    id = Column(Integer, primary_key=True, index=True)
    recipient_phone = Column(String(50), nullable=False)
    recipient_name = Column(String(150), nullable=True)
    message = Column(Text, nullable=False)
    
    # API 2: Semaphore SMS tracking
    provider = Column(String(50), default="Semaphore")
    status = Column(String(50), default="SENT")
    message_id = Column(String(100), nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
