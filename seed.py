"""
Seed script — Populates the database with initial data matching the frontend mock data.
Run: python seed.py
"""

from datetime import datetime, timezone, timedelta
from database import SessionLocal, engine, Base
from models import User, Document
from auth import hash_password

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # Check if already seeded
    if db.query(User).count() > 0:
        print("Database already seeded. Skipping.")
    else:
        # ─── Create Users ────────────────────────────────────
        users_data = [
            {"name": "Alex Johnson", "email": "alex@docvault.io", "password": "admin123", "role": "Admin"},
            {"name": "Sarah Chen", "email": "sarah@docvault.io", "password": "member123", "role": "Member"},
            {"name": "Mike Rivera", "email": "mike@docvault.io", "password": "member123", "role": "Member"},
            {"name": "Lisa Park", "email": "lisa@docvault.io", "password": "member123", "role": "Member"},
        ]

        users = {}
        for u in users_data:
            user = User(
                name=u["name"],
                email=u["email"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
            )
            db.add(user)
            db.flush()
            users[u["name"]] = user

        # Also create special "team" users for display
        team_users = [
            {"name": "Dev Team", "email": "dev@docvault.io", "password": "team123", "role": "Team"},
            {"name": "IT Team", "email": "it@docvault.io", "password": "team123", "role": "Team"},
            {"name": "HR Team", "email": "hr@docvault.io", "password": "team123", "role": "Team"},
            {"name": "Legal", "email": "legal@docvault.io", "password": "team123", "role": "Team"},
        ]
        for u in team_users:
            user = User(
                name=u["name"],
                email=u["email"],
                hashed_password=hash_password(u["password"]),
                role=u["role"],
            )
            db.add(user)
            db.flush()
            users[u["name"]] = user

        # ─── Create Documents ────────────────────────────────
        base_date = datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc)
        documents_data = [
            {"name": "Q4 Financial Report 2025.pdf", "type": "PDF", "size": "2.4 MB", "size_bytes": 2516582, "owner": "Alex Johnson", "days_ago": 0, "tags": ["Finance", "Reports"], "status": "Active"},
            {"name": "Employee Handbook v3.docx", "type": "DOCX", "size": "1.8 MB", "size_bytes": 1887436, "owner": "Sarah Chen", "days_ago": 1, "tags": ["HR", "Policy"], "status": "Active"},
            {"name": "Product Roadmap 2026.pptx", "type": "PPTX", "size": "5.2 MB", "size_bytes": 5452595, "owner": "Mike Rivera", "days_ago": 2, "tags": ["Product", "Strategy"], "status": "Active"},
            {"name": "Vendor Contract - CloudServ.pdf", "type": "PDF", "size": "890 KB", "size_bytes": 911360, "owner": "Alex Johnson", "days_ago": 3, "tags": ["Legal", "Contracts"], "status": "Active"},
            {"name": "Marketing Budget Q1.xlsx", "type": "XLSX", "size": "1.2 MB", "size_bytes": 1258291, "owner": "Lisa Park", "days_ago": 4, "tags": ["Marketing", "Finance"], "status": "Active"},
            {"name": "API Documentation v2.md", "type": "MD", "size": "340 KB", "size_bytes": 348160, "owner": "Dev Team", "days_ago": 5, "tags": ["Engineering", "Docs"], "status": "Active"},
            {"name": "Customer Survey Results.xlsx", "type": "XLSX", "size": "3.1 MB", "size_bytes": 3250585, "owner": "Lisa Park", "days_ago": 6, "tags": ["Research", "Data"], "status": "Archived"},
            {"name": "Brand Guidelines 2026.pdf", "type": "PDF", "size": "12.5 MB", "size_bytes": 13107200, "owner": "Sarah Chen", "days_ago": 7, "tags": ["Design", "Branding"], "status": "Active"},
            {"name": "Security Audit Report.pdf", "type": "PDF", "size": "4.7 MB", "size_bytes": 4928307, "owner": "IT Team", "days_ago": 8, "tags": ["Security", "Compliance"], "status": "Active"},
            {"name": "Meeting Notes - Board.docx", "type": "DOCX", "size": "520 KB", "size_bytes": 532480, "owner": "Alex Johnson", "days_ago": 9, "tags": ["Management", "Notes"], "status": "Active"},
            {"name": "Project Timeline.xlsx", "type": "XLSX", "size": "780 KB", "size_bytes": 798720, "owner": "Mike Rivera", "days_ago": 10, "tags": ["Project", "Planning"], "status": "Active"},
            {"name": "NDA - Partner Corp.pdf", "type": "PDF", "size": "210 KB", "size_bytes": 215040, "owner": "Legal", "days_ago": 11, "tags": ["Legal", "NDA"], "status": "Active"},
            {"name": "Training Materials.zip", "type": "ZIP", "size": "45.3 MB", "size_bytes": 47499264, "owner": "HR Team", "days_ago": 12, "tags": ["HR", "Training"], "status": "Active"},
            {"name": "System Architecture.png", "type": "PNG", "size": "2.1 MB", "size_bytes": 2202009, "owner": "Dev Team", "days_ago": 13, "tags": ["Engineering", "Architecture"], "status": "Active"},
            {"name": "Quarterly OKRs.docx", "type": "DOCX", "size": "430 KB", "size_bytes": 440320, "owner": "Alex Johnson", "days_ago": 14, "tags": ["Strategy", "OKR"], "status": "Active"},
        ]

        for d in documents_data:
            doc = Document(
                name=d["name"],
                type=d["type"],
                size=d["size"],
                size_bytes=d["size_bytes"],
                owner_id=users[d["owner"]].id,
                status=d["status"],
                created_at=base_date - timedelta(days=d["days_ago"]),
            )
            doc.tags = d["tags"]
            db.add(doc)

        db.commit()
        print(f"✅ Seeded {len(users_data) + len(team_users)} users and {len(documents_data)} documents.")
        print(f"   Default admin: alex@docvault.io / admin123")

finally:
    db.close()
