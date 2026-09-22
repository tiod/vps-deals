# ::ILANG [TYPE:script][PROJECT:vps-deals][LANG:zh]
# ::ROLE 读取 data/offers.json 和 .ilang/site.ilang 生成静态站 site/
# ::BOUNDARY 只渲染已抓取事实 不补写未验证价格或有效期 不编优惠
# ::CONFIG 品牌 细分 域名 厂商清单来自 .ilang/site.ilang
# ::OUTPUT index provider deal compare sitemap robots og图

from __future__ import annotations

import html
import json
import re
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / ".ilang" / "site.ilang"
DATA_PATH = ROOT / "data" / "offers.json"
TEMPLATE_DIR = ROOT / "templates"
SITE_DIR = ROOT / "site"
OG_SUBDIR = "og"
OG_WIDTH = 1200
OG_HEIGHT = 630

# ---------------------------------------------------------------- og 图字体
# 5x7 点阵大写字体，纯标准库绘制，运行时零依赖零推理
FONT: dict[str, str] = {
    "A": ".###./#...#/#...#/#####/#...#/#...#/#...#",
    "B": "####./#...#/#...#/####./#...#/#...#/####.",
    "C": ".####/#..../#..../#..../#..../#..../.####",
    "D": "####./#...#/#...#/#...#/#...#/#...#/####.",
    "E": "#####/#..../#..../####./#..../#..../#####",
    "F": "#####/#..../#..../####./#..../#..../#....",
    "G": ".####/#..../#..../#..##/#...#/#...#/.####",
    "H": "#...#/#...#/#...#/#####/#...#/#...#/#...#",
    "I": "#####/..#../..#../..#../..#../..#../#####",
    "J": "..###/...#./...#./...#./...#./#..#./.##..",
    "K": "#...#/#..#./#.#../##.../#.#../#..#./#...#",
    "L": "#..../#..../#..../#..../#..../#..../#####",
    "M": "#...#/##.##/#.#.#/#...#/#...#/#...#/#...#",
    "N": "#...#/##..#/#.#.#/#..##/#...#/#...#/#...#",
    "O": ".###./#...#/#...#/#...#/#...#/#...#/.###.",
    "P": "####./#...#/#...#/####./#..../#..../#....",
    "Q": ".###./#...#/#...#/#...#/#.#.#/#..#./.##.#",
    "R": "####./#...#/#...#/####./#.#../#..#./#...#",
    "S": ".####/#..../#..../.###./....#/....#/####.",
    "T": "#####/..#../..#../..#../..#../..#../..#..",
    "U": "#...#/#...#/#...#/#...#/#...#/#...#/.###.",
    "V": "#...#/#...#/#...#/#...#/#...#/.#.#./..#..",
    "W": "#...#/#...#/#...#/#.#.#/#.#.#/##.##/#...#",
    "X": "#...#/#...#/.#.#./..#../.#.#./#...#/#...#",
    "Y": "#...#/#...#/.#.#./..#../..#../..#../..#..",
    "Z": "#####/....#/...#./..#../.#.../#..../#####",
    "0": ".###./#...#/#..##/#.#.#/##..#/#...#/.###.",
    "1": "..#../.##../..#../..#../..#../..#../.###.",
    "2": ".###./#...#/....#/...#./..#../.#.../#####",
    "3": "#####/...#./..#../...#./....#/#...#/.###.",
    "4": "...#./..##./.#.#./#..#./#####/...#./...#.",
    "5": "#####/#..../####./....#/....#/#...#/.###.",
    "6": "..##./.#.../#..../####./#...#/#...#/.###.",
    "7": "#####/....#/...#./..#../.#.../.#.../.#...",
    "8": ".###./#...#/#...#/.###./#...#/#...#/.###.",
    "9": ".###./#...#/#...#/.####/....#/...#./.##..",
    " ": "...../...../...../...../...../...../.....",
    "-": "...../...../...../#####/...../...../.....",
    ".": "...../...../...../...../...../.##../.##..",
    ",": "...../...../...../...../.##../.##../.#...",
    "/": "....#/....#/...#./..#../.#.../#..../#....",
    ":": "...../.##../.##../...../.##../.##../.....",
    "&": ".##../#..#./#..#./.##../#.#.#/#..#./.##.#",
    "$": "..#../.####/#.#../.###./..#.#/####./..#..",
    "+": "...../..#../..#../#####/..#../..#../.....",
    "!": "..#../..#../..#../..#../..#../...../..#..",
    "'": "..#../..#../...../...../...../...../.....",
    "(": "...#./..#../.#.../.#.../.#.../..#../...#.",
    ")": ".#.../..#../...#./...#./...#./..#../.#...",
    "=": "...../...../#####/...../#####/...../.....",
}

