# Energi på Stortinget

En egen nettside for å følge energisaker på Stortinget: saker til behandling,
spørsmål til energiministeren, høringer, frister og nyheter fra
Energidepartementet. Den har RSS-feed og fungerer på mobil og desktop.

Publiseres på GitHub Pages under `/energi/`
(<https://sheffielddivided.github.io/temp/energi/>).

```
energi/
  fetch.py             henter og bearbeider data (bare standardbiblioteket)
  ku.py                parsere for operatørenes konsekvensutredninger
  personer.py          profilkort for representanter
  site/data/personer.json      indeks over representanter (lastes ved oppstart)
  site/data/personer/<id>.json  ett profilkort per person (lastes ved klikk)
  site/index.html      nettsiden (vanlig HTML/CSS/JS, ingen byggesteg)
  site/app.js          visninger, filtre, søk, ruting (#/saker/123, #/horinger osv.)
  site/style.css       lyst og mørkt tema, mobil med bunnmeny
  site/data/energi.json  generert data
  site/feed.xml        generert RSS (siste 80 energihendelser)
  tests/               tester for parsere og generert data
```

## Datakilder

| Kilde | Hva | Merknad |
|---|---|---|
| `data.stortinget.no/eksport/saker`, `/sak` | saker, saksgang, frister, vedtak, dokumenter | inneværende og forrige sesjon |
| `…/skriftligesporsmal`, `/sporretimesporsmal`, `/interpellasjoner` | besvarte spørsmål | API-et har bare besvarte spørsmål |
| Stortingets RSS «spørsmål som venter besvarelse» (energiministeren) | ubesvarte spørsmål | fyller hullet i API-et |
| Stortingets RSS «hovedtema Energi» | saker Stortinget har merket med energi | fanger energisaker i andre komiteer |
| `…/horinger` | høringer i Energi- og miljøkomiteen | innspillsfrister, tidspunkt |
| `…/moter`, `/dagsorden` | når sakene står på dagsorden i plenum | 7 dager bakover, 45 dager fram |
| regjeringen.no RSS (`owner=750`) | nyheter og statsrådens program fra Energidepartementet | |
| regjeringen.no RSS (`documentType=dokumenter`, med og uten `owner=750`) | høringer fra Energidepartementet, og høringer om petroleum fra alle departementer | se under |
| `miljodirektoratet.no/hearingslistpage/gethearings` | Miljødirektoratets høringer med frist, saksnummer og emne | aktive høringer og nylig avsluttede innen olje og gass og klima |
| Equinor: `equinor.com/no/baerekraft/konsekvensutredninger` | KU-dokumenter per prosjekt (høringsbrev, programforslag, KU) | data leses fra den innebygde Next.js-strømmen; norske prosjekter |
| Vår Energi: `varenergi.no/no/var-virksomhet/konsekvensutredninger/` | pågående og gjennomførte KU-høringer med frist og datoer | HTML |
| Aker BP: `akerbp.com/wp-json/wp/v2/media` | KU-dokumenter med publiseringsdato (siste 18 mnd.) | WordPress-API |
| Stortingets RSS «Aktuelt-saker» | aktuelt fra Stortinget om energi, og «Uke NN på Stortinget» | vises under Nyheter |
| Stortingets RSS «Stortingsvedtak» | lenke til vedtaket i saker vi følger | |

### Høringer fra regjeringen.no

Eksportsiden for høringer (`/oversyn-over-hoyringssaker/id546535/Export`) er bak
Cloudflare-sperre og kan ikke hentes automatisk. Derfor brukes regjeringens
RSS-feeder for dokumenter:

- Høringer fra Energidepartementet tas med.
- Høringer fra alle departementer tas med når tittel eller ingress gjelder
  petroleum, olje og gass eller havindustri (`PETROLEUM_RE`).

Feeden for alle departementer viser bare de siste ~100 dokumentene. Derfor slås
nye treff sammen med det som er lagret fra før, slik at listen bygges opp over
tid. RSS har ikke høringsfrist. Fristen står på høringssiden, og siden lenker
dit.

### Høringer fra Miljødirektoratet

Høringer med emnet «Olje og gass» eller med energitema i tittelen regnes som
energi. Høringer med emnet «Klima» tas med, men vises bare når bryteren «Ta med
klima og miljø» er på.

### Konsekvensutredninger fra operatørene (`ku.py`)

KU-høringer for PUD/PAD og avslutningsplaner vises som egne kort under
Høringer → «Operatører (KU)», med de nyeste dokumentene og eventuell frist.

- **Vår Energi** oppgir frist og dato for hvert dokument.
- **Aker BP** har dato per dokument fra mediebiblioteket. Dokumentene grupperes
  per prosjekt ut fra tittelen (`akerbp_prosjekt`).
- **Equinor** har ikke datoer på siden. Dato hentes fra filnavnet når den står
  der, og ellers settes den til dagen dokumentet ble oppdaget første gang.
  Første kjøring får ingen slike datoer, slik at eldre dokumenter ikke ser nye
  ut.

Hver operatør hentes for seg. Hvis én feiler, beholdes forrige data for den.

### Profilkort for representanter (`personer.py`)

Når du klikker på et navn, åpnes et profilkort (`#/person/<id>`). Kortet viser:

- Grunndata: parti, fylke, alder, e-post og faste komiteer, fra
  `dagensrepresentanter`.
- Bilde, fra `personbilde`. Det hentes direkte fra Stortinget.
- Kodet biografi: perioder, verv på Stortinget, utdanning, arbeidserfaring,
  verv utenfor Stortinget og litteratur, fra `kodetbiografi`.
- Alle saker personen er forslagstiller eller saksordfører på, og alle
  spørsmål personen har stilt i inneværende og forrige sesjon, uansett tema.
  Energisakene er merket.

Biografiene caches i `energi/.cache/` (`actions/cache` i CI, ikke i git) og
fornyes etter 7 dager, høyst 60 per kjøring (`BIO_MAX`). Personfilene skrives
bare når innholdet endres.

### Hva regnes som en energisak?

- **Saker:** alle saker i Energi- og miljøkomiteen (`ENERGI`). Saker som bare
  gjelder klima og miljø vises når bryteren «Ta med klima og miljø» er slått på.
  Saker i andre komiteer tas med når korttittelen har energiord, eller når
  Stortinget har merket dem med hovedtema Energi.
- **Spørsmål:** alle spørsmål der energiministeren er spurt, rette vedkommende
  eller den som svarte. Energispørsmål til andre statsråder kan slås på med en
  egen bryter.
- Temaene (Strøm og nett, Vindkraft, Havvind, Olje og gass, …) settes ut fra
  nøkkelord i `TEMA` i `fetch.py`. Juster listen der hvis noe treffer feil.
  `tests/test_fetch.py` har eksempler på treff som skal og ikke skal slå ut.

## Oppdatering

`.github/workflows/energi.yml` kjører annenhver time fra kl. 06 til 22 norsk tid,
ved push til `energi/` og ved manuell start. Den gjør dette:

1. Kjører testene.
2. Kjører `fetch.py`. Hvis en kilde feiler, beholdes forrige data for den
   kilden, og siden viser en advarsel.
3. Committer `site/data` og `feed.xml` bare når innholdet er endret.
4. Publiserer hele Pages-nettstedet: rig count i roten og energisiden under
   `/energi/`.

Rig count-workflowen (`update.yml`) setter sammen nettstedet på samme måte, så
de to sidene ikke overskriver hverandre.

Lokalt:

```bash
python energi/fetch.py
cd energi/site && python -m http.server 8000   # åpne http://localhost:8000
python -m pytest -q energi/tests
```

## RSS

`feed.xml` inneholder nye saker, avgitte innstillinger, vedtak, spørsmål som
er stilt og besvart, og nyheter fra Energidepartementet. Bare energisaker er
med. Hver hendelse har en fast `guid`, så en RSS-leser viser den bare én gang.
