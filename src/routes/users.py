from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from schemas.models import UserInDB
from config import get_db
from auth_utils import verify_access_token
from fastapi.security import OAuth2PasswordBearer

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UserInDB:
    payload = verify_access_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_email = payload["sub"]
    user = db.query(UserInDB).filter(UserInDB.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


class UserUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None


@router.get("/{user_id}", response_model=UserInDB)
def get_profile(user_id: int, db: Session = Depends(get_db), user: UserInDB = Depends(get_current_user)):
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this profile")
    return user


@router.put("/{user_id}", response_model=UserInDB)
def update_profile(
    user_id: int,
    update: UserUpdate,
    db: Session = Depends(get_db),
    user: UserInDB = Depends(get_current_user),
):
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this profile")

    if update.name is not None:
        user.name = update.name
    if update.password is not None:
        from auth_utils import hash_password

        user.hashed_password = hash_password(update.password)
    db.commit()
    db.refresh(user)
    return user 