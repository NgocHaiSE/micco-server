import logging

from openai import OpenAI
from langchain_core.messages import HumanMessage

from services.agent.state import AgentState

logger = logging.getLogger(__name__)

_STRUCTURAL_KEYWORDS = {
    "nhà cung cấp", "hợp đồng", "xuất xứ", "liên quan đến",
    "phiếu nhập", "truy xuất", "quan hệ", "kết nối", "thuộc", "cung cấp bởi",
}
_SEMANTIC_KEYWORDS = {
    "tóm tắt", "nội dung", "tìm kiếm", "mô tả",
    "giải thích", "thông tin về", "chi tiết",
}

_VALID_INTENTS = {"structural", "semantic", "hybrid"}


def _keyword_classify(query: str) -> str | None:
    """Fast path: classify by Vietnamese keyword matching. Returns None if ambiguous."""
    lower = query.lower()
    has_structural = any(kw in lower for kw in _STRUCTURAL_KEYWORDS)
    has_semantic = any(kw in lower for kw in _SEMANTIC_KEYWORDS)
    if has_structural and not has_semantic:
        return "structural"
    if has_semantic and not has_structural:
        return "semantic"
    return None  # both or neither — fall through to LLM


def _llm_classify(query: str) -> str:
    """LLM fallback: single-shot gpt-4o-mini classification. Defaults to 'hybrid' on any error."""
    try:
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": (
                    "Classify this Vietnamese query as exactly one of: structural, semantic, hybrid.\n"
                    "structural = questions about relationships, traceability, suppliers, contracts.\n"
                    "semantic = questions about document content, summaries, descriptions.\n"
                    "hybrid = both or unclear.\n"
                    f"Query: {query}\nAnswer:"
                ),
            }],
            max_tokens=5,
        )
        result = resp.choices[0].message.content.strip().lower()
        if result in _VALID_INTENTS:
            return result
    except Exception as exc:
        logger.warning("Intent LLM classification failed: %s", exc)
    return "hybrid"


def intent_router(state: AgentState) -> AgentState:
    """LangGraph node: classify user query intent and set state['intent']."""
    query = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break

    try:
        raw_intent = _keyword_classify(query) or _llm_classify(query)
        intent = raw_intent if raw_intent in _VALID_INTENTS else "hybrid"
    except Exception as exc:
        logger.warning("Intent routing failed, defaulting to hybrid: %s", exc)
        intent = "hybrid"

    logger.debug("Intent=%s for query: %.80s", intent, query)
    return {**state, "intent": intent}
