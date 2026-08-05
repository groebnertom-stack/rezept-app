"""Tests für Kategorisierung und einheitenabhängiges Runden."""

import pytest

from models import (
    KAT_BEILAGE,
    KAT_EINGEMACHTES,
    KAT_GEBAECK,
    KAT_GETRAENK,
    KAT_HAUPT,
    KAT_NACHSPEISE,
    KAT_SALAT,
    KAT_SUPPE,
    STATUS_PROCESSED,
    Rezept,
    filtern,
    kategorie_raten,
    menge_formatieren,
    menge_runden,
    skalieren,
)

# --------------------------------------------------------------- Kategorien


@pytest.mark.parametrize(
    "titel,erwartet",
    [
        # Die Fälle, die eine naive Teilstring-Suche falsch einordnet
        ("Pestofisch im Backofen", KAT_HAUPT),            # "pesto"
        ("Zürcher Geschnetzeltes mit Reis", KAT_HAUPT),   # "eis"
        ("Saftiger Ofenlachs in Sauce", KAT_HAUPT),       # "saft"
        # Deutsche Komposita müssen weiterhin greifen
        ("Klassische Hühnersuppe", KAT_SUPPE),
        ("Finnische Lachssuppe", KAT_SUPPE),
        ("Karottenkuchen", KAT_NACHSPEISE),
        ("Holunderblütengelee", KAT_EINGEMACHTES),
        ("Holunderblütensirup", KAT_GETRAENK),
        ("Erdbeermarmelade", KAT_EINGEMACHTES),
        ("Bauernbrot", KAT_GEBAECK),
        ("Griechischer Bauernsalat", KAT_SALAT),
        ("Semmelknödel", KAT_BEILAGE),
        # Pluralformen
        ("Handsemmeln selber machen", KAT_GEBAECK),
        ("Zwiebelsuppen-Variation", KAT_SUPPE),
        # Ohne Signal bleibt es ein Hauptgericht
        ("Bayerische Fleischpflanzerl", KAT_HAUPT),
        ("Tofu-Erdnuss-Curry mit Spinat", KAT_HAUPT),
    ],
)
def test_kategorie_aus_titel(titel, erwartet):
    assert kategorie_raten(titel) == erwartet


@pytest.mark.parametrize(
    "einheit,erwartet",
    [
        ("Gläser (à 250 ml)", KAT_EINGEMACHTES),
        ("Semmeln", KAT_GEBAECK),
        ("Personen", KAT_HAUPT),
    ],
)
def test_basiseinheit_schlaegt_titel(einheit, erwartet):
    """Ein neutraler Titel wird über die Basiseinheit eingeordnet."""
    assert kategorie_raten("Omas Spezialität", einheit) == erwartet


def test_kategorie_aus_json_wird_uebernommen():
    r = Rezept(titel="Holunderblütengelee", status=STATUS_PROCESSED)
    r.anwenden_zutaten_json(
        {"basis_menge": 6, "kategorie": "Nachspeise", "zutaten": [{"menge": 1, "zutat": "Zucker"}]}
    )
    assert r.kategorie == "Nachspeise"       # LLM-Wert gewinnt
    assert r.kategorie_geraten is False


def test_unbekannte_kategorie_faellt_auf_heuristik_zurueck():
    r = Rezept(titel="Holunderblütengelee", status=STATUS_PROCESSED)
    r.anwenden_zutaten_json(
        {"basis_menge": 6, "kategorie": "Fingerfood", "zutaten": [{"menge": 1, "zutat": "Zucker"}]}
    )
    assert r.kategorie == KAT_EINGEMACHTES
    assert r.kategorie_geraten is True


