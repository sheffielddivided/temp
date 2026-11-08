"""Baker Hughes North America Rig Count (ukentlig) – parsing og site-data.

To filtyper i raw-na/:
- «North America Rig Count Report» (.xlsx): fanen «NAM Weekly», ca. siste 3 år.
- «North American Rotary Rig Count Pivot Table» (.xlsb): fanen «Master Data»,
  historikk fra 2011. Mangler GOM-kolonnen; den utledes som USA offshore i
  Gulf-delstatene (regelen er kontrollert mot .xlsx-filene i tests/test_na.py,
  og de to formatene er identiske i overlappende uker).
Alle filer slås sammen per uke; for uker som finnes i flere filer vinner
filen med senest innhold.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import warnings
from collections import defaultdict
from pathlib import Path

SHEET = "NAM Weekly"
COLUMNS = {
    "country": "country",
    "county": "county",
    "basin": "basin",
    "gom": "gom",
    "drillfor": "drill_for",
    "location": "location",
    "state/province": "state",
    "trajectory": "trajectory",
    "us_publishdate": "date",
    "rig count value": "rigs",
}
# Historisk pivot-fil (.xlsb, fanen «Master Data»)
XLSB_SHEET = "Master Data"
XLSB_COLUMNS = {
    "country": "country", "county": "county", "basin": "basin", "drillfor": "drill_for",
    "location": "location", "trajectory": "trajectory", "rigcount": "rigs",
    "state/province": "state", "publishdate": "date",
}
GULF_STATES = {"Louisiana", "Texas", "Alabama", "Mississippi"}
# CSV-en aggregeres uten county for å holde størrelsen nede (county finnes i rådatafilene).
FIELDS = ["date", "country", "state", "basin", "gom", "drill_for", "location", "trajectory", "rigs"]
LOCATIONS = {"inland waters": "Inland Waters", "land": "Land", "offshore": "Offshore"}
SMALL = {"of", "the", "and"}
ACRONYMS = {"nl": "NL", "bc": "BC", "nwt": "NWT", "gom": "GOM"}


def _key(c) -> str:
    return re.sub(r"\s+", " ", str(c or "")).strip().lower()


def _title(s) -> str:
    words = re.split(r"(\s+|-|/)", str(s or "").strip().lower())
    return "".join(ACRONYMS.get(w) or (w if (i and w in SMALL) else w[:1].upper() + w[1:])
                   for i, w in enumerate(words))


def _date(v) -> str:
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(v))
    if m:
        return m.group(0)
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(v))  # MM/DD/YYYY
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    raise ValueError(f"ukjent datoformat: {v!r}")


def parse_file(path: Path) -> list[dict]:
    return parse_xlsb(path) if path.suffix.lower() == ".xlsb" else parse_workbook(path)


def is_gulf(country: str, location: str, state: str) -> bool:
    return country == "United States" and location == "Offshore" and state in GULF_STATES


def parse_xlsb(path: Path) -> list[dict]:
    from pyxlsb import open_workbook

    out = []
    with open_workbook(str(path)) as wb:
        if XLSB_SHEET not in wb.sheets:
            raise ValueError(f"{path.name}: fant ikke fanen «{XLSB_SHEET}» (faner: {wb.sheets})")
        with wb.get_sheet(XLSB_SHEET) as sh:
            cols = None
            for row in sh.rows():
                v = [c.v for c in row]
                if cols is None:
                    keys = [_key(c) for c in v]
                    if all(k in keys for k in XLSB_COLUMNS):
                        cols = {dst: keys.index(src) for src, dst in XLSB_COLUMNS.items()}
                    continue
                g = lambda name: v[cols[name]] if cols[name] < len(v) else None  # noqa: E731
                if not g("country"):
                    continue
                d = g("date")
                date = (dt.date(1899, 12, 30) + dt.timedelta(days=int(d))).isoformat() if isinstance(d, (int, float)) else _date(d)
                country, state = _title(g("country")), _title(g("state"))
                location = LOCATIONS.get(_key(g("location")), str(g("location") or "").strip())
                rigs = g("rigs")
                out.append({
                    "date": date, "country": country, "state": state,
                    "basin": str(g("basin") or "").strip() or "Other",
                    "gom": "Yes" if is_gulf(country, location, state) else "No",
                    "drill_for": str(g("drill_for") or "").strip(),
                    "location": location,
                    "trajectory": str(g("trajectory") or "").strip() or "Other",
                    "rigs": float(rigs) if isinstance(rigs, (int, float)) else 0.0,
                })
            if cols is None:
                raise ValueError(f"{path.name}: fant ikke overskriftsraden {list(XLSB_COLUMNS)} i «{XLSB_SHEET}»")
    if not out:
        raise ValueError(f"{path.name}: «{XLSB_SHEET}» er tom")
    return out


def parse_workbook(path: Path) -> list[dict]:
    import openpyxl

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if SHEET not in wb.sheetnames:
            raise ValueError(f"{path.name}: fant ikke fanen «{SHEET}» (faner: {wb.sheetnames})")
        cols, out = None, []
        for r in wb[SHEET].iter_rows(values_only=True):
            if cols is None:
                keys = [_key(c) for c in r]
                if all(k in keys for k in COLUMNS):
                    cols = {v: keys.index(k) for k, v in COLUMNS.items()}
                continue
            g = lambda name: r[cols[name]] if cols[name] < len(r) else None  # noqa: E731
            if g("country") is None:
                continue
            v = g("rigs")
            out.append({
                "date": _date(g("date")),
                "country": _title(g("country")),
                "state": _title(g("state")),
                "basin": str(g("basin") or "").strip() or "Other",
                "gom": "Yes" if _key(g("gom")) == "yes" else "No",
                "drill_for": str(g("drill_for") or "").strip(),
                "location": LOCATIONS.get(_key(g("location")), str(g("location") or "").strip()),
                "trajectory": str(g("trajectory") or "").strip() or "Other",
                "rigs": float(v) if isinstance(v, (int, float)) else 0.0,
            })
        if cols is None:
            raise ValueError(f"{path.name}: fant ikke overskriftsraden {list(COLUMNS)} i «{SHEET}»")
        if not out:
            raise ValueError(f"{path.name}: «{SHEET}» er tom")
        return out
    finally:
        wb.close()


def merge(files: list[list[dict]]) -> list[dict]:
    ordered = sorted(files, key=lambda rows: max(r["date"] for r in rows))
    by_week: dict[str, list[dict]] = {}
    for rows in ordered:
        weeks = defaultdict(list)
        for r in rows:
            weeks[r["date"]].append(r)
        by_week.update(weeks)
    return [r for d in sorted(by_week) for r in by_week[d]]


def to_site_json(rows: list[dict], meta: dict) -> dict:
    dates = sorted({r["date"] for r in rows})
    idx = {d: i for i, d in enumerate(dates)}
    out = {"meta": meta, "dates": dates, "countries": {}}
    dims = {"basin": "basins", "state": "states", "drill_for": "drill_for",
            "trajectory": "trajectory", "location": "location"}
    for country in sorted({r["country"] for r in rows}):
        acc = {k: defaultdict(lambda: [0] * len(dates)) for k in dims.values()}
        total = [0] * len(dates)
        gom = [0] * len(dates)
        for r in rows:
            if r["country"] != country:
                continue
            i = idx[r["date"]]
            total[i] += r["rigs"]
            if r["gom"] == "Yes":
                gom[i] += r["rigs"]
            for src, dst in dims.items():
                acc[dst][r[src]][i] += r["rigs"]
        clean = lambda a: [int(v) if float(v).is_integer() else round(v, 2) for v in a]  # noqa: E731
        c = {"total": clean(total)}
        for dst, series in acc.items():
            c[dst] = {k: clean(v) for k, v in sorted(series.items())}
        if any(gom):
            c["gom"] = clean(gom)
        out["countries"][country] = c
    return out


def build(raw_dir: Path, data_dir: Path, site_data: Path) -> None:
    files = sorted(p for p in raw_dir.glob("*") if p.suffix.lower() in (".xlsx", ".xlsb")) if raw_dir.exists() else []
    if not files:
        print("Ingen North America-filer i raw-na/ – hopper over ukesdata.")
        return
    parsed = []
    for f in files:
        rows = parse_file(f)
        print(f"  {f.name}: {len(rows)} rader, {min(r['date'] for r in rows)} – {max(r['date'] for r in rows)}")
        parsed.append(rows)
    rows = merge(parsed)
    agg: dict[tuple, float] = defaultdict(float)
    for r in rows:
        agg[tuple(r[k] for k in FIELDS[:-1])] += r["rigs"]
    data_dir.mkdir(exist_ok=True)
    with (data_dir / "na_weekly_long.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(FIELDS)
        for k, v in agg.items():
            w.writerow([*k, int(v) if float(v).is_integer() else round(v, 3)])
    latest = max(zip(files, parsed), key=lambda fp: max(r["date"] for r in fp[1]))[0]
    meta = {"files": [f.name for f in files], "latest_file": latest.name,
            "first": rows[0]["date"], "last": rows[-1]["date"]}
    site_data.mkdir(parents=True, exist_ok=True)
    (site_data / "na.json").write_text(json.dumps(to_site_json(rows, meta), separators=(",", ":")))
    last = [r for r in rows if r["date"] == meta["last"]]
    us = sum(r["rigs"] for r in last if r["country"] == "United States")
    ca = sum(r["rigs"] for r in last if r["country"] == "Canada")
    print(f"North America: {len(rows)} rader, {meta['first']} – {meta['last']} "
          f"({len({r['date'] for r in rows})} uker). Siste uke: USA {us:g}, Canada {ca:g}")
