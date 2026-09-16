# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Börsen-Ratespiel — News, Wissen, ein Ratespiel und ein Musterdepot rund um die Börse, alles simuliert und ohne Risiko. Reines Vanilla HTML/CSS/JS ohne Build-Step und ohne Abhängigkeiten. Als installierbare PWA nutzbar (siehe unten).

## Running

Einfach `index.html` im Browser öffnen. Kein Build, kein Package-Manager, keine Tests vorhanden.

## Architecture

Die Single-Page-App (`index.html` + `style.css` + `script.js`) ist der Kern, dazu kommen PWA-Dateien und zwei rechtliche Standalone-Seiten:

- `index.html` — Seitenstruktur: ein Menü (`#menu`) zur Auswahl, plus je eine `<section class="view">` pro Feature (`#news-view`, `#learn-view`, `#game-view`, `#depot-view`)
- `style.css` — Theme via CSS-Variablen in `:root` (Farben für bg/panel/text/green/red/accent), Glassmorphism-Look (Blur, halbtransparente Panels), lokal gehostete Schriftart "Outfit" (siehe PWA-Abschnitt)
- `script.js` — Navigations-Logik + gesamte Spiellogik
- `manifest.json`, `sw.js`, `icons/`, `apple-touch-icon.png`, `favicon.png`, `fonts/` — PWA-Infrastruktur
- `impressum.html`, `datenschutz.html` — eigenständige Seiten (kein Teil der SPA-Navigation, verlinkt aus dem `.app-footer` in `index.html`), teilen sich aber `style.css` für den gleichen Look

**Navigation:** Die App startet auf dem Menü (`#menu`). Ein Klick auf einen `.menu-item[data-view]`-Button blendet das Menü aus und die passende `.view`-Section ein (per `hidden`-Klasse, siehe `script.js` oben). Der `.back-btn` in jeder View kehrt zum Menü zurück. Neue Features bekommen einfach eine weitere `.view`-Section plus einen Menüpunkt.

**Spielablauf in `script.js`** (Section `#game-view`):

1. `generateSeries()` erzeugt einen Kursverlauf als Random Walk mit Drift + Volatilität (Gaussian-verteilte Schocks über `gaussianRandom()`, Box-Muller-Transformation). Insgesamt `HISTORY_POINTS` (90) sichtbare Vergangenheitspunkte + `FUTURE_POINTS` (25) verdeckte Zukunftspunkte.
2. `draw(visibleCount, opts)` rendert den Verlauf auf dem `<canvas>` per 2D-Context — Gradient-Fläche + Glow unter/um die Linie, Vergangenheit in Blau, aufgedeckte Zukunft farbig je nach Ergebnis (grün/rot), getrennt durch eine gestrichelte Linie bei `HISTORY_POINTS`.
3. `newRound()` startet zusätzlich `startRoundTimer()` — ein `ROUND_TIME_MS` (6s) Countdown mit visueller Leiste (`#roundTimerBar`). Läuft die Zeit ab, wird die Runde automatisch als falsch gewertet (`revealAndScore(null, true)` — `null` kann nie `=== true/false` sein, daher immer `correct === false`).
4. Klick auf „Rauf“/„Runter“ triggert `revealAndScore()`, das den Timer stoppt und den Rest der Serie per `setInterval` (40ms/Frame) animiert aufdeckt, dann `showResult()` aufruft.
5. `showResult()` wertet Treffer/Serie/Bestserie aus. Punkte pro Treffer = `BASE_POINTS` (10) × Multiplikator aus `getMultiplier(streak)` (1× / 1.5× ab Serie 3 / 2× ab Serie 5 / 3× ab Serie 10, angezeigt als Badge). Bei Erreichen einer Serie aus `STREAK_MILESTONES` erscheint ein kurzer Toast (`showStreakToast()`). Bei Treffer zusätzlich `burstConfetti()`. Die Bestserie (`best`) wird in `localStorage` unter dem Key `boersenspiel_best` persistiert.

Wichtig: `newRound()`/der Rundentimer werden NICHT beim Laden der Seite gestartet, sondern erst wenn `#game-view` über das Menü geöffnet wird (`if (btn.dataset.view === 'game-view') newRound();` im Menü-Click-Handler oben in der Datei) — sonst würde der 6s-Timer schon unsichtbar im Hintergrund laufen, bevor der Nutzer das Spiel überhaupt sieht, und beim ersten Blick wäre die Runde eventuell schon durch Zeitablauf verloren. Verlassen der Ansicht über `.back-btn` stoppt den Timer über `clearRoundTimer()`.

