# Handoff: Würfeln · Fragen · Upload (Rezept-App der Familie)

## Overview
Zwei Features der Streamlit-App "Rezepte der Familie" (Notion als Datenquelle) wurden neu gestaltet:

1. **Würfeln** — Zufallsvorschlag für das Abendessen aus der gefilterten Auswahl, Ergebnis als Typo-Karte, Personenzahl direkt in der Karte einstellbar (Default **7**).
2. **Fragen (Chat)** — Freitext-Chat über die Sammlung; in der Antwort erkannte Rezepte erscheinen als kompakte Textkarten unter der Antwort.

Wichtige Randbedingung: **Die Sammlung hat meist keine Fotos.** Alle Karten sind deshalb rein typografisch aufgebaut (Titel groß, Zutaten-Chips als Vorschau, Initial-Kachel im Chat) — keine Bild-Platzhalter.

## About the Design Files
Die HTML-Datei in diesem Bundle (\`Rezept Feinschliff.dc.html\`) ist eine **Design-Referenz**, kein Produktionscode. Sie ist ein interaktiver Prototyp (mobile Frames, echte Würfel-Interaktion) und zeigt Aussehen und Verhalten.

Zielumgebung ist hier bereits vorhanden: **Streamlit (Python)** mit \`app.py\` + \`theme.py\` (CSS via \`st.markdown(..., unsafe_allow_html=True)\`). Die Designs sind in dieser Umgebung nachzubauen bzw. weiterzupflegen — nicht das HTML als Ganzes zu übernehmen. Ein erster Übertrag ist in \`app_ausschnitt.py\` / \`theme.py\` in diesem Bundle enthalten (Stand: siehe unten).

## Fidelity
**High-fidelity.** Farben, Typografie, Radien, Abstände und Interaktionen sind final gemeint. Innerhalb von Streamlit gilt: Struktur und Werte pixelgenau übernehmen, wo Streamlit es zulässt; native Streamlit-Widgets (number_input, chat_input, tabs) behalten ihr Verhalten und werden nur per CSS angeglichen.

## Umsetzung mit Claude Code
Die Zielumgebung existiert schon: **Streamlit (Python)**, `app.py` + `theme.py`, CSS über `st.markdown(..., unsafe_allow_html=True)`. Nicht das HTML übernehmen, sondern die Screens in dieser Umgebung nachbauen. Empfohlener Ablauf:

1. **Bundle ins Repo legen:** diesen Ordner nach `docs/design_handoff_wuerfeln_chat/` kopieren, Claude Code im Repo-Root starten.
2. **Erst lesen lassen:** "Lies docs/design_handoff_wuerfeln_chat/README.md und quellcode/app.py, quellcode/theme.py. Vergleiche mit unserem app.py und theme.py und liste die Unterschiede, bevor du etwas änderst."
3. **In vier Schritten umsetzen, jeder ein eigener Commit** — nicht alles in einem Rutsch, damit jeder Schritt einzeln im Browser prüfbar ist:
   - `theme.py`: Palette + CSS-Blöcke (Segment, Stat-Farben, Karten, Chips, Bubbles).
   - Reiter-Struktur: `st.tabs(["Würfeln", "Fragen", "Upload"])`, `tab_upload` mit Segment-Radio, `verarbeiten_bereich` / `fehler_bereich`.
   - Würfeln-Flow (Screens 1–3 unten): Leerzustand, Vorschlagskarte, Mengenliste mit Stepper.
   - Fragen-Reiter: gruppierte Einstiege im Leerzustand, Anschlussfragen im Gespräch, Mini-Karten.
4. **Diese Dateien als Vorlage nutzen:** `quellcode/app.py` und `quellcode/theme.py` sind ein lauffähiger Übertrag des Designs — Claude Code soll sie als Referenz diffen, nicht blind überschreiben (eure `llm.py`, `notion_repo.py`, `models.py` bleiben unberührt).
5. **Grenzen benennen** (bitte an Claude Code weitergeben): Streamlit rendert die Würfel-Rotation und das freie Positionieren der Chat-Eingabe nicht; `st.chat_input` sitzt immer unten. Übernommen wird dort die Struktur (gruppierte Einstiege, betonte Eingabe, Karten), nicht die Pixel. Alles, was reines CSS ist (Radien, Farben, Schatten, Typo), pixelgenau übernehmen.
6. **Abnahme:** `streamlit run app.py` und mit den Screenshots in `screenshots/` vergleichen, dazu `pytest` (die Tests im Repo laufen ohne Notion-Zugang).

## Screens / Views

### 1. Würfeln (Reiter 1) — Flow in drei Zuständen
**Purpose:** Zufallsvorschlag für das Abendessen; danach Menge auf die Personenzahl hochrechnen.

**Screen 1 · vor dem Wurf** — leerer Screen, der Zufall ist die Hauptsache:
- Kopf oben fix (padding 52/20/0): Eyebrow "Familienküche" (0.68rem, 600, uppercase, letter-spacing .14em, accent_dark) + H1 "Was koche ich heute?" (Fraunces 700, 1.7rem, lh 1.15).
- Mittelzone `flex:1`, Inhalt vertikal und horizontal zentriert, gap 16 px, padding 0/28:
  - Würfel-Button **132×132 px**, radius 40 px, Gradient 135° accent → accent_dark, Schatten `0 14px 34px rgba(158,63,90,.32)`, Icon 🎲 58 px.
  - Titel "Lass den Würfel entscheiden" (Fraunces 700, 1.3rem, zentriert).
  - Hinweis 0.8rem, muted, lh 1.55: "Er zieht aus **18 Hauptgerichten, Suppen & Salaten**. Nachspeisen, Gebäck und Eingemachtes bleiben außen vor."
- Unterer Bereich (padding 0/20/14, gap 10): Filter-Chips-Reihe (erste Chip "Alle 18" aktiv = accent/weiß; übrige surface_alt + border, radius 999px, padding 7/16, 0.8rem) und darunter zentriert "Lieber selbst aus der Liste wählen" (0.8rem, 600, accent_dark) als leiser Ausweg.

**Screen 2 · der Vorschlag** — füllt den Screen:
- Kopfzeile (padding 52/20/12): links Eyebrow "Der Würfel sagt", rechts "aus 18 Mahlzeiten" (0.7rem, muted).
- Vorschlagskarte: radius 26 px, 1 px border, Schatten `0 8px 26px rgba(44,33,38,.08)`, overflow hidden, Einblendung `cardFlipIn`.
  - Kopfband: Gradient 135° accent_soft → #F3EDE4, unten 1 px border, padding 20/20/22. Zeile: Kategorie-Pill (green_soft/green, radius 999px, 4/12, 0.7rem, 600) + "45 Min · 4 Portionen" (0.72rem, muted). Titel **Fraunces 700, 2rem, lh 1.12**. Darunter ein Satz Kurzbeschreibung (0.8rem, muted, lh 1.5).
  - Body (padding 18/20/20): Label "9 ZUTATEN" (0.66rem, 600, uppercase, ls .1em, muted); Chips der ersten 5 Zutaten (bg bg, 1 px border, radius 999px, 5/11, 0.78rem) + "+ 4 weitere" muted; Personen-Stepper (radius 20 px, bg bg, border, padding 10/12/10/15; Label "Personen" 0.84rem/600 + "Original: 4 Portionen" 0.68rem muted; −/+ 44×44 radius 14, Wert Fraunces 700 1.35rem).
- Sekundäre Aktionen **unter einer Trennlinie mit Mittelwort "passt nicht?"** (1 px Linien links/rechts, 0.72rem muted): "🎲 Nochmal würfeln" (surface_alt, accent_dark) und "Aus Liste wählen" (surface, border) — je flex 1, radius 999px, padding 12, 0.85rem/600.
- Fixierte Primäraktion über der Tab-Bar: "Mengen für {N} Personen", volle Breite, accent, weiß, radius 999px, padding 15 px, 0.94rem/600, Schatten `0 6px 18px rgba(158,63,90,.24)`.

**Screen 3 · Mengen** — Liste hängt live an der Personenzahl:
- Kopf: Rücksprung "‹ Vorschlag" (0.8rem, 600, accent_dark), darunter Rezepttitel (Fraunces 700, 1.45rem).
- **Stepper-Leiste oben fixiert:** surface, 1 px border, radius 20 px, Schatten `0 2px 10px rgba(44,33,38,.05)`, padding 9/11/9/15. Links "{N} Personen" (0.84rem/600) + "Original 4 Port. · Faktor 1,75×" (0.68rem, muted). Rechts −/+ 44×44.
- Mengenliste in einer Karte (surface, border, radius 22 px, padding 6/16): Zeilen `display:flex`, align-items baseline, gap 12, padding 11/2, 1 px dashed border unten (letzte Zeile ohne). Menge rechtsbündig, min-width 92 px, Fraunces 600, 1rem, accent_dark; Name 0.88rem, text. Nicht skalierbare Zutaten: "nach Gefühl" kursiv, 0.82rem, muted ("Salz, Pfeffer, Rosmarin").
- Rundung der Mengen: ≥100 → auf 10 gerundet (1400 g), sonst auf 0,5 (3,5 Zucchini); Dezimalkomma.
- Hinweisbox bei geschätzter Basismenge: bg warn_soft, 3 px linke Kante warn, radius 0/14/14/0, 0.76rem, warn.
- Fußzeile: "Einkaufsliste kopieren" (accent, flex 1) + "🎲" (surface_alt, border) für einen neuen Wurf.

### 2. Fragen (Reiter 2) — Eingabe im Zentrum
**Purpose:** Freitextfrage an die Sammlung; Antwort plus erkannte Rezepte als Karten.

**Startzustand (leerer Verlauf):**
- Kopf: Eyebrow "Küchen-Assistent" + H1 "Was willst du wissen?" (Fraunces 700, 1.7rem).
- **Eingabe-Panel** — bewusst dasselbe Gradient-Panel wie der Würfel (radius 26 px, 1 px border, Gradient 135° accent_soft → #F3EDE4, padding 18/16/16, gap 12), darin eine weiße Eingabekarte: radius 20 px, 1 px border, Schatten `0 4px 14px rgba(44,33,38,.07)`, padding 14/14/12; Textarea 3 Zeilen, randlos, 0.95rem, lh 1.45, Placeholder "Frag mich etwas über eure Rezepte …"; Fußzeile mit 1 px Oberlinie: links "Antwortet nur aus euren **34 Rezepten**" (0.68rem, muted), rechts Sendeknopf 46×46 px, radius 16 px, Gradient accent → accent_dark, Icon ↑, Schatten `0 6px 16px rgba(158,63,90,.28)`. Unter der Karte zentriert: "Tippe frei — oder nimm einen Einstieg unten." (0.72rem, muted).
- **Einstiege nach Absicht gruppiert** statt einer Reihe gleichwertiger Beispiele. Je Gruppe eine Überschrift (0.66rem, 600, uppercase, ls .1em, muted) und darunter Chips (surface, 1 px border, radius 999px, padding 8/14, 0.8rem, linksbündig, umbrechend):
  - *Aus dem Vorrat:* "Was kann ich mit Kartoffeln und Zwiebeln kochen?", "Welche Rezepte sind vegetarisch?", "Wofür brauche ich Hefe?"
  - *Für viele Gäste:* "Ich habe 12 Gäste — was skaliert gut?", "Was kann ich vorbereiten?"
  - *Schnell & einfach:* "Welches Rezept braucht die wenigsten Zutaten?", "Was ist in 30 Minuten fertig?"
  - Antippen füllt das Eingabefeld (nicht sofort senden).
- Nach dem Senden wächst der Verlauf unter einer 1 px Trennlinie: User-Bubble, Antwort-Bubble, Mini-Karten (Werte wie unten).

**Gesprächszustand:**
- Kopf schrumpft auf eine Zeile (padding 52/20/10): links "Küchen-Assistent" (Fraunces 700, 1.15rem) + "34 Rezepte als Datenbasis · 21 Fragen frei" (0.68rem, muted), rechts Pill "Neu" (surface_alt, border, 0.7rem/600) leert den Verlauf.
- Verlauf scrollt (gap 10 px). **User-Bubble:** align-self flex-end, max-width 82 %, accent, weiß, padding 11/15, radius `18 18 4 18`, 0.86rem, lh 1.4. **Antwort-Bubble:** surface, 1 px border, radius `18 18 18 4`, max-width 92 %. **Rezept-Mini-Karten** darunter gestapelt: surface, border, radius 16 px, padding 12/14; Initial-Kachel 38×38 px, radius 12 px, accent_soft/accent_dark, Fraunces 700 1.05rem; Titel Fraunces 600 0.98rem, Meta "Kategorie · N Zutaten" 0.7rem muted, Zutatenzeile 0.72rem. Rein informativ, kein Klickverhalten, maximal 3.
- **Eingabe bleibt unten fixiert und ist optisch betont:** über ihr eine horizontal scrollende Reihe Anschlussfragen ("Mengen für 7 Personen?", "Nur vegetarisch", "Was fehlt im Vorrat?" — surface, border, radius 999px, 7/13, 0.76rem). Composer: surface, **1,5 px border in #E3C9D2**, radius 24 px, padding 8/8/8/16, Schatten `0 6px 18px rgba(44,33,38,.08)`, Sendeknopf 44×44 radius 16, Gradient accent → accent_dark.

### 3. Upload (Reiter 3) — Verarbeitung + Fehler
**Purpose:** Die Rezeptdatenbank verarbeiten lassen und Fehlerfälle nacharbeiten. Ersetzt die bisherigen Reiter "Verarbeiten" und "Fehler".

**Gemeinsamer Kopf:**
- Eyebrow "Datenbasis" + H1 "Upload & Verarbeitung".
- **Statistik-Reihe:** drei Karten (flex 1, surface, 1 px border, radius 18 px, padding 10/12): Zahl Fraunces 700 1.4rem — "34 Rezepte" (text), "6 offen" (warn #A9762A), "3 Fehler" (error #B4483C) — Label 0.62rem, 600, uppercase, ls .08em, muted.
- **Segment** (statt zweier Reiter): Leiste bg surface_alt, 1 px border, radius 999px, padding 3 px; zwei gleich breite Segmente, padding 9/0, 0.8rem. Aktiv: surface, radius 999px, 600, accent_dark, Schatten `0 1px 3px rgba(44,33,38,.08)`. Inaktiv: muted/500. Labels "Verarbeiten" und "Fehler · 3".

**Segment "Verarbeiten":**
- **Steuerpanel:** Gradient 135° accent_soft → #F3EDE4, 1 px border, radius 24 px, padding 16/16/18, gap 12. Titel "{N} Rezepte in der Warteschlange" (Fraunces 700, 1.12rem). Checkbox-Zeile: Kästchen 22×22 px, radius 7 px (ungeprüft surface + border #E3C9D2, geprüft accent + Häkchen weiß), Label "Die 3 Fehlerfälle erneut versuchen" (0.82rem) — schaltet die Fehlerfälle in die Warteschlange (6 → 9). Erklärtext 0.72rem, muted: "Quelle abrufen, Zutaten ins Schema übersetzen, Ergebnis zurück nach Notion schreiben. Jeder Durchlauf kostet einen Claude-Aufruf pro Rezept." Primärknopf "Verarbeitung starten" (accent, weiß, radius 999px, padding 13, 0.9rem/600).
- **Laufender Durchlauf:** der Knopf wird durch Fortschrittsbalken ersetzt (Höhe 8 px, radius 999px, Spur surface + border, Füllung accent, `transition: width .35s ease`) plus Statuszeile "{Rezepttitel} ({i}/{N})" (0.74rem, accent_dark, 500), am Ende "{N} von {N} verarbeitet".
- **Warteschlange:** Karten (surface, border, radius 16 px, padding 11/13): Titel 0.88rem/600, darunter Pills "Quelle: Weblink | Foto | manueller Text" (surface_alt, border, muted) und Statuspill "offen" (warn_soft/warn), je 0.68rem/600, radius 999px.
- **Letzter Durchlauf** (Abschnittslabel mit Zeitstempel): Protokollkarten mit Pill "ok" (green_soft/green) bzw. "Fehler" (error_soft/error) links, daneben Titel 0.86rem/600 und Meldung 0.72rem muted ("9 Zutaten erkannt · Quelle: Weblink", "Seite nicht erreichbar (403) — Text nachtragen").

**Segment "Fehler":**
- Hinweisbox oben (warn_soft, 3 px Kante warn, radius 0/14/14/0, 0.76rem): "Quellen, die sich nicht automatisch auswerten ließen. Rezepttext hier einfügen — beim nächsten Durchlauf wird er bevorzugt verwendet."
- **Aufgeklappter Fall:** Karte surface, border, radius 20 px, padding 14/15/15, Schatten `0 4px 14px rgba(44,33,38,.06)`. Kopfzeile: Titel Fraunces 600 1.05rem + Statuspill "Fehler" rechts. Fehlergrund in error_soft-Box (radius 12 px, 0.74rem, error). Quellzeile 0.7rem muted, `word-break:break-all`. Label "Rezepttext einfügen" (0.72rem/600), Textarea min-height 86 px (bg bg, border, radius 14 px, padding 11/12, Placeholder "Zutatenliste und Portionsangabe aus der Quelle hier hineinkopieren …"). Aktionen: "Speichern & verarbeiten" (accent, flex 1) + "Nur speichern" (surface_alt, border).
- **Zugeklappte Fälle:** Zeilen (surface, border, radius 20 px, padding 13/15) mit Titel + Grund (0.72rem muted) links und ＋ rechts.
- Tab-Bar unten jetzt **dreiteilig**: 🎲 Würfeln · 💬 Fragen · 📥 Upload (aktiv accent_dark/600, inaktiv muted/500 mit Icon-opacity .4).

### Frühere Fassung (Turn 1/2, überholt durch die Screens oben)

### 1. Würfeln — erste Fassung
**Purpose:** Rezept per Zufall ziehen oder aus Liste wählen, Menge auf Personenzahl hochrechnen.

**Layout (mobil, 402 px Referenzbreite):**
- Vertikaler Stack, Seitenpadding 20 px, Inhalt scrollt, Tab-Bar unten fix.
- Kopf: Eyebrow (uppercase, 0.68rem, letter-spacing .14em, Akzent-dunkel) + H1 Serif 1.7rem / line-height 1.15.
- Filter-Chips: horizontale Reihe, gap 8 px, überlaufend scrollbar. Aktiv = Akzentfüllung, weiß; inaktiv = surface_alt, 1 px border, radius 999px, padding 7/16.
- **Würfel-Panel:** radius 26 px, 1 px border, Gradient 135° accent_soft → creme; Inhalt zentriert, gap 14 px:
  - Würfel-Button 92×92 px, radius 28 px, Gradient 135° accent → accent_dark, Schatten \`0 8px 20px rgba(158,63,90,.3)\`, Icon 🎲 40 px.
  - Label "Würfeln" Serif 600, 1rem.
  - Hinweistext 0.76rem, muted, line-height 1.5, max-width 250 px: "Der Würfel zieht aus **18 Hauptgerichten, Suppen & Salaten** — Nachspeisen und Eingemachtes bleiben außen vor." (Zahl = Größe des Würfel-Topfs; bei aktivem Kategoriefilter Text: "Der Würfel zieht aus **N Rezepten** der aktuellen Auswahl.")
- **Ergebniskarte** (erscheint nach dem Wurf, radius 24 px, 1 px border, Schatten \`0 6px 20px rgba(44,33,38,.07)\`, overflow hidden):
  - Kopfband: Hintergrund surface_alt (bzw. Gradient accent_soft → surface_alt), unten 1 px border. Zeile mit Kategorie-Pill (Salbei: bg green_soft, Text green) + Meta `Original: 4 Portionen · 11 Zutaten` (0.72rem, muted). Darunter Titel Serif 700, 1.55rem, line-height 1.15.
  - Body (padding 16/18/18): Label "N ZUTATEN" (0.68rem, 600, uppercase, letter-spacing .1em, muted); Zutaten-Chips (erste 4 Namen; bg = Seitenhintergrund, 1 px border, radius 999px, padding 5/11, 0.76rem) + "+ N weitere" in muted.
  - **Personen-Stepper:** Zeile radius 18 px, bg Seitenhintergrund, 1 px border, padding 10/12/10/14. Links Label "Personen" (0.82rem, 600) + "Original: 4 Portionen" (0.68rem, muted). Rechts: Minus-Button 44×44 (radius 14, surface_alt, border), Wert Serif 700 1.3rem (min-width 34 px, zentriert), Plus-Button 44×44 (radius 14, accent_soft, border, accent_dark). Default **7**, Grenzen 1–30.
  - Buttons: primär "Mengen berechnen" (flex 1, accent, weiß, radius 999px, padding 11 px, 600, 0.88rem), sekundär "↻" (surface_alt, border) löst neuen Wurf aus.
- Tab-Bar unten: weiß, 1 px Oberkante, padding 10/24/20; zwei Items (Icon 1.15rem + Label 0.72rem), aktiv accent_dark/600, inaktiv muted/500 und Icon opacity .4. **Labels: "Würfeln" und "Fragen".**

### 2. Fragen / Chat (Reiter 2)
**Purpose:** Freitextfrage an die Sammlung; Antwort plus erkannte Rezepte als Karten.

**Layout:**
- Kopf wie Würfeln (Eyebrow "Küchen-Assistent" + H1 "Frag die Sammlung", Serif 1.6rem).
- Thread: Spalte, gap 12 px.
  - **User-Bubble:** align-self flex-end, max-width 80 %, bg accent, Text weiß, padding 11/15, radius \`18px 18px 4px 18px\`, 0.88rem, line-height 1.4.
  - **Assistant-Bubble:** align-self flex-start, max-width ~92 %, bg surface, 1 px border, radius \`18px 18px 18px 4px\`, Textfarbe text.
  - **Rezept-Mini-Karten** direkt unter der Antwort, gestapelt (gap 8 px): surface, 1 px border, radius 16 px, padding 12/14, Schatten \`0 2px 8px rgba(44,33,38,.05)\`; links Initial-Kachel 38×38 px, radius 12 px, bg accent_soft, Text accent_dark, Serif 700 1.05rem; rechts Titel (Serif 600, 1rem, line-height 1.2), Meta "Kategorie · N Zutaten" (0.75rem, muted), Zutatenzeile "Kartoffeln, Zucchini, Paprika, Feta …" (0.8rem, text). **Rein informativ, kein Klickverhalten.**
- Beispielfragen-Chips über der Eingabe (surface_alt, 1 px border, radius 999px, 0.78rem).
- Limit-Hinweis zentriert, 0.72rem, muted: "Noch 21 Fragen in dieser Sitzung".
- Eingabezeile: Pill radius 999px, bg surface_alt, 1 px border, padding 6/6/6/16, Placeholder "Frag mich etwas über eure Rezepte …" (0.84rem, muted), Sende-Button 34×34 Kreis, bg accent, weiß.

## Interactions & Behavior
- **Würfeln:** Klick auf den Würfel → 850 ms Animation, danach neues Ergebnis. Der neue Treffer darf nicht der vorherige sein. Würfel-Topf = aktuell gefilterte Auswahl; ohne aktiven Kategoriefilter nur Mahlzeiten (\`ist_mahlzeit\`: Hauptgericht, Suppe, Salat) — Nachspeisen/Gebäck/Eingemachtes ausgeschlossen. Mit Kategoriefilter zählt die Auswahl unverändert.
- **Animationen** (Prototyp, CSS): Würfel \`diceSpin\` 850 ms ease-in-out (rotate 0→720°, Scale 1→1.1→0.94→1); Ergebniskarte \`cardFlipIn\` 500 ms ease (opacity 0→1, translateY 16→0 px, scale .94→1). In Streamlit ist die Rotation nicht nachbaubar — dort genügt die Einblend-Animation der Karte; alternativ Spinner während des Reruns.
- **Personen-Stepper:** −/+ um 1, Clamp 1–30, Default 7. In Streamlit ist das \`st.number_input\` mit \`value = 7.0 if basis*20 >= 7 else basis\`, \`min_value = schritt\`, \`step = 1.0\` (bzw. 0.5 bei Basis < 2). Änderung rechnet Zutaten sofort neu (\`skalieren()\`, lokal, kein LLM).
- **Chat:** Absenden → Antwort streamt/erscheint, danach Mini-Karten für alle Rezepte, deren Titel (case-insensitive) im Antworttext vorkommt, maximal 3. Gleiches Rendering beim Nachzeichnen des Verlaufs.
- **Fehler-/Leerzustände:** kein Treffer im Filter → Info "Kein Rezept passt zu …"; leerer Würfel-Topf → Button disabled; Chat-Limit erreicht → Warnhinweis statt Anfrage.

## State Management
- \`gewaehltes_rezept\` (str | None) — aktuell angezeigtes Rezept.
- \`wuerfel_treffer\` (str | None) — letzter Wurf; steuert das Einblenden der Ergebniskarte und wird nach dem Rendern zurückgesetzt.
- \`ziel_<page_id>\` (float) — Personen-/Mengenwert pro Rezept, Default 7.
- \`chat_verlauf\` (list[{role, content}]), \`chat_aufrufe\` (int, Limit-Zähler), \`cache_schluessel\` (int, Notion-Cache-Invalidierung).
- Datenbeschaffung: Notion über \`NotionRepo.rezepte_laden()\`, gecacht (\`st.cache_data\`, ttl 900 s). Chat via Anthropic-Modell, Kontext = alle Rezepte mit strukturierten Zutaten.

## Design Tokens (Palette "Beere & Creme", hell)
| Token | Wert |
| --- | --- |
| bg | #FBF6F7 |
| surface | #FFFFFF |
| surface_alt | #F6EBEE |
| accent | #C15A76 |
| accent_dark | #9E3F5A |
| accent_soft | #FAE3E9 |
| green (Kategorie) | #3C6F63 |
| green_soft | #E6EFEA |
| text | #2C2126 |
| muted | #8E7C82 |
| border | #EFDDE2 |
| warn / warn_soft | #A9762A / #F7EFDF |
| error / error_soft | #B4483C / #FAE4E1 |

**Typografie:** Fraunces (500/600/700) für Headlines, Titel, Mengen und Initialen; Inter (400/500/600) für alles andere. H1 2.4rem / H2 1.6rem / H3 1.15rem (Desktop), Kartentitel 1.55rem, Fließtext 0.86–0.9rem, Meta 0.7–0.78rem.

**Radien:** 999px (Pills/Buttons), 26–28px (Panels), 24px (Ergebniskarte), 18px (Stepper, Bubbles), 16px (Mini-Karte), 14px (Stepper-Buttons), 12px (Initial-Kachel).

**Schatten:** Panel/Karte \`0 6px 20px rgba(44,33,38,.07)\`; Mini-Karte \`0 2px 8px rgba(44,33,38,.05)\`; Würfel-Button \`0 8px 20px rgba(158,63,90,.3)\`.

**Spacing:** 4 / 6 / 8 / 12 / 16 / 20 / 26 px; Touch-Ziele mindestens 44×44 px.

## Assets
Keine Bilder, keine Icon-Bibliothek. Verwendet werden ausschließlich Emoji, die die App schon nutzt (🎲 Würfeln, 🍲 Assistent/Marke, 🧑‍🍳 Nutzer, 💬 Chat-Tab). Fotos sind bewusst nicht Teil des Designs.

## Files
- \`Rezept Feinschliff.dc.html\` — interaktiver Design-Prototyp, neueste Fassung oben: **Turn 5 = Würfeln-Flow (5a)**, **Turn 4 = Fragen (4a)**, **Turn 3 = Upload (3a)**; Turn 2 = Farbwelten (2b gewählt = Heidelbeer/"Beere & Creme"), Turn 1 = Layout-Richtungen (1a gewählt). Turn 1/2 sind Historie.
- \`ios-frame.jsx\` — nur Präsentationsrahmen des Prototyps (nicht Teil des Produkts).
- \`quellcode/\` — lauffähiger Übertrag als Referenz zum Diffen: \`app.py\` (vollständig, mit \`tab_upload\`, \`verarbeiten_bereich\`, \`fehler_bereich\`, \`FRAGE_GRUPPEN\`, \`ANSCHLUSS_FRAGEN\`), \`theme.py\`, \`models.py\`, \`llm.py\`, \`requirements.txt\`.
- \`theme.py\` — Palette + CSS (inkl. Segment-Styling \`.st-key-upload_bereich\`, \`.stat .zahl.warn/.error\`, \`.wuerfel-karte\`, \`.zutat-chip\`, \`.mini-karte\`).
- \`app_ausschnitt.py\` — nur die designrelevanten Funktionen: \`rezept_detail\`, \`zutaten_vorschau\`, \`wuerfel_karte\`, \`tab_kochen\`, \`chat_rezept_karten\`, \`tab_fragen\`, \`tab_upload\` und die beiden Upload-Bereiche.

## Screenshots
- `screenshots/turn5-wuerfeln-flow.png` — Würfeln, alle drei Zustände: vor dem Wurf, Vorschlag, Mengen.
- `screenshots/turn4-fragen-eingabe.png` — Fragen: Startzustand mit Eingabe-Panel und gruppierten Einstiegen, daneben Gesprächszustand mit fixierter Eingabe.
- `screenshots/turn3-upload.png` — Upload: Segment "Verarbeiten" (Statistik, Warteschlange, Protokoll) und Segment "Fehler" (Nacharbeit mit Textfeld).
- `screenshots/gewaehlt-2b-wuerfeln-und-chat.png` — frühere Fassung, Palette Heidelbeer erstmals angewandt (Historie).
- `screenshots/layout-1a-wuerfeln-und-chat.png` — Layout-Richtung 1a in der ersten Palette (Historie).
