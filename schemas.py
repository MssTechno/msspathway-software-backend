from pydantic import BaseModel, EmailStr, Field 
from typing import Optional
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    role: str

class UserCreate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    mobile: str | None = None
    designation: str | None = None
    email: EmailStr
    password: str
    role: str = "user"
    reporting_to : int | None = None
    HR : int | None = None

class UserLimitedUpdate(BaseModel):
    mobile: Optional[str] = None
    designation: Optional[str] = None
    role: Optional[str] = None
    reporting_to: Optional[int] = None
    HR: Optional[int] = None

class UserResponse(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    mobile: str | None = None
    designation: str | None = None
    email: str
    role: str

    class Config:
        from_attributes = True


#-------------------------------calander apis-------------------

from datetime import date
from typing import List
from models import DayStatus


class CalendarResponse(BaseModel):
    id: int
    date: date
    status: DayStatus

    class Config:
        from_attributes = True


class CalendarUpdate(BaseModel):
    status: DayStatus



#------------------------display working hours in calander-----------------------

from typing import Optional
from datetime import date
from pydantic import BaseModel
from models import DayStatus


class CalendarWithHoursResponse(BaseModel):
    id: int
    date: date
    status: DayStatus
    total_hours: float = 0

    class Config:
        from_attributes = True

