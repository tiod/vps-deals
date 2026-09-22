# vps-deals promo radar

**Brand:** vps-deals
**Niche:** VPS hosting deals
**Locale:** en-US
**Site address:** `https://vps-deals.pages.dev` — configured in `.ilang/site.ilang`. Not live yet: it goes live once this repository is connected to Cloudflare Pages. Do not treat the URL as reachable before that.

A zero-server static deals site. Every price, date, and source URL on the site is read from a
provider's own public page. Nothing is estimated, invented, or back-filled.

## What this repository is

A public, continuously-updated record of publicly listed VPS offers. Each automated commit is a
timestamped update: it shows the site is alive and gives the domain an operating history.

## How it works

1. `scraper.py` reads `.ilang/site.ilang`.
2. It fetches each provider's public page when `robots.txt` allows it.
3. It writes the facts it could actually verify to `data/offers.json`.
4. `build.py` reads `.ilang/site.ilang` and `data/offers.json`.
5. It generates `site/` — HTML pages, canonical tags, JSON-LD, `sitemap.xml`, `robots.txt`, and
   1200x630 social preview images in `site/og/`.

No runtime API keys, server, database, paid inference, or third-party packages are required —
Python standard library only.

## Data honesty rules

- A price is written only when the scraper can read it off the provider's own page. Otherwise the
  `price` field is omitted from the page **and** from the structured data.
- When `valid_until` has passed, the offer is marked expired: the page shows an expired badge, the
  JSON-LD switches to `OutOfStock`, and `priceValidUntil` is dropped rather than left in the past.
- Every offer page lists its `source_url` and `fetched_at`, so any number on the site can be traced
  back to the page it came from and the moment it was read.

## Providers currently tracked

Read from `.ilang/site.ilang` — that file, not this list, is the source of truth:

IONOS, OVHcloud, Hetzner, ScalaHosting, AWS Lightsail, Atlantic.Net, Alibaba Cloud ECS.

## Local run

```bash
python scraper.py
python build.py
```

Open `site/index.html` after the build.

## Changing the site

Edit `.ilang/site.ilang`, not the code. Brand, niche, locale, domain, and the provider list are all
read from that file by both scripts. Add or remove a provider line, rerun the two commands, and the
generated site changes. Provider line format:

```
Name | homepage | offer page / sitemap / feed | affiliate link (blank = use the plain official URL)
```

## GitHub Actions

`.github/workflows/update.yml` runs every six hours and commits refreshed `data/offers.json` plus
`site/` when anything changes.

## Cloudflare Pages

Connect the repository with:

- Build command: `python build.py`
- Output directory: `site`

The free `pages.dev` subdomain is fine for cold start, but it does not build domain age for an owned
asset. Registering and binding a real domain early lets canonical URLs, sitemaps, and search history
accrue to your own domain instead of Cloudflare's shared subdomain.

## Monetization

Only official affiliate programs with public terms (CJ, ShareASale, Impact and similar). Put the
affiliate link in the fourth field of a provider line in `.ilang/site.ilang`; leave it blank until
you are approved and the site falls back to the provider's plain public URL.

Outbound links are marked `rel="sponsored nofollow noopener"`. When at least one affiliate link is
present, `build.py` renders the disclosure text from the `AFFILIATE` section of `.ilang/site.ilang`
into every page footer. No affiliate link, no disclosure — the site does not claim a commission it
cannot earn.

Never: brand-bidding, cookie injection, or self-purchasing. The value of a site like this is the
years and trust behind it; one rule violation can reset years of accumulation.

Site rules are described with the I-Lang protocol in `.ilang/site.ilang`; protocol reference: ilang.ai.
