from pydantic import BaseModel
from datetime import date, time
from typing import Optional 
import datetime  
from datetime import date as dt_date
from typing import Literal
class TimesheetCreate(BaseModel):
    project_name: str
    task_name: str
    start_time: time
    end_time: time
    break_time: int  
# leave_schemas.py

class LeaveApply(BaseModel):
    leave_type: str
    leave_date: Optional[dt_date] = None
    start_date: Optional[dt_date] = None
    end_date: Optional[dt_date] = None
    description: str

class LeaveStatusUpdate(BaseModel):
    status: Literal["approved", "rejected"]
