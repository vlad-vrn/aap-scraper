"""
Scraper for Horizon Europe, through the public search API of the EU Funding & Tenders portal.

No HTML scraping here: the portal is a JavaScript app, but it uses a public API
(no account, apiKey=SEDIA is the public key used by the portal itself).
The API wants a POST request where the filters are sent as JSON "files".

The filters use numeric codes that are not documented much. The ones we use:
  - frameworkProgramme 43108390 = Horizon Europe
  - status 31094501 = forthcoming, 31094502 = open for submission
  - type 1 and 2 = grant topics / calls

Warning: the index of the API contains old entries (indexed in 2022-2023 and never updated)
that are still marked "open" or "forthcoming" although all their deadlines are past.
A date filter in the query is ignored by the API, so we remove them ourselves (is_outdated).

The results are sorted by identifier, which is unique. With a sort on the deadline, many
topics share the same date, their order changes from one page to the next, and some topics
were returned twice while others were never returned.

The topic description is in the API answer, so we don't download PDFs for this source
(the Horizon "work programme" PDFs are huge documents shared by hundreds of topics).

Run alone for a quick test:  python -m scrapers.horizon
"""
import json
import logging

from utils import http_client, html_tools
from utils.storage import new_record, to_iso_date, join_list, today_iso

log = logging.getLogger(__name__)

SOURCE = "horizon"
API_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
TOPIC_PAGE_URL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/"

HORIZON_EUROPE = "43108390"
STATUS_FORTHCOMING = "31094501"
STATUS_OPEN = "31094502"
STATUS_LABELS = {STATUS_FORTHCOMING: "forthcoming", STATUS_OPEN: "open", "31094503": "closed"}

PAGE_SIZE = 50
MAX_PAGES = 40  # safety limit: 40 x 50 = 2000 topics max


def build_query():
    """Build the search filter: Horizon Europe topics that are open or forthcoming."""
    return {
        "bool": {
            "must": [
                {"terms": {"type": ["1", "2"]}},
                {"terms": {"status": [STATUS_FORTHCOMING, STATUS_OPEN]}},
                {"terms": {"frameworkProgramme": [HORIZON_EUROPE]}},
            ]
        }
    }


def fetch_page(page_number):
    """Ask the API for one page of results. Returns (results, total_number_of_results)."""
    params = {"apiKey": "SEDIA", "text": "***", "pageSize": PAGE_SIZE, "pageNumber": page_number}
    # The API reads its filters from multipart "files", hence this format
    files = {
        "query": ("blob", json.dumps(build_query()), "application/json"),
        "languages": ("blob", json.dumps(["en"]), "application/json"),
        "sort": ("blob", json.dumps({"order": "ASC", "field": "identifier"}), "application/json"),
    }
    response = http_client.post(API_URL, params=params, files=files)
    if response is None:
        return [], 0
    try:
        data = response.json()
    except ValueError:
        log.warning("Horizon: the API did not answer valid JSON")
        return [], 0
    return data.get("results", []), data.get("totalResults", 0)


def first_value(metadata, key):
    """The API stores each field as a list: return its first element, or '' if it is missing."""
    values = metadata.get(key)
    if not values:
        return ""
    return str(values[0])


def next_deadline(deadlines):
    """Return the first deadline that is today or later, or the last one if they are all past.
    The deadlines must be sorted 'YYYY-MM-DD' strings (this format sorts like dates)."""
    today = today_iso()
    for deadline in deadlines:
        if deadline >= today:
            return deadline
    return deadlines[-1]


def is_outdated(record):
    """Tell if a topic is an old entry of the index: its (last) deadline is already past."""
    if not record["deadline"]:
        return False  # no deadline given: we keep it, the NLP step will look at the text
    return record["deadline"] < today_iso()


def result_to_record(result):
    """Turn one API result into a row with the common format."""
    metadata = result.get("metadata", {})
    identifier = first_value(metadata, "identifier")

    record = new_record(SOURCE)
    record["funder"] = "Commission européenne (Horizon Europe)"
    record["source_id"] = identifier
    record["title"] = first_value(metadata, "title") or result.get("summary", "")
    # " ".join(split()) removes the double spaces found in some values ("HORIZON  Research...")
    record["call_type"] = " ".join(first_value(metadata, "typesOfAction").split())
    record["status"] = STATUS_LABELS.get(first_value(metadata, "status"), first_value(metadata, "status"))
    record["opening_date"] = to_iso_date(first_value(metadata, "startDate"))

    # Some topics have several deadlines (two-stage topics, EIC cut-off dates):
    # deadline = the next one that is not past yet (or the last one if all are past),
    # and all of them are kept in dates_text.
    deadlines = []
    for value in metadata.get("deadlineDate", []):
        deadlines.append(to_iso_date(str(value)))
    deadlines.sort()
    if deadlines:
        record["deadline"] = next_deadline(deadlines)
        record["dates_text"] = "deadlines: " + join_list(deadlines)

    call_title = first_value(metadata, "callTitle")
    call_id = first_value(metadata, "callIdentifier")
    if call_title:
        record["summary"] = "Call: " + call_title + " (" + call_id + ")"

    record["page_text"] = html_tools.html_to_text(first_value(metadata, "descriptionByte"))
    record["url"] = TOPIC_PAGE_URL + identifier
    return record


def scrape(max_items=None, with_pdfs=True):
    """Collect the open and forthcoming Horizon Europe topics, page by page.
    (with_pdfs is accepted for consistency with the other scrapers but not used here.)"""
    records = []
    seen_ids = []
    outdated = 0
    page_number = 1
    while page_number <= MAX_PAGES:
        results, total = fetch_page(page_number)
        if page_number == 1:
            log.info("Horizon: %s topics announced by the API", total)

        for result in results:
            record = result_to_record(result)
            # The API can return the same topic twice (several document versions)
            if not record["source_id"] or record["source_id"] in seen_ids:
                continue
            seen_ids.append(record["source_id"])
            if is_outdated(record):
                outdated += 1
                continue
            records.append(record)
            if max_items and len(records) >= max_items:
                return records

        if len(results) < PAGE_SIZE:
            break  # last page reached
        page_number += 1
    log.info("Horizon: %d outdated topics skipped (all their deadlines are past)", outdated)
    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for row in scrape(max_items=5):
        print(row["source_id"], "|", row["status"], "|", row["deadline"], "|", row["title"][:70])
