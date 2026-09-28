import sys
import os
import re
import json
import time
import base64
import random
from urllib.parse import urlparse, parse_qs, unquote, urljoin

import requests
from bs4 import BeautifulSoup
import openpyxl

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

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BAD_EMAIL_END = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")
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

# ---------------------------------------------------------------------------
# SEED: verified by manual web research. Used ONLY to fill cells live lookup missed.
# ---------------------------------------------------------------------------
SEED = {
    "mizuno usa inc.": dict(
        website="https://usa.mizuno.com",
        linkedin="https://www.linkedin.com/company/mizuno-usa",
        address="3155 Northwoods Parkway NW, Peachtree Corners, GA 30071, USA",
        employees="~465 (US entity) | parent Mizuno Corp much larger"),
    "yokogawa digital corporation": dict(
        website="https://www.yokogawadigital.com",
        linkedin="https://jp.linkedin.com/company/yokogawadigital",
        address="2-9-32 Naka-cho, Musashino-shi, Tokyo, Japan",
        employees="Not disclosed (subsidiary est. 2022) | Yokogawa Group 17,000+"),
    "benesse corporation": dict(
        website="https://www.benesse.co.jp",
        linkedin="https://www.linkedin.com/company/benesse-corporation",
        address="Kita-ku, Okayama City, Okayama Prefecture, Japan",
        employees="1,001-5,000 (LinkedIn)"),
    "omron healthcare co. ltd.": dict(
        website="https://healthcare.omron.com",
        linkedin="https://www.linkedin.com/company/omronhealthcare",
        address="Kunotsubo-53, Teradocho, Muko, Kyoto 617-0002, Japan",
        employees="~10,000 (global group)"),
    "sekisui jushi corporation": dict(
        website="https://www.sekisuijushi.co.jp/en/",
        linkedin="",
        address="2-4-4 Nishitemma, Kita-ku, Osaka 530-0047, Japan",
        employees="Not separately disclosed | Sekisui Chemical Group ~26,000"),
    "nippon paint industrial coatings co. ltd.": dict(
        website="https://www.nipponpaint-holdings.com/en/",
        linkedin="https://www.linkedin.com/company/nippon-paint-holdings-co-ltd",
        address="Oyodo Kita, Kita-ku, Osaka 531-8511, Japan (Holdings HQ)",
        employees="Not separately disclosed | Nippon Paint Group ~33,000"),
    "jgc japan corporation": dict(
        website="https://www.jgc.com/en/",
        linkedin="https://www.linkedin.com/company/jgc",
        address="2-3-1 Minato Mirai, Nishi-ku, Yokohama, Kanagawa 220-6001, Japan",
        employees="JGC Holdings 7,500+ consolidated"),
    "ihi infrastructure systems co. ltd.": dict(
        website="https://www.ihi.co.jp/iis/en/",
        linkedin="",
        address="3 Ohamanishi-machi, Sakai-ku, Sakai-shi, Osaka 590-0977, Japan",
        employees="Not separately disclosed | IHI Corp ~26,600 (renamed IHI Infra-square - verify)"),
    "sumitomo heavy industries material handling systems co. ltd.": dict(
        website="https://shi-mh.co.jp/english/",
        linkedin="",
        address="Sumitomo Fudosan Osaki Garden Tower, 1-1-1 Nishi-Shinagawa, Shinagawa-ku, Tokyo 141-0033, Japan",
        employees="Not separately disclosed | SHI Group ~17,900"),
    "nisshinbo mechatronics inc.": dict(
        website="https://www.nisshinbo-mechatronics.co.jp/english/",
        linkedin="",
        address="2-31-11 Ningyo-cho, Nihonbashi, Chuo-ku, Tokyo 103-8650, Japan",
        employees="~1,000-4,999 (estimate)"),
}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
DEAD_ENGINES = set()


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


