# Worldwide Rig Count

Månedlig import av Baker Hughes **Worldwide Rig Count** og en statisk nettside
(GitHub Pages) som visualiserer antall rigger per region og land.

```
raw/                 nedlastede xlsx-filer (nyeste brukes)
scripts/rigcount.py  fetch / ingest / build
data/                worldwide_long.csv – ryddig «long»-format
site/                nettsiden (index.html, app.js, style.css, data/worldwide.json)
tests/               parsertester
```

## Slik fungerer det

GitHub Action (`.github/workflows/update.yml`) kjører daglig dag 2–14 i hver
måned, ved push til `raw/`, `scripts/` eller `site/`, og manuelt:

1. `fetch` – henter rigcount.bakerhughes.com/intl-rig-count, finner
   Worldwide-lenken og laster ned filen hvis innholdet er nytt.
2. `build` – parser nyeste fil i `raw/` til `data/worldwide_long.csv` og
   `site/data/worldwide.json`.
3. Endringer committes, og `site/` publiseres til GitHub Pages.

## Viktig: Akamai-blokkering

Baker Hughes' rigcount-side ligger bak Akamai, som blokkerer mange
datasenter-IP-er. GitHub Actions-runnere vil derfor sannsynligvis få **403**.
Da gir `fetch` en advarsel, og siden bygges fra siste fil i `raw/`.

Manuell oppdatering (tar et minutt i måneden):

1. Last ned Worldwide Rig Count-filen fra
   https://rigcount.bakerhughes.com/intl-rig-count
2. Enten last den opp via GitHub-nettsiden til `raw/` med navnet
   `ÅÅÅÅ-MM-DD_worldwide.xlsx`, eller lokalt:
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

## Parseren

Excel-layouten fra Baker Hughes er ikke dokumentert og har endret seg før.
Parseren leter derfor etter overskriftsrader med månedsnavn/datoer, finner
år fra fane- eller titteltekst, og kjenner igjen seksjoner (Land/Offshore/Total),
regioner og land. Hvis `build` melder «Fant ingen data», må `_parse_sheet()`
justeres mot den faktiske filen.
