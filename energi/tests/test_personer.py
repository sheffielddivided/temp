"""Tester for profilkortene (personer.py) – uten nettverk."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch as F  # noqa: E402
import personer as P  # noqa: E402


def _p(pid, navn="Ola Nordmann", parti="H"):
    f, e = navn.split(" ", 1)
    return {"id": pid, "fornavn": f, "etternavn": e, "parti": {"id": parti, "navn": "Høyre"}, "fylke": {"navn": "Oslo"},
            "foedselsdato": "/Date(461282400000+0200)/", "kjoenn": 2}


def test_slug():
    assert P.slug("BÅH") == "B_c5H"
    assert P.slug("MARNIL") == "MARNIL"


def test_index():
    saker = [("2026-2027", {"id": 1, "korttittel": "Havvind", "henvisning": "Dok 8:1", "status": 2, "komite": {"navn": "E"},
                            "forslagstiller_liste": [_p("A")], "saksordfoerer_liste": [_p("B", "Kari Nordmann")],
                            "sist_oppdatert_dato": "/Date(1793793429330+0100)/"}),
             ("2025-2026", {"id": 1, "korttittel": "duplikat"})]
    spm = [("2026-2027", {"id": 9, "type": 5, "tittel": "Nettleie?", "sporsmal_fra": _p("A"), "datert_dato": "/Date(1793793429330+0100)/",
                          "sporsmal_til_minister_tittel": "energiministeren", "besvart_dato": None})]
    akt, base = P.build_index(saker, spm, {1}, {9}, F.msdate, F.clean)
    assert akt["A"]["saker"][0]["r"] == "forslag" and akt["A"]["saker"][0]["e"] is True
    assert akt["B"]["saker"][0]["r"] == "ordforer"
    assert akt["A"]["sporsmal"][0] == {"id": 9, "ty": "skriftlig", "t": "Nettleie?", "d": "2026-11-04", "til": "energiministeren",
                                       "b": False, "e": True, "s": "2026-2027"}
    assert base["B"]["navn"] == "Kari Nordmann" and base["A"]["parti"] == "H"


def test_biografi():
    d = {"personalia_kodet": {"ansiennitet_aar": 5, "ansiennitet_dager": 1},
         "stortingsperiode_kodet_liste": [{"stortingsperiode_id": "2025-2029", "fylke": "Oslo", "parti_id": "H", "verv": "Representant"}],
         "stortingsverv_kodet_liste": [{"stortingsperiode_id": "2025-2029", "komite_type": "FAG", "komite_navn": "Energi- og miljøkomiteen", "verv": "Medlem"}],
         "utdanning_yrke_kodet_liste": [{"type": "10", "navn": "Cand.jur.", "fra_aar": 2000, "til_aar": 2005},
                                        {"type": "20", "navn": "Advokat", "fra_aar": 2006, "til_aar_ukjent": True, "til_aar": 0}],
         "verv_kodet_liste": [{"organisasjon": "Bystyre", "sted": "Oslo", "verv": "Medlem", "fra_aar": 2011, "til_aar": 2015}]}
    b = P.parse_biografi(d, F.msdate)
    assert b["utdanning"][0]["navn"] == "Cand.jur." and b["yrke"][0]["til"] is None
    assert b["stortingsverv"][0]["type"] == "Fagkomité" and b["ansiennitet"]["aar"] == 5
    assert b["verv"][0]["organisasjon"] == "Bystyre"
