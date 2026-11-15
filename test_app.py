import unittest
import threading
import time
import httpx
import uvicorn
from app.main import app
from app.models import Appointment, SmsLog, User
from app.database import SessionLocal

class ServerThread(threading.Thread):
    def __init__(self, app, host="127.0.0.1", port=8009):
        super().__init__(daemon=True)
        self.server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True

class TestCareSyncSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_thread = ServerThread(app, port=8009)
        cls.server_thread.start()
        time.sleep(2)
        cls.client = httpx.Client(base_url="http://127.0.0.1:8009", timeout=10.0, follow_redirects=False)
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.db.close()
        cls.server_thread.stop()

    def test_01_homepage_renders(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("CareSync", res.text)
        self.assertIn("Healthcare Booking", res.text)
        self.assertIn("Appoint Now", res.text)

    def test_02_health_api(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")

    def test_03_5_api_system_status(self):
        res = self.client.get("/api/system/status")
        self.assertEqual(res.status_code, 200)
        apis = res.json()["apis"]
        self.assertIn("paymongo", apis)
        self.assertIn("semaphore", apis)
        self.assertIn("google_calendar", apis)
        self.assertIn("google_oauth", apis)
        self.assertIn("cloudinary", apis)

    def test_04_auth_login_admin(self):
        res = self.client.post("/login", data={"email": "admin@caresync.ph", "password": "admin123"})
        self.assertEqual(res.status_code, 303)
        self.assertIn("access_token", res.cookies)

    def test_05_google_oauth_mock_flow(self):
        res = self.client.get("/auth/google/callback?mock_email=test.patient@example.com&mock_name=Test+Patient&mock_role=PATIENT")
        self.assertEqual(res.status_code, 303)
        self.assertIn("access_token", res.cookies)

    def test_06_patient_booking_and_sms(self):
        login_res = self.client.post("/login", data={"email": "patient.cruz@example.com", "password": "patient123"})
        cookies = login_res.cookies

        book_res = self.client.post(
            "/patient/book",
            data={
                "doctor_id": 1,
                "service_id": 1,
                "appointment_date": "2026-11-05",
                "appointment_time": "10:00 AM",
                "patient_notes": "Unit test booking note"
            },
            cookies=cookies
        )
        self.assertEqual(book_res.status_code, 303)
        self.assertEqual(book_res.headers.get("location"), "/patient/dashboard?booked=true")

        recent_sms = self.db.query(SmsLog).order_by(SmsLog.sent_at.desc()).first()
        self.assertIsNotNone(recent_sms)

    def test_07_paymongo_payment_confirmation(self):
        appt = self.db.query(Appointment).first()
        self.assertIsNotNone(appt)

        res = self.client.post(
            "/patient/paymongo-simulator/confirm",
            data={
                "code": appt.appointment_code,
                "payment_method": "gcash",
                "reference_number": "test_ref_12345"
            }
        )
        self.assertEqual(res.status_code, 303)

    def test_08_patient_only_registration(self):
        test_email = "new.patient.test@example.com"
        # Cleanup if existed
        existing = self.db.query(User).filter(User.email == test_email).first()
        if existing:
            self.db.delete(existing)
            self.db.commit()

        res = self.client.post(
            "/register",
            data={
                "full_name": "New Registered Patient",
                "email": test_email,
                "phone_number": "09171112233",
                "password": "securepassword123",
                "confirm_password": "securepassword123"
            }
        )
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers.get("location"), "/patient/dashboard")

        # Verify created in DB strictly with PATIENT role
        user = self.db.query(User).filter(User.email == test_email).first()
        self.assertIsNotNone(user)
        self.assertEqual(user.role.value, "PATIENT")

    def test_09_medical_record_upload_security(self):
        login_res = self.client.post("/login", data={"email": "patient.cruz@example.com", "password": "patient123"})
        cookies = login_res.cookies

        # Valid document upload (PDF)
        files = {"file": ("test_report.pdf", b"%PDF-1.4 sample content", "application/pdf")}
        res = self.client.post(
            "/patient/records/upload",
            data={"title": "Lab Blood Chemistry", "document_type": "Lab Result", "notes": "Test upload"},
            files=files,
            cookies=cookies
        )
        self.assertEqual(res.status_code, 303)
        self.assertIn("uploaded=true", res.headers.get("location", ""))

        # Invalid extension blocked (e.g. .exe)
        invalid_files = {"file": ("malicious.exe", b"binary content", "application/x-msdownload")}
        res_invalid = self.client.post(
            "/patient/records/upload",
            data={"title": "Malicious File", "document_type": "Lab Result"},
            files=invalid_files,
            cookies=cookies
        )
        self.assertEqual(res_invalid.status_code, 303)
        self.assertIn("error=", res_invalid.headers.get("location", ""))

if __name__ == "__main__":
    unittest.main()
