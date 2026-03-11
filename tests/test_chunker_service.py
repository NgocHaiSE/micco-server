import pytest
from services.chunker_service import chunk_text


def test_chunk_text_returns_list_of_dicts():
    pages = ["Hello world. " * 50]
    chunks = chunk_text(pages)
    assert isinstance(chunks, list)
    assert len(chunks) > 0
    for c in chunks:
        assert "chunk_index" in c
        assert "content" in c
        assert "char_start" in c


def test_chunk_indices_are_sequential():
    pages = ["A " * 300]
    chunks = chunk_text(pages)
    for i, c in enumerate(chunks):
        assert c["chunk_index"] == i


def test_empty_pages_returns_empty_list():
    assert chunk_text([]) == []
    assert chunk_text([""]) == []


def test_single_short_page_produces_one_chunk():
    pages = ["Short text."]
    chunks = chunk_text(pages)
    assert len(chunks) == 1
    assert chunks[0]["content"] == "Short text."
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["char_start"] == 0


def test_long_text_is_split():
    pages = ["x " * 2500]
    chunks = chunk_text(pages)
    assert len(chunks) > 1


def test_chunk_size_parameter():
    pages = ["word " * 200]
    chunks_small = chunk_text(pages, chunk_size=100, overlap=10)
    chunks_large = chunk_text(pages, chunk_size=500, overlap=10)
    assert len(chunks_small) > len(chunks_large)
