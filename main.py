from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- DATABASE SETUP (SUPABASE POSTGRESQL) ---
# Ensure you paste your actual Supabase URI connection string here
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:CyscomHexacore@db.bfnqczjdtqghdtzyqxrt.supabase.co:5432/postgres"

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
app = FastAPI(title="Hexacore Mainframe API")

# Configure CORS to allow your frontend to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any origin (e.g., your local Live Server)
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
async def register_participant(participant: CompetitionRegister):
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