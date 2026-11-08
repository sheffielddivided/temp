#!/usr/bin/env python3
"""Henter og parser Baker Hughes Worldwide Rig Count.

Bruk:
  python scripts/rigcount.py fetch          # last ned nyeste Worldwide-fil til raw/ (hvis ny)
  python scripts/rigcount.py ingest FIL     # legg inn en manuelt nedlastet fil i raw/
  python scripts/rigcount.py build          # parse nyeste fil i raw/ -> data/ og site/data/

Kilden (rigcount.bakerhughes.com) ligger bak Akamai og blokkerer ofte
datasenter-IP-er (inkl. GitHub Actions). Derfor: hvis `fetch` får 403,
avslutter den uten feil og `build` bruker siste fil som ligger i raw/.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
DATA = ROOT / "data"
SITE_DATA = ROOT / "site" / "data"

PAGE_URL = "https://rigcount.bakerhughes.com/intl-rig-count"
LINK_PATTERN = re.compile(r"worldwide", re.I)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

MONTHS = {
    m: i + 1
    for i, names in enumerate(
        [
            ("jan", "january"), ("feb", "february"), ("mar", "march"),
            ("apr", "april"), ("may",), ("jun", "june"), ("jul", "july"),
            ("aug", "august"), ("sep", "sept", "september"),
            ("oct", "october"), ("nov", "november"), ("dec", "december"),
        ]
    )
    for m in names
}

# Kanoniske regionnavn og variantene vi gjenkjenner i filene.
REGIONS = {
    "Latin America": ["latin america", "south america"],
    "Europe": ["europe"],
    "Africa": ["africa"],
    "Middle East": ["middle east"],
    "Asia Pacific": ["asia pacific", "asia-pacific", "far east", "asia"],
    "Canada": ["canada"],
    "United States": ["united states", "u.s.", "us", "usa"],
}
TOTAL_LABELS = ["total world", "worldwide", "world total", "total worldwide", "grand total"]
INTL_LABELS = ["total international", "international total", "international"]
SECTIONS = {"land": "Land", "offshore": "Offshore", "total": "Total", "onshore": "Land"}


# ---------------------------------------------------------------- fetch

def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def find_worldwide_link(page: str, base: str) -> str | None:
    for href, text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.I | re.S):
        label = html.unescape(re.sub(r"<[^>]+>", " ", text))
        if LINK_PATTERN.search(label) or LINK_PATTERN.search(href):
            if re.search(r"static-files|\.xlsx?($|\?)", href, re.I):
                return urllib.parse.urljoin(base, html.unescape(href))
    return None


def cmd_fetch() -> int:
    try:
        page = _get(PAGE_URL).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        print(f"::warning::Klarte ikke hente {PAGE_URL}: HTTP {e.code}. "
              "Bruker eksisterende fil i raw/ (legg inn manuelt med `ingest`).")
        return 0
    except urllib.error.URLError as e:
        print(f"::warning::Nettverksfeil mot {PAGE_URL}: {e.reason}")
        return 0
    url = find_worldwide_link(page, PAGE_URL)
    if not url:
        print("::error::Fant ingen Worldwide-lenke på siden – sidestrukturen har trolig endret seg.")
        return 1
    print(f"Laster ned {url}")
    blob = _get(url)
    return _store(blob, source=url)


def cmd_ingest(path: str) -> int:
    return _store(Path(path).read_bytes(), source=f"manual:{Path(path).name}")


def _store(blob: bytes, source: str) -> int:
    if not blob.startswith(b"PK"):
        print("::error::Nedlastet innhold er ikke en xlsx-fil.")
        return 1
    digest = hashlib.sha256(blob).hexdigest()
    RAW.mkdir(exist_ok=True)
    for f in RAW.glob("*.xlsx"):
        if hashlib.sha256(f.read_bytes()).hexdigest() == digest:
            print(f"Ingen endring (samme innhold som {f.name}).")
            return 0
    name = f"{dt.date.today().isoformat()}_worldwide.xlsx"
    (RAW / name).write_bytes(blob)
    (RAW / (name + ".source.txt")).write_text(source + "\n")
    print(f"Lagret raw/{name}")
    return 0


# ---------------------------------------------------------------- parse

def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def _region_of(label: str) -> str | None:
    key = re.sub(r"^total\s+|\s+total$", "", label.lower()).strip(" :")
    for canon, variants in REGIONS.items():
        if key in variants:
            return canon
    return None


def _is_any(label: str, options) -> bool:
    return label.lower().strip(" :") in options


def _month_of(cell) -> tuple[int | None, int | None]:
    """(måned, år) fra en headercelle – datetime, 'Jan', 'Jan 2024', 'Jan-24' osv."""
    if isinstance(cell, (dt.datetime, dt.date)):
        return cell.month, cell.year
    if not isinstance(cell, str):
        return None, None
    m = re.fullmatch(r"([A-Za-z]+)\.?(?:[\s\-/']+(\d{2,4}))?", cell.strip())
    if not m or m.group(1).lower() not in MONTHS:
        return None, None
    year = m.group(2)
    if year:
        year = int(year)
        year += 2000 if year < 100 and year < 50 else (1900 if year < 100 else 0)
    return MONTHS[m.group(1).lower()], year


def _year_hint(*texts) -> int | None:
    for t in texts:
        if t is None:
            continue
        m = re.search(r"\b(19[5-9]\d|20\d\d)\b", str(t))
        if m:
            return int(m.group(1))
    return None


def parse_workbook(path: Path) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out: list[dict] = []
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        out.extend(_parse_sheet(ws.title, rows))
    wb.close()
    return out


def _parse_sheet(title: str, rows: list[list]) -> list[dict]:
    records: list[dict] = []
    header = None  # {col: (month, year)}
    section = "Total"
    region = None
    pending: list[dict] = []  # land uten region (hvis regionsummen kommer etter landene)
    context_text: list[str] = [title]

    for r in rows:
        cells = [c for c in r]
        months = {i: _month_of(c) for i, c in enumerate(cells)}
        months = {i: v for i, v in months.items() if v[0]}
        if len(months) >= 6:
            year = _year_hint(*[c for c in cells if not _month_of(c)[0]], *reversed(context_text))
            header = {i: (m, y or year) for i, (m, y) in months.items()}
            if any(y is None for _, y in header.values()):
                header = None  # kan ikke tidfeste – hopp over blokken
            region, pending = None, []
            continue
        strings = [_norm(c) for c in cells if isinstance(c, str) and _norm(c)]
        if strings:
            context_text.append(" ".join(strings))
        if not header:
            sec = next((SECTIONS[s.lower()] for s in strings if s.lower() in SECTIONS), None)
            if sec:
                section = sec
            continue

        first_month_col = min(header)
        label = next((_norm(c) for c in cells[:first_month_col] if isinstance(c, str) and _norm(c)), None)
        values = {
            header[i]: cells[i]
            for i in header
            if i < len(cells) and isinstance(cells[i], (int, float)) and not isinstance(cells[i], bool)
        }
        if not label:
            continue
        low = label.lower().strip(" :")
        if not values:
            if low in SECTIONS:
                section = SECTIONS[low]
            elif (reg := _region_of(label)):
                region, pending = reg, []
            continue

        reg = _region_of(label)
        if _is_any(label, TOTAL_LABELS):
            level, name, rgn = "world", "World", None
        elif _is_any(label, INTL_LABELS):
            level, name, rgn = "international", "International", None
        elif reg:
            level, name, rgn = "region", reg, reg
            if region != reg:
                for p in pending:
                    p["region"] = reg
            region, pending = None, []
        elif low.startswith("total") or low in ("avg", "average"):
            continue
        else:
            level, name, rgn = "country", label, region

        for (m, y), v in values.items():
            rec = dict(date=f"{y:04d}-{m:02d}", section=section, level=level,
                       region=rgn or "", name=name, rigs=float(v), sheet=title)
            records.append(rec)
            if level == "country" and not region:
                pending.append(rec)
    return records


def tidy(records: list[dict]) -> list[dict]:
    """Dedupliser (siste forekomst vinner) og sorter."""
    best: dict[tuple, dict] = {}
    for r in records:
        best[(r["date"], r["section"], r["level"], r["region"], r["name"])] = r
    rows = sorted(best.values(), key=lambda r: (r["section"], r["level"], r["region"], r["name"], r["date"]))
    # US/Canada kan ligge både som land og region – behold dem som region.
    return [r for r in rows if not (r["level"] == "country" and _region_of(r["name"]) in ("United States", "Canada"))]


def to_site_json(rows: list[dict], meta: dict) -> dict:
    sections: dict[str, dict] = {}
    for r in rows:
        s = sections.setdefault(r["section"], {"region": {}, "country": {}, "world": {}, "international": {}})
        key = r["name"] if r["level"] != "country" else f'{r["region"]}|{r["name"]}'
        s[r["level"]].setdefault(key, {})[r["date"]] = r["rigs"]

    result = {"meta": meta, "sections": {}}
    for name, s in sections.items():
        dates = sorted({d for lvl in s.values() for series in lvl.values() for d in series})
        def arr(series):
            return [series.get(d) for d in dates]
        regions = {k: arr(v) for k, v in s["region"].items()}
        world = arr(s["world"]["World"]) if "World" in s["world"] else None
        if world is None and regions:
            world = [sum(v[i] for v in regions.values() if v[i] is not None) if any(v[i] is not None for v in regions.values()) else None for i in range(len(dates))]
        countries = []
        for k, v in s["country"].items():
            rgn, cname = k.split("|", 1)
            countries.append({"name": cname, "region": rgn, "values": arr(v)})
        result["sections"][name] = {"dates": dates, "world": world, "regions": regions, "countries": countries}
    return result


def cmd_build() -> int:
    files = sorted(RAW.glob("*.xlsx"))
    if not files:
        print("::error::Ingen filer i raw/. Kjør `fetch` eller `ingest FIL` først.")
        return 1
    src = files[-1]
    print(f"Parser {src.name}")
    rows = tidy(parse_workbook(src))
    if not rows:
        print("::error::Fant ingen data i filen – layouten gjenkjennes ikke. Juster _parse_sheet().")
        return 1

    DATA.mkdir(exist_ok=True)
    with (DATA / "worldwide_long.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "section", "level", "region", "name", "rigs", "sheet"])
        w.writeheader()
        w.writerows(rows)

    srcnote = src.with_name(src.name + ".source.txt")
    meta = {
        "file": src.name,
        "source": srcnote.read_text().strip() if srcnote.exists() else "",
        "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "first": min(r["date"] for r in rows),
        "last": max(r["date"] for r in rows),
    }
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "worldwide.json").write_text(json.dumps(to_site_json(rows, meta), separators=(",", ":")))

    by = {}
    for r in rows:
        by.setdefault((r["section"], r["level"]), set()).add(r["name"])
    print(f"{len(rows)} rader, {meta['first']} – {meta['last']}")
    for (s, l), names in sorted(by.items()):
        print(f"  {s:9} {l:13} {len(names):4} serier")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("fetch", "ingest", "build"):
        print(__doc__)
        return 2
    if argv[0] == "fetch":
        return cmd_fetch()
    if argv[0] == "ingest":
        if len(argv) < 2:
            print("Bruk: rigcount.py ingest FIL.xlsx")
            return 2
        return cmd_ingest(argv[1])
    return cmd_build()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
