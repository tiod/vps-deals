# ::ILANG [TYPE:script][PROJECT:vps-deals][LANG:zh]
# ::ROLE 抓公开厂商页面并写 data/offers.json
# ::BOUNDARY 不编优惠 不编价格 不绕 robots.txt 不抓登录内容
# ::CONFIG 只从 .ilang/site.ilang 读取品牌和厂商清单

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / ".ilang" / "site.ilang"
DATA_PATH = ROOT / "data" / "offers.json"
USER_AGENT = "static-coupon-scraper/1.0"


def set_user_agent(domain: str) -> None:
    """用 site.ilang 里的域名拼 UA，避免把域名硬编码在代码里。"""
    global USER_AGENT
    domain = (domain or "").strip().rstrip("/")
    USER_AGENT = f"static-coupon-scraper/1.0 (+{domain})" if domain else "static-coupon-scraper/1.0"


@dataclass(frozen=True)
class Provider:
    name: str
    homepage: str
    source_url: str
    affiliate_url: str


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.h1: list[str] = []
        self.headings: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._tag_stack: list[str] = []
        self._current_link: str | None = None
        self._link_text: list[str] = []
        self._capture_title = False
        self._capture_h1 = False
        self._h1_text: list[str] = []
        self.visible_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {k.lower(): v or "" for k, v in attrs}
        self._tag_stack.append(tag)
        if tag == "title":
            self._capture_title = True
        if tag == "h1":
            self._capture_h1 = True
            self._h1_text = []
        if tag in {"h2", "h3"}:
            self.headings.append("")
        if tag == "a" and attrs_map.get("href"):
            self._current_link = attrs_map["href"]
            self._link_text = []
        if tag == "meta" and attrs_map.get("name", "").lower() == "description":
            self.meta_description = clean(attrs_map.get("content", ""))
        if tag == "meta" and attrs_map.get("property", "").lower() == "og:description":
            self.meta_description = self.meta_description or clean(attrs_map.get("content", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._capture_title = False
        if tag == "h1":
            self._capture_h1 = False
            h1 = clean(" ".join(self._h1_text))
            if h1:
                self.h1.append(h1)
        if tag == "a" and self._current_link:
            label = clean(" ".join(self._link_text))
            if label:
                self.links.append((label, self._current_link))
            self._current_link = None
            self._link_text = []
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        text = clean(data)
        if not text:
            return
        if self._capture_title:
            self.title = clean(f"{self.title} {text}")
        if self._capture_h1:
            self._h1_text.append(text)
        if self._current_link:
            self._link_text.append(text)
        if self._tag_stack and self._tag_stack[-1] in {"script", "style", "noscript"}:
            return
        self.visible_text.append(text)


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_config(path: Path) -> dict[str, object]:
    raw = path.read_text(encoding="utf-8")
    site: dict[str, str] = {}
    state_match = re.search(r"::STATE\{@SITE,\s*(.*?)\}", raw, re.S)
    if state_match:
        for key, value in re.findall(r"(\w+):([^,\}]+)", state_match.group(1)):
            site[key.strip()] = value.strip()

    providers: list[Provider] = []
    in_providers = False
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("::MODULE{PROVIDERS"):
            in_providers = True
            continue
        if in_providers and stripped.startswith("::"):
            break
        if in_providers and "|" in stripped:
            parts = [part.strip() for part in stripped.split("|")]
            if len(parts) >= 3:
                providers.append(Provider(parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 else ""))
    return {"site": site, "providers": providers}


def allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:
        return True
    return parser.can_fetch(USER_AGENT, url)


def fetch(url: str) -> str:
    if not allowed_by_robots(url):
        raise RuntimeError(f"robots.txt disallows {url}")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8"})
    with urlopen(request, timeout=25) as response:
        content_type = response.headers.get("content-type", "")
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read(1_500_000)
    if not any(kind in content_type for kind in ("html", "xml", "text", "application/octet-stream")):
        raise RuntimeError(f"unsupported content type {content_type}")
    return body.decode(charset, errors="replace")


def extract_price(text: str) -> tuple[str, str] | tuple[None, None]:
    patterns = [
        (r"\$\s?(\d+(?:\.\d{1,2})?)", "USD"),
        (r"€\s?(\d+(?:\.\d{1,2})?)", "EUR"),
        (r"£\s?(\d+(?:\.\d{1,2})?)", "GBP"),
    ]
    for pattern, currency in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1), currency
    return None, None


def extract_valid_until(text: str) -> str | None:
    patterns = [
        r"(?:valid until|ends|expires)\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        r"(20\d{2}-\d{2}-\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        value = match.group(1)
        for fmt in ("%B %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                pass
    return None


def offer_title(provider: Provider, parser: TextExtractor) -> str:
    candidates = parser.h1 + [parser.title, parser.meta_description]
    for candidate in candidates:
        if candidate:
            return clean(candidate)[:140]
    return f"{provider.name} public VPS offer page"


def scrape_provider(provider: Provider, fetched_at: str) -> dict[str, object]:
    html = fetch(provider.source_url)
    parser = TextExtractor()
    parser.feed(html)
    text = clean(" ".join(parser.visible_text))
    price, currency = extract_price(text)
    valid_until = extract_valid_until(text)
    target_url = provider.affiliate_url or provider.source_url
    title = offer_title(provider, parser)
    today = datetime.now(timezone.utc).date().isoformat()
    status = "expired" if (valid_until and valid_until < today) else "active"
    offer: dict[str, object] = {
        "provider": provider.name,
        "provider_homepage": provider.homepage,
        "title": title,
        "offer_url": target_url,
        "source_url": provider.source_url,
        "fetched_at": fetched_at,
        "status": status,
    }
    if price and currency:
        offer["price"] = price
        offer["currency"] = currency
    if valid_until:
        offer["valid_until"] = valid_until
    if parser.meta_description:
        offer["description"] = parser.meta_description[:240]
    return offer


def main() -> int:
    config = parse_config(CONFIG_PATH)
    set_user_agent(str(config["site"].get("domain", "")))
    providers: Iterable[Provider] = config["providers"]  # type: ignore[assignment]
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    offers: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    for provider in providers:
        try:
            offers.append(scrape_provider(provider, fetched_at))
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            errors.append({"provider": provider.name, "source_url": provider.source_url, "error": str(exc)})

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": fetched_at,
        "site": config["site"],
        "offers": offers,
        "errors": errors,
    }
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(offers)} offers to {DATA_PATH}")
    if errors:
        print(f"{len(errors)} provider(s) failed; see data/offers.json", file=sys.stderr)
    return 0 if offers else 1


if __name__ == "__main__":
    raise SystemExit(main())
