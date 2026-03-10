from pydantic import BaseModel, EmailStr, Field 
from typing import Optional
from enums import ClientStatus

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

class ClientCreate(BaseModel):
    client_name: str
    mobile: str
    technology: str
    status: ClientStatus
    assigned_user_id: int

class ClientResponse(BaseModel):
    id: int
    client_name: str
    mobile: str
    technology: str
    status: str

    class Config:
        from_attributes = True

class ClientStatusUpdate(BaseModel):
    status: ClientStatus