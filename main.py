from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from auth import router as auth_router
from database import engine, get_db
from db_dependencies import admin_only
from models import User, Base, Client
from schemas import UserCreate, UserResponse, UserLimitedUpdate, ClientCreate, ClientResponse
from schemas import ClientStatusUpdate
from security import hash_password
from db_dependencies import get_db, admin_only, get_current_user
import models


# ------------------ CLIENT ROUTER ------------------
router = APIRouter()

@router.post("/create-client")
def create_client(client: ClientCreate, db: Session = Depends(get_db),admin=Depends(admin_only)):

    new_client = Client(
        client_name=client.client_name,
        mobile=client.mobile,
        technology=client.technology,
        status=client.status,
        assigned_user_id=client.assigned_user_id
    )

    db.add(new_client)
    db.commit()
    db.refresh(new_client)

    return {
        "message": "Client created successfully",
        "data": new_client
    }

@router.get("/clients", response_model=list[ClientResponse])
def get_clients(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    if current_user["role"] == "admin":
        clients = db.query(Client).all()
    else:
        clients = db.query(Client).filter(
            Client.assigned_user_id == current_user["id"]
        ).all()

    return clients

@router.put("/clients/{client_id}/status")
def update_client_status(
    client_id: int,
    data: ClientStatusUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    client.status = data.status

    db.commit()
    db.refresh(client)

    return {
        "message": "Client status updated",
        "client_id": client.id,
        "status": client.status
    }
# ------------------ CREATE APP ------------------
app = FastAPI(
    title="Pathway Project API",
    description="Backend APIs for Pathway Project",
    version="1.0.0"
)

app.include_router(auth_router)
app.include_router(router, prefix="/clients", tags=["Clients"])


# ------------------ CREATE TABLES ------------------
Base.metadata.create_all(bind=engine)


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


# ------------------ UPDATE USER ------------------
@app.put("/admin/users/{user_id}")
def update_user(
    user_id: int,
    user: UserLimitedUpdate,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    db_user = db.query(User).filter(User.id == user_id).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

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
