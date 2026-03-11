from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage


def _make_state(query: str) -> dict:
    return {
        "messages": [HumanMessage(content=query)],
        "intent": "",
        "document_ids": [],
    }


# ── Keyword classifier (no API call) ────────────────────────

def test_structural_keywords_classify_as_structural():
    from services.agent.intent_router import intent_router
    state = _make_state("Nhà cung cấp nào cung cấp vật tư này?")
    result = intent_router(state)
    assert result["intent"] == "structural"


def test_supplier_keyword_classifies_as_structural():
    from services.agent.intent_router import intent_router
    state = _make_state("Truy xuất nguồn gốc của hợp đồng này")
    result = intent_router(state)
    assert result["intent"] == "structural"


def test_semantic_keywords_classify_as_semantic():
    from services.agent.intent_router import intent_router
    state = _make_state("Tóm tắt nội dung tài liệu này")
    result = intent_router(state)
    assert result["intent"] == "semantic"


def test_detail_keyword_classifies_as_semantic():
    from services.agent.intent_router import intent_router
    state = _make_state("Thông tin về quy định an toàn")
    result = intent_router(state)
    assert result["intent"] == "semantic"


# ── LLM fallback path (ambiguous / empty) ───────────────────

def test_empty_query_falls_back_to_llm_and_returns_hybrid():
    with patch("services.agent.intent_router._llm_classify", return_value="hybrid") as mock_llm:
        from services.agent.intent_router import intent_router
        state = _make_state("What is the status?")
        result = intent_router(state)
        assert result["intent"] == "hybrid"
        mock_llm.assert_called_once()


def test_mixed_keywords_falls_back_to_llm():
    with patch("services.agent.intent_router._llm_classify", return_value="hybrid") as mock_llm:
        from services.agent.intent_router import intent_router
        # Both structural ("hợp đồng") and semantic ("tóm tắt") keywords present
        state = _make_state("Tóm tắt hợp đồng với nhà cung cấp")
        result = intent_router(state)
        assert result["intent"] == "hybrid"
        mock_llm.assert_called_once()


def test_llm_returns_structural_is_accepted():
    with patch("services.agent.intent_router._llm_classify", return_value="structural"):
        from services.agent.intent_router import intent_router
        state = _make_state("unknown query pattern")
        result = intent_router(state)
        assert result["intent"] == "structural"


def test_llm_returns_unexpected_value_defaults_to_hybrid():
    with patch("services.agent.intent_router._llm_classify", return_value="banana"):
        from services.agent.intent_router import intent_router
        state = _make_state("unknown query pattern")
        result = intent_router(state)
        assert result["intent"] == "hybrid"


def test_llm_raises_exception_defaults_to_hybrid():
    with patch("services.agent.intent_router._llm_classify", side_effect=Exception("API error")):
        from services.agent.intent_router import intent_router
        state = _make_state("unknown query pattern")
        result = intent_router(state)
        assert result["intent"] == "hybrid"


# ── _llm_classify unit test ──────────────────────────────────

def test_llm_classify_calls_openai_and_parses_response():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = " semantic "

    with patch("services.agent.intent_router.OpenAI", return_value=mock_client):
        from services.agent.intent_router import _llm_classify
        result = _llm_classify("some query")
        assert result == "semantic"


def test_llm_classify_returns_hybrid_on_api_error():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("connection timeout")
    with patch("services.agent.intent_router.OpenAI", return_value=mock_client):
        from services.agent.intent_router import _llm_classify
        result = _llm_classify("some query")
        assert result == "hybrid"
