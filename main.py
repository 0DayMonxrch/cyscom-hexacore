from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
import re
import logging

load_dotenv()

# --- DATABASE SETUP
SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("No SQLALCHEMY_DATABASE_URL set for database connection")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- SQLALCHEMY DATABASE MODEL ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    registration_number = Column(String(9), nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    phone_number = Column(String(15), nullable=False)
    college_name = Column(String(150), nullable=False)
    is_vit = Column(Boolean, default=False)

# Initialize Database Tables (Will create the table if it doesn't exist)
Base.metadata.create_all(bind=engine)

# --- FASTAPI APP INITIALIZATION ---
def get_real_ip(request: Request) -> str:
    # DigitalOcean App Platform uses DO-Connecting-IP
    do_ip = request.headers.get("DO-Connecting-IP")
    if do_ip:
        return do_ip
        
    # Nginx commonly uses X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to X-Forwarded-For
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Note: If your LB appends the real IP, [-1] is correct.
        # If your LB is TCP passthrough, this is still spoofable.
        return forwarded.split(",")[-1].strip()
        
    return request.client.host  

#get_remote_address reads request.client.host. 
#On Render, all requests arrive via their load balancer, so request.client.host is always the same internal proxy IP. 
#This means all users share a single rate limit bucket

limiter = Limiter(
    key_func=get_real_ip,
    storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")
)

app = FastAPI(title="Hexacore Mainframe API", docs_url=None, redoc_url=None) #disable docs in production
app.state.limiter = limiter

def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "RATE_LIMIT_EXCEEDED", "status": "failed"}
    )

app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# Configure CORS to block malicious cross-origin requests
# Reads allowed origins from .env, defaults to localhost for development
frontend_url_env = os.getenv("FRONTEND_URL", "http://localhost:3000")
allowed_origins = [url.strip() for url in frontend_url_env.split(",") if url.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Strictly locked down to specific domains
    allow_credentials=True,
    allow_methods=["POST"], #Minimum surface area
    allow_headers=["*"],
)

from pydantic import BaseModel, EmailStr, Field

class CompetitionRegister(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=100)
    registration_number: str = Field(None, max_length=9)
    email: EmailStr
    phone_number: str = Field(..., min_length=10, max_length=15)
    college_name: str = Field(..., max_length=150)
    is_vit: bool

# --- API ROUTES ---
@app.post("/register-participant", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def register_participant(request: Request, participant: CompetitionRegister):
    db = SessionLocal()
    
    try:
        # 1. Check for duplicate operatives (emails)
        existing_user = db.query(User).filter(User.email == participant.email).first()
        if existing_user:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"error": "ALREADY_REGISTERED", "status": "failed"}
            )
        
        # Backend validation for VIT students
        if participant.is_vit: 
            if not re.fullmatch(r'\d{2}[A-Z]{3}\d{4}', participant.registration_number or ""):
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": "INVALID_REG_ID", "status": "failed"}
                )
        
        # 2. Prepare the new record
        final_reg_number = participant.registration_number if participant.is_vit else "N/A"
        
        new_user = User(
            full_name=participant.full_name,
            registration_number=final_reg_number,
            email=participant.email,
            phone_number=participant.phone_number,
            college_name=participant.college_name,
            is_vit=participant.is_vit
        )
        
        # 3. Commit to the database
        db.add(new_user)
        db.commit()
        
        # Because we set status_code=status.HTTP_201_CREATED in the decorator, 
        # this will return a 201 status code automatically.
        return {"status": "success"}
    
    except HTTPException as he:
        # Catch explicit HTTP exceptions first so they aren't masked by the generic Exception block
        db.rollback()
        raise he
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception("Registration failed")
        db.rollback()
        
        # 500 Internal Server Error returned via JSONResponse
        # This sends the correct HTTP status code while keeping your custom dictionary format
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "INTERNAL_SERVER_ERROR", "status": "failed"}
        )
        
    finally:
        # Always close the connection
        db.close()