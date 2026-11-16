"""
NEXT STEP (not plugged in yet): extract structured fields from the raw texts.

The scrapers only collect raw text (web page + PDF texts). Many important fields
(deadline, eligibility, budget, funded costs) are written differently on every site,
often only inside the PDF. Writing one regex per site does not scale, hence this module.

Planned approach: extractive Question Answering with an open-source BERT-like model.
  1. load_call_text() gathers all the text of one call (page + PDFs).
  2. The text is cut into chunks of ~350 words (these models read ~512 tokens at most).
  3. For each field, we ask a question on every chunk, e.g.
     "Quelle est la date limite de dépôt ?", and keep the answer with the best score.
  4. The answer + its score are stored; low scores go to human validation.

Candidate models (Hugging Face, open source, run on a laptop CPU):
  - etalab-ia/camembert-base-squadFR-fquad-piaf   (French)
  - deepset/xlm-roberta-base-squad2               (multilingual: FR + EN for Horizon)

Minimal usage once `transformers` and `torch` are installed:
    from transformers import pipeline
    qa = pipeline("question-answering", model="etalab-ia/camembert-base-squadFR-fquad-piaf")
    qa(question=QUESTIONS["deadline"], context=chunk)   # -> {"answer": ..., "score": ...}
"""
import os

# One question per field we want to extract
QUESTIONS = {
    "deadline": "Quelle est la date limite de dépôt ?",
    "eligibility": "Qui peut déposer un projet ?",
    "budget": "Quel est le budget ou le montant de l'aide ?",
    "funded_costs": "Quelles dépenses sont financées ?",
}


def load_call_text(record):
    """Gather all the raw text of one call: the web page text + the text of each of its PDFs."""
    texts = [record.get("page_text", "")]
    for txt_path in record.get("pdf_text_files", "").split(" | "):
        if txt_path and os.path.exists(txt_path):
            with open(txt_path, encoding="utf-8") as file:
                texts.append(file.read())
    return "\n\n".join(texts)


def split_into_chunks(text, words_per_chunk=350):
    """Cut a long text into pieces small enough for a BERT-like model."""
    words = text.split()
    chunks = []
    for start in range(0, len(words), words_per_chunk):
        chunks.append(" ".join(words[start:start + words_per_chunk]))
    return chunks


def extract_fields(record):
    """Return {field: value} for one call. For now every value is empty: the QA model will fill them."""
    fields = {}
    for field_name in QUESTIONS:
        fields[field_name] = ""
    return fields
