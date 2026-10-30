# 📈 Börsen-Ratespiel

News, Wissen, Spiel & Musterdepot — ein kleiner, spielerischer Einstieg in die Börse, ganz ohne Risiko und ohne echtes Geld.

## Bereiche

- **🗓️ Tages-Challenge** — jeden Tag dieselben 5 Kursverläufe für alle Spieler, ein Versuch pro Tag. Das Ergebnis lässt sich als Emoji-Zeile (z. B. 🟩🟩🟥🟩🟩 4/5) per WhatsApp & Co. teilen, dazu gibt es eine Serie für Tage in Folge, eine Statistik wie bei Wordle und ein Ergebnisbild für Instagram-Storys.
- **🧭 Lernpfad** — sechs Schritte für Einsteiger quer durch die App, die sich automatisch abhaken.
- **📰 News** — aktuelle Wirtschaftsmeldungen vom [Statistischen Bundesamt](https://www.destatis.de/) und der [Europäischen Zentralbank](https://www.ecb.europa.eu/) (stündlich per GitHub Action aktualisiert), mit Thema, Richtung der gemeldeten Zahl (📈/📉), Relevanz, Quellenangabe und Link zum Original, plus laufendem Ticker. Wenn die News nicht geladen werden können, erscheinen klar gekennzeichnete Beispielmeldungen.
- **📚 Lernen** — Multiple-Choice-Quiz zu Investment-Grundlagen in drei Schwierigkeitsgraden (Leicht/Mittel/Schwer) mit je 20 Fragen, von denen pro Durchlauf 10 zufällig gezogen werden. Mit Leben, Punkten, Highscores und Links ins Lexikon.
- **📈📉 Rauf oder Runter** — du siehst einen simulierten Kursverlauf und tippst, ob es als Nächstes rauf oder runter geht. Mit Countdown, Streak-Multiplikator und Konfetti bei einer heißen Serie.
- **💼 Musterdepot** — virtuelles Startkapital, fiktive Aktien kaufen/verkaufen, optional live mitverfolgen, wie sich die Kurse bewegen.
  Mit „Sparplan üben" läuft ein virtueller ETF-Sparplan, bei dem man Monate und Jahre vorspulen kann.
- **🌱 Sparplan-Rechner** — Sparrate, Startbetrag, Laufzeit und angenommene Rendite einstellen und sehen, was mit Zinseszins daraus werden kann (optional in heutiger Kaufkraft).
- **📖 Börsen-Lexikon** — 38 Fachbegriffe einfach erklärt, mit Suche. Quiz und News verlinken direkt auf die passenden Einträge. Jeder Begriff hat zusätzlich eine eigene Seite unter `/lexikon/` (für Suchmaschinen).
- **🏅 Erfolge** — 17 Abzeichen quer durch alle Bereiche.
- **🏦 Echtes Depot eröffnen?** — Checkliste, worauf man bei einem Broker achten sollte, plus gekennzeichnete Partnerlinks.

Jeder Bereich hat einen Direktlink, z. B. `https://boersen-ratespiel.github.io/#challenge`, `#sparplan` oder `#lexikon`.

## Spielen

Einfach [`index.html`](index.html) im Browser öffnen — kein Build-Step, keine Abhängigkeiten.

## Installieren (PWA)

Die App ist eine Progressive Web App: über "Zum Home-Bildschirm hinzufügen" (iOS Safari) bzw. "App installieren" (Android Chrome, Desktop-Browser) lässt sie sich wie eine echte App installieren — mit eigenem Icon und ohne Browser-Leiste. Ein Service Worker (`sw.js`) cached die App-Shell, sodass sie danach auch offline startet. Das ist (noch) keine Veröffentlichung im Apple App Store oder Google Play Store, aber der einfachste Weg zu einem "App-Gefühl" ganz ohne Store-Anmeldung oder Review-Prozess.

## Dateien

| Datei | Zweck |
|---|---|
| `index.html` | Seitenstruktur, alle Bereiche als eigene Views (inkl. Lexikon-Texten) |
| `style.css` | Theme, Glassmorphism-Look, Animationen |
| `script.js` | Navigation + Logik aller Bereiche |
| `news.json` | Aktuelle Meldungen, wird automatisch von `scripts/update_news.py` geschrieben (nicht von Hand ändern) |
| `scripts/update_news.py` | Holt die RSS-Feeds von Destatis und EZB und erzeugt `news.json` (nur Python-Standardbibliothek) |
| `.github/workflows/update-news.yml` | Führt das Skript stündlich aus und committet `news.json` bei Änderungen |
| `scripts/build_lexikon.py` | Erzeugt beim Deploy die Lexikon-Einzelseiten und `sitemap.xml` |
| `.github/workflows/deploy-pages.yml` | Veröffentlicht die Seite auf GitHub Pages |
| `scripts/build_tiktok.py`, `scripts/tiktok/render.html` | Zeichnen beim Deploy die Bilder für den täglichen TikTok-Beitrag (Kurs-Rätsel, Quizfrage, Börsen-Begriff) |
| `scripts/tiktok_post.py`, `.github/workflows/tiktok-post.yml` | Postet den Beitrag täglich über die TikTok-API (Einrichtung: `scripts/tiktok_auth.py`, Details in `CLAUDE.md`) |
| `manifest.json`, `sw.js` | PWA-Manifest und Service Worker |
| `icons/`, `apple-touch-icon.png`, `favicon.png` | App-Icons |
| `fonts/` | Lokal gehostete Schriftart (kein Google-Fonts-Aufruf) |
| `impressum.html`, `datenschutz.html` | Rechtliche Pflichtseiten |

Mehr Details zur Architektur stehen in [`CLAUDE.md`](CLAUDE.md).

## Hinweis

Alle Kursverläufe und Aktien (Spiel und Musterdepot) sind rein zufällig simuliert und stellen **keine echten Marktdaten** dar. Die News stammen vom Statistischen Bundesamt und der EZB; Thema, Richtung der Zahl und Relevanz leitet die App automatisch aus dem Text ab (keine Kursprognose). Die App dient nur zum Üben des eigenen Gespürs für Trends, Volatilität und Grundlagenwissen — sie ist **keine Anlageberatung**.

