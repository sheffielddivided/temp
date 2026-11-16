"""Tester for energi/fetch.py – kjøres uten nettverk."""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import fetch as F  # noqa: E402

DATA = ROOT / "site" / "data" / "energi.json"


def test_datoer():
    assert F.msdate("/Date(1794816025563+0100)/").startswith("2026-11-16T")
    assert F.msdate("/Date(-62135596800000)/") is None
    assert F.msdate(None) is None
    assert F.dmydate("26.03.2026 00:00:00") == "2026-03-26"
    assert F.dmydate("01.01.0001 00:00:00") is None
    assert F.rssdate("Thu, 19 Nov 2026 08:30:00 +0100") == "2026-11-19T08:30+01:00"
    assert F.rssdate("2026-11-13") == "2026-11-13"


@pytest.mark.parametrize("tekst,tema", [
    ("Representantforslag om strømstøtte til næringslivet", "Strøm og nett"),
    ("raskere og skånsom utbygging av solenergi", "Solenergi"),
    ("helhetlig plan for arealvennlig utbygging av landvind", "Vindkraft"),
    ("Petroleumsskattelovgivningen – teknisk revisjon", "Olje og gass"),
    ("midlertidig stans av økt strømforbruk til datasentre", "Datasentre"),
    ("Vil regjeringen subsidiere havvind i Norge?", "Havvind"),
])
def test_tema_treff(tekst, tema):
    assert tema in F.tema_for(tekst)


@pytest.mark.parametrize("tekst", [
    "Lillestrøm kommune sliter med gjennomgangstrafikk",
    "Mangel på arbeidskraft i helsesektoren",
    "18-årsgrense for porno på internett",
    "ivaretakelse av 2G-nettet",
    "Strømmetjenester og opphavsrett",
    "En kraftig økning i antall saker",
])
def test_tema_ingen_feiltreff(tekst):
    assert not set(F.tema_for(tekst)) & F.ENERGI_TEMA, F.tema_for(tekst)


def _spm(**kw):
    base = {
        "id": 1, "type": 5, "tittel": "Hva gjør statsråden med nettleien?", "emne_liste": [],
        "sporsmal_til_minister_tittel": "energiministeren", "rette_vedkommende_minister_tittel": None,
        "besvart_av_minister_tittel": None, "besvart_pa_vegne_av_minister_tittel": None,
        "sporsmal_fra": {"id": "X", "fornavn": "Ola", "etternavn": "Nordmann", "parti": {"id": "H"}, "fylke": {"navn": "Oslo"}},
        "sporsmal_til": None, "besvart_av": None,
        "datert_dato": "/Date(1793793429330+0100)/", "besvart_dato": None,
    }
    base.update(kw)
    return base


def test_sporsmal_filter():
    q = F.build_spm(_spm(), "2026-2027")
    assert q["energiminister"] and q["status"] == "venter" and q["fra"]["parti"] == "H"
    assert "Skriftlig-sporsmal/?qnid=1" in q["url"]
    # sendt videre til energiministeren
    q = F.build_spm(_spm(sporsmal_til_minister_tittel="finansministeren", rette_vedkommende_minister_tittel="energiministeren", tittel="Om skatt"), "x")
    assert q and q["energiminister"]
    # annen statsråd og ikke energi -> utelates
    assert F.build_spm(_spm(sporsmal_til_minister_tittel="helseministeren", tittel="Om sykehus"), "x") is None
    # annen statsråd, men energitema -> tas med som relatert
    q = F.build_spm(_spm(sporsmal_til_minister_tittel="finansministeren", tittel="Om elavgiften"), "x")
    assert q and not q["energiminister"]


