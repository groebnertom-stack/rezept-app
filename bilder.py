"""Abruf und Aufbereitung von Rezeptfotos aus Notion.

Notion liefert bei eigenen Uploads zeitlich begrenzte S3-URLs (laufen nach
ca. einer Stunde ab) -- deshalb wird hier immer frisch heruntergeladen, nie
zwischengespeichert. Vor dem Versand an Claude wird auf die von Anthropic
empfohlene Kantenlaenge herunterskaliert und einheitlich als JPEG kodiert;
das haelt Handyfotos zuverlaessig unter dem Groessenlimit der Vision-API.
"""

from __future__ import annotations

import io
from typing import Optional

import requests
from PIL import Image

from scraper import USER_AGENT, ScrapingFehler

TIMEOUT = 20
MAX_KANTE = 1568  # Anthropic-Empfehlung: darueber steigen nur Tokenkosten, nicht die Lesbarkeit


def verkleinern(inhalt: bytes, max_kante: int = MAX_KANTE, ziel_bytes: Optional[int] = None) -> bytes:
    """Skaliert auf max_kante und kodiert als JPEG; senkt bei Bedarf die Qualitaet.

    ziel_bytes erzwingt zusaetzlich eine Obergrenze (z.B. Notions 5-MB-Upload-Limit),
    indem die Qualitaet schrittweise reduziert wird -- fuer Rezeptfotos immer noch
    lesbar, weit bevor die Kompression sichtbar stoert.
    """
    try:
        bild = Image.open(io.BytesIO(inhalt))
        bild.load()
    except Exception as exc:
        raise ScrapingFehler(f"Datei ist kein lesbares Bildformat: {exc}") from exc

    if bild.mode not in ("RGB", "L"):
        bild = bild.convert("RGB")
    if max(bild.size) > max_kante:
        bild.thumbnail((max_kante, max_kante), Image.LANCZOS)

    for qualitaet in (90, 80, 70, 60, 50):
        puffer = io.BytesIO()
        bild.save(puffer, format="JPEG", quality=qualitaet)
        daten = puffer.getvalue()
        if ziel_bytes is None or len(daten) <= ziel_bytes:
            return daten
    return daten  # kleinste probierte Qualitaet, auch wenn ziel_bytes knapp gerissen wird


def bild_laden(url: str) -> tuple[bytes, str]:
    """Laedt ein Foto und liefert es JPEG-kodiert zurueck: (bytes, media_type)."""
    try:
        antwort = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        antwort.raise_for_status()
    except requests.RequestException as exc:
        raise ScrapingFehler(f"Foto nicht abrufbar: {exc}") from exc

    return verkleinern(antwort.content), "image/jpeg"
