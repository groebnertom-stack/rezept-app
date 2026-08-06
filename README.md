# Rezept-App der Familie

Streamlit-Oberfläche für die Notion-Datenbank „Rezepte“. Sie liest die strukturierten
Zutatenlisten, rechnet Mengen live auf jede Zielmenge hoch, beantwortet Freitextfragen
über die Sammlung und kann neue Rezepte per LLM ins Zielschema übersetzen.

## Was drin ist

| Reiter | Funktion |
| --- | --- |
| **Kochen** | Rezept suchen oder auswählen, Menge skalieren, Einkaufsliste kopieren, Zufallsrezept würfeln |
| **Fragen** | Freitext-Chat mit Claude über die gesamte Sammlung („Was kann ich aus Kartoffeln kochen?“) |
| **Verarbeiten** | Rezepte mit Status „nicht verarbeitet“ scrapen, extrahieren, zurück nach Notion schreiben |
| **Fehler** | Problemfälle sichten, Rezepttext manuell nachtragen, sofort neu verarbeiten |

Die beiden schreibenden Reiter erscheinen nur bei aktivem Schreibzugriff (siehe unten).

## Dateien

```
app.py               Streamlit-UI, alle vier Reiter
models.py            Datenmodell, JSON:-Parsing, Skalierungslogik (LLM-frei)
notion_repo.py       Notion lesen und schreiben, Rich-Text-Chunking
llm.py               Claude für Chat und Zutaten-Extraktion
scraper.py           schema.org-Recipe-JSON-LD, Fallback auf Fließtext
theme.py             Farben, Typografie, CSS
test_models.py       Parsing, Skalierung, Rundung, Filter
test_integration.py  LLM-Antworten, Notion-Serialisierung, Scraping
test_kategorien.py   Kategorisierung und einheitenabhängiges Runden
_uitest.py           End-to-End-Render-Test aller Reiter mit Fake-Notion
_realdata_check.py   Skalierung gegen die echten Notion-Daten
```

## Lokal starten

```bash
pip install -r requirements.txt
cp .env.example .env      # Token eintragen
streamlit run app.py
```

Tests:

```bash
python -m pytest -q        # 89 Tests
python _uitest.py          # UI-Render-Test
python _realdata_check.py  # Skalierung gegen echte Rezeptdaten
python notion_check.py     # Diagnose des Notion-Zugangs
```

## Konfiguration

Lokal aus `.env`, in der Cloud aus den App-Secrets — beides landet in denselben Variablen.

| Variable | Pflicht | Bedeutung |
| --- | --- | --- |
| `NOTION_TOKEN` | ja | Secret der internen Notion-Integration |
| `NOTION_DATABASE_ID` | ja | `5ef6746d9a144974a0fbb499f845100f` |
| `ANTHROPIC_API_KEY` | ja | Key von console.anthropic.com |
| `ANTHROPIC_MODEL` | nein | Modell der Extraktion, Standard `claude-sonnet-5` |
| `ANTHROPIC_CHAT_MODEL` | nein | Modell des Chats, Standard `claude-haiku-4-5` |
| `REZEPTE_SCHREIBZUGRIFF` | nein | `true` blendet „Verarbeiten“ und „Fehler“ ein. **Standard `false`** |
| `REZEPTE_CHAT_LIMIT` | nein | LLM-Fragen pro Browser-Sitzung, Standard `25`, `0` = kein Limit |

## Technische Eigenheiten

**`JSON:`-Präfix.** Notion interpretiert einen Textwert, der wie gültiges JSON aussieht,
als Objekt und lehnt ihn beim Schreiben ab. Deshalb steht vor jedem Zutaten-JSON das
Präfix `JSON:`, das beim Lesen entfernt wird (`models.zutaten_json_parsen`).

**2000-Zeichen-Blöcke.** Notion zerlegt lange Textwerte in Rich-Text-Blöcke. Wer nur den
ersten Block liest, schneidet längeres JSON ab. `notion_repo` fügt beim Lesen alle Blöcke
zusammen und stückelt beim Schreiben entsprechend.

