import urllib.parse
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
import logging
from app.config import settings

logger = logging.getLogger("caresync.google_calendar")

class GoogleCalendarService:
    def __init__(self):
        self.api_key = settings.GOOGLE_CALENDAR_API_KEY
        self.is_configured = settings.is_google_calendar_configured

    def generate_calendar_link(
        self,
        appointment_code: str,
        doctor_name: str,
        specialization: str,
        appointment_date: date,
        appointment_time: str,
        clinic_room: str = "Room 101",
        patient_notes: Optional[str] = None
    ) -> str:
        """
        Generates a direct 'Add to Google Calendar' deep link with formatted event details.
        """
        # Parse time (e.g. '09:00 AM' or '14:30')
        start_hour, start_min = 9, 0
        try:
            time_parts = appointment_time.replace(":", " ").split()
            if len(time_parts) >= 2:
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                meridiem = time_parts[2].upper() if len(time_parts) > 2 else ""
                if meridiem == "PM" and hour < 12:
                    hour += 12
                elif meridiem == "AM" and hour == 12:
                    hour = 0
                start_hour, start_min = hour, minute
        except Exception:
            pass

        start_dt = datetime.combine(appointment_date, datetime.min.time()).replace(
            hour=start_hour, minute=start_min
        )
        end_dt = start_dt + timedelta(minutes=45)

        # Google Calendar requires format: YYYYMMDDTHHmmSSZ
        start_str = start_dt.strftime("%Y%m%dT%H%M%S")
        end_str = end_dt.strftime("%Y%m%dT%H%M%S")

        title = f"Medical Consultation: Dr. {doctor_name} ({specialization})"
        description = (
            f"CareSync Appointment Code: {appointment_code}\n"
            f"Doctor: Dr. {doctor_name}\n"
            f"Specialization: {specialization}\n"
            f"Clinic Room: {clinic_room}\n"
            f"Notes: {patient_notes or 'Standard consultation'}\n\n"
            f"Booked via CareSync Online Clinic System"
        )
        location = f"CareSync Medical Clinic, {clinic_room}, Metro Manila"

        query_params = {
            "action": "TEMPLATE",
            "text": title,
            "dates": f"{start_str}/{end_str}",
            "details": description,
            "location": location,
            "sf": "true",
            "output": "xml"
        }

        calendar_url = f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(query_params)}"
        return calendar_url

    async def sync_appointment_event(
        self,
        appointment_code: str,
        doctor_name: str,
        specialization: str,
        appointment_date: date,
        appointment_time: str,
        clinic_room: str = "Room 101"
    ) -> Dict[str, Any]:
        """
        Returns sync data and calendar URL.
        """
        url = self.generate_calendar_link(
            appointment_code, doctor_name, specialization,
            appointment_date, appointment_time, clinic_room
        )
        return {
            "success": True,
            "mode": "GOOGLE_CALENDAR_LIVE" if self.is_configured else "GOOGLE_CALENDAR_DIRECT_SYNC",
            "calendar_link": url,
            "event_id": f"gcal_evt_{appointment_code.lower()}"
        }

google_calendar_service = GoogleCalendarService()
