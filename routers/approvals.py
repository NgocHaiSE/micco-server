import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from database import get_db
from models import User, Document, KnowledgeEntry
from auth import get_current_user
from services import ingest_pipeline
from routers.knowledge import ingest_knowledge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approvals", tags=["Approvals"])


# ─── Access guard ────────────────────────────────────────────

def _require_approver(current_user: User = Depends(get_current_user)) -> User:
    """Only Trưởng phòng or Admin can approve/reject."""
    if current_user.role not in ("Admin", "Trưởng phòng"):
        raise HTTPException(status_code=403, detail="Chỉ Trưởng phòng hoặc Admin mới có quyền phê duyệt")
    return current_user


def _can_approve(approver: User, department_id: Optional[int]) -> bool:
    """Admin can approve anything; Trưởng phòng only their own department."""
    if approver.role == "Admin":
        return True
    return department_id is not None and approver.department_id == department_id


# ─── Pending count (for sidebar badge) ──────────────────────

@router.get("/count")
def pending_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_approver),
):
    """Return count of pending items in the approver's scope."""
    doc_q = db.query(Document).filter(Document.approval_status == "pending_approval")
    kn_q = db.query(KnowledgeEntry).filter(KnowledgeEntry.approval_status == "pending_approval")

    if current_user.role != "Admin":
        doc_q = doc_q.filter(Document.department_id == current_user.department_id)
        kn_q = kn_q.filter(KnowledgeEntry.department_id == current_user.department_id)

    return {"count": doc_q.count() + kn_q.count()}


# ─── List pending items ──────────────────────────────────────

@router.get("/pending")
def list_pending(
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_approver),
):
    """List all pending_approval documents and knowledge entries."""
    doc_q = db.query(Document).options(
        joinedload(Document.owner),
        joinedload(Document.department),
    ).filter(Document.approval_status == "pending_approval")

    kn_q = db.query(KnowledgeEntry).options(
        joinedload(KnowledgeEntry.owner),
        joinedload(KnowledgeEntry.department),
    ).filter(KnowledgeEntry.approval_status == "pending_approval")

    if current_user.role != "Admin":
        doc_q = doc_q.filter(Document.department_id == current_user.department_id)
        kn_q = kn_q.filter(KnowledgeEntry.department_id == current_user.department_id)

    docs = doc_q.order_by(Document.created_at.desc()).all()
    entries = kn_q.order_by(KnowledgeEntry.created_at.desc()).all()

    return {
        "documents": [
            {
                "id": d.id,
                "type": "document",
                "name": d.name,
                "file_type": d.type,
                "category": d.category,
                "size": d.size,
                "owner": d.owner.name if d.owner else "Unknown",
                "department": d.department.name if d.department else None,
                "department_id": d.department_id,
                "visibility": d.visibility or "internal",
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ],
        "knowledge": [
            {
                "id": e.id,
                "type": "knowledge",
                "title": e.title,
                "category": e.category,
                "owner": e.owner.name if e.owner else "Unknown",
                "department": e.department.name if e.department else None,
                "department_id": e.department_id,
                "visibility": e.visibility or "internal",
                "content_text": e.content_text[:200] if e.content_text else "",
                "tags": e.tags or [],
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    }


# ─── Approve/Reject Documents ────────────────────────────────

@router.post("/documents/{doc_id}/approve")
def approve_document(
    doc_id: int,
    body: dict = {},
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_approver),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Tài liệu không tồn tại")
    if not _can_approve(current_user, doc.department_id):
        raise HTTPException(status_code=403, detail="Không có quyền phê duyệt tài liệu này")
    if doc.approval_status == "approved":
        raise HTTPException(status_code=400, detail="Tài liệu đã được phê duyệt")

    doc.approval_status = "approved"
    doc.approved_by_id = current_user.id
    doc.approved_at = datetime.now(timezone.utc)
    doc.approval_note = body.get("note")
    db.commit()

    # Now trigger ingest
    if background_tasks:
        background_tasks.add_task(ingest_pipeline.run, doc.id)
    else:
        import threading
        threading.Thread(target=ingest_pipeline.run, args=(doc.id,), daemon=True).start()

    logger.info("Document %d approved by user %d", doc_id, current_user.id)
    return {"message": "Đã phê duyệt", "id": doc_id}


@router.post("/documents/{doc_id}/reject")
def reject_document(
    doc_id: int,
    body: dict = {},
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_approver),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Tài liệu không tồn tại")
    if not _can_approve(current_user, doc.department_id):
        raise HTTPException(status_code=403, detail="Không có quyền từ chối tài liệu này")

    doc.approval_status = "rejected"
    doc.approved_by_id = current_user.id
    doc.approved_at = datetime.now(timezone.utc)
    doc.approval_note = body.get("note")
    db.commit()

    logger.info("Document %d rejected by user %d", doc_id, current_user.id)
    return {"message": "Đã từ chối", "id": doc_id}


# ─── Approve/Reject Knowledge ────────────────────────────────

@router.post("/knowledge/{entry_id}/approve")
def approve_knowledge(
    entry_id: int,
    body: dict = {},
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_approver),
):
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Tri thức không tồn tại")
    if not _can_approve(current_user, entry.department_id):
        raise HTTPException(status_code=403, detail="Không có quyền phê duyệt tri thức này")
    if entry.approval_status == "approved":
        raise HTTPException(status_code=400, detail="Tri thức đã được phê duyệt")

    entry.approval_status = "approved"
    entry.approved_by_id = current_user.id
    entry.approved_at = datetime.now(timezone.utc)
    entry.approval_note = body.get("note")
    db.commit()

    # Trigger ingest if Active
    if entry.status == "Active":
        if background_tasks:
            background_tasks.add_task(ingest_knowledge, entry.id)
        else:
            import threading
            threading.Thread(target=ingest_knowledge, args=(entry.id,), daemon=True).start()

    logger.info("Knowledge %d approved by user %d", entry_id, current_user.id)
    return {"message": "Đã phê duyệt", "id": entry_id}


@router.post("/knowledge/{entry_id}/reject")
def reject_knowledge(
    entry_id: int,
    body: dict = {},
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_approver),
):
    entry = db.query(KnowledgeEntry).filter(KnowledgeEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Tri thức không tồn tại")
    if not _can_approve(current_user, entry.department_id):
        raise HTTPException(status_code=403, detail="Không có quyền từ chối tri thức này")

    entry.approval_status = "rejected"
    entry.approved_by_id = current_user.id
    entry.approved_at = datetime.now(timezone.utc)
    entry.approval_note = body.get("note")
    db.commit()

    logger.info("Knowledge %d rejected by user %d", entry_id, current_user.id)
    return {"message": "Đã từ chối", "id": entry_id}
