"""
Code shared by the scrapers that read HTML pages (ANR, Bpifrance).
Each of them first finds the list of calls, then calls add_page_details()
on every call to read its own page. add_page_details() returns the parsed page,
so a scraper can read more site-specific details without downloading it again.
"""
import logging

from utils import http_client, html_tools, pdf_tools
from utils.storage import join_list

log = logging.getLogger(__name__)

# Words that usually appear on the lines giving dates (opening, deadline, "relève"...)
DATE_KEYWORDS = ["ouverture", "clôture", "cloture", "fermeture", "limite", "date", "relève", "releve",
                 "deadline"]


def add_page_details(record, source, with_pdfs):
    """Open the page of one call and fill: page_text, dates_text, pdf_urls and the PDF text files.
    Returns the parsed page (BeautifulSoup), or None if the page could not be downloaded."""
    response = http_client.get(record["url"])
    if response is None:
        return None

    soup = html_tools.parse_html(response.text)

    if not record["title"]:
        record["title"] = html_tools.page_title(soup)

    # PDF links first (visible_text() below removes some tags from the soup)
    pdf_urls = html_tools.find_pdf_links(soup, record["url"])
    record["pdf_urls"] = join_list(pdf_urls)

    record["page_text"] = html_tools.main_text(response.text)

    # Dates are often in a side block that the main-text extractor drops,
    # so we search for them in the whole visible text of the page.
    full_text = html_tools.visible_text(soup)
    date_lines = html_tools.short_lines_with_keywords(full_text, DATE_KEYWORDS)
    record["dates_text"] = join_list(date_lines)

    if with_pdfs and pdf_urls:
        txt_files, methods = pdf_tools.process_pdfs(pdf_urls, source)
        record["pdf_text_files"] = join_list(txt_files)
        record["pdf_methods"] = join_list(methods)

    return soup
