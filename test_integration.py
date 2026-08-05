"""Tests der Randbereiche: LLM-Antwort-Parsing, Notion-Serialisierung, Scraping."""

import json

import pytest
from bs4 import BeautifulSoup

from llm import ExtraktionsFehler, _json_aus_antwort, _schema_pruefen, kontext_bauen
from models import STATUS_PROCESSED, Rezept
from notion_repo import (
    NotionKonfigurationsFehler,
    _data_source_id_aus_datenbank,
    _plain_to_rich_text,
    _rich_text_to_plain,
    _select_name,
)
from scraper import _ist_recipe, _jsonld_objekte, _text_aus_recipe, quelle_bestimmen

# ------------------------------------------------- LLM-Antwort robust parsen


@pytest.mark.parametrize(
    "roh",
    [
        '{"a":1}',
        '```json\n{"a":1}\n```',
        "```\n{\"a\":1}\n```",
        'Hier ist das Ergebnis:\n{"a":1}\nFertig.',
    ],
)
def test_json_aus_antwort(roh):
    assert _json_aus_antwort(roh)["a"] == 1


def test_json_aus_antwort_ohne_json_wirft():
    with pytest.raises(ExtraktionsFehler):
        _json_aus_antwort("Kein JSON hier, sorry.")


# ------------------------------------------------------- Schema-Validierung


def test_schema_setzt_defaults():
    ok = _schema_pruefen({"basis_menge": "4", "zutaten": [{"zutat": "Salz"}]})
    assert ok["basis_menge"] == 4.0
    assert ok["basis_einheit"] == "Personen"
    assert ok["basis_geschaetzt"] is False


@pytest.mark.parametrize(
    "kaputt",
    [
        {"zutaten": []},                                    # keine Zutat erkannt
        {"basis_menge": 4},                                 # Feld zutaten fehlt
        {"basis_menge": 0, "zutaten": [{"zutat": "x"}]},    # Basismenge 0 -> Division
        {"basis_menge": "vier", "zutaten": [{"zutat": "x"}]},
    ],
)
def test_schema_lehnt_unbrauchbares_ab(kaputt):
    with pytest.raises(ExtraktionsFehler):
        _schema_pruefen(kaputt)


# ------------------------------------------------- Notion Rich-Text-Handling


def test_langer_text_wird_gestueckelt_und_verlustfrei_zurueckgelesen():
    """Notion erlaubt nur 2000 Zeichen pro Block -- langes JSON darf nicht abreissen."""
    lang = "x" * 5001
    bloecke = _plain_to_rich_text(lang)
    assert len(bloecke) == 3
    zurueck = _rich_text_to_plain(
        {"rich_text": [{"plain_text": b["text"]["content"]} for b in bloecke]}
    )
    assert zurueck == lang


def test_leerer_text_ergibt_einen_leeren_block():
    assert _plain_to_rich_text("") == [{"type": "text", "text": {"content": ""}}]


def test_fehlende_properties_werfen_nicht():
    assert _rich_text_to_plain(None) is None
    assert _rich_text_to_plain({"rich_text": []}) is None
    assert _select_name(None) is None
    assert _select_name({"select": None}) is None


def test_data_source_id_aus_datenbank():
    antwort = {"data_sources": [{"id": "abc-123", "name": "Rezepte"}]}
    assert _data_source_id_aus_datenbank(antwort) == "abc-123"


def test_data_source_id_fehlt_wirft():
    with pytest.raises(NotionKonfigurationsFehler):
        _data_source_id_aus_datenbank({"data_sources": []})


# ------------------------------------------------------------- Chat-Kontext


def test_kontext_enthaelt_nur_rezepte_mit_zutaten():
    voll = Rezept(titel="A", status=STATUS_PROCESSED)
    voll.anwenden_zutaten_json({"basis_menge": 4, "zutaten": [{"menge": 1, "zutat": "Salz"}]})
    leer = Rezept(titel="B")

    kontext = json.loads(kontext_bauen([voll, leer]))
    assert [k["titel"] for k in kontext] == ["A"]


# ----------------------------------------------------------------- Scraping

HTML_GRAPH = """<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
 {"@type":"WebPage","name":"egal"},
 {"@type":["Recipe","Thing"],"name":"Kartoffelsuppe","recipeYield":["4 Portionen"],
  "recipeIngredient":["600 g Kartoffeln","1 Zwiebel","Salz"],
  "recipeInstructions":[{"@type":"HowToStep","text":"Schaelen."},
                        {"@type":"HowToStep","text":"Kochen."}]}
]}
</script></head><body><p>x</p></body></html>"""


def test_recipe_wird_aus_graph_und_typ_liste_gefunden():
    soup = BeautifulSoup(HTML_GRAPH, "html.parser")
    rezepte = [o for o in _jsonld_objekte(soup) if _ist_recipe(o)]
    assert len(rezepte) == 1

    text = _text_aus_recipe(rezepte[0])
    assert "600 g Kartoffeln" in text
    assert "Ergibt: 4 Portionen" in text
    assert "2. Kochen." in text


def test_kaputtes_jsonld_wird_uebersprungen():
    soup = BeautifulSoup(
        '<script type="application/ld+json">{nicht json}</script>', "html.parser"
    )
    assert _jsonld_objekte(soup) == []


# ------------------------------------------------------ Quellen-Prioritaet


def test_prioritaet_text_vor_weblink_vor_foto():
    assert quelle_bestimmen("Ein ausreichend langer manueller Rezepttext.", "http://x", True) == "text"
    assert quelle_bestimmen(None, "http://x", True) == "weblink"
    assert quelle_bestimmen("kurz", None, True) == "foto"
    assert quelle_bestimmen(None, None, False) == "keine"


def test_automatische_fehlermeldung_gilt_nicht_als_quelle():
    """Sonst würde ein Fehlertext aus einem früheren Lauf als Rezepttext verarbeitet."""
    assert quelle_bestimmen(
        "[Automatisch] Seite nicht abrufbar wegen Timeout beim Laden", "http://x", False
    ) == "weblink"
