"""Tester parseren.

Kjør: python -m pytest -q tests

test_real_files_match_summary sjekker HVER fil i raw/ mot Baker Hughes' egen
oppsummering øverst i «WW Monthly» (regionsummer per måned). Hvis BH endrer
layout eller tallene ikke lenger summerer, feiler workflowen før noe publiseres.
"""
import sys
import tempfile
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import rigcount  # noqa: E402

HEADER = ["Region", "Country", "DrillFor", "Location", "Rig Status", "Year", "Month", "Rig Count Value"]
REAL_FILES = sorted((ROOT / "raw").glob("*.xlsx"))


def _wb(rows, path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "WW Monthly"
    ws.append([None, None, "WORLDWIDE Monthly"])
    for _ in range(9):
        ws.append([])
    ws.append([])
    ws.append(HEADER)
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


def test_parse_synthetic():
    d = Path(tempfile.mkdtemp())
    p = _wb([
        ["Asia-Pacific", "CONGO, THE DEMOCRATIC REPUBLIC OF THE", "Oil", "Inland waters", "Active Rigs", 2026, 3, 2],
        ["Middle East", "SAUDI ARABIA", "Gas", "Land", "Operating Rigs", 2026, 3, 40.5],
    ], d / "a.xlsx")
    rows = rigcount.parse_workbook(p)
    assert rows[0]["region"] == "Asia Pacific"
    assert rows[0]["country"] == "Congo, the Democratic Republic of the"
    assert rigcount._title("UAE - ABU DHABI") == "UAE - Abu Dhabi"
    assert rows[0]["location"] == "Inland Waters" and rows[0]["date"] == "2026-03"
    assert rows[1]["rigs"] == 40.5 and rows[1]["status"] == "Operating Rigs"


def test_missing_header_fails_loudly():
    d = Path(tempfile.mkdtemp())
    wb = openpyxl.Workbook()
    wb.active.title = "WW Monthly"
    wb.active.append(["Region", "Land", "Year"])
    wb.save(d / "bad.xlsx")
    with pytest.raises(ValueError, match="overskriftsraden"):
        rigcount.parse_workbook(d / "bad.xlsx")


def test_merge_newer_file_wins_and_history_kept():
    old = [dict(date="2023-12", region="Europe", country="Norway", drill_for="Oil", location="Offshore", status="Active Rigs", rigs=10, file="old"),
           dict(date="2024-01", region="Europe", country="Norway", drill_for="Oil", location="Offshore", status="Active Rigs", rigs=11, file="old")]
    new = [dict(date="2024-01", region="Europe", country="Norway", drill_for="Oil", location="Offshore", status="Active Rigs", rigs=12, file="new"),
           dict(date="2024-02", region="Europe", country="Norway", drill_for="Oil", location="Offshore", status="Active Rigs", rigs=13, file="new")]
    rows = rigcount.merge([new, old])
    assert [(r["date"], r["rigs"]) for r in rows] == [("2023-12", 10), ("2024-01", 12), ("2024-02", 13)]


def test_find_breaks():
    mk = lambda d, st: dict(date=d, region="Middle East", country="Saudi Arabia", drill_for="Oil",
                            location="Land", status=st, rigs=1, file="x")
    rows = [mk("2023-11", "Active Rigs"), mk("2023-12", "Active Rigs"),
            mk("2024-01", "Operating Rigs"), mk("2024-02", "Operating Rigs")]
    assert rigcount.find_breaks(rows) == [
        {"date": "2024-01", "country": "Saudi Arabia", "from": "Active Rigs", "to": "Operating Rigs"}]


def test_parse_without_status_column():
    d = Path(tempfile.mkdtemp())
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "WW Monthly"
    ws.append(["Region", "Country", "DrillFor", "Location", "Year", "Month", "Rig Count Value"])
    ws.append(["Africa", "ALGERIA", "Gas", "Land", 2013, 1, 16])
    wb.save(d / "old.xlsx")
    rows = rigcount.parse_workbook(d / "old.xlsx")
    assert rows[0]["status"] == "Active Rigs" and rows[0]["date"] == "2013-01"


def test_find_link():
    page = ('<a href="/static-files/abc">North America</a>'
            '<a href="/static-files/1234-uuid">Worldwide Rig Count Oct 2026</a>')
    assert rigcount.find_worldwide_link(page, rigcount.PAGE_URL) == \
        "https://rigcount.bakerhughes.com/static-files/1234-uuid"


def _summary(path):
    """Regionsummene i toppen av «WW Monthly»: {(region, 'YYYY-MM'): verdi}."""
    import datetime as dt
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out, dates = {}, None
    for r in wb["WW Monthly"].iter_rows(max_row=11, values_only=True):
        if "Region" in r:
            i = r.index("Region")
            dates = [(j, c) for j, c in enumerate(r) if isinstance(c, dt.datetime)]
            continue
        if dates and r[i]:
            for j, d in dates:
                if isinstance(r[j], (int, float)) and r[j]:
                    out[(rigcount.REGION_NAMES.get(r[i].lower(), r[i]), f"{d.year:04d}-{d.month:02d}")] = r[j]
    wb.close()
    return out


@pytest.mark.skipif(not REAL_FILES, reason="ingen filer i raw/")
@pytest.mark.parametrize("path", REAL_FILES, ids=lambda p: p.name)
def test_real_files_match_summary(path):
    rows = rigcount.parse_workbook(path)
    summary = _summary(path)
    assert summary, "fant ikke oppsummeringen øverst i WW Monthly"
    totals = {}
    for r in rows:
        for key in (r["region"], "Worldwide", None if r["region"] == "North America" else "International"):
            if key:
                totals[(key, r["date"])] = totals.get((key, r["date"]), 0) + r["rigs"]
    checked = 0
    for k, v in summary.items():
        assert totals.get(k) == pytest.approx(v, abs=0.01), k
        checked += 1
    assert checked >= 40


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
