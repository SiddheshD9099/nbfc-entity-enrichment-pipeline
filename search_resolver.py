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
    """Aggregate and deduplicate results from available search engines."""
    all_results = []
    seen_urls = set()

    for name, fn in ENGINES:
        if name in DEAD_ENGINES:
            continue

        res = _call_engine_with_retry(name, fn, query)

        if res is None:
            DEAD_ENGINES.add(name)
            log_search_engine_skip(
                name,
                "failed after retries; skipping for rest of run",
            )
            continue

        if not res:
            print(f"    {name}: 0 results")
            continue

        print(f"    search ok via {name} ({len(res)} results)")
        log_search_engine_ok(name, query, len(res))

        for url in res:
            if not isinstance(url, str):
                continue

            url = url.strip()

            if not url.startswith(("http://", "https://")):
                continue

            normalized = url.rstrip("/").lower()

            if normalized in seen_urls:
                continue

            seen_urls.add(normalized)
            all_results.append(url)

    if all_results:
        print(f"    aggregated unique results: {len(all_results)}")

    return all_results

def clean_origin(url):
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"

def normalize_company_name(name: str) -> str:
    """Convert a company name into a simple comparison string."""
    name = name.lower()
    name = re.sub(
        r"\b(limited|ltd|private|pvt|inc|incorporated|corporation|corp|company|co)\b",
        " ",
        name,
    )
    return re.sub(r"[^a-z0-9]", "", name)


def domain_matches_company(company: str, url: str) -> bool:
    """Check whether a domain matches a company name or verified alias."""
    host = (urlparse(url).hostname or "").lower()

    if host.startswith("www."):
        host = host[4:]

    verified_domains = {
        "bajaj finance limited": {"bajajfinserv.in"},
        "manappuram finance limited": {"manappuram.com"},
        "shriram finance limited": {"shriramfinance.in"},
        "cholamandalam investment and finance company limited": {
            "cholamandalam.com",
        },
        "mahindra & mahindra financial services limited": {
            "mahindrafinance.com",
        },
        "l&t finance limited": {"ltfinance.com"},
        "poonawalla fincorp limited": {"poonawallafincorp.com"},
        "iifl finance limited": {"iifl.com"},
        "muthoot finance limited": {"muthootfinance.com"},
        "tata capital limited": {"tatacapital.com"},
        "sundaram finance limited": {"sundaramfinance.in"},
        "bajaj housing finance limited": {"bajajhousingfinance.in"},
        "aditya birla finance limited": {"adityabirlacapital.com"},
        "hero fincorp limited": {"herofincorp.com"},
        "tvs credit services limited": {"tvscredit.com"},
        "u gro capital limited": {"ugrocapital.com"},
        "five-star business finance limited": {"fivestargroup.in"},
        "creditaccess grameen limited": {"creditaccessgrameen.in"},
        "aavas financiers limited": {"aavas.in"},
        "aptus value housing finance india limited": {"aptusindia.com"},
        "home first finance company india limited": {"homefirstindia.com"},
        "pnb housing finance limited": {"pnbhousing.com"},
        "can fin homes limited": {"canfinhomes.com"},
        "lic housing finance limited": {"lichousing.com"},
        "india shelter finance corporation limited": {"indiashelter.in"},
        "fedbank financial services limited": {"fedfina.com"},
        "mas financial services limited": {"mas.co.in"},
        "arman financial services limited": {"armanindia.com"},
        "capri global capital limited": {"capriglobal.in"},
        "nuvama wealth management limited": {"nuvama.com"},
        "jm financial limited": {"jmfinancialservices.in"},
        "motilal oswal financial services limited": {"motilaloswal.com"},
        "bls e-services limited": {"blseservices.com"},
        "paisalo digital limited": {"paisalo.in"},
        "northern arc capital limited": {"northernarc.com"},
        "indostar capital finance limited": {"indostarcapital.com"},
        "reliance commercial finance limited": {"reliancecommercialfinance.com"},
        "lendingkart finance limited": {"lendingkart.com"},
        "kinara capital private limited": {"kinaracapital.com"},
        "aye finance private limited": {"ayefin.com"},
        "dmi finance private limited": {"dmifinance.in"},
        "vivriti capital limited": {"vivriticapital.com"},
        "avanse financial services limited": {"avanse.com"},
        "incred financial services limited": {"incred.com"},
        "tata motors finance limited": {"tatamotorsfinance.com"},
        "navi finserv limited": {"navi.com"},
        "kogta financial india limited": {"kogta.com"},
        "clix capital services private limited": {"clix.capital"},
        "muthoot microfin limited": {"muthootmicrofin.com"},
        "satin creditcare network limited": {"satincreditcare.com"},
    }

    company_key = company.lower().strip()

    if host in verified_domains.get(company_key, set()):
        return True

    domain_name = host.split(".")[0]
    company_name = normalize_company_name(company)
    domain_name = normalize_company_name(domain_name)

    if not company_name or not domain_name:
        return False

    if company_name == domain_name:
        return True

    return (
        len(domain_name) >= 5
        and len(company_name) >= 5
        and (
            domain_name in company_name
            or company_name in domain_name
        )
    )



def website_title_matches_company(company: str, url: str) -> bool:
    """Check whether the website title provides evidence of a company match."""
    html = fetch_html(url)

    if not html:
        return False

    soup = BeautifulSoup(html, "html.parser")

    if soup.title and soup.title.string:
        title = soup.title.string.strip().lower()
    else:
        return False

    normalized_company = normalize_company_name(company)
    normalized_title = normalize_company_name(title)

    return (
        bool(normalized_company)
        and len(normalized_company) >= 5
        and normalized_company in normalized_title
    )


def find_website(company):
    core = re.sub(
        r"\b(co\.?,?\s*ltd\.?|inc\.?|corporation|corp\.?|ltd\.?)\b",
        "",
        company,
        flags=re.I,
    ).strip()

    queries = (
        f"{company} official website",
        f"{core} official site corporate",
    )

    candidates = []
    seen = set()

    for query in queries:
        for url in web_search(query):
            if not url.startswith(("http://", "https://")):
                continue

            host = (urlparse(url).hostname or "").lower()

            if not host:
                continue

            # Reject known directories, social media and other unwanted sites.
            if any(junk in host for junk in JUNK_DOMAINS):
                continue

            # Avoid processing the same website repeatedly.
            origin = clean_origin(url)

            if origin in seen:
                continue

            seen.add(origin)
            candidates.append(origin)

        polite()

    # First preference: the domain resembles the company name.
    for url in candidates:
        if domain_matches_company(company, url):
            print(f"    website candidate matched company domain: {url}")
            return url

    # Second preference: the website title contains the company name.
    for url in candidates:
        if website_title_matches_company(company, url):
            print(f"    website candidate matched page title: {url}")
            return url

    print(f"    no sufficiently verified website found for: {company}")
    return None


def find_linkedin(company):
    for url in web_search(f"{company} linkedin company"):
        m = re.search(r"https?://[a-z]{2,3}\.linkedin\.com/company/[^/?#]+|https?://(?:www\.)?linkedin\.com/company/[^/?#]+", url)
        if m:
            return m.group(0)
    return None


def polite():
    time.sleep(random.uniform(1.5, 3.0))
