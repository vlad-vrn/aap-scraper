"""
Scraper for the ANR (Agence nationale de la recherche).

Listing page: https://anr.fr/fr/appels/ ("Appels en cours et à venir", all calls on one page).
On this page, each call is a block with:
  - a type line ("Appel à projets spécifique", "France 2030"),
  - a period line ("16/11/2026 - 25/05/2027" or "Novembre 2026 - Juin 2027"),
  - a <h2> title with a link to the call page (URL containing "/call/"),
  - a short summary, and sometimes the label "Pré-annonce".
The call page contains the full text, the PDFs (call text, annexes) and a calendar:
one <div class="task"> per step ("Ouverture :", "Fermeture :"...), whose attribute
data-date gives the exact date in ISO format, e.g. data-date="2027-01-28T11:00:00+01:00".

Run alone for a quick test:  python -m scrapers.anr
"""
import re
import logging
from urllib.parse import urljoin

from utils import http_client, html_tools
from utils.storage import new_record, to_iso_date
from scrapers.common import add_page_details

log = logging.getLogger(__name__)

SOURCE = "anr"
LIST_URL = "https://anr.fr/fr/appels/"

DATE_RANGE = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
EXACT_DATE = re.compile(r"\d{2}/\d{2}/\d{4}")

# Labels of the calendar steps on a call page
OPENING_LABELS = ["ouverture"]
DEADLINE_LABELS = ["fermeture", "clôture", "cloture", "limite"]


def find_card_block(h2):
    """Climb up from a call title to the HTML block holding this call only (type, dates, summary).
    We stop just before reaching a block that contains several titles, i.e. several calls."""
    block = h2
    for _ in range(4):
        parent = block.parent
        if parent is None:
            break
        if len(parent.find_all("h2")) > 1:
            break
        block = parent
    return block


def get_call_cards(soup):
    """Find every call of the listing page. A call = a <h2> containing a link to a '/call/' page."""
    cards = []
    for h2 in soup.find_all("h2"):
        link = h2.find("a", href=True)
        if link is None or "/call/" not in link["href"]:
            continue
        block = find_card_block(h2)
        cards.append({
            "title": link.get_text(" ", strip=True),
            "url": urljoin(LIST_URL, link["href"]),
            "text": block.get_text("\n", strip=True),
            "period": read_period(block),
        })
    return cards


def read_period(block):
    """Read the period of a card, e.g. '16/11/2026 - 25/05/2027' or 'Novembre 2026 - Juin 2027'.
    It is in <div class="date">, where the two dates are on separate lines of the HTML:
    we join all the words with single spaces so that DATE_RANGE can find the two dates."""
    date_block = block.find(class_="date")
    if date_block is None:
        return ""
    words = date_block.get_text(" ").split()
    return " ".join(words)


def read_summary(card_text, title):
    """The summary is the longest line of the card (other lines are short labels or links)."""
    best = ""
    for line in card_text.splitlines():
        if line == title or line.startswith("Plus de détails"):
            continue
        if len(line) > len(best):
            best = line
    return best


def card_to_record(card):
    """Turn one card of the listing page into a row with the common format."""
    record = new_record(SOURCE)
    record["funder"] = "ANR"
    record["title"] = card["title"]
    record["url"] = card["url"]
    record["source_id"] = card["url"].rstrip("/").split("/")[-1]
    record["call_type"] = card["text"].splitlines()[0]
    record["summary"] = read_summary(card["text"], card["title"])

    if "pré-annonce" in card["text"].lower():
        record["status"] = "pré-annonce"
    else:
        record["status"] = "ouvert"

    period = card["period"]
    record["dates_text"] = period
    match = DATE_RANGE.search(period)
    if match:
        record["opening_date"] = to_iso_date(match.group(1))
        record["deadline"] = to_iso_date(match.group(2))
    return record


def read_calendar(soup):
    """Read the calendar of a call page: a list of (label, iso_date) for each step,
    e.g. ('Fermeture :', '2027-01-28T11:00:00+01:00').
    For a pre-announcement the page only shows a month ('Février 2027') but data-date
    holds an estimated day: such steps are skipped, we only keep the dates shown as dd/mm/yyyy."""
    steps = []
    for task in soup.find_all("div", class_="task"):
        if not EXACT_DATE.search(task.get_text(" ")):
            continue
        title = task.find(class_="task-title")
        if title is None:
            label = ""
        else:
            label = title.get_text(" ", strip=True)
        steps.append((label, task.get("data-date", "")))
    return steps


def label_contains(label, words):
    """Tell if a calendar label contains one of the given words (case-insensitive)."""
    lower_label = label.lower()
    for word in words:
        if word in lower_label:
            return True
    return False


def add_calendar_dates(record, soup):
    """Use the calendar of the call page to set the exact opening date and deadline.
    These dates are more precise than the period of the listing page, so they replace it.
    If there are several deadlines (pre-proposals, then full proposals), we keep the first one."""
    steps = read_calendar(soup)
    opening = ""
    deadline = ""
    for label, iso_date in steps:
        if label_contains(label, OPENING_LABELS) and not opening:
            opening = to_iso_date(iso_date)
        if label_contains(label, DEADLINE_LABELS) and not deadline:
            deadline = to_iso_date(iso_date)

    if opening:
        record["opening_date"] = opening
    if deadline:
        record["deadline"] = deadline


def scrape(max_items=None, with_pdfs=True):
    """Collect the ANR calls: read the listing page, then open each call page (and its PDFs)."""
    response = http_client.get(LIST_URL)
    if response is None:
        return []

    cards = get_call_cards(html_tools.parse_html(response.text))
    log.info("ANR: %d calls found on the listing page", len(cards))
    if max_items:
        cards = cards[:max_items]

    records = []
    for card in cards:
        record = card_to_record(card)
        listing_dates = record["dates_text"]
        soup = add_page_details(record, SOURCE, with_pdfs)
        if soup is not None:
            add_calendar_dates(record, soup)
        # Keep the period of the listing in front of the detailed date lines
        if listing_dates:
            record["dates_text"] = listing_dates + " | " + record["dates_text"]
        records.append(record)
        log.info("ANR: %s", record["title"][:80])
    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for row in scrape(max_items=3, with_pdfs=False):
        print(row["title"], "|", row["opening_date"], "->", row["deadline"], "|", row["pdf_urls"][:100])
