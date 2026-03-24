from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, ChatMessage
from schemas import ChatSendRequest, ChatMessageResponse
from auth import get_current_user
from services.agent import run_agent

router = APIRouter(prefix="/api/chat", tags=["Chat Assistant"])


@router.post("/send", response_model=ChatMessageResponse)
def send_message(
    req: ChatSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a user message and get an AI response from the LangGraph agent."""
    # Save user message
    user_msg = ChatMessage(
        user_id=current_user.id,
        role="user",
        content=req.message,
    )
    user_msg.sources = []
    db.add(user_msg)
    db.commit()

    # Run agent — scope by department (Admin sees all)
    dept_id = None if current_user.role == "Admin" else current_user.department_id
    result = run_agent(req.message, db, department_id=dept_id)

    ai_msg = ChatMessage(
        user_id=current_user.id,
        role="ai",
        content=result.answer,
    )
    ai_msg.sources = []  # sources is a mapped JSONB column (default=[])
    # graph_data is NOT persisted to DB — passed directly to response payload below
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)

    return ChatMessageResponse(
        id=ai_msg.id,
        role=ai_msg.role,
        content=ai_msg.content,
        sources=ai_msg.sources,
        graph_data=result.graph_data,
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
            graph_data=None,  # no retroactive graph data for history messages
        )
        for msg in messages
    ]
