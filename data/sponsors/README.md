# Sponsor portfolio test list

**What it is:** 291 current portfolio companies of 6 US private equity sponsors, taken from each sponsor's own website on 2026-11-01. It is the input for measuring how many PE-owned companies appear as borrowers in BDC filings. No matching has been run.

**File:** `sponsor_portfolios.csv`. Columns: sponsor, company_name (as written on the site), sector (as written, blank if none), hq (blank if none), status, source_url, retrieved_date.

## Sponsors

| Sponsor | Size | Result | Rows | Current on site | Source |
|---|---|---|---|---|---|
| Thoma Bravo | Large | Used | 60 | 62 | thomabravo.com/portfolio (data embedded in page) |
| Vista Equity Partners | Large | Used, replaces Clearlake | 60 | 86 | vistaequitypartners.com/about/companies/ (one detail page per company) |
| Genstar Capital | Mid-market | Used | 47 | 47 | gencap.com/companies/ |
| Alpine Investors | Mid-market | Used | 30 | 30 | alpineinvestors.com/portfolio/ |
| Gryphon Investors | Mid-market | Used | 35 | 35 | gryphon-inv.com/companies/ (Private Equity page) |
| Shore Capital Partners | Mid-market | Used | 59 | 64 listed as current | shorecp.com/companies |
| Clearlake Capital | Large | Failed | 0 | n/a | Cloudflare challenge (403) on the page, wp-json and sitemap |
| H.I.G. Capital | Mid-market | Readable, not used | 0 | 167 active | Not needed once 4 mid-market sponsors worked |
| Audax, Riverside | Mid-market | Not used | 0 | n/a | Tables load by JavaScript; not pursued |

## How "current" was decided

- **Thoma Bravo:** status field `current` in the page data. 15 companies have no status at all; they were left out.
- **Vista:** `data-status="current"` on the listing, confirmed by "Status: Current" on each detail page.
- **Genstar:** "Status: Current / [year] Investment". The page repeats each company across sector tabs; duplicates were removed.
- **Alpine:** Status column = Current.
- **Gryphon:** status filter = current.
- **Shore:** `realized` = FALSE. Left out: 2 "To Be Announced (Healthcare)" placeholders and 3 records named "(Merged)" (SouthStar Urgent Care, Column Health, Elevate Women's Health) even though flagged unrealized.

## Caveats

- **Cap of 60:** Thoma Bravo and Vista keep the first 60 current companies in the order the page lists them. Shore stayed under the cap.
- **Order:** Shore's list was sorted alphabetically to match the rendered page, because the raw data order differs.
- **HQ:** only Vista gives a city. Thoma Bravo gives a region ("US – West", "UK"), stored in `hq` as written. Others are blank.
- **Sector:** Alpine is "Industry / Vertical". Thoma Bravo uses its 3 broad sectors. Gryphon uses the one-line description shown under each logo.
- **Non-US companies:** Thoma Bravo and Vista include some non-US companies (for example Accelya, Barcelona). They are kept.
- **Scope:** Gryphon's Junior Capital page and Vista credit holdings are not included.
- **Freshness:** sponsor sites lag deals. Some "current" companies may have been sold.