def test_sak_fase():
    x = {"id": 5, "komite": {"id": "ENERGI", "navn": "Energi- og miljøkomiteen"}, "status": 2, "type": 2,
         "dokumentgruppe": 4, "tittel": "Representantforslag om havvind", "korttittel": "Havvind",
         "henvisning": "Dokument 8:1 S", "innstilling_id": -1, "emne_liste": [], "saksordfoerer_liste": [],
         "forslagstiller_liste": [], "sist_oppdatert_dato": "/Date(1793793429330+0100)/"}
    d = {"saksgang": {"saksgang_steg_liste": [{"saksgang_hendelse_liste": [
        {"id": "FREMSATT", "dato": "11.11.2026 00:00:00"}, {"id": "SENDT", "dato": "12.11.2026 00:00:00"},
        {"id": "AVGFRIST", "dato": "03.12.2026 00:00:00"}, {"id": "ORDFORER", "dato": "01.01.0001 00:00:00"}]}]}}
    s = F.build_sak("2026-2027", x, d, set())
    assert s["fase"] == 2 and s["energi"] and "Havvind" in s["tema"]
    assert s["datoer"]["innstillingsfrist"] == "2026-12-03" and s["datoer"]["fremmet"] == "2026-11-11"
    # sak i annen komité uten energiord -> utelates
    y = dict(x, komite={"id": "HELSEOMS"}, tittel="Om sykehus", korttittel="Om sykehus")
    assert F.build_sak("2026-2027", y, {}, set()) is None


def test_parse_rss():
    raw = b"""<?xml version="1.0"?><rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item>
      <guid>tag:stortinget.no,2000:dok15.130280</guid>
      <title>Skriftlig sp\xc3\xb8rsm\xc3\xa5l fra Marius Arion Nilsen (FrP) til energiministeren. Til behandling</title>
      <link>https://www.stortinget.no/x/?qnid=130280&amp;utm_medium=rss</link>
      <description>Magasinfyllingsgraden i NO2</description><dc:date>2026-11-13</dc:date></item></channel></rss>"""
    it = F.parse_rss(raw)[0]
    assert it["link"] == "https://www.stortinget.no/x/?qnid=130280"
    assert it["date"] == "2026-11-13"
    m = F._RSS_TITLE.search(it["title"])
    assert m.group(1) == "Marius Arion Nilsen" and m.group(2) == "FrP"


@pytest.mark.skipif(not DATA.exists(), reason="ingen data generert ennå")
def test_data_og_feed_er_gyldige():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    for k in ("saker", "sporsmal", "horinger", "kalender", "aktivitet", "nyheter", "kilder", "generert", "sesjon"):
        assert k in d
    assert d["saker"] and d["sporsmal"]
    assert all(s["url"].startswith("https://") for s in d["saker"])
    feed = ROOT / "site" / "feed.xml"
    root = ET.parse(feed).getroot()
    assert root.tag == "rss" and root.find("channel/title").text == "Energi på Stortinget"


def test_eksterne_horinger_hjelpere():
    assert F.avsender_fra("Landbruks- og matdepartementet sender med dette NOU 2026:13 på høring") == "Landbruks- og matdepartementet"
    assert F.avsender_fra("Energidepartementet foreslår endringer i energiloven") == "Energidepartementet"
    assert F.avsender_fra("Kommisjonens gjennomføringsforordning") == "Regjeringen"
    assert F._HORING_RE.search("Høring av forslag til endringer i petroleumsforskriften")
    assert F._HORING_RE.search("Høyring – endringar i forskrift")
    assert not F._HORING_RE.search("Prop. 1 S (2026–2027)")
    assert F.PETROLEUM_RE.search("endringer i petroleumsskatteloven")
    assert F.PETROLEUM_RE.search("sikkerhet i havindustrien")
    assert not F.PETROLEUM_RE.search("Kunstig intelligens i høyere utdanning")
    assert "Kjernekraft" in F.tema_for("planer om nytt kjernekraftverk i Helsinki")
    assert "Vannkraft" not in F.tema_for("planer om nytt kjernekraftverk i Helsinki")
