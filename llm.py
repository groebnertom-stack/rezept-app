"""LLM-Anbindung: Freitext-Chat ueber die Rezeptsammlung und Zutaten-Extraktion.

Zwei getrennte Aufgaben:
1. chat_antwort()  -- beantwortet Nutzerfragen auf Basis der Rezeptdaten
2. zutaten_extrahieren() -- wandelt Rohtext einer Quelle in das Zielschema (2.2)

Beide nutzen Claude. Der Chat bekommt die komplette Sammlung als kompakten
JSON-Kontext: bei einer Familiensammlung (25-200 Rezepte) passt das bequem ins
Kontextfenster, ein Vector-Store waere unnoetige Komplexitaet.
"""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Iterable, Optional

from anthropic import Anthropic

from models import KATEGORIEN, Rezept

MODELL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

CHAT_SYSTEM = """Du bist der Küchen-Assistent einer familieninternen Rezeptsammlung.

Du bekommst die komplette Sammlung als JSON. Beantworte Fragen ausschließlich \
auf Basis dieser Daten.

Regeln:
- Nenne Rezepte immer mit ihrem exakten Titel aus den Daten.
- Erfinde keine Rezepte, keine Zutaten und keine Mengen. Wenn die Sammlung \
nichts Passendes enthält, sage das klar.
- Mengenangaben beziehen sich immer auf die angegebene basis_menge und \
basis_einheit. Wenn du umrechnest, nenne die Bezugsgröße dazu.
- Ist basis_geschaetzt true, weise darauf hin, dass die Basismenge geschätzt ist.
- Achte auf das Feld "kategorie". Fragt jemand nach einem Abendessen oder \
Mittagessen, schlage nichts aus "Eingemachtes", "Getränk" oder "Nachspeise" vor \
— ein Holunderblütengelee ist keine Mahlzeit. Umgekehrt gilt dasselbe: bei der \
Frage nach einem Nachtisch keine Hauptgerichte anbieten.
- Antworte auf Deutsch, knapp und praktisch. Bei Vorschlagslisten: maximal fünf \
Treffer, je mit einem Satz Begründung.
- Du darfst kombinieren und filtern (z.B. "was kann ich aus Kartoffeln und Lauch \
kochen", "welche Rezepte sind vegetarisch", "was geht schnell").
- Feld "zeit_minuten" ist die Gesamtzeit aus der Quelle, falls dort angegeben -- \
sonst null. Ist es null, erfinde keine Zeitangabe; sag stattdessen, dass die \
Quelle keine Zeit nennt. Bei "was geht schnell" nur Rezepte mit gesetztem \
zeit_minuten nennen (Richtwert bis 30 Minuten), nicht raten.
- Feld "zubereitung" enthält die Arbeitsschritte in Reihenfolge. Fragt jemand \
"wie mache ich X" oder "was muss ich tun", fasse diese Schritte zusammen statt \
nur auf Zutaten einzugehen.
"""

