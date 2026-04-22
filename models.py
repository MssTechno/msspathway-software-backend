from sqlalchemy import Column, Integer, String, ForeignKey, Date, Text, Boolean
from database import Base
from sqlalchemy.orm import relationship
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    employee_id = Column(String, unique=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    mobile = Column(String, nullable=True)
    designation = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")
    reporting_to = Column(String, ForeignKey("users.employee_id"), nullable=True)
    HR = Column(String, ForeignKey("users.employee_id"), nullable=True)
    aadhaar_number = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    location = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    photo = Column(String, nullable=True)
    documents = Column(String, nullable=True)  # store file paths (comma separated or JSON)

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String)
    mobile = Column(String)
    technology = Column(String)
    status = Column(String)
    employee_id = Column(String, ForeignKey("users.employee_id"), nullable=True)
    professional_role = Column(String)
    aadhaar_number = Column(String)
    location = Column(String)
    email = Column(String)
    photo = Column(String)
    documents = Column(String)  

class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    company_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    platform = Column(String, nullable=False)
    date_applied = Column(Date, nullable=False)
    application_link = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    source = Column(String)
    
class Credential(Base):

    __tablename__ = "credentials"

    id = Column(Integer,primary_key=True,index=True)

    client_id = Column(Integer,ForeignKey("clients.id"))

    portal_name = Column(String,nullable=False)
    portal_link = Column(String,nullable=False)
    username = Column(String,nullable=False)
    password = Column(String,nullable=False)
    notes =  Column(String,nullable=True)
    client = relationship("Client")


class Reports(Base):

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)

    client_id = Column(Integer, ForeignKey("clients.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String)
    company_name = Column(String)
    recruiter_name = Column(String)
    recruiter_contact = Column(Integer)
    recruiter_email = Column(String)
    date = Column(Date)
    status = Column(String, default="PENDING")
    notes = Column(String)
    source = Column(String)
    #---------------------------calander apis------------------------------------------

from sqlalchemy import Date, Enum
import enum


class DayStatus(str, enum.Enum):
    normal = "normal"
    publicholiday = "publicholiday"
    leave = "leave"


class Calendar(Base):
    __tablename__ = "calendar"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    status = Column(Enum(DayStatus), default=DayStatus.normal, nullable=False)
