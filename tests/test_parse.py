"""Tester parseren mot syntetiske arbeidsbøker i to sannsynlige layouter.

Kjør: python -m pytest tests  (eller: python tests/test_parse.py)
NB: Ekte Baker Hughes-filer kan se annerledes ut – legg gjerne til en test
med en ekte fil i raw/ når den foreligger.
"""
import datetime as dt
import sys
import tempfile
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import rigcount  # noqa: E402

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def layout_a(ws, year):
    """Én fane per år, seksjonsoverskrift, regionoverskrift før land, total etter."""
    ws.append([f"Worldwide Rig Count {year}"])
    ws.append([])
    ws.append(["LAND"])
    ws.append(["", *MON, "Avg"])
    ws.append(["Latin America"])
    ws.append(["Argentina", *[50 + i for i in range(12)], 55.5])
    ws.append(["Brazil", *[10] * 12, 10])
    ws.append(["Total Latin America", *[60 + i for i in range(12)], 65.5])
    ws.append(["Europe"])
    ws.append(["Norway", *[15] * 12, 15])
    ws.append(["Total Europe", *[15] * 12, 15])
    ws.append(["Canada", *[150] * 12, 150])
    ws.append(["United States", *[600] * 12, 600])
    ws.append(["Total World", *[825 + i for i in range(12)], 830])


def layout_b(ws):
    """Header med datoer, landene før regionsummen uten overskrift."""
    ws.append(["Country", *[dt.datetime(2025, m, 1) for m in range(1, 13)]])
    ws.append(["Algeria", *[30] * 12])
    ws.append(["Nigeria", *[12] * 12])
    ws.append(["Africa", *[42] * 12])
    ws.append(["Saudi Arabia", *[80] * 12])
    ws.append(["Middle East", *[80] * 12])


def _build(fill):
    wb = openpyxl.Workbook()
    fill(wb)
    d = Path(tempfile.mkdtemp())
    p = d / "t.xlsx"
    wb.save(p)
    return rigcount.tidy(rigcount.parse_workbook(p))


def test_layout_a():
    def fill(wb):
        layout_a(wb.active, 2024)
        wb.active.title = "2024"
        layout_a(wb.create_sheet("2023"), 2023)
    rows = _build(fill)
    arg = [r for r in rows if r["name"] == "Argentina" and r["date"] == "2024-03"]
    assert arg and arg[0]["rigs"] == 52 and arg[0]["region"] == "Latin America" and arg[0]["section"] == "Land"
    assert any(r["level"] == "region" and r["name"] == "United States" and r["date"] == "2023-12" for r in rows)
    assert [r for r in rows if r["name"] == "Norway"][0]["region"] == "Europe"
    world = [r for r in rows if r["level"] == "world" and r["date"] == "2024-12"]
    assert world[0]["rigs"] == 836
    assert not any(r["name"].lower() == "avg" for r in rows)
    assert len({r["date"] for r in rows}) == 24


def test_layout_b():
    rows = _build(lambda wb: layout_b(wb.active))
    alg = [r for r in rows if r["name"] == "Algeria"][0]
    assert alg["region"] == "Africa" and alg["date"] == "2025-01"
    assert [r for r in rows if r["name"] == "Saudi Arabia"][0]["region"] == "Middle East"


def test_find_link():
    page = ('<a href="/static-files/abc">North America</a>'
            '<a href="/static-files/1234-uuid">Worldwide Rig Count Oct 2026</a>')
    assert rigcount.find_worldwide_link(page, rigcount.PAGE_URL) == \
        "https://rigcount.bakerhughes.com/static-files/1234-uuid"


if __name__ == "__main__":
    test_layout_a(); test_layout_b(); test_find_link(); print("OK")
