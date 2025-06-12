from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from io import BytesIO

from schemas.models import (
    DocumentInDB,
    DocumentCreate,
    DocumentUpdate,
    DocumentSchema,
    UserInDB,
)
from config import get_db
from auth_utils import verify_access_token
from fastapi.security import OAuth2PasswordBearer
from starlette.responses import StreamingResponse
from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from reportlab.pdfgen import canvas

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Helper to get current user

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UserInDB:
    payload = verify_access_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_email = payload["sub"]
    user = db.query(UserInDB).filter(UserInDB.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# CRUD Endpoints

@router.post("/", response_model=DocumentSchema)
def create_document(
    doc: DocumentCreate,
    db: Session = Depends(get_db),
    user: UserInDB = Depends(get_current_user),
):
    new_doc = DocumentInDB(
        user_id=user.id,
        title=doc.title,
        content=doc.content,
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    return new_doc


@router.get("/{document_id}", response_model=DocumentSchema)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: UserInDB = Depends(get_current_user),
):
    document = (
        db.query(DocumentInDB)
        .filter(DocumentInDB.id == document_id, DocumentInDB.user_id == user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.put("/{document_id}", response_model=DocumentSchema)
def update_document(
    document_id: int,
    update: DocumentUpdate,
    db: Session = Depends(get_db),
    user: UserInDB = Depends(get_current_user),
):
    document = (
        db.query(DocumentInDB)
        .filter(DocumentInDB.id == document_id, DocumentInDB.user_id == user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if update.title is not None:
        document.title = update.title
    if update.content is not None:
        document.content = update.content
    document.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(document)
    return document


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: UserInDB = Depends(get_current_user),
):
    document = (
        db.query(DocumentInDB)
        .filter(DocumentInDB.id == document_id, DocumentInDB.user_id == user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    db.delete(document)
    db.commit()
    return {"detail": "Document deleted"}


# Export helpers

def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n")


def _generate_pdf(text: str) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    text_object = pdf.beginText(40, 800)
    for line in text.split("\n"):
        text_object.textLine(line)
    pdf.drawText(text_object)
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.read()


def _generate_docx(text: str) -> bytes:
    doc = DocxDocument()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    byte_io = BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return byte_io.read()


@router.get("/{document_id}/export")
def export_document(
    document_id: int,
    format: str = Query("pdf", enum=["pdf", "docx", "txt"]),
    db: Session = Depends(get_db),
    user: UserInDB = Depends(get_current_user),
):
    document = (
        db.query(DocumentInDB)
        .filter(DocumentInDB.id == document_id, DocumentInDB.user_id == user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    plain_text = _html_to_text(document.content)

    filename_base = f"document_{document_id}_{datetime.utcnow().isoformat()}"

    if format == "txt":
        file_bytes = plain_text.encode()
        media_type = "text/plain"
        filename = f"{filename_base}.txt"
    elif format == "docx":
        file_bytes = _generate_docx(plain_text)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{filename_base}.docx"
    else:  # pdf
        file_bytes = _generate_pdf(plain_text)
        media_type = "application/pdf"
        filename = f"{filename_base}.pdf"

    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    ) 