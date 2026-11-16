"""
A small report printed at the end of each run.
It shows, per source, the percentage of rows where each field is filled.
=> It makes visible which information each website gives (or not),
   i.e. what the future NLP / BERT step will have to find in the texts.
"""

REPORT_COLUMNS = ["title", "opening_date", "deadline", "dates_text", "summary",
                  "page_text", "pdf_urls", "pdf_text_files"]


def list_sources(records):
    """Return the names of the sources present in the rows, in order of appearance."""
    sources = []
    for record in records:
        if record["source"] not in sources:
            sources.append(record["source"])
    return sources


def fill_rate(rows, column):
    """Return the percentage of rows where the column is not empty."""
    if not rows:
        return 0
    filled = 0
    for row in rows:
        if row[column]:
            filled += 1
    return round(100 * filled / len(rows))


def print_fill_report(records):
    """Print a table: one line per source, one column per field, values = % of rows filled."""
    header = "source".ljust(12) + "rows".rjust(6)
    for column in REPORT_COLUMNS:
        header += column[:13].rjust(15)
    print()
    print(header)
    print("-" * len(header))

    for source in list_sources(records):
        rows = []
        for record in records:
            if record["source"] == source:
                rows.append(record)
        line = source.ljust(12) + str(len(rows)).rjust(6)
        for column in REPORT_COLUMNS:
            line += (str(fill_rate(rows, column)) + "%").rjust(15)
        print(line)
    print()
