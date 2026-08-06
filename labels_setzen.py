"""Setzt die Notion-Labels "Vegetarisch" und "Zeitaufwand" fuer alle Rezepte.

Einmaliger Durchgang -- danach halten die Extraktion und dieses Skript die
Labels aktuell. Standardmaessig nur ein Trockenlauf; erst --schreiben aendert
etwas in Notion.

    python3 labels_setzen.py              # zeigt nur, was passieren wuerde
    python3 labels_setzen.py --schreiben  # legt Properties an und setzt Labels

Woher die Werte kommen:
  Vegetarisch  Heuristik ueber die Zutatennamen (models.vegetarisch_geraten).
               Ein bereits in Notion gesetztes Label wird NICHT ueberschrieben
               -- wer dort von Hand korrigiert, behaelt recht. --neu-bewerten
               hebt das auf.
  Zeitaufwand  Gerechnet aus zeit_minuten: <= 30 "Schnell", >= 60 "Ich hab
               Zeit", dazwischen und ohne Zeitangabe leer. Reine Ableitung,
               wird deshalb immer auf den Sollwert gebracht.
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from models import VEG_JA, VEG_NEIN, Rezept
from notion_repo import NotionKonfigurationsFehler, NotionRepo


def _veg_soll(rezept: Rezept, neu_bewerten: bool) -> tuple[bool | None, str]:
    """Zielwert fuer das Vegetarisch-Label und eine Begruendung fuer die Ausgabe."""
    if not rezept.zutaten:
        return None, "keine Zutaten -- keine Aussage moeglich"

    geraten = rezept.vegetarisch_geraten
    if rezept.vegetarisch_label and not neu_bewerten:
        passt = (rezept.vegetarisch_label == VEG_JA) == geraten
        hinweis = "" if passt else f"  ⚠ Heuristik saegt {VEG_JA if geraten else VEG_NEIN}"
        return None, f"bleibt „{rezept.vegetarisch_label}“ (in Notion gesetzt){hinweis}"

    return geraten, VEG_JA if geraten else VEG_NEIN


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schreiben", action="store_true",
                        help="Aenderungen wirklich nach Notion schreiben")
    parser.add_argument("--neu-bewerten", action="store_true",
                        help="auch bereits gesetzte Vegetarisch-Labels ueberschreiben")
    args = parser.parse_args()

    try:
        repo = NotionRepo()
        rezepte = repo.rezepte_laden()
    except NotionKonfigurationsFehler as exc:
        print(f"Abbruch: {exc}")
        return 1

    fehlend = repo.label_properties_fehlen()
    if fehlend:
        if args.schreiben:
            angelegt = repo.label_properties_anlegen()
            print(f"Properties angelegt: {', '.join(angelegt)}\n")
        else:
            print(f"Properties fehlen noch und wuerden angelegt: {', '.join(fehlend)}\n")

    veg_aenderungen = zeit_aenderungen = 0
    konflikte: list[str] = []

    for r in sorted(rezepte, key=lambda x: x.titel):
        if not r.zutaten:
            continue

        veg_neu, veg_text = _veg_soll(r, args.neu_bewerten)
        zeit_soll = r.zeitaufwand_label_soll
        zeit_aendert = zeit_soll != r.zeitaufwand_label

        if veg_neu is None and not zeit_aendert:
            continue

        teile = [veg_text]
        if zeit_aendert:
            teile.append(f"Zeit: {r.zeitaufwand_label or '—'} → {zeit_soll or '—'}"
                         f" ({r.zeit_minuten or '?'} Min)")
        print(f"  {r.titel[:44]:46} {' | '.join(teile)}")

        if "⚠" in veg_text:
            konflikte.append(r.titel)
        if veg_neu is not None:
            veg_aenderungen += 1
        if zeit_aendert:
            zeit_aenderungen += 1

        if args.schreiben:
            repo.labels_schreiben(
                r.page_id,
                vegetarisch=veg_neu,
                zeitaufwand=zeit_soll if zeit_aendert else None,
                zeitaufwand_leeren=zeit_aendert and zeit_soll is None,
            )

    print(f"\nVegetarisch zu setzen: {veg_aenderungen} | Zeitaufwand zu setzen: {zeit_aenderungen}")
    if konflikte:
        print(f"\n⚠ {len(konflikte)} Rezept(e) mit Notion-Label gegen Heuristik — "
              "in Notion pruefen, das Label bleibt unangetastet:")
        for t in konflikte:
            print(f"   {t}")
    if not args.schreiben:
        print("\nTrockenlauf. Mit --schreiben wirklich ausfuehren.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
