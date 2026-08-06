"""End-to-End-Render-Test der Streamlit-UI mit gefaketem Notion-Repo.

Ausfuehren:  python _uitest.py
Prueft, dass alle drei Ansichten (Wuerfeln, Fragen, Upload) ohne Exception
rendern und die zentralen Widgets (Rezeptauswahl, Skalierungs-Input,
Wuerfel-Button, Chat, Statistik-Kacheln) da sind.

Navigiert wird ueber die Bottom-Nav-Buttons (nav_wuerfeln / nav_fragen /
nav_upload), nicht ueber st.tabs -- die App nutzt keine Streamlit-Tabs.
"""

import os
import pathlib
import shutil
import sys
import tempfile

from streamlit.testing.v1 import AppTest

BASIS = pathlib.Path(__file__).parent
TEMP = pathlib.Path(tempfile.mkdtemp(prefix="rezept_uitest_"))
sys.path.insert(0, str(BASIS))
sys.path.insert(0, str(TEMP))

FIXTURE = '''
import notion_repo, models


def _bau(titel, status, daten=None, **kw):
    r = models.Rezept(titel=titel, page_id="id-" + titel, status=status, **kw)
    if daten:
        r.anwenden_zutaten_json(daten)
    return r


class FakeRepo:
    def rezepte_laden(self):
        return [
            _bau("Kartoffelknoedel", "verarbeitet", {
                "basis_menge": 12, "basis_einheit": "Stücke", "basis_geschaetzt": True,
                "hinweis": "Quelle nannte keine Stueckzahl",
                "zutaten": [
                    {"menge": 1000, "einheit": "g", "zutat": "Kartoffeln", "skalierbar": True},
                    {"menge": 1, "einheit": "TL", "zutat": "Salz", "skalierbar": True},
                    {"menge": None, "einheit": None, "zutat": "Muskatnuss", "skalierbar": False},
                ]}, weblink="https://einfachkochen.de/x"),
            _bau("Holunderbluetengelee", "verarbeitet", {
                "basis_menge": 6, "basis_einheit": "Gläser (à 250 ml)",
                "zutaten": [{"menge": 1500, "einheit": "ml", "zutat": "Holunderbluetensud"}]}),
            _bau("Tofu-Curry mit Spinat", "verarbeitet", {
                "basis_menge": 4, "basis_einheit": "Personen", "kategorie": "Hauptgericht",
                "zeit_minuten": 20,
                "zutaten": [{"menge": 400, "einheit": "g", "zutat": "Tofu"}]}),
            # Fleisch und lange Garzeit -- Gegenstueck fuer die frueheren Filter,
            # die es in dieser Ansicht nicht mehr gibt, aber als zweites
            # Hauptgericht fuer die Kategorie-Pillen weiterhin nuetzlich.
            _bau("Rinderbraten", "verarbeitet", {
                "basis_menge": 6, "basis_einheit": "Personen", "kategorie": "Hauptgericht",
                "zeit_minuten": 180,
                "zutaten": [{"menge": 1500, "einheit": "g", "zutat": "Rinderbraten"}]}),
            # Geschaetzte Basismenge und gemischte Zutaten -- frueher an
            # Kartoffelknoedel getestet, das aber als Beilage in dieser
            # Ansicht nicht mehr auftaucht.
            _bau("Klare Gemüsesuppe", "verarbeitet", {
                "basis_menge": 12, "basis_einheit": "Portionen", "basis_geschaetzt": True,
                "hinweis": "Quelle nannte keine Portionszahl", "kategorie": "Suppe",
                "zutaten": [
                    {"menge": 1000, "einheit": "g", "zutat": "Gemüse", "skalierbar": True},
                    {"menge": 1, "einheit": "TL", "zutat": "Salz", "skalierbar": True},
                    {"menge": None, "einheit": None, "zutat": "Lorbeerblatt", "skalierbar": False},
                ]}),
            _bau("Griechischer Salat", "verarbeitet", {
                "basis_menge": 4, "basis_einheit": "Personen", "kategorie": "Salat",
                "zutaten": [{"menge": 300, "einheit": "g", "zutat": "Tomaten"}]}),
            _bau("Karottenkuchen", "verarbeitet", {
                "basis_menge": 12, "basis_einheit": "Stücke",
                "zutaten": [{"menge": 300, "einheit": "g", "zutat": "Karotten"}]}),
            _bau("Pestofisch im Backofen", "Fehler", weblink="https://chefkoch.de/x",
                 rezepttext="[Automatisch] Seite nicht abrufbar"),
            _bau("Instagram-Quick-Recipe", "nicht verarbeitet"),
            _bau("Kaputtes JSON", "verarbeitet"),
        ]

    def rezepttext_setzen(self, *a, **k):
        pass

    def zutaten_schreiben(self, *a, **k):
        pass

    def fehler_markieren(self, *a, **k):
        pass


notion_repo.NotionRepo = FakeRepo
'''


