from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from auth import router as auth_router
from database import engine, get_db
from db_dependencies import admin_only
from schemas import UserCreate, UserResponse, UserLimitedUpdate, ClientCreate, ClientResponse, ReportCreate
from schemas import ClientUpdate, ApplicationUpdate, SourceLinksRequest, SourceLink
from security import hash_password
from db_dependencies import get_db, admin_only, get_current_user
from models import Base, User, Client, Application, Credential, Reports
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
from timesheet_models import Leave
from fastapi import Query
from fastapi.responses import FileResponse
import os
from fastapi.staticfiles import StaticFiles
from fastapi import UploadFile, File
from typing import List
from sqlalchemy import distinct

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
    "https://pathway.msstechno.com",
          
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
                            "notes":{"type":"string"}
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
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    # ✅ SAVE TO DATABASE
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
    }
#------------------update client---------------------------
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
    notes: Optional[str] = Form(None),

    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    # ✅ Check client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    try:
        # ✅ Update only provided fields
        if client_name is not None:
            client.client_name = client_name

        if mobile is not None:
            client.mobile = mobile

        if technology is not None:
            client.technology = technology

        if status is not None:
            client.status = status

        if employee_id is not None:
            client.employee_id = employee_id

        if professional_role is not None:
            client.professional_role = professional_role

        if aadhaar_number is not None:
            client.aadhaar_number = aadhaar_number

        if location is not None:
            client.location = location

        if email is not None:
            client.email = email

        db.commit()
        db.refresh(client)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "message": "Client updated successfully",
        "client_id": client.id
    }

