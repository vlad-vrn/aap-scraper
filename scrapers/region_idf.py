"""
Scraper for the Région Île-de-France, through its open data.

Dataset "Aides et appels à projets de la Région" (the one used to build
https://www.iledefrance.fr/aides-et-appels-a-projets), published on data.iledefrance.fr.
We download the whole dataset as JSON: no HTML scraping needed.

The documents of each aid (PDF, Word, Excel...) are in a second dataset,
"documents-publics-des-aides-regionales", linked by the administrative reference of the aid.
We keep only the PDFs, "Document d'information" first (the "Document nécessaire" are
mostly forms to fill in).

The column names below were checked on 16/11/2026. If the Region changes them, run:
    python -m scrapers.region_idf --columns
The dataset has no column for the type nor the status of an aid:
call_type stays empty, and the status is computed from the dates (see compute_status).
All the dates are given in UTC (e.g. "2026-08-31T22:00:00+00:00" = 1 September, midnight
in Paris): to_iso_date() converts them to Paris time.

Warning: this dataset contains ALL the aids of the Region (sport, culture, companies...),
not only research, and also the closed ones (status "clos"). Filtering by relevance is the
job of the matching step, not of the scraper.

Run alone for a quick test:  python -m scrapers.region_idf
"""
import sys
import logging

from utils import http_client, html_tools, pdf_tools
from utils.storage import new_record, to_iso_date, join_list, today_iso

log = logging.getLogger(__name__)

SOURCE = "region_idf"

# Official open data API (Opendatasoft), and the same file through data.gouv.fr as a backup
DATA_URL = "https://data.iledefrance.fr/api/explore/v2.1/catalog/datasets/aides-appels-a-projets/exports/json"
BACKUP_DATA_URL = "https://www.data.gouv.fr/api/1/datasets/r/6833b7a1-9a0d-4639-a243-711d3edd7f14"
DOCUMENTS_URL = ("https://data.iledefrance.fr/api/explore/v2.1/catalog/datasets/"
                 "documents-publics-des-aides-regionales/exports/json")
WEBSITE_URL = "https://www.iledefrance.fr/aides-et-appels-a-projets"

# Columns of the dataset
ID_COLUMN = "reference_administrative"
TITLE_COLUMNS = ["titre_alternatif_de_l_aide", "nom_de_l_aide_de_la_demarche"]  # first non-empty one
SUMMARY_COLUMNS = ["chapo_txt", "entete"]
OPENING_COLUMN = "date_ouverture"
DEADLINE_COLUMN = "date_cloture"
NEXT_CAMPAIGN_COLUMN = "datedebutfuturcampagne"
URL_COLUMN = "url_descriptif"

# Technical columns (identifiers, codes, duplicates) left out of page_text
TECHNICAL_COLUMNS = ["id_aide", "id_theme", "id_publics", "porteur_siren", "competences",
                     "recup_id_thm", "presence_ref", "qui", "libelle", "date"]


def download_json(urls):
    """Download a dataset as a list of dicts, trying each URL in turn ([] if they all fail)."""
    for url in urls:
        response = http_client.get(url, check_robots=False)  # official open data, made to be downloaded
        if response is None:
            continue
        try:
            rows = response.json()
        except ValueError:
            log.warning("Région IDF: invalid JSON at %s", url)
            continue
        if isinstance(rows, list):
            return rows
    return []


def download_rows():
    """Download the dataset of the aids (one dict per aid). Tries the backup URL if needed."""
    return download_json([DATA_URL, BACKUP_DATA_URL])


def download_pdf_links():
    """Download the documents dataset and return {administrative reference: [PDF URLs]}.
    For each aid, the information documents come before the forms to fill in."""
    documents = download_json([DOCUMENTS_URL])
    information_links = {}
    other_links = {}
    for document in documents:
        if to_text(document.get("extension")).lower() != "pdf":
            continue
        reference = to_text(document.get("referenceadministrative"))
        url = to_text(document.get("doc_url"))
        if not reference or not url:
            continue
        if document.get("type_doc") == "Document d'information":
            links = information_links
        else:
            links = other_links
        if reference not in links:
            links[reference] = []
        links[reference].append(url)

    pdf_links = {}
    for links in [information_links, other_links]:
        for reference in links:
            if reference not in pdf_links:
                pdf_links[reference] = []
            pdf_links[reference].extend(links[reference])
    return pdf_links


def to_text(value):
    """Turn any value of the dataset (text, number, list, None) into a simple string."""
    if value is None:
        return ""
    if isinstance(value, list):
        parts = []
        for item in value:
            parts.append(str(item))
        return ", ".join(parts)
    return str(value)


def first_filled(row, columns):
    """Return the value of the first of these columns that is not empty ('' if none)."""
    for column_name in columns:
        value = to_text(row.get(column_name))
        if value:
            return value
    return ""


def row_to_full_text(row):
    """Gather the useful columns of the aid into one text ('column: value' per line), for the NLP step.
    Technical columns are skipped, and so is the HTML version of a column that also exists
    as plain text (e.g. 'objectif' is skipped because 'objectif_txt' exists)."""
    lines = []
    for column_name in row:
        if column_name in TECHNICAL_COLUMNS:
            continue
        if column_name + "_txt" in row:
            continue
        text = html_tools.html_to_text(to_text(row[column_name]))
        if text:
            lines.append(column_name + ": " + text)
    return "\n".join(lines)


def compute_status(opening_date, deadline):
    """Compute the status of an aid from its dates: 'à venir', 'ouvert', 'clos' or 'sans date'.
    The dates are 'YYYY-MM-DD' strings, which can be compared like dates."""
    today = today_iso()
    if deadline and deadline < today:
        return "clos"
    if opening_date and opening_date > today:
        return "à venir"
    if opening_date or deadline:
        return "ouvert"
    return "sans date"


def row_to_record(row):
    """Turn one aid of the dataset into a row with the common format."""
    record = new_record(SOURCE)
    record["funder"] = "Région Île-de-France"
    record["source_id"] = to_text(row.get(ID_COLUMN))
    record["title"] = html_tools.html_to_text(first_filled(row, TITLE_COLUMNS))
    record["summary"] = html_tools.html_to_text(first_filled(row, SUMMARY_COLUMNS))

    opening = to_text(row.get(OPENING_COLUMN))
    deadline = to_text(row.get(DEADLINE_COLUMN))
    next_campaign = to_text(row.get(NEXT_CAMPAIGN_COLUMN))
    record["opening_date"] = to_iso_date(opening)
    record["deadline"] = to_iso_date(deadline)
    record["status"] = compute_status(record["opening_date"], record["deadline"])

    date_lines = []
    if opening:
        date_lines.append("ouverture: " + record["opening_date"])
    if deadline:
        date_lines.append("clôture: " + record["deadline"])
    if next_campaign:
        date_lines.append("prochaine campagne: " + to_iso_date(next_campaign))
    record["dates_text"] = join_list(date_lines)

    record["page_text"] = row_to_full_text(row)
    record["url"] = to_text(row.get(URL_COLUMN)) or WEBSITE_URL
    return record


def scrape(max_items=None, with_pdfs=True):
    """Collect the aids and calls of the Région Île-de-France from the open data files."""
    rows = download_rows()
    log.info("Région IDF: %d aids in the dataset", len(rows))
    if max_items:
        rows = rows[:max_items]

    pdf_links = download_pdf_links()
    log.info("Région IDF: PDF documents found for %d aids", len(pdf_links))

    records = []
    for row in rows:
        record = row_to_record(row)
        pdf_urls = pdf_links.get(record["source_id"], [])
        record["pdf_urls"] = join_list(pdf_urls)
        if with_pdfs and pdf_urls:
            txt_files, methods = pdf_tools.process_pdfs(pdf_urls, SOURCE)
            record["pdf_text_files"] = join_list(txt_files)
            record["pdf_methods"] = join_list(methods)
        records.append(record)
    return records


def print_columns():
    """Print the column names of the dataset with the first value, to update the *_COLUMN names above."""
    rows = download_rows()
    if not rows:
        print("Could not download the dataset")
        return
    for column_name in rows[0]:
        print(column_name, "=", to_text(rows[0][column_name])[:80])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if "--columns" in sys.argv:
        print_columns()
    else:
        for row in scrape(max_items=5, with_pdfs=False):
            print(row["source_id"], "|", row["status"], "|", row["deadline"], "|", row["title"][:70])
