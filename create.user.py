from database import SessionLocal, Base, engine
from models import User
from security import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()

email = "admin@gmail.com"
password = "admin1234"
role = "admin"

print("DB URL:", engine.url)#

existing_user = db.query(User).filter(User.email == email).first()
if existing_user:
    print(f"User '{email}' already exists.")
else:
    new_user = User(
        email=email,
        password_hash=hash_password(password),
        role=role
    )
    db.add(new_user)
    db.commit()
    print(f"User '{email}' created successfully!")

db.close()

