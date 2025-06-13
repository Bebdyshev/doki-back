from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from auth_utils import hash_password, verify_password, create_access_token, verify_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from config import get_db
from schemas.models import UserInDB, Token
from datetime import timedelta
import traceback
import logging
from pydantic import BaseModel, EmailStr
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Define missing Pydantic models
class UserLogin(BaseModel):
    email: str
    password: str

class CreateUser(BaseModel):
    name: str
    email: str
    password: str
    type: str = "user"

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

@router.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    try:
        logger.info(f"Attempting login for email: {user.email}")
        db_user = db.query(UserInDB).filter(UserInDB.email == user.email).first()
        if not db_user:
            logger.warning(f"User not found: {user.email}")
            raise HTTPException(status_code=400, detail="Invalid credentials")
        
        logger.info(f"Found user: {db_user.email}")
        logger.info("Attempting to verify password")
        
        if not verify_password(user.password, db_user.hashed_password):
            logger.warning(f"Password verification failed for user: {user.email}")
            raise HTTPException(status_code=400, detail="Invalid credentials")
        
        logger.info(f"Password verified successfully for user: {user.email}")
        access_token = create_access_token(
            data={"sub": user.email, "type": db_user.type},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": access_token, "type": db_user.type}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in login: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/register", response_model=Token)
def register(user: CreateUser, db: Session = Depends(get_db)):
    if db.query(UserInDB).filter(UserInDB.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = hash_password(user.password)
    new_user = UserInDB(email=user.email, hashed_password=hashed_password, name=user.name, type=user.type)
    db.add(new_user)
    db.commit()

    access_token = create_access_token(
        data={"sub": new_user.email, "type": new_user.type},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "type": new_user.type}

@router.delete("/users/", response_model=dict)
def delete_all_users(db: Session = Depends(get_db)):
    try:
        db.query(UserInDB).delete()
        db.commit()  
        return {"message": "All users deleted successfully."}
    except Exception as e:
        db.rollback() 
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/users/me")
def get_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = verify_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_email = payload.get("sub")
    user = db.query(UserInDB).filter(UserInDB.email == user_email).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# Logout endpoint
@router.post("/logout")
def logout(token: str = Depends(oauth2_scheme)):
    # For stateless JWT, logout is handled client-side by discarding the token.
    return {"detail": "Logged out"}

# Google OAuth endpoint
class GoogleOAuthRequest(BaseModel):
    token: str  # Google ID token from frontend

@router.post("/google-login", response_model=Token)
def google_login(data: GoogleOAuthRequest, db: Session = Depends(get_db)):
    try:
        # Verify the token
        idinfo = id_token.verify_oauth2_token(
            data.token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
        email = idinfo["email"]
        name = idinfo.get("name", email.split("@")[0])
        # Find or create user
        user = db.query(UserInDB).filter(UserInDB.email == email).first()
        if not user:
            user = UserInDB(email=email, name=name, hashed_password="google-oauth", type="user")
            db.add(user)
            db.commit()
            db.refresh(user)
        access_token = create_access_token(
            data={"sub": user.email, "type": user.type},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": access_token, "type": user.type}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Google OAuth failed: {e}")