"""
The common format of a "call for proposals" row, and how to save the rows.

Every scraper fills the SAME columns, whatever the website looks like.
When a website does not give a piece of information, the column stays empty:
it will be filled later by the NLP step (see extraction/field_extractor.py).
"""
import os
import csv
import re
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

# All the calls we collect are French or European: dates are given in Paris time
PARIS = ZoneInfo("Europe/Paris")

COLUMNS = [
    "source",          # which scraper produced the row: anr, bpifrance, horizon, region_idf
    "source_id",       # identifier of the call on its website (slug, topic code...)
    "title",
    "funder",
    "call_type",       # e.g. "France 2030", "RIA", "Appel à projets spécifique"
    "status",          # as written by the source: open, forthcoming, pré-annonce...
    "opening_date",    # YYYY-MM-DD when we could read it, empty otherwise
    "deadline",        # YYYY-MM-DD when we could read it, empty otherwise
    "dates_text",      # raw lines about dates, kept as-is for the NLP step
    "summary",
    "page_text",       # main text of the web page (or the description given by the API)
    "pdf_urls",        # PDF links found on the page, separated by " | "
    "pdf_text_files",  # local .txt files containing the text extracted from the PDFs
    "pdf_methods",     # how each PDF was read: text_layer or ocr
    "url",             # page of the call (to check by hand)
    "collected_at",    # when we collected it
]

# Excel cannot display more than 32 767 characters in one cell.
# The full PDF texts are in .txt files anyway, so we cut very long page texts in the CSV.
MAX_CELL_CHARS = 30000

DATE_FR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
DATE_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def new_record(source):
    """Create an empty row containing every column, so all sources share the same format."""
    record = {}
    for column in COLUMNS:
        record[column] = ""
    record["source"] = source
    record["collected_at"] = datetime.now().isoformat(timespec="seconds")
    return record


def join_list(values):
    """Turn a Python list into a single CSV-friendly string."""
    return " | ".join(values)


def to_iso_date(text):
    """Convert '16/11/2026' or '2026-11-16T17:00:00' into '2026-11-16'. Returns '' if no date found.
    A date with a time zone (e.g. '2026-08-31T22:00:00+00:00') is first converted to Paris time,
    otherwise midnight in Paris (22:00 UTC) would give the day before."""
    if not text:
        return ""
    paris_date = to_paris_date(text)
    if paris_date:
        return paris_date
    match = DATE_FR.search(text)
    if match:
        day, month, year = match.groups()
        return year + "-" + month + "-" + day
    match = DATE_ISO.search(text)
    if match:
        return match.group(0)
    return ""


def to_paris_date(text):
    """Read a full ISO date-time with a time zone and return its day in Paris ('' if not possible)."""
    try:
        moment = datetime.fromisoformat(text.strip())
    except ValueError:
        return ""
    if moment.tzinfo is None:
        return ""  # no time zone given: to_iso_date() keeps the date as written
    return moment.astimezone(PARIS).date().isoformat()


def today_iso():
    """Return today's date as 'YYYY-MM-DD', to compare it with the dates of the calls."""
    return datetime.now(PARIS).date().isoformat()


def save_to_csv(records, path):
    """Write all the rows into one CSV file (utf-8-sig so that Excel shows accents correctly)."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = dict(record)
            for column in COLUMNS:
                if len(row[column]) > MAX_CELL_CHARS:
                    row[column] = row[column][:MAX_CELL_CHARS] + " [...]"
            writer.writerow(row)
    log.info("%d rows saved in %s", len(records), path)


def save_to_postgres(records):
    """Placeholder for later: insert the rows into PostgreSQL (one table with the same COLUMNS).
    Suggested key to avoid duplicates between weekly runs: (source, source_id)."""
    log.warning("save_to_postgres is not implemented yet, nothing saved in the database")