**News (`#news-view`):** `NEWS_POOL` in `script.js` enthält 10 handkuratierte Meldungen (Kategorie, Sentiment bullish/bearish/neutral, Impact 1-3 Flammen). `renderNews()` zieht per `pickRandomNews(4)` eine zufällige Auswahl: die erste wird als große "🔥 Top Story"-Karte (`#newsTop`) hervorgehoben, der Rest als Liste (`#newsList`, `.info-list`-Layout wie gehabt). "🔀 Neue Meldungen" (`#newsShuffle`) ruft `renderNews()` erneut auf. Der Ticker (`#tickerTrack`) zeigt alle Schlagzeilen aus `NEWS_POOL` als endlos scrollenden Streifen (Inhalt doppelt aneinandergehängt + CSS-Animation `translateX(-50%)`, damit der Loop nahtlos wirkt). Es gibt keine echten Marktdaten — nirgendwo in der App sind es Live-Feeds, alles ist simuliert bzw. manuell zusammengefasst (siehe README).

**Lernen (`#learn-view`):** Multiple-Choice-Quiz mit drei Schwierigkeitsgraden (`LEVELS` in `script.js`: leicht/mittel/schwer, je 5 Fragen in `QUIZ_DATA`). Ablauf: Level-Auswahl (`#learnLevels`) → Quiz (`#learnQuiz`, 3 Leben, Punkte je nach Level, Fortschrittsbalken) → Ergebnis (`#learnResult`, mit Konfetti bei perfektem Lauf). `resetLearnView()` setzt die Ansicht beim erneuten Öffnen über das Menü immer auf die Level-Auswahl zurück, egal in welchem Quiz-Zustand man vorher war. Highscores pro Level werden unter `localStorage`-Key `boersenspiel_learn_best` persistiert.

Achtung: `.result-panel` hat eine EIGENE Animation (`resultPopIn`) statt der `popIn`-Keyframe vom `.banner` — `popIn` enthält `translate(-50%,-50%)`, was nur für das absolut-positionierte, zentrierte Banner Sinn ergibt. Eine geteilte Animation zwischen beiden hatte das Ergebnis-Panel in die obere linke Ecke verschoben.

**Musterdepot (`#depot-view`):** einfache Paper-Trading-Simulation. Startkapital `DEPOT_START_CASH` (10.000 €) plus vier fiktive Aktien (`DEPOT_STOCKS_DEFAULT`). „Kaufen“ investiert einen festen Betrag (`DEPOT_BUY_AMOUNT`, 500 €) zum aktuellen Kurs, „Verkaufen“ löst die komplette Position auf. Der komplette Depot-Zustand (Cash, Kurse, Positionen) wird als JSON unter `localStorage`-Key `boersenspiel_depot` persistiert, siehe `loadDepot()`/`saveDepot()`.

**Live-Modus im Depot:** „▶️ Simulation starten“ (`depotToggle`) startet `setInterval(tickDepotPrices, DEPOT_TICK_MS)` (1800ms) — Kurse bewegen sich automatisch per Random Walk, Kaufen/Verkaufen bleibt währenddessen über die normale Event-Delegation auf `#depotStocks` möglich (kein Re-Render blockiert Interaktion). `depotTrends` merkt sich pro Aktie die letzte Richtung (`up`/`down`) für die kurze Flash-Animation im Preis. „⏸ Pausieren“ oder Verlassen der Ansicht über `.back-btn` ruft `stopDepotLive()` auf, das den Timer beendet — sonst würde er unsichtbar im Hintergrund weiterlaufen. Beim Zurücksetzen des Depots wird der Timer ebenfalls gestoppt.

**KI-Berater (`#aiModal`, ausgelöst über `#aiAdvisorBtn` im Depot):** KEIN echter LLM-Aufruf — das ist bewusst so, weil diese App eine rein statische GitHub-Pages-Seite ohne Backend ist und ein API-Key eines LLM-Anbieters im öffentlichen Client-Code für jeden auslesbar/missbrauchbar wäre. Stattdessen wertet `generateDepotAdvice()` den tatsächlichen Depot-Zustand regelbasiert aus (Diversifikation über Anzahl gehaltener Aktien, Klumpenrisiko über den Anteil der größten Position am Depotwert, Cash-Quote, Rendite) und gibt daraus 3-4 passende, natürlich klingende Textbausteine zurück. `openAiAdvisor()` inszeniert das als Chat: erst eine "tippt..."-Bubble (`showTypingBubble`, ca. 1.1s), dann erscheinen die Nachrichten nacheinander leicht versetzt (450ms Abstand) als Sprechblasen. Der Disclaimer im Modal ("Regelbasierte Analyse... keine echte Anlageberatung") ist bewusst da, um nicht den Eindruck einer echten KI-Anlageberatung zu erwecken.

