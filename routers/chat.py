from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, ChatMessage, Document
from schemas import ChatSendRequest, ChatMessageResponse
from auth import get_current_user

router = APIRouter(prefix="/api/chat", tags=["Chat Assistant"])

# ─── Mock AI Response Engine ────────────────────────────────
# (Replace with real LLM integration later)

AI_RESPONSES = {
    "summarize": {
        "content": (
            "Based on my analysis of the **Vendor Contract - CloudServ.pdf**, here's a summary:\n\n"
            "**Parties:** Your company and CloudServ Inc.\n\n"
            "**Key Terms:**\n"
            "- Service period: 24 months starting Jan 2026\n"
            "- Monthly fee: $12,500 for Enterprise tier\n"
            "- SLA guarantee: 99.9% uptime\n"
            "- Data retention: 7 years after termination\n\n"
            "**Notable Clauses:**\n"
            "- Auto-renewal unless 60-day written notice\n"
            "- Liability capped at 12 months of fees\n"
            "- Termination for cause with 30-day cure period"
        ),
        "sources": ["Vendor Contract - CloudServ.pdf"],
    },
    "payment": {
        "content": (
            "I found the following **payment terms** across your documents:\n\n"
            "**Vendor Contract - CloudServ.pdf:**\n"
            "- Net 30 payment terms\n"
            "- Monthly invoicing on the 1st\n"
            "- Late payment penalty: 1.5% per month\n"
            "- Annual pre-payment discount: 10%\n\n"
            "**NDA - Partner Corp.pdf:**\n"
            "- No direct payment terms (NDA only)\n"
            "- References to separate commercial agreement"
        ),
        "sources": ["Vendor Contract - CloudServ.pdf", "NDA - Partner Corp.pdf"],
    },
    "risk": {
        "content": (
            "Here are the **key risks** identified across your documents:\n\n"
            "**Security Audit Report.pdf:**\n"
            "1. 🔴 Critical: Legacy API endpoints without rate limiting\n"
            "2. 🟡 Medium: Session tokens not rotated on privilege change\n"
            "3. 🟢 Low: Verbose error messages in staging environment\n\n"
            "**Vendor Contract - CloudServ.pdf:**\n"
            "1. Auto-renewal clause may lock you into unfavorable terms\n"
            "2. Liability cap limits recourse in case of data breach\n"
            "3. No SLA penalties defined for partial outages"
        ),
        "sources": ["Security Audit Report.pdf", "Vendor Contract - CloudServ.pdf"],
    },
    "compare": {
        "content": (
            "I've compared the selected documents and identified the following **key differences**:\n\n"
            "**Structure:** Both documents follow standard enterprise format, "
            "but differ in section organization.\n\n"
            "**Key Differences:**\n"
            "- Termination clauses vary significantly\n"
            "- Liability caps differ by 3x\n"
            "- Data handling provisions are more detailed in the newer document\n\n"
            "**Recommendations:**\n"
            "- Align termination clauses for consistency\n"
            "- Review liability caps with legal team"
        ),
        "sources": ["Employee Handbook v3.docx", "Vendor Contract - CloudServ.pdf"],
    },
    "revenue": {
        "content": (
            "Here are the **quarterly revenue figures** from the Q4 Financial Report:\n\n"
            "| Quarter | Revenue | Growth |\n"
            "|---------|---------|--------|\n"
            "| Q1 2025 | $4.2M   | +12%   |\n"
            "| Q2 2025 | $4.8M   | +14%   |\n"
            "| Q3 2025 | $5.1M   | +6%    |\n"
            "| Q4 2025 | $5.9M   | +16%   |\n\n"
            "**Annual Total:** $20.0M (YoY growth: +12.4%)"
        ),
        "sources": ["Q4 Financial Report 2025.pdf"],
    },
    "compliance": {
        "content": (
            "I found **compliance requirements** referenced across your documents:\n\n"
            "**Security Audit Report.pdf:**\n"
            "- SOC 2 Type II certification required\n"
            "- GDPR compliance for EU data subjects\n"
            "- Annual penetration testing mandate\n\n"
            "**Employee Handbook v3.docx:**\n"
            "- Data privacy training quarterly\n"
            "- HIPAA compliance for health-related data\n"
            "- Record retention policies per regulation"
        ),
        "sources": ["Security Audit Report.pdf", "Employee Handbook v3.docx"],
    },
}


def get_ai_response(message: str) -> dict:
    """Match user message to an AI response."""
    lower = message.lower()

    if any(word in lower for word in ["summarize", "summary"]):
        return AI_RESPONSES["summarize"]
    if any(word in lower for word in ["payment", "terms", "invoice"]):
        return AI_RESPONSES["payment"]
    if any(word in lower for word in ["risk", "risks", "danger"]):
        return AI_RESPONSES["risk"]
    if any(word in lower for word in ["compare", "difference", "diff"]):
        return AI_RESPONSES["compare"]
    if any(word in lower for word in ["revenue", "financial", "income", "quarterly"]):
        return AI_RESPONSES["revenue"]
    if any(word in lower for word in ["compliance", "regulation", "requirement"]):
        return AI_RESPONSES["compliance"]

    return {
        "content": (
            "I've analyzed your selected documents and here's what I found:\n\n"
            "Based on the documents in your workspace, I can see relevant information "
            "across multiple files. The key points include document management best practices, "
            "team collaboration guidelines, and compliance requirements.\n\n"
            "Would you like me to dive deeper into any specific aspect?"
        ),
        "sources": ["Employee Handbook v3.docx", "Q4 Financial Report 2025.pdf"],
    }


@router.post("/send", response_model=ChatMessageResponse)
def send_message(
    req: ChatSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a user message and get an AI response."""
    # Save user message
    user_msg = ChatMessage(
        user_id=current_user.id,
        role="user",
        content=req.message,
    )
    user_msg.sources = []
    db.add(user_msg)
    db.commit()

    # Generate AI response
    response = get_ai_response(req.message)

    ai_msg = ChatMessage(
        user_id=current_user.id,
        role="ai",
        content=response["content"],
    )
    ai_msg.sources = response["sources"]
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)

    return ChatMessageResponse(
        id=ai_msg.id,
        role=ai_msg.role,
        content=ai_msg.content,
        sources=ai_msg.sources,
    )


@router.get("/history", response_model=list[ChatMessageResponse])
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get chat history for the current user."""
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return [
        ChatMessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            sources=msg.sources,
        )
        for msg in messages
    ]
