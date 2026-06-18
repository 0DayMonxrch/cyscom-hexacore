from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
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
    full_name = Column(String, nullable=False)
    registration_number = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    phone_number = Column(String, nullable=False)
    college_name = Column(String, nullable=False)
    is_vit = Column(Boolean, default=False)

# Initialize Database Tables (Will create the table if it doesn't exist)
Base.metadata.create_all(bind=engine)

# --- FASTAPI APP INITIALIZATION ---
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Hexacore Mainframe API")
app.state.limiter = limiter

def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "RATE_LIMIT_EXCEEDED", "status": "failed"}
    )

app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# Configure CORS to block malicious cross-origin requests
# Reads allowed origins from .env, defaults to localhost for development
frontend_url_env = os.getenv("FRONTEND_URL", "http://localhost:3000,http://127.0.0.1:3000")
allowed_origins = [url.strip() for url in frontend_url_env.split(",") if url.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Strictly locked down to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PYDANTIC VALIDATION SCHEMA ---
# This matches the JSON.stringify payload sent from your register.html exactly
class CompetitionRegister(BaseModel):
    full_name: str
    registration_number: str = None
    email: EmailStr
    phone_number: str
    college_name: str
    is_vit: bool

# --- API ROUTES ---
@app.post("/register-participant")
@limiter.limit("5/hour")
async def register_participant(request: Request, participant: CompetitionRegister):
    db = SessionLocal()
    
    try:
        # 1. Check for duplicate operatives (emails)
        existing_user = db.query(User).filter(User.email == participant.email).first()
        if existing_user:
            return {"error": "OPERATIVE_ALREADY_REGISTERED", "status": "failed"}
        
        # 2. Prepare the new record
        # If they are not from VIT, ensure the registration number is stored cleanly
        final_reg_number = participant.registration_number if participant.is_vit else "N/A"
        
        new_user = User(
            full_name=participant.full_name,
            registration_number=final_reg_number,
            email=participant.email,
            phone_number=participant.phone_number,
            college_name=participant.college_name,
            is_vit=participant.is_vit
        )
        
        # 3. Commit to the Supabase database
        db.add(new_user)
        db.commit()
        
        return {"status": "success"}
        
    except Exception as e:
        # Catch unexpected database errors so the server doesn't crash
        db.rollback()
        return {"error": "INTERNAL_SERVER_ERROR", "status": "failed"}
        
    finally:
        # Always close the connection
        db.close()