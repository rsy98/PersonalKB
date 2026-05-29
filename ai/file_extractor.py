import os


TEXT_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.java', '.cpp', '.c', '.html',
    '.css', '.json', '.yaml', '.yml', '.xml', '.csv', '.rst', '.tex',
    '.vim', '.sty', '.bib', '.def',
}

DOCX_EXTENSIONS = {'.docx'}
PDF_EXTENSIONS = {'.pdf'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}


class FileExtractor:
    """Extract text content from files by extension."""

    @staticmethod
    def is_supported(filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in TEXT_EXTENSIONS | DOCX_EXTENSIONS | PDF_EXTENSIONS

    @staticmethod
    def is_image(filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in IMAGE_EXTENSIONS

    @staticmethod
    def extract(filepath: str) -> str | None:
        """Extract text from a file. Returns None if unsupported."""
        ext = os.path.splitext(filepath)[1].lower()

        if ext in TEXT_EXTENSIONS:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()

        if ext in PDF_EXTENSIONS:
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(filepath)
                pages = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return '\n\n'.join(pages)
            except ImportError:
                return None
            except Exception:
                return None

        if ext in DOCX_EXTENSIONS:
            try:
                from docx import Document
                doc = Document(filepath)
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                return '\n\n'.join(paragraphs)
            except ImportError:
                return None
            except Exception:
                return None

        return None
