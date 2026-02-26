from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date
from db_dependencies import get_db, get_current_user
from models import User
from timesheet_models import DraftTimesheet, Timesheet, Leave
from timesheet_schemas import TimesheetCreate, LeaveApply, LeaveStatusUpdate
router = APIRouter(prefix="/timesheet", tags=["Timesheet"])


# ------------------ HELPERS ------------------

def calculate_hours(start, end, break_minutes):
    total_minutes = (
        (datetime.combine(datetime.today(), end) -
         datetime.combine(datetime.today(), start)).seconds
    ) // 60

    worked_minutes = total_minutes - break_minutes

    if worked_minutes <= 0:
        raise HTTPException(status_code=400, detail="Invalid time calculation")

    return round(worked_minutes / 60, 2)


def get_db_user(db: Session, token_user: dict):
    email = token_user.email
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")

    db_user = db.query(User).filter(User.email == email).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    return db_user


# ============================================================
# CREATE OR UPDATE DRAFT (STRICT ONE PER DAY)
# ============================================================
@router.post("/draft")
def create_draft(
    data: TimesheetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    today = date.today()

    # 🔴 Check if already submitted
    already_submitted = db.query(Timesheet).filter(
        Timesheet.user_id == current_user.id,
        Timesheet.submitted_date == today
    ).first()

    if already_submitted:
        raise HTTPException(
            status_code=400,
            detail="Timesheet already submitted for this date"
        )

    # 🔴 Limit 5 drafts per day
    draft_count = db.query(DraftTimesheet).filter(
        DraftTimesheet.user_id == current_user.id,
        DraftTimesheet.work_date == today
    ).count()

    if draft_count >= 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum 5 drafts allowed per day"
        )

    calculated_hours = calculate_hours(
        data.start_time,
        data.end_time,
        data.break_time
    )

    draft = DraftTimesheet(
        user_id=current_user.id,
        project_name=data.project_name,
        task_name=data.task_name,
        work_date=today,
        start_time=data.start_time,
        end_time=data.end_time,
        break_time=data.break_time,
        hours=calculated_hours
    )

    db.add(draft)
    db.commit()
    db.refresh(draft)

    return draft



@router.post("/update/{draft_id}") #update
def update_draft(
    draft_id: int,
    data: TimesheetCreate,
    db: Session = Depends(get_db),
    token_user=Depends(get_current_user)
):
    db_user = get_db_user(db, token_user)

    draft = db.query(DraftTimesheet).filter(
        DraftTimesheet.id == draft_id,
        DraftTimesheet.user_id == db_user.id
    ).first()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    calculated_hours = calculate_hours(
        data.start_time,
        data.end_time,
        data.break_time
    )

    draft.project_name = data.project_name
    draft.task_name = data.task_name
    draft.start_time = data.start_time
    draft.end_time = data.end_time
    draft.break_time = data.break_time
    draft.hours = calculated_hours

    db.commit()
    db.refresh(draft)

    return {"message": "Draft updated successfully"}

@router.post("/delete/{draft_id}") #delete
def delete_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    token_user=Depends(get_current_user)
):
    db_user = get_db_user(db, token_user)

    draft = db.query(DraftTimesheet).filter(
        DraftTimesheet.id == draft_id,
        DraftTimesheet.user_id == db_user.id
    ).first()

    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    db.delete(draft)
    db.commit()

    return {"message": "Draft deleted successfully"}

@router.post("/draft/{work_date}") #get 
def get_drafts_by_date(
    work_date: date,
    db: Session = Depends(get_db),
    token_user=Depends(get_current_user)
):
    db_user = get_db_user(db, token_user)

    drafts = db.query(DraftTimesheet).filter(
        DraftTimesheet.user_id == db_user.id,
        DraftTimesheet.work_date == work_date
    ).all()

    return drafts

@router.post("/submit")
def submit_timesheet(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    today = date.today()

    drafts = db.query(DraftTimesheet).filter(
        DraftTimesheet.user_id == current_user.id,
        DraftTimesheet.work_date == today
    ).all()

    if not drafts:
        raise HTTPException(
            status_code=400,
            detail="No drafts found for today"
        )

    # Check if already submitted
    existing = db.query(Timesheet).filter(
        Timesheet.user_id == current_user.id,
        Timesheet.submitted_date == today
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Timesheet already submitted for today"
        )

    total_hours = round(sum(d.hours for d in drafts), 2)

    activities = []

    for d in drafts:
        activities.append({
            "project_name": d.project_name,
            "task_name": d.task_name,
            "start_time": str(d.start_time),
            "end_time": str(d.end_time),
            "break_minutes": d.break_time,
            "hours": d.hours
        })

    timesheet = Timesheet(
        user_id=current_user.id,
        submitted_date=today,
        total_hours=total_hours,
        activities=activities
    )

    db.add(timesheet)

    db.commit()

    return {
        "message": "Timesheet submitted successfully",
        "total_hours": total_hours
    }


# leave_router.py

@router.post("/Leaveapply")
def apply_leave(
    leave: LeaveApply,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    # 1️⃣ One Day Leave
    if leave.leave_type == "one_day":
        if not leave.leave_date:
            raise HTTPException(status_code=400, detail="Date is required")

        start_date = leave.leave_date
        end_date = leave.leave_date
        total_days = 1

    # 2️⃣ Multiple Days Leave
    elif leave.leave_type == "multiple_days":
        if not leave.start_date or not leave.end_date:
            raise HTTPException(status_code=400, detail="Start and End date required")

        if leave.end_date < leave.start_date:
            raise HTTPException(status_code=400, detail="Invalid date range")

        start_date = leave.start_date
        end_date = leave.end_date
        total_days = (end_date - start_date).days + 1

    else:
        raise HTTPException(status_code=400, detail="Invalid leave type")

    new_leave = Leave(
        user_id=current_user.id,
        leave_type=leave.leave_type,
        start_date=start_date,
        end_date=end_date,
        total_days=total_days,
        description=leave.description
    )

    db.add(new_leave)
    db.commit()
    db.refresh(new_leave)

    return {
        "message": "Leave applied successfully",
        "leave_id": new_leave.id,
        "total_days": total_days,
        "status": new_leave.status
    }

@router.get("/admin/leave-requests")
def get_leave_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    # If current user is admin → get all leave requests
    if current_user.role == "admin":
        leaves = db.query(Leave).all()

    # Else → get leave requests of employees reporting to current user
    else:
        leaves = db.query(Leave).join(
            User, Leave.user_id == User.id
        ).filter(
            User.reporting_to == current_user.id
        ).all()

    result = []

    for leave in leaves:
        result.append({
            "leave_id": leave.id,
            "employee_id": leave.user_id,
            "status": leave.status,
            "approved_by_id": leave.approved_by,
            "approved_by_name": leave.approver.first_name if leave.approver else None,
            "approved_by_designation": leave.approver.designation if leave.approver else None,
            "approved_on": leave.approved_on
        })

    return result



@router.put("/admin/leave-status/{leave_id}")
def update_leave_status(
    leave_id: int,
    status_update: LeaveStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can update leave status")

    leave = db.query(Leave).filter(Leave.id == leave_id).first()

    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")

    if leave.status != "pending":
        raise HTTPException(status_code=400, detail="Leave already processed")

    leave.status = status_update.status
    leave.approved_by = current_user.id
    leave.approved_on = date.today()

    db.commit()
    db.refresh(leave)

    return {
        "message": f"Leave {status_update.status} successfully",
        "leave_id": leave.id,
        "status": leave.status
    }
