from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, Time, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from database import Base
from datetime import date


class DraftTimesheet(Base):
    __tablename__ = "draft_timesheets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    project_name = Column(String, nullable=False)
    task_name = Column(String, nullable=False)

    work_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    break_time = Column(Integer, default=0)  # stored in minutes
    hours = Column(Float, nullable=False)    # stored in hours

   
class Timesheet(Base):
    __tablename__ = "timesheets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    submitted_date = Column(Date, nullable=False)
    total_hours = Column(Float, nullable=False)

    activities = Column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "submitted_date", name="unique_user_submit_per_day"),
    )

# leave_models.py

class Leave(Base):
    __tablename__ = "leaves"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    leave_type = Column(String)  # one_day / multiple_days
    start_date = Column(Date)
    end_date = Column(Date)
    total_days = Column(Integer)
    description = Column(String)
    status = Column(String, default="pending")
    applied_on = Column(Date, default=date.today)
    user = relationship("User")

    status = Column(String, default="pending")

    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_on = Column(Date, nullable=True)

    

    user = relationship("User", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approved_by])
