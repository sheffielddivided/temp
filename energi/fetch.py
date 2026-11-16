#!/usr/bin/env python3
"""Henter energisaker fra Stortinget og regjeringen.no.

Skriver
  site/data/energi.json  – alt nettsiden trenger
  site/feed.xml          – RSS med siste aktivitet

Bare standardbiblioteket brukes. Hver kilde feiler «mykt»: går en kilde ned,
beholdes forrige data for den kilden, og feilen vises på siden.

Kjør:  python energi/fetch.py
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
OUT_JSON = SITE / "data" / "energi.json"
OUT_RSS = SITE / "feed.xml"

API = "https://data.stortinget.no/eksport"
ST = "https://www.stortinget.no"
ST_RSS = ST + "/no/Stottemeny/RSS"
REG_RSS = "https://www.regjeringen.no/no/rss/Rss/2581966/"
REG_OWNER = "750"  # Energidepartementet

KOMITE = "ENERGI"
MINISTER = "energiministeren"
TZ = ZoneInfo("Europe/Oslo")
UA = "Mozilla/5.0 (compatible; energi-stortinget/1.0; +https://github.com/)"

SITE_URL = "https://sheffielddivided.github.io/temp/energi/"

# --------------------------------------------------------------------------
# Tema: nøkkelord (regex, små bokstaver). Norske sammensetninger gjør at vi
# matcher på ordstammer, men unngår vanlige feiltreff (kraftig, nettside …).
# --------------------------------------------------------------------------
TEMA: dict[str, str] = {
    "Strøm og nett": r"\bstrøm(?!m)|nettleie|strømnett|kraftnett|nettselskap|transmisjonsnett|"
    r"distribusjonsnett|statnett|elektrisitet|elavgift|elsertifikat|"
    r"kraftpris|kraftmarked|kraftsystem|kraftforsyning|kraftbalanse|kraftsituasjon|"
    r"kraftkrevende|kraftforedl|kraftutveksling|kraftlinje|kraftselskap|kraftproduksjon|"
    r"kraftunderskudd|kraftoverskudd|kraftkabel|utenlandskab|\brme\b|reguleringsmyndigheten for energi|"
    r"anleggsbidrag|nettilknytning|kapasitetskø|magasinfylling|norgespris|"
    r"energiloven|energipris|energiforsyning|energisikkerhet|\bnves?\b",
    "Vindkraft": r"vindkraft|landvind|vindturbin|vindpark|vindmølle",
    "Havvind": r"havvind|offshore vind|utsira nord|sørlige nordsjø",
    "Solenergi": r"solenergi|solkraft|solcelle|solpanel",
    "Vannkraft": r"vannkraft|vasskraft|(?<!kjerne)(?<!atom)kraftverk|vassdragsregulering|konsesjonskraft|"
    r"naturressursskatt|grunnrenteskatt på vann|minstevannføring|småkraft",
    "Olje og gass": r"petroleum|olje- og gass|olje og gass|oljeselskap|oljeutslipp|oljevirksomhet|"
    r"oljeproduksjon|oljefelt|oljeindustri|oljeboring|oljeleting|gasseksport|gassproduksjon|"
    r"gassrørledning|gasskraft|naturgass|gassco|\bsokkel|equinor|\blng\b|"
    r"leteareal|\btfo\b|konsesjonsrunde|elektrifisering av sokkel|havbunnsmineral|mineralvirksomhet på",
    "Hydrogen og CCS": r"hydrogen|ammoniakk|co2-fangst|karbonfangst|\bccs\b|longship|"
    r"northern lights|co2-lagring|fangst og lagring",
    "Kjernekraft": r"kjernekraft|atomkraft|thorium|små modulære reaktor",
    "Energieffektivisering": r"energieffektiv|enøk|varmepumpe|\benova|energisparing|fjernvarme|bioenergi|energimerk",
    "Datasentre": r"datasent",
    "Klima": r"\bklima|utslippskutt|utslippsreduksjon|co2-utslipp|klimakvote|kvotesystem|klimagass|lavutslipp|nullutslipp|co2-avgift|karbonprising",
    "Natur og miljø": r"\bnatur(?!lig)|\bmiljø|\bvern\b|\bverne|forurens|avfall|plast|villrein|"
    r"\bulv|rovvilt|\bskog|\bmyr|biologisk mangfold|friluft",
}
ENERGI_TEMA = {
    "Strøm og nett", "Vindkraft", "Havvind", "Solenergi", "Vannkraft", "Olje og gass",
    "Hydrogen og CCS", "Kjernekraft", "Energieffektivisering", "Datasentre",
}
_TEMA_RE = {k: re.compile(v, re.I) for k, v in TEMA.items()}
ENERGI_EMNER = {"energi", "olje og gass", "elektrisitet", "kraftforsyning", "vassdragsregulering"}

SAK_STATUS = {0: "Ukjent", 1: "Behandlet", 2: "Til behandling", 3: "Varslet", 4: "Trukket", 5: "Bortfalt"}
SAK_TYPE = {1: "Budsjett", 2: "Alminnelig sak", 3: "Lovsak"}
DOKGRUPPE = {
    0: "Annet", 1: "Proposisjon", 2: "Melding", 3: "Redegjørelse", 4: "Representantforslag",
    5: "Grunnlovsforslag", 6: "Dokumentserien", 7: "Innstilling", 8: "Innberetning",
}
HENDELSE = {
    "FREMMET": "Fremmet", "FREMSATT": "Fremsatt", "REFS": "Referert i Stortinget",
    "SENDT": "Sendt til komiteen", "HOERFRIST": "Frist for å melde seg til høring",
    "HOER": "Høring", "AVGFRIST": "Frist for innstilling", "AVGITT": "Innstilling avgitt",
    "PLBEHS": "Planlagt behandlet", "BEHS": "Behandlet i Stortinget", "VOT": "Votering",
    "VEDTAK": "Vedtak",
}
SPM_TYPE = {5: "skriftlig", 1: "sporretime", 2: "muntlig", 6: "interpellasjon"}
SPM_URL = {
    "skriftlig": "/no/Saker-og-publikasjoner/Sporsmal/Skriftlige-sporsmal-og-svar/Skriftlig-sporsmal/?qnid={}",
    "sporretime": "/no/Saker-og-publikasjoner/Sporsmal/Sporretimesporsmal/et-sporretimesporsmal/?qnid={}",
    "muntlig": "/no/Saker-og-publikasjoner/Sporsmal/Sporretimesporsmal/et-sporretimesporsmal/?qnid={}",
    "interpellasjon": "/no/Saker-og-publikasjoner/Sporsmal/Interpellasjoner/Interpellasjon/?qnid={}",
}


# --------------------------------------------------------------------------
# Hjelpere
# --------------------------------------------------------------------------
_throttle_lock = threading.Lock()
_last_call: dict[str, float] = {}
MIN_INTERVAL = 0.35  # sekunder mellom kall til samme vert (Stortinget gir 429 ellers)


def _throttle(url: str) -> None:
    host = urllib.parse.urlsplit(url).netloc
    with _throttle_lock:
        wait = _last_call.get(host, 0) + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.monotonic()


def get(url: str, *, retries: int = 5, timeout: int = 40) -> bytes:
    last: Exception | None = None
    for i in range(retries):
        _throttle(url)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                break
            ra = e.headers.get("Retry-After") if e.headers else None
            delay = float(ra) if ra and ra.isdigit() else 5 * 2 ** i  # 5, 10, 20, 40 s
            print(f"  … {e.code} fra {urllib.parse.urlsplit(url).netloc}, venter {delay:.0f} s", file=sys.stderr)
            time.sleep(min(delay, 60))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def api(path: str, **params) -> dict:
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(get(f"{API}/{path}?{q}{'&' if q else ''}format=json"))


_MS = re.compile(r"/Date\((-?\d+)")


def msdate(s: str | None) -> str | None:
    """'/Date(1794816025563+0100)/' -> ISO-tid i norsk tid. Tom/år 1 -> None."""
    if not s:
        return None
    m = _MS.search(s)
    if not m:
        return None
    ms = int(m.group(1))
    if ms < 0:
        return None
    return dt.datetime.fromtimestamp(ms / 1000, TZ).isoformat(timespec="minutes")


def dmydate(s: str | None) -> str | None:
    """'26.03.2026 00:00:00' -> '2026-03-26'. Plassholder 01.01.0001 -> None."""
    if not s or s.startswith("01.01.0001"):
        return None
    try:
        return dt.datetime.strptime(s[:10], "%d.%m.%Y").date().isoformat()
    except ValueError:
        return None


def rssdate(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    try:
        return email.utils.parsedate_to_datetime(s).astimezone(TZ).isoformat(timespec="minutes")
    except (TypeError, ValueError):
        pass
    try:
        return dt.date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        return None


def person(p: dict | None) -> dict | None:
    if not p:
        return None
    return {
        "id": p.get("id"),
        "navn": f"{p.get('fornavn', '')} {p.get('etternavn', '')}".strip(),
        "parti": (p.get("parti") or {}).get("id"),
        "fylke": (p.get("fylke") or {}).get("navn"),
    }


def tema_for(*texts: str | None) -> list[str]:
    t = " ".join(x for x in texts if x).lower()
    return [k for k, rx in _TEMA_RE.items() if rx.search(t)]


def clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()


def strip_utm(url: str) -> str:
    return re.sub(r"[&?]utm_[^&]*", "", url or "").replace("?&", "?")


def sessions() -> tuple[str, list[str]]:
    d = api("sesjoner")
    cur = d["innevaerende_sesjon"]["id"]
    y = int(cur[:4])
    return cur, [cur, f"{y - 1}-{y}"]


# --------------------------------------------------------------------------
# Kilder
# --------------------------------------------------------------------------
def fetch_saker(sesj: list[str], tema_ids: set[int]) -> list[dict]:
    raw: dict[int, tuple[str, dict]] = {}
    for s in sesj:
        for x in api("saker", sesjonid=s)["saker_liste"]:
            kom = (x.get("komite") or {}).get("id")
            emner = {e["navn"].lower() for e in x.get("emne_liste") or []}
            t = tema_for(x.get("korttittel"))
            energy_hit = bool(set(t) & ENERGI_TEMA) or bool(emner & ENERGI_EMNER) or x["id"] in tema_ids
            if kom == KOMITE or energy_hit:
                raw.setdefault(x["id"], (s, x))

    def detail(item):
        s, x = item
        try:
            d = api("sak", sakid=x["id"])
        except Exception as e:  # detaljer er «nice to have»
            print(f"  ! sak {x['id']}: {e}", file=sys.stderr)
            d = {}
        return build_sak(s, x, d, tema_ids)

    with cf.ThreadPoolExecutor(2) as ex:
        out = list(ex.map(detail, raw.values()))
    return [s for s in out if s]


def build_sak(sesjon: str, x: dict, d: dict, tema_ids: set[int]) -> dict | None:
    kom = (x.get("komite") or {})
    emner = [e["navn"] for e in (d.get("emne_liste") or x.get("emne_liste") or [])]
    stikk = [e.get("navn", "") for e in d.get("stikkord_liste") or [] if isinstance(e, dict)]
    # Lange titler (budsjett o.l.) gir mange feiltreff, så utenfor energikomiteen
    # brukes bare korttittelen.
    egen = kom.get("id") == KOMITE
    t = tema_for(x.get("tittel") if egen else None, x.get("korttittel"), " ".join(emner), " ".join(stikk))
    if not egen:  # emnelistene på store saker (budsjett) er for brede til tema
        t = tema_for(x.get("korttittel"))
    energi = (
        bool(set(t) & ENERGI_TEMA)
        or bool(re.search(r"\benergi", x.get("korttittel") or "", re.I))
        or (egen and bool({e.lower() for e in emner} & ENERGI_EMNER))
    )
    tema_merket = x["id"] in tema_ids
    if not egen and not energi and not tema_merket:
        return None

    hend: list[dict] = []
    for steg in ((d.get("saksgang") or {}).get("saksgang_steg_liste") or []):
        for h in steg.get("saksgang_hendelse_liste") or []:
            dato = dmydate(h.get("dato"))
            if dato and h["id"] in HENDELSE:
                e = {"id": h["id"], "label": HENDELSE[h["id"]], "dato": dato}
                if e not in hend:
                    hend.append(e)
    hend.sort(key=lambda e: e["dato"])
    first = lambda *ids: next((e["dato"] for e in hend if e["id"] in ids), None)  # noqa: E731
    last = lambda *ids: next((e["dato"] for e in reversed(hend) if e["id"] in ids), None)  # noqa: E731

    status = x.get("status", 0)
    if status == 1:
        fase = 4
    elif status in (4, 5):
        fase = -1
    elif first("AVGITT") or x.get("innstilling_id", -1) > 0:
        fase = 3
    elif first("SENDT"):
        fase = 2
    elif status == 3:
        fase = 0
    else:
        fase = 1

    pubs = [
        {"tekst": p.get("lenke_tekst"), "url": "https:" + p["lenke_url"] if p.get("lenke_url", "").startswith("//") else p.get("lenke_url")}
        for p in d.get("publikasjon_referanse_liste") or []
        if p.get("lenke_url")
    ]
    opphav = (d.get("sak_opphav") or {}).get("forslagstiller_liste") or x.get("forslagstiller_liste") or []

    return {
        "id": x["id"],
        "sesjon": sesjon,
        "tittel": clean(x.get("tittel")),
        "korttittel": clean(x.get("korttittel")),
        "henvisning": x.get("henvisning"),
        "type": SAK_TYPE.get(x.get("type"), ""),
        "dokgruppe": DOKGRUPPE.get(x.get("dokumentgruppe"), ""),
        "status": SAK_STATUS.get(status, ""),
        "fase": fase,
        "komite": kom.get("navn"),
        "komite_id": kom.get("id"),
        "energi": energi,
        "tema_merket": tema_merket,
        "tema": t,
        "emner": emner,
        "parentes": d.get("parentestekst"),
        "forslagstillere": [p for p in map(person, opphav) if p],
        "saksordforer": [p for p in map(person, x.get("saksordfoerer_liste") or []) if p],
        "hendelser": hend,
        "datoer": {
            "fremmet": first("FREMMET", "FREMSATT", "REFS"),
            "sendt": first("SENDT"),
            "horingsfrist": last("HOERFRIST"),
            "horing": last("HOER"),
            "innstillingsfrist": last("AVGFRIST"),
            "avgitt": first("AVGITT"),
            "planlagt": last("PLBEHS"),
            "behandlet": first("BEHS", "VOT"),
        },
        "kortvedtak": clean(d.get("kortvedtak")),
        "vedtakstekst": clean(d.get("vedtakstekst")),
        "innstillingstekst": clean(d.get("innstillingstekst")),
        "publikasjoner": pubs,
        "oppdatert": msdate(x.get("sist_oppdatert_dato")),
        "url": f"{ST}/no/Saker-og-publikasjoner/Saker/Sak/?p={x['id']}",
    }


def build_spm(x: dict, sesjon: str) -> dict | None:
    titler = {
        (x.get("sporsmal_til_minister_tittel") or "").lower(),
        (x.get("rette_vedkommende_minister_tittel") or "").lower(),
        (x.get("besvart_av_minister_tittel") or "").lower(),
        (x.get("besvart_pa_vegne_av_minister_tittel") or "").lower(),
    }
    t = tema_for(x.get("tittel"), " ".join(e["navn"] for e in x.get("emne_liste") or []))
    til_em = MINISTER in titler
    if not til_em and not (set(t) & ENERGI_TEMA):
        return None
    typ = SPM_TYPE.get(x.get("type"), "skriftlig")
    til = person(x.get("sporsmal_til"))
    besv = person(x.get("besvart_av"))
    return {
        "id": x["id"],
        "sesjon": sesjon,
        "type": typ,
        "tittel": clean(x.get("tittel")),
        "fra": person(x.get("sporsmal_fra")),
        "til": til["navn"] if til else None,
        "til_tittel": x.get("rette_vedkommende_minister_tittel") or x.get("sporsmal_til_minister_tittel"),
        "besvart_av": besv["navn"] if besv else None,
        "besvart_av_tittel": x.get("besvart_av_minister_tittel"),
        "datert": msdate(x.get("datert_dato")) or msdate(x.get("sendt_dato")),
        "besvart": msdate(x.get("besvart_dato")),
        "status": "besvart" if x.get("besvart_dato") else "venter",
        "energiminister": til_em,
        "tema": t,
        "url": ST + SPM_URL[typ].format(x["id"]),
    }


def fetch_sporsmal(sesj: list[str]) -> list[dict]:
    out: dict[int, dict] = {}
    for s in sesj:
        for ep in ("skriftligesporsmal", "sporretimesporsmal", "interpellasjoner"):
            for x in api(ep, sesjonid=s)["sporsmal_liste"]:
                q = build_spm(x, s)
                if q:
                    out[q["id"]] = q
    return list(out.values())


_RSS_TITLE = re.compile(r"(?:Skriftlig spørsmål|Interpellasjon|Spørsmål)\s+fra\s+(.+?)\s+\(([^)]+)\)\s+til\s+([^.]+)")


def fetch_ventende(known: set[int]) -> list[dict]:
    """Ubesvarte spørsmål finnes ikke i API-et – de hentes fra Stortingets RSS."""
    feeds = {
        "skriftlig": f"{ST_RSS}/Rss-lister-for-sporsmal-som-venter-besvarelse1/Skriftlige-sporsmal/Energiministeren/",
        "interpellasjon": f"{ST_RSS}/Rss-lister-for-sporsmal-som-venter-besvarelse1/Interpellasjoner/energiministeren/",
    }
    out = []
    for typ, url in feeds.items():
        for it in parse_rss(get(url)):
            m = re.search(r"\.(\d+)$", it["guid"] or "") or re.search(r"qnid=(\d+)", it["link"] or "")
            if not m:
                continue
            qid = int(m.group(1))
            if qid in known:
                continue
            tm = _RSS_TITLE.search(it["title"] or "")
            navn, parti, til = (tm.group(1), tm.group(2), tm.group(3).strip()) if tm else (None, None, MINISTER)
            out.append({
                "id": qid, "sesjon": None, "type": typ, "tittel": clean(it["description"]) or it["title"],
                "fra": {"id": None, "navn": navn, "parti": parti, "fylke": None} if navn else None,
                "til": None, "til_tittel": til, "besvart_av": None, "besvart_av_tittel": None,
                "datert": it["date"], "besvart": None, "status": "venter", "energiminister": True,
                "tema": tema_for(it["description"]), "url": ST + SPM_URL[typ].format(qid),
            })
    return out


def fetch_tema_ids() -> set[int]:
    """Saker Stortinget selv har merket med hovedtema Energi (også i andre komiteer)."""
    ids = set()
    for it in parse_rss(get(f"{ST_RSS}/Rss-lister-for-hovedtema/Energi/")):
        m = re.search(r"[?&]p=(\d+)", it["link"] or "")
        if m:
            ids.add(int(m.group(1)))
    return ids


def fetch_horinger(sesj: list[str]) -> list[dict]:
    out = {}
    for s in sesj:
        for h in api("horinger", sesjonid=s)["horinger_liste"]:
            if (h.get("komite") or {}).get("id") != KOMITE:
                continue
            saker = [
                {"id": i.get("sak_id"), "tittel": clean(i.get("sak_korttittel") or i.get("sak_tittel")),
                 "henvisning": i.get("sak_henvisning")}
                for i in h.get("horing_sak_info_liste") or []
            ]
            tider = [
                {"tid": msdate(t.get("tidspunkt")), "sted": t.get("sted")}
                for t in h.get("horingstidspunkt_liste") or []
                if msdate(t.get("tidspunkt"))
            ]
            out[h["id"]] = {
                "id": h["id"],
                "saker": saker,
                "skriftlig": bool(h.get("skriftlig")),
                "innspillsfrist": msdate(h.get("innspillsfrist")),
                "anmodningsfrist": msdate(h.get("anmodningsfrist_dato_tid")),
                "start": msdate(h.get("start_dato")),
                "tidspunkt": tider,
                "status": h.get("horing_status"),
                "info": clean(h.get("status_info_tekst")),
                "url": f"{ST}/no/Saker-og-publikasjoner/Saker/Sak/?p={saker[0]['id']}" if saker else f"{ST}/no/Hva-skjer-pa-Stortinget/Horing/",
            }
    return list(out.values())


def fetch_dagsorden(cur: str, sak_ids: set[int], spm_ids: set[int]) -> list[dict]:
    now = dt.datetime.now(TZ)
    moter = [
        m for m in api("moter", sesjonid=cur)["moter_liste"]
        if m.get("id", 0) > 0 and msdate(m.get("mote_dato_tid"))
        and now - dt.timedelta(days=7) <= dt.datetime.fromisoformat(msdate(m["mote_dato_tid"])) <= now + dt.timedelta(days=45)
    ]
    out = []
    for m in moter:
        try:
            d = api("dagsorden", moteid=m["id"])
        except Exception as e:
            print(f"  ! dagsorden {m['id']}: {e}", file=sys.stderr)
            continue
        tid = msdate(d.get("mote_dato_tid") or m["mote_dato_tid"])
        for p in d.get("dagsordensak_liste") or []:
            if p.get("sak_id") in sak_ids or p.get("sporsmal_id") in spm_ids or p.get("komite_id") == KOMITE:
                out.append({
                    "tid": tid, "mote_id": m["id"], "nr": p.get("dagsordensak_nummer"),
                    "tekst": clean(p.get("dagsordensak_tekst")), "henvisning": p.get("dagsordensak_henvisning"),
                    "sak_id": p.get("sak_id") if p.get("sak_id", -1) > 0 else None,
                    "sporsmal_id": p.get("sporsmal_id") if p.get("sporsmal_id", -1) > 0 else None,
                })
    return out


def parse_rss(raw: bytes) -> list[dict]:
    root = ET.fromstring(raw)
    out = []
    for it in root.iter("item"):
        date = it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")
        out.append({
            "title": clean(it.findtext("title")),
            "link": strip_utm((it.findtext("link") or "").strip()),
            "guid": (it.findtext("guid") or "").strip(),
            "description": clean(re.sub(r"<[^>]+>", " ", it.findtext("description") or "")),
            "date": rssdate(date),
        })
    return out


def fetch_regjeringen() -> list[dict]:
    nyheter = parse_rss(get(f"{REG_RSS}?documentType=aktuelt/nyheter&owner={REG_OWNER}"))
    alle = parse_rss(get(f"{REG_RSS}?owner={REG_OWNER}"))
    links = {n["link"] for n in nyheter}
    out = [{**n, "kategori": "nyhet"} for n in nyheter]
    for a in alle:
        if a["link"] not in links:
            out.append({**a, "kategori": "kalender" if re.match(r"(Energiministeren|Statssekretær|Statsråd)", a["title"]) else "annet"})
    for o in out:
        o.pop("guid", None)
        o["url"] = o.pop("link")
        o["tittel"] = o.pop("title")
        o["dato"] = o.pop("date")
        o["beskrivelse"] = o.pop("description")
    out.sort(key=lambda x: x["dato"] or "", reverse=True)
    return out


# --------------------------------------------------------------------------
# Eksterne høringer: regjeringen.no og Miljødirektoratet
# --------------------------------------------------------------------------
PETROLEUM_RE = re.compile(TEMA["Olje og gass"] + r"|havindustri|havbunnsmineral|petroleumstilsyn", re.I)
_HORING_RE = re.compile(r"\bh(ø|oe)ring|\bhøyring", re.I)
_DEP_RE = re.compile(r"^((?:[A-ZÆØÅ]\w*-(?:,? \w+-)* og )?\w*departementet)\b")
MDIR = "https://www.miljodirektoratet.no"
MDIR_API = MDIR + "/hearingslistpage/gethearings"
MDIR_OLJE_GASS, MDIR_KLIMA = 6169, 4389  # emne-id-er i Miljødirektoratets høringsliste


def _ekstern(**k) -> dict:
    t = tema_for(k.get("tittel"), k.get("beskrivelse"), " ".join(k.get("emner") or []))
    k.setdefault("tema", t)
    return k


def avsender_fra(beskrivelse: str | None) -> str:
    m = _DEP_RE.match(beskrivelse or "")
    return m.group(1) if m else "Regjeringen"


def fetch_reg_horinger(prev: list[dict]) -> list[dict]:
    """Høringer fra regjeringen.no via RSS (eksportsiden er bak bot-sperre).

    - Energidepartementet: alle høringer.
    - Alle departementer: høringer som gjelder petroleum/olje og gass.
    Feedene viser bare de siste ~100 dokumentene, så vi slår sammen med det vi
    har fra før. Frist finnes ikke i RSS – den står på høringssiden.
    """
    out: dict[str, dict] = {h["url"]: h for h in prev if h.get("kilde") == "regjeringen"}
    ed = parse_rss(get(f"{REG_RSS}?documentType=dokumenter&owner={REG_OWNER}"))
    alle = parse_rss(get(f"{REG_RSS}?documentType=dokumenter"))
    for it, fra_ed in [(x, True) for x in ed] + [(x, False) for x in alle]:
        if not _HORING_RE.search(it["title"]):
            continue
        tekst = f"{it['title']} {it['description']}"
        petro = bool(PETROLEUM_RE.search(tekst))
        if not fra_ed and not petro:
            continue
        avsender = "Energidepartementet" if fra_ed else avsender_fra(it["description"])
        old = out.get(it["link"], {})
        out[it["link"]] = _ekstern(
            id=it["link"], kilde="regjeringen", avsender=avsender, tittel=it["title"],
            beskrivelse=it["description"][:500], publisert=(it["date"] or "")[:10] or old.get("publisert"),
            frist=None, status=None, saksnr=None, emner=["Petroleum"] if petro else [],
            energi=True, url=it["link"],
        )
    return sorted(out.values(), key=lambda h: h["publisert"] or "", reverse=True)


def _mdir_date(s: str | None) -> str | None:
    try:
        return dt.datetime.strptime(s, "%d.%m.%Y").date().isoformat() if s else None
    except ValueError:
        return None


def fetch_mdir_horinger(prev: list[dict]) -> list[dict]:
    """Miljødirektoratets høringer (JSON-endepunktet bak høringssiden).

    Alle aktive høringer hentes, pluss nylig avsluttede innen olje og gass og
    klima. Vi tar med høringer om olje og gass, og andre med energitema; rene
    klimahøringer merkes som ikke-energi (vises med «klima og miljø»-bryteren).
    """
    def page(**params):
        q = urllib.parse.urlencode(params)
        return json.loads(get(f"{MDIR_API}?{q}"))

    rows: list[tuple[dict, bool]] = []
    skip, total = 0, 1
    while skip < total and skip < 200:
        d = page(skip=skip, searchExpired="false")
        total = d.get("totalMatching") or 0
        rows += [(h, False) for h in d.get("hearings") or []]
        skip += 20
    for subj, n in ((MDIR_OLJE_GASS, 40), (MDIR_KLIMA, 20)):
        for skip in range(0, n, 20):
            rows += [(h, True) for h in page(skip=skip, subjectids=subj, searchExpired="true").get("hearings") or []]

    out: dict[str, dict] = {h["url"]: h for h in prev if h.get("kilde") == "miljodirektoratet"}
    today = dt.date.today().isoformat()
    for h, _expired in rows:
        emner = h.get("subjects") or []
        t = tema_for(h.get("title"), " ".join(emner))
        olje = "Olje og gass" in emner
        energi = olje or bool(set(t) & ENERGI_TEMA)
        klima = "Klima" in emner
        if not (energi or klima):
            continue
        url = MDIR + h["url"] if h.get("url", "").startswith("/") else h.get("url")
        frist = _mdir_date(h.get("deadline"))
        if olje and "Olje og gass" not in t:
            t = ["Olje og gass", *t]
        out[url] = _ekstern(
            id=url, kilde="miljodirektoratet", avsender="Miljødirektoratet", tittel=clean(h.get("title")),
            beskrivelse="", publisert=_mdir_date(h.get("published")), frist=frist,
            status=("åpen" if frist and frist >= today else "avsluttet") if frist else None,
            saksnr=h.get("hearingNumber"), emner=emner, energi=energi, url=url, tema=t,
        )
    # Vurder eldre oppføringer på nytt (regler og tema kan ha endret seg)
    for h in list(out.values()):
        t = tema_for(h["tittel"], " ".join(h["emner"]))
        if "Olje og gass" in h["emner"] and "Olje og gass" not in t:
            t = ["Olje og gass", *t]
        h["tema"] = t
        h["energi"] = "Olje og gass" in h["emner"] or bool(set(t) & ENERGI_TEMA)
        if not (h["energi"] or "Klima" in h["emner"]):
            del out[h["url"]]
    for h in out.values():
        if h.get("frist"):
            h["status"] = "åpen" if h["frist"] >= today else "avsluttet"
    return sorted(out.values(), key=lambda h: h["publisert"] or "", reverse=True)


# --------------------------------------------------------------------------
# Avledede lister: kalender og aktivitet
# --------------------------------------------------------------------------
def build_kalender(saker, horinger, dagsorden, nyheter, eksterne=()) -> list[dict]:
    today = dt.date.today().isoformat()
    by_id = {s["id"]: s for s in saker}
    cal = []
    add = lambda **k: cal.append(k)  # noqa: E731
    med_horing = {x["id"] for h in horinger for x in h["saker"]}
    for s in saker:
        d = s["datoer"]
        if s["fase"] in (4, -1):
            continue
        for key, typ, label in (
            ("horingsfrist", "frist", "Frist for å melde seg til høring"),
            ("innstillingsfrist", "frist", "Frist for innstilling fra komiteen"),
            ("planlagt", "plenum", "Planlagt behandlet i Stortinget"),
        ):
            if key == "horingsfrist" and s["id"] in med_horing:
                continue  # høringslista har eksakt frist og klokkeslett
            if d.get(key) and d[key] >= today:
                add(dato=d[key], type=typ, label=label, tittel=s["korttittel"], sak_id=s["id"], energi=s["energi"], url=s["url"])
    for h in horinger:
        sak = h["saker"][0] if h["saker"] else {}
        if h["innspillsfrist"] and h["innspillsfrist"][:10] >= today:
            add(dato=h["innspillsfrist"], type="horing", label="Frist for skriftlig innspill" if h["skriftlig"] else "Frist for påmelding til høring",
                tittel=sak.get("tittel"), sak_id=sak.get("id"), url=h["url"], energi=None)
        for t in h["tidspunkt"]:
            if t["tid"][:10] >= today and t["sted"] and t["sted"].lower() != "skriftlig":
                add(dato=t["tid"], type="horing", label=f"Muntlig høring ({t['sted']})", tittel=sak.get("tittel"), sak_id=sak.get("id"), url=h["url"], energi=None)
    for p in dagsorden:
        if p["tid"][:10] >= today:
            add(dato=p["tid"], type="plenum", label=f"Dagsorden sak {p['nr']}" if p["nr"] else "Dagsorden",
                tittel=p["tekst"], sak_id=p["sak_id"], url=f"{ST}/no/Saker-og-publikasjoner/Saker/Sak/?p={p['sak_id']}" if p["sak_id"] else f"{ST}/no/Hva-skjer-pa-Stortinget/Dagsorden/", energi=None)
    for n in nyheter:
        if n["kategori"] == "kalender" and n["dato"] and n["dato"][:10] >= today:
            add(dato=n["dato"], type="minister", label="Statsrådens kalender", tittel=n["tittel"], url=n["url"], energi=True)
    for h in eksterne:
        if h.get("frist") and h["frist"] >= today:
            add(dato=h["frist"], type="horing", label=f"Høringsfrist – {h['avsender']}", tittel=h["tittel"], url=h["url"], energi=h["energi"])
    for c in cal:
        if c.get("energi") is None:
            c["energi"] = by_id[c["sak_id"]]["energi"] if c.get("sak_id") in by_id else False
    # fjern dubletter (samme dato+sak+type)
    seen, uniq = set(), []
    for c in sorted(cal, key=lambda c: c["dato"]):
        k = (c["dato"][:10], c.get("sak_id"), c["type"], c["label"][:20] if not c.get("sak_id") else "")
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq


def build_aktivitet(saker, sporsmal, nyheter, eksterne=()) -> list[dict]:
    today = dt.date.today().isoformat()
    akt = []
    for s in saker:
        d = s["datoer"]
        base = dict(sak_id=s["id"], energi=s["energi"], url=s["url"], tittel=s["korttittel"], tema=s["tema"])
        if d.get("fremmet"):
            akt.append({**base, "dato": d["fremmet"], "type": "ny_sak", "label": f"Ny sak: {s['dokgruppe'].lower() or 'sak'}", "meta": s["henvisning"]})
        if d.get("avgitt"):
            akt.append({**base, "dato": d["avgitt"], "type": "innstilling", "label": "Innstilling avgitt", "meta": s["komite"]})
        if s["fase"] == 4 and (d.get("behandlet") or s["oppdatert"]):
            akt.append({**base, "dato": d.get("behandlet") or s["oppdatert"][:10], "type": "vedtak", "label": "Behandlet i Stortinget", "meta": s["vedtakstekst"] or None})
    for q in sporsmal:
        base = dict(spm_id=q["id"], energi=q["energiminister"] or bool(set(q["tema"]) & ENERGI_TEMA), url=q["url"], tittel=q["tittel"], tema=q["tema"])
        who = f"{q['fra']['navn']} ({q['fra']['parti']})" if q.get("fra") else ""
        navn = {"skriftlig": "Skriftlig spørsmål", "sporretime": "Spørretimespørsmål", "muntlig": "Muntlig spørsmål", "interpellasjon": "Interpellasjon"}[q["type"]]
        if q["datert"]:
            akt.append({**base, "dato": q["datert"], "type": "spm", "label": f"{navn} stilt", "meta": f"{who} → {q['til_tittel'] or ''}".strip()})
        if q["besvart"]:
            akt.append({**base, "dato": q["besvart"], "type": "svar", "label": f"{navn} besvart", "meta": f"Besvart av {q['besvart_av_tittel'] or q['besvart_av'] or ''}".strip()})
    for n in nyheter:
        if n["kategori"] == "nyhet" and n["dato"]:
            akt.append({"dato": n["dato"], "type": "regjeringen", "label": "Regjeringen", "tittel": n["tittel"], "url": n["url"], "meta": n["beskrivelse"][:200], "energi": True, "tema": []})
    for h in eksterne:
        if h.get("publisert"):
            frist = f"Frist {dt.date.fromisoformat(h['frist']).strftime('%d.%m.%Y')}" if h.get("frist") else None
            akt.append({"dato": h["publisert"], "type": "ekstern_horing", "label": f"Ny høring – {h['avsender']}", "tittel": h["tittel"],
                        "url": h["url"], "meta": " · ".join(x for x in (frist, h.get("saksnr")) if x) or None, "energi": h["energi"], "tema": h["tema"]})
    akt = [a for a in akt if a["dato"][:10] <= today]
    akt.sort(key=lambda a: a["dato"], reverse=True)
    return akt[:400]


def write_rss(akt: list[dict], generated: str) -> None:
    def rfc(d: str) -> str:
        x = dt.datetime.fromisoformat(d) if "T" in d else dt.datetime.fromisoformat(d + "T08:00").replace(tzinfo=TZ)
        return email.utils.format_datetime(x)

    items = []
    for a in [a for a in akt if a.get("energi")][:80]:
        guid = f"{a['type']}-{a.get('sak_id') or a.get('spm_id') or a['url']}-{a['dato'][:10]}"
        desc = " · ".join(x for x in (a["label"], a.get("meta")) if x)
        items.append(
            "<item>"
            f"<title>{html.escape(a['label'] + ': ' + (a['tittel'] or ''))}</title>"
            f"<link>{html.escape(a['url'])}</link>"
            f"<guid isPermaLink=\"false\">{html.escape(guid)}</guid>"
            f"<pubDate>{rfc(a['dato'])}</pubDate>"
            f"<category>{html.escape(a['type'])}</category>"
            f"<description>{html.escape(desc)}</description>"
            "</item>"
        )
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        "<title>Energi på Stortinget</title>"
        f"<link>{SITE_URL}</link>"
        f'<atom:link href="{SITE_URL}feed.xml" rel="self" type="application/rss+xml"/>'
        "<description>Nye energisaker, innstillinger, vedtak og spørsmål til energiministeren</description>"
        "<language>no</language>"
        f"<lastBuildDate>{email.utils.format_datetime(dt.datetime.fromisoformat(generated))}</lastBuildDate>"
        + "".join(items)
        + "</channel></rss>\n"
    )
    OUT_RSS.write_text(xml, encoding="utf-8")


# --------------------------------------------------------------------------
def main() -> int:
    prev = {}
    if OUT_JSON.exists():
        try:
            prev = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        except ValueError:
            pass
    kilder: dict[str, dict] = {}

    def run(name: str, fn, fallback):
        t0 = time.time()
        try:
            v = fn()
            kilder[name] = {"ok": True, "antall": len(v) if hasattr(v, "__len__") else None, "sek": round(time.time() - t0, 1)}
            print(f"✓ {name}: {kilder[name]['antall']} ({kilder[name]['sek']} s)")
            return v
        except Exception as e:
            kilder[name] = {"ok": False, "feil": str(e)[:300]}
            print(f"✗ {name}: {e}", file=sys.stderr)
            return fallback

    cur, sesj = sessions()
    tema_ids = run("Stortinget RSS: hovedtema Energi", fetch_tema_ids, set())
    saker = run("Stortinget API: saker", lambda: fetch_saker(sesj, tema_ids), prev.get("saker", []))
    spm = run("Stortinget API: spørsmål", lambda: fetch_sporsmal(sesj), [q for q in prev.get("sporsmal", []) if q["status"] == "besvart"])
    vent = run("Stortinget RSS: ubesvarte spørsmål", lambda: fetch_ventende({q["id"] for q in spm}),
               [q for q in prev.get("sporsmal", []) if q["status"] == "venter"])
    spm = spm + [q for q in vent if q["id"] not in {x["id"] for x in spm}]
    horinger = run("Stortinget API: høringer", lambda: fetch_horinger(sesj), prev.get("horinger", []))
    dagsorden = run("Stortinget API: dagsorden", lambda: fetch_dagsorden(cur, {s["id"] for s in saker}, {q["id"] for q in spm}),
                    prev.get("dagsorden", []))
    nyheter = run("Regjeringen.no: Energidepartementet", fetch_regjeringen, prev.get("nyheter", []))
    prev_ext = prev.get("eksterne_horinger", [])
    reg_h = run("Regjeringen.no: høringer (ED + petroleum)", lambda: fetch_reg_horinger(prev_ext),
                [h for h in prev_ext if h["kilde"] == "regjeringen"])
    mdir_h = run("Miljødirektoratet: høringer", lambda: fetch_mdir_horinger(prev_ext),
                 [h for h in prev_ext if h["kilde"] == "miljodirektoratet"])
    eksterne = sorted(reg_h + mdir_h, key=lambda h: h.get("publisert") or "", reverse=True)

    if not saker and not spm:
        print("Ingen data – avbryter uten å skrive.", file=sys.stderr)
        return 1

    saker.sort(key=lambda s: (s["datoer"].get("fremmet") or s["oppdatert"] or ""), reverse=True)
    spm.sort(key=lambda q: q["datert"] or "", reverse=True)
    generated = dt.datetime.now(TZ).isoformat(timespec="minutes")
    data = {
        "generert": generated,
        "sesjon": cur,
        "sesjoner": sesj,
        "tema": list(TEMA),
        "energi_tema": sorted(ENERGI_TEMA),
        "kilder": kilder,
        "saker": saker,
        "sporsmal": spm,
        "horinger": horinger,
        "dagsorden": dagsorden,
        "nyheter": nyheter[:120],
        "eksterne_horinger": eksterne,
        "kalender": build_kalender(saker, horinger, dagsorden, nyheter, eksterne),
        "aktivitet": build_aktivitet(saker, spm, nyheter, eksterne),
    }
    # «endret» flyttes bare når selve innholdet endrer seg, slik at workflowen
    # kan la være å committe når ingenting nytt har skjedd.
    sig = lambda d: hashlib.sha256(json.dumps({k: v for k, v in d.items() if k not in ("generert", "endret", "kilder")},  # noqa: E731
                                              ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    changed = not prev or sig(prev) != sig(data)
    data["endret"] = generated if changed else prev.get("endret", generated)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"changed={'true' if changed else 'false'}\n")
    print("Innholdet er endret." if changed else "Ingen endringer i innholdet.")
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_rss(data["aktivitet"], generated)
    print(f"Skrev {OUT_JSON.relative_to(ROOT.parent)} ({OUT_JSON.stat().st_size // 1024} kB) og {OUT_RSS.relative_to(ROOT.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