**`basis_einheit` ist nicht „Personen“.** Das Skalierungsfeld beschriftet sich aus den
Daten: „Anzahl Semmeln“, „Anzahl Gläser (à 250 ml)“, „Anzahl Burritos“.

**Skalierung ohne LLM.** Faktor = Zielmenge ÷ Basismenge, rein lokal gerechnet. Zutaten
mit `skalierbar: false` bleiben unverändert („Prise Salz”).

**Runden nach Einheit.** Wie gerundet wird, hängt davon ab, was man abmessen kann:

| Einheit | Schritt | Beispiel |
| --- | --- | --- |
| Stück, Dose, Bund, Zehen … | halbe | 0,75 Gewürznelken → 1 Stück |
| TL, EL, Msp. | viertel | 0,12 TL Kardamom → ¼ TL |
| g, ml, kg, l | nach Größenordnung | 1234,7 g → 1235 g |

Unterhalb der jeweiligen Schwelle steht „etwas” statt einer Zahl — niemand wiegt 0,06
Knollensellerie ab. Brüche werden als ½ ¼ ¾ gesetzt, nicht als 0,5 / 0,25 / 0,75.

**Kategorien.** Jedes Rezept wird einer von acht Kategorien zugeordnet: Hauptgericht,
Suppe, Salat, Beilage, Nachspeise, Gebäck, Eingemachtes, Getränk. Die Extraktion setzt
sie mit; für Rezepte aus der Zeit davor greift eine Heuristik aus Titel und Basiseinheit
(`kategorie_raten`), erkennbar am `?` hinter dem Kategorie-Label in der UI.

Der Würfel zieht nur aus Hauptgericht, Suppe und Salat — sonst schlägt er
Holunderblütengelee als Abendessen vor. Filtert man ausdrücklich nach einer Kategorie,
würfelt er innerhalb dieser Auswahl.

Die Heuristik prüft auf Wortenden, nicht auf Teilstrings: „Hühner**suppe**” wird als
Suppe erkannt, „**Pesto**fisch” aber nicht als Eingemachtes und „Ofenlachs mit R**eis**”
nicht als Nachspeise.

**Filter beim Würfeln.** Neben der Kategorie gibt es drei weitere Filter, die sich
mit ihr und mit der Suche kombinieren lassen:

| Filter | Bedingung |
| --- | --- |
| ⚡ Muss schnell gehen | `zeit_minuten` ≤ 30 |
| ⏳ Ich hab Zeit | `zeit_minuten` ≥ 60 |
| 🌱 Vegetarisch | keine Fleisch- oder Fischzutat |

Zeit ist ein Umschalter, kein Paar Häkchen — beides gleichzeitig hätte garantiert
null Treffer. Rezepte zwischen 31 und 59 Minuten fallen bewusst in keinen der
beiden Töpfe, ebenso Rezepte ohne Zeitangabe in der Quelle.

**Zwei echte Notion-Properties: `Vegetarisch` und `Zeitaufwand`.** Beide sind
Select-Felder, kein Checkbox/Zahl — ein leeres Select bleibt als „noch nicht
bewertet” von einem gesetzten Wert unterscheidbar. `Vegetarisch` hat die Werte
`ja`/`nein`, `Zeitaufwand` die Werte `Schnell`/`Ich hab Zeit`. Ist ein Label
gesetzt, hat es in der App Vorrang vor jeder Berechnung — wer in Notion von Hand
korrigiert, wird nicht überstimmt. Ist es leer, greift bei Vegetarisch die
Heuristik (`vegetarisch_geraten`) und bei der Zeit die Rechnung aus
`zeit_minuten`. So lässt sich auch ein Rezept ganz ohne Zeitangabe in Notion von
Hand einsortieren.

Frisch verarbeitete Rezepte bekommen beide Labels automatisch mit
(`app.labels_nachziehen`). Für den Altbestand einmalig:

