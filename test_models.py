"""Tests der Parsing- und Skalierungslogik. Ausfuehren: python -m pytest -q"""

import json

import pytest

from models import (
    JSON_PREFIX,
    STATUS_PROCESSED,
    Rezept,
    RezeptParseError,
    menge_formatieren,
    menge_runden,
    skalieren,
    filtern,
    zutaten_json_parsen,
    zutaten_json_serialisieren,
)


def rezept_bauen(**overrides) -> Rezept:
    daten = {
        "basis_menge": 4,
        "basis_einheit": "Personen",
        "basis_geschaetzt": False,
        "zutaten": [
            {"menge": 600, "einheit": "g", "zutat": "Kartoffeln", "skalierbar": True},
            {"menge": None, "einheit": None, "zutat": "Salz", "skalierbar": False},
        ],
    }
    daten.update(overrides)
    r = Rezept(titel="Testrezept", status=STATUS_PROCESSED)
    r.anwenden_zutaten_json(daten)
    return r


# ---------------------------------------------------------------- Parsing


def test_praefix_wird_entfernt():
    roh = JSON_PREFIX + '{"basis_menge":4,"zutaten":[]}'
    assert zutaten_json_parsen(roh)["basis_menge"] == 4


def test_parsing_ohne_praefix_funktioniert_auch():
    assert zutaten_json_parsen('{"basis_menge":2,"zutaten":[]}')["basis_menge"] == 2


def test_leeres_feld_wirft():
    with pytest.raises(RezeptParseError):
        zutaten_json_parsen("")
    with pytest.raises(RezeptParseError):
        zutaten_json_parsen(None)


def test_kaputtes_json_wirft():
    with pytest.raises(RezeptParseError):
        zutaten_json_parsen(JSON_PREFIX + '{"basis_menge":')


def test_json_array_statt_objekt_wirft():
    with pytest.raises(RezeptParseError):
        zutaten_json_parsen(JSON_PREFIX + "[1,2,3]")


def test_roundtrip_serialisierung():
    daten = {"basis_menge": 4, "basis_einheit": "Gläser (à 250 ml)", "zutaten": []}
    text = zutaten_json_serialisieren(daten)
    assert text.startswith(JSON_PREFIX)
    assert zutaten_json_parsen(text) == daten
    # Umlaute duerfen nicht escaped werden -- sonst steht à in Notion
    assert "à" in text


def test_zutat_ohne_namen_wirft():
    r = Rezept(titel="x")
    with pytest.raises(RezeptParseError):
        r.anwenden_zutaten_json({"basis_menge": 4, "zutaten": [{"menge": 1, "zutat": "  "}]})


def test_menge_als_string_wird_konvertiert():
    r = rezept_bauen(zutaten=[{"menge": "250", "einheit": "g", "zutat": "Mehl"}])
    assert r.zutaten[0].menge == 250.0


def test_unbrauchbare_menge_wird_nicht_skaliert():
    r = rezept_bauen(zutaten=[{"menge": "etwas", "einheit": None, "zutat": "Öl", "skalierbar": True}])
    assert r.zutaten[0].menge is None
    assert r.zutaten[0].skalierbar is False  # ohne Menge nicht rechenbar


# ------------------------------------------------------------- Skalierung


def test_verdoppeln():
    r = rezept_bauen()
    ergebnis = skalieren(r, 8)
    assert ergebnis[0].menge_text == "1200"
    assert ergebnis[0].skaliert is True


def test_halbieren():
    assert skalieren(rezept_bauen(), 2)[0].menge_text == "300"


def test_nicht_skalierbare_zutat_bleibt_unveraendert():
    ergebnis = skalieren(rezept_bauen(), 12)
    salz = ergebnis[1]
    assert salz.zutat == "Salz"
    assert salz.menge_text == ""
    assert salz.skaliert is False


def test_ungerade_zielmenge():
    ergebnis = skalieren(rezept_bauen(), 3)  # Faktor 0.75 -> 450 g
    assert ergebnis[0].menge_text == "450"


def test_kleine_mengen_werden_nicht_auf_null_gerundet():
    r = rezept_bauen(
        basis_menge=4,
        zutaten=[{"menge": 1, "einheit": "TL", "zutat": "Kurkuma", "skalierbar": True}],
    )
    ergebnis = skalieren(r, 2)  # 0.5 TL
    assert ergebnis[0].menge_text == "½"


def test_nicht_skalierbares_rezept_wirft():
    r = Rezept(titel="Leer", status=STATUS_PROCESSED)
    assert r.ist_skalierbar is False
    with pytest.raises(RezeptParseError):
        skalieren(r, 4)


def test_basis_menge_null_ist_nicht_skalierbar():
    r = rezept_bauen(basis_menge=0)
    assert r.ist_skalierbar is False


def test_parse_fehler_blockiert_skalierung():
    r = rezept_bauen()
    r.parse_fehler = "kaputt"
    assert r.ist_skalierbar is False


# ------------------------------------------------------- Einheiten-Labels


@pytest.mark.parametrize(
    "einheit,erwartet",
    [
        ("Personen", "Anzahl Personen"),
        ("Semmeln", "Anzahl Semmeln"),
        ("Gläser (à 250 ml)", "Anzahl Gläser (à 250 ml)"),
        ("Burritos", "Anzahl Burritos"),
        (None, "Menge"),
    ],
)
def test_einheit_label_nie_hart_personen(einheit, erwartet):
    assert rezept_bauen(basis_einheit=einheit).einheit_label == erwartet


# -------------------------------------------------------------- Formatierung


@pytest.mark.parametrize(
    "wert,erwartet",
    # Brüche werden als Zeichen dargestellt, siehe test_kategorien.py
    [(1200.0, "1200"), (0.5, "½"), (2.25, "2¼"), (None, ""), (7.0, "7")],
)
def test_menge_formatieren(wert, erwartet):
    assert menge_formatieren(wert) == erwartet


def test_runden_stufen():
    assert menge_runden(1234.7) == 1235.0     # gross -> ganze Zahl
    assert menge_runden(12.34) == 12.3        # mittel -> eine Nachkommastelle
    assert menge_runden(2.4) == 2.5           # klein -> Viertelschritte
    assert menge_runden(0.333) == 0.33        # sehr klein -> zwei Stellen


# ------------------------------------------------------------------ Filter


def test_filter_nach_zutat():
    a = rezept_bauen()
    a.titel = "Kartoffelsuppe"
    b = rezept_bauen(zutaten=[{"menge": 200, "einheit": "g", "zutat": "Reis"}])
    b.titel = "Risotto"
    assert [r.titel for r in filtern([a, b], suche="reis")] == ["Risotto"]
    assert [r.titel for r in filtern([a, b], suche="kartoffel")] == ["Kartoffelsuppe"]
    assert len(filtern([a, b], suche="")) == 2


def test_filter_sortiert_alphabetisch():
    a, b = rezept_bauen(), rezept_bauen()
    a.titel, b.titel = "Zwiebelkuchen", "Apfelmus"
    assert [r.titel for r in filtern([a, b])] == ["Apfelmus", "Zwiebelkuchen"]


# ------------------------------------------------------------- LLM-Kontext


def test_llm_kontext_ist_serialisierbar_und_kompakt():
    kontext = rezept_bauen().als_llm_kontext()
    json.dumps(kontext)  # darf nicht werfen
    assert "page_id" not in kontext
    assert kontext["basis_einheit"] == "Personen"
