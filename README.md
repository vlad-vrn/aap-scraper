# Prototype de collecte d'appels à projets (PI2 n°158)

## Installation
```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```
Pour l'OCR des PDF scannés (indispensable pour les textes France 2030 de l'ANR), installer aussi
Tesseract (langues fra + eng) et Poppler, par exemple sous Arch :
`pacman -S tesseract tesseract-data-fra tesseract-data-eng poppler`.

Avant le premier lancement : mettre un vrai email de contact dans `config.py` (USER_AGENT).

## Documentation
`docs/documentation_code.tex` (et le PDF compilé) explique le code problème par problème :
le problème, la solution retenue, puis l'implémentation.
Compilation : `cd docs && pdflatex documentation_code.tex && pdflatex documentation_code.tex`.

## Lancer
```bash
python main.py --max-items 5 --no-pdf     # test rapide
python main.py --max-items 5              # avec les PDF
python main.py                            # tout
python -m scrapers.anr                    # tester une seule source
python -m scrapers.region_idf --columns   # voir les colonnes du jeu de données Région
```
Sorties : `data/output/aap_<date>.csv`, PDF et textes extraits dans `data/pdfs/<source>/`, logs dans `logs/`.

## Structure
```
main.py                   lance les scrapers, écrit le CSV, affiche le taux de remplissage
config.py                 paramètres (délai entre requêtes, dossiers, OCR)
scrapers/
  anr.py                  HTML : anr.fr/fr/appels + pages de chaque appel + PDF
  bpifrance.py            HTML : bpifrance.fr/nos-appels-a-projets-concours + PDF
  horizon.py              API Funding & Tenders (SEDIA)
  region_idf.py           open data data.iledefrance.fr (JSON) + PDF des aides
  common.py               lecture d'une page d'appel (texte, lignes de dates, PDF)
utils/
  http_client.py          requêtes, délai, robots.txt, gestion d'erreurs
  html_tools.py           texte principal d'une page, liens PDF, lignes de dates
  pdf_tools.py            téléchargement PDF, texte (pdfplumber) puis OCR si scanné
  storage.py              format commun d'une ligne (COLUMNS) + CSV (+ PostgreSQL à venir)
  report.py               tableau de taux de remplissage par source
extraction/
  field_extractor.py      étape suivante : extraction des champs par modèle QA (BERT)
```

## Ajouter une source
Créer `scrapers/<nom>.py` avec une fonction `scrape(max_items=None, with_pdfs=True)` qui renvoie
une liste de lignes créées avec `new_record()`, puis l'ajouter dans `scrapers/__init__.py`.
