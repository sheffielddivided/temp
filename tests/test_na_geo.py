"""Detaljkartet: alle steder må ha koordinater, og county-historikken må
summere til nøyaktig samme tall som hovedhistorikken hver uke."""
import sys
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import na  # noqa: E402
import na_geo  # noqa: E402

COUNTY = ROOT / "history" / "na_county_weekly.csv"
MAIN = ROOT / "history" / "na_weekly.csv"


@pytest.mark.skipif(not COUNTY.exists(), reason="ingen county-historikk")
def test_all_places_have_coordinates():
    weeks = na.load_history(COUNTY, na.COUNTY_FIELDS)
    missing = sorted({(c, s, co) for data in weeks.values() for (c, s, co, _) in data
                      if not na_geo.locate(c, s, co)})
    assert not missing, f"Legg til koordinater i scripts/na_geo.py for: {missing[:20]}"


@pytest.mark.skipif(not (COUNTY.exists() and MAIN.exists()), reason="ingen historikk")
def test_county_history_matches_main_history():
    county = na.load_history(COUNTY, na.COUNTY_FIELDS)
    main = na.load_history(MAIN)
    assert set(county) == set(main), "samme uker i begge historikkfilene"
    for d in main:
        a, b = defaultdict(float), defaultdict(float)
        for k, v in main[d].items():
            a[(k[0], k[1], k[2])] += v          # land, delstat, basseng
        for k, v in county[d].items():
            b[(k[0], k[1], k[3])] += v
        a = {k: v for k, v in a.items() if v}
        assert a == pytest.approx(dict(b)), d


def test_locate_examples():
    assert na_geo.locate("United States", "Texas", "Reeves")["fips"] == "48389"
    assert na_geo.locate("United States", "Louisiana", "De Soto")["fips"] == "22031"
    assert na_geo.locate("United States", "Louisiana", "St. Mary")["fips"] == "22101"
    assert na_geo.locate("United States", "Louisiana", "Green Canyon") is not None
    assert na_geo.locate("Canada", "Alberta", "Foothills Front") is not None
    assert na_geo.locate("Norway", "x", "y") is None
