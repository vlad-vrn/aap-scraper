"""
All the network requests of the project go through this file.
It takes care of three things so the scrapers don't have to:
  - waiting between two requests (we don't want to overload the sites),
  - checking robots.txt before reading an HTML page,
  - catching network errors (a failed request returns None instead of crashing).
"""
import time
import logging
from urllib import robotparser
from urllib.parse import urlparse

import requests

import config

log = logging.getLogger(__name__)

# One shared session = faster (connections are reused) and same User-Agent everywhere
session = requests.Session()
session.headers.update({"User-Agent": config.USER_AGENT})

robots_cache = {}       # site -> parsed robots.txt (downloaded only once per site)
last_request_time = 0   # used to space out the requests


def load_robots(site):
    """Download and parse the robots.txt of a website. Returns None if the site has none."""
    try:
        response = session.get(site + "/robots.txt", timeout=config.REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as error:
        log.warning("Could not read robots.txt of %s (%s), continuing", site, error)
        return None
    if response.status_code != 200:
        return None
    parser = robotparser.RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser


def is_allowed_by_robots(url):
    """Check the site's robots.txt to know if our bot is allowed to read this URL."""
    parts = urlparse(url)
    site = parts.scheme + "://" + parts.netloc
    if site not in robots_cache:
        robots_cache[site] = load_robots(site)
    parser = robots_cache[site]
    if parser is None:
        return True
    return parser.can_fetch(config.USER_AGENT, url)


def wait_politely():
    """Sleep a little so that two requests are never closer than REQUEST_DELAY_SECONDS."""
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < config.REQUEST_DELAY_SECONDS:
        time.sleep(config.REQUEST_DELAY_SECONDS - elapsed)
    last_request_time = time.time()


def check_response(response, url):
    """Return the response if it is a success (HTTP 200), otherwise log the problem and return None."""
    if response.status_code == 200:
        return response
    if response.status_code == 403:
        log.warning("HTTP 403 (access refused, maybe an anti-bot protection) for %s", url)
    else:
        log.warning("HTTP %s for %s", response.status_code, url)
    return None


def get(url, params=None, check_robots=True):
    """Download a URL with a GET request. Returns the response, or None if anything went wrong.
    check_robots=False is only for official APIs / open data files, which are made to be downloaded."""
    if check_robots and not is_allowed_by_robots(url):
        log.warning("robots.txt forbids this URL, skipped: %s", url)
        return None
    wait_politely()
    try:
        response = session.get(url, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as error:
        log.warning("Request failed for %s: %s", url, error)
        return None
    return check_response(response, url)


def post(url, params=None, files=None):
    """Send a POST request to an API (the EU search API needs POST). Returns the response or None."""
    wait_politely()
    try:
        response = session.post(url, params=params, files=files, timeout=config.REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as error:
        log.warning("Request failed for %s: %s", url, error)
        return None
    return check_response(response, url)
