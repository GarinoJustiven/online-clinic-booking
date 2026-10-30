import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.database import engine, Base, get_db
from app.models import DoctorProfile, Service
from app.auth import get_optional_current_user
from app.routers import auth_routes, patient_routes, doctor_routes, admin_routes, api_routes
from seed import seed_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("caresync")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables and seed initial data if needed
    logger.info("Initializing CareSync PH database and models...")
    Base.metadata.create_all(bind=engine)
    try:
        seed_database()
    except Exception as e:
        logger.error(f"Seeding error (non-fatal): {e}")
    yield
    logger.info("CareSync PH shutdown.")

app = FastAPI(
    title="CareSync PH - Online Clinic Booking System",
    description="Online Clinic & Doctor Appointment Booking Web Application integrating 5 External APIs (PayMongo Sandbox, Semaphore SMS, Google Calendar, Google OAuth, and Cloudinary).",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files Mount
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Mount Routers
app.include_router(auth_routes.router)
app.include_router(patient_routes.router)
app.include_router(doctor_routes.router)
app.include_router(admin_routes.router)
app.include_router(api_routes.router)

@app.get("/", response_class=HTMLResponse)
async def home_page(
    request: Request,
    current_user = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    doctors = db.query(DoctorProfile).filter(DoctorProfile.is_available == True).all()
    services = db.query(Service).filter(Service.is_active == True).all()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "current_user": current_user,
            "doctors": doctors,
            "services": services,
            "settings": settings
        }
    )
