from datetime import datetime, time as dtime
from database import SessionLocal
from timesheet_models import DraftTimesheet, Timesheet

def move_drafts_to_timesheet():
    db = SessionLocal()
    try:
        now = datetime.now().time()

        # Run only after 11:59 PM
        if now < dtime(23, 59):
            return

        drafts = db.query(DraftTimesheet).all()

        for draft in drafts:
            timesheet = Timesheet(
                user_id=draft.user_id,
                project_name=draft.project_name,
                task_name=draft.task_name,
                start_time=draft.start_time,
                end_time=draft.end_time,
                break_time=draft.break_time,
                total_time=draft.total_time,
            )

            db.add(timesheet)
            db.delete(draft)

        db.commit()

    finally:
        db.close()

