# Legend

Daily aggregator of American Legend "Legend Cub" classified listings from
[Barnstormers.com](https://www.barnstormers.com), published as a static page
(`docs/index.html`) meant to be embedded via `<iframe>` on taildraggers.com.

Controller.com was evaluated but dropped: its search results are only reachable
through an internal client-side widget (not a plain URL), which a headless
browser can't drive reliably for an unattended daily job.

## How it works

- Barnstormers has no dedicated category for Legend aircraft (unlike Aeronca,
  Extra, or Great Lakes), so `scraper/barnstormers.py` uses Barnstormers'
  [advanced search for classified headlines containing "Legend"](https://www.barnstormers.com/cat_search.php?headline=Legend&body=&part_num=&mfg=&model=&user__profile__company=&user__last_name=&user__first_name=&user__profile__country=&specialcase__state=&user__profile__city=&user__profile__uzip=&specialcase__phone=&user__email=&my_cats__name=&price__gte=&price__lte=&search_type=advanced&keyword=)
  instead of a category page - the closest equivalent available. It follows
  pagination, then visits each listing's detail page to pull out the price,
  location, and posted date (falling back to regex heuristics over the visible
  text since the site doesn't expose structured data). The title is derived
  from the listing URL's own SEO slug, since every detail page shares one
  generic `<title>`/`<h1>`.

  The pagination scheme for these search results pages (`&page=<n>`) is a
  best-effort guess, not confirmed against the live site - if it's wrong, the
  scraper still degrades safely to just page 1 rather than looping or
  duplicating results (see the docstring on `_page_url` in
  `scraper/barnstormers.py`).
- Only whole-aircraft-for-sale listings are published. Titles that read as
  parts, accessories, services, or raffles are dropped (see `EXCLUDE_KEYWORDS`
  in `scraper/common.py`) before anything else. Because this scraper is
  keyword-search-based rather than category-based, a bare "Legend" match isn't
  enough on its own to accept a listing - unlike the category-scoped
  Aeronca/Extra/Great Lakes repos, a headline search can surface unrelated ads
  that merely mention "Legend" in passing. Every surviving title must also
  name the **Legend Cub**, **Super Legend Cub**, or **Texas Sport Cub** model;
  the **AL3** type-certificate code (optionally with its horsepower/engine
  variant suffix, e.g. `AL3-100`); or the **AL18**/**AL-18** code or its
  factory nickname **MOAC** ("Mother Of All Cubs", American Legend's larger
  non-LSA Cub variant) - see `_AL3_RE`/`_AL18_RE`/`_MOAC_RE`/
  `_MODEL_NAME_RULES` in `scraper/barnstormers.py`. Every surviving listing's
  title is rewritten to a
  canonical **`YEAR Legend MODEL`** form when the ad states a model year (e.g.
  `2015 Legend Cub`, `2018 Legend Super Cub`), or just **`Legend MODEL`** when
  it doesn't - a missing year isn't disqualifying, since plenty of genuine ads
  simply don't state one in the title - regardless of how the original ad was
  worded, so the page reads consistently.
- `main.py` runs the scraper, de-duplicates results, and renders them into
  `docs/index.html` titled **"Other Legend Ads on the Web"**, with one row per
  listing: Title (linked to the original ad), Price, Location, Date Posted, and
  Site Posted On. Links use `rel="noopener noreferrer"` and the page sets a
  `no-referrer` meta policy, so Barnstormers never sees that the click came
  from taildraggers.com.
- `.github/workflows/daily-scrape.yml` runs the whole thing once a day (13:00
  UTC), commits the regenerated `docs/index.html` if it changed, and can also
  be triggered manually from the Actions tab (`workflow_dispatch`).

## One-time setup: enable GitHub Pages

This repo publishes `docs/index.html` as a plain static file — GitHub Pages just needs
to be pointed at it once:

1. Go to **Settings → Pages** in this repository.
2. Under **Build and deployment → Source**, choose **Deploy from a branch**.
3. Branch: `main`, folder: `/docs`. Save.
4. GitHub will publish the page at `https://taildraggers.github.io/legend/`
   (may take a minute or two the first time).

## Embedding on taildraggers.com

```html
<iframe
  src="https://taildraggers.github.io/legend/"
  title="Other Legend Ads on the Web"
  style="width: 100%; height: 800px; border: 0;"
  loading="lazy">
</iframe>
```

## Running locally

```bash
pip install -r requirements.txt
python main.py
```

This writes/overwrites `docs/index.html`.

## Notes

- If Barnstormers changes its markup or is briefly unreachable, the run logs will
  show a `[warn]`/`[error]` line pointing at what broke rather than failing silently.
- The scraper identifies itself with a browser-like `User-Agent` and adds a short
  delay between requests to be polite to the site.