```bash
python3 labels_setzen.py              # Trockenlauf, zeigt nur was passieren würde
python3 labels_setzen.py --schreiben  # legt die Properties an, falls sie fehlen, und setzt die Labels
```

Ein bereits gesetztes `Vegetarisch`-Label wird dabei **nicht** überschrieben —
`--neu-bewerten` hebt das für einen erneuten Durchgang auf. `Zeitaufwand` ist
reine Ableitung aus `zeit_minuten` und wird deshalb immer auf den Sollwert
gebracht.

**Die Heuristik ist geraten, nicht unfehlbar.** `vegetarisch_geraten` prüft die
Zutatennamen gegen eine Liste von Fleisch- und Fischstämmen — ohne LLM, wie bei
`kategorie_raten`. Deutsche Komposita machen das heikel: „Rinder­brühe” ist
Fleisch, „Fleisch­tomate”, „speckige Erdäpfel” und „Frucht­fleisch” sind es
nicht. Solche Fälle stehen in `_VEGETARISCHE_AUSNAHMEN`. Mehrdeutige Stämme
(`hack` in „gehackte Tomaten”, `herz` in „Artischockenherzen”) sind gar nicht
erst in der Liste. Verdeckt Tierisches — Worcestersauce, Lab im Parmesan —
erkennt sie nicht; gemeint ist die übliche Familien-Lesart. Ein Rezept, dessen
Zutat „Hackfleisch oder schwarze Bohnen” lautet, gilt vorsichtshalber als nicht
vegetarisch. Steht die Heuristik im Widerspruch zu einem bereits gesetzten
Notion-Label, meldet `labels_setzen.py` das als Konflikt, ohne das Label
anzufassen.

---

# Weg zur öffentlichen App

Ziel: eine URL, die jeder ohne Anmeldung öffnen kann.

## Vorher: zwei Dinge klären

**Dein API-Key zahlt für alle.** Eine öffentliche App ohne Login heißt, dass jeder
Besucher Anfragen auf deine Rechnung stellt. Deshalb sind zwei Schutzschalter eingebaut
und im öffentlichen Deployment beide aktiv:

- `REZEPTE_SCHREIBZUGRIFF=false` (Standard) — niemand kann deine Notion-Datenbank
  verändern. Zum Verarbeiten neuer Rezepte startest du die App lokal mit `true`.
- `REZEPTE_CHAT_LIMIT=25` — 25 Fragen pro Browser-Sitzung. Umgehbar durch Neuladen,
  bremst aber gedankenloses Dauerfeuer.

Zusätzlich unbedingt: **in der Anthropic Console ein Monats-Spending-Limit setzen.** Das
ist die einzige harte Obergrenze.

**Deine Rezepte werden öffentlich.** Alle Rezepte samt Zutaten und Quell-Links sind für
jeden sichtbar, der die URL kennt. Bei Familienrezepten meist egal — aber es ist eine
bewusste Entscheidung.

## Schritt 1 — Notion-Integration scharf schalten

1. Notion → Settings → Connections → *Develop or manage integrations* → **New integration**
2. Typ „Internal“, Workspace auswählen, Capabilities: *Read content* genügt für den
   öffentlichen Betrieb (Insert/Update nur, wenn du lokal verarbeiten willst)
3. Secret kopieren
4. Datenbank „Rezepte“ öffnen → `···` → **Connections** → Integration hinzufügen

Ohne Schritt 4 sieht die Integration die Datenbank nicht, auch mit gültigem Token nicht.

## Schritt 2 — Rezepte fertig verarbeiten (lokal)

Vor dem Veröffentlichen sollte die Sammlung sauber sein. Laut Statusdokument stehen offen:

- 9 Rezepte mit Status „Fehler“, weil chefkoch.de, zeit.de und sz-magazin in der Sandbox
  blockiert waren. **Lokal auf deinem Rechner sind diese Seiten normal erreichbar** — der
  „Verarbeiten“-Button dürfte die meisten davon jetzt schaffen.
- Rezept #5 (Instagram) braucht manuellen Text — Reiter „Fehler“.
- Rezepte #26–52 sind noch gar nicht im Schema erfasst.

