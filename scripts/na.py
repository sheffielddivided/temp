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


def _county(v) -> str:
    s = str(v or "").strip()
    return "Ukjent" if s.lower() in ("", "none", "null") else _title(s)


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
                    "date": date, "country": country, "state": state, "county": _county(g("county")),
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
                "county": _county(g("county")),
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


# ------------------------------------------------------------------ historikk
# history/na_weekly.csv er kilden til sannhet for ukedataene: én rad per uke ×
# land × delstat × basseng × GOM × type × lokasjon × brønnbane (uten county).
# history/na_sources.json sier hvilken rapport hver uke kommer fra, slik at en
# eldre rapport aldri overskriver tall fra en nyere (BH reviderer av og til).

KEYS = FIELDS[:-1]


def _num(v: float):
    return int(v) if float(v).is_integer() else round(v, 3)


# County-historikken er egen (og grovere på de andre dimensjonene) for å holde
# filene små: én rad per uke × land × delstat/provins × county × basseng.
COUNTY_FIELDS = ["date", "country", "state", "county", "basin", "rigs"]


def load_history(history: Path, fields: list[str] = FIELDS) -> dict[str, dict[tuple, float]]:
    weeks: dict[str, dict[tuple, float]] = defaultdict(dict)
    if history.exists():
        with history.open(newline="") as fh:
            for r in csv.DictReader(fh):
                weeks[r["date"]][tuple(r[k] for k in fields[1:-1])] = float(r["rigs"])
    return weeks


def save_history(history: Path, weeks: dict[str, dict[tuple, float]], fields: list[str] = FIELDS) -> None:
    history.parent.mkdir(exist_ok=True)
    tmp = history.with_suffix(".tmp")
    with tmp.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(fields)
        for d in sorted(weeks):
            for k in sorted(weeks[d]):
                w.writerow([d, *k, _num(weeks[d][k])])
    tmp.replace(history)


def ingest(files: list[Path], history: Path, sources_path: Path, county_history: Path | None = None) -> list[str]:
    """Flett rapporter inn i historikken. Returnerer en linje per fil til loggen."""
    weeks = load_history(history)
    cweeks = load_history(county_history, COUNTY_FIELDS) if county_history else None
    sources = json.loads(sources_path.read_text()) if sources_path.exists() else {}
    log = []
    parsed = [(f, parse_file(f)) for f in files]
    for f, rows in sorted(parsed, key=lambda fp: max(r["date"] for r in fp[1])):
        last = max(r["date"] for r in rows)
        agg: dict[str, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
        cagg: dict[str, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))
        for r in rows:
            agg[r["date"]][tuple(r[k] for k in KEYS[1:])] += r["rigs"]
            if cweeks is not None:
                cagg[r["date"]][tuple(r.get(k, "Ukjent") for k in COUNTY_FIELDS[1:-1])] += r["rigs"]
        new = upd = skip = 0
        for d, data in agg.items():
            prev = sources.get(d)
            if prev and prev["report_last"] > last:
                skip += 1
                continue
            if d not in weeks:
                new += 1
            elif weeks[d] != dict(data):
                upd += 1
            weeks[d] = dict(data)
            if cweeks is not None:
                cweeks[d] = {k: v for k, v in cagg[d].items() if v}
            sources[d] = {"report_last": last, "file": f.name}
        log.append(f"{f.name}: {len(agg)} uker ({min(agg)} – {last}); {new} nye, {upd} reviderte, "
                   f"{skip} hoppet over (nyere rapport finnes)")
    save_history(history, weeks)
    if cweeks is not None:
        save_history(county_history, cweeks, COUNTY_FIELDS)
    # Én linje per uke, så diffene i git blir små og lesbare.
    lines = [f"  {json.dumps(d)}: {json.dumps(sources[d], ensure_ascii=False)}" for d in sorted(sources)]
    sources_path.write_text("{\n" + ",\n".join(lines) + "\n}\n")
    return log


def build(history: Path, sources_path: Path, site_data: Path) -> None:
    weeks = load_history(history)
    if not weeks:
        print("Ingen ukesdata i history/ – hopper over.")
        return
    rows = [dict(zip(KEYS, (d, *k)), rigs=v) for d in sorted(weeks) for k, v in weeks[d].items()]
    sources = json.loads(sources_path.read_text()) if sources_path.exists() else {}
    files = sorted({s["file"] for s in sources.values()})
    latest = sources[max(sources)]["file"] if sources else ""
    meta = {"files": files, "latest_file": latest, "first": rows[0]["date"], "last": rows[-1]["date"]}
    site_data.mkdir(parents=True, exist_ok=True)
    (site_data / "na.json").write_text(json.dumps(to_site_json(rows, meta), separators=(",", ":")))
    last = [r for r in rows if r["date"] == meta["last"]]
    us = sum(r["rigs"] for r in last if r["country"] == "United States")
    ca = sum(r["rigs"] for r in last if r["country"] == "Canada")
    print(f"North America: {len(rows)} rader, {meta['first']} – {meta['last']} "
          f"({len(weeks)} uker). Siste uke: USA {us:g}, Canada {ca:g}")


# ------------------------------------------------------------------ detaljkart
def build_map(county_history: Path, sources_path: Path, site_data: Path) -> list[str]:
    """site/data/na_map.json: rigger per county (USA) / BH-region (Canada) per uke.

    Hver plass har en «v»-liste med (indeksdelta, rigger)-par for uker med rigger,
    så filen holder seg liten selv med 800+ uker. Returnerer ukjente steder.
    """
    import na_geo

    weeks = load_history(county_history, COUNTY_FIELDS)
    if not weeks:
        print("Ingen county-historikk – hopper over detaljkart.")
        return []
    dates = sorted(weeks)
    idx = {d: i for i, d in enumerate(dates)}
    series: dict[tuple, dict[int, float]] = defaultdict(dict)
    basins: dict[tuple, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for d, data in weeks.items():
        for (country, state, county, basin), v in data.items():
            key = (country, state, county)
            series[key][idx[d]] = series[key].get(idx[d], 0) + v
            basins[key][basin] += v
    out = {"dates": dates, "countries": {}}
    missing = []
    for key in sorted(series):
        country, state, county = key
        loc = na_geo.locate(country, state, county)
        if not loc:
            missing.append(f"{country} / {state} / {county}")
            continue
        pairs, prev = [], -1
        for i in sorted(series[key]):
            pairs += [i - prev, _num(series[key][i])]
            prev = i
        b = basins[key]
        main_basin = max(b, key=b.get)
        c = out["countries"].setdefault(country, [])
        place = {"n": loc.get("name", county) if loc.get("fips") else county, "s": state, "b": main_basin,
                 "x": round(loc["lon"], 3), "y": round(loc["lat"], 3), "v": pairs}
        if loc.get("fips"):
            place["f"] = loc["fips"]  # kobler stedet til county-polygonet på kartet
        c.append(place)
    sources = json.loads(sources_path.read_text()) if sources_path.exists() else {}
    out["meta"] = {"first": dates[0], "last": dates[-1], "latest_file": sources[max(sources)]["file"] if sources else ""}
    site_data.mkdir(parents=True, exist_ok=True)
    (site_data / "na_map.json").write_text(json.dumps(out, separators=(",", ":")))
    for m in missing:
        print(f"::warning::Mangler koordinater for {m} i scripts/na_geo.py – vises ikke på detaljkartet.")
    n = {c: len(v) for c, v in out["countries"].items()}
    print(f"Detaljkart: {n} steder, {len(dates)} uker.")
    return missing
