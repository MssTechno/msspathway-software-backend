from enum import Enum
from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import Optional
from pydantic import BaseModel, HttpUrl
from datetime import date
from typing import Optional
from typing import List
class ClientStatus(str, Enum):
    active = "A"
    terminated = "T"
    pass_status = "P"
    completed = "C"

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
    aadhar_number: Optional[str] = None
    location: Optional[str] = None
    reporting_to: Optional[str] = None
    HR: Optional[str] = None

class UserLimitedUpdate(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    mobile: Optional[str] = None
    designation: Optional[str] = None
    role: Optional[str] = None
    reporting_to: Optional[str] = None
    HR: Optional[str] = None
    password: Optional[str] = None

class UserResponse(BaseModel):
    employee_id: Optional[str] = None
    first_name: str | None = None
    last_name: str | None = None
    mobile: str | None = None
    designation: str | None = None
    email: str
    role: str

    class Config:
        from_attributes = True

class ClientCreate(BaseModel):
    client_name: str
    mobile: str
    technology: str
    status: ClientStatus
    employee_id: str

class ClientResponse(BaseModel):
    id: int
    client_name: str
    mobile: str
    email: Optional[str]
    technology: Optional[str]
    status: Optional[str]
    professional_role: Optional[str]
    aadhaar_number: Optional[str]
    location: Optional[str]
    employee_name: Optional[str]
    employee_id: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True

class ClientUpdate(BaseModel):
    client_name: Optional[str] = None
    mobile: Optional[str] = None
    technology: Optional[str] = None
    status: Optional[str] = None
    employee_id: Optional[str] = None

    
class PlatformEnum(str, Enum):
    naukri = "Naukri"
    linkedin = "LinkedIn"
    career_pages = "Career Pages"
    cold_emails = "Cold Emails"
    other = "Other"


class ApplicationCreate(BaseModel):
    platform: PlatformEnum
    company_name: str
    role: str
    date_applied: date
    application_link: Optional[HttpUrl] = None
    notes: Optional[str] = None

class ApplicationUpdate(BaseModel):
    platform: Optional[str] = None
    company_name: Optional[str] = None
    role: Optional[str] = None
    date_applied: Optional[date] = None
    application_link: Optional[str] = None
    notes: Optional[str] = None

class CredentialCreate(BaseModel):

    portal_name:str
    portal_link:str
    username:str
    password:str
    notes:str

class CredentialUpdate(BaseModel):

    portal_name:str | None=None
    portal_link:str | None=None
    username:str | None=None
    password:str | None=None
    notes:str | None=None

class ReportCreate(BaseModel):
    company_name:str
    recruiter_name:str
    recruiter_contact:int
    recruiter_email:str
    type:str
    status:Optional[str]=None
    date:str
    notes:str | None = None

class ReportUpdate(BaseModel):
    company_name: Optional[str]
    recruiter_name: Optional[str]
    recruiter_contact: Optional[int]
    recruiter_email: Optional[str]
    type: Optional[str]
    status: Optional[str]
    date: Optional[date]
    notes: Optional[str]

class SourceLink(BaseModel):
    link: str
    link_type: str

class SourceLinksRequest(BaseModel):
    links: List[SourceLink]
#-------------------------------calander schemas apis-------------------

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