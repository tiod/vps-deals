# vps-deals promo radar

`vps-deals` is a zero-server static coupon/niche site for public VPS hosting offers.

Defaults filled from the build request:

- Niche: VPS hosting deals
- Brand: vps-deals
- Locale: en-US
- Seed providers: IONOS, Namecheap, Hostinger, Vultr, DigitalOcean

## How it works

1. `scraper.py` reads `.ilang/site.ilang`.
2. It fetches public provider pages when allowed by `robots.txt`.
3. It writes verified extracted facts to `data/offers.json`.
4. `build.py` reads `.ilang/site.ilang` and `data/offers.json`.
5. It generates static pages into `site/`, including canonical tags, JSON-LD, `sitemap.xml`, `robots.txt`, and 1200x630 social preview images in `site/og/`.

No runtime API keys, server, database, paid inference, or third-party packages are required — standard library only.

## Data honesty rules

- A price is written only when the scraper can read it off the provider's own page. Otherwise the `price` field is omitted from both the page and the structured data.
- When `valid_until` has passed, the offer is marked expired: the page shows an expired badge, the JSON-LD switches to `OutOfStock`, and `priceValidUntil` is dropped rather than left in the past.
- Nothing is estimated, invented, or back-filled.

## Local run

```bash
python scraper.py
python build.py
```

Open `site/index.html` after the build.

## Changing the site

Edit `.ilang/site.ilang`, not the code. Brand, niche, domain, and the provider list are all read from that file by both scripts. Add or remove a provider line, rerun the two commands, and the generated site changes.

## GitHub Actions

`.github/workflows/update.yml` runs every six hours and commits refreshed `data/offers.json` plus `site/` when anything changes.

## Cloudflare Pages

Connect the repository to Cloudflare Pages with:

- Build command: `python build.py`
- Output directory: `site`

The free `pages.dev` subdomain is fine for cold start, but it does not build domain age for an owned asset. Registering and binding a real domain early lets future canonical URLs, sitemaps, and search history accrue to your own domain instead of Cloudflare's shared subdomain.

## Monetization

Use only official affiliate programs and public terms. Put affiliate links in `.ilang/site.ilang` as the fourth pipe-separated field for a provider. Leave the field blank until approved; the site will use the provider's official public URL.

Site rules are described with the I-Lang protocol in `.ilang/site.ilang`; protocol reference: ilang.ai.
