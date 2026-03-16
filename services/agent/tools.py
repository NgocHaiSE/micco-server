import json
import logging
import re

from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_core.tools import tool, ToolException

from services.neo4j_service import neo4j_service
from services.embedding_service import embed
from models import Document

logger = logging.getLogger(__name__)

_WRITE_PATTERN = re.compile(
    r'\b(CREATE|MERGE|DELETE|SET|REMOVE|DROP|CALL|FOREACH)\b', re.IGNORECASE
)
_MAX_ROWS = 50


def make_tools(db: Session) -> list:
    """Create tool instances with `db` session captured in closure.

    Called once per run_agent() invocation. Each call returns fresh tool
    instances bound to the provided SQLAlchemy session.
    """

    @tool
    def query_knowledge_graph(cypher: str) -> str:
        """Run a read-only Cypher MATCH query on the Neo4j knowledge graph.

        Returns up to 50 rows as a JSON array. Only MATCH and RETURN
        clauses are allowed — write operations are rejected.
        """
        if _WRITE_PATTERN.search(cypher):
            raise ToolException(
                "Write operations are not allowed. Use only MATCH/RETURN."
            )
        if not neo4j_service.available:
            raise ToolException("Graph DB unavailable.")

        # Auto-fix: If type(rel) is used but rel variable not defined, extract rel type from MATCH pattern
        if "type(rel)" in cypher and "-[:" not in cypher.replace("-[:", "-[rel:"):
            # Find relationship type in the query and replace type(rel) with literal
            match = re.search(r'-\[(\w+):(\w+)\]->', cypher)
            if match:
                var_name, rel_type = match.groups()
                if var_name != "rel":
                    cypher = cypher.replace("type(rel)", f"'{rel_type}'")
                    logger.info(f"Auto-fixed Cypher: replaced type(rel) with '{rel_type}'")

        try:
            rows = neo4j_service.run_cypher(cypher, {})[:_MAX_ROWS]
            return json.dumps(rows, ensure_ascii=False, indent=2)
        except Exception as exc:
            raise ToolException(f"Graph query failed: {exc}") from exc

    @tool
    def search_kg_semantic(query: str, limit: int = 5) -> str:
        """Semantic search over document chunks using Neo4j vector similarity.

        Uses embeddings stored in Neo4j to find relevant document chunks.
        Returns chunk content, source document ID, and similarity score.
        Use this for content-based questions about document text.
        """
        try:
            vector = embed([query])[0]
            rows = neo4j_service.search_similar_chunks(vector, limit)
            if not rows:
                return "No matching chunks found in knowledge graph."
            lines = []
            doc_ids = []
            for i, row in enumerate(rows, 1):
                doc_ids.append(str(row.get("document_id", "")))
                lines.append(
                    f"Chunk {i} (doc_id={row.get('document_id')}, "
                    f"similarity={row.get('similarity', 0):.3f}):\n{row.get('content', '')}"
                )
            doc_id_str = ",".join(dict.fromkeys(doc_ids))
            return "DOCUMENT_IDS: " + doc_id_str + "\n---\n" + "\n\n".join(lines)
        except Exception as exc:
            logger.warning("Neo4j semantic search failed: %s", exc)
            return ""

    @tool
    def search_document_chunks(query: str, limit: int = 5) -> str:
        """Semantic search over document chunk embeddings.

        Returns top matching chunks with content and source document IDs.
        The result begins with a DOCUMENT_IDS header that the graph can use
        for follow-up Cypher queries. Returns an empty string on DB error.
        """
        try:
            vector = embed([query])[0]
            rows = db.execute(
                text("SELECT * FROM search_chunks_by_embedding(CAST(:embedding AS vector), :limit)"),
                {"embedding": str(vector), "limit": limit},
            ).fetchall()

            if not rows:
                return "No matching document chunks found."

            # Deduplicate document IDs while preserving order
            doc_ids = list(dict.fromkeys(row.document_id for row in rows))
            lines = [f"DOCUMENT_IDS: {','.join(str(i) for i in doc_ids)}", "---"]
            for i, row in enumerate(rows, 1):
                lines.append(
                    f"Chunk {i} (doc_id={row.document_id}, "
                    f"similarity={row.similarity:.3f}):\n{row.content}"
                )
            return "\n".join(lines)
        except Exception as exc:
            logger.warning("Vector search failed: %s", exc)
            return ""

    @tool
    def get_document_details(document_id: int) -> str:
        """Look up metadata for a specific document by its integer ID.

        Returns name, category, owner, date, and ingest status.
        """
        try:
            # Note: doc.owner_name lazy-loads the User relationship (N+1 if called in a loop).
            # Phase 3 should consider adding joinedload(Document.owner) if this becomes a hotspot.
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc is None:
                return "Document not found."
            return (
                f"Document ID: {doc.id}\n"
                f"Name: {doc.name}\n"
                f"Category: {doc.category}\n"
                f"Owner: {doc.owner_name}\n"
                f"Date: {doc.date}\n"
                f"Ingest status: {doc.ingest_status}"
            )
        except Exception as exc:
            raise ToolException(f"Document lookup failed: {exc}") from exc

    @tool
    def search_kg_flexible(keywords: str, limit: int = 10) -> str:
        """Flexible search in knowledge graph without knowing exact labels/relationships.

        Provide keywords about what you're looking for (e.g., "công ty", "nhà cung cấp",
        "hợp đồng", "báo giá", "mua bán"). This tool will:
        1. Search for nodes matching the keywords in name property
        2. Search for relationships containing the keywords
        3. Return all connected relationships automatically

        Use this when you don't know the exact Neo4j labels or relationship types.
        """
        if not neo4j_service.available:
            raise ToolException("Graph DB unavailable.")
        try:
            kw = keywords.lower().strip()

            # Search for nodes by name containing keywords
            cypher = f"""
            MATCH (n)-[r]-(m)
            WHERE toLower(n.name) CONTAINS '{kw}' OR toLower(m.name) CONTAINS '{kw}'
            RETURN n.name AS source, labels(n)[0] AS source_type,
                   type(r) AS relation, m.name AS target, labels(m)[0] AS target_type
            LIMIT {limit * 2}
            """
            rows = neo4j_service.run_cypher(cypher, {})

            if not rows:
                # Search by label (e.g., "công ty" -> NhaCungCap)
                label_map = {
                    "công ty": "NhaCungCap", "nhà cung cấp": "NhaCungCap", "ncc": "NhaCungCap",
                    "nhà máy": "NhaSanXuat", "sản xuất": "NhaSanXuat",
                    "vật tư": "VatTu", "vật liệu": "VatTu",
                    "hợp đồng": "HopDong",
                    "đơn hàng": "DonHang",
                    "báo giá": "ChaoGia", "chào giá": "ChaoGia",
                    "kho": "Kho",
                    "chứng chỉ": "ChungChi", "chứng nhận": "ChungChi",
                    "quy định": "QuyDinh",
                    "sự cố": "SuCo",
                    "kế hoạch": "KeHoachMuaSam",
                }

                found_label = None
                for key, label in label_map.items():
                    if key in kw:
                        found_label = label
                        break

                if found_label:
                    cypher = f"""
                    MATCH (n:{found_label})-[r]-(m)
                    RETURN n.name AS source, labels(n)[0] AS source_type,
                           type(r) AS relation, m.name AS target, labels(m)[0] AS target_type
                    LIMIT {limit * 2}
                    """
                    rows = neo4j_service.run_cypher(cypher, {})

            if not rows:
                # Search by relationship type containing keywords
                rel_keywords = ["cung cap", "cấp", "cung cấp", "mua", "bán", "chào giá",
                               "yêu cầu", "cần", "theo", "liên quan", "sản xuất", "nhập", "xuất"]
                for rkw in rel_keywords:
                    if rkw in kw:
                        cypher = f"""
                        MATCH (n)-[r]-(m)
                        WHERE toLower(type(r)) CONTAINS '{rkw}'
                        RETURN n.name AS source, labels(n)[0] AS source_type,
                               type(r) AS relation, m.name AS target, labels(m)[0] AS target_type
                        LIMIT {limit * 2}
                        """
                        rows = neo4j_service.run_cypher(cypher, {})
                        if rows:
                            break

            if not rows:
                # Try semantic search fallback
                vector = embed([keywords])[0]
                chunk_results = neo4j_service.search_similar_chunks(vector, limit)
                if chunk_results:
                    doc_ids = list(dict.fromkeys(str(r.get("document_id", "")) for r in chunk_results))
                    lines = [f"Found {len(chunk_results)} relevant document chunks:", ""]
                    for i, r in enumerate(chunk_results, 1):
                        lines.append(f"{i}. doc_id={r.get('document_id')}: {r.get('content', '')[:200]}...")
                    return "\n".join(lines)
                return f"Không tìm thấy kết quả nào cho từ khóa: {keywords}"

            # Group by unique relationships
            unique_results = []
            seen = set()
            for row in rows:
                key = (row.get("source", ""), row.get("relation", ""), row.get("target", ""))
                if key not in seen and row.get("source") and row.get("target"):
                    seen.add(key)
                    unique_results.append(row)

            unique_results = unique_results[:limit]

            lines = [f"Tìm thấy {len(unique_results)} kết quả cho '{keywords}':", ""]
            for i, row in enumerate(unique_results, 1):
                lines.append(
                    f"{i}. {row.get('source', '')} --[{row.get('relation', '')}]--> {row.get('target', '')}"
                )
            return "\n".join(lines)
        except Exception as exc:
            logger.warning("Flexible search failed: %s", exc)
            return f"Tìm kiếm thất bại: {exc}"

    @tool
    def list_kg_schema() -> str:
        """List all available node labels and relationship types in the knowledge graph.

        Use this to discover what labels and relationships exist in the database
        before writing queries.
        """
        if not neo4j_service.available:
            raise ToolException("Graph DB unavailable.")
        try:
            # Get all node labels
            label_cypher = "CALL db.labels() YIELD label RETURN label"
            labels = neo4j_service.run_cypher(label_cypher, {})

            # Get all relationship types
            rel_cypher = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
            rels = neo4j_service.run_cypher(rel_cypher, {})

            # Get sample nodes with names
            sample_cypher = """
            MATCH (n)
            WHERE n.name IS NOT NULL
            RETURN labels(n)[0] AS label, n.name AS name
            LIMIT 20
            """
            samples = neo4j_service.run_cypher(sample_cypher, {})

            lines = ["=== NODE LABELS ===", ", ".join([l.get("label", "") for l in labels])]
            lines.append("")
            lines.append("=== RELATIONSHIP TYPES ===")
            lines.append(", ".join([r.get("relationshipType", "") for r in rels]))
            lines.append("")
            lines.append("=== SAMPLE NODES ===")
            for s in samples:
                lines.append(f"- [{s.get('label', '')}] {s.get('name', '')}")

            return "\n".join(lines)
        except Exception as exc:
            return f"Failed to list schema: {exc}"

    @tool
    def llm_reasoning(question: str) -> str:
        """Analyze and reason about a user question to determine the best search strategy.

        This tool helps:
        1. Understand what the user is asking
        2. Identify key entities (companies, materials, contracts, etc.)
        3. Determine what type of information is needed
        4. Suggest the best search approach

        Use this first when the question is complex or unclear.
        """
        try:
            from openai import OpenAI
            client = OpenAI()

            prompt = f"""Bạn là một trợ lý AI phân tích câu hỏi để tìm kiếm thông tin trong knowledge graph.

Hãy phân tích câu hỏi sau và trả lời theo format JSON:

{{
    "cau_hoi_goc": "{question}",
    "thuc_the_chinh": "Tên các thực thể chính (công ty, vật tư, hợp đồng...)",
    "loai_thong_tin": "loại thông tin cần tìm (quan hệ, nội dung, thống kê...)",
    "tu_khoa_tim_kiem": "các từ khóa để tìm kiếm trong graph",
    "cau_hoi_chuan_hoa": "câu hỏi được chuẩn hóa",
    "giai_phap_de_xuat": "nên dùng tool nào (query_knowledge_graph / search_kg_flexible / search_kg_semantic)"
}}

CHỈ trả JSON, không giải thích gì thêm."""

            response = client.chat.completions.create(
                model="gpt-4o",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "Bạn là chuyên gia phân tích câu hỏi để tìm kiếm trong knowledge graph"},
                    {"role": "user", "content": prompt}
                ],
            )

            result = response.choices[0].message.content
            return result
        except Exception as exc:
            logger.warning("LLM reasoning failed: %s", exc)
            return f"Phân tích thất bại: {exc}"

    return [query_knowledge_graph, search_kg_semantic, search_kg_flexible, list_kg_schema, llm_reasoning, search_document_chunks, get_document_details]
