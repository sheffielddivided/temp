"""Sanity-sjekker av den sammenslåtte ukehistorikken (history/)."""
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import na  # noqa: E402

HIST = ROOT / "history" / "na_weekly.csv"
SRC = ROOT / "history" / "na_sources.json"


@pytest.mark.skipif(not HIST.exists(), reason="ingen historikk ennå")
def test_history_is_continuous_and_sourced():
    weeks = na.load_history(HIST)
    dates = sorted(weeks)
    sources = json.loads(SRC.read_text())
    assert set(dates) == set(sources), "hver uke må ha kilde i na_sources.json"
    gaps = [(a, b) for a, b in zip(dates, dates[1:])
            if not 5 <= (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days <= 11]  # helligdager flytter publisering
    assert not gaps, f"hull i ukeserien: {gaps[:5]}"
    for d in dates[-5:]:
        us = sum(v for k, v in weeks[d].items() if k[0] == "United States")
        assert 100 < us < 3000, (d, us)


def test_ingest_newer_wins_and_older_is_skipped(tmp_path, monkeypatch):
    def fake(rows_by_file):
        monkeypatch.setattr(na, "parse_file", lambda f: rows_by_file[f.name])
    mk = lambda d, v: dict(date=d, country="United States", state="Texas", basin="Permian", gom="No",
                           drill_for="Oil", location="Land", trajectory="Horizontal", rigs=v)
    hist, src = tmp_path / "h.csv", tmp_path / "s.json"
    fake({"a.xlsx": [mk("2024-01-05", 10), mk("2024-01-12", 11)],
          "b.xlsx": [mk("2024-01-12", 12), mk("2024-01-19", 13)],
          "old.xlsx": [mk("2024-01-05", 99)]})  # eldre rapport: slutter før de andre
    na.ingest([tmp_path / "a.xlsx"], hist, src)
    na.ingest([tmp_path / "b.xlsx"], hist, src)
    log = na.ingest([tmp_path / "old.xlsx"], hist, src)
    w = na.load_history(hist)
    got = {d: sum(v.values()) for d, v in w.items()}
    assert got == {"2024-01-05": 10, "2024-01-12": 12, "2024-01-19": 13}
    assert "1 hoppet over" in log[0]
