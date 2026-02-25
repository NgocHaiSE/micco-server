from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import User, Document
from schemas import DashboardStats, UploadDataPoint, StorageDataPoint
from auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard statistics."""
    total_files = db.query(Document).count()
    total_bytes = db.query(func.sum(Document.size_bytes)).scalar() or 0
    team_members = db.query(User).count()

    # Recent uploads (last 7 days)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_uploads = db.query(Document).filter(
        Document.created_at >= seven_days_ago
    ).count()

    # Format storage
    if total_bytes >= 1024 * 1024 * 1024:
        storage = f"{total_bytes / (1024 * 1024 * 1024):.1f} GB"
    elif total_bytes >= 1024 * 1024:
        storage = f"{total_bytes / (1024 * 1024):.1f} MB"
    else:
        storage = f"{total_bytes / 1024:.1f} KB"

    return DashboardStats(
        totalFiles=total_files,
        storageUsed=storage,
        recentUploads=recent_uploads,
        teamMembers=team_members,
    )


@router.get("/uploads-over-time", response_model=list[UploadDataPoint])
def get_uploads_over_time(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get uploads per month for the last 6 months."""
    now = datetime.now(timezone.utc)
    months = []

    for i in range(5, -1, -1):
        month_dt = now - timedelta(days=30 * i)
        month_name = month_dt.strftime("%b")
        month_start = month_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_dt.month == 12:
            month_end = month_start.replace(year=month_dt.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_dt.month + 1)

        count = db.query(Document).filter(
            Document.created_at >= month_start,
            Document.created_at < month_end,
        ).count()

        months.append(UploadDataPoint(month=month_name, uploads=count))

    return months


@router.get("/storage-by-type", response_model=list[StorageDataPoint])
def get_storage_by_type(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get storage usage grouped by file type."""
    type_colors = {
        "PDF": "#1E3A8A",
        "DOCX": "#4F46E5",
        "XLSX": "#10B981",
        "PPTX": "#F59E0B",
        "PNG": "#8B5CF6",
        "JPG": "#8B5CF6",
        "MD": "#6B7280",
        "ZIP": "#EAB308",
    }

    results = (
        db.query(Document.type, func.sum(Document.size_bytes))
        .group_by(Document.type)
        .all()
    )

    data = []
    for doc_type, total_bytes in results:
        size_gb = (total_bytes or 0) / (1024 * 1024 * 1024)
        # Convert to MB if < 1 GB for better readability
        size_display = round(size_gb, 1) if size_gb >= 0.1 else round((total_bytes or 0) / (1024 * 1024), 1)
        data.append(StorageDataPoint(
            type=doc_type,
            size=size_display,
            fill=type_colors.get(doc_type, "#6B7280"),
        ))

    # If no data, return defaults based on mock data
    if not data:
        data = [
            StorageDataPoint(type="PDF", size=12.4, fill="#1E3A8A"),
            StorageDataPoint(type="DOCX", size=8.2, fill="#4F46E5"),
            StorageDataPoint(type="XLSX", size=5.1, fill="#10B981"),
            StorageDataPoint(type="Images", size=4.8, fill="#F59E0B"),
            StorageDataPoint(type="Other", size=4.3, fill="#6B7280"),
        ]

    return data
