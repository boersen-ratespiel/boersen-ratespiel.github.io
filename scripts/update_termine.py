#!/usr/bin/env python3
"""Holt die anstehenden Wirtschaftstermine der nächsten Tage aus frei nutzbaren Quellen und schreibt termine.json.

Quellen (Nutzungsbedingungen jeweils geprüft, siehe CLAUDE.md):
  - Statistisches Bundesamt (Destatis), Wochenvorschau: "Vervielfältigung und Verbreitung ... mit Quellennachweis gestattet"
  - U.S. Bureau of Economic Analysis (BEA), Veröffentlichungskalender (iCal): Public Domain
  - Europäische Zentralbank (EZB), Sitzungskalender des EZB-Rats: freie Nutzung mit Quellenangabe, korrekte Wiedergabe
  - U.S. Federal Reserve Board, FOMC-Sitzungskalender: Public Domain

Bewusst NICHT enthalten: ifo, Einkaufsmanagerindizes (S&P Global), Uni-Michigan-Index, US-Arbeitsmarktdaten (BLS
sperrt automatische Abrufe) und Quartalszahlen von Unternehmen — dafür gibt es keine frei nutzbare Quelle.

Läuft zusammen mit update_news.py per GitHub Action. Nur Standardbibliothek. termine.json wird nur neu geschrieben,
wenn sich die Termine geändert haben; schlägt jeder Abruf fehl, bleibt die alte Datei liegen (Exit 1).
"""

import html
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from update_news import HIGH_IMPACT, RELEVANT, clean_text, contains, fetch

BERLIN = ZoneInfo('Europe/Berlin')
WASHINGTON = ZoneInfo('America/New_York')
DAYS_AHEAD = 14  # die App zeigt davon nur die nächsten 7 Tage, der Rest ist Puffer, falls die Action mal ausfällt
OUT_FILE = Path(__file__).resolve().parent.parent / 'termine.json'

DESTATIS_URL = 'https://www.destatis.de/DE/Presse/Wochenvorschau/_inhalt.html'
BEA_ICS_URL = 'https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics'
BEA_PAGE_URL = 'https://www.bea.gov/news/schedule'
ECB_URL = 'https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html'
FOMC_URL = 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'

MONTHS_DE = ['januar', 'februar', 'märz', 'april', 'mai', 'juni', 'juli', 'august', 'september', 'oktober',
             'november', 'dezember']
MONTHS_EN = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october',
             'november', 'december']

# Nur die BEA-Veröffentlichungen, die an der Börse beachtet werden. `hint` ist eine Erklärung der App, kein Quellentext.
BEA_RELEASES = [
    ('gdp', 'US-Wirtschaftsleistung (BIP)', True),
    ('gross domestic product', 'US-Wirtschaftsleistung (BIP)', True),
    ('personal income and outlays', 'Einkommen und Konsum in den USA, inkl. PCE-Inflation (wichtigstes Inflationsmaß der Fed)', True),
    ('international trade in goods and services', 'Außenhandel der USA', False),
]


def parse_destatis(page):
    """Tabelle der Wochenvorschau: Nr. | EVAS | Pressemitteilung | Berichtszeitraum | Erscheinungstermin."""
    body = page.split('<tbody', 1)[-1].split('</tbody>', 1)[0]
    for row in re.findall(r'<tr.*?</tr>', body, flags=re.S):
        cells = [clean_text(c) for c in re.findall(r'<td[^>]*>(.*?)</td>', row, flags=re.S)]
        if len(cells) < 5 or cells[2].startswith('Zahl der Woche'):
            continue
        title, period, when = cells[2], cells[3], cells[4]
        m = re.match(r'(\d{1,2})\.\s*(\w+)\s+(\d{4})', when)
        if not m or m.group(2).lower() not in MONTHS_DE:
            continue
        if not contains(title.lower(), RELEVANT):
            continue
        yield {
            'date': date(int(m.group(3)), MONTHS_DE.index(m.group(2).lower()) + 1, int(m.group(1))),
            'time': '08:00',  # laut Destatis "im Allgemeinen um 8:00 Uhr"
            'title': title,
            'period': period,
            'hint': '',
            'region': 'DE',
            'key': contains(title.lower(), HIGH_IMPACT),
            'source': 'Statistisches Bundesamt (Destatis)',
            'lang': 'de',
            'url': DESTATIS_URL,
        }


