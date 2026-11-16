"""Tester for operatørenes KU-parsere (ku.py) – uten nettverk."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ku  # noqa: E402


def test_datoer():
    assert ku.norsk_dato("I samråd … til 19. november 2026.") == "2026-11-19"
    assert ku.norsk_dato("ingen dato") is None
    assert ku.dato_fra_filnavn("equinor-utslipp-rystad-energy-20260826.pdf") == "2026-08-26"
    assert ku.dato_fra_filnavn("atlantis-hoeringsbrev-kup-mars-2026.pdf") == "2026-03-01"
    assert ku.dato_fra_filnavn("konsekvensutredning.pdf") is None


def _rsc(components):
    payload = "\n".join("8c:" + json.dumps(["$", "$L81", "x", {"component": c}]) for c in components)
    return f'<script>self.__next_f.push([1,{json.dumps(payload)}])</script>'


def _blocks(t):
    return [{"_type": "block", "children": [{"_type": "span", "text": t}]}]


def test_equinor():
    page = _rsc([
        {"title": _blocks("Atlantis, NCS"), "text": _blocks("Gassfelt i Nordsjøen."), "callToActions": [
            {"label": "Høringsbrev", "file": {"url": "https://cdn/x.pdf", "originalFilename": "atlantis-hoeringsbrev-mars-2026.pdf"}}]},
        {"title": _blocks("Atlantis, NCS"), "callToActions": [  # duplikat i RSC-strømmen
            {"label": "Høringsbrev", "file": {"url": "https://cdn/x.pdf", "originalFilename": "x.pdf"}}]},
        {"title": _blocks("Argentina"), "callToActions": [
            {"label": "3D Seismic, impact assessment", "file": {"url": "https://cdn/y.pdf", "originalFilename": "y.pdf"}}]},
    ])
    ps = ku.parse_equinor(page)
    assert [p["prosjekt"] for p in ps] == ["Atlantis"]
    assert ps[0]["dokumenter"][0]["dato"] == "2026-03-01"
    assert ps[0]["beskrivelse"] == "Gassfelt i Nordsjøen."


def test_varenergi():
    page = """
    <h2>Pågående utredninger og høringer:</h2>
    <section class="publications u-container"><h2 id="vidsyn">Vidsyn</h2>
      <p>Programforslaget legges nå fram til høring.</p><p>Høringsperioden er satt til seks uker, til <strong>19. november 2026.</strong></p>
      <div class="row"><div class="title"><a href="https://v/a.pdf" class="styled-link">Vidsyn &#8211; Høringsbrev</a></div><div class="meta"> 8. oktober 2026 </div></div>
    </section>
    <h2>Gjennomførte utredninger og høringer:</h2>
    <section class="publications u-container"><h2 id="ringhorne">Ringhorne Nord</h2><p>Avsluttet.</p>
      <div class="row"><div class="title"><a href="https://v/b.pdf">KU</a></div><div class="meta">30. juni 2026</div></div>
    </section>"""
    ps = ku.parse_varenergi(page, today="2026-11-16")
    assert [(p["prosjekt"], p["status"], p["frist"]) for p in ps] == [("Vidsyn", "åpen", "2026-11-19"), ("Ringhorne Nord", "avsluttet", None)]
    assert ps[0]["dokumenter"] == [{"tittel": "Vidsyn – Høringsbrev", "url": "https://v/a.pdf", "dato": "2026-10-08"}]
    assert ps[0]["url"].endswith("#vidsyn")


def test_akerbp():
    media = [
        {"date": "2026-08-25T10:00:00", "title": {"rendered": "Atlas &#8211; program for konsekvensutredning"}, "source_url": "https://a/atlas.pdf"},
        {"date": "2026-07-01T10:00:00", "title": {"rendered": "Lunde_KUP_v1"}, "source_url": "https://a/lunde-kup-v1.pdf"},
        {"date": "2026-07-01T10:00:00", "title": {"rendered": "Årsrapport 2025"}, "source_url": "https://a/arsrapport.pdf"},
    ]
    ps = ku.parse_akerbp(media)
    assert sorted(p["prosjekt"] for p in ps) == ["Atlas", "Lunde"]
    assert ku.akerbp_prosjekt("Konsekvensutredning Ve og Tir (oktober 2026) – Følgebrev") == "Ve og Tir"
