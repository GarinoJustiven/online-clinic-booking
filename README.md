# CareSync PH — Online Clinic & Doctor Appointment Booking System

![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red?logo=sqlalchemy)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.4-38B2AC?logo=tailwindcss)
![Status](https://img.shields.io/badge/Status-Complete-brightgreen)

> An individual final-year web application integrating **5 external APIs** into an end-to-end healthcare consultation and appointment booking ecosystem connecting Patients, Doctors, and Clinic Administrators.

---

## 🌟 1. System Overview

**CareSync PH** modernizes the outpatient clinic experience in the Philippines. It allows patients to discover certified medical specialists, schedule consultations, upload clinical lab reports to the cloud, pay booking fees via local e-Wallets (GCash & Maya), sync appointments into their personal Google Calendar, and receive instantaneous SMS alerts.

### User Roles Supported:
1. **Patient (User)**: Browse doctors, select appointment slots, pay via PayMongo, upload medical files (Cloudinary), sync with Google Calendar, receive Semaphore SMS notifications, view doctor prescriptions.
2. **Doctor (Physician)**: Manage consultation queue, review patient medical history and lab reports, update consultation status (Confirm / Complete / Cancel), issue digital prescriptions, configure clinic room and consultation fees.
3. **Clinic Administrator (Admin)**: Executive summary dashboard with real-time revenue analytics (PHP from PayMongo), full CRUD control over physicians, services, and appointments, audit logs for Semaphore SMS and payments, and live 5-API integration monitor.

---

## 🔌 2. The 5 External APIs Integration Matrix

Every external API is purposefully tied to a core clinical business process:

| External API | Clinical Purpose | Sandbox / Live Behavior | Documentation Link |
| :--- | :--- | :--- | :--- |
| **1. PayMongo (Sandbox & Live)** | Consultation fee payment gateway (GCash, Maya, GrabPay, Credit/Debit cards). | When API keys are set, creates live checkout sessions. In sandbox mode, opens the interactive GCash/Maya simulator with real-time payment confirmation and receipt generation. | [PayMongo Docs](https://developers.paymongo.com) |
| **2. Semaphore SMS API** | Instant mobile text message notifications (booking confirmation, payment receipts, appointment reminders, doctor prescription alerts). | Dispatches real SMS through `api.semaphore.co/api/v4/messages`. In sandbox mode, records full delivery logs into the `SmsLog` database table and displays in admin audit trails. | [Semaphore Docs](https://semaphore.co/docs) |
| **3. Google Calendar API** | Calendar scheduling and event synchronization for patients and doctors. | Generates a 1-click universal calendar synchronization link with doctor details, clinic room, and appointment notes. | [Google Calendar API](https://developers.google.com/calendar) |
| **4. Google OAuth 2.0** | Verified social single sign-on (SSO) for patients and physicians. | Standard Google Identity OAuth flow when configured. Includes an interactive Google OAuth Account Chooser for 1-click test evaluations. | [Google OAuth 2.0](https://developers.google.com/identity) |
| **5. Cloudinary API** | Secure cloud storage and delivery for medical documents, lab results, prescriptions, and valid IDs. | Secure multi-part uploads with format validation, thumbnail generation, and secure cloud URLs. Falls back to local `/static/uploads/` if credentials are not specified. | [Cloudinary API](https://cloudinary.com/documentation) |

---

## 🛠️ 3. Core System Architecture & CRUD Modules

```
                           +------------------------------------------+
                           |       CareSync PH Web Application        |
                           |   (FastAPI + Jinja2 + Tailwind CSS)      |
                           +------------------------------------------+
                                  /       |       |       \
                                 /        |       |        \
        +-----------------------+         |       |         +-----------------------+
        |  Role: Patient        |         |       |         |  Role: Doctor         |
        |  - Book appointments  |         |       |         |  - Patient Queue      |
        |  - PayMongo Checkout  |         |       |         |  - Diagnosis & Rx     |
        |  - Cloudinary Uploads |         |       |         |  - Clinic Hours & Fee |
        +-----------------------+         |       |         +-----------------------+
                                          |       |
                                          |       +---------------------------------+
                                          |       |  Role: Clinic Admin             |
                                          |       |  - Executive KPI Summary        |
                                          |       |  - Physicians CRUD              |
                                          |       |  - Clinic Services CRUD         |
                                          |       |  - PayMongo & SMS Audit Logs    |
                                          |       +---------------------------------+
                                          |
                      +---------------------------------------+
                      |         SQLAlchemy ORM Models         |
                      | (Users, Doctors, Services, Appts,     |
                      |  Payments, MedicalRecords, SmsLogs)   |
                      +---------------------------------------+
                                          |
                      +---------------------------------------+
                      |         Database Layer                |
                      |   SQLite (Local) / PostgreSQL (Cloud) |
                      +---------------------------------------+
```

### CRUD Modules Implemented:
1. **Appointments CRUD Module**:
   - **Create**: Patients select doctor, clinic service, date, time slot, and medical symptoms.
   - **Read**: Filterable appointment tables for Patients, Doctors, and Administrators.
   - **Update**: Doctors issue clinical diagnosis, advice, and digital prescriptions; Admins can override schedules and statuses.
   - **Delete / Cancel**: Patients and Admins can cancel scheduled bookings with automatic SMS notice.
2. **Physicians & Specialists CRUD Module (Admin)**:
   - **Create**: Register new doctors with consultation fees, license number, and clinic room.
   - **Read**: List of active specialists with availability badges.
   - **Update**: Edit schedule hours, bio, and clinic room.
   - **Delete**: Cascading removal of doctor records.
3. **Clinic Services CRUD Module (Admin)**:
   - **Create**: Add new consultation packages and lab review services.
   - **Read**: Public and patient catalog with base fees and durations.
   - **Update / Delete**: Manage active clinic offerings.
4. **Medical Records & Cloudinary Documents CRUD Module**:
   - **Create / Upload**: Upload lab results, CBC panels, valid IDs, or prescriptions.
   - **Read**: Instant preview with secure Cloudinary asset links.
   - **Delete**: Remove outdated patient records.

---

## 🚀 4. Step-by-Step Installation & Local Setup

### Prerequisites
- Python 3.10+ (Tested on Python 3.12 / 3.14)
- Git

### 1. Clone the Repository
```bash
git clone <your-repository-url>
cd "Online clinic booking"
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(All 5 APIs include built-in smart sandbox fallbacks, so the system runs immediately even before you add API credentials!)*

### 5. Seed Database with Demo Records
```bash
python seed.py
```

### 6. Start the Server
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open your browser at: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🔑 5. Pre-Configured Demo Accounts for Presentation

Use these accounts to evaluate role-based authorization during testing:

| Role | Email | Password | Access Highlights |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@caresync.ph` | `admin123` | Executive KPI dashboard, revenue analytics, Doctors CRUD, Services CRUD, SMS logs, API monitor |
| **Doctor** | `doctor.santos@caresync.ph` | `doctor123` | Physician queue, patient medical history, clinical diagnosis & prescription issuer |
| **Patient** | `patient.cruz@example.com` | `patient123` | Appointment booking wizard, PayMongo sandbox checkout, Cloudinary document manager |

*Tip: You can also use the **1-Click Preset Buttons** on the Login page and Homepage to switch roles instantly.*

---

## 📊 6. Interactive Swagger API Documentation

FastAPI automatically generates interactive OpenAPI/Swagger documentation.
Once running, navigate to:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc UI**: `http://127.0.0.1:8000/redoc`

---

## ☁️ 7. Free Cloud Deployment (Render / Railway)

### Deploying to Render.com (Free Tier):
1. Push your repository to GitHub or GitLab.
2. Sign in to [Render](https://render.com) and click **New + > Web Service**.
3. Select your repository.
4. Render will automatically detect `render.yaml` or use the following settings:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Click **Deploy Web Service**!

---

## 🧪 8. Automated Unit Testing

Run the included automated test suite:
```bash
python test_app.py
```
*Tests verify homepage rendering, API health checks, system API configuration status, authentication session cookies, patient appointment booking flow, and PayMongo payment confirmation.*

---

## 📜 Academic Integrity Statement
This project was designed, developed, and tested individually as part of the Web Application & Systems Integration coursework.
