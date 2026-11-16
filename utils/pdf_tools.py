"""
Everything about PDFs: download them, then get their text.

Strategy:
  1. Most call-for-proposals PDFs are "digital" PDFs: the text is already inside,
     pdfplumber reads it directly (fast and exact).
  2. Only if a PDF has almost no text (= it is a scanned image), we try OCR.
     OCR is optional: it needs Tesseract and Poppler installed on the computer.
"""
import os
import hashlib
import logging

import pdfplumber

import config
from utils import http_client

log = logging.getLogger(__name__)


def pdf_file_name(url):
    """Build a short and unique file name from a PDF URL (hash + end of the original name)."""
    short_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:10]
    original_name = url.split("/")[-1].split("?")[0]
    if not original_name.lower().endswith(".pdf"):
        original_name = original_name + ".pdf"
    return short_hash + "_" + original_name[-60:]


def download_pdf(url, source_name):
    """Download a PDF into data/pdfs/<source>/ and return its local path (None if it failed)."""
    folder = os.path.join(config.PDF_DIR, source_name)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, pdf_file_name(url))

    if os.path.exists(path):
        return path  # already downloaded during a previous run

    response = http_client.get(url)
    if response is None:
        return None

    # Some "PDF" links actually lead to an HTML page: check the file really is a PDF
    if not response.content.startswith(b"%PDF"):
        log.warning("Not a real PDF, skipped: %s", url)
        return None

    with open(path, "wb") as file:
        file.write(response.content)
    return path


def extract_text_with_pdfplumber(path):
    """Read the text layer of a PDF page by page. Returns (text, number_of_pages)."""
    pages_text = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages_text.append(page.extract_text() or "")
    return "\n\n".join(pages_text), len(pages_text)


def extract_text_with_ocr(path):
    """Read a scanned PDF with OCR (Tesseract). Returns '' if the OCR tools are not installed."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        log.info("OCR libraries not installed, OCR skipped for %s", path)
        return ""

    try:
        images = convert_from_path(path, dpi=200)
    except Exception as error:
        log.warning("Could not turn the PDF into images (is Poppler installed?): %s", error)
        return ""

    pages_text = []
    for image in images:
        pages_text.append(pytesseract.image_to_string(image, lang=config.OCR_LANGUAGES))
    return "\n\n".join(pages_text)


def pdf_to_text(path):
    """Get the text of a PDF: text layer first, OCR only if the PDF looks scanned.
    Returns (text, method) where method is 'text_layer' or 'ocr'."""
    try:
        text, nb_pages = extract_text_with_pdfplumber(path)
    except Exception as error:
        log.warning("pdfplumber could not read %s: %s", path, error)
        text, nb_pages = "", 1

    chars_per_page = len(text.strip()) / max(nb_pages, 1)
    if chars_per_page >= config.OCR_MIN_CHARS_PER_PAGE:
        return text, "text_layer"

    log.info("Little text found in %s, trying OCR", path)
    ocr_text = extract_text_with_ocr(path)
    if len(ocr_text.strip()) > len(text.strip()):
        return ocr_text, "ocr"
    return text, "text_layer"


def process_pdfs(pdf_urls, source_name):
    """For one call: download its PDFs, extract their text and save it in a .txt next to each PDF.
    Returns two lists: the .txt paths and the method used for each PDF."""
    txt_paths = []
    methods = []
    for url in pdf_urls[:config.MAX_PDFS_PER_CALL]:
        pdf_path = download_pdf(url, source_name)
        if pdf_path is None:
            continue
        text, method = pdf_to_text(pdf_path)
        txt_path = pdf_path[:-4] + ".txt"
        with open(txt_path, "w", encoding="utf-8") as file:
            file.write(text)
        txt_paths.append(txt_path)
        methods.append(method)
    return txt_paths, methods
