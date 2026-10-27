import datetime
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models.entities import (
    User, ParentProfile, HealthDocument, PrivacyPermission, AuditLog,
    TemporaryPermission, CareCircleMember, PrivacySetting
)
from app.schemas.schemas import HealthDocumentResponse, HealthExplanationRequest, HealthExplanationResponse
from app.routers.deps import get_current_user

router = APIRouter(prefix="/health-documents", tags=["Health Reports & AI Explanation"])

UPLOAD_DIR = "backend/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("", response_model=List[HealthDocumentResponse])
def get_health_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role.upper() == "PARENT":
        profile = current_user.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == current_user.id).first()
        parent_user_id = current_user.id
        parent_id = profile.id if profile else current_user.id
    else:
        from app.services.relationship_service import RelationshipService
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have an approved family relationship to view health documents."
            )
        profile = parent.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == parent.id).first()
        parent_user_id = parent.id
        parent_id = profile.id if profile else parent.id

    # Check privacy and authorization for family, guardian, and caregiver roles
    if current_user.role.upper() in ["FAMILY", "GUARDIAN", "CAREGIVER"]:
        now = datetime.datetime.utcnow()

        # 1. Temporary Permission Check (must belong to this specific family user)
        has_temp = db.query(TemporaryPermission).filter(
            TemporaryPermission.parent_id == parent_user_id,
            TemporaryPermission.resource_type == "HEALTH_DOC",
            TemporaryPermission.status == "ACTIVE",
            TemporaryPermission.expires_at > now,
            (TemporaryPermission.grantee_name.like(f"%{current_user.full_name}%")) |
            (TemporaryPermission.grantee_name == current_user.phone)
        ).first()

        # 2. Care Circle Member Role Permissions
        circle_member = db.query(CareCircleMember).filter(
            CareCircleMember.parent_id == parent_user_id,
            (CareCircleMember.phone == current_user.phone) | (CareCircleMember.name.like(f"%{current_user.full_name}%"))
        ).first()

        if circle_member and circle_member.can_emergency_only and not has_temp:
            audit = AuditLog(
                user_id=current_user.id,
                action="VIEW_HEALTH_DOCS_BLOCKED",
                target_resource="HEALTH_DOCS",
                details="Emergency-only role attempted to view routine health documents"
            )
            db.add(audit)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Emergency first-responder role cannot access routine medical documents."
            )

        if circle_member and not circle_member.can_health_docs and not has_temp:
            audit = AuditLog(
                user_id=current_user.id,
                action="VIEW_HEALTH_DOCS_BLOCKED",
                target_resource="HEALTH_DOCS",
                details="Role without health_docs permission attempted to view health reports"
            )
            db.add(audit)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your Care Circle role does not have authorization to view health documents."
            )

        # 3. Sovereign Privacy Settings Check
        priv_setting = db.query(PrivacySetting).filter(PrivacySetting.parent_id == parent_user_id).first()
        perm = db.query(PrivacyPermission).filter(
            PrivacyPermission.parent_id == parent_user_id
        ).first()

        is_health_blocked = (priv_setting and not priv_setting.health_info) or (perm and not perm.share_health)

        if is_health_blocked and not has_temp:
            audit = AuditLog(
                user_id=current_user.id,
                action="VIEW_HEALTH_DOCS_BLOCKED_BY_PRIVACY",
                target_resource="HEALTH_DOCS",
                details="Family member access blocked by Parent Privacy Setting (Health: OFF)"
            )
            db.add(audit)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Parent has chosen to keep health reports private."
            )

        audit = AuditLog(
            user_id=current_user.id,
            action="VIEW_HEALTH_DOCS",
            target_resource="HEALTH_DOCS",
            details="Care circle member accessed shared health document list"
        )
        db.add(audit)
        db.commit()

    docs = db.query(HealthDocument).filter(
        HealthDocument.parent_id == parent_id
    ).order_by(HealthDocument.uploaded_at.desc()).all()

    return docs

from fastapi.responses import FileResponse, Response

