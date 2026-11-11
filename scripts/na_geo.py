"""Koordinater for Baker Hughes' «County»-felt i North America-dataene.

USA: tyngdepunkt per county fra us-atlas@3.0.1 (US Census, 1:10m), lagret i
scripts/us_county_centroids.csv. BH-navn matches på delstat + normalisert navn
(«St.» = «Saint», uten «Parish»/«County», tegnsetting og mellomrom).
Steder som ikke er counties – BOEMs offshore-blokker i Mexicogolfen og
kartblader i Alaska – har manuelle, omtrentlige midtpunkter i US_EXTRA.

Canada: BH bruker egne regioner (f.eks. «Foothills Front», «Northeastern
Alberta»), ikke counties. De har manuelle, omtrentlige punkter i CANADA.

Nye navn i fremtidige rapporter MÅ legges inn her – tests/test_na_geo.py
feiler ellers, så ingen rigger forsvinner stille fra kartet.
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

CENTROIDS = Path(__file__).with_name("us_county_centroids.csv")

# (lat, lon) – omtrentlige midtpunkter.
US_EXTRA: dict[tuple[str, str], tuple[float, float]] = {
    # Mexicogolfen: BOEM OCS-protraksjonsområder og blokker
    ("Louisiana", "Mississippi Canyon"): (28.5, -89.5),
    ("Louisiana", "Green Canyon"): (27.4, -91.0),
    ("Louisiana", "Walker Ridge"): (26.4, -91.0),
    ("Louisiana", "Keathley Canyon"): (26.4, -92.6),
    ("Louisiana", "Main Pass"): (29.6, -88.7),
    ("Louisiana", "Main Pass South and East"): (29.2, -88.4),
    ("Louisiana", "Ship Shoal"): (28.8, -91.0),
    ("Louisiana", "Ship Shoal South"): (28.4, -91.0),
    ("Louisiana", "South Timbalier"): (28.7, -90.4),
    ("Louisiana", "Eugene Island"): (28.9, -91.6),
    ("Louisiana", "Eugene Island South"): (28.3, -91.5),
    ("Louisiana", "Garden Banks"): (27.5, -92.6),
    ("Louisiana", "West Delta"): (29.0, -89.8),
    ("Louisiana", "West Delta South"): (28.6, -89.8),
    ("Louisiana", "Ewing Bank"): (28.2, -90.6),
    ("Louisiana", "Vermilion Offshore"): (28.9, -92.3),
    ("Louisiana", "Vermilion South"): (28.4, -92.3),
    ("Louisiana", "South Marsh Island"): (28.9, -91.9),
    ("Louisiana", "South Marsh Island South"): (28.4, -91.9),
    ("Louisiana", "South Marsh Island North"): (29.3, -91.9),
    ("Louisiana", "Grand Isle"): (28.9, -90.1),
    ("Louisiana", "Grand Isle Offshore"): (28.7, -90.0),
    ("Louisiana", "West Cameron"): (29.3, -93.3),
    ("Louisiana", "West Cameron West"): (29.3, -93.7),
    ("Louisiana", "West Cameron South"): (28.5, -93.3),
    ("Louisiana", "East Cameron"): (29.3, -92.8),
    ("Louisiana", "East Cameron South"): (28.5, -92.8),
    ("Louisiana", "Viosca Knoll"): (29.4, -88.3),
    ("Alabama", "Viosca Knoll"): (29.4, -88.3),
    ("Louisiana", "Bay Marchand"): (29.1, -90.15),
    ("Louisiana", "Breton Sound"): (29.5, -89.4),
    ("Louisiana", "Atwater Valley"): (27.5, -89.5),
    ("Louisiana", "South Pelto"): (28.9, -90.65),
    ("Louisiana", "Sigsbee Escarpment"): (26.3, -93.0),
    ("Louisiana", "South Pass"): (28.8, -89.4),
    ("Texas", "Alaminos Canyon"): (26.5, -94.5),
    ("Texas", "High Island"): (29.4, -94.1),
    ("Texas", "High Island South"): (28.1, -94.0),
    ("Texas", "East Breaks"): (27.5, -94.6),
    ("Texas", "Galveston Offshore"): (28.9, -94.6),
    ("Texas", "Matagorda Island"): (28.3, -96.3),
    ("Texas", "Brazos Offshore"): (28.4, -95.6),
    ("Texas", "Mustang Island"): (27.6, -96.9),
    ("Florida", "De Soto Canyon"): (29.2, -87.3),
    ("Florida", "Lloyd Ridge"): (28.3, -86.7),
    # California offshore
    ("California", "Santa Maria"): (34.9, -120.4),
    # Alaska: USGS-kartblader / Cook Inlet
    ("Alaska", "Beechey Point"): (70.4, -149.0),
    ("Alaska", "Harrison Bay"): (70.5, -151.5),
    ("Alaska", "Sagavanirktok"): (69.5, -148.6),
    ("Alaska", "Umiat"): (69.4, -152.1),
    ("Alaska", "North Slope Offshore"): (70.6, -148.0),
    ("Alaska", "Tyonek"): (61.1, -151.2),
    ("Alaska", "Kenai"): (60.5, -151.1),
}

CANADA: dict[tuple[str, str], tuple[float, float]] = {
    ("Alberta", "Central Alberta"): (52.3, -113.8),
    ("Alberta", "East Central Alberta"): (52.5, -111.0),
    ("Alberta", "Foothills"): (53.6, -117.8),
    ("Alberta", "Foothills Front"): (52.4, -116.0),
    ("Alberta", "Northeastern Alberta"): (56.6, -111.8),
    ("Alberta", "Northwestern Alberta"): (56.6, -118.6),
    ("Alberta", "Southeastern Alberta"): (50.3, -111.0),
    ("Alberta", "Ukjent"): (54.0, -114.5),
    ("British Columbia", "Northern British Columbia"): (56.4, -121.4),
    ("British Columbia", "Southern British Columbia"): (50.5, -121.0),
    ("British Columbia", "Ukjent"): (55.0, -123.0),
    ("Manitoba", "Manitoba"): (49.5, -100.9),
    ("New Brunswick", "New Brunswick"): (46.0, -65.5),
    ("Newfoundland and Labrador", "Newfoundland & Labrador"): (49.0, -57.5),
    ("NL Offshore", "NL Offshore"): (46.7, -48.6),
    ("Nova Scotia", "Nova Scotia"): (44.9, -63.5),
    ("Quebec", "Quebec"): (46.5, -72.0),
    ("Saskatchewan", "Central Saskatchewan"): (52.0, -108.6),
    ("Saskatchewan", "Eastern Saskatchewan"): (49.5, -102.5),
    ("Saskatchewan", "Southwestern Saskatchewan"): (50.0, -108.0),
    ("Saskatchewan", "Ukjent"): (51.5, -106.0),
}


def norm(s: str) -> str:
    s = str(s).upper().replace("&", " AND ")
    s = re.sub(r"\bSAINT\b|\bSTE\b", "ST", s)
    s = re.sub(r"\b(COUNTY|PARISH|BOROUGH|CENSUS AREA|MUNICIPALITY|CITY AND BOROUGH)\b", "", s)
    return re.sub(r"[^A-Z]", "", s)


@lru_cache(maxsize=1)
def _centroids() -> dict[tuple[str, str], tuple[float, float, str, str]]:
    out = {}
    with CENTROIDS.open(newline="") as fh:
        for r in csv.DictReader(fh):
            out[(norm(r["state"]), norm(r["county"]))] = (float(r["lat"]), float(r["lon"]), r["fips"], r["county"])
    return out


def locate(country: str, state: str, county: str) -> dict | None:
    """{'lat', 'lon', 'fips'?, 'name'} for et BH-sted, eller None hvis ukjent."""
    if country == "United States":
        hit = _centroids().get((norm(state), norm(county)))
        if hit:
            return {"lat": hit[0], "lon": hit[1], "fips": hit[2], "name": hit[3]}
        for (st, co), (lat, lon) in US_EXTRA.items():
            if norm(st) == norm(state) and norm(co) == norm(county):
                return {"lat": lat, "lon": lon, "name": co}
        return None
    if country == "Canada":
        for (pr, reg), (lat, lon) in CANADA.items():
            if norm(pr) == norm(state) and norm(reg) == norm(county):
                return {"lat": lat, "lon": lon, "name": reg}
        return None
    return None