def test_ist_mahlzeit():
    def bauen(kategorie):
        r = Rezept(titel="x", status=STATUS_PROCESSED)
        r.anwenden_zutaten_json(
            {"basis_menge": 4, "kategorie": kategorie, "zutaten": [{"menge": 1, "zutat": "y"}]}
        )
        return r

    assert bauen(KAT_HAUPT).ist_mahlzeit
    assert bauen(KAT_SUPPE).ist_mahlzeit
    assert bauen(KAT_SALAT).ist_mahlzeit
    assert not bauen(KAT_EINGEMACHTES).ist_mahlzeit
    assert not bauen(KAT_NACHSPEISE).ist_mahlzeit
    assert not bauen(KAT_GETRAENK).ist_mahlzeit


def test_filter_nach_kategorie():
    gelee = Rezept(titel="Holunderblütengelee", status=STATUS_PROCESSED)
    gelee.anwenden_zutaten_json({"basis_menge": 6, "zutaten": [{"menge": 1, "zutat": "Zucker"}]})
    curry = Rezept(titel="Tofu-Curry", status=STATUS_PROCESSED)
    curry.anwenden_zutaten_json({"basis_menge": 4, "zutaten": [{"menge": 1, "zutat": "Tofu"}]})

    alle = [gelee, curry]
    assert [r.titel for r in filtern(alle, kategorien=[KAT_HAUPT])] == ["Tofu-Curry"]
    assert [r.titel for r in filtern(alle, kategorien=[KAT_EINGEMACHTES])] == ["Holunderblütengelee"]
    assert len(filtern(alle, kategorien=None)) == 2


# ----------------------------------------------- Einheitenabhängiges Runden


def test_zaehlbare_einheiten_nur_halbe_schritte():
    """0,75 Gewürznelken kann niemand abzählen -- daraus wird 1 Stück."""
    assert menge_runden(0.75, "Stück") == 1.0
    assert menge_runden(0.25, "Stück") == 0.5
    assert menge_runden(1.3, "Stück") == 1.5
    assert menge_runden(4.0, "Stück") == 4.0


def test_halber_porree_wird_nicht_wegge_rundet():
    """Pythons round() macht aus 0.5 eine 0 -- hier darf das nicht passieren."""
    assert menge_runden(0.5, "Stück") == 0.5
    assert menge_runden(0.5, "TL") == 0.5


def test_zu_kleine_zaehlbare_menge_wird_zu_none():
    assert menge_runden(0.0625, "Stück") is None      # 0,06 Knollensellerie
    assert menge_runden(0.1, "Dose") is None


def test_loeffel_in_viertelschritten():
    assert menge_runden(0.125, "TL") == 0.25
    assert menge_runden(0.6, "TL") == 0.5
    assert menge_runden(0.75, "EL") == 0.75
    assert menge_runden(0.1, "TL") is None            # 0,12 TL Kardamom


def test_gewicht_bleibt_feinstufig():
    assert menge_runden(1200.4, "g") == 1200.0
    assert menge_runden(12.34, "ml") == 12.3
    assert menge_runden(0.33, "g") == 0.33            # kein None bei Massen


def test_grosse_stueckzahlen_werden_ganzzahlig():
    assert menge_runden(11.0, "Stück") == 11.0
    assert menge_runden(22.4, "Stück") == 22.0


# ------------------------------------------------------ Bruchdarstellung


@pytest.mark.parametrize(
    "wert,erwartet",
    [(0.5, "½"), (0.25, "¼"), (0.75, "¾"), (1.5, "1½"), (2.25, "2¼"),
     (3.0, "3"), (None, ""), (0.06, "0,06")],
)
def test_menge_formatieren_mit_bruechen(wert, erwartet):
    assert menge_formatieren(wert) == erwartet


def test_zu_kleine_menge_wird_als_etwas_ausgegeben():
    r = Rezept(titel="Suppe", status=STATUS_PROCESSED)
    r.anwenden_zutaten_json({
        "basis_menge": 4,
        "zutaten": [{"menge": 0.125, "einheit": "Stück", "zutat": "Knollensellerie"}],
    })
    zeile = skalieren(r, 2)[0]        # halbiert -> 0,0625 Stück
    assert zeile.menge_text == "etwas"
    assert zeile.einheit == ""
