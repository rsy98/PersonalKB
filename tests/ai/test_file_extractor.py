import os
import tempfile
import pytest
from ai.file_extractor import FileExtractor


class TestFileExtractor:
    def test_extract_txt(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Hello world\n这是中文内容")
            path = f.name
        try:
            text = FileExtractor.extract(path)
            assert "Hello world" in text
            assert "这是中文内容" in text
        finally:
            os.unlink(path)

    def test_extract_markdown(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("# Title\n\nSome content here.")
            path = f.name
        try:
            text = FileExtractor.extract(path)
            assert "# Title" in text
        finally:
            os.unlink(path)

    def test_extract_python(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write("def hello():\n    return 'world'\n")
            path = f.name
        try:
            text = FileExtractor.extract(path)
            assert "def hello()" in text
        finally:
            os.unlink(path)

    def test_extract_unsupported_returns_none(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False) as f:
            f.write("data")
            path = f.name
        try:
            text = FileExtractor.extract(path)
            assert text is None
        finally:
            os.unlink(path)

    def test_is_supported(self):
        assert FileExtractor.is_supported("doc.pdf") is True
        assert FileExtractor.is_supported("doc.docx") is True
        assert FileExtractor.is_supported("doc.txt") is True
        assert FileExtractor.is_supported("doc.md") is True
        assert FileExtractor.is_supported("doc.xyz") is False

    def test_is_image(self):
        assert FileExtractor.is_image("photo.png") is True
        assert FileExtractor.is_image("photo.jpg") is True
        assert FileExtractor.is_image("photo.jpeg") is True
        assert FileExtractor.is_image("photo.gif") is True
        assert FileExtractor.is_image("photo.webp") is True
        assert FileExtractor.is_image("doc.pdf") is False
