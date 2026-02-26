from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    mobile = Column(String, nullable=True)
    designation = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")
    reporting_to = Column(String, nullable=True)
    HR = Column(String, nullable=True)
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