#----------------------to add source links---------------
@router.post("/clients/{client_id}/add-source-links")
def add_source_links(
    client_id: int,
    request: SourceLinksRequest,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    clean_links = []

    for item in request.links:
        # extra safety (even though Pydantic validates)
        if item.link and item.link_type:
            clean_links.append(f"{item.link}::{item.link_type}")

    existing = client.source_links.split(",") if client.source_links else []

    # جلوگیری duplicates
    all_links = list(set(existing + clean_links))

    client.source_links = ",".join(all_links)

    db.commit()
    db.refresh(client)

    formatted = [
        {"link": entry.split("::")[0], "link_type": entry.split("::")[1]}
        for entry in all_links if "::" in entry
    ]

    return {
        "message": "Source links added successfully",
        "client_id": client.id,
        "source_links": formatted
    }

#--------------get source link---------------------

@router.get("/clients/{client_id}/source-links")
def get_source_links(
    client_id: int,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    raw_links = client.source_links.split(",") if client.source_links else []

    formatted = [
        {"link": entry.split("::")[0], "link_type": entry.split("::")[1]}
        for entry in raw_links if "::" in entry
    ]

    return {
        "client_id": client.id,
        "source_links": formatted
    }
#-----------------------delete source link-------------
@router.delete("/clients/{client_id}/delete-source-link")
def delete_source_link(
    client_id: int,
    link: str,  # only URL
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.source_links:
        raise HTTPException(status_code=400, detail="No links to delete")

    existing = client.source_links.split(",")

    # remove by matching URL part
    updated_links = [
        l for l in existing if not l.startswith(link + "::")
    ]

    if len(existing) == len(updated_links):
        raise HTTPException(status_code=404, detail="Link not found")

    client.source_links = ",".join(updated_links) if updated_links else None

    db.commit()
    db.refresh(client)

    return {
        "message": "Source link deleted successfully",
        "client_id": client.id,
        "source_links": updated_links
    }

#-----------------client profile------------------------
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

    # ✅ BASE URL (PRODUCTION SAFE)
    base_url = "https://timesheet-api-790373899641.asia-south1.run.app"

    # ✅ PHOTO URL
    photo_url = None
    if client.photo:
        filename = client.photo.split("/")[-1]
        photo_url = f"{base_url}/clients/photos/{filename}?t={int(time.time())}"

    # ✅ DOCUMENTS
    documents_list = []
    if client.documents:
        for doc in client.documents.split(","):
            filename = doc.split("/")[-1]

            documents_list.append({
                "file_name": filename,
                "view_url": f"{base_url}/clients/documents/{filename}",
                "download_url": f"{base_url}/clients/documents/{filename}?download=true"
            })

    return {
        "client_id": client.id,
        "client_name": client.client_name,
        "professional_role": client.professional_role,
        "mobile": client.mobile,
        "email": client.email,
        "aadhaar_number": client.aadhaar_number,
        "location": client.location,

        "photo": photo_url,
        "documents": documents_list
    }
#--------------------get clients----------------------------

@router.get("/clients", response_model=list[ClientResponse])
def get_clients(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # 🔹 Get logged-in user
    user = db.query(User).filter(User.id == current_user["id"]).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 🔹 Role-based filtering (UNCHANGED)
    if current_user["role"] == "admin":
        clients = db.query(Client).all()
    else:
        clients = db.query(Client).filter(
            Client.employee_id == user.employee_id
        ).all()

    # 🔹 Build response with employee name
    response = []

    for client in clients:
        emp_user = db.query(User).filter(
            User.employee_id == client.employee_id
        ).first()

        employee_name = None
        if emp_user:
            employee_name = f"{emp_user.first_name or ''} {emp_user.last_name or ''}".strip()

        response.append({
            "id": client.id,
            "client_name": client.client_name,
            "mobile": client.mobile,
            "email": client.email,
            "technology": client.technology,
            "status": client.status,
            "employee_id": client.employee_id,
            "employee_name": employee_name,  # 👈 replaced
            "professional_role": client.professional_role,
            "aadhaar_number": client.aadhaar_number,
            "location": client.location,
            "notes":client.notes

        })

    return response

#------------------get client by id--------------------
@router.get("/clients/{client_id}", response_model=ClientResponse)
def get_client_by_id(
    client_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # 🔹 Get logged-in user
    user = db.query(User).filter(User.id == current_user["id"]).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 🔹 Get client
    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # 🔐 Role-based access check
    if current_user["role"] != "admin":
        if client.employee_id != user.employee_id:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to access this client"
            )

    # 🔹 Get employee details from users table
    emp_user = db.query(User).filter(
        User.employee_id == client.employee_id
    ).first()

    employee_name = None
    if emp_user:
        employee_name = f"{emp_user.first_name or ''} {emp_user.last_name or ''}".strip()

    # 🔹 Return mapped response
    return {
        "id": client.id,
        "client_name": client.client_name,
        "mobile": client.mobile,
        "email": client.email,
        "technology": client.technology,
        "status": client.status,
        "professional_role": client.professional_role,
        "aadhaar_number": client.aadhaar_number,
        "location": client.location,
        "employee_id": client.employee_id,   # ✅ keep
        "employee_name": employee_name,
        "notes":client.notes
    }
#--------------------------delete client-----------------------
@router.delete("/clients/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    
    db.query(Application).filter(Application.client_id == client_id).delete()

    
    db.delete(client)
    db.commit()

    return {"message": "Client deleted successfully"}
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

        company_key = r.company_name.lower().strip()  
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

    
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    applications_data = db.query(
        Application.platform,   
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
#------------------documents apis---------------------------------------------

import os
import uuid
import datetime
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from google.cloud import storage

from database import get_db
from models import Client


documents_router = APIRouter(prefix="/documents", tags=["Documents"])

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "client-documents-uploads")

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".xlsx", ".csv", ".txt"}
MAX_FILE_SIZE_MB = 10


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def validate_file(file: UploadFile):
    ext = os.path.splitext(file.filename)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File '{file.filename}' has unsupported extension '{ext}'. Allowed: {ALLOWED_EXTENSIONS}"
        )


def upload_to_gcs(content: bytes, destination_blob_name: str, content_type: str) -> str:
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(content, content_type=content_type)
    return f"gs://{GCS_BUCKET_NAME}/{destination_blob_name}"


def generate_public_url(gcs_path: str) -> str | None:
    """Convert gs://bucket/path to public HTTPS URL."""
    if not gcs_path or not gcs_path.startswith("gs://"):
        return None
    path = gcs_path[5:]
    if "/" not in path:
        return None
    bucket_name, blob_name = path.split("/", 1)
    return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"


def parse_gcs_path(gcs_path: str) -> tuple[str, str]:
    """Return (bucket_name, blob_name) from a gs:// path."""
    if not gcs_path.startswith("gs://"):
        raise ValueError("Invalid GCS path — must start with gs://")
    parts = gcs_path[5:].split("/", 1)
    if len(parts) != 2:
        raise ValueError("Invalid GCS path — missing blob name")
    return parts[0], parts[1]


def generate_signed_url(gcs_path: str, expiration_seconds: int = 3600) -> str:
    """
    Generate a v4 signed URL.
    NOTE: Requires a service-account key JSON (GOOGLE_APPLICATION_CREDENTIALS).
    On Cloud Run with default compute SA this will FAIL — use stream_download() instead.
    """
    import google.auth
    import google.auth.transport.requests
    from google.oauth2 import service_account

    bucket_name, blob_name = parse_gcs_path(gcs_path)

    # Try explicit service account key first (set via env var SA_KEY_PATH or SA_KEY_JSON)
    sa_key_path = os.getenv("SA_KEY_PATH")
    sa_key_json = os.getenv("SA_KEY_JSON")

    if sa_key_json:
        import json
        info = json.loads(sa_key_json)
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    elif sa_key_path:
        credentials = service_account.Credentials.from_service_account_file(
            sa_key_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    else:
        raise RuntimeError(
            "Signed URLs require a service-account key. "
            "Set SA_KEY_JSON or SA_KEY_PATH env var, or use the /download endpoint which streams directly."
        )

    storage_client = storage.Client(credentials=credentials)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(seconds=expiration_seconds),
        method="GET",
    )


def delete_from_gcs(gcs_path: str):
    bucket_name, blob_name = parse_gcs_path(gcs_path)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.delete()


def filename_from_path(gcs_path: str) -> str:
    return gcs_path.rstrip("/").split("/")[-1]


# ─────────────────────────────────────────
# UPLOAD
# ─────────────────────────────────────────
@documents_router.post("/clients/{client_id}/upload-documents")
async def upload_documents(
    client_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    admin=Depends(admin_only),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    safe_name = client.client_name.strip().replace(" ", "-").lower()
    folder_name = f"documents/clients/{client.id}-{safe_name}"

    uploaded_paths: list[dict] = []
    failed_files: list[dict] = []

    for file in files:
        try:
            validate_file(file)

            content = await file.read()
            size_mb = len(content) / (1024 * 1024)

            if size_mb > MAX_FILE_SIZE_MB:
                failed_files.append({
                    "filename": file.filename,
                    "error": f"Exceeds {MAX_FILE_SIZE_MB}MB limit (got {size_mb:.2f}MB)",
                })
                continue

            ext = os.path.splitext(file.filename)[-1].lower()
            original_stem = os.path.splitext(file.filename)[0]
            unique_name = f"{original_stem}_{uuid.uuid4().hex}{ext}"
            blob_path = f"{folder_name}/{unique_name}"

            gcs_path = upload_to_gcs(
                content, blob_path, file.content_type or "application/octet-stream"
            )

            uploaded_paths.append({
                "filename": unique_name,          # ← only filename returned
                "original_name": file.filename,
                "path": gcs_path,
                "size_mb": round(size_mb, 2),
            })

        except HTTPException as e:
            failed_files.append({"filename": file.filename, "error": e.detail})
        except Exception as e:
            failed_files.append({"filename": file.filename, "error": str(e)})

    if uploaded_paths:
        existing = (
            [p for p in client.documents.split(",") if p.strip()]
            if client.documents
            else []
        )
        new_paths = [f["path"] for f in uploaded_paths]
        client.documents = ",".join(existing + new_paths)
        db.commit()
        db.refresh(client)

    return {
        "message": "Upload complete",
        "client_id": client_id,
        "uploaded": uploaded_paths,
        "failed": failed_files,
        "total_uploaded": len(uploaded_paths),
        "total_failed": len(failed_files),
    }


# ─────────────────────────────────────────
# GET DOCUMENTS  — filename only
# ─────────────────────────────────────────
@documents_router.get("/clients/{client_id}/documents")
def get_client_documents(
    client_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.documents:
        return {"client_id": client_id, "total": 0, "documents": []}

    paths = [p.strip() for p in client.documents.split(",") if p.strip()]

    documents = []
    for path in paths:
        if not path.startswith("gs://"):
            continue
        documents.append({
            "filename": filename_from_path(path),   # ← ONLY the filename
            "gcs_path": path,                        # kept so frontend can pass it to delete/download
        })

    return {
        "client_id": client_id,
        "total": len(documents),
        "documents": documents,
    }


# ─────────────────────────────────────────
# VIEW DOCUMENT  — streams file inline for browser preview
# ─────────────────────────────────────────
VIEWABLE_INLINE = {
    "pdf":  "application/pdf",
    "png":  "image/png",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "txt":  "text/plain",
}

# These need Google Docs Viewer (can't render natively in browser)
GOOGLE_DOCS_VIEWABLE = {"doc", "docx", "xlsx", "csv"}


@documents_router.get("/clients/{client_id}/view-documents")
def view_client_documents(
    client_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Returns a list of documents with a `view_url` per file:
    - PDF / images / txt  → `/documents/view?gcs_path=...`  (streams inline)
    - doc / docx / xlsx   → Google Docs Viewer URL (opens in browser tab)
    - others              → falls back to the download endpoint
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.documents:
        return {"client_id": client_id, "total": 0, "documents": []}

    paths = [p.strip() for p in client.documents.split(",") if p.strip()]

    documents = []
    for path in paths:
        if not path.startswith("gs://"):
            continue
        fname = filename_from_path(path)
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        encoded_path = path  # frontend encodes when building the URL

        if ext in VIEWABLE_INLINE:
            # Served inline by our /view endpoint
            view_url = f"/documents/view?gcs_path={encoded_path}"
            viewer = "inline"
        elif ext in GOOGLE_DOCS_VIEWABLE:
            # Public URL is needed for Google Docs Viewer
            public_url = generate_public_url(path)
            view_url = f"https://docs.google.com/viewer?url={public_url}&embedded=true"
            viewer = "google_docs"
        else:
            # Unknown type — offer download instead
            view_url = f"/documents/download?gcs_path={encoded_path}"
            viewer = "download"

        documents.append({
            "filename": fname,
            "file_type": ext,
            "gcs_path": path,
            "view_url": view_url,
            "viewer": viewer,      # tells frontend HOW to open it
        })

    return {"client_id": client_id, "total": len(documents), "documents": documents}


@documents_router.get("/view")
def view_file_inline(
    gcs_path: str,
    user=Depends(get_current_user),
):
    if not gcs_path or not gcs_path.startswith("gs://"):
        raise HTTPException(status_code=400, detail="Invalid or missing gcs_path")

    try:
        # ✅ Use correct parser
        bucket_name, blob_name = parse_gcs_path(gcs_path)

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if not blob.exists():
            raise HTTPException(status_code=404, detail="File not found in GCS")

        blob.reload()

        fname = filename_from_path(gcs_path)
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""

        content_type = VIEWABLE_INLINE.get(
            ext,
            blob.content_type or "application/octet-stream"
        )

        from fastapi.responses import StreamingResponse

        # ✅ DIRECT STREAM (no memory issue)
        return StreamingResponse(
            blob.open("rb"),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{fname}"',
                "Cache-Control": "private, max-age=3600",
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"View failed: {str(e)}")
# ─────────────────────────────────────────
# DOWNLOAD  — streams file directly from GCS
# Works on Cloud Run with NO signed-URL / no SA key needed
# ─────────────────────────────────────────
@documents_router.get("/download")
def download_file(
    gcs_path: str,
    user=Depends(get_current_user),
):
    """
    Streams file from GCS as a download (Cloud Run safe).
    """
    if not gcs_path or not gcs_path.startswith("gs://"):
        raise HTTPException(status_code=400, detail="Invalid or missing gcs_path")

    try:
        # ✅ Correct parsing
        bucket_name, blob_name = parse_gcs_path(gcs_path)

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if not blob.exists():
            raise HTTPException(status_code=404, detail="File not found in GCS")

        blob.reload()

        fname = filename_from_path(gcs_path)
        content_type = blob.content_type or "application/octet-stream"

        from fastapi.responses import StreamingResponse

        # ✅ DIRECT STREAM (no memory load)
        return StreamingResponse(
            blob.open("rb"),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{fname}"',
                "Cache-Control": "no-cache",
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
# ─────────────────────────────────────────
# DELETE DOCUMENT
# ─────────────────────────────────────────
@documents_router.delete("/clients/{client_id}/documents")
def delete_client_document(
    client_id: int,
    gcs_path: str,                                  # query param: ?gcs_path=gs://bucket/path
    db: Session = Depends(get_db),
    admin=Depends(admin_only),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    existing = (
        [p.strip() for p in client.documents.split(",") if p.strip()]
        if client.documents
        else []
    )

    if gcs_path not in existing:
        raise HTTPException(status_code=404, detail="Document not found for this client")

    # 1. Delete from GCS
    try:
        delete_from_gcs(gcs_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete from GCS: {e}")

    # 2. Remove from DB
    updated = [p for p in existing if p != gcs_path]
    client.documents = ",".join(updated)
    db.commit()

    return {
        "message": "Document deleted successfully",
        "deleted_filename": filename_from_path(gcs_path),
    }

# ─────────────────────────────────────────
# ALLOWED TYPES FOR PROFILE PICTURE
# ─────────────────────────────────────────
import os
import uuid
import io
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from google.cloud import storage

from database import get_db
from models import Client


ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_PROFILE_PIC_SIZE_MB = 5
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "client-documents-uploads")


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def delete_from_gcs(gcs_path: str):
    """Delete a blob from GCS silently."""
    try:
        parts = gcs_path[5:].split("/", 1)
        storage_client = storage.Client()
        bucket = storage_client.bucket(parts[0])
        blob = bucket.blob(parts[1])
        blob.delete()
    except Exception as e:
        print(f"GCS delete warning: {e}")


def gcs_blob_from_path(gcs_path: str):
    """Return a GCS Blob object from a gs:// path."""
    bucket_name, blob_name = gcs_path[5:].split("/", 1)
    storage_client = storage.Client()
    return storage_client.bucket(bucket_name).blob(blob_name)


# ─────────────────────────────────────────
# UPLOAD PROFILE PICTURE
# ─────────────────────────────────────────
@documents_router.post("/clients/{client_id}/profile-picture")
async def upload_profile_picture(
    client_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin=Depends(admin_only),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    ext = os.path.splitext(file.filename)[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Allowed: {ALLOWED_IMAGE_EXTENSIONS}",
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_PROFILE_PIC_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.2f}MB). Max: {MAX_PROFILE_PIC_SIZE_MB}MB",
        )

    # Delete old picture
    if client.profile_picture and client.profile_picture.startswith("gs://"):
        delete_from_gcs(client.profile_picture)

    # Upload new picture
    safe_name = client.client_name.strip().replace(" ", "-").lower()
    unique_name = f"profile_{uuid.uuid4().hex}{ext}"
    blob_path = f"profile-pictures/clients/{client.id}-{safe_name}/{unique_name}"

    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(content, content_type=file.content_type or "image/jpeg")

    gcs_path = f"gs://{GCS_BUCKET_NAME}/{blob_path}"
    client.profile_picture = gcs_path
    db.commit()
    db.refresh(client)

    return {
        "message": "Profile picture uploaded successfully",
        "client_id": client_id,
        # ✅ Use this URL directly in <img src="...">
        "profile_picture_url": f"/documents/clients/{client_id}/profile-picture/view",
        "size_mb": round(size_mb, 2),
    }


# ─────────────────────────────────────────
# GET PROFILE PICTURE  (metadata)
# ─────────────────────────────────────────
@documents_router.get("/clients/{client_id}/profile-picture")
def get_profile_picture(
    client_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.profile_picture:
        raise HTTPException(status_code=404, detail="No profile picture found")

    return {
        "client_id": client_id,
        # ✅ Point your <img src> at this URL — it streams the actual image bytes
        "profile_picture_url": f"/documents/clients/{client_id}/profile-picture/view",
        "gcs_path": client.profile_picture,
    }

# ─────────────────────────────────────────
# VIEW / STREAM PROFILE PICTURE
# Use this directly as <img src="BASE_URL/documents/clients/7/profile-picture/view">
# ─────────────────────────────────────────
@documents_router.get("/clients/{client_id}/profile-picture/view")
def view_profile_picture(
    client_id: int,
    db: Session = Depends(get_db),
):
    """
    Streams latest profile image (no caching).
    Always returns fresh image from GCS.
    """

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.profile_picture:
        raise HTTPException(status_code=404, detail="No profile picture found")

    try:
        blob = gcs_blob_from_path(client.profile_picture)

        if not blob.exists():
            raise HTTPException(status_code=404, detail="Image not found in storage")

        blob.reload()
        content_type = blob.content_type or "image/jpeg"

        buf = io.BytesIO()
        blob.download_to_file(buf)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type=content_type,
            headers={
                # 🚫 Disable caching completely
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",

                # ✅ Display in browser
                "Content-Disposition": "inline",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load image: {e}")
# ─────────────────────────────────────────
# DELETE PROFILE PICTURE
# ─────────────────────────────────────────
@documents_router.delete("/clients/{client_id}/profile-picture")
def delete_profile_picture(
    client_id: int,
    db: Session = Depends(get_db),
    admin=Depends(admin_only),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.profile_picture:
        raise HTTPException(status_code=404, detail="No profile picture to delete")

    delete_from_gcs(client.profile_picture)
    client.profile_picture = None
    db.commit()

    return {"message": "Profile picture deleted successfully", "client_id": client_id}

#------for employess documents upload APIS-----


#-----------------------add employee document--------
@documents_router.post("/employees/{employee_id}/upload-documents")
async def upload_employee_documents(
    employee_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    admin=Depends(admin_only),
):
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    safe_name = f"{user.first_name or ''}-{user.last_name or ''}".strip().replace(" ", "-").lower()
    folder_name = f"documents/employees/{user.employee_id}-{safe_name}"

    uploaded_paths = []
    failed_files = []

    for file in files:
        try:
            validate_file(file)

            content = await file.read()
            size_mb = len(content) / (1024 * 1024)

            if size_mb > MAX_FILE_SIZE_MB:
                failed_files.append({"filename": file.filename, "error": "File too large"})
                continue

            ext = os.path.splitext(file.filename)[-1].lower()
            unique_name = f"{uuid.uuid4().hex}{ext}"
            blob_path = f"{folder_name}/{unique_name}"

            gcs_path = upload_to_gcs(content, blob_path, file.content_type)

            uploaded_paths.append({
                "filename": unique_name,
                "path": gcs_path
            })

        except Exception as e:
            failed_files.append({"filename": file.filename, "error": str(e)})

    if uploaded_paths:
        existing = user.documents.split(",") if user.documents else []
        user.documents = ",".join(existing + [f["path"] for f in uploaded_paths])
        db.commit()

    return {"uploaded": uploaded_paths, "failed": failed_files}
#-------------------get employee document---------------
@documents_router.get("/employees/{employee_id}/documents")
def get_employee_documents(employee_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not user.documents:
        return {"documents": []}

    paths = [p.strip() for p in user.documents.split(",") if p.strip()]

    return {
        "documents": [{"filename": filename_from_path(p), "gcs_path": p} for p in paths]
    }
#-----------------------------view employee document----------

@documents_router.get("/employees/{employee_id}/view-document")
def view_employee_document(
    employee_id: str,
    gcs_path: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user_obj = db.query(User).filter(User.employee_id == employee_id).first()

    if not user_obj:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not gcs_path.startswith("gs://"):
        raise HTTPException(status_code=400, detail="Invalid gcs_path")

    try:
        bucket_name, blob_name = parse_gcs_path(gcs_path)

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if not blob.exists():
            raise HTTPException(status_code=404, detail="File not found")

        blob.reload()

        fname = filename_from_path(gcs_path)
        ext = fname.split(".")[-1].lower()

        content_type = VIEWABLE_INLINE.get(
            ext,
            blob.content_type or "application/octet-stream"
        )

        from fastapi.responses import StreamingResponse

        return StreamingResponse(
            blob.open("rb"),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{fname}"',
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
#---------------------------------delete employee document-----------
@documents_router.delete("/employees/{employee_id}/documents")
def delete_employee_document(
    employee_id: str,
    gcs_path: str,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    existing = user.documents.split(",") if user.documents else []

    if gcs_path not in existing:
        raise HTTPException(status_code=404, detail="Document not found")

    delete_from_gcs(gcs_path)

    user.documents = ",".join([p for p in existing if p != gcs_path])
    db.commit()

    return {"message": "Deleted successfully"}

#--------------download document-----------------------
@documents_router.get("/employees/{employee_id}/download-document")
def download_employee_document(
    employee_id: str,
    gcs_path: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user_obj = db.query(User).filter(User.employee_id == employee_id).first()

    if not user_obj:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not gcs_path.startswith("gs://"):
        raise HTTPException(status_code=400, detail="Invalid gcs_path")

    try:
        bucket_name, blob_name = parse_gcs_path(gcs_path)

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if not blob.exists():
            raise HTTPException(status_code=404, detail="File not found")

        blob.reload()

        fname = filename_from_path(gcs_path)
        content_type = blob.content_type or "application/octet-stream"

        from fastapi.responses import StreamingResponse

        return StreamingResponse(
            blob.open("rb"),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{fname}"',
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
#---------------upload profile photo for employee--------   
@documents_router.put("/employees/{employee_id}/upload-profile-pic")
async def upload_employee_profile_pic(
    employee_id: str,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    ext = os.path.splitext(photo.filename)[-1].lower()

    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="Invalid image format")

    content = await photo.read()

    file_name = f"profile_{uuid.uuid4().hex}{ext}"
    blob_path = f"employees/profile/{user.employee_id}/{file_name}"

    gcs_path = upload_to_gcs(content, blob_path, photo.content_type)

    user.profile_pic = gcs_path
    db.commit()

    return {"profile_pic": gcs_path}
#---------------------get employee profile pic-------------

@documents_router.get("/employees/{employee_id}/profile-pic")
def get_employee_profile_pic(
    employee_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    user_obj = db.query(User).filter(User.employee_id == employee_id).first()

    if not user_obj:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not user_obj.profile_pic:
        raise HTTPException(status_code=404, detail="No profile picture found")

    try:
        bucket_name, blob_name = parse_gcs_path(user_obj.profile_pic)

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if not blob.exists():
            raise HTTPException(status_code=404, detail="File not found in GCS")

        blob.reload()

        content_type = blob.content_type or "image/jpeg"

        from fastapi.responses import StreamingResponse

        return StreamingResponse(
            blob.open("rb"),
            media_type=content_type,
            headers={
                "Content-Disposition": "inline",
                "Cache-Control": "no-cache",
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#-----------------delete profile pic----------------------

@documents_router.delete("/employees/{employee_id}/profile-pic")
def delete_employee_profile_pic(employee_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not user.profile_pic:
        raise HTTPException(status_code=404, detail="No profile picture found")

    delete_from_gcs(user.profile_pic)

    deleted_file = filename_from_path(user.profile_pic)

    user.profile_pic = None
    db.commit()

    return {"message": "Deleted", "deleted_file": deleted_file}
# ------------------ CREATE APP ------------------


app.include_router(auth_router)
app.include_router(router, prefix="/clients", tags=["Clients"])
app.include_router(application_router)
app.include_router(Credential_router)
app.include_router(reports_router)
app.include_router(auth_router)
app.include_router(timesheet_router)
app.include_router(calendar_router)
app.include_router(documents_router)
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
    

@app.post("/admin/users", response_model=UserResponse)
def create_user(
    
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("user"),
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    mobile: Optional[str] = Form(None),
    designation: Optional[str] = Form(None),

    
    reporting_to: Optional[str] = Form(None),
    HR: Optional[str] = Form(None),

    
    aadhaar_number: Optional[str] = Form(None),
    start_date: Optional[date] = Form(None),
    end_date: Optional[str] = Form(None),  
    location: Optional[str] = Form(None),

    
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):

    
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    
    employee_id = generate_employee_id(db)

    
    if reporting_to:
        manager = db.query(User).filter(User.employee_id == reporting_to).first()
        if not manager:
            raise HTTPException(status_code=400, detail="Reporting manager not found")

    
    if HR:
        hr = db.query(User).filter(User.employee_id == HR).first()
        if not hr:
            raise HTTPException(status_code=400, detail="HR not found")

    
    if aadhaar_number:
        if not aadhaar_number.isdigit() or len(aadhaar_number) != 12:
            raise HTTPException(
                status_code=400,
                detail="Aadhaar must be exactly 12 digits"
            )

    
    parsed_end_date = None
    is_active = True

    if end_date:
        if end_date.lower() == "currently working":
            parsed_end_date = None
            is_active = True
        else:
            try:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                is_active = False
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="end_date must be YYYY-MM-DD or 'currently working'"
                )

    
    if start_date and parsed_end_date and parsed_end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="End date cannot be before start date"
        )

    
    hashed_password = hash_password(password)


    new_user = User(
        employee_id=employee_id,
        email=email,
        password_hash=hashed_password,
        role=role,
        first_name=first_name,
        last_name=last_name,
        mobile=mobile,
        designation=designation,

        reporting_to=reporting_to,
        HR=HR,

        aadhaar_number=aadhaar_number,
        start_date=start_date,
        end_date=parsed_end_date,  
        location=location,
        is_active=is_active
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
    email: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    mobile: Optional[str] = Form(None),
    designation: Optional[str] = Form(None),

    # Relations
    reporting_to: Optional[str] = Form(None),
    HR: Optional[str] = Form(None),

    # Fields
    aadhaar_number: Optional[str] = Form(None),
    start_date: Optional[date] = Form(None),
    end_date: Optional[str] = Form(None),  # ✅ string like create
    location: Optional[str] = Form(None),

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

    # ✅ Reporting manager validation
    if reporting_to:
        manager = db.query(User).filter(User.employee_id == reporting_to).first()
        if not manager:
            raise HTTPException(status_code=400, detail="Reporting manager not found")
        user.reporting_to = reporting_to

    # ✅ HR validation
    if HR:
        hr = db.query(User).filter(User.employee_id == HR).first()
        if not hr:
            raise HTTPException(status_code=400, detail="HR not found")
        user.HR = HR

    # ✅ Aadhaar validation
    if aadhaar_number:
        if not aadhaar_number.isdigit() or len(aadhaar_number) != 12:
            raise HTTPException(
                status_code=400,
                detail="Aadhaar must be exactly 12 digits"
            )
        user.aadhaar_number = aadhaar_number

    # ✅ End date parsing (same as create)
    parsed_end_date = user.end_date
    is_active = user.is_active

    if end_date is not None:
        if end_date.lower() == "currently working":
            parsed_end_date = None
            is_active = True
        else:
            try:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                is_active = False
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="end_date must be YYYY-MM-DD or 'currently working'"
                )

    # ✅ Start date validation
    if start_date and parsed_end_date and parsed_end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="End date cannot be before start date"
        )

    # Update dates
    if start_date:
        user.start_date = start_date
    user.end_date = parsed_end_date
    user.is_active = is_active

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


#------------------get by employee id---------------------
@app.get("/admin/users/{employee_id}")
def get_user_by_employee_id(
    employee_id: str,
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    user = db.query(User).filter(User.employee_id == employee_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "data": {
            "employee_id": user.employee_id,
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
            "location": user.location
        }
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
    '''db.query(leaves).filter(
        Leave.user_id == user.id
    ).delete()'''

    # ✅ Delete user
    db.delete(user)

    db.commit()

    return {"message": "User deleted successfully"}

#-----------get users table-----------------
@app.get("/admin/users-table")
def get_all_users(
    db: Session = Depends(get_db),
    admin=Depends(admin_only)
):
    users = db.query(User).all()

    result = []

    for user in users:
        # 👇 get reporting manager name
        reporting_name = None
        if user.reporting_to:
            manager = db.query(User).filter(
                User.employee_id == user.reporting_to
            ).first()

            if manager:
                reporting_name = f"{manager.first_name or ''} {manager.last_name or ''}".strip()

        result.append({
            "employee_id": user.employee_id,
            "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "mobile": user.mobile,
            "email": user.email,
            "reporting_to": reporting_name
        })

    return result

@app.get("/employee-ids", response_model=list[str])
def get_employee_ids(db: Session = Depends(get_db)):
    
    employee_ids = (
        db.query(User.employee_id)
        .distinct()
        .order_by(User.employee_id.asc())   # ✅ SORTING
        .all()
    )

    return [emp_id[0] for emp_id in employee_ids if emp_id[0]]