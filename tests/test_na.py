"""Kontrollerer North America-parseren mot BHs egen «NAM Summary» i hver fil i raw-na/.

Summary har «This Week», «Last Week» og «Year Ago» for totaler, US/Canada-
fordeling, de største delstatene og bassengene. Alle må stemme med summen av
detaljradene i «NAM Weekly».
"""
import datetime as dt
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import na  # noqa: E402

FILES = sorted(p for d in ("raw-na", "inbox") if (ROOT / d).exists() for p in (ROOT / d).glob("*")
               if p.suffix.lower() in (".xlsx", ".xlsb"))
SUMMARY_FILES = [p for p in FILES if p.suffix.lower() == ".xlsx"]


def _summary(path):
    """{(seksjon, etikett): (this_week, last_week, year_ago)}"""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out, section = {}, "top"
    for r in wb["NAM Summary"].iter_rows(values_only=True):
        label = r[1] if len(r) > 1 else None
        if not isinstance(label, str):
            continue
        low = label.lower()
        if "u.s. breakout" in low:
            section = "us"; continue
        if "canada breakout" in low:
            section = "ca"; continue
        if "major state" in low:
            section = "state"; continue
        if "major basin" in low:
            section = "basin"; continue
        vals = [r[i] if len(r) > i else None for i in (3, 5, 7)]
        if all(isinstance(v, (int, float)) for v in vals):
            out[(section, label.strip())] = tuple(vals)
    wb.close()
    return out


def _week_dates(rows):
    dates = sorted({r["date"] for r in rows})
    this = dates[-1]
    last = dates[-2]
    target = (dt.date.fromisoformat(this) - dt.timedelta(days=364)).isoformat()
    year_ago = min(dates, key=lambda d: abs((dt.date.fromisoformat(d) - dt.date.fromisoformat(target)).days))
    return this, last, year_ago


@pytest.mark.skipif(not SUMMARY_FILES, reason="ingen .xlsx i raw-na/")
@pytest.mark.parametrize("path", SUMMARY_FILES, ids=lambda p: p.name)
def test_na_matches_summary(path):
    rows = na.parse_workbook(path)
    summary = _summary(path)
    weeks = _week_dates(rows)

    agg = defaultdict(float)
    for r in rows:
        c = r["country"]
        keys = [("country", c)]
        if c == "United States":
            keys += [("top", r["location"]), ("us", r["drill_for"]), ("us", r["trajectory"]),
                     ("state", r["state"]), ("basin", r["basin"])]
            if r["gom"] == "Yes":
                keys.append(("top", "Gulf of Mexico"))
        if c == "Canada":
            keys.append(("ca", r["drill_for"]))
        for k in keys:
            agg[(k, r["date"])] += r["rigs"]

    alias = {("top", "United States"): ("country", "United States"), ("top", "United States Total"): ("country", "United States"),
             ("top", "Canada"): ("country", "Canada")}
    checked = 0
    for (section, label), vals in summary.items():
        key = alias.get((section, label), (section, label))
        if label == "North America":
            got = [agg[(("country", "United States"), w)] + agg[(("country", "Canada"), w)] for w in weeks]
        else:
            got = [agg[(key, w)] for w in weeks]
        # Year Ago kan mangle hvis filen ikke går ett år tilbake.
        for g, v, w in zip(got, vals, ("denne uken", "forrige uke", "i fjor")):
            if w == "i fjor" and weeks[2] == min(r["date"] for r in rows) and g == 0:
                continue
            assert g == pytest.approx(v, abs=0.01), f"{section}/{label} {w}: {g} != {v}"
            checked += 1
    assert checked >= 60, checked


def test_title_and_date():
    assert na._title("NL OFFSHORE") == "NL Offshore"
    assert na._title("NEW MEXICO") == "New Mexico"
    assert na._date(dt.datetime(2026, 11, 6)) == "2026-11-06"
    assert na._date("11/06/2026") == "2026-11-06"


def test_merge_newer_file_wins():
    old = [dict(date="2024-01-05", rigs=1), dict(date="2024-01-12", rigs=2)]
    new = [dict(date="2024-01-12", rigs=3), dict(date="2024-01-19", rigs=4)]
    assert [(r["date"], r["rigs"]) for r in na.merge([new, old])] == [
        ("2024-01-05", 1), ("2024-01-12", 3), ("2024-01-19", 4)]


XLSX = [p for p in FILES if p.suffix.lower() == ".xlsx"]


@pytest.mark.skipif(not XLSX, reason="ingen .xlsx i raw-na/")
@pytest.mark.parametrize("path", XLSX, ids=lambda p: p.name)
def test_gom_rule_holds(path):
    """Den historiske .xlsb-filen mangler GOM; vi utleder den som USA offshore i
    Gulf-delstatene. Denne testen sikrer at regelen gir BHs egne GOM-tall."""
    rows = na.parse_workbook(path)
    gom, rule = defaultdict(float), defaultdict(float)
    for r in rows:
        if r["gom"] == "Yes":
            gom[r["date"]] += r["rigs"]
        if na.is_gulf(r["country"], r["location"], r["state"]):
            rule[r["date"]] += r["rigs"]
    assert {d: v for d, v in gom.items() if v} == {d: v for d, v in rule.items() if v}
