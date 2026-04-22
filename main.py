from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from auth import router as auth_router
from database import engine, get_db
from db_dependencies import admin_only
from models import User, Base, Client
from schemas import UserCreate, UserResponse, UserLimitedUpdate, ClientCreate, ClientResponse, ReportCreate
from schemas import ClientUpdate, ApplicationUpdate
from security import hash_password
from db_dependencies import get_db, admin_only, get_current_user
import models
from timesheet_models import Leave
from models import Application, Client, Credential, Reports
from schemas import ApplicationCreate, CredentialCreate, CredentialUpdate, ReportUpdate, ClientStatus
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import UploadFile, File, Form
from typing import Optional, List
from timesheet_schedular import move_drafts_to_timesheet
from calendar_router import router as calendar_router
from timesheet_router import router as timesheet_router
import timesheet_models
from datetime import date
from fastapi import Query
from fastapi.responses import FileResponse
import os
from fastapi.staticfiles import StaticFiles

app = FastAPI()

os.makedirs("uploads", exist_ok=True)
os.makedirs("uploads/photos", exist_ok=True)
os.makedirs("uploads/docs", exist_ok=True)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
print("THIS FILE IS RUNNING")
# ------------------ CORS CONFIG ------------------
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",       
    "http://127.0.0.1:5174", 
    "https://msstechno-timesheet.vercel.app",      
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ------------------ CREATE TABLES ------------------
Base.metadata.create_all(bind=engine)
# ------------------ SCHEDULER (Commented as you kept) ------------------
scheduler = BackgroundScheduler()
scheduler.add_job(
     move_drafts_to_timesheet,
     "cron",
     hour=23,
     minute=59
 )
scheduler.start()
# ------------------ CLIENT ROUTER ------------------
router = APIRouter()

from fastapi import APIRouter, Form, File, UploadFile, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional
import os
import uuid

