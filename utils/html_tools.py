"""
Small helpers to read HTML pages.
The idea: avoid depending on the CSS classes of each website (they change often),
and rely instead on things that are stable: <h1>, links ending in .pdf, keywords...
"""
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import trafilatura


def parse_html(html):
    """Turn raw HTML into a BeautifulSoup object we can search in."""
    return BeautifulSoup(html, "html.parser")


def html_to_text(html):
    """Remove the HTML tags from a string and return plain text."""
    if not html:
        return ""
    if "<" not in html:
        return html.strip()  # no tag inside: nothing to remove
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def main_text(html):
    """Extract the main readable text of a page (without menus, footer, cookie banner).
    trafilatura does this for any website, so we don't write one extractor per site."""
    text = trafilatura.extract(html, include_tables=True, favor_recall=True)
    if text:
        return text
    # Fallback if trafilatura finds nothing: all the visible text of the page
    return visible_text(parse_html(html))


def visible_text(soup):
    """Return all the visible text of a page, one block per line (scripts and styles removed)."""
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def page_title(soup):
    """Return the title of a page: the <h1> if there is one, otherwise the <title> tag."""
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(" ", strip=True)
    if soup.title:
        return soup.title.get_text(" ", strip=True)
    return ""


def find_pdf_links(soup, page_url):
    """Return the full URLs of all the PDF files linked from a page, without duplicates."""
    pdf_urls = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" not in href.lower():
            continue
        full_url = urljoin(page_url, href)
        if full_url not in pdf_urls:
            pdf_urls.append(full_url)
    return pdf_urls


def short_lines_with_keywords(text, keywords, max_length=200):
    """Keep the short lines of a text that contain one of the keywords (case-insensitive).
    Used to grab lines like 'Limite de dépôt : 06/04/2027 à 15:00' wherever they are on the page.
    A label alone ('Fermeture :') is joined with the next line, which usually holds its value."""
    lines = text.splitlines()
    found = []
    for index in range(len(lines)):
        line = lines[index].strip()
        if not line or len(line) > max_length:
            continue
        if line.endswith(":") and index + 1 < len(lines):
            line = line + " " + lines[index + 1].strip()
        lower_line = line.lower()
        for keyword in keywords:
            if keyword in lower_line:
                if line not in found:
                    found.append(line)
                break
    return found
