"""
Entry point of the prototype: runs the scrapers and saves everything in one CSV.

Examples:
    python main.py                               # all sources, everything
    python main.py --max-items 5                 # quick demo: 5 calls per source
    python main.py --sources anr horizon         # only some sources
    python main.py --no-pdf                      # skip PDF download (much faster)
"""
import os
import argparse
import logging
from datetime import datetime

import config
from scrapers import SCRAPERS
from utils.storage import save_to_csv
from utils.report import print_fill_report

log = logging.getLogger("main")


def setup_logging(run_id):
    """Show the logs in the terminal and also save them in logs/run_<run_id>.log."""
    os.makedirs(config.LOG_DIR, exist_ok=True)
    log_file = os.path.join(config.LOG_DIR, "run_" + run_id + ".log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")],
    )
    # trafilatura and pdfminer are very talkative, we only keep their warnings
    logging.getLogger("trafilatura").setLevel(logging.WARNING)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)


def parse_arguments():
    """Read the command line options: which sources, how many calls, with or without PDFs."""
    parser = argparse.ArgumentParser(description="Collect calls for proposals (prototype PI2 ESILV).")
    parser.add_argument("--sources", nargs="+", choices=list(SCRAPERS), default=list(SCRAPERS),
                        help="sources to scrape (default: all)")
    parser.add_argument("--max-items", type=int, default=None,
                        help="max number of calls per source (useful for tests)")
    parser.add_argument("--no-pdf", action="store_true",
                        help="do not download nor read the PDFs")
    return parser.parse_args()


def main():
    """Run each selected scraper, gather all the rows and save them in one CSV file."""
    # Date and time down to the second: two runs never write the same CSV or log file
    run_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    setup_logging(run_id)
    args = parse_arguments()

    all_records = []
    for name in args.sources:
        log.info("===== %s =====", name)
        try:
            records = SCRAPERS[name](max_items=args.max_items, with_pdfs=not args.no_pdf)
        except Exception:
            # One broken source must not stop the others
            log.exception("The %s scraper crashed, moving on to the next source", name)
            records = []
        log.info("%s: %d calls collected", name, len(records))
        all_records.extend(records)

    csv_path = os.path.join(config.OUTPUT_DIR, "aap_" + run_id + ".csv")
    save_to_csv(all_records, csv_path)
    print_fill_report(all_records)
    print("CSV file:", csv_path)


if __name__ == "__main__":
    main()