BG = (15, 118, 110)
BG_DEEP = (13, 100, 94)
INK = (255, 255, 255)
INK_SOFT = (204, 251, 241)
ACCENT = (180, 83, 9)


def clean(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "offer"


def parse_site(path: Path) -> dict[str, str]:
    raw = path.read_text(encoding="utf-8")
    match = re.search(r"::STATE\{@SITE,\s*(.*?)\}", raw, re.S)
    site: dict[str, str] = {}
    if match:
        for key, value in re.findall(r"(\w+):([^,\}]+)", match.group(1)):
            site[key.strip()] = value.strip()
    return site


def load_template(name: str) -> Template:
    return Template((TEMPLATE_DIR / name).read_text(encoding="utf-8"))


def canonical(base: str, path: str = "") -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}".rstrip("/") + ("/" if path and not Path(path).suffix else "")


def iso_date(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).date().isoformat()
    return value[:10]


def month_label() -> str:
    return datetime.now(timezone.utc).strftime("%B %Y")


def is_expired(offer: dict) -> bool:
    if str(offer.get("status", "active")) != "active":
        return True
    valid_until = offer.get("valid_until")
    if not valid_until:
        return False
    return str(valid_until)[:10] < datetime.now(timezone.utc).date().isoformat()


# ------------------------------------------------------------- og 图生成器
def _new_canvas(color: tuple[int, int, int]) -> bytearray:
    return bytearray(bytes(color)) * (OG_WIDTH * OG_HEIGHT)


