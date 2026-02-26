from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from timesheet_schedular import move_drafts_to_timesheet
from calendar_router import router as calendar_router #Calender router
from timesheet_router import router as timesheet_router
from auth import router as auth_router
from database import Base, engine
from db_dependencies import get_db, admin_only
from models import User
from schemas import UserCreate, UserResponse, UserLimitedUpdate
from security import hash_password 

import models
import timesheet_models

app = FastAPI(title="Login API")
#calender apis
app.include_router(timesheet_router)
app.include_router(auth_router)
app.include_router(calendar_router)
# Create tables
Base.metadata.create_all(bind=engine)

# ------------------ SCHEDULER ------------------
scheduler = BackgroundScheduler()
scheduler.add_job(
    move_drafts_to_timesheet,
    "cron",
    hour=18,
    minute=0
)
scheduler.start()
# ----------------------------------------------

# ------------------ CREATE USER ------------------
@app.post("/admin/users", response_model=UserResponse)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = hash_password(user.password)

    new_user = User(
    email=user.email,
    password_hash=hashed_password,
    role=user.role,
    first_name=user.first_name,
    last_name=user.last_name,
    mobile=user.mobile,
    designation=user.designation,
    reporting_to=user.reporting_to,
    HR=user.HR

)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# ------------------ GET USERS ------------------
@app.get("/admin/users", response_model=list[UserResponse])
def get_users(
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    return db.query(User).all()

# ------------------ UPDATE USER ROLE ------------------
@app.put("/admin/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user: UserLimitedUpdate,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    db_user = db.query(User).filter(User.id == user_id).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # ✅ Update only allowed fields
    if user.mobile is not None:
        db_user.mobile = user.mobile

    if user.designation is not None:
        db_user.designation = user.designation

    if user.role is not None:
        db_user.role = user.role.lower()

    if user.reporting_to is not None:
        db_user.reporting_to = user.reporting_to

    if user.HR is not None:
        db_user.HR = user.HR

    db.commit()
    db.refresh(db_user)

    return db_user

# ------------------ DELETE USER ------------------
@app.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": "User deleted"}