Die News-Ansicht hat ebenfalls ein KI-Element: `renderNewsAiFazit()` zählt bullish/bearish/neutral unter den 4 aktuell angezeigten Meldungen und generiert daraus einen Ein-Zeiler ("🤖 KI-Fazit ..."), der bei jedem `renderNews()`-Aufruf (inkl. "Neue Meldungen") neu berechnet wird.

Beide KI-Features nutzen eine eigene Akzentfarbe (`--ai: #22d3ee`, cyan) statt der bestehenden Blau/Lila/Grün-Palette, damit "das ist der KI-Teil" auf den ersten Blick erkennbar ist (Badge, Button-Glow, Chat-Bubbles).

**Boot-Splash (`#bootSplash`):** Kurze "KI-System wird initialisiert..."-Animation (~1.3s) beim allerersten Laden der Seite pro Browser-Tab, passend zur AI/Tech-Optik. Zwei Mechanismen verhindern ein Aufblitzen bei wiederholten Ladevorgängen in derselben Session:

1. Ein **inline `<script>` direkt nach dem `#bootSplash`-Markup** (noch vor `bg-grid`/`bg-glow`) prüft synchron, BEVOR der Browser irgendetwas rendert, ob `sessionStorage['boersenspiel_booted']` gesetzt ist, und setzt in dem Fall sofort `display:none` — ohne diesen Trick gäbe es bei jedem Reload einen kurzen Frame, in dem der Splash unnötig aufblitzt.
2. `script.js` (ganz oben, vor allem anderen Code) liest denselben Zustand aus: nur beim allerersten Laden läuft die volle Sequenz (Timer, `hide`-Klasse für den Fade-out, danach `remove()`), bei jedem weiteren Laden in derselben Session wird das Element sofort ohne Animation entfernt.

Der Flag ist `sessionStorage`, nicht `localStorage` — der Splash soll bei jedem neuen Tab/Session-Start wieder einmal laufen, nicht nur beim allerersten Besuch überhaupt.

**PWA (Progressive Web App):** `manifest.json` (Name, Icons, `display: standalone`, Theme-Farbe) + `sw.js` (Service Worker) machen die App installierbar ("Zum Home-Bildschirm hinzufügen"/"App installieren") und offline-fähig. Der Service Worker cached die App-Shell (`index.html`, `style.css`, `script.js`, Icons) beim ersten Laden cache-first mit Netzwerk-Fallback (siehe `sw.js`), registriert wird er ganz am Ende von `script.js` nach `window.onload`. Icons liegen unter `icons/icon-192.png` und `icons/icon-512.png` (plus `apple-touch-icon.png` für iOS und `favicon.png`) — alle aus einer einzigen 512×512-Canvas-Zeichnung (Gradient + 📈-Emoji) per `sips` auf die jeweilige Größe herunterskaliert, da auf der Maschine keine Bildbearbeitungstools (ImageMagick/Pillow) installiert sind. Das ist noch keine echte App-Store-Veröffentlichung, nur der PWA-Zwischenschritt dahin (siehe README).

**Social-Media-Vorschau:** `og-image.jpg` (1200×630, per Canvas gezeichnet und mit `sips` als JPEG statt PNG exportiert — deutlich kleinere Datei bei gleicher Bildqualität für einen Gradient-Hintergrund) wird über Open-Graph-/Twitter-Card-Meta-Tags in `index.html` eingebunden, damit geteilte Links (WhatsApp, Twitter/X, etc.) mit Bild + Beschreibung statt nacktem Link angezeigt werden. `og:image`/`og:url`/der `<link rel="canonical">` sind auf die GitHub-Pages-URL (`https://boersen-ratespiel.github.io/`) hartkodiert — falls die Seite unter einer anderen URL landet, müssen diese Tags angepasst werden.