def _nav_labels(at: AppTest) -> list[str]:
    """Beschriftungen der Bottom-Nav -- ersetzt den frueheren st.tabs-Check."""
    return [b.label for b in at.button if (b.key or "").startswith("nav_")]


def main() -> int:
    # Temporaere Dateien liegen ausserhalb des Projektordners, damit nichts
    # zurueckbleibt, was spaeter versehentlich deployed wird.
    (TEMP / "_fixture.py").write_text(FIXTURE)

    quelle = (BASIS / "app.py").read_text().replace(
        "from dotenv import load_dotenv",
        "from dotenv import load_dotenv\nimport _fixture",
    )
    ziel = TEMP / "_app_test.py"
    ziel.write_text(quelle)

    at = AppTest.from_file(str(ziel), default_timeout=90).run()

    if at.exception:
        for ex in at.exception:
            print("EXCEPTION:", ex.value)
            print(ex.stack_trace)
        return 1
    print("✓ Render ohne Exception")

    markup = " ".join(m.value for m in at.markdown)

    # Vor jeder Wahl zeigt die Ansicht nur den Wuerfel -- keine Rezeptliste,
    # das ist der radikale Teil des neuen Entwurfs.
    assert len(at.selectbox) == 0, "Rezeptliste sollte vor der ersten Wahl verborgen sein"
    print("✓ Ohne Würfeln oder manuelle Wahl bleibt die Rezeptliste verborgen")

    assert "Lass den Würfel entscheiden" in markup, "Neue Würfel-Überschrift fehlt"
    print("✓ Würfel-Panel zeigt „Lass den Würfel entscheiden“")

    # Kategorie-Pillen: "Alle 4" per Default, dahinter die drei Mahlzeit-
    # Kategorien. Nachspeise/Beilage/Eingemachtes (Kuchen, Knödel, Gelee)
    # tauchen in dieser Ansicht gar nicht mehr auf.
    kategorie_optionen = at.pills[0].options
    assert kategorie_optionen == ["Alle 4", "Hauptgericht", "Suppe", "Salat"], kategorie_optionen
    print("✓ Kategorie-Pillen:", kategorie_optionen)

    assert "aus <b>4 Hauptgerichten, Suppen &amp; Salaten</b>" in markup, markup[:300]
    print("✓ Würfel-Topf: 4 Mahlzeiten (Gelee, Kuchen, Beilage ausgeschlossen)")

    buttons = [b.label for b in at.button]
    assert any("🎲" in b for b in buttons), buttons
    assert "Lieber selbst aus der Liste wählen" in buttons, buttons
    print("✓ Würfel-Button und „Lieber selbst wählen“-Link vorhanden")

    # Kategorie-Pille wechseln: Beschreibung engt sich ein, die Liste bleibt
    # trotzdem verborgen -- die Pille allein deckt sie nicht auf.
    at.pills[0].select("Hauptgericht").run()
    assert not at.exception, [e.value for e in at.exception]
    markup_haupt = " ".join(m.value for m in at.markdown)
    assert "aus <b>2 Hauptgerichten</b>" in markup_haupt, markup_haupt[:300]
    assert len(at.selectbox) == 0, "Kategorie-Wahl allein darf die Liste nicht aufdecken"
    print("✓ Kategorie-Pille „Hauptgericht“ engt auf 2 Rezepte ein, Liste bleibt verborgen")

    at.pills[0].select("Suppe").run()
    markup_suppe = " ".join(m.value for m in at.markdown)
    assert "aus <b>1 Suppen</b>" in markup_suppe, markup_suppe[:300]
    print("✓ Kategorie-Pille „Suppe“ engt auf 1 Rezept ein")

    # --- "Lieber selbst wählen" deckt die Liste auf -- beschränkt auf Mahlzeiten
    at_manuell = AppTest.from_file(str(ziel), default_timeout=90)
    at_manuell.run()
    at_manuell.button(key="manuell_umschalten").click().run()
    assert not at_manuell.exception, [e.value for e in at_manuell.exception]
    optionen = at_manuell.selectbox[0].options
    assert optionen == [
        "Griechischer Salat", "Klare Gemüsesuppe", "Rinderbraten", "Tofu-Curry mit Spinat",
    ], optionen
    print("✓ „Lieber selbst wählen“ zeigt nur die 4 Mahlzeiten:", optionen)

    # Auf das Rezept mit geschätzter Basismenge und gemischten Zutaten wechseln
    at_manuell.selectbox[0].set_value("Klare Gemüsesuppe").run()
    markup = " ".join(m.value for m in at_manuell.markdown)
    assert at_manuell.number_input[0].label == "Anzahl Portionen", at_manuell.number_input[0].label
    print("✓ Rezeptwechsel ändert das Skalierungs-Label auf „Anzahl Portionen“")

    assert "geschätzt" in markup, "Hinweis auf geschätzte Basismenge fehlt"
    print("✓ Hinweis auf geschätzte Basismenge")

    # Voreinstellung ist die Familiengroesse (7), nicht die Basismenge (12) --
    # die Mengen sind also von Haus aus heruntergerechnet.
    assert at_manuell.number_input[0].value == 7, at_manuell.number_input[0].value
    assert "583 g" in markup and "Lorbeerblatt" in markup, "Zutatenliste nicht gerendert"
    assert "nach Gefühl" in markup, "Zutat ohne Menge falsch dargestellt"
    print("✓ Zutatenliste auf Standard 7 Portionen: 1000 g → 583 g, inkl. „nach Gefühl“")

    # Auf die Basismenge zurückstellen -- dort müssen die Originalwerte stehen
    at_manuell.number_input[0].set_value(12).run()
    markup_basis = " ".join(m.value for m in at_manuell.markdown)
    assert "1000 g" in markup_basis and "1 TL" in markup_basis, markup_basis[:400]
    print("✓ Auf Basismenge 12 Portionen stehen die Originalmengen (1000 g, 1 TL)")

    # Skalierung 12 -> 24 Portionen
    at_manuell.number_input[0].set_value(24).run()
    markup2 = " ".join(m.value for m in at_manuell.markdown)
    assert "2000 g" in markup2, "Skalierung auf 24 Portionen fehlgeschlagen"
    assert "2 TL" in markup2, "Kleine Menge falsch skaliert"
    assert "Lorbeerblatt" in markup2 and "nach Gefühl" in markup2
    print("✓ Interaktive Skalierung 12 → 24 Portionen: 1000 g → 2000 g, 1 TL → 2 TL")

    # --- Würfel-Button in frischer Instanz (der im Panel, nicht die Bottom-Nav-Kachel)
    at_wuerfel = AppTest.from_file(str(ziel), default_timeout=90)
    at_wuerfel.run()
    wuerfel = at_wuerfel.button(key="wuerfel_dice")
    at2 = wuerfel.click().run()
    assert not at2.exception, [e.value for e in at2.exception]
    texte = [m.value for m in at2.markdown] + [s.value for s in at2.success]
    assert any("Der Würfel sagt" in t for t in texte), "Würfel-Ergebnis nicht angezeigt"
    assert len(at2.selectbox) == 1, "Nach dem Würfeln muss die Liste sichtbar sein"
    print("✓ Würfel-Button liefert ein Rezept und deckt die Liste automatisch auf")

    # --- Ansicht „Fragen“ über die Bottom-Nav
    at_chat = AppTest.from_file(str(ziel), default_timeout=90)
    at_chat.run()
    at_chat.button(key="nav_fragen").click().run()
    assert not at_chat.exception, [e.value for e in at_chat.exception]
    assert len(at_chat.chat_input) == 1, at_chat.chat_input
    print("✓ Ansicht „Fragen“: Chat-Eingabefeld vorhanden")

    markup_chat = " ".join(m.value for m in at_chat.markdown)
    assert "AUS DEM VORRAT" in markup_chat.upper(), "Gruppierte Einstiege fehlen"
    print("✓ Ansicht „Fragen“: gruppierte Einstiege im Leerzustand")

    # --- Schreibzugriff: die Upload-Kachel erscheint nur, wenn ausdrücklich erlaubt
    at_ro = AppTest.from_file(str(ziel), default_timeout=90)
    at_ro.run()
    labels_ro = _nav_labels(at_ro)
    assert labels_ro == ["🎲 Würfeln", "💬 Fragen"], labels_ro
    print("✓ Nur-Lese-Modus (Standard): Bottom-Nav zeigt", labels_ro)

    os.environ["REZEPTE_SCHREIBZUGRIFF"] = "true"
    try:
        at_rw = AppTest.from_file(str(ziel), default_timeout=90)
        at_rw.run()
        assert not at_rw.exception, [e.value for e in at_rw.exception]
        labels_rw = _nav_labels(at_rw)
        assert labels_rw == ["🎲 Würfeln", "💬 Fragen", "📥 Upload"], labels_rw
        print("✓ Schreibzugriff aktiv: Bottom-Nav zeigt", labels_rw)

        # --- Ansicht „Upload“: Statistik-Kacheln und Segment.
        # Direkt in der Upload-Ansicht starten statt über die Nav zu klicken:
        # sonst bleibt das number_input der Würfeln-Ansicht als verwaistes
        # Widget zurück und AppTest stolpert beim nächsten run() darüber.
        at_up = AppTest.from_file(str(ziel), default_timeout=90)
        at_up.session_state["aktive_ansicht"] = "upload"
        at_up.run()
        assert not at_up.exception, [e.value for e in at_up.exception]

        markup_up = " ".join(m.value for m in at_up.markdown)
        assert 'class="zahl">10<' in markup_up, "Gesamtzahl der Statistik falsch"
        print("✓ Ansicht „Upload“: Statistik-Kacheln gerendert (10 Rezepte gesamt)")

        assert len(at_up.radio) == 1, at_up.radio
        assert at_up.radio[0].options[0] == "Verarbeiten", at_up.radio[0].options
        print("✓ Ansicht „Upload“: Segment", at_up.radio[0].options)

        at_up.radio[0].set_value(at_up.radio[0].options[1]).run()
        assert not at_up.exception, [e.value for e in at_up.exception]
        markup_fehler = " ".join(m.value for m in at_up.markdown)
        assert "nicht automatisch auswerten" in markup_fehler, "Fehler-Bereich nicht gerendert"
        print("✓ Ansicht „Upload“: Segment schaltet auf „Fehler“ um")
    finally:
        os.environ.pop("REZEPTE_SCHREIBZUGRIFF", None)

    shutil.rmtree(TEMP, ignore_errors=True)

    print("\nAlle UI-Prüfungen bestanden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