```bash
REZEPTE_SCHREIBZUGRIFF=true streamlit run app.py
```

Reiter „Verarbeiten“ → Häkchen bei „Fehlerfälle erneut versuchen“ → starten. Was übrig
bleibt, im Reiter „Fehler“ von Hand nachtragen.

## Schritt 3 — Repository anlegen

```bash
cd rezept_app
git init && git add . && git commit -m "Rezept-App"
```

`.gitignore` schließt `.env` und `.streamlit/secrets.toml` bereits aus. **Vor dem Push
prüfen:** `git log -p | grep -i "secret_\|sk-ant"` muss leer sein. Ein einmal gepushter
Key ist verbrannt und muss rotiert werden, auch nach dem Löschen.

Dann als **öffentliches** Repo zu GitHub pushen (Streamlit Community Cloud braucht für
kostenlose öffentliche Apps ein öffentliches Repo).

## Schritt 4 — Auf Streamlit Community Cloud deployen

1. [share.streamlit.io](https://share.streamlit.io) → mit GitHub anmelden
2. **Create app** → Repository, Branch `main`, Main file `app.py`
3. **Advanced settings → Secrets**, folgendes einfügen:

```toml
NOTION_TOKEN = "secret_..."
NOTION_DATABASE_ID = "5ef6746d9a144974a0fbb499f845100f"
ANTHROPIC_API_KEY = "sk-ant-..."
REZEPTE_SCHREIBZUGRIFF = "false"
REZEPTE_CHAT_LIMIT = "25"
```

4. **Deploy** — dauert wenige Minuten

Ergebnis: `https://<name>.streamlit.app`, öffentlich erreichbar, kein Login. Die App liest
die Secrets automatisch (`_secrets_in_env_spiegeln` in `app.py`).

## Schritt 5 — Nach dem Deploy prüfen

- [ ] Seite im privaten Fenster öffnen — lädt ohne Anmeldung
- [ ] Nur die Reiter „Kochen“ und „Fragen“ sichtbar, Sidebar zeigt „Nur-Lese-Modus“
- [ ] Rezept skalieren: Mengen ändern sich, „Prise Salz“ bleibt stehen
- [ ] Würfel-Button liefert wechselnde Rezepte
- [ ] Eine Frage im Chat stellen — Antwort nennt echte Rezepttitel
- [ ] Auf dem Handy öffnen (die Familie wird die App fast nur mobil nutzen)

## Grenzen der kostenlosen Variante

Streamlit Community Cloud ist gratis, hat aber Grenzen, die für eine Familien-App
verschmerzbar sind:

- **Schlafmodus nach 12 Stunden ohne Zugriff.** Der erste Besucher danach sieht einen
  Weckbildschirm und muss einmal klicken — dann dauert der Start etwa 30 Sekunden.
- **~1 GB RAM**, unbegrenzt viele öffentliche Apps, nur eine private.
- **Keine eigene Domain.** Willst du `rezepte.familie.de`, brauchst du eine andere
  Plattform (Hetzner-VPS mit Caddy, Railway, Render).

Der Notion-Cache in der App hält 15 Minuten. Änderst du in Notion ein Rezept, greift der
Sidebar-Button „Aus Notion aktualisieren“ sofort.

## Danach — was sich anbietet

- **Foto-Extraktion:** Claude kann Bilder lesen. Die Rezepte mit hinterlegtem Foto ließen
  sich damit verarbeiten, statt sie als Fehler zu markieren. `scraper.py` hat den Zweig
  bereits vorgesehen.
- **Gerichtfotos in den Karten** — das Konzept hat sie bewusst zurückgestellt, sie wären
  aber der größte optische Sprung.
- **Wochenplan und Sammel-Einkaufsliste** über mehrere Rezepte hinweg.
- **Verarbeitung als Cron-Job** statt Button, damit du nichts mehr lokal starten musst.
  Ein GitHub-Actions-Workflow mit den gleichen Secrets genügt.