def _fill(canvas: bytearray, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(OG_WIDTH, x + w), min(OG_HEIGHT, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(color) * (x1 - x0)
    for yy in range(y0, y1):
        start = (yy * OG_WIDTH + x0) * 3
        canvas[start:start + len(row)] = row


def _text_width(text: str, scale: int) -> int:
    return max(0, len(text) * 6 * scale - scale)


def _draw_text(canvas: bytearray, text: str, x: int, y: int, scale: int, color: tuple[int, int, int]) -> int:
    cursor = x
    for char in text.upper():
        rows = FONT.get(char, FONT[" "]).split("/")
        for ry, row in enumerate(rows):
            for rx, cell in enumerate(row):
                if cell == "#":
                    _fill(canvas, cursor + rx * scale, y + ry * scale, scale, scale, color)
        cursor += 6 * scale
    return cursor - x - scale


def _truncate(text: str, scale: int, max_width: int) -> str:
    if _text_width(text, scale) <= max_width:
        return text
    allowed = max(1, (max_width + scale) // (6 * scale))
    clipped = text[:allowed].rstrip()
    if " " in clipped and text[allowed:allowed + 1] not in (" ", ""):
        clipped = clipped.rsplit(" ", 1)[0]  # 断在词边界，不要切半个词
    return clipped.rstrip(" -/:,")


def _wrap(text: str, scale: int, max_width: int, max_lines: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if _text_width(candidate, scale) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if not lines:
        lines = [""]
    lines[-1] = _truncate(lines[-1], scale, max_width)
    return lines


def _encode_png(canvas: bytearray) -> bytes:
    raw = bytearray()
    stride = OG_WIDTH * 3
    for y in range(OG_HEIGHT):
        raw.append(0)
        raw += canvas[y * stride:(y + 1) * stride]

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", OG_WIDTH, OG_HEIGHT, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def render_og_image(brand: str, headline: str, subline: str, footer: str) -> bytes:
    canvas = _new_canvas(BG)
    _fill(canvas, 0, 0, OG_WIDTH, 18, ACCENT)
    _fill(canvas, 0, OG_HEIGHT - 120, OG_WIDTH, 120, BG_DEEP)

    pad = 72
    max_width = OG_WIDTH - pad * 2
    _draw_text(canvas, _truncate(brand, 6, max_width), pad, 68, 6, INK_SOFT)

    lines = _wrap(headline, 8, max_width, 2)
    y = 220
    for line in lines:
        _draw_text(canvas, line, pad, y, 8, INK)
        y += 8 * 7 + 34

    _draw_text(canvas, _truncate(subline, 4, max_width), pad, 470, 4, INK_SOFT)
    _draw_text(canvas, _truncate(footer, 3, max_width), pad, 550, 3, INK_SOFT)
    return _encode_png(canvas)


# ------------------------------------------------------------------ 结构化数据
def offer_json_ld(offer: dict, url: str) -> dict:
    expired = is_expired(offer)
    payload = {
        "@context": "https://schema.org",
        "@type": "Offer",
        "name": offer.get("title"),
        "url": offer.get("offer_url"),
        "availability": "https://schema.org/OutOfStock" if expired else "https://schema.org/InStock",
        "mainEntityOfPage": url,
        "seller": {"@type": "Organization", "name": offer.get("provider")},
    }
    if offer.get("price") and offer.get("currency"):
        payload["price"] = offer["price"]
        payload["priceCurrency"] = offer["currency"]
    if offer.get("valid_until") and not expired:
        payload["priceValidUntil"] = offer["valid_until"]
    return payload


def breadcrumb_json_ld(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": idx, "name": name, "item": url}
            for idx, (name, url) in enumerate(items, start=1)
        ],
    }


def item_list_json_ld(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {"@type": "ListItem", "position": idx, "name": name, "url": url}
            for idx, (name, url) in enumerate(items, start=1)
        ],
    }


def layout(site: dict[str, str], title: str, description: str, body: str, canonical_url: str,
           og_image: str, json_ld: list[dict] | None = None) -> str:
    ld = "\n".join(
        f'<script type="application/ld+json">{json.dumps(item, ensure_ascii=False)}</script>' for item in (json_ld or [])
    )
    return load_template("base.html").safe_substitute(
        brand=clean(site.get("brand", "vps-deals")),
        niche=clean(site.get("niche", "VPS hosting deals")),
        title=clean(title),
        description=clean(description),
        canonical=clean(canonical_url),
        og_url=clean(canonical_url),
        og_image=clean(og_image),
        og_site_name=clean(site.get("brand", "vps-deals")),
        json_ld=ld,
        body=body,
        generated_at=clean(datetime.now(timezone.utc).replace(microsecond=0).isoformat()),
    )


def offer_card(offer: dict, detail_path: str) -> str:
    expired = is_expired(offer)
    bits = [f'<span>{clean(offer.get("provider"))}</span>']
    if offer.get("price") and offer.get("currency"):
        price_text = f'{clean(offer["currency"])} {clean(offer["price"])}'
        bits.append(f'<span class="price">{price_text}</span>' if not expired else f'<span class="price stale">{price_text}</span>')
    if offer.get("valid_until"):
        bits.append(f'<span>Valid until {clean(offer["valid_until"])}</span>')
    if expired:
        bits.append('<span class="badge">Expired</span>')
    description = f'<p>{clean(offer.get("description", ""))}</p>' if offer.get("description") else ""
    return f"""
    <article class="deal-card">
      <div class="deal-meta">{''.join(bits)}</div>
      <h2><a href="{clean(detail_path)}">{clean(offer.get("title"))}</a></h2>
      {description}
      <div class="actions">
        <a class="button primary" href="{clean(offer.get("offer_url"))}" rel="sponsored nofollow noopener">View official offer</a>
        <a class="button" href="{clean(detail_path)}">Details</a>
      </div>
    </article>
    """


def price_span(offer: dict) -> str:
    if not offer.get("price") or not offer.get("currency"):
        return ""
    value = f'{offer["currency"]} {offer["price"]}'
    return value


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main() -> int:
    site = parse_site(CONFIG_PATH)
    data = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.exists() else {"offers": [], "generated_at": ""}
    offers: list[dict] = data.get("offers", [])
    offers.sort(key=lambda o: (is_expired(o), str(o.get("provider", ""))))
    brand = site.get("brand", "vps-deals")
    niche = site.get("niche", "VPS hosting deals")
    base_url = site.get("domain", "https://vps-deals.pages.dev").rstrip("/")
    month = month_label()
    SITE_DIR.mkdir(exist_ok=True)

    og_paths: dict[str, str] = {}

    def emit_og(key: str, headline: str, subline: str) -> str:
        slug = slugify(key)
        rel = f"{OG_SUBDIR}/{slug}.png"
        write_bytes(SITE_DIR / rel, render_og_image(brand, headline, subline, base_url.replace("https://", "")))
        og_paths[key] = rel
        return f"{base_url}/{rel}"

    detail_paths: dict[int, str] = {
        index: f"deals/{slugify(str(offer.get('provider', 'provider')) + '-' + str(offer.get('title', 'offer')))}.html"
        for index, offer in enumerate(offers)
    }
    active_count = sum(1 for offer in offers if not is_expired(offer))
    provider_names = sorted({str(offer.get("provider", "Provider")) for offer in offers})

    # ---------------------------------------------------------------- index
    cards = "\n".join(offer_card(offer, detail_paths[idx]) for idx, offer in enumerate(offers)) or \
        "<p>No current public offers were extracted yet.</p>"
    index_title = f"{brand}: {active_count} verified {niche} ({month})"
    index_desc = (
        f"{active_count} current public {niche} offers from {len(provider_names)} providers, "
        f"checked against official pages. Prices shown only when verified. Updated {month}."
    )
    index_url = canonical(base_url, "index.html")
    index_og = emit_og("index", f"{active_count} verified {niche}", f"Checked {month} - verified at source")
    index_body = load_template("index.html").safe_substitute(
        brand=clean(brand),
        niche=clean(niche),
        updated=clean(data.get("generated_at", "")),
        cards=cards,
        count=str(active_count),
        providers=str(len(provider_names)),
    )
    item_links = [(str(offer.get("title")), canonical(base_url, detail_paths[idx])) for idx, offer in enumerate(offers)]
    write(SITE_DIR / "index.html", layout(site, index_title, index_desc, index_body, index_url, index_og, [item_list_json_ld(item_links)]))

    # ------------------------------------------------------------- provider
    provider_groups: dict[str, list[tuple[int, dict]]] = {}
    for idx, offer in enumerate(offers):
        provider_groups.setdefault(str(offer.get("provider", "Provider")), []).append((idx, offer))

    for provider, grouped in provider_groups.items():
        provider_path = f"providers/{slugify(provider)}.html"
        provider_url = canonical(base_url, provider_path)
        live = [o for _, o in grouped if not is_expired(o)]
        prices = sorted(float(o["price"]) for o in live if str(o.get("price", "")).replace(".", "", 1).isdigit())
        currency = next((str(o.get("currency")) for o in live if o.get("currency")), "USD")
        price_hint = f"from {currency} {prices[0]:g}" if prices else "official public pages"
        provider_title = f"{provider} {niche}: {price_hint} ({month})"
        provider_desc = (
            f"{len(live)} current public {provider} offer(s) extracted from the provider's own pages. "
            f"{price_hint}. Source links and fetch dates included."
        )
        provider_og = emit_og(f"provider-{provider}", f"{provider} {niche}", price_hint)
        body = load_template("provider.html").safe_substitute(
            provider=clean(provider),
            niche=clean(niche),
            cards="\n".join(offer_card(offer, "../" + detail_paths[idx]) for idx, offer in grouped),
        )
        aggregate = {
            "@context": "https://schema.org",
            "@type": "Service",
            "name": f"{provider} {niche}",
            "serviceType": niche,
            "provider": {"@type": "Organization", "name": provider, "url": grouped[0][1].get("provider_homepage")},
            "url": provider_url,
        }
        if prices:
            aggregate["offers"] = {
                "@type": "AggregateOffer",
                "lowPrice": prices[0],
                "highPrice": prices[-1],
                "offerCount": len(prices),
                "priceCurrency": currency,
            }
        write(SITE_DIR / provider_path, layout(site, provider_title, provider_desc, body, provider_url, provider_og, [aggregate]))

    # ----------------------------------------------------------------- deal
    for idx, offer in enumerate(offers):
        detail_path = detail_paths[idx]
        detail_url = canonical(base_url, detail_path)
        provider_path = f"providers/{slugify(str(offer.get('provider', 'provider')))}.html"
        expired = is_expired(offer)
        price_line = ""
        if offer.get("price") and offer.get("currency"):
            price_line = f"<dt>Verified price</dt><dd>{clean(offer['currency'])} {clean(offer['price'])}</dd>"
        valid_line = ""
        if offer.get("valid_until"):
            label = "Expired on" if expired else "Valid until"
            valid_line = f"<dt>{label}</dt><dd>{clean(offer['valid_until'])}</dd>"
        status_line = '<dt>Status</dt><dd><span class="badge">Expired — check the source for current pricing</span></dd>' if expired else ""
        verified = price_span(offer)
        deal_title = f"{offer.get('title')} — {offer.get('provider')}"
        if verified and not expired:
            deal_title += f" from {verified}"
        deal_title += f" ({month})"
        deal_desc = (
            f"{offer.get('provider')} public offer page facts: "
            + (f"verified price {verified}. " if verified else "price not verified at source. ")
            + f"Checked {iso_date(str(offer.get('fetched_at')))}."
        )
        deal_og = emit_og(
            f"deal-{offer.get('provider')}-{offer.get('title')}",
            str(offer.get("title")),
            (f"{offer.get('provider')} - {verified}" if verified else f"{offer.get('provider')} - price unverified"),
        )
        body = load_template("deal.html").safe_substitute(
            title=clean(offer.get("title")),
            provider=clean(offer.get("provider")),
            description=clean(offer.get("description", "This page summarizes facts extracted from the provider's public offer page.")),
            source_url=clean(offer.get("source_url")),
            offer_url=clean(offer.get("offer_url")),
            fetched_at=clean(offer.get("fetched_at")),
            price_line=price_line,
            valid_line=valid_line,
            status_line=status_line,
            provider_path=clean("../" + provider_path),
        )
        breadcrumbs = breadcrumb_json_ld([
            ("Home", canonical(base_url, "index.html")),
            (str(offer.get("provider")), canonical(base_url, provider_path)),
            (str(offer.get("title")), detail_url),
        ])
        write(
            SITE_DIR / detail_path,
            layout(site, deal_title, deal_desc, body, detail_url, deal_og,
                   [offer_json_ld(offer, detail_url), breadcrumbs]),
        )

    # -------------------------------------------------------------- compare
    compare_rows = "\n".join(
        "<tr><td>{p}</td><td><a href='{d}'>{t}</a></td><td>{pr}</td><td>{s}</td><td><a href='{u}' rel='sponsored nofollow noopener'>Official page</a></td></tr>".format(
            p=clean(o.get("provider")),
            d=clean(detail_paths[i]),
            t=clean(o.get("title")),
            pr=clean(price_span(o) or "unverified"),
            s='<span class="badge">Expired</span>' if is_expired(o) else "Active",
            u=clean(o.get("offer_url")),
        )
        for i, o in enumerate(offers)
    )
    compare_body = load_template("compare.html").safe_substitute(rows=compare_rows, niche=clean(niche))
    compare_url = canonical(base_url, "compare.html")
    compare_og = emit_og("compare", f"Compare {niche}", f"{active_count} active offers - {month}")
    write(
        SITE_DIR / "compare.html",
        layout(site, f"Compare {niche}: {active_count} offers ({month})",
               f"Side-by-side table of {len(offers)} public {niche} offers extracted from official pages. Unverified prices are marked.",
               compare_body, compare_url, compare_og, [item_list_json_ld(item_links)]),
    )

    # ------------------------------------------------------- sitemap / robots
    urls = [("index.html", data.get("generated_at", "")), ("compare.html", data.get("generated_at", ""))]
    urls += [(detail_paths[i], o.get("fetched_at", data.get("generated_at", ""))) for i, o in enumerate(offers)]
    urls += [(f"providers/{slugify(provider)}.html", data.get("generated_at", "")) for provider in provider_groups]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, lastmod in urls:
        sitemap.append(f"  <url><loc>{clean(canonical(base_url, path))}</loc><lastmod>{clean(iso_date(str(lastmod)))}</lastmod></url>")
    sitemap.append("</urlset>")
    write(SITE_DIR / "sitemap.xml", "\n".join(sitemap) + "\n")
    write(SITE_DIR / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {canonical(base_url, 'sitemap.xml')}\n")
    print(f"built {len(urls)} pages + {len(og_paths)} og images in {SITE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