EXTRAKTION_SYSTEM = """Du extrahierst aus Rezepttexten strukturierte Zutatenlisten \
und die Zubereitung.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in exakt diesem Schema:

{
  "basis_menge": 4,
  "basis_einheit": "Personen",
  "basis_geschaetzt": false,
  "kategorie": "Hauptgericht",
  "hinweis": "optional, nur bei Besonderheiten",
  "zeit_minuten": 35,
  "zutaten": [
    {"menge": 600, "einheit": "g", "zutat": "Kartoffeln", "skalierbar": true},
    {"menge": null, "einheit": null, "zutat": "Salz", "skalierbar": false}
  ],
  "zubereitung": [
    "Kartoffeln schälen und in 2 cm große Würfel schneiden.",
    "Wasser salzen, Kartoffeln 15 Minuten kochen, bis sie weich sind."
  ]
}

Die Zubereitung ist genauso zentral wie die Zutatenliste, nicht optional:
- Ein Schritt pro Listenelement, in der Reihenfolge der Quelle. Imperativ, knapp \
("Zwiebeln anschwitzen" statt "Die Zwiebeln werden angeschwitzt").
- Fasse die Quelle sinnvoll zusammen, erfinde aber keine Schritte, die nicht \
im Text stehen oder sich nicht zwingend aus den Zutaten ergeben.
- Nennt die Quelle keine Zubereitung (z.B. reine Zutatenliste ohne Anleitung), \
liefere ein leeres Array -- nicht raten.

"zeit_minuten" ist die Gesamtzeit in Minuten als Ganzzahl, falls die Quelle sie \
nennt:
- Nennt die Quelle Zubereitungs- und Kochzeit getrennt, addiere sie.
- Nennt die Quelle nur eine einzelne Zeitangabe ("fertig in 30 Minuten"), nimm \
diese.
- Steht keinerlei Zeitangabe im Text, setze null -- nicht schätzen, nicht raten.

Für "kategorie" ist genau einer dieser Werte erlaubt:
Hauptgericht, Suppe, Salat, Beilage, Nachspeise, Gebäck, Eingemachtes, Getränk

- "Eingemachtes" für alles, was in Gläser abgefüllt und haltbar gemacht wird: \
Gelee, Marmelade, Konfitüre, Chutney, eingelegtes Gemüse, Pesto auf Vorrat.
- "Getränk" für Sirup, Limonade, Punsch, Saft.
- "Gebäck" für Brot, Semmeln, Brötchen — süße Kuchen und Torten gehören \
dagegen zu "Nachspeise".
- "Beilage" für Knödel, Spätzle, Püree, Gemüsebeilagen, Dips.
- Im Zweifel zwischen Hauptgericht und Beilage entscheidet die Menge: Sättigt \
das Gericht allein, ist es ein Hauptgericht.

Regeln:
- basis_einheit ist nicht zwingend "Personen". Nutze, was die Quelle sagt: \
"Personen", "Stücke", "Semmeln", "Gläser (à 250 ml)", "Burritos", "Liter" usw.
- Nennt die Quelle keine Portionszahl, schätze plausibel anhand der Zutatenmengen \
und setze basis_geschaetzt auf true. Begründe die Schätzung kurz im Feld hinweis.
- Zutaten ohne feste Menge ("Prise Salz", "etwas Pfeffer", "Öl zum Braten") \
bekommen menge: null, einheit: null und skalierbar: false.
- Rechne US-Einheiten in metrische um (1 cup Mehl ≈ 120 g, 1 cup Flüssigkeit \
≈ 240 ml, 1 tbsp ≈ 15 ml, 1 tsp ≈ 5 ml). Die Umrechnung passiert hier, nicht \
später in der App.
- Bereiche ("2-3 Zwiebeln") auf den Mittelwert bringen (2.5) oder den unteren \
Wert nehmen, wenn ein Mittelwert unsinnig wäre.
- Übernimm Zutatennamen in der Sprache der Quelle, aber ohne Zubereitungs-Zusätze: \
aus "300 g Kartoffeln, geschält und gewürfelt" wird zutat: "Kartoffeln".
- Keine Erklärung, kein Markdown, kein Codefence. Nur das JSON-Objekt.
"""


class LLMKonfigurationsFehler(RuntimeError):
    pass


class ExtraktionsFehler(RuntimeError):
    pass


def _client() -> Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise LLMKonfigurationsFehler(
            "ANTHROPIC_API_KEY ist nicht gesetzt. Key unter console.anthropic.com "
            "erzeugen und in die .env-Datei eintragen."
        )
    return Anthropic(api_key=key)


def kontext_bauen(rezepte: Iterable[Rezept], max_rezepte: int = 300) -> str:
    """Serialisiert die verwertbaren Rezepte als JSON-Kontext fuer den Chat."""
    nutzbar = [r for r in rezepte if r.zutaten]
    daten = [r.als_llm_kontext() for r in nutzbar[:max_rezepte]]
    return json.dumps(daten, ensure_ascii=False, indent=None)


def chat_antwort(
    frage: str,
    rezepte: Iterable[Rezept],
    verlauf: Optional[list[dict[str, str]]] = None,
    max_tokens: int = 1200,
) -> str:
    """Beantwortet eine Freitextfrage auf Basis der Rezeptsammlung."""
    rezepte = list(rezepte)
    kontext = kontext_bauen(rezepte)

    if not json.loads(kontext):
        return (
            "In der Sammlung ist noch kein Rezept mit strukturierten Zutaten vorhanden. "
            "Verarbeite zuerst ein paar Rezepte über den Reiter „Verarbeiten“."
        )

    nachrichten: list[dict[str, Any]] = []
    for eintrag in (verlauf or [])[-8:]:  # letzte vier Runden reichen als Gedaechtnis
        nachrichten.append({"role": eintrag["role"], "content": eintrag["content"]})

    nachrichten.append(
        {
            "role": "user",
            "content": f"<rezeptsammlung>\n{kontext}\n</rezeptsammlung>\n\nFrage: {frage}",
        }
    )

    antwort = _client().messages.create(
        model=MODELL,
        max_tokens=max_tokens,
        system=CHAT_SYSTEM,
        messages=nachrichten,
    )
    return "".join(block.text for block in antwort.content if block.type == "text").strip()