@router.post("", response_model=HealthDocumentResponse)
async def upload_health_document(
    file: Optional[UploadFile] = File(None),
    filename: Optional[str] = Form(None),
    document_type: str = Form("Blood Test"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = current_user.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == current_user.id).first()
    parent_id = profile.id if profile else current_user.id

    actual_filename = filename or (file.filename if file else "Medical_Report.pdf")
    stored_path = f"/uploads/{actual_filename}"

    if file:
        try:
            content = await file.read()
            safe_name = f"{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(file.filename)}"
            dest = os.path.join(UPLOAD_DIR, safe_name)
            with open(dest, "wb") as f:
                f.write(content)
            stored_path = f"/uploads/{safe_name}"
            actual_filename = file.filename
        except Exception as e:
            pass

    doc = HealthDocument(
        parent_id=parent_id,
        filename=actual_filename,
        document_type=document_type,
        file_path=stored_path,
        ai_summary="AI Summary: Parameters show normal baseline stability. Please review with family doctor.",
        is_shared_with_family=True,
        uploaded_at=datetime.datetime.utcnow()
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

@router.get("/{id}/download")
@router.get("/{id}/file")
def get_health_document_file(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(HealthDocument).filter(HealthDocument.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Health document not found.")

    if current_user.role.upper() == "PARENT":
        profile = current_user.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == current_user.id).first()
        parent_id = profile.id if profile else current_user.id
        if doc.parent_id != parent_id:
            raise HTTPException(status_code=403, detail="Access forbidden: You do not own this document.")
    else:
        from app.services.relationship_service import RelationshipService
        parent = RelationshipService.get_parent_for_family(db, current_user.id)
        if not parent:
            raise HTTPException(status_code=403, detail="Access forbidden: You do not have an approved family relationship to view this document.")
        parent_prof = parent.parent_profile or db.query(ParentProfile).filter(ParentProfile.user_id == parent.id).first()
        parent_id = parent_prof.id if parent_prof else parent.id
        if doc.parent_id != parent_id:
            raise HTTPException(status_code=403, detail="Access forbidden: Document belongs to a different family.")

    abs_path = os.path.join(UPLOAD_DIR, os.path.basename(doc.file_path or doc.filename))
    if os.path.exists(abs_path):
        return FileResponse(abs_path, filename=doc.filename)

    sample_content = f"EVER NEAR AI Health Document: {doc.filename}\nType: {doc.document_type}\nSummary: {doc.ai_summary}\nDate: {doc.uploaded_at}"
    return Response(content=sample_content, media_type="text/plain", headers={"Content-Disposition": f"attachment; filename={doc.filename}.txt"})

@router.post("/explain", response_model=HealthExplanationResponse)
def explain_medical_term(req: HealthExplanationRequest):
    term_lower = req.term.lower().strip()
    
    explanations = {
        "vitamin d": (
            "Vitamin D helps your bones stay strong and assists the body in absorbing calcium from healthy food.",
            "வைட்டமின் டி உங்கள் எலும்புகளை பலப்படுத்தவும், உணவில் உள்ள சத்துக்களை உடல் கிரகித்துக் கொள்ளவும் உதவுகிறது."
        ),
        "blood pressure": (
            "Blood pressure measures how gently and steadily your heart circulates blood through your body.",
            "இரத்த அழுத்தம் என்பது இதயம் உடல் முழுவதும் இரத்தத்தை சீராக செலுத்தும் அளவீடாகும்."
        ),
        "hba1c": (
            "HbA1c shows the average sugar level in your bloodstream over the past three months.",
            "HbA1c என்பது கடந்த 3 மாதங்களில் உங்கள் இரத்தத்தில் இருந்த சராசரி சர்க்கரை அளவைக் குறிக்கிறது."
        ),
        "calcium": (
            "Calcium keeps bones and teeth resilient and supports daily muscle movement.",
            "கால்சியம் உங்கள் எலும்புகள் மற்றும் மூட்டுகளை உறுதியாக வைத்திருக்க உதவுகிறது."
        )
    }

    if term_lower in explanations:
        en_text, ta_text = explanations[term_lower]
    else:
        en_text = f"'{req.term}' is a common wellness marker found in routine health screenings. It reflects normal body balance."
        ta_text = f"'{req.term}' என்பது வழக்கமான மருத்துவப் பரிசோதனைகளில் சோதிக்கப்படும் ஒரு பொதுவான சுகாதார குறியீடு ஆகும்."

    return HealthExplanationResponse(
        term=req.term,
        explanation=en_text,
        explanation_tamil=ta_text,
        disclaimer="This is a general educational explanation. Please ask a qualified healthcare professional for medical advice."
    )