# ---------------------------------------------------------------------------
# Search engines (each returns list of URLs, or None if engine unreachable)
# ---------------------------------------------------------------------------
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


def web_search(query):
    for name, fn in ENGINES:
        if name in DEAD_ENGINES:
            continue
        res = fn(query)
        if res is None:
            DEAD_ENGINES.add(name)  # unreachable/not configured -> don't retry every row
            continue
        if res:
            print(f"    search ok via {name} ({len(res)} results)")
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


# ---------------------------------------------------------------------------
# Scraping the company's own site
# ---------------------------------------------------------------------------
LINK_HINTS = ("contact", "about", "company", "corporate", "profile", "access", "overview",
              "inquiry", "outline", "location", "会社", "企業", "概要", "お問い合わせ", "アクセス", "拠点")


def candidate_pages(website, home_html):
    """Homepage + links found on it that look like contact/about pages (max 5)."""
    pages = [website]
    if home_html:
        soup = BeautifulSoup(home_html, "html.parser")
        seen = {website.rstrip("/")}
        for a in soup.find_all("a", href=True):
            label = (a.get_text(" ", strip=True) + " " + a["href"]).lower()
            if any(h in label for h in LINK_HINTS):
                full = urljoin(website + "/", a["href"]).split("#")[0]
                if full.startswith(("http://", "https://")) and urlparse(full).netloc == urlparse(website).netloc:
                    if full.rstrip("/") not in seen:
                        seen.add(full.rstrip("/"))
                        pages.append(full)
            if len(pages) >= 6:
                break
    if len(pages) == 1:  # nothing discovered -> blind guesses
        pages += [website.rstrip("/") + p for p in ("/contact", "/about", "/company", "/en/company")]
    return pages