def parse_bea(ics):
    text = re.sub(r'\r?\n[ \t]', '', ics.replace('\r\n', '\n'))  # iCal-Zeilenumbrüche ("folding") auflösen
    for block in re.findall(r'BEGIN:VEVENT\n(.*?)END:VEVENT', text, flags=re.S):
        fields = {}
        for line in block.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                fields[key.split(';', 1)[0]] = value
        title = fields.get('SUMMARY', '').replace('\\,', ',').replace('\\;', ';').strip()
        start = fields.get('DTSTART', '')
        match = next(((hint, key) for word, hint, key in BEA_RELEASES if word in title.lower()), None)
        if not match or not re.fullmatch(r'\d{8}T\d{6}Z', start):
            continue
        when = datetime.strptime(start, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).astimezone(BERLIN)
        yield {
            'date': when.date(),
            'time': when.strftime('%H:%M'),
            'title': title,
            'period': '',
            'hint': match[0],
            'region': 'US',
            'key': match[1],
            'source': 'U.S. Bureau of Economic Analysis (BEA)',
            'lang': 'en',
            'url': BEA_PAGE_URL,
        }


def parse_ecb(page):
    """Nur die Tage mit geldpolitischem Beschluss: geldpolitische Sitzung, "followed by press conference"."""
    main = page.split('<main', 1)[-1]
    for day, month, year, raw in re.findall(r'<dt>\s*(\d{2})/(\d{2})/(\d{4})\s*</dt>\s*<dd>(.*?)</dd>', main, flags=re.S):
        title = clean_text(raw)
        low = title.lower()
        if 'monetary policy meeting' not in low or 'non-monetary' in low or 'press conference' not in low:
            continue
        yield {
            'date': date(int(year), int(month), int(day)),
            'time': '',
            'title': title,
            'period': '',
            'hint': 'Zinsentscheid der Europäischen Zentralbank',
            'region': 'EU',
            'key': True,
            'source': 'Europäische Zentralbank (EZB)',
            'lang': 'en',
            'url': ECB_URL,
        }


def parse_fomc(page):
    """Die Fed verkündet ihren Zinsentscheid am letzten Sitzungstag. Titel stammt von der App (Quelle: Public Domain)."""
    for year, section in re.findall(r'>(\d{4}) FOMC Meetings</a>(.*?)(?=>\d{4} FOMC Meetings</a>|$)', page, flags=re.S):
        pairs = re.findall(r'fomc-meeting__month[^>]*>\s*<strong>([A-Za-z/]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<',
                           section, flags=re.S)
        for month_raw, days_raw in pairs:
            months = [m.lower() for m in month_raw.split('/')]
            days = re.findall(r'\d{1,2}', days_raw)
            if not days or months[-1] not in MONTHS_EN or '(notation vote)' in days_raw.lower():
                continue
            # Das Statement erscheint um 14:00 Uhr Washingtoner Zeit, umgerechnet inkl. unterschiedlicher Zeitumstellung
            when = datetime(int(year), MONTHS_EN.index(months[-1]) + 1, int(days[-1]), 14, 0, tzinfo=WASHINGTON).astimezone(BERLIN)
            yield {
                'date': when.date(),
                'time': when.strftime('%H:%M'),
                'title': 'US-Notenbank (Fed): Zinsentscheid',
                'period': '',
                'hint': '',
                'region': 'US',
                'key': True,
                'source': 'U.S. Federal Reserve Board',
                'lang': 'de',
                'url': FOMC_URL,
            }


SOURCES = [
    ('Destatis', DESTATIS_URL, parse_destatis),
    ('BEA', BEA_ICS_URL, parse_bea),
    ('EZB', ECB_URL, parse_ecb),
    ('Fed', FOMC_URL, parse_fomc),
]


def build_items():
    today = datetime.now(BERLIN).date()
    last = today + timedelta(days=DAYS_AHEAD)
    items, failures = [], 0
    for name, url, parser in SOURCES:
        try:
            found = [e for e in parser(fetch(url).decode('utf-8', errors='replace')) if today <= e['date'] <= last]
            print(f'{name}: {len(found)} Termine')
            items.extend(found)
        except Exception as exc:  # eine kaputte Quelle soll die anderen nicht mitreißen
            failures += 1
            print(f'Quelle fehlgeschlagen: {name}: {exc}', file=sys.stderr)
    if failures == len(SOURCES):
        return None

    unique = {(e['date'], e['title']): e for e in items}
    result = []
    for e in sorted(unique.values(), key=lambda e: (e['date'], e['time'] or '99:99', e['title'])):
        result.append({**e, 'date': e['date'].isoformat(), 'title': html.unescape(e['title'])})
    return result


def main():
    items = build_items()
    if items is None:
        print('Keine Quelle erreichbar — termine.json bleibt unverändert.', file=sys.stderr)
        return 1

    if OUT_FILE.exists():
        try:
            if json.loads(OUT_FILE.read_text(encoding='utf-8')).get('items') == items:
                print('Keine neuen Termine.')
                return 0
        except (ValueError, OSError):
            pass

    payload = {
        'updated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'items': items,
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(items)} Termine geschrieben.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
