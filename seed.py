import sys
from datetime import date, datetime, timedelta
from app.database import engine, Base, SessionLocal
from app.models import (
    User, UserRole, DoctorProfile, Service,
    Appointment, AppointmentStatus, Payment, PaymentStatus, MedicalRecord, SmsLog
)
from app.auth import get_password_hash
from app.services.google_calendar_service import google_calendar_service

def seed_database():
    print("Initializing CareSync database tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(User).filter(User.email == "admin@caresync.ph").first():
            print("Database already contains seed data. Skipping.")
            return

        print("Seeding Users...")
        # 1. Admin
        admin = User(
            email="admin@caresync.ph",
            hashed_password=get_password_hash("admin123"),
            full_name="Admin Clinic Manager",
            phone_number="09171234567",
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)

        # 2. Doctors
        doc1_user = User(
            email="doctor.santos@caresync.ph",
            hashed_password=get_password_hash("doctor123"),
            full_name="Maria Santos, MD",
            phone_number="09181234567",
            role=UserRole.DOCTOR,
            avatar_url="https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=150&auto=format&fit=crop",
            is_active=True
        )
        doc2_user = User(
            email="doctor.ramirez@caresync.ph",
            hashed_password=get_password_hash("doctor123"),
            full_name="Andrea Ramirez, MD",
            phone_number="09191234567",
            role=UserRole.DOCTOR,
            avatar_url="https://images.unsplash.com/photo-1622253692010-333f2da6031d?w=150&auto=format&fit=crop",
            is_active=True
        )
        doc3_user = User(
            email="doctor.cruz@caresync.ph",
            hashed_password=get_password_hash("doctor123"),
            full_name="Gabriel Cruz, MD",
            phone_number="09201234567",
            role=UserRole.DOCTOR,
            avatar_url="https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?w=150&auto=format&fit=crop",
            is_active=True
        )
        db.add_all([doc1_user, doc2_user, doc3_user])

        # 3. Patients
        patient1 = User(
            email="patient.cruz@example.com",
            hashed_password=get_password_hash("patient123"),
            full_name="Juan Dela Cruz",
            phone_number="09179876543",
            role=UserRole.PATIENT,
            avatar_url="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop",
            is_active=True
        )
        patient2 = User(
            email="patient.reyes@example.com",
            hashed_password=get_password_hash("patient123"),
            full_name="Ana Reyes",
            phone_number="09175551234",
            role=UserRole.PATIENT,
            is_active=True
        )
        db.add_all([patient1, patient2])
        db.commit()

        # Doctor Profiles
        print("Seeding Doctor Profiles...")
        doc1_profile = DoctorProfile(
            user_id=doc1_user.id,
            specialization="General Medicine",
            license_number="PRC-0198421",
            bio="Experienced family physician specializing in preventive health and chronic disease management.",
            consultation_fee=500.0,
            clinic_room="Room 101, Main Wing",
            schedule_days="Monday to Friday",
            schedule_hours="09:00 AM - 05:00 PM",
            is_available=True
        )
        doc2_profile = DoctorProfile(
            user_id=doc2_user.id,
            specialization="Cardiology",
            license_number="PRC-0294102",
            bio="Board-certified cardiologist focused on hypertension, echocardiography, and heart health.",
            consultation_fee=850.0,
            clinic_room="Room 205, Specialty Wing",
            schedule_days="Tuesday, Thursday, Saturday",
            schedule_hours="10:00 AM - 04:00 PM",
            is_available=True
        )
        doc3_profile = DoctorProfile(
            user_id=doc3_user.id,
            specialization="Pediatrics",
            license_number="PRC-0319401",
            bio="Compassionate pediatrician dedicated to child development, newborn care, and vaccinations.",
            consultation_fee=600.0,
            clinic_room="Room 108, Pediatric Care",
            schedule_days="Monday to Saturday",
            schedule_hours="08:30 AM - 03:30 PM",
            is_available=True
        )
        db.add_all([doc1_profile, doc2_profile, doc3_profile])
        db.commit()

        # Clinic Services
        print("Seeding Clinic Services...")
        srv1 = Service(
            name="General Medical Consultation",
            category="General Practice",
            description="Comprehensive consultation including vitals check, clinical exam, and prescription.",
            base_price=500.0,
            duration_minutes=30
        )
        srv2 = Service(
            name="Comprehensive Cardiac Screening",
            category="Cardiology",
            description="Cardiovascular assessment, ECG review, and lifestyle recommendations.",
            base_price=850.0,
            duration_minutes=45
        )
        srv3 = Service(
            name="Pediatric Wellness & Developmental Exam",
            category="Pediatrics",
            description="Child growth tracking, developmental milestones, and immunization assessment.",
            base_price=600.0,
            duration_minutes=30
        )
        srv4 = Service(
            name="Dermatology & Skin Checkup",
            category="Dermatology",
            description="Skin evaluation for allergies, acne, rashes, and suspicious lesions.",
            base_price=700.0,
            duration_minutes=30
        )
        db.add_all([srv1, srv2, srv3, srv4])
        db.commit()

        # Sample Appointments
        print("Seeding Sample Appointments...")
        today = date.today()
        
        # Appointment 1 (Confirmed & Paid)
        appt1_code = f"CS-{today.year}-1001"
        link1 = google_calendar_service.generate_calendar_link(
            appt1_code, doc1_user.full_name, doc1_profile.specialization,
            today, "09:00 AM", doc1_profile.clinic_room
        )
        appt1 = Appointment(
            appointment_code=appt1_code,
            patient_id=patient1.id,
            doctor_id=doc1_profile.id,
            service_id=srv1.id,
            appointment_date=today,
            appointment_time="09:00 AM",
            status=AppointmentStatus.CONFIRMED,
            payment_status=PaymentStatus.PAID,
            consultation_fee=500.0,
            patient_notes="Annual physical checkup and mild cough.",
            doctor_diagnosis="Mild Upper Respiratory Tract Infection (URTI).",
            doctor_prescription="Rx:\n1. Paracetamol 500mg - 1 tab every 6h as needed\n2. Vitamin C with Zinc - 1 cap daily",
            google_calendar_link=link1
        )
        db.add(appt1)
        db.commit()
        db.refresh(appt1)

        pay1 = Payment(
            appointment_id=appt1.id,
            paymongo_payment_id="pay_pm_gcash_live_sample001",
            amount=500.0,
            currency="PHP",
            status=PaymentStatus.PAID,
            payment_method="gcash",
            paid_at=datetime.utcnow()
        )
        db.add(pay1)

        # Appointment 2 (Pending & Unpaid)
        appt2_code = f"CS-{today.year}-1002"
        tomorrow = today + timedelta(days=1)
        link2 = google_calendar_service.generate_calendar_link(
            appt2_code, doc2_user.full_name, doc2_profile.specialization,
            tomorrow, "10:00 AM", doc2_profile.clinic_room
        )
        appt2 = Appointment(
            appointment_code=appt2_code,
            patient_id=patient1.id,
            doctor_id=doc2_profile.id,
            service_id=srv2.id,
            appointment_date=tomorrow,
            appointment_time="10:00 AM",
            status=AppointmentStatus.PENDING,
            payment_status=PaymentStatus.UNPAID,
            consultation_fee=850.0,
            patient_notes="Occasional heart palpitations after exercise.",
            google_calendar_link=link2
        )
        db.add(appt2)
        db.commit()
        db.refresh(appt2)

        pay2 = Payment(
            appointment_id=appt2.id,
            amount=850.0,
            currency="PHP",
            status=PaymentStatus.PENDING,
            payment_method="paymongo"
        )
        db.add(pay2)

        # Sample Medical Records (Cloudinary)
        print("Seeding Medical Records (Cloudinary)...")
        rec1 = MedicalRecord(
            patient_id=patient1.id,
            appointment_id=appt1.id,
            title="Complete Blood Count (CBC) Lab Panel",
            document_type="Lab Result",
            file_url="https://res.cloudinary.com/demo/image/upload/sample.jpg",
            cloudinary_public_id="sample_cbc_panel",
            file_format="jpg",
            notes="Normal white blood cell count and hemoglobin."
        )
        rec2 = MedicalRecord(
            patient_id=patient1.id,
            appointment_id=appt1.id,
            title="Chest X-Ray Digital Scan",
            document_type="Imaging / X-Ray",
            file_url="https://res.cloudinary.com/demo/image/upload/sample.jpg",
            cloudinary_public_id="sample_chest_xray",
            file_format="jpg",
            notes="Clear lung fields. No active cardiopulmonary disease."
        )
        db.add_all([rec1, rec2])

        # Sample Semaphore SMS Logs
        print("Seeding Semaphore SMS Logs...")
        sms1 = SmsLog(
            recipient_phone="09179876543",
            recipient_name="Juan Dela Cruz",
            message=f"Hi Juan Dela Cruz, your CareSync appointment {appt1_code} with Dr. Maria Santos, MD on {today} at 09:00 AM is received! Thank you!",
            provider="Semaphore (Sandbox Mock)",
            status="SENT",
            message_id="smph_sim_849201"
        )
        sms2 = SmsLog(
            recipient_phone="09179876543",
            recipient_name="Juan Dela Cruz",
            message=f"Payment Received! PHP 500.00 for CareSync Appt {appt1_code} via GCASH. Status: CONFIRMED. Dr. Maria Santos, MD. Thank you!",
            provider="Semaphore (Sandbox Mock)",
            status="SENT",
            message_id="smph_sim_849202"
        )
        db.add_all([sms1, sms2])
        db.commit()

        print("Database seeded successfully with Admin, Doctors, Patients, Services, and Appointments!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
