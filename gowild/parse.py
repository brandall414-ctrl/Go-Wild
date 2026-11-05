"""Turn Frontier's pages into short lists of offer lines that can be compared run to run."""

import html
import re
import xml.etree.ElementTree as ET

# Words that mark a sentence as being about a deal or a pass price.
OFFER_WORDS = re.compile(
    r"(?i)\b(sale|on sale|% ?off|discount(?! den)|limited[- ]time|promo|promotion|introductory|"
    r"lowest|save|savings|deal|special offer|voucher|bonus|renewal price)\b"
)
PRICE = re.compile(r"\$\s?\d[\d,]*(?:\.\d\d)?")
PASS_WORDS = re.compile(r"(?i)\b(go ?wild|pass|unlimited|all[- ]you[- ]can[- ]fly)\b")

# Fees that appear in the FAQ and are not pass prices. Changes to these are noise.
FEE_NOISE = re.compile(
    r"(?i)(\$0\.01|taxes|fees and charges|peak day charge|early booking charge|"
    r"in excess of \$100|per segment)"
)


def visible_text(page: str) -> str:
    """Strip comments, scripts, styles and tags. Frontier leaves old promos inside
    HTML comments, so comments must go before anything else."""
    s = re.sub(r"<!--.*?-->", " ", page, flags=re.S)
    s = re.sub(r"<(head|script|style|noscript|svg|nav|header|footer)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def sentences(text: str) -> list[str]:
    # Split on sentence ends, but not inside prices like $0.01.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z$*])", text)
    return [p.strip() for p in parts if 15 <= len(p.strip()) <= 600]


def _dedupe(lines):
    seen, out = set(), []
    for line in lines:
        if line not in seen:
            seen.add(line)
            out.append(line)
    return out


def deals_offers(page: str) -> list[str]:
    """Offer lines from the GoWild deals page: any sentence with a pass price or
    sale wording, minus the per-flight fee boilerplate."""
    out = []
    for sent in sentences(visible_text(page)):
        has_price = bool(PRICE.search(sent))
        if not (has_price or OFFER_WORDS.search(sent)):
            continue
        if not PASS_WORDS.search(sent):
            continue
        if has_price and FEE_NOISE.search(sent) and not OFFER_WORDS.search(sent):
            continue
        out.append(sent)
    return _dedupe(out)


def terms_prices(page: str) -> list[str]:
    """Annual pass price lines from the Frontier Miles terms page."""
    text = visible_text(page)
    out = []
    for m in re.finditer(r"(?i)[^.]{0,200}annual pass[^.]{0,200}\$\s?\d[\d,]*(?:\.\d\d)?[^.]{0,120}", text):
        line = m.group(0).strip(" ,")
        if "$0.01" in line:
            continue
        out.append(line)
    return _dedupe(out)


def feed_items(xml_text: str) -> list[dict]:
    """GoWild-related posts from the newsroom promotions feed."""
    root = ET.fromstring(xml_text.encode("utf-8"))
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        guid = (it.findtext("guid") or link).strip()
        date = (it.findtext("pubDate") or "").strip()
        if PASS_WORDS.search(title):
            items.append({"id": guid, "title": html.unescape(title), "link": link, "date": date})
    return items
