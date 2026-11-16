# Global settings of the scraper.
# Change the values here rather than inside the code.

# Name sent to the websites. Put a real contact email: it is good practice
# and site admins can reach us instead of blocking us.
USER_AGENT = "ESILV-PI2-AAP-Scraper/0.1 (projet etudiant ESILV; contact: prenom.nom@edu.devinci.fr)"

# Politeness: minimum pause between two requests, and max waiting time per request
REQUEST_DELAY_SECONDS = 1.5
REQUEST_TIMEOUT_SECONDS = 30

# Where files are written
OUTPUT_DIR = "data/output"   # CSV files
PDF_DIR = "data/pdfs"        # downloaded PDFs + their extracted text (.txt)
LOG_DIR = "logs"             # one log file per run

# PDFs: how many PDFs to download per call (the first ones are usually the call text)
MAX_PDFS_PER_CALL = 3

# OCR is only used when a PDF has almost no text layer (= scanned document)
OCR_MIN_CHARS_PER_PAGE = 100
OCR_LANGUAGES = "fra+eng"
