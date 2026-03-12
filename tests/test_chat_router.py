# backend/tests/test_chat_router.py
from unittest.mock import MagicMock, patch


def _mock_db_that_refreshes():
    """Mock db whose refresh() sets id and sources on the passed ChatMessage.

    content and role are set during ChatMessage construction and are preserved
    through refresh — the mock does not need to set them.
    """
    mock_db = MagicMock()

    def _refresh(obj):
        obj.id = 42
        obj.sources = []

    mock_db.refresh.side_effect = _refresh
    return mock_db


def test_send_message_returns_agent_answer():
    """send_message uses run_agent and returns its answer as content."""
    from services.agent import AgentResult
    from routers.chat import send_message
    from schemas import ChatSendRequest

    req = ChatSendRequest(message="hello", document_ids=[])
    db = _mock_db_that_refreshes()
    user = MagicMock()
    user.id = 1

    with patch("routers.chat.run_agent", return_value=AgentResult(answer="test answer", graph_data=None)):
        response = send_message(req=req, db=db, current_user=user)
    assert response.content == "test answer"
    assert response.graph_data is None


def test_send_message_passes_graph_data_through_to_response():
    """graph_data from AgentResult is included in the ChatMessageResponse."""
    from services.agent import AgentResult
    from routers.chat import send_message
    from schemas import ChatSendRequest

    graph = {
        "nodes": [{"id": "A", "label": "A", "type": "Supplier"}],
        "edges": [],
    }
    req = ChatSendRequest(message="who supplies?", document_ids=[])
    db = _mock_db_that_refreshes()
    user = MagicMock()
    user.id = 1

    with patch("routers.chat.run_agent", return_value=AgentResult(answer="result", graph_data=graph)):
        response = send_message(req=req, db=db, current_user=user)

    assert response.graph_data == graph


def test_send_message_calls_run_agent_with_message_and_db():
    """run_agent receives the user's message text and the db session."""
    from services.agent import AgentResult
    from routers.chat import send_message
    from schemas import ChatSendRequest

    req = ChatSendRequest(message="specific query", document_ids=[])
    db = _mock_db_that_refreshes()
    user = MagicMock()
    user.id = 1

    with patch("routers.chat.run_agent", return_value=AgentResult(answer="ans", graph_data=None)) as mock_run:
        send_message(req=req, db=db, current_user=user)

    mock_run.assert_called_once_with("specific query", db)


def test_get_history_returns_graph_data_none_for_all_messages():
    """History messages always have graph_data=None (no retroactive graph data)."""
    from routers.chat import get_history
    from models import ChatMessage

    msg1 = ChatMessage(id=1, role="user", content="hello", sources=[])
    msg2 = ChatMessage(id=2, role="ai", content="world", sources=[])

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [msg1, msg2]
    user = MagicMock()
    user.id = 1

    responses = get_history(db=mock_db, current_user=user)
    assert len(responses) == 2
    assert all(r.graph_data is None for r in responses)