@router.post(
    "/create-client",
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "client_name": {"type": "string"},
                            "mobile": {"type": "string"},
                            "technology": {"type": "string"},
                            "status": {"type": "string"},
                            "employee_id": {"type": "string"},
                            "professional_role": {"type": "string"},
                            "aadhaar_number": {"type": "string"},
                            "location": {"type": "string"},
                            "email": {"type": "string"},
                            "photo": {"type": "string", "format": "binary"},
                            "documents": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary"}
                            }
                        },
                        "required": ["client_name", "mobile", "employee_id"]
                    }
                }
            }
        }
    }
)
async def create_client(
    client_name: str = Form(...),
    mobile: str = Form(...),
    technology: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    employee_id: str = Form(...),

    professional_role: Optional[str] = Form(None),
    aadhaar_number: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    email: Optional[str] = Form(None),

    photo: Optional[UploadFile] = File(None),
    documents: List[UploadFile] = File(default=[]),

    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    import os, uuid

    os.makedirs("uploads/photos", exist_ok=True)
    os.makedirs("uploads/docs", exist_ok=True)

    # ✅ PHOTO
    photo_path = None
    if photo and photo.filename:
        name = f"{uuid.uuid4()}_{photo.filename}"
        photo_path = f"uploads/photos/{name}"
        with open(photo_path, "wb") as f:
            f.write(photo.file.read())

    # ✅ DOCUMENTS
    document_paths = []
    for doc in documents:
        if doc and doc.filename:
            name = f"{uuid.uuid4()}_{doc.filename}"
            path = f"uploads/docs/{name}"
            with open(path, "wb") as f:
                f.write(doc.file.read())
            document_paths.append(path)

    # ✅ SAVE TO DATABASE (THIS WAS MISSING)
    try:
        new_client = Client(
            client_name=client_name,
            mobile=mobile,
            email=email,
            technology=technology,
            status=status,
            employee_id=employee_id,
            professional_role=professional_role,
            aadhaar_number=aadhaar_number,
            location=location,
            photo=photo_path,
            documents=",".join(document_paths) if document_paths else None
        )

        db.add(new_client)
        db.commit()
        db.refresh(new_client)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    # ✅ RESPONSE
    return {
        "message": "Client created successfully",
        "client_id": new_client.id,
        "photo": photo_path,
        "documents": document_paths
    }

@router.get("/client-profile/{client_id}")
def get_client_profile(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    import time

    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # ✅ Documents formatting
    documents_list = []
    if client.documents:
        for doc in client.documents.split(","):
            documents_list.append({
                "file_name": doc.split("/")[-1],
                "file_url": doc
            })

    return {
        "client_name": client.client_name,
        "professional_role": client.professional_role,
        "mobile": client.mobile,
        "email": client.email,
        "aadhaar_number": client.aadhaar_number,
        "location": client.location,

        # ✅ Fix caching issue
        "photo": f"{client.photo}?t={int(time.time())}",
        "documents": documents_list
    }

@router.get("/clients/{client_id}")
def get_client_by_id(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # ✅ Fetch client
    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # ✅ Convert documents string → list
    documents_list = client.documents.split(",") if client.documents else []

    return {
        "id": client.id,
        "client_name": client.client_name,
        "mobile": client.mobile,
        "email": client.email,
        "technology": client.technology,
        "status": client.status,
        "employee_id": client.employee_id,
        "professional_role": client.professional_role,
        "aadhaar_number": client.aadhaar_number,
        "location": client.location,

        # ✅ Separate fields
        "photo": client.photo,
        "documents": documents_list
    }

@router.get("/clients", response_model=list[ClientResponse])
def get_clients(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    # 🔹 Get full user from DB
    user = db.query(User).filter(User.id == current_user["id"]).first()

    if current_user["role"] == "admin":
        clients = db.query(Client).all()
    else:
        clients = db.query(Client).filter(
            Client.employee_id == user.employee_id
        ).all()

    return clients
    
@router.put("/update-client/{client_id}")
async def update_client(
    client_id: int,

    client_name: Optional[str] = Form(None),
    mobile: Optional[str] = Form(None),
    technology: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    employee_id: Optional[str] = Form(None),

    professional_role: Optional[str] = Form(None),
    aadhaar_number: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    email: Optional[str] = Form(None),

    photo: Optional[UploadFile] = File(None),
    documents: List[UploadFile] = File(default=[]),

    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    import os, uuid

    os.makedirs("uploads/photos", exist_ok=True)
    os.makedirs("uploads/docs", exist_ok=True)

    # ✅ Get client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # =========================
    # ✅ UPDATE TEXT FIELDS
    # =========================
    update_fields = {
        "client_name": client_name,
        "mobile": mobile,
        "technology": technology,
        "status": status,
        "employee_id": employee_id,
        "professional_role": professional_role,
        "aadhaar_number": aadhaar_number,
        "location": location,
        "email": email
    }

    for field, value in update_fields.items():
        if value is not None:
            setattr(client, field, value)

    # =========================
    # ✅ UPDATE PHOTO
    # =========================
    if photo and photo.filename:
        # (optional) delete old photo
        if client.photo and os.path.exists(client.photo):
            os.remove(client.photo)

        photo_name = f"{uuid.uuid4()}_{photo.filename}"
        photo_path = f"uploads/photos/{photo_name}"

        with open(photo_path, "wb") as f:
            f.write(photo.file.read())

        client.photo = photo_path

    # =========================
    # ✅ UPDATE DOCUMENTS
    # =========================
    existing_docs = []
    if client.documents:
        existing_docs = [doc for doc in client.documents.split(",") if doc]

    new_docs = []
    for doc in documents:
        if doc and doc.filename:
            doc_name = f"{uuid.uuid4()}_{doc.filename}"
            doc_path = f"uploads/docs/{doc_name}"

            with open(doc_path, "wb") as f:
                f.write(doc.file.read())

            new_docs.append(doc_path)

    # 👉 Merge
    all_docs = existing_docs + new_docs
    client.documents = ",".join(all_docs) if all_docs else None

    # =========================
    # ✅ SAVE
    # =========================
    try:
        db.commit()
        db.refresh(client)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "message": "Client updated successfully",
        "client_id": client.id,
        "photo": client.photo,
        "documents": all_docs
    }
@router.get("/client_profile/{client_id}")
def get_client_by_id(
    client_id: int,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    # ✅ Fetch client
    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # ✅ Convert documents string → list
    documents = []
    if client.documents:
        documents = [doc for doc in client.documents.split(",") if doc]

    return {
        "client_id": client.id,
        "client_name": client.client_name,
        "professional_role": client.professional_role,
        "mobile": client.mobile,
        "email": client.email,
        "aadhaar_number": client.aadhaar_number,
        "location": client.location,
        "photo": client.photo,
        "documents": documents
    }

@router.put("/update-client_profile/{client_id}")
async def update_client(
    client_id: int,
    client_name: Optional[str] = Form(None),
    mobile: Optional[str] = Form(None),
    professional_role: Optional[str] = Form(None),
    aadhaar_number: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    email: Optional[str] = Form(None),

    photo: Optional[UploadFile] = File(None),
    documents: List[UploadFile] = File(default=[]),

    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    import os, uuid

    os.makedirs("uploads/photos", exist_ok=True)
    os.makedirs("uploads/docs", exist_ok=True)

    # ✅ Get client
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # =========================
    # ✅ UPDATE TEXT FIELDS
    # =========================
    update_fields = {
        "client_name": client_name,
        "mobile": mobile,
        "professional_role": professional_role,
        "aadhaar_number": aadhaar_number,
        "location": location,
        "email": email
    }

    for field, value in update_fields.items():
        if value is not None:
            setattr(client, field, value)

    # =========================
    # ✅ UPDATE PHOTO
    # =========================
    if photo and photo.filename:
        # (optional) delete old photo
        if client.photo and os.path.exists(client.photo):
            os.remove(client.photo)

        photo_name = f"{uuid.uuid4()}_{photo.filename}"
        photo_path = f"uploads/photos/{photo_name}"

        with open(photo_path, "wb") as f:
            f.write(photo.file.read())

        client.photo = photo_path

    # =========================
    # ✅ UPDATE DOCUMENTS
    # =========================
    existing_docs = []
    if client.documents:
        existing_docs = [doc for doc in client.documents.split(",") if doc]

    new_docs = []
    for doc in documents:
        if doc and doc.filename:
            doc_name = f"{uuid.uuid4()}_{doc.filename}"
            doc_path = f"uploads/docs/{doc_name}"

            with open(doc_path, "wb") as f:
                f.write(doc.file.read())

            new_docs.append(doc_path)

    # 👉 Merge
    all_docs = existing_docs + new_docs
    client.documents = ",".join(all_docs) if all_docs else None

    # =========================
    # ✅ SAVE
    # =========================
    try:
        db.commit()
        db.refresh(client)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "message": "Client updated successfully",
        "client_id": client.id,
        "photo": client.photo,
        "documents": all_docs
    }

BASE_DIR = "uploads/docs"

def get_safe_file_path(filename: str):
    # Prevent path traversal attack
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = os.path.join(BASE_DIR, filename)
    return file_path

@router.get("/documents/view/{filename}")
def view_document(filename: str):
    file_path = get_safe_file_path(filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        media_type="application/octet-stream"
    )

@router.get("/documents/download/{filename}")
def download_document(filename: str):
    file_path = get_safe_file_path(filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        media_type="application/octet-stream",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.delete("/clients/{client_id}")
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    db.delete(client)
    db.commit()

    return {
        "message": "Client deleted successfully",
        "client_id": client_id
    }
#-------------------application router----------
application_router = APIRouter(prefix="/applications", tags=["Applications"])

@application_router.post("/create_application/{client_id}")
def create_application(

    client_id:int,   # from URL
    data: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    client = db.query(Client).filter(
        Client.id == client_id
    ).first()

    if not client:
        return {"message":"Client not found"}


    new_application = Application(

        client_id=client_id,   # from URL (FIX)
        platform=data.platform.value,
        company_name=data.company_name,
        role=data.role,
        date_applied=data.date_applied,
        application_link=str(data.application_link) if data.application_link else None,
        notes=data.notes
    )

    db.add(new_application)
    db.commit()
    db.refresh(new_application)

    return {
        "message":"Application saved successfully"
    }

from sqlalchemy import func

@application_router.get("/applications/{client_id}")
def get_applications(
    client_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    client = db.query(Client).filter(
        Client.id == client_id
    ).first()

    if not client:
        return {"message": "Client not found"}


    # get applications
    applications = db.query(Application).filter(
        Application.client_id == client_id
    ).order_by(
        Application.date_applied.desc()
    ).all()

    # stats
    stats_query = db.query(
        Application.platform,
        func.count(Application.id)
    ).filter(
        Application.client_id == client_id
    ).group_by(
        Application.platform
    ).all()

    stats = {
        "Naukri": 0,
        "LinkedIn": 0,
        "Career Pages": 0,
        "Cold Emails": 0,
        "Other": 0
    }

    for platform, count in stats_query:
        if platform in stats:
            stats[platform] = count
        else:
            stats["Other"] += count

    # platform grouped data
    platform_data = {
        "Naukri": [],
        "LinkedIn": [],
        "Career Pages": [],
        "Cold Emails": [],
        "Other": []
    }

    for app in applications:

        application_obj = {
            "id": app.id,
            "company_name": app.company_name,
            "role": app.role,
            "date": app.date_applied.strftime("%b %d, %Y"),
            "application_link": app.application_link,
            "platform": app.platform
        }

        if app.platform in platform_data:
            platform_data[app.platform].append(application_obj)
        else:
            platform_data["Other"].append(application_obj)

    return {
        "stats": stats,
        "applications": platform_data
    }

@application_router.put("/update/{application_id}")
def update_application(

    application_id: int,
    data: ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)

):

    application = db.query(Application).filter(
        Application.id == application_id
    ).first()

    if not application:
        return {"message": "Application not found"}

    if data.platform:
        application.platform = data.platform

    if data.company_name:
        application.company_name = data.company_name

    if data.role:
        application.role = data.role

    if data.date_applied:
        application.date_applied = data.date_applied

    if data.application_link:
        application.application_link = str(data.application_link)

    if data.notes:
        application.notes = data.notes

    db.commit()
    db.refresh(application)

    return {
        "message": "Application updated successfully",
        "application_id": application.id
    }

@application_router.delete("/delete/{application_id}")
def delete_application(

    application_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)

):

    application = db.query(Application).filter(
        Application.id == application_id
    ).first()

    if not application:
        return {"message": "Application not found"}

    db.delete(application)
    db.commit()

    return {
        "message": "Application deleted successfully"
    }
#-----------------credentials routers--------------
Credential_router = APIRouter(
    prefix="/credentials",
    tags=["Credentials"]
)
@Credential_router.post("/create_credentials/{client_id}")
def create_credential(

    client_id:int,
    data:CredentialCreate,

    db:Session = Depends(get_db),
    current_user = Depends(get_current_user)

):

    client = db.query(Client).filter(
        Client.id == client_id
    ).first()

    if not client:
        return {"message":"Client not found"}

   

    new_credential = Credential(

        client_id=client_id,

        portal_name=data.portal_name,
        portal_link=data.portal_link,
        username=data.username,
        password=data.password,
        notes=data.notes
    )

    db.add(new_credential)

    db.commit()

    db.refresh(new_credential)

    return {

        "message":"Credential added successfully",

        "data":{
            "id":new_credential.id,
            "portal_name":new_credential.portal_name,
            "username":new_credential.username
        }
    }

@Credential_router.get("/{client_id}")
def get_credentials(

    client_id:int,
    db:Session = Depends(get_db)

):

    client = db.query(Client).filter(
        Client.id == client_id
    ).first()

    if not client:
        raise HTTPException(404,"Client not found")

    credentials = db.query(Credential).filter(
        Credential.client_id == client_id
    ).all()

    result=[]

    for cred in credentials:

        result.append({

            "id":cred.id,
            "portal_name":cred.portal_name,
            "portal_link":cred.portal_link,
            "username":cred.username,
            "password":cred.password,
            "notes":cred.notes
        })

    return {
        "credentials":result
    }
    

@Credential_router.put("/update/{credential_id}")
def update_credential(

    credential_id:int,
    data:CredentialUpdate,
    db:Session = Depends(get_db)

):

    credential = db.query(Credential).filter(
        Credential.id == credential_id
    ).first()

    if not credential:
        raise HTTPException(404,"Credential not found")

    if data.portal_name:
        credential.portal_name = data.portal_name
    
    if data.portal_link:
        credential.portal_link = data.portal_link
        
    if data.username:
        credential.username = data.username

    if data.password:
        credential.password = data.password
   
    if data.notes:
        credential.notes = data.notes

    db.commit()
    db.refresh(credential)

    return {
        "message":"Updated successfully",
        "credential_id":credential.id
    }

@Credential_router.delete("/delete/{credential_id}")
def delete_credential(

    credential_id:int,
    db:Session = Depends(get_db)

):

    credential = db.query(Credential).filter(
        Credential.id == credential_id
    ).first()

    if not credential:
        raise HTTPException(404,"Credential not found")

    db.delete(credential)
    db.commit()

    return {"message":"Deleted successfully"}
        #------------------reports Api-------------------------------

reports_router = APIRouter(prefix="/reports", tags=["Reports"])

@reports_router.post("/clients/{client_id}/reports")
def create_report(

    client_id:int,
    data: ReportCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):

    client = db.query(Client).filter(
        Client.id == client_id
    ).first()

    if not client:
        raise HTTPException(
            status_code=404,
            detail="Client not found"
        )


    new_report = Reports(

        client_id = client_id,
        user_id = current_user["id"],
        company_name = data.company_name,
        recruiter_name = data.recruiter_name,
        recruiter_contact = data.recruiter_contact,
        recruiter_email = data.recruiter_email,
        type = data.type,
        status = data.status,
        date = data.date,
        notes = data.notes
    )

    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return {
        "message":"Report added successfully"
    }

@reports_router.get("/clients/{client_id}/reports")
def get_reports(client_id: int, db: Session = Depends(get_db)):

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    reports = db.query(Reports).filter(
        Reports.client_id == client_id
    ).all()

    stats = {
        "calls_received": 0,
        "mails_received": 0,
        "l1_interviews": 0,
        "l2_interviews": 0,
        "offer_letters": 0
    }

    companies = {}

    # ✅ NORMALIZE FUNCTION
    def normalize(stage):
        if not stage:
            return ""
        stage = stage.lower().strip()

        if "call" in stage:
            return "call"
        if "mail" in stage:
            return "mail"
        if "l1" in stage:
            return "l1"
        if "l2" in stage:
            return "l2"
        if "offer" in stage:
            return "offer"

        return stage

    order = ["call", "mail", "l1", "l2", "offer"]

    for r in reports:

        company_key = r.company_name.lower().strip()   # ✅ FIX duplicates
        stage = normalize(r.type)

        # -------- COUNT LOGIC --------
        if stage in order:
            idx = order.index(stage)

            if idx >= 0:
                stats["calls_received"] += 1
            if idx >= 1:
                stats["mails_received"] += 1
            if idx >= 2:
                stats["l1_interviews"] += 1
            if idx >= 3:
                stats["l2_interviews"] += 1
            if idx >= 4:
                stats["offer_letters"] += 1

        # -------- COMPANY DATA --------
        companies[company_key] = {
            "company": r.company_name,
            "latest_report_id": r.id,
            "updated_at": r.date,
            "current_stage": stage,
            "status": r.status
        }

    return {
        "pipeline_overview": stats,
        "company_progression": list(companies.values())
    }

@reports_router.get("/reports/{report_id}")
def get_single_report(
    report_id: int,
    db: Session = Depends(get_db)
):
    report = db.query(Reports).filter(
        Reports.id == report_id
    ).first()

    if not report:
        raise HTTPException(404, "Report not found")

    return {
        "id": report.id,
        "company_name": report.company_name,
        "recruiter_name": report.recruiter_name,
        "recruiter_contact": report.recruiter_contact,
        "recruiter_email": report.recruiter_email,
        "type": report.type,
        "status": report.status,
        "date": report.date,
        "notes": report.notes
    }
@reports_router.put("/reports/{report_id}")
def update_report(
    report_id: int,
    data: ReportUpdate,
    db: Session = Depends(get_db)
):
    report = db.query(Reports).filter(
        Reports.id == report_id
    ).first()

    if not report:
        raise HTTPException(404, "Report not found")

    # update fields
    for key, value in data.dict(exclude_unset=True).items():
        setattr(report, key, value)

    db.commit()
    db.refresh(report)

    return {
        "message": "Report updated successfully",
        "report": report
    }


@reports_router.delete("/reports/{report_id}")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    report = db.query(Reports).filter(
        Reports.id == report_id
    ).first()

    if not report:
        raise HTTPException(404, "Report not found")

    db.delete(report)
    db.commit()

    return {
        "message": "Report deleted successfully"
    }

from sqlalchemy import func
@reports_router.get("/dashboard/overview/{client_id}")
def get_overview(client_id: int, db: Session = Depends(get_db)):

    # ===============================
    # ✅ Check client
    # ===============================
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # ===============================
    # 📊 Applications by Platform
    # ===============================
    applications_data = db.query(
        Application.platform,   # ✅ FIXED (was source)
        func.count(Application.id).label("count")
    ).filter(
        Application.client_id == client_id
    ).group_by(Application.platform).all()

    applications_map = {
        "naukri": 0,
        "linkedin": 0,
        "cold_emails": 0,
        "careers_page": 0,
        "others": 0
    }

    # ✅ Normalize platform values from DB
    def normalize_platform(platform: str):
        if not platform:
            return "others"

        p = platform.lower().strip()

        if "naukri" in p:
            return "naukri"
        elif "linkedin" in p:
            return "linkedin"
        elif "cold" in p:
            return "cold_emails"
        elif "career" in p:
            return "careers_page"

        return "others"

    for platform, count in applications_data:
        key = normalize_platform(platform)
        applications_map[key] += count

    # ===============================
    # 📈 Recruitment Funnel (CUMULATIVE)
    # ===============================
    reports = db.query(Reports).filter(
        Reports.client_id == client_id
    ).all()

    stats = {
        "calls_received": 0,
        "mails_received": 0,
        "l1_interviews": 0,
        "l2_interviews": 0,
        "offer_letters": 0
    }

    stage_order = ["call", "mail", "l1", "l2", "offer"]

    # ✅ Normalize stage (your column is `type`)
    def normalize_stage(stage: str):
        if not stage:
            return ""

        s = stage.lower().strip()

        if "call" in s: return "call"
        if "mail" in s: return "mail"
        if "l1" in s: return "l1"
        if "l2" in s: return "l2"
        if "offer" in s: return "offer"

        return ""

    for r in reports:
        current_stage = normalize_stage(r.type)

        if current_stage in stage_order:
            idx = stage_order.index(current_stage)

            # ✅ cumulative counting
            if idx >= 0:
                stats["calls_received"] += 1
            if idx >= 1:
                stats["mails_received"] += 1
            if idx >= 2:
                stats["l1_interviews"] += 1
            if idx >= 3:
                stats["l2_interviews"] += 1
            if idx >= 4:
                stats["offer_letters"] += 1

    # ===============================
    # 🎯 FINAL RESPONSE (UI FORMAT)
    # ===============================
    return {
        "applications_by_platform": [
            {"name": "Naukri", "count": applications_map["naukri"]},
            {"name": "LinkedIn", "count": applications_map["linkedin"]},
            {"name": "Cold Emails", "count": applications_map["cold_emails"]},
            {"name": "Careers Page", "count": applications_map["careers_page"]},
            {"name": "Others", "count": applications_map["others"]},
        ],
        "recruitment_reports": stats
    }
# ------------------ CREATE APP ------------------


app.include_router(auth_router)
app.include_router(router, prefix="/clients", tags=["Clients"])
app.include_router(application_router)
app.include_router(Credential_router)
app.include_router(reports_router)
app.include_router(auth_router)
app.include_router(timesheet_router)
app.include_router(calendar_router)
# ------------------ CREATE TABLES ------------------
Base.metadata.create_all(bind=engine)


# ------------------ CREATE USER ------------------
import re

def generate_employee_id(db: Session):

    last_user = db.query(User).filter(
        User.employee_id.like("MSS%")
    ).order_by(User.employee_id.desc()).first()

    if not last_user:
        return "MSS001"

    # Extract only digits
    numbers = re.findall(r'\d+', last_user.employee_id)

    if not numbers:
        return "MSS001"

    last_number = int(numbers[0])
    new_number = last_number + 1

    return f"MSS{new_number:03d}"
    
'''@app.post("/admin/users", response_model=UserResponse)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):

    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Generate employee id
    employee_id = generate_employee_id(db)

    # Validate reporting manager
    if user.reporting_to:
        manager = db.query(User).filter(
            User.employee_id == user.reporting_to
        ).first()

        if not manager:
            raise HTTPException(
                status_code=400,
                detail="Reporting manager employee_id not found"
            )

    # Validate HR
    if user.HR:
        hr = db.query(User).filter(
            User.employee_id == user.HR
        ).first()

        if not hr:
            raise HTTPException(
                status_code=400,
                detail="HR employee_id not found"
            )

    hashed_password = hash_password(user.password)

    new_user = User(

        employee_id=employee_id,

        email=user.email,
        password_hash=hashed_password,
        role=user.role,
        first_name=user.first_name,
        last_name=user.last_name,
        mobile=user.mobile,
        designation=user.designation,
        
        reporting_to=user.reporting_to if user.reporting_to else None,
        HR=user.HR if user.HR else None
)
    

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user'''

@app.post("/admin/users", response_model=UserResponse)
def create_user(
    # Basic Info
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
    first_name: str = Form(None),
    last_name: str = Form(None),
    mobile: str = Form(None),
    designation: str = Form(None),

    # Relations
    reporting_to: str = Form(None),
    HR: str = Form(None),

    # New Fields
    aadhaar_number: str = Form(None),
    start_date: date = Form(None),
    end_date: date = Form(None),
    location: str = Form(None),

    # Files
    photo: UploadFile = File(None),
    documents: list[UploadFile] = File(None),

    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):

    # 🔍 Check existing email
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 🆔 Generate employee ID
    employee_id = generate_employee_id(db)

    # ✅ Validate reporting manager
    if reporting_to:
        manager = db.query(User).filter(User.employee_id == reporting_to).first()
        if not manager:
            raise HTTPException(status_code=400, detail="Reporting manager not found")

    # ✅ Validate HR
    if HR:
        hr = db.query(User).filter(User.employee_id == HR).first()
        if not hr:
            raise HTTPException(status_code=400, detail="HR not found")

    # ✅ Aadhaar validation (basic)
    if aadhaar_number and len(aadhaar_number) != 12:
        raise HTTPException(status_code=400, detail="Aadhaar must be 12 digits")

    # ✅ Date validation
    if start_date and end_date and end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="End date cannot be before start date"
        )

    # 🔐 Hash password
    hashed_password = hash_password(password)

    # 🟢 Active status logic
    is_active = True if not end_date else False

    # 📁 File storage
    upload_dir = "uploads/users"
    os.makedirs(upload_dir, exist_ok=True)

    # 📸 Save photo
    photo_path = None
    if photo:
        photo_filename = f"{employee_id}_photo_{photo.filename}"
        photo_path = os.path.join(upload_dir, photo_filename)

        with open(photo_path, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)

    # 📄 Save documents
    document_paths = []
    if documents:
        for doc in documents:
            doc_filename = f"{employee_id}_doc_{doc.filename}"
            doc_path = os.path.join(upload_dir, doc_filename)

            with open(doc_path, "wb") as buffer:
                shutil.copyfileobj(doc.file, buffer)

            document_paths.append(doc_path)

    # 👤 Create user
    new_user = User(
        employee_id=employee_id,
        email=email,
        password_hash=hashed_password,
        role=role,
        first_name=first_name,
        last_name=last_name,
        mobile=mobile,
        designation=designation,

        reporting_to=reporting_to if reporting_to else None,
        HR=HR if HR else None,

        aadhaar_number=aadhaar_number,
        start_date=start_date,
        end_date=end_date,
        location=location,
        is_active=is_active,

        photo=photo_path,
        documents=",".join(document_paths) if document_paths else None
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

#----------------------update user------------------

@app.put("/admin/users/{employee_id}", response_model=UserResponse)
def update_user(
    employee_id: str,

    # Basic Info
    email: str = Form(None),
    password: str = Form(None),
    role: str = Form(None),
    first_name: str = Form(None),
    last_name: str = Form(None),
    mobile: str = Form(None),
    designation: str = Form(None),

    # Relations
    reporting_to: str = Form(None),
    HR: str = Form(None),

    # New Fields
    aadhaar_number: str = Form(None),
    start_date: date = Form(None),
    end_date: date = Form(None),
    location: str = Form(None),

    # Files
    photo: UploadFile = File(None),
    documents: list[UploadFile] = File(None),

    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):

    user = db.query(User).filter(User.employee_id == employee_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ✅ Email check
    if email and email != user.email:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")
        user.email = email

    # 🔐 Password update
    if password:
        user.password_hash = hash_password(password)

    # ✅ Validate reporting manager
    if reporting_to:
        manager = db.query(User).filter(User.employee_id == reporting_to).first()
        if not manager:
            raise HTTPException(status_code=400, detail="Reporting manager not found")
        user.reporting_to = reporting_to

    # ✅ Validate HR
    if HR:
        hr = db.query(User).filter(User.employee_id == HR).first()
        if not hr:
            raise HTTPException(status_code=400, detail="HR not found")
        user.HR = HR

    # ✅ Aadhaar validation
    if aadhaar_number:
        if len(aadhaar_number) != 12:
            raise HTTPException(status_code=400, detail="Aadhaar must be 12 digits")
        user.aadhaar_number = aadhaar_number

    # ✅ Date validation
    if start_date and end_date and end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="End date cannot be before start date"
        )

    # Update dates
    if start_date:
        user.start_date = start_date
    if end_date is not None:
        user.end_date = end_date

    # 🟢 Active logic
    user.is_active = False if user.end_date else True

    # Other fields
    if role:
        user.role = role
    if first_name:
        user.first_name = first_name
    if last_name:
        user.last_name = last_name
    if mobile:
        user.mobile = mobile
    if designation:
        user.designation = designation
    if location:
        user.location = location

    # 📁 File handling
    upload_dir = "uploads/users"
    os.makedirs(upload_dir, exist_ok=True)

    # 📸 Replace photo
    if photo:
        # delete old photo
        if user.photo and os.path.exists(user.photo):
            os.remove(user.photo)

        photo_path = os.path.join(upload_dir, f"{employee_id}_photo_{photo.filename}")
        with open(photo_path, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)

        user.photo = photo_path

    # 📄 Replace documents
    if documents:
        # delete old documents
        if user.documents:
            for path in user.documents.split(","):
                if os.path.exists(path):
                    os.remove(path)

        doc_paths = []
        for doc in documents:
            doc_path = os.path.join(upload_dir, f"{employee_id}_doc_{doc.filename}")
            with open(doc_path, "wb") as buffer:
                shutil.copyfileobj(doc.file, buffer)
            doc_paths.append(doc_path)

        user.documents = ",".join(doc_paths)

    db.commit()
    db.refresh(user)

    return user


# ------------------ GET USERS ------------------
@app.get("/admin/users", response_model=list[UserResponse])
def get_users(
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    return db.query(User).all()


# ------------------ UPDATE USER ------------------
'''@app.put("/admin/users/{employee_id}", response_model=UserResponse)
def update_user(
    employee_id: str,
    user:UserLimitedUpdate,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):

    existing_user = db.query(User).filter(
        User.employee_id == employee_id
    ).first()

    if not existing_user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Validate reporting manager
    if user.reporting_to:
        manager = db.query(User).filter(
            User.employee_id == user.reporting_to
        ).first()

        if not manager:
            raise HTTPException(
                status_code=400,
                detail="Reporting manager employee_id not found"
            )

    # Validate HR
    if user.HR:
        hr = db.query(User).filter(
            User.employee_id == user.HR
        ).first()

        if not hr:
            raise HTTPException(
                status_code=400,
                detail="HR employee_id not found"
            )

    # Update fields only if provided
    if user.email:
        existing_user.email = user.email

    if user.first_name:
        existing_user.first_name = user.first_name

    if user.last_name:
        existing_user.last_name = user.last_name

    if user.mobile:
        existing_user.mobile = user.mobile

    if user.designation:
        existing_user.designation = user.designation

    if user.role:
        existing_user.role = user.role

    # Update hierarchy
    existing_user.reporting_to = (
        user.reporting_to if user.reporting_to else None
    )

    existing_user.HR = (
        user.HR if user.HR else None
    )

    # Update password if provided
    if user.password:
        existing_user.password_hash = hash_password(user.password)

    db.commit()
    db.refresh(existing_user)

    return existing_user'''

@app.get("/admin/users/{employee_id}", response_model=UserResponse)
def get_user_by_employee_id(
    employee_id: str,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):

    user = db.query(User).filter(
        User.employee_id == employee_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # ✅ Build full name
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    # ✅ Convert documents to list
    documents = []
    if user.documents:
        documents = user.documents.split(",")

    return {
        "id": user.id,
        "employee_id": user.employee_id,
        "full_name": full_name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "mobile": user.mobile,
        "designation": user.designation,
        "role": user.role,

        "reporting_to": user.reporting_to,
        "HR": user.HR,

        "aadhaar_number": user.aadhaar_number,
        "start_date": user.start_date,
        "end_date": user.end_date,
        "location": user.location,

        "status": "Currently Working" if user.is_active else "Relieved",

        "photo": user.photo,
        "documents": documents
    }
#------------------get by employee id---------------------

@app.get("/admin/users/{employee_id}", response_model=UserResponse)
def get_user_by_employee_id(
    employee_id: str,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    user = db.query(User).filter(
        User.employee_id == employee_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "employee_id": user.employee_id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "mobile": user.mobile,
        "designation": user.designation,
        "role": user.role,
        "reporting_to": user.reporting_to,
        "HR": user.HR
    }
# ------------------ DELETE USER ------------------
@app.delete("/admin/users/{employee_id}")
def delete_user(
    employee_id: str,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):

    user = db.query(User).filter(
        User.employee_id == employee_id
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ✅ Remove reporting references
    db.query(User).filter(
        User.reporting_to == employee_id
    ).update({"reporting_to": None})

    # ✅ Remove HR references
    db.query(User).filter(
        User.HR == employee_id
    ).update({"HR": None})

    # ✅ Remove client mapping
    db.query(Client).filter(
        Client.employee_id == employee_id
    ).update({"employee_id": None})

    # 🔥 IMPORTANT: Remove leaves
    db.query(Leave).filter(
        Leave.user_id == user.id
    ).delete()

    # ✅ Delete user
    db.delete(user)

    db.commit()

    return {"message": "User deleted successfully"}
@app.get("/users/profile/{employee_id}")
def get_user_profile(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    user = db.query(User).filter(
        User.employee_id == employee_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # ✅ Full name
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

    # ✅ Documents list
    documents = []
    if user.documents:
        documents = user.documents.split(",")

    # ✅ End date logic
    end_date_value = (
        "Currently Working"
        if not user.end_date
        else user.end_date.strftime("%Y-%m-%d")
    )

    return {
        "employee_id": user.employee_id,
        "name": full_name,
        "designation": user.designation,
        "mobile": user.mobile,
        "email": user.email,
        "aadhaar_number": user.aadhaar_number,
        "location": user.location,
        "start_date": user.start_date.strftime("%Y-%m-%d") if user.start_date else None,
        "end_date": end_date_value,
        "photo": user.photo,
        "documents": documents
    }