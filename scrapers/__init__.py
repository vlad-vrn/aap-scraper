"""
List of the available scrapers.

Every scraper module exposes the same function:
    scrape(max_items=None, with_pdfs=True) -> list of rows (dicts with the columns of utils/storage.py)

To add a new source: create scrapers/<name>.py with a scrape() function,
then add one line in the SCRAPERS dict below.
"""
from scrapers import anr, bpifrance, horizon, region_idf

SCRAPERS = {
    "anr": anr.scrape,
    "bpifrance": bpifrance.scrape,
    "horizon": horizon.scrape,
    "region_idf": region_idf.scrape,
}
