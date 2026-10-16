import os
import re
import time
import base64
import random
from urllib.parse import urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

from logger import (
    log_search_engine_failure,
    log_search_engine_ok,
    log_search_engine_skip,
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 15
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

API_KEY = os.environ.get("GOOGLE_API_KEY")
CX = os.environ.get("GOOGLE_CX")

JUNK_DOMAINS = (
    "linkedin.", "facebook.", "twitter.", "x.com", "instagram.", "youtube.", "wikipedia.",
    "bloomberg.", "zoominfo.", "dnb.com", "crunchbase.", "rocketreach.", "leadiq.",
    "apollo.io", "glassdoor.", "indeed.", "yelp.", "mapquest.", "yellowpages.",
    "buzzfile.", "opencorporates.", "cbinsights.", "pitchbook.", "reuters.", "forbes.",
    "amazon.", "google.", "bing.com", "duckduckgo.", "yahoo.", "baidu.", "tripadvisor.",
    "companiesmarketcap.", "globaldata.", "signalhire.", "seamless.", "lusha.",
    "kompass.", "alibaba.", "ebay.", "wiza.", "contactout.", "adapt.io", "craft.co",
    "growjo.", "comparably.", "owler.", "clay.com", "datanyze.", "tracxn.", "marketscreener.",
    "kabutan.", "nikkei.", "prtimes.", "mynavi.", "rikunabi.", "en-japan.", "wantedly.",
)

DEAD_ENGINES = set()
SEARCH_RETRIES = 2
RETRY_BASE_DELAY_SEC = 1.5


def get(url, **kw):
    """GET -> Response or None. Never raises."""
    try:
        r = SESSION.get(url, timeout=TIMEOUT, **kw)
        return r
    except requests.exceptions.RequestException as e:
        print(f"    ! request failed {url[:70]}: {type(e).__name__}")
        return None


def fetch_html(url):
    r = get(url)
    if r is not None and r.status_code == 200 and "text" in r.headers.get("Content-Type", "text"):
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding  # fixes Japanese pages
        return r.text
    return None


def decode_bing(href):
    if "bing.com/ck/a" in href:
        u = parse_qs(urlparse(href).query).get("u", [""])[0]
        if u.startswith("a1"):
            b = u[2:]
            b += "=" * (-len(b) % 4)
            try:
                return base64.urlsafe_b64decode(b).decode("utf-8")
            except Exception:
                return href
    return href


def search_google_api(q):
    if not (API_KEY and CX):
        return None
    r = get("https://www.googleapis.com/customsearch/v1",
            params={"key": API_KEY, "cx": CX, "q": q, "num": 8})
    if r is None:
        return None
    try:
        data = r.json()
    except ValueError:
        return []
    if "error" in data:
        print(f"    ! google api: {data['error'].get('message')}")
        return None
    return [i["link"] for i in data.get("items", [])]


def search_bing(q):
    r = get("https://www.bing.com/search", params={"q": q, "setlang": "en", "cc": "us"})
    if r is None:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    return [decode_bing(a["href"]) for a in soup.select("li.b_algo h2 a[href]")]


def search_ddg(q):
    try:
        r = SESSION.post("https://html.duckduckgo.com/html/", data={"q": q}, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(f"    ! request failed duckduckgo: {type(e).__name__}")
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.select("a.result__a[href]"):
        href = a["href"]
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
        elif href.startswith("//"):
            href = "https:" + href
        out.append(href)
    return out


def search_googlelib(q):
    try:
        from googlesearch import search  # optional dependency
        return list(search(q, num_results=8))
    except ImportError:
        return None
    except Exception:
        return None


ENGINES = [("google_api", search_google_api), ("bing", search_bing),
           ("duckduckgo", search_ddg), ("googlesearch-lib", search_googlelib)]


def _call_engine_with_retry(name, fn, query):
    """Up to 1 + SEARCH_RETRIES attempts before treating engine as failed (None)."""
    attempts = 1 + SEARCH_RETRIES
    for attempt in range(1, attempts + 1):
        res = fn(query)
        if res is not None:
            return res
        reason = "unreachable or not configured"
        log_search_engine_failure(name, query, reason, attempt=attempt)
        if attempt < attempts:
            delay = RETRY_BASE_DELAY_SEC * (2 ** (attempt - 1))
            time.sleep(delay)
    return None


def web_search(query):
    for name, fn in ENGINES:
        if name in DEAD_ENGINES:
            continue
        res = _call_engine_with_retry(name, fn, query)
        if res is None:
            DEAD_ENGINES.add(name)  # unreachable/not configured -> don't retry every row
            log_search_engine_skip(name, "failed after retries; skipping for rest of run")
            continue
        if res:
            print(f"    search ok via {name} ({len(res)} results)")
            log_search_engine_ok(name, query, len(res))
            return res
        print(f"    {name}: 0 results, trying next engine")
    return []


def clean_origin(url):
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def find_website(company):
    core = re.sub(r"\b(co\.?,?\s*ltd\.?|inc\.?|corporation|corp\.?|ltd\.?)\b", "", company, flags=re.I).strip()
    for q in (f"{company} official website", f"{core} official site corporate"):
        for url in web_search(q):
            if url.startswith("http") and not any(j in url.lower() for j in JUNK_DOMAINS):
                return clean_origin(url)
        polite()
    return None


def find_linkedin(company):
    for url in web_search(f"{company} linkedin company"):
        m = re.search(r"https?://[a-z]{2,3}\.linkedin\.com/company/[^/?#]+|https?://(?:www\.)?linkedin\.com/company/[^/?#]+", url)
        if m:
            return m.group(0)
    return None


def polite():
    time.sleep(random.uniform(1.5, 3.0))
