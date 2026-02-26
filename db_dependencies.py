from database import SessionLocal
from fastapi import Depends, HTTPException
from jose import jwt, JWTError
from config import SECRET_KEY, ALGORITHM
from fastapi.security import HTTPAuthorizationCredentials
from security import bearer_scheme
from models import User
from sqlalchemy.orm import Session


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ✅ AUTHENTICATION (USER OR ADMIN)
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        email = payload.get("sub")
        if not email:
            raise HTTPException(401, "Invalid token payload")

        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(401, "User not found")

        return user
    except JWTError:
        raise HTTPException(401, "Invalid token")


# ✅ ADMIN AUTHORIZATION
def admin_only(
    user: dict = Depends(get_current_user)
):
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return user
