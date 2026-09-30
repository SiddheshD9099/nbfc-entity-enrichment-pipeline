import json
import re
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from search_resolver import fetch_html

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BAD_EMAIL_END = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")

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
