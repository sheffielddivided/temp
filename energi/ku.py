"""Konsekvensutredninger (KU) og KU-høringer fra operatørene.

Rene parse-funksjoner (uten nettverk) for:
  * Equinor   – https://www.equinor.com/no/baerekraft/konsekvensutredninger
                (Next.js-side; data ligger i den innebygde RSC-strømmen)
  * Vår Energi – https://varenergi.no/no/var-virksomhet/konsekvensutredninger/
                («Pågående» / «Gjennomførte» utredninger, med frister og datoer)
  * Aker BP   – WordPress-API-et (mediebiblioteket har dato per dokument)

Alle returnerer prosjekter på samme form:
  {"operator", "prosjekt", "beskrivelse", "frist", "status", "url",
   "dokumenter": [{"tittel", "url", "dato"}]}
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re

MND = {m: i for i, m in enumerate(
    ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
     "september", "oktober", "november", "desember"], 1)}
_DMY = re.compile(r"(\d{1,2})\.\s*(" + "|".join(MND) + r")\s+(\d{4})", re.I)


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def norsk_dato(s: str | None) -> str | None:
    """'8. oktober 2026' -> '2026-10-08'."""
    m = _DMY.search(s or "")
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), MND[m.group(2).lower()], int(m.group(1))).isoformat()
    except ValueError:
        return None


def dato_fra_filnavn(name: str) -> str | None:
    """Finn en dato i et filnavn: 20260826, 2026-08-26 eller «mars-2026» (-> 1. i mnd)."""
    n = name.lower()
    m = re.search(r"(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)", n)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    m = re.search(r"(" + "|".join(MND) + r")[-_ ](20\d{2})", n)
    if m:
        return dt.date(int(m.group(2)), MND[m.group(1)], 1).isoformat()
    return None


# --------------------------------------------------------------------------
# Equinor
# --------------------------------------------------------------------------
EQUINOR_URL = "https://www.equinor.com/no/baerekraft/konsekvensutredninger"
_KU_ORD = re.compile(r"konsekvensutredning|utredningsprogram|program for|høring|hørings|\bku\b|kup\b|"
                     r"avslutningsplan|ringvirkning|tilleggsutredning|fastsett", re.I)


def _rsc_payload(page: str) -> str:
    chunks = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', page)
    return "".join(json.loads(c) for c in chunks)


def _blocks_text(blocks) -> str:
    if not isinstance(blocks, list):
        return ""
    return " ".join(ch.get("text", "") for b in blocks if isinstance(b, dict) for ch in b.get("children") or [] if isinstance(ch, dict)).strip()


def parse_equinor(page: str) -> list[dict]:
    """Prosjekter på norsk sokkel/land med KU-dokumenter (utenlandske hoppes over)."""
    payload = _rsc_payload(page) or page
    dec = json.JSONDecoder()
    out, seen = [], set()
    for m in re.finditer(r'\{"component":', payload):
        try:
            obj, _ = dec.raw_decode(payload, m.start())
        except ValueError:
            continue
        comp = obj.get("component") or {}
        ctas = comp.get("callToActions") or []
        title = _blocks_text(comp.get("title"))
        if not title or not ctas:
            continue
        docs = []
        for c in ctas:
            f = c.get("file") or {}
            if not f.get("url"):
                continue
            label = _clean(c.get("label") or f.get("title") or f.get("originalFilename"))
            docs.append({"tittel": label, "url": f["url"], "dato": dato_fra_filnavn(f.get("originalFilename") or "")})
        # Norske prosjekter har norske dokumenttitler; utenlandske har «impact assessment» o.l.
        if not docs or not any(_KU_ORD.search(d["tittel"]) for d in docs):
            continue
        navn = re.sub(r"\bCO\s+2\b", "CO2", re.sub(r",\s*(NCS|Norge)$", "", title)).strip()
        navn = re.sub(r"\s+", " ", navn)
        if navn in seen:  # RSC-strømmen inneholder hver komponent to ganger
            continue
        seen.add(navn)
        out.append({
            "operator": "Equinor", "prosjekt": navn,
            "beskrivelse": _blocks_text(comp.get("text"))[:400], "frist": None, "status": None,
            "url": EQUINOR_URL, "dokumenter": docs,
        })
    return out


# --------------------------------------------------------------------------
# Vår Energi
# --------------------------------------------------------------------------
VAREN_URL = "https://varenergi.no/no/var-virksomhet/konsekvensutredninger/"


def parse_varenergi(page: str, today: str | None = None) -> list[dict]:
    today = today or dt.date.today().isoformat()
    out = []
    # Overskriftene «Pågående …» / «Gjennomførte …» skiller seksjonene.
    parts = re.split(r"(<h2[^>]*>\s*(?:Pågående|Gjennomførte)[^<]*</h2>)", page)
    state = None
    for part in parts:
        if re.match(r"<h2[^>]*>\s*Pågående", part):
            state = "pågående"
            continue
        if re.match(r"<h2[^>]*>\s*Gjennomførte", part):
            state = "gjennomført"
            continue
        if not state:
            continue
        for sec in re.findall(r'<section class="publications[^"]*">(.*?)</section>', part, re.S):
            h = re.search(r'<h2(?:[^>]*?\bid="([^"]*)")?[^>]*>(.*?)</h2>', sec, re.S)
            if not h:
                continue
            paras = [_clean(p) for p in re.findall(r"<p>(.*?)</p>", sec, re.S)]
            tekst = " ".join(paras)
            fm = re.search(r"\btil\s+(\d{1,2}\.\s*\w+\s+\d{4})", tekst)
            frist = norsk_dato(fm.group(1)) if fm else None
            docs = []
            for row in re.findall(r'<div class="row">(.*?)<div class="meta">\s*(.*?)\s*</div>', sec, re.S):
                a = re.search(r'<div class="title">\s*<a href="([^"]+)"[^>]*>(.*?)</a>', row[0], re.S)
                if a:
                    docs.append({"tittel": _clean(a.group(2)), "url": html.unescape(a.group(1)), "dato": norsk_dato(row[1])})
            status = "åpen" if state == "pågående" and (not frist or frist >= today) else "avsluttet"
            out.append({
                "operator": "Vår Energi", "prosjekt": _clean(h.group(2)), "beskrivelse": (paras[0] if paras else "")[:400],
                "frist": frist, "status": status,
                "url": VAREN_URL + (f"#{h.group(1)}" if h.group(1) else ""), "dokumenter": docs,
            })
    return out


# --------------------------------------------------------------------------
# Aker BP
# --------------------------------------------------------------------------
AKERBP_API = "https://akerbp.com/wp-json/wp/v2/media"
AKERBP_SOK = ("konsekvensutredning", "utredningsprogram", "kup", "høring")
_AKERBP_STRIP = [
    r"^\d+\.\s*", r"^20\d{6}\s*", r"\(\w+ 20\d\d\)", r"\bfølgebrev\b", r"\bforslag til\b",
    r"\bprogram for\b", r"\bkonsekvensutredning(en|er)?\b", r"\bkup\b", r"\bku\b", r"_v\d+\b", r"\bv\d+$",
    r"\bhøringsuttalelser?\b( til| for)?", r"\boppsummering( av)? høringskommentarer\b( og tilsvar)?",
    r"\bfastsettelse av\b", r"\bfor\b", r"\btil\b", r"\butredning av forbrenningsutslipp som tillegg\b",
    r"\(\d+\)", r"\bfinal\b", r"\.docx?\b", r"\bweb\b",
]


def akerbp_prosjekt(title: str) -> str:
    t = _clean(title).replace("_", " ")
    for rx in _AKERBP_STRIP:
        t = re.sub(rx, " ", t, flags=re.I)
    t = re.sub(r"\s*[–—-]\s*", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" .,–-")
    return t[:1].upper() + t[1:] if t else "Ukjent prosjekt"


def parse_akerbp(media: list[dict]) -> list[dict]:
    by: dict[str, dict] = {}
    for m in media:
        title = _clean((m.get("title") or {}).get("rendered"))
        if not _KU_ORD.search(title + " " + (m.get("source_url") or "")):
            continue
        key = akerbp_prosjekt(title)
        p = by.setdefault(key.lower(), {
            "operator": "Aker BP", "prosjekt": key, "beskrivelse": "", "frist": None, "status": None,
            "url": "https://akerbp.com/var-virksomhet/", "dokumenter": [],
        })
        if m.get("source_url") not in {d["url"] for d in p["dokumenter"]}:
            p["dokumenter"].append({"tittel": title, "url": m.get("source_url"), "dato": (m.get("date") or "")[:10] or None})
    return list(by.values())
