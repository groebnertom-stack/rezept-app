"""Abruf von Rezeptquellen.

Erkenntnis aus dem Scraping-Test (Abschnitt 3): schema.org-Recipe-JSON-LD ist
deutlich zuverlaessiger als Fliesstext. Deshalb zweistufig:
1. JSON-LD vom Typ Recipe suchen und in lesbaren Text giessen
2. nur falls das fehlschlaegt: sichtbaren Fliesstext extrahieren
"""

from __future__ import annotations

import json
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 20


class ScrapingFehler(RuntimeError):
    pass


def _seite_laden(url: str) -> str:
    try:
        antwort = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "de,en;q=0.8"},
            timeout=TIMEOUT,
        )
        antwort.raise_for_status()
    except requests.RequestException as exc:
        raise ScrapingFehler(f"Seite nicht abrufbar: {exc}") from exc
    return antwort.text


def _jsonld_objekte(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Sammelt alle JSON-LD-Objekte, auch aus @graph-Containern und Listen."""
    gefunden: list[dict[str, Any]] = []

    for tag in soup.find_all("script", type="application/ld+json"):
        rohtext = tag.string or tag.get_text() or ""
        try:
            daten = json.loads(rohtext)
        except json.JSONDecodeError:
            continue

        stapel = daten if isinstance(daten, list) else [daten]
        while stapel:
            eintrag = stapel.pop()
            if not isinstance(eintrag, dict):
                continue
            if "@graph" in eintrag and isinstance(eintrag["@graph"], list):
                stapel.extend(eintrag["@graph"])
            gefunden.append(eintrag)

    return gefunden


def _ist_recipe(obj: dict[str, Any]) -> bool:
    typ = obj.get("@type")
    if isinstance(typ, list):
        return any(str(t).lower() == "recipe" for t in typ)
    return str(typ).lower() == "recipe"


def _text_aus_recipe(recipe: dict[str, Any]) -> str:
    """Formt das JSON-LD in einen kompakten Rezepttext fuer die LLM-Extraktion."""
    zeilen: list[str] = []

    if name := recipe.get("name"):
        zeilen.append(f"Titel: {name}")

    ertrag = recipe.get("recipeYield")
    if isinstance(ertrag, list):
        ertrag = ertrag[0] if ertrag else None
    if ertrag:
        zeilen.append(f"Ergibt: {ertrag}")

    if beschreibung := recipe.get("description"):
        zeilen.append(f"Beschreibung: {beschreibung}")

    zutaten = recipe.get("recipeIngredient") or recipe.get("ingredients") or []
    if isinstance(zutaten, str):
        zutaten = [zutaten]
    if zutaten:
        zeilen.append("\nZutaten:")
        zeilen.extend(f"- {z}" for z in zutaten)

    anleitung = recipe.get("recipeInstructions")
    schritte: list[str] = []
    if isinstance(anleitung, str):
        schritte = [anleitung]
    elif isinstance(anleitung, list):
        for schritt in anleitung:
            if isinstance(schritt, str):
                schritte.append(schritt)
            elif isinstance(schritt, dict):
                schritte.append(schritt.get("text") or schritt.get("name") or "")
    schritte = [s for s in schritte if s]
    if schritte:
        zeilen.append("\nZubereitung:")
        zeilen.extend(f"{i}. {s}" for i, s in enumerate(schritte, 1))

    return "\n".join(zeilen).strip()


def _fliesstext(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    text = soup.get_text("\n")
    zeilen = [z.strip() for z in text.splitlines()]
    return "\n".join(z for z in zeilen if z)


def rezepttext_holen(url: str) -> tuple[str, str]:
    """Liefert (text, methode). methode ist 'schema.org' oder 'fliesstext'."""
    if not url or not url.startswith(("http://", "https://")):
        raise ScrapingFehler("Kein gültiger Weblink hinterlegt.")

    soup = BeautifulSoup(_seite_laden(url), "html.parser")

    for obj in _jsonld_objekte(soup):
        if _ist_recipe(obj):
            text = _text_aus_recipe(obj)
            if len(text) > 80:
                return text, "schema.org"

    text = _fliesstext(soup)
    if len(text) < 200:
        raise ScrapingFehler(
            "Seite enthält kein schema.org-Recipe und kaum auswertbaren Text "
            "(vermutlich JavaScript-gerendert)."
        )
    return text[:60000], "fliesstext"


def quelle_bestimmen(rezepttext: Optional[str], weblink: Optional[str], hat_foto: bool) -> str:
    """Prioritaet laut Konzept: manueller Text > Weblink > Foto > keine Quelle."""
    if rezepttext and len(rezepttext.strip()) >= 30 and not rezepttext.startswith("[Automatisch]"):
        return "text"
    if weblink:
        return "weblink"
    if hat_foto:
        return "foto"
    return "keine"
