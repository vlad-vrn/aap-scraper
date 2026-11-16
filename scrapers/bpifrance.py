"""
Scraper for Bpifrance ("Appels à projets et concours").

Listing page: https://www.bpifrance.fr/nos-appels-a-projets-concours
Every call has its own page under /nos-appels-a-projets-concours/<name-of-the-call>.
Bpifrance has no API, so we read the HTML:
  1. go through the listing pages (?page=0, ?page=1...) and collect the call links,
  2. open each call page (text, date lines, "cahier des charges" PDFs).

Notes:
  - robots.txt is checked automatically by utils/http_client.py.
  - The CGU of the site must also be checked by hand before running it every week.
  - If Bpifrance answers HTTP 403, it is an anti-bot protection: the log will say it.

Run alone for a quick test:  python -m scrapers.bpifrance
"""
import logging
from urllib.parse import urljoin

from utils import http_client, html_tools
from utils.storage import new_record
from scrapers.common import add_page_details

log = logging.getLogger(__name__)

SOURCE = "bpifrance"
BASE_URL = "https://www.bpifrance.fr"
LIST_URL = BASE_URL + "/nos-appels-a-projets-concours"
CALL_PATH = "/nos-appels-a-projets-concours/"
MAX_LIST_PAGES = 15  # safety limit, in case the pagination never stops


def clean_url(href):
    """Make a link absolute and remove what comes after ? or # (so duplicates are detected)."""
    url = urljoin(BASE_URL, href)
    url = url.split("#")[0].split("?")[0]
    return url.rstrip("/")


def collect_call_links(max_items):
    """Go through the listing pages and collect the links that point to a call page."""
    links = []
    for page_number in range(MAX_LIST_PAGES):
        response = http_client.get(LIST_URL, params={"page": page_number})
        if response is None:
            break

        soup = html_tools.parse_html(response.text)
        new_links = 0
        for link in soup.find_all("a", href=True):
            url = clean_url(link["href"])
            if CALL_PATH in url + "/" and url != LIST_URL and url not in links:
                links.append(url)
                new_links += 1

        log.info("Bpifrance: listing page %d -> %d new calls", page_number, new_links)
        if new_links == 0:
            break  # nothing new: we reached the last page
        if max_items and len(links) >= max_items:
            break
    return links


def scrape(max_items=None, with_pdfs=True):
    """Collect the Bpifrance calls: listing pages first, then each call page (and its PDFs)."""
    links = collect_call_links(max_items)
    log.info("Bpifrance: %d calls found", len(links))
    if max_items:
        links = links[:max_items]

    records = []
    for url in links:
        record = new_record(SOURCE)
        record["funder"] = "Bpifrance"
        record["url"] = url
        record["source_id"] = url.split("/")[-1]
        # Bpifrance mostly operates calls for the State (France 2030...): type and status
        # are not shown in a uniform way, so we leave them to the extraction step.
        add_page_details(record, SOURCE, with_pdfs)
        records.append(record)
        log.info("Bpifrance: %s", record["title"][:80])
    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for row in scrape(max_items=3, with_pdfs=False):
        print(row["title"], "|", row["dates_text"][:120], "|", row["pdf_urls"][:100])
