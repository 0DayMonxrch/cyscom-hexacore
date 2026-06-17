import uvicorn
import os
import random
import string
import smtplib
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from datetime import datetime, timedelta
from passlib.context import CryptContext

SQLALCHEMY_DATABASE_URL = "sqlite:///./users.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    userid = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OTPStore(Base):
    __tablename__ = "otp_store"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    otp_hash = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, default=0)
    used = Column(Boolean, default=False)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed: str) -> bool:
    return pwd_context.verify(plain_password, hashed)


def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()


SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "cyscomvit@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "AJAXcyscom.1234")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_otp_email(to_email: str, otp: str, purpose: str):
    subject = "Your OTP" if purpose == "login" else "Verify your email"
    body = f"""Hi,

Your One-Time Password (OTP) is: {otp}

This OTP is valid for 10 minutes.
Do NOT share it with anyone.

-- AJAX Auth System"""
    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


app = FastAPI()


class RegisterRequest(BaseModel):
    userid: str
    password: str


class LoginRequest(BaseModel):
    userid: str
    password: str


class SendOTPRequest(BaseModel):
    email: str
    purpose: str


class VerifyOTPRequest(BaseModel):
    email: str
    otp: str
    purpose: str


class EmailLoginRequest(BaseModel):
    email: str
    password: str


@app.post("/register")
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    existing = db.query(User).filter(User.userid == request.userid).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    hashed = hash_password(request.password)
    user = User(userid=request.userid, hashed_password=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": "success", "user": user.userid, "id": user.id}


@app.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.userid == request.userid).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"status": "success", "user": user.userid, "id": user.id}


@app.post("/register-email")
async def register_email(request: RegisterRequest, db: Session = Depends(get_db)):
    email = request.userid.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Please provide a valid email address")
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    existing = db.query(User).filter(User.userid == email).first()
    if existing and existing.email_verified:
        raise HTTPException(status_code=400, detail="User already exists")
    if not existing:
        hashed = hash_password(request.password)
        user = User(userid=email, hashed_password=hashed, email=email, email_verified=False)
        db.add(user)
        db.commit()

    db.query(OTPStore).filter(
        OTPStore.email == email,
        OTPStore.purpose == "register",
        OTPStore.used == False
    ).delete(synchronize_session=False)
    db.commit()

    otp = generate_otp()
    record = OTPStore(
        email=email,
        otp_hash=hash_otp(otp),
        purpose="register",
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(record)
    db.commit()

    send_otp_email(email, otp, "register")
    return {
        "status": "otp_sent",
        "message": "OTP sent to your email. Please verify to complete registration."
    }


@app.post("/send-otp")
async def send_otp(request: SendOTPRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    purpose = request.purpose

    if purpose not in ("register", "login"):
        raise HTTPException(status_code=400, detail="Invalid purpose")

    if purpose == "login":
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return {
                "status": "otp_sent",
                "message": "If this email is registered, an OTP has been sent."
            }

    one_min_ago = datetime.utcnow() - timedelta(minutes=1)

    recent = db.query(OTPStore).filter(
        OTPStore.email == email,
        OTPStore.purpose == purpose,
        OTPStore.expires_at > one_min_ago
    ).count()

    if recent >= 3:
        raise HTTPException(
            status_code=429,
            detail="Too many OTP requests. Please wait before trying again."
        )

    db.query(OTPStore).filter(
        OTPStore.email == email,
        OTPStore.purpose == purpose,
        OTPStore.used == False
    ).delete(synchronize_session=False)
    db.commit()

    otp = generate_otp()

    record = OTPStore(
        email=email,
        otp_hash=hash_otp(otp),
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(record)
    db.commit()

    send_otp_email(email, otp, purpose)

    return {
        "status": "otp_sent",
        "message": "OTP sent to your email."
    }


@app.post("/verify-otp")
async def verify_otp(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()
    purpose = request.purpose

    record = db.query(OTPStore).filter(
        OTPStore.email == email,
        OTPStore.purpose == purpose,
        OTPStore.used == False,
        OTPStore.expires_at > datetime.utcnow()
    ).order_by(OTPStore.id.desc()).first()

    if not record:
        raise HTTPException(
            status_code=400,
            detail="OTP expired or not found. Request a new one."
        )

    if record.attempts >= 5:
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Request a new OTP."
        )

    if record.otp_hash != hash_otp(request.otp):
        record.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP")

    record.used = True
    db.commit()

    if purpose == "register":
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.email_verified = True
            db.commit()

        return {
            "status": "verified",
            "message": "Email verified. Registration complete.",
            "user": email
        }

    elif purpose == "login":
        user = db.query(User).filter(User.email == email).first()

        if not user or not user.email_verified:
            raise HTTPException(
                status_code=401,
                detail="Email not registered or not verified."
            )

        return {
            "status": "success",
            "user": user.userid,
            "id": user.id
        }


@app.post("/login-email")
async def login_email(request: EmailLoginRequest, db: Session = Depends(get_db)):
    email = request.email.strip().lower()

    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(
        request.password,
        user.hashed_password
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.email_verified:
        raise HTTPException(
            status_code=403,
            detail="Email not verified. Please verify your email first."
        )

    return {
        "status": "success",
        "user": user.userid,
        "id": user.id
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

print("------------------------------------------")
print(">>> PYTHON FASTAPI BACKEND IS ACTIVE <<<")
print("------------------------------------------")
