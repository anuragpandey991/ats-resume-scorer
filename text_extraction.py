"""
text_extraction.py
Extracts and cleans raw text from uploaded resume files (PDF / DOCX).
JD is handled as plain pasted text in the UI, so no extraction needed for it.
"""

import re
import io
import pdfplumber
import docx


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file given as bytes."""
    text_chunks = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_chunks.append(page_text)
    return "\n".join(text_chunks)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file given as bytes."""
    doc = docx.Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    # Also grab text inside tables (some resumes use table layouts)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    paragraphs.append(cell.text)
    return "\n".join(paragraphs)


def clean_text(raw_text: str) -> str:
    """Basic cleanup: normalize whitespace, remove weird bullet characters."""
    if not raw_text:
        return ""
    text = raw_text.replace("\u2022", " ").replace("\uf0b7", " ")  # bullet glyphs
    # PDF icon fonts (LinkedIn/email/phone icons rendered as glyphs with no real
    # text mapping) often extract as raw "(cid:123)" character-ID placeholders.
    # These are extraction artifacts, not real words — strip them before any
    # downstream text analysis (especially grammar checking) sees them.
    text = re.sub(r"\(cid:\d+\)", " ", text)
    # Private Use Area unicode characters (U+E000-U+F8FF) are also commonly
    # used by icon fonts and show up as mojibake/garbled single characters
    # (e.g. a phone or LinkedIn icon glyph). Strip these too.
    text = re.sub(r"[\uE000-\uF8FF]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)          # collapse repeated spaces/tabs
    text = re.sub(r"\n\s*\n+", "\n", text)        # collapse multiple blank lines
    text = text.strip()
    return text


def extract_resume_text(uploaded_file) -> str:
    """
    Given a Streamlit UploadedFile object, detect type by extension
    and return cleaned text. Raises ValueError for unsupported types.
    """
    filename = uploaded_file.name.lower()
    file_bytes = uploaded_file.read()

    if filename.endswith(".pdf"):
        raw = extract_text_from_pdf(file_bytes)
    elif filename.endswith(".docx"):
        raw = extract_text_from_docx(file_bytes)
    else:
        raise ValueError("Unsupported file type. Please upload a PDF or DOCX resume.")

    cleaned = clean_text(raw)
    if not cleaned:
        raise ValueError(
            "No extractable text found. The file might be a scanned image "
            "(no OCR support in this version) or empty."
        )
    return cleaned


if __name__ == "__main__":
    # Quick manual test with a plain text string, since we have no sample files here.
    sample = "Experience\n\u2022 Built REST APIs\n\n\n\u2022 Led   a team of 5"
    print(repr(clean_text(sample)))
