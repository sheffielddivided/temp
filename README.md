# Worldwide Rig Count

Månedlig import av Baker Hughes **Worldwide Rig Count** og en statisk nettside
(GitHub Pages) som visualiserer antall rigger per region og land.

```
raw/                 Worldwide-filer (månedlig, = historikken)
history/             ukehistorikk USA/Canada fra 2011 (na_weekly.csv) + kilde per uke
                     (na_sources.json) – kilden til sannhet for ukedataene
scripts/rigcount.py  fetch / ingest / build
data/                worldwide_long.csv – én rad per måned/land/type/lokasjon
site/                nettsiden: index.html (graf), map.html (kart + avspiller),
                     us.html (USA/Canada), upload.html (opplasting),
                     data/worldwide.json
scripts/geo.py       koordinater per land for kartet
scripts/na.py        parser for North America-filen («NAM Weekly»)
tests/               parsertester
```

## Slik fungerer det

GitHub Action (`.github/workflows/update.yml`) kjører daglig dag 2–14 i hver
måned, ved push til `raw/`, `scripts/` eller `site/`, og manuelt:

1. `fetch` – henter rigcount.bakerhughes.com/intl-rig-count, finner
   Worldwide-lenken og laster ned filen hvis innholdet er nytt.
2. `build` – parser og slår sammen alle filer i `raw/` til `data/worldwide_long.csv` og
   `site/data/worldwide.json`.
3. Endringer committes, og `site/` publiseres til GitHub Pages.

## Viktig: Akamai-blokkering

Baker Hughes' rigcount-side ligger bak Akamai, som blokkerer mange
datasenter-IP-er. GitHub Actions-runnere vil derfor sannsynligvis få **403**.
Da gir `fetch` en advarsel, og siden bygges fra siste fil i `raw/`.

Manuell oppdatering (tar et minutt i måneden):

**Enklest: opplastingssiden** `upload.html` på GitHub Pages-siden (lenke øverst
på grafen). Den laster filen rett inn i `raw/` via GitHub-API-et med et
fine-grained token (kun dette repoet, kun «Contents: Read and write»). Tokenet
lagres bare i nettleseren hvis du krysser av for det.

Alternativt:

1. Last ned Worldwide Rig Count-filen fra
   https://rigcount.bakerhughes.com/intl-rig-count
2. Enten last den opp via GitHub-nettsiden til `raw/` (filnavnet spiller
   ingen rolle), eller lokalt:
   ```bash
   python scripts/rigcount.py ingest ~/Downloads/Worldwide*.xlsx
   git add raw && git commit -m "Ny rig count-fil" && git push
   ```
   Pushen trigger bygging og publisering.

Alternativt kan `fetch` kjøres fra en maskin med vanlig IP (cron lokalt eller
en self-hosted runner).

## Oppsett

- **Settings → Pages → Source: GitHub Actions.**
- GitHub Pages på private repoer krever betalt plan (Pro/Team). Ellers må
  repoet være offentlig.

## Lokalt

```bash
pip install -r requirements.txt pytest
python -m pytest -q tests
python scripts/rigcount.py build
python -m http.server -d site 8000
```

## Parseren og historikk

`build` leser detaljtabellen i fanen **«WW Monthly»** (kolonnene Region,
Country, DrillFor, Location, Rig Status, Year, Month, Rig Count Value).

- Hver månedsfil dekker bare ca. de siste 34 månedene. `build` slår derfor
  sammen **alle** filer i `raw/`; for overlappende måneder vinner filen med
  senest innhold. **Slett ikke gamle filer** – de er historikken.
- Saudi-Arabia rapporteres som «Operating Rigs», øvrige land som
  «Active Rigs». Begge tas med, slik Baker Hughes' egne totaler gjør.
- **Metodebrudd:** BH har revidert Saudi-Arabia til «Operating Rigs» bakover
  bare til jan 2024 (~300 mot ~85 «Active Rigs» tidligere). Sammenslåtte
  serier får derfor et hopp på ~220 rigger i Midtøsten/verden i jan 2024.
  `build` oppdager slike statusskifter automatisk og nettsiden markerer dem.
- Eldre filer (f.eks. juli 2025) mangler «Rig Status»-kolonnen; da antas
  «Active Rigs». Juli 2025-filen går tilbake til jan 2013.
- «Land» på nettsiden inkluderer Inland Waters (som BHs oppsummering).
- Testen `test_real_files_match_summary` sjekker hver fil i `raw/` mot BHs
  egen regionoppsummering øverst i fanen. Endrer BH layouten, feiler
  workflowen før noe publiseres.

## North America (ukentlig)

Ukerapportene fra Baker Hughes («North America Rig Count Report», ~7 MB) lagres
**ikke** i main. Flyten er:

1. Opplastingssiden legger filen i grenen **`inbox`** (mappen `inbox/`) og
   starter workflowen (krever «Actions: Read and write» på tokenet; ellers tas
   den av den daglige kjøringen kl. 17:23 UTC).
2. Workflowen henter filen fra `inbox`, kontrollerer den mot BHs egen
   «NAM Summary» (`tests/test_na.py`), og fletter ukene inn i
   `history/na_weekly.csv`. For hver uke vinner rapporten med senest innhold
   (`history/na_sources.json` holder styr på det), så en eldre rapport aldri
   overskriver nyere/reviderte tall.
3. `inbox` nullstilles til en ny rot-commit uten filen, så Excel-filen
   forsvinner fra repoet. Main vokser bare med de små tekstendringene i
   `history/`.

Feiler kontrollen, blir filen liggende i `inbox` og ingenting publiseres.

`history/` ble bygd fra BHs pivot-fil «North American Rotary Rig Count Pivot
Table (Feb 2011 - Mar 2024).xlsb» og ukerapporten 11-06-2026. Begge ligger i
git-historikken (commit 2eb93c4, mappen `raw-na/`) om historikken må bygges på
nytt. Pivot-filen mangler GOM-kolonnen; den ble utledet som USA offshore i
Louisiana, Texas, Alabama og Mississippi – regelen gir nøyaktig BHs GOM-tall i
alle 149 uker i ukerapporten, og testes for hver ny rapport.

Manuelt (lokalt): legg filen i `inbox/` og kjør `python scripts/rigcount.py build`.
