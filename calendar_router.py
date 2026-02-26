from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from datetime import date
import calendar as pycalendar
from typing import List
from db_dependencies import get_db, admin_only, get_current_user
from models import Calendar, DayStatus
from timesheet_models import Timesheet, Leave
from schemas import CalendarResponse, CalendarUpdate, CalendarWithHoursResponse

router = APIRouter(prefix="/calendar", tags=["Calendar"])


# ✅ AUTO GENERATE + SHOW HOURS
@router.get("/month/{year}/{month}", response_model=List[CalendarWithHoursResponse])
def get_calendar_by_month(
    year: int,
    month: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    # 1️⃣ Check if month exists
    existing = db.query(Calendar).filter(
        extract("year", Calendar.date) == year,
        extract("month", Calendar.date) == month
    ).first()

    # 2️⃣ If not → generate full month
    if not existing:
        total_days = pycalendar.monthrange(year, month)[1]

        for day in range(1, total_days + 1):
            current_date = date(year, month, day)

            if current_date.weekday() == 6:  # Sunday
                status = DayStatus.leave
            else:
                status = DayStatus.normal

            new_day = Calendar(
                date=current_date,
                status=status
            )

            db.add(new_day)

        db.commit()

    # 3️⃣ Fetch calendar with working hours
    results = (
        db.query(
            Calendar.id,
            Calendar.date,
            Calendar.status,
            (func.coalesce(func.sum(Timesheet.total_hours), 0) ).label("total_hours")
        )
        .outerjoin(
            Timesheet,
            (Calendar.date == Timesheet.submitted_date) &
            (Timesheet.user_id == current_user.id)
        )
        .filter(
            extract("year", Calendar.date) == year,
            extract("month", Calendar.date) == month
        )
        .group_by(Calendar.id)
        .order_by(Calendar.date)
        .all()
    )

    return results


# ✅ Admin update day status
@router.put("/{calendar_id}", response_model=CalendarResponse)
def update_calendar(
    calendar_id: int,
    update_data: CalendarUpdate,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    calendar = db.query(Calendar).filter(Calendar.id == calendar_id).first()

    if not calendar:
        raise HTTPException(status_code=404, detail="Date not found")

    calendar.status = update_data.status
    db.commit()
    db.refresh(calendar)

    return calendar



# ✅ Public holidays
@router.get("/public-holidays", response_model=List[CalendarResponse])
def get_public_holidays(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return db.query(Calendar).filter(
        Calendar.status == DayStatus.publicholiday
    ).order_by(Calendar.date).all()


from datetime import datetime, timedelta
@router.get("/date-range")
def get_month_data(
    month: int,
    year: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    from datetime import datetime, timedelta, date
    import calendar

    # ✅ Get first and last date of month
    start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = date(year, month, last_day)

    # Fetch all timesheets in selected month
    timesheets = db.query(Timesheet).filter(
        Timesheet.user_id == current_user.id,
        Timesheet.submitted_date >= start,
        Timesheet.submitted_date <= end
    ).all()

    timesheet_map = {t.submitted_date: t for t in timesheets}

    response = {
        "date": {},
        "weekly_hours": 0
    }

    # ✅ Current week Monday–Friday calculation (same logic)
    today = datetime.today().date()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=4)             # Friday

    current_week_total = 0
    current = start

    while current <= end:

        # 🔹 Check if approved leave exists
        approved_leave = db.query(Leave).filter(
            Leave.user_id == current_user.id,
            Leave.status == "approved",
            Leave.start_date <= current,
            Leave.end_date >= current
        ).first()

        # 🔹 Get calendar status
        calendar_day = db.query(Calendar).filter(
            Calendar.date == current
        ).first()

        if approved_leave:
            status = "leave"
        else:
            status = calendar_day.status if calendar_day else "normal"

        # 🔹 If timesheet exists
        if current in timesheet_map:
            ts = timesheet_map[current]
            daily_hours = round(ts.total_hours, 2)

            activities = [
                {
                    "project_name": a.get("project_name"),
                    "task_category": a.get("task_category"),
                    "start_time": a.get("start_time"),
                    "end_time": a.get("end_time"),
                    "hours": round(float(a.get("hours", 0)), 2)
                }
                for a in ts.activities
            ]
        else:
            daily_hours = 0
            activities = []

        # ✅ Count only current week Monday–Friday (same as your logic)
        if week_start <= current <= week_end:
            current_week_total += daily_hours

        response["date"][current.strftime("%d-%m-%Y")] = {
            "status": status,
            "hours": daily_hours,
            "logged_activities": activities
        }

        current += timedelta(days=1)

    response["weekly_hours"] = round(current_week_total, 2)

    return response