def _json_aus_antwort(text: str) -> dict[str, Any]:
    """Holt das JSON-Objekt heraus, auch wenn das Modell einen Codefence setzt."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start, ende = text.find("{"), text.rfind("}")
    if start != -1 and ende > start:
        try:
            return json.loads(text[start : ende + 1])
        except json.JSONDecodeError as exc:
            raise ExtraktionsFehler(f"Antwort enthielt kein lesbares JSON: {exc.msg}") from exc
    raise ExtraktionsFehler("Antwort enthielt kein JSON-Objekt.")


def _schema_pruefen(data: dict[str, Any]) -> dict[str, Any]:
    if "zutaten" not in data or not isinstance(data["zutaten"], list):
        raise ExtraktionsFehler("Feld 'zutaten' fehlt oder ist keine Liste.")
    if not data["zutaten"]:
        raise ExtraktionsFehler("Es wurde keine einzige Zutat erkannt.")

    zubereitung = data.get("zubereitung")
    if isinstance(zubereitung, list):
        data["zubereitung"] = [
            s.strip() for s in zubereitung if isinstance(s, str) and s.strip()
        ]
    else:
        data["zubereitung"] = []

    try:
        zeit = int(data.get("zeit_minuten"))
        data["zeit_minuten"] = zeit if zeit > 0 else None
    except (TypeError, ValueError):
        data["zeit_minuten"] = None

    try:
        basis = float(data.get("basis_menge"))
    except (TypeError, ValueError):
        raise ExtraktionsFehler("Feld 'basis_menge' fehlt oder ist keine Zahl.")
    if basis <= 0:
        raise ExtraktionsFehler("'basis_menge' muss größer als 0 sein.")

    data["basis_menge"] = basis
    data.setdefault("basis_einheit", "Personen")
    data["basis_geschaetzt"] = bool(data.get("basis_geschaetzt", False))

    # Kategorie ist erwünscht, aber kein Grund die Extraktion zu verwerfen --
    # models.kategorie_raten() fängt fehlende oder unbekannte Werte auf.
    kategorie = data.get("kategorie")
    if not isinstance(kategorie, str) or kategorie.strip() not in KATEGORIEN:
        data.pop("kategorie", None)
    else:
        data["kategorie"] = kategorie.strip()

    return data


def zutaten_extrahieren(titel: str, rohtext: str, quelle: str = "") -> dict[str, Any]:
    """Wandelt Rohtext in das Zielschema. Wirft ExtraktionsFehler bei Unbrauchbarem."""
    if not rohtext or len(rohtext.strip()) < 30:
        raise ExtraktionsFehler("Quelltext ist zu kurz für eine sinnvolle Extraktion.")

    prompt = (
        f"Rezepttitel: {titel}\n"
        f"Quelle: {quelle or 'unbekannt'}\n\n"
        f"<rezepttext>\n{rohtext[:60000]}\n</rezepttext>"
    )

    antwort = _client().messages.create(
        model=MODELL,
        max_tokens=6000,
        system=EXTRAKTION_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in antwort.content if b.type == "text")
    return _schema_pruefen(_json_aus_antwort(text))


def zutaten_aus_bildern_extrahieren(
    titel: str, bilder: list[tuple[bytes, str]], quelle: str = "Foto"
) -> dict[str, Any]:
    """Wie zutaten_extrahieren(), aber die Quelle sind ein oder mehrere Rezeptfotos.

    Mehrere Bilder gelten als ein Rezept (z.B. Vorder-/Rueckseite einer Karteikarte
    oder mehrere Seiten) und werden gemeinsam in einer Anfrage gelesen.
    """
    if not bilder:
        raise ExtraktionsFehler("Kein Foto zum Auslesen vorhanden.")

    content: list[dict[str, Any]] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.standard_b64encode(daten).decode("ascii"),
            },
        }
        for daten, media_type in bilder
    ]
    content.append(
        {
            "type": "text",
            "text": (
                f"Bisheriger Titel (oft nur ein Dateiname, unzuverlässig): {titel}\n"
                f"Quelle: {quelle}\n\n"
                "Die Bilder oben zeigen dieses eine Rezept, ggf. auf mehreren Seiten "
                "oder Vorder-/Rückseite. Lies Zutaten UND Zubereitungsschritte heraus "
                "und wandle sie in das Schema um -- die Zubereitung ist genauso wichtig "
                "wie die Zutatenliste. Ist die Handschrift oder ein Teil des Fotos "
                "unleserlich, überspringe nur diese einzelne Zutat bzw. diesen einzelnen "
                "Schritt statt die ganze Extraktion abzubrechen.\n\n"
                "Ergänze zusätzlich ein Feld \"titel_erkannt\": ein kurzer, passender "
                "Rezeptname, wie er auf dem Foto steht, oder sonst treffend aus Zutaten "
                "und Zubereitung abgeleitet. Nicht den bisherigen Titel übernehmen, "
                "falls der nur ein Dateiname ist."
            ),
        }
    )

    antwort = _client().messages.create(
        model=MODELL,
        max_tokens=6000,
        system=EXTRAKTION_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(b.text for b in antwort.content if b.type == "text")
    return _schema_pruefen(_json_aus_antwort(text))
