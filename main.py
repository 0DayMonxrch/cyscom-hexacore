from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import random

# --- SETUP ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:CyscomHexacore@db.bfnqczjdtqghdtzyqxrt.supabase.co:5432/postgres"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Temporary memory storage for OTPs (In production, use Redis)
otp_storage = {}

# --- MODELS ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    userid = Column(String, unique=True, index=True)
    password = Column(String)

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserCreate(BaseModel):
    userid: EmailStr
    password: str

class OTPVerify(BaseModel):
    email: str
    otp: str
    purpose: str

class SendOTP(BaseModel):
    email: str
    purpose: str

class UserLogin(BaseModel):
    userid: EmailStr
    password: str

# --- ROUTES ---

@app.post("/register")
async def register(user: UserCreate):
    db = SessionLocal()
    if db.query(User).filter(User.userid == user.userid).first():
        db.close()
        raise HTTPException(status_code=400, detail="User already exists")
    
    hashed_pw = pwd_context.hash(user.password)
    db.add(User(userid=user.userid, password=hashed_pw))
    db.commit()
    db.close()
    return {"status": "success"}

@app.post("/register-email")
async def register_email(user: UserCreate):
    db = SessionLocal()
    if db.query(User).filter(User.userid == user.userid).first():
        db.close()
        raise HTTPException(status_code=400, detail="User already exists")
    db.close()
    
    otp = str(random.randint(100000, 999999))
    otp_storage[user.userid] = {"otp": otp, "password": pwd_context.hash(user.password)}
    print(f"DEBUG: OTP for {user.userid} is {otp}") # Check your terminal!
    return {"status": "otp_sent"}

@app.post("/verify-otp")
async def verify_otp(data: OTPVerify):
    stored = otp_storage.get(data.email)
    
    # Check if OTP exists and matches the input
    if stored and stored["otp"] == data.otp:
        
        # If this is a registration, save them to the database now
        if data.purpose == "register" and "password" in stored:
            db = SessionLocal()
            db.add(User(userid=data.email, password=stored["password"]))
            db.commit()
            db.close()
            
        # If it's a login, we don't need to save anything, just grant access
        
        # Cleanup: Delete the OTP so it can't be reused
        del otp_storage[data.email]
        return {"status": "success"}
        
    return {"error": "Invalid Decryption Key or expired session", "status": "failed"}

@app.post("/send-otp")
async def send_or_resend_otp(data: SendOTP):
    otp = str(random.randint(100000, 999999))
    
    # -- IF LOGGING IN --
    if data.purpose == "login":
        # Ensure the user actually exists in the database first
        db = SessionLocal()
        user_exists = db.query(User).filter(User.userid == data.email).first()
        db.close()
        
        if not user_exists:
            return {"error": "Target email not found in Hexacore database", "status": "failed"}
            
        # Store OTP temporarily
        otp_storage[data.email] = {"otp": otp, "purpose": "login"}
        print(f"DEBUG: LOGIN OTP for {data.email} is {otp}")
        
        # Your JS specifically looks for 'otp_sent' here
        return {"status": "otp_sent"} 
        
    # -- IF RESENDING REGISTRATION OTP --
    elif data.purpose == "register":
        if data.email in otp_storage:
            otp_storage[data.email]["otp"] = otp
            print(f"DEBUG: RESENT REGISTRATION OTP for {data.email} is {otp}")
            return {"status": "success"}
            
    return {"error": "Session expired", "status": "failed"}


# The Login Route
@app.post("/login")
async def login(user: UserLogin):
    db = SessionLocal()
    db_user = db.query(User).filter(User.userid == user.userid).first()
    db.close()
    
    # Check if user exists AND if the password matches the hash
    if not db_user or not pwd_context.verify(user.password, db_user.password):
        return {"error": "Access Denied: Invalid credentials", "status": "failed"}
    
    return {"status": "success"}