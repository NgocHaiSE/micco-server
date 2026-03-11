import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_driver():
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver, session


def test_connect_sets_available_true(mock_driver):
    driver, _ = mock_driver
    with patch("services.neo4j_service.GraphDatabase.driver", return_value=driver):
        from services.neo4j_service import Neo4jService
        svc = Neo4jService.__new__(Neo4jService)
        svc.available = False
        svc._driver = None
        svc.uri = "bolt://localhost:7687"
        svc.user = "neo4j"
        svc.password = "test"
        svc.connect()
        assert svc.available is True


def test_connect_sets_available_false_on_error():
    with patch("services.neo4j_service.GraphDatabase.driver", side_effect=Exception("conn refused")):
        from services.neo4j_service import Neo4jService
        svc = Neo4jService.__new__(Neo4jService)
        svc.available = True
        svc._driver = None
        svc.uri = "bolt://localhost:7687"
        svc.user = "neo4j"
        svc.password = "wrong"
        svc.connect()
        assert svc.available is False


def test_merge_document_node_runs_cypher(mock_driver):
    driver, session = mock_driver
    with patch("services.neo4j_service.GraphDatabase.driver", return_value=driver):
        from services.neo4j_service import Neo4jService
        svc = Neo4jService.__new__(Neo4jService)
        svc.available = True
        svc._driver = driver
        doc = {
            "document_id": 42,
            "label": "VatTu",
            "ten": "Thep CT3",
            "owner": "admin",
            "created_at": "2026-01-01",
        }
        svc.merge_document_node(doc)
        assert session.run.called
        cypher_call = session.run.call_args
        assert "MERGE" in cypher_call[0][0]
        assert cypher_call[1]["document_id"] == 42


def test_merge_document_node_noop_when_unavailable(mock_driver):
    driver, session = mock_driver
    from services.neo4j_service import Neo4jService
    svc = Neo4jService.__new__(Neo4jService)
    svc.available = False
    svc._driver = driver
    svc.merge_document_node({"document_id": 1, "label": "VatTu", "ten": "", "owner": "", "created_at": ""})
    session.run.assert_not_called()


def test_create_chunk_node_runs_cypher(mock_driver):
    driver, session = mock_driver
    with patch("services.neo4j_service.GraphDatabase.driver", return_value=driver):
        from services.neo4j_service import Neo4jService
        svc = Neo4jService.__new__(Neo4jService)
        svc.available = True
        svc._driver = driver
        svc.create_chunk_node(document_id=42, chunk_idx=0)
        assert session.run.called
        cypher_call = session.run.call_args
        assert "HAS_CHUNK" in cypher_call[0][0]
        assert cypher_call[1]["document_id"] == 42
        assert cypher_call[1]["chunk_index"] == 0
