from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from schemas.models import DocumentInDB, DocumentSchema, UserInDB
from config import get_db
from auth_utils import verify_access_token
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import or_

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


@router.get("/", response_model=List[DocumentSchema])
def search_documents(
    query: str = Query(..., description="Search keyword"),
    db: Session = Depends(get_db),
    user: UserInDB = Depends(get_current_user),
):
    # Simple ILIKE search across title and content
    search_pattern = f"%{query}%"
    results = (
        db.query(DocumentInDB)
        .filter(
            DocumentInDB.user_id == user.id,
            or_(DocumentInDB.title.ilike(search_pattern), DocumentInDB.content.ilike(search_pattern)),
        )
        .order_by(DocumentInDB.updated_at.desc())
        .all()
    )
    return results 