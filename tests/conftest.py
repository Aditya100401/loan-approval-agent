"""Shared pytest fixtures."""

import fitz
import pytest


@pytest.fixture
def make_pdf(tmp_path):
    """Factory: writes a single-page PDF with the given text, returns the path."""
    def _make(text: str) -> str:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 72), text)
        path = str(tmp_path / "test.pdf")
        doc.save(path)
        doc.close()
        return path
    return _make
