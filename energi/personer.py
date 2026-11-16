"""Profilkort for representanter.

Bygger site/data/personer.json med
  * grunndata fra «dagensrepresentanter» (parti, fylke, e-post, komiteer, vara)
  * kodet biografi (perioder, stortingsverv, utdanning, yrke, andre verv)
  * alle saker personen står på (forslagstiller/saksordfører) og alle spørsmål
    personen har stilt – på tvers av tema, med markering av energisakene.

Biografier caches og fornyes etter BIO_MAKS_ALDER dager, høyst BIO_MAKS_PER_KJORING
per kjøring (styres med miljøvariabelen BIO_MAX), så Stortingets API ikke belastes.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from urllib.parse import quote

BIO_MAKS_ALDER = 7
BIO_MAKS_PER_KJORING = int(os.environ.get("BIO_MAX", "60"))
BILDE_URL = "https://data.stortinget.no/eksport/personbilde?personid={}&storrelse=middels"
PROFIL_URL = "https://www.stortinget.no/no/Representanter-og-komiteer/Representantene/Representant/?perid={}"

SAK_STATUS = {1: "Behandlet", 2: "Til behandling", 3: "Varslet", 4: "Trukket", 5: "Bortfalt"}
SPM_TYPE = {5: "skriftlig", 1: "sporretime", 2: "muntlig", 6: "interpellasjon"}
UTD_TYPE = {"10": "utdanning", "14": "utdanning", "20": "yrke"}
VERV_TYPE = {"KOMI": "Komité", "FAG": "Fagkomité", "DELE": "Delegasjon", "PART": "Partigruppe", "PRES": "Presidentskapet",
             "REGJ": "Regjering", "EØS": "EØS/EFTA", "INTR": "Internasjonalt", "SKS": "Særskilt komité"}


def _ms(s, msdate):
    v = msdate(s)
    return v[:10] if v else None


def _navn(p: dict) -> str:
    return f"{p.get('fornavn', '')} {p.get('etternavn', '')}".strip()


def build_index(raw_saker, raw_spm, energi_saker: set[int], energi_spm: set[int], msdate, clean) -> tuple[dict, dict]:
    """-> (aktivitet per person-id, grunndata per person-id fra sakene/spørsmålene)."""
    akt: dict[str, dict] = {}
    base: dict[str, dict] = {}

    def note(p):
        if p and p.get("id") and p["id"] not in base:
            base[p["id"]] = {"id": p["id"], "navn": _navn(p), "fornavn": p.get("fornavn"), "etternavn": p.get("etternavn"),
                             "parti": (p.get("parti") or {}).get("id"), "parti_navn": (p.get("parti") or {}).get("navn"),
                             "fylke": (p.get("fylke") or {}).get("navn"), "kjonn": p.get("kjoenn"),
                             "fodt": _ms(p.get("foedselsdato"), msdate)}

    seen_sak = set()
    for sesjon, x in raw_saker:
        if x["id"] in seen_sak:
            continue
        seen_sak.add(x["id"])
        ref = {"id": x["id"], "t": clean(x.get("korttittel") or x.get("tittel"))[:220], "h": x.get("henvisning"),
               "st": SAK_STATUS.get(x.get("status"), ""), "s": sesjon, "e": x["id"] in energi_saker,
               "k": (x.get("komite") or {}).get("navn"), "d": _ms(x.get("sist_oppdatert_dato"), msdate)}
        for rolle, lst in (("forslag", x.get("forslagstiller_liste")), ("ordforer", x.get("saksordfoerer_liste"))):
            for p in lst or []:
                note(p)
                akt.setdefault(p["id"], {"saker": [], "sporsmal": []})["saker"].append({**ref, "r": rolle})
    seen_spm = set()
    for sesjon, x in raw_spm:
        p = x.get("sporsmal_fra")
        if not p or x["id"] in seen_spm:
            continue
        seen_spm.add(x["id"])
        note(p)
        akt.setdefault(p["id"], {"saker": [], "sporsmal": []})["sporsmal"].append({
            "id": x["id"], "ty": SPM_TYPE.get(x.get("type"), "skriftlig"), "t": clean(x.get("tittel"))[:240],
            "d": _ms(x.get("datert_dato"), msdate), "til": x.get("rette_vedkommende_minister_tittel") or x.get("sporsmal_til_minister_tittel"),
            "b": bool(x.get("besvart_dato")), "e": x["id"] in energi_spm, "s": sesjon,
        })
    for a in akt.values():
        a["saker"].sort(key=lambda r: (r["s"], r["id"]), reverse=True)
        a["sporsmal"].sort(key=lambda r: r["d"] or "", reverse=True)
    return akt, base


def parse_biografi(d: dict, msdate) -> dict:
    pers = d.get("personalia_kodet") or {}
    out = {
        "ansiennitet": {"aar": pers.get("ansiennitet_aar"), "dager": pers.get("ansiennitet_dager")},
        "fodested": ", ".join(x for x in (pers.get("foede_kommune"), pers.get("foede_fylke")) if x) or None,
        "perioder": [], "stortingsverv": [], "utdanning": [], "yrke": [], "annet": [], "verv": [], "litteratur": [],
        "permisjoner": [],
    }
    for p in d.get("stortingsperiode_kodet_liste") or []:
        out["perioder"].append({"periode": p.get("stortingsperiode_id"), "fylke": p.get("fylke"), "parti": p.get("parti_id"),
                                "verv": p.get("verv"), "nr": p.get("representantnummer")})
    for v in d.get("stortingsverv_kodet_liste") or []:
        out["stortingsverv"].append({"periode": v.get("stortingsperiode_id"), "type": VERV_TYPE.get(v.get("komite_type"), v.get("komite_type")),
                                     "navn": v.get("komite_navn"), "verv": v.get("verv"), "fra": _ms(v.get("fra_dato"), msdate),
                                     "til": _ms(v.get("til_dato"), msdate), "sort": v.get("sortering")})
    for u in d.get("utdanning_yrke_kodet_liste") or []:
        rec = {"navn": u.get("navn"), "fra": None if u.get("fra_aar_ukjent") else u.get("fra_aar"),
               "til": None if u.get("til_aar_ukjent") else u.get("til_aar"), "merknad": u.get("merknad") or None}
        out[UTD_TYPE.get(str(u.get("type")), "annet")].append(rec)
    for v in d.get("verv_kodet_liste") or []:
        out["verv"].append({"organisasjon": v.get("organisasjon"), "sted": v.get("sted"), "verv": v.get("verv"), "type": v.get("type"),
                            "fra": None if v.get("fra_aar_ukjent") else v.get("fra_aar"),
                            "til": None if v.get("til_aar_ukjent") else v.get("til_aar"), "merknad": v.get("merknad") or None})
    for li in d.get("litteratur_kodet_liste") or []:
        tekst = " · ".join(str(v) for k, v in li.items() if k not in ("respons_dato_tid", "versjon") and isinstance(v, (str, int)) and v not in ("", -1))
        if tekst:
            out["litteratur"].append(tekst)
    for p in d.get("permisjon_kodet_liste") or []:
        out["permisjoner"].append({k: v for k, v in p.items() if k not in ("respons_dato_tid", "versjon")})
    for k in ("utdanning", "yrke", "annet", "verv"):
        out[k].sort(key=lambda r: (r.get("fra") or 0), reverse=True)
    return out


def slug(pid: str) -> str:
    """Filnavn for en person-id (æøå o.l. kodes som _hex). Samme regel i app.js."""
    return "".join(c if re.match(r"[A-Za-z0-9]", c) else f"_{ord(c):x}" for c in pid)


def build(api, msdate, clean, raw_saker, raw_spm, energi_saker, energi_spm, bio_cache: dict,
          old_bios: dict, log=print) -> tuple[dict, dict]:
    """-> (personer per id, oppdatert bio-cache {id: {"bio", "hentet"}}).

    bio_cache er en lokal cache (actions/cache i CI) med hentedato; old_bios er
    biografier fra de publiserte filene, brukt når cachen mangler.
    """
    today = dt.date.today()
    akt, base = build_index(raw_saker, raw_spm, energi_saker, energi_spm, msdate, clean)

    dagens = {r["id"]: r for r in api("dagensrepresentanter")["dagensrepresentanter_liste"]}
    personer: dict[str, dict] = {}
    for pid in set(dagens) | set(akt):
        r = dagens.get(pid)
        if r:
            p = {"id": pid, "navn": _navn(r), "fornavn": r.get("fornavn"), "etternavn": r.get("etternavn"),
                 "parti": (r.get("parti") or {}).get("id"), "parti_navn": (r.get("parti") or {}).get("navn"),
                 "fylke": (r.get("fylke") or {}).get("navn"), "kjonn": r.get("kjoenn"), "fodt": _ms(r.get("foedselsdato"), msdate),
                 "epost": r.get("epost"), "aktiv": True, "vara": bool(r.get("vara_representant")),
                 "komiteer": [k.get("navn") for k in r.get("komiteer_liste") or []],
                 "vara_for": _navn(r["vara_for"]) if r.get("vara_for") else None,
                 "fast_vara_for": _navn(r["fast_vara_for"]) if r.get("fast_vara_for") else None}
        else:
            p = {**base[pid], "epost": None, "aktiv": False, "vara": None, "komiteer": [], "vara_for": None, "fast_vara_for": None}
        p["bilde"] = BILDE_URL.format(quote(pid))
        p["profil"] = PROFIL_URL.format(quote(pid))
        a = akt.get(pid, {"saker": [], "sporsmal": []})
        p["saker"], p["sporsmal"] = a["saker"], a["sporsmal"]
        personer[pid] = p

    cache = {pid: c for pid, c in (bio_cache or {}).items() if pid in personer}
    def alder(pid):
        h = (cache.get(pid) or {}).get("hentet")
        return (today - dt.date.fromisoformat(h)).days if h else 10_000
    trenger = sorted((pid for pid in personer if alder(pid) >= BIO_MAKS_ALDER),
                     key=lambda pid: (-alder(pid), not personer[pid]["aktiv"]))
    hentet = feil = 0
    for pid in trenger[:BIO_MAKS_PER_KJORING]:
        try:
            d = api("kodetbiografi", personid=pid)
            if d.get("person_id"):
                cache[pid] = {"bio": parse_biografi(d, msdate), "hentet": today.isoformat()}
                hentet += 1
        except Exception as e:  # én feilende biografi skal ikke stoppe resten
            feil += 1
            log(f"  ! biografi {pid}: {e}")
    for pid, p in personer.items():
        bio = (cache.get(pid) or {}).get("bio") or old_bios.get(pid)
        if bio:
            p["bio"] = bio
    log(f"  biografier: {hentet} hentet, {feil} feilet, {max(0, len(trenger) - BIO_MAKS_PER_KJORING)} venter til neste kjøring")
    return personer, cache


def index_entry(p: dict) -> dict:
    return {
        "id": p["id"], "navn": p["navn"], "parti": p.get("parti"), "fylke": p.get("fylke"), "aktiv": p.get("aktiv"),
        "vara": p.get("vara"), "fil": slug(p["id"]),
        "n": [len(p["saker"]), sum(r["e"] for r in p["saker"]), len(p["sporsmal"]), sum(r["e"] for r in p["sporsmal"])],
    }


def name_key(navn: str) -> str:
    return re.sub(r"\s+", " ", (navn or "").strip().lower())
