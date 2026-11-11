#!/usr/bin/env python3
"""Henter og parser Baker Hughes Worldwide Rig Count.

Bruk:
  python scripts/rigcount.py fetch          # last ned nyeste Worldwide-fil til raw/ (hvis ny)
  python scripts/rigcount.py ingest FIL     # legg inn en manuelt nedlastet fil i raw/
  python scripts/rigcount.py build          # slå sammen alle filer i raw/ -> data/ og site/data/

Hver månedsfil fra Baker Hughes dekker bare ca. de siste 34 månedene
(fanen «WW Monthly»). `build` slår derfor sammen ALLE filer i raw/; for
måneder som finnes i flere filer vinner den nyeste filen (den med senest
måned i innholdet). Ta vare på filene – de er historikken.

Kilden (rigcount.bakerhughes.com) ligger bak Akamai og blokkerer
datasenter-IP-er (inkl. GitHub Actions). Hvis `fetch` får 403 avslutter
den uten feil, og `build` bruker filene som allerede ligger i raw/.
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
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
DATA = ROOT / "data"
SITE_DATA = ROOT / "site" / "data"
NA_HISTORY = ROOT / "history" / "na_weekly.csv"
NA_SOURCES = ROOT / "history" / "na_sources.json"
NA_COUNTY = ROOT / "history" / "na_county_weekly.csv"

PAGE_URL = "https://rigcount.bakerhughes.com/intl-rig-count"
LINK_PATTERN = re.compile(r"worldwide", re.I)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

SHEET = "WW Monthly"
# Kolonnene i detaljtabellen (overskriftsraden, ca. rad 12 i «WW Monthly»).
COLUMNS = {
    "region": "region",
    "country": "country",
    "drillfor": "drill_for",
    "location": "location",
    "rig status": "status",
    "year": "year",
    "month": "month",
    "rig count value": "rigs",
}
# «Rig Status» finnes ikke i eldre filer (f.eks. juli 2025).
OPTIONAL = {"rig status"}
FIELDS = ["date", "region", "country", "drill_for", "location", "status", "rigs", "file"]

REGION_NAMES = {"asia-pacific": "Asia Pacific"}
LOCATION_NAMES = {"inland waters": "Inland Waters", "land": "Land", "offshore": "Offshore"}
SMALL_WORDS = {"of", "the", "and", "da", "de", "du"}
ACRONYMS = {"uae": "UAE", "usa": "USA", "uk": "UK", "us": "US"}


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
              "Bruker filene som ligger i raw/ (legg inn nye manuelt).")
        return 0
    except urllib.error.URLError as e:
        print(f"::warning::Nettverksfeil mot {PAGE_URL}: {e.reason}")
        return 0
    url = find_worldwide_link(page, PAGE_URL)
    if not url:
        print("::error::Fant ingen Worldwide-lenke på siden – sidestrukturen har trolig endret seg.")
        return 1
    print(f"Laster ned {url}")
    return _store(_get(url), source=url)


def cmd_ingest(path: str) -> int:
    return _store(Path(path).read_bytes(), source=f"manual:{Path(path).name}")


def _store(blob: bytes, source: str) -> int:
    if not blob.startswith(b"PK"):
        print("::error::Innholdet er ikke en xlsx-fil.")
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

def _title(s: str) -> str:
    words = re.split(r"(\s+|-|,)", s.strip().lower())
    out = []
    for i, w in enumerate(words):
        out.append(ACRONYMS.get(w) or (w if (i and w in SMALL_WORDS) else w[:1].upper() + w[1:]))
    return "".join(out)


def _key(c) -> str:
    return re.sub(r"\s+", " ", str(c or "")).strip().lower()


def parse_workbook(path: Path) -> list[dict]:
    """Leser detaljtabellen i «WW Monthly». Feiler tydelig hvis layouten er endret."""
    import openpyxl
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if SHEET not in wb.sheetnames:
            raise ValueError(f"{path.name}: fant ikke fanen «{SHEET}» (faner: {wb.sheetnames})")
        cols = None
        out = []
        for r in wb[SHEET].iter_rows(values_only=True):
            if cols is None:
                keys = [_key(c) for c in r]
                if all(k in keys for k in COLUMNS if k not in OPTIONAL):
                    cols = {COLUMNS[k]: keys.index(k) for k in COLUMNS if k in keys}
                continue
            rec = {name: r[i] if i < len(r) else None for name, i in cols.items()}
            rec.setdefault("status", None)
            if rec["region"] is None and rec["country"] is None:
                continue
            if not isinstance(rec["year"], int) or not isinstance(rec["month"], int):
                raise ValueError(f"{path.name}: uventet år/måned i rad {r[:8]}")
            v = rec["rigs"]
            out.append({
                "date": f'{rec["year"]:04d}-{rec["month"]:02d}',
                "region": REGION_NAMES.get(_key(rec["region"]), str(rec["region"]).strip()),
                "country": _title(str(rec["country"])),
                "drill_for": str(rec["drill_for"] or "").strip(),
                "location": LOCATION_NAMES.get(_key(rec["location"]), str(rec["location"] or "").strip()),
                "status": str(rec["status"] or "Active Rigs").strip(),  # eldre filer mangler kolonnen
                "rigs": round(float(v), 3) if isinstance(v, (int, float)) else 0.0,
                "file": path.name,
            })
        if cols is None:
            raise ValueError(f"{path.name}: fant ikke overskriftsraden {[k for k in COLUMNS if k not in OPTIONAL]} i «{SHEET}»")
        if not out:
            raise ValueError(f"{path.name}: detaljtabellen i «{SHEET}» er tom")
        return out
    finally:
        wb.close()


def merge(files: list[list[dict]]) -> list[dict]:
    """Slå sammen flere filer. For hver måned brukes radene fra filen med senest innhold."""
    ordered = sorted(files, key=lambda rows: max(r["date"] for r in rows))
    by_month: dict[str, list[dict]] = {}
    for rows in ordered:
        months = defaultdict(list)
        for r in rows:
            months[r["date"]].append(r)
        by_month.update(months)  # nyere fil overskriver hele måneden
    return sorted(
        (r for d in sorted(by_month) for r in by_month[d]),
        key=lambda r: (r["date"], r["region"], r["country"], r["drill_for"], r["location"], r["status"]),
    )


# ---------------------------------------------------------------- site-data

def find_breaks(rows: list[dict]) -> list[dict]:
    """Metodebrudd: land der «Rig Status» skifter fra én måned til den neste.

    Eks.: Saudi-Arabia er «Active Rigs» t.o.m. des 2023 i eldre filer, men
    «Operating Rigs» fra jan 2024 i nyere filer (BH revidert bakover) – et
    hopp på ~220 rigger som ikke er reell aktivitet.
    """
    status: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for r in rows:
        status[r["country"]][r["date"]].add(r["status"])
    out = []
    for country, months in status.items():
        prev = None
        for d in sorted(months):
            cur = months[d]
            if prev is not None and cur != prev:
                out.append({"date": d, "country": country,
                            "from": ", ".join(sorted(prev)), "to": ", ".join(sorted(cur))})
            prev = cur
    return sorted(out, key=lambda b: (b["date"], b["country"]))


def chart_region(r: dict) -> str:
    """USA og Canada vises som egne «regioner» i stedet for North America."""
    return r["country"] if r["region"] == "North America" else r["region"]


def to_site_json(rows: list[dict], meta: dict) -> dict:
    dates = sorted({r["date"] for r in rows})
    idx = {d: i for i, d in enumerate(dates)}
    sections = {}
    for sec, keep in (
        ("Total", lambda r: True),
        ("Land", lambda r: r["location"] in ("Land", "Inland Waters")),  # som BHs egen oppsummering
        ("Offshore", lambda r: r["location"] == "Offshore"),
    ):
        regions: dict[str, list] = defaultdict(lambda: [0.0] * len(dates))
        countries: dict[tuple, list] = defaultdict(lambda: [0.0] * len(dates))
        world = [0.0] * len(dates)
        for r in rows:
            if not keep(r):
                continue
            i = idx[r["date"]]
            regions[chart_region(r)][i] += r["rigs"]
            countries[(r["region"], r["country"])][i] += r["rigs"]
            world[i] += r["rigs"]
        rnd = lambda a: [round(v, 2) for v in a]  # noqa: E731
        sections[sec] = {
            "dates": dates,
            "world": rnd(world),
            "regions": {k: rnd(v) for k, v in regions.items()},
            "countries": [{"name": c, "region": reg, "values": rnd(v)}
                          for (reg, c), v in sorted(countries.items())],
        }
    from geo import COORDS
    names = sorted({r["country"] for r in rows})
    missing = [n for n in names if n not in COORDS]
    for n in missing:
        print(f"::warning::Mangler koordinater for «{n}» i scripts/geo.py – vises ikke på kartet.")
    geo = {n: [COORDS[n][1], COORDS[n][0]] for n in names if n in COORDS}  # [lon, lat]
    # Detaljer for USA og Canada (brukes av us.html): fordeling på type og lokasjon.
    detail = {}
    for country in ("United States", "Canada"):
        cr = [r for r in rows if r["country"] == country]
        if not cr:
            continue
        drill: dict[str, list] = defaultdict(lambda: [0.0] * len(dates))
        loc: dict[str, list] = defaultdict(lambda: [0.0] * len(dates))
        total = [0.0] * len(dates)
        for r in cr:
            i = idx[r["date"]]
            drill[r["drill_for"] or "Ukjent"][i] += r["rigs"]
            loc[r["location"] or "Ukjent"][i] += r["rigs"]
            total[i] += r["rigs"]
        rnd = lambda a: [round(v, 2) for v in a]  # noqa: E731
        detail[country] = {"drill_for": {k: rnd(v) for k, v in drill.items()},
                           "location": {k: rnd(v) for k, v in loc.items()},
                           "total": rnd(total)}
    return {"meta": meta, "sections": sections, "geo": geo, "detail": detail, "dates": dates}


def cmd_build() -> int:
    files = sorted(RAW.glob("*.xlsx"))
    if not files:
        print("::error::Ingen filer i raw/. Kjør `fetch` eller `ingest FIL` først.")
        return 1
    parsed = []
    for f in files:
        rows = parse_workbook(f)
        print(f"  {f.name}: {len(rows)} rader, {rows[0]['date']} – {max(r['date'] for r in rows)}")
        parsed.append(rows)
    rows = merge(parsed)

    DATA.mkdir(exist_ok=True)
    with (DATA / "worldwide_long.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    latest = max(files, key=lambda f: max(r["date"] for r in parsed[files.index(f)]))
    meta = {
        "files": [f.name for f in files],
        "latest_file": latest.name,
        "first": rows[0]["date"],
        "last": rows[-1]["date"],
        "breaks": find_breaks(rows),
    }
    for b in meta["breaks"]:
        print(f"::notice::Metodebrudd {b['date']}: {b['country']} går fra «{b['from']}» til «{b['to']}»")
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "worldwide.json").write_text(json.dumps(to_site_json(rows, meta), separators=(",", ":")))

    import na
    na_files = sorted(p for d in (ROOT / "raw-na", ROOT / "inbox") if d.exists()
                      for p in d.glob("*") if p.suffix.lower() in (".xlsx", ".xlsb"))
    if na_files:
        for line in na.ingest(na_files, NA_HISTORY, NA_SOURCES, NA_COUNTY):
            print("  " + line)
    na.build(NA_HISTORY, NA_SOURCES, SITE_DATA)
    na.build_map(NA_COUNTY, NA_SOURCES, SITE_DATA)

    last = [r for r in rows if r["date"] == meta["last"]]
    print(f"Totalt {len(rows)} rader, {meta['first']} – {meta['last']}, "
          f"{len({r['country'] for r in rows})} land. Verden {meta['last']}: "
          f"{sum(r['rigs'] for r in last):.1f}")
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