**Repo-Standort:** liegt seit 2026-09-16 bei `boersen-ratespiel/boersen-ratespiel.github.io` (nicht mehr `WM-Predit/boersen-ratespiel`). Für die kurze, unterordnerlose GitHub-Pages-URL waren zwei Schritte nötig: erst eine eigene Organisation `boersen-ratespiel` anlegen (eine Org allein reicht NICHT, das ergäbe nur `boersen-ratespiel.github.io/boersen-ratespiel/`), dann das Repo darin zusätzlich auf den exakten Spezialnamen `boersen-ratespiel.github.io` umbenennen — erst dieser exakte Repo-Name triggert GitHubs "User/Org-Site"-Sonderfall (Root-URL statt Projekt-Site-Unterordner). Details siehe Memory [[project-github-setup]].

**SEO-Basics:** `robots.txt` (erlaubt alles, verweist auf `sitemap.xml`) und `sitemap.xml` (listet `index.html`, `impressum.html`, `datenschutz.html`) wurden beim Live-Start ergänzt. `impressum.html`/`datenschutz.html` tragen zusätzlich `<meta name="robots" content="noindex">`, damit Suchmaschinen nur die eigentliche App indexieren, nicht die Rechtsseiten.

**Analytics (GoatCounter):** Ein `<script data-goatcounter="https://boersen-ratespiel.goatcounter.com/count" ...>`-Snippet in `index.html` zählt Besuche — bewusst GoatCounter statt Google Analytics gewählt, weil es keine Cookies setzt und keine IP-Adressen speichert (siehe Erklärung in `datenschutz.html`, Abschnitt "Reichweitenmessung"). Das Skript ignoriert `localhost` automatisch (loggt eine Konsolen-Warnung statt zu zählen) — beim lokalen Testen ist das erwartetes, kein fehlerhaftes Verhalten. Dashboard: https://boersen-ratespiel.goatcounter.com (Login bei Max).

Falls das Dashboard nach dem Launch weiter "Keine Daten empfangen" zeigt, obwohl das Skript korrekt eingebunden ist (Ad-Blocker/Inkognito ausgeschlossen): zuerst prüfen, ob die GoatCounter-Bestätigungsmail angeklickt wurde — ein unbestätigter Account hat bei uns tatsächlich keine Daten gezählt, obwohl alles technisch korrekt konfiguriert war. War die eigentliche Ursache am 2026-09-16, keine Werbeblocker-Sache.

Die Schriftart "Outfit" wurde bewusst von Google Fonts auf lokal gehostet umgestellt (`fonts/outfit-variable.woff2`, eingebunden über `@font-face` in `style.css`): Das dynamische Nachladen von Google Fonts überträgt beim Seitenaufruf die IP-Adresse des Besuchers an Google (USA) — das gilt in Deutschland als DSGVO-Risiko (siehe u. a. LG München I, 2022) und wurde vor dem geplanten Live-Start entfernt. Die Datei ist eine Variable-Font-Version, die alle Schriftschnitte (400–800) in einer einzigen ~32 KB großen Datei abdeckt.

## Achtung: lokaler Test-Server cached script.js

`python3 -m http.server` sendet keine `Cache-Control`-Header. Chrome cached `script.js` deshalb teils ohne jede Nachfrage (kein Log-Eintrag, kein 304) über mehrere Reloads hinweg, während `index.html`/`style.css` normal revalidiert werden. Wenn Änderungen an `script.js` im Preview nicht ankommen, obwohl die Datei auf der Platte korrekt ist: harter Reload reicht oft nicht — zur Sicherheit den Server auf einem neuen Port neu starten (neue Origin = garantiert kein Cache-Treffer).

**Noch wichtiger seit dem Service Worker (`sw.js`):** Sobald eine Origin (z. B. `http://localhost:8814`) einmal besucht wurde, registriert sich der Service Worker und cached `index.html` in der Cache Storage API. Ab dann liefert JEDER weitere Request auf diese Origin — auch `fetch(url, {cache: 'no-store'})` — die alte, gecachte Version aus, komplett unabhängig vom `python3 -m http.server`-Prozess und selbst wenn dieser Prozess neu gestartet wird. Ein `preview_start` mit demselben Port kann außerdem "reused: true" melden und einen alten, noch laufenden Prozess auf diesem Port weiterverwenden, statt die (evtl. geänderte) Port-Konfiguration aus `launch.json` neu zu lesen. Sicherster Weg beim Testen von Änderungen, die den Service Worker/die App-Shell betreffen: einen Port verwenden, der in dieser Session noch NIE besucht wurde (nicht nur "neu gestartet") — sonst testet man garantiert eine Cache-Leiche statt des aktuellen Codes.
