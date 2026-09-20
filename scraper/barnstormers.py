"""Scraper for American Legend "Legend Cub" listings on barnstormers.com.

Barnstormers has no dedicated category for Legend aircraft (unlike Aeronca,
Extra, or Great Lakes), so this searches by headline keyword instead of a
category page - see SEARCH_URLS.

Only whole-aircraft-for-sale listings are published: each ad's title must
name the Legend Cub / Super Legend Cub / Texas Sport Cub model or the AL3
type-certificate code, and titles that look like parts/accessories/
services/raffles are dropped. Requiring "Cub" (or the AL3 code) alongside
the bare "Legend" keyword matters more here than in the category-based
scrapers, since a headline keyword search can surface unrelated ads that
merely mention the word "Legend" in passing. Surviving titles are
rewritten to a canonical "YEAR Legend MODEL" form so every listing follows
the same format.
"""
from __future__ import annotations

import re
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup

from .common import (
    Listing,
    extract_date,
    extract_location,
    extract_price,
    fetch,
    format_aircraft_title,
)

SITE_NAME = "Barnstormers.com"
BASE = "https://www.barnstormers.com"
MAKE = "Legend"

# Barnstormers' advanced-search results for classified headlines containing
# "Legend" - the closest equivalent to a category page for this make, since
# no dedicated Legend category exists on the site.
SEARCH_URLS = [
    f"{BASE}/cat_search.php?headline=Legend&body=&part_num=&mfg=&model="
    "&user__profile__company=&user__last_name=&user__first_name="
    "&user__profile__country=&specialcase__state=&user__profile__city="
    "&user__profile__uzip=&specialcase__phone=&user__email=&my_cats__name="
    "&price__gte=&price__lte=&search_type=advanced&keyword=",
]

MAX_PAGES = 10
LISTING_LINK_RE = re.compile(r"^/classified-(\d+)-(.+)\.html$")
GENERIC_SITE_TITLE_SNIPPET = "barnstormers.com find aircraft"

# American Legend's LSA type designation (AL3), optionally with the
# horsepower/engine variant suffix Barnstormers sellers often append
# ("AL3-100", "AL3-115", "AL3-125"), written with or without a
# space/hyphen before the digits.
_MODEL_CODE_RE = re.compile(r"\bal3[\s-]?(\d{2,3})?\b", re.IGNORECASE)

# Named models, longest/most-specific first so "Super Legend Cub" isn't
# shadowed by the shorter "Legend Cub". Mapped to just the distinguishing
# part of the name (Cub / Super Cub / Sport Cub) since MAKE ("Legend") is
# prepended separately when the title is assembled - matching how e.g. the
# Aeronca scraper maps "Super Chief" rather than "Aeronca Super Chief".
_MODEL_NAME_RULES = [
    (re.compile(r"super\s*legend\s*cub", re.IGNORECASE), "Super Cub"),
    (re.compile(r"texas\s*sport\s*cub", re.IGNORECASE), "Sport Cub"),
    (re.compile(r"legend\s*cub", re.IGNORECASE), "Cub"),
]


def _extract_model(title: str) -> tuple[str, str] | None:
    match = _MODEL_CODE_RE.search(title)
    if match:
        hp = match.group(1)
        model = "AL3"
        if hp:
            model += f"-{hp}"
        return MAKE, model
    for pattern, canonical in _MODEL_NAME_RULES:
        if pattern.search(title):
            return MAKE, canonical
    return None


def _title_from_url(url: str) -> str:
    """Listing pages share a generic <title>/<h1>, but the URL slug is the ad's own title."""
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    match = LISTING_LINK_RE.match("/" + slug)
    if not match:
        return unquote(slug)
    return unquote(match.group(2)).replace("-", " ").strip()


def _find_listing_links(html: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if LISTING_LINK_RE.match(href):
            links.add(urljoin(BASE, href))
    return links


def _page_url(search_url: str, page: int) -> str:
    """Build a search results page's URL directly.

    Unlike Barnstormers' category pages (which paginate via a documented
    ?seocategory=<path>&page=<n> pattern - see the sibling Aeronca/Extra/
    Great Lakes repos), this environment couldn't reach barnstormers.com to
    confirm the equivalent for cat_search.php results, so this appends the
    same "&page=<n>" convention used elsewhere on the site as a best
    effort. If that guess is wrong, the "no new links" check in scrape()
    below still stops the loop safely after page 2 rather than looping or
    duplicating results - it just means only page 1 gets scraped.
    """
    if page <= 1:
        return search_url
    return f"{search_url}&page={page}"


def _debug_dump_hrefs(html: str, limit: int = 25) -> None:
    soup = BeautifulSoup(html, "lxml")
    hrefs = [a["href"] for a in soup.find_all("a", href=True)]
    interesting = [h for h in hrefs if "classified" in h.lower() or "legend" in h.lower()]
    sample = interesting[:limit] or hrefs[:limit]
    print(f"  [debug] {len(hrefs)} total <a href> on page; sample: {sample}")


def _parse_detail_page(url: str, html: str) -> Listing | None:
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None
    if title:
        title = re.sub(r"\s*[\|\-]\s*Barnstormers.*$", "", title, flags=re.IGNORECASE).strip()
    if not title or GENERIC_SITE_TITLE_SNIPPET in title.lower():
        title = _title_from_url(url)
    if not title:
        return None

    text = soup.get_text(" ", strip=True)

    formatted_title = format_aircraft_title(title, text, _extract_model)
    if not formatted_title:
        return None
    title = formatted_title

    price = extract_price(text)
    location = extract_location(text)
    date_posted = extract_date(text)

    return Listing(
        title=title,
        price=price,
        location=location,
        date_posted=date_posted,
        site=SITE_NAME,
        url=url,
    )


def scrape() -> list[Listing]:
    print(f"[{SITE_NAME}] starting scrape")
    all_links: set[str] = set()

    for search_url in SEARCH_URLS:
        seen_this_search: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            url = _page_url(search_url, page)
            html = fetch(url)
            if not html:
                break
            links = _find_listing_links(html)
            new_links = links - seen_this_search
            print(f"  [{search_url}] page {page}: {len(links)} links ({len(new_links)} new)")
            if page == 1 and not links:
                _debug_dump_hrefs(html)
            seen_this_search |= links
            if not new_links:
                break
        all_links |= seen_this_search

    print(f"[{SITE_NAME}] {len(all_links)} unique listing URLs found")

    listings: list[Listing] = []
    for url in sorted(all_links):
        html = fetch(url)
        if not html:
            continue
        listing = _parse_detail_page(url, html)
        if listing:
            listings.append(listing)

    print(f"[{SITE_NAME}] parsed {len(listings)} listings")
    return listings