def address_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    # 1) JSON-LD PostalAddress
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except (ValueError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                addr = node.get("address")
                if isinstance(addr, dict):
                    parts = [addr.get(k) for k in ("streetAddress", "addressLocality", "addressRegion",
                                                    "postalCode", "addressCountry")]
                    parts = [p if isinstance(p, str) else (p or {}).get("name", "") for p in parts]
                    txt = ", ".join(p for p in parts if p)
                    if len(txt) > 8:
                        return txt
                stack.extend(v for v in node.values() if isinstance(v, (dict, list)))
            elif isinstance(node, list):
                stack.extend(node)
    # 2) <address> tag
    tag = soup.find("address")
    if tag:
        txt = re.sub(r"\s+", " ", tag.get_text(" ", strip=True))
        if len(txt) > 10:
            return txt[:200]
    text = soup.get_text("\n", strip=True)
    # 3) Japanese postal block
    m = re.search(r"〒\s?\d{3}-?\d{4}[ \u3000]*[^\n]{4,90}", text)
    if m:
        return m.group(0).strip()
    # 4) English label
    m = re.search(r"(?:Head\s*Office|Headquarters|Address|Location|所在地|本社)\s*[:：]?\s*\n?\s*([^\n]{12,140})", text, re.I)
    if m:
        return m.group(1).strip()
    return None


def employees_from_html(html):
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    m = re.search(r"(?:number of employees|total employees|employees|従業員数|社員数)\s*[:：]?\s*(?:approx\.?|about|約)?\s*([\d,]{2,8})\s*(?:people|persons|名|人)?", text, re.I)
    if m and re.search(r"\d", m.group(1)):
        return m.group(1)
    return None


def contacts_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    emails, phones = set(), set()
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if h.lower().startswith("mailto:"):
            emails.add(h[7:].split("?")[0].strip())
        elif h.lower().startswith("tel:"):
            phones.add(h[4:].strip())
    emails.update(EMAIL_RE.findall(soup.get_text(" ")))
    emails = {e for e in emails if not e.lower().endswith(BAD_EMAIL_END) and "@" in e}
    return emails, phones


def scrape_site(website):
    """Returns dict(address, employees, emails, phones) from the company's own pages."""
    out = dict(address=None, employees=None, contacts=None)
    home = fetch_html(website)
    emails, phones = set(), set()
    for url in candidate_pages(website, home):
        html = home if url == website else fetch_html(url)
        if not html:
            continue
        out["address"] = out["address"] or address_from_html(html)
        out["employees"] = out["employees"] or employees_from_html(html)
        e, p = contacts_from_html(html)
        emails |= e
        phones |= p
        if out["address"] and out["employees"] and len(emails) >= 3:
            break
    parts = []
    if emails:
        parts.append("Emails: " + "; ".join(sorted(emails)[:8]))
    if phones:
        parts.append("Phones: " + "; ".join(sorted(phones)[:4]))
    out["contacts"] = " | ".join(parts) if parts else None
    return out


def linkedin_employees(url):
    """Best effort - LinkedIn usually returns 999/login wall for scripts."""
    html = fetch_html(url) if url else None
    if not html:
        return None
    meta = BeautifulSoup(html, "html.parser").find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        m = re.search(r"([\d,]+\+?\s*(?:-\s*[\d,]+)?\s*employees)", meta["content"], re.I)
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def process(input_path, output_path, use_seed=True):
    wb = openpyxl.load_workbook(input_path)
    ws = wb.active

    header_row = next((c.row for row in ws.iter_rows(min_col=1, max_col=1) for c in row
                       if isinstance(c.value, str) and c.value.strip().lower() == "account name"), None)
    if header_row is None:
        raise ValueError('Could not find an "Account Name" cell in column A')

    headers = ["Account Name", "Company Website", "Company Linkedin", "Company Address",
               "Employee Size", "Contacts Available on Website", "Source"]
    for i, h in enumerate(headers, 1):
        ws.cell(row=header_row, column=i, value=h)
    for col, w in zip("ABCDEFG", (45, 38, 45, 55, 45, 55, 22)):
        ws.column_dimensions[col].width = w

    try:
        r = header_row + 1
        while ws.cell(row=r, column=1).value:
            company = str(ws.cell(row=r, column=1).value).strip()
            print(f"\n[{r - header_row}] {company}")
            seed = SEED.get(company.lower(), {}) if use_seed else {}
            sources = set()

            website = find_website(company)
            polite()
            linkedin = find_linkedin(company)
            polite()
            (sources.add("live") if (website or linkedin) else None)

            if not website and seed.get("website"):
                website, _ = seed["website"], sources.add("seed")
            if not linkedin and seed.get("linkedin"):
                linkedin, _ = seed["linkedin"], sources.add("seed")

            site = scrape_site(website) if website else dict(address=None, employees=None, contacts=None)
            if any(site.values()):
                sources.add("live")

            address = site["address"] or None
            if not address and seed.get("address"):
                address = seed["address"]; sources.add("seed")

            employees = site["employees"] or linkedin_employees(linkedin)
            if employees and site["employees"]:
                employees = f"{employees} (company site)"
            if not employees and seed.get("employees"):
                employees = seed["employees"]; sources.add("seed")
            if not employees and linkedin:
                employees = f"Check manually: {linkedin}"

            contacts = site["contacts"] or "No direct contacts published (contact form only)"

            row = [website or "Not found", linkedin or "Not found",
                   address or "Not found", employees or "Not found", contacts,
                   "+".join(sorted(sources)) or "none"]
            for i, v in enumerate(row, start=2):
                ws.cell(row=r, column=i, value=v)
            print(f"    -> site={website} | li={linkedin} | addr={bool(address)} | src={row[-1]}")
            r += 1
    finally:
        wb.save(output_path)  # saves even if you press Ctrl+C mid-run
        print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    in_file = args[0] if len(args) > 0 else "Walkins_Test_05082026.xlsx"
    out_file = args[1] if len(args) > 1 else "Walkins_Test_filled.xlsx"
    process(in_file, out_file, use_seed="--no-seed" not in sys.argv)