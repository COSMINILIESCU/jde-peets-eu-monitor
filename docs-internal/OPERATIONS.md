# Proceduri de operare (pentru Cosmin — fără cunoștințe tehnice)

Dashboard public: **https://cosminiliescu.github.io/jde-peets-eu-monitor/**
Totul de mai jos se rulează din PowerShell, din folderul proiectului:
`cd "C:\Users\CI\CLAUDE CODE\jde-peets-eu-monitor"`

## Ce se întâmplă automat
- **Luni, 07:00** — rularea săptămânală completă (colectare → analiză AI → publicare pe dashboard).
  Dacă PC-ul e oprit, rularea pornește automat la prima pornire a PC-ului.
- **Prima zi de luni din lună, 08:00** — scout-ul de surse noi.
- Nu trebuie să faceți nimic. Dashboardul se actualizează singur în ~2 minute după rulare.

## Verificări rapide
| Vreau să… | Fac așa |
|---|---|
| Văd dacă rularea de luni a mers | Deschid dashboardul → data din antet („Last updated…") e din ziua curentă |
| Văd raportul rulării | Deschid cel mai nou fișier `logs\report_*.json` (dublu-click) |
| Pornesc o actualizare acum | `python scripts\run_weekly.py` |
| Retrag ultima publicare (a apărut ceva greșit) | `python scripts\rollback.py` |
| Aprob sursele propuse de scout | Deschid `sources\registry.yaml`, caut `pending_approval` și schimb în `active` (sau `rejected`), apoi la următoarea rulare intră în funcțiune |
| Repar surse care tot eșuează | `python scripts\run_specialist.py` |

## Probleme frecvente
- **Dashboardul nu s-a actualizat luni.** PC-ul era oprit? Rularea pornește la următoarea pornire —
  așteptați ~1 oră după pornirea PC-ului, apoi verificați din nou. Dacă tot nimic:
  `python scripts\run_weekly.py` manual și citiți ultimele linii afișate.
- **„Not logged in" în raport (analiza AI a eșuat).** Rulați `claude` în PowerShell, tastați `/login`,
  autentificați-vă în browser, închideți cu `exit`. Elementele neanalizate se reiau automat la
  următoarea rulare.
- **GitHub cere autentificare la publicare.** Rulați `gh auth login` și urmați pașii din browser.
- **Vreau să văd dashboardul înainte de publicare.** `python scripts\run_weekly.py --no-publish`,
  apoi deschideți `docs\index.html` printr-un server local (sau cereți asistentului „pornește
  previzualizarea dashboardului JDE").

## Reguli de siguranță
- Nu editați manual fișierele din `docs\data\` (se regenerează automat).
- Nu ștergeți `data\monitor.db` — e arhiva completă. Backup automat în `data\backup\` (ultimele 8).
- Fișierul `.env` (dacă va conține vreodată chei) nu se urcă niciodată pe GitHub — e deja protejat.
