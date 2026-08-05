"""Prüft die Skalierungslogik gegen die echten Notion-Daten.

Die Rezepte sind hier eingebettet, damit der Test ohne Notion-Zugang läuft.
Gesucht wird nach: Parse-Fehlern, Mengen die auf 0 zusammenfallen,
absurden Nachkommastellen und unlesbaren Ausgaben.
"""

import json

from models import Rezept, RezeptParseError, skalieren, zutaten_json_parsen

# Echte Werte aus der Notion-Datenbank (Stand 4.8.2026), gekürzt auf die
# Felder, die für die Skalierung relevant sind.
ECHTE_DATEN = [
    ("Champignons wie vom Weihnachtsmarkt", 'JSON:{"basis_menge":2,"basis_einheit":"Personen","basis_geschaetzt":false,"zutaten":[{"menge":500,"einheit":"g","zutat":"Champignons","skalierbar":true},{"menge":1,"einheit":"Stück","zutat":"kleine Zwiebel","skalierbar":true},{"menge":1,"einheit":"EL","zutat":"Olivenöl","skalierbar":true},{"menge":2,"einheit":"EL","zutat":"Petersilie","skalierbar":true},{"menge":null,"einheit":null,"zutat":"Salz und Pfeffer","skalierbar":false},{"menge":200,"einheit":"g","zutat":"Crème fraîche","skalierbar":true},{"menge":2,"einheit":"Stück","zutat":"Knoblauchzehen","skalierbar":true}]}'),
    ("Klassische Hühnersuppe", 'JSON:{"basis_menge":4,"basis_einheit":"Personen","basis_geschaetzt":false,"zutaten":[{"menge":1,"einheit":"Stück","zutat":"Suppenhuhn","skalierbar":true},{"menge":15,"einheit":"g","zutat":"Butter","skalierbar":true},{"menge":0.5,"einheit":"Stück","zutat":"Porree","skalierbar":true},{"menge":0.125,"einheit":"Stück","zutat":"Knollensellerie","skalierbar":true},{"menge":800,"einheit":"ml","zutat":"Wasser","skalierbar":true},{"menge":2,"einheit":"Stück","zutat":"Pfefferkörner","skalierbar":true},{"menge":1.5,"einheit":"Stück","zutat":"Gewürznelken","skalierbar":true},{"menge":1.5,"einheit":"Stück","zutat":"Piment","skalierbar":true}]}'),
    ("Aloo Gobi", 'JSON:{"basis_menge":4,"basis_einheit":"Personen","basis_geschaetzt":true,"hinweis":"geschätzt","zutaten":[{"menge":0.5,"einheit":"Bund","zutat":"Koriander","skalierbar":true},{"menge":1,"einheit":"TL","zutat":"Kurkuma","skalierbar":true},{"menge":0.5,"einheit":"TL","zutat":"Cayennepfeffer","skalierbar":true},{"menge":600,"einheit":"g","zutat":"Kartoffeln","skalierbar":true},{"menge":200,"einheit":"ml","zutat":"Kokosmilch","skalierbar":true}]}'),
    ("Handsemmeln", 'JSON:{"basis_menge":12,"basis_einheit":"Semmeln","basis_geschaetzt":false,"zutaten":[{"menge":120,"einheit":"g","zutat":"glattes Mehl","skalierbar":true},{"menge":150,"einheit":"ml","zutat":"kaltes Wasser","skalierbar":true},{"menge":5,"einheit":"g","zutat":"Germ","skalierbar":true},{"menge":1,"einheit":"TL","zutat":"Salz","skalierbar":true}]}'),
    ("Soba-Nudeln", 'JSON:{"basis_menge":2,"basis_einheit":"Personen","basis_geschaetzt":false,"zutaten":[{"menge":35,"einheit":"g","zutat":"Pistazien","skalierbar":true},{"menge":0.25,"einheit":"TL","zutat":"Kardamom","skalierbar":true},{"menge":null,"einheit":null,"zutat":"Prise Chili","skalierbar":false},{"menge":15,"einheit":"g","zutat":"Basilikum","skalierbar":true}]}'),
    ("Ottolenghis Roast Chicken", 'JSON:{"basis_menge":5,"basis_einheit":"Personen","basis_geschaetzt":true,"hinweis":"Yield 4-6, Mittelwert","zutaten":[{"menge":8,"einheit":"Stück","zutat":"Hähnchenschenkel","skalierbar":true},{"menge":1.5,"einheit":"TL","zutat":"Salz","skalierbar":true},{"menge":0.5,"einheit":"TL","zutat":"Pfeffer","skalierbar":true},{"menge":240,"einheit":"ml","zutat":"Hühnerbrühe","skalierbar":true},{"menge":45,"einheit":"g","zutat":"Pinienkerne","skalierbar":true}]}'),
    ("Mexikanische Burritos", 'JSON:{"basis_menge":7,"basis_einheit":"Burritos","basis_geschaetzt":true,"hinweis":"6-8, Mittelwert","zutaten":[{"menge":8,"einheit":"Stück","zutat":"Tortillas","skalierbar":true},{"menge":1,"einheit":"Dose","zutat":"Mais","skalierbar":true},{"menge":1,"einheit":"Pck.","zutat":"Taco-Gewürzmischung","skalierbar":true},{"menge":600,"einheit":"g","zutat":"Hackfleisch","skalierbar":true}]}'),
    ("Holunderblütengelee", 'JSON:{"basis_menge":6,"basis_einheit":"Gläser (à 250 ml)","basis_geschaetzt":false,"hinweis":"Ausbeute an Gläsern","zutaten":[{"menge":22,"einheit":"Stück","zutat":"Holunderblütendolden","skalierbar":true},{"menge":1,"einheit":"Liter","zutat":"Apfelsaft","skalierbar":true},{"menge":1,"einheit":"kg","zutat":"Gelierzucker","skalierbar":true},{"menge":2,"einheit":"Stück","zutat":"Zitronen","skalierbar":true}]}'),
    ("Bunter Hirsesalat", 'JSON:{"basis_menge":2,"basis_einheit":"Personen","basis_geschaetzt":false,"zutaten":[{"menge":100,"einheit":"g","zutat":"Hirse","skalierbar":true},{"menge":4,"einheit":"Stiele","zutat":"Petersilie","skalierbar":true},{"menge":2,"einheit":"Stiele","zutat":"Minze","skalierbar":true},{"menge":0.5,"einheit":"Stück","zutat":"Zitrone","skalierbar":true}]}'),
    ("Kartoffelknödel", 'JSON:{"basis_menge":4,"basis_einheit":"Personen","basis_geschaetzt":true,"hinweis":"geschätzt","zutaten":[{"menge":600,"einheit":"g","zutat":"Kartoffeln","skalierbar":true},{"menge":30,"einheit":"g","zutat":"flüssige Butter","skalierbar":true},{"menge":0.5,"einheit":"TL","zutat":"Salz","skalierbar":true},{"menge":1,"einheit":"Stück","zutat":"Ei","skalierbar":true},{"menge":90,"einheit":"g","zutat":"Kartoffelstärke","skalierbar":true}]}'),
]

ZIELFAKTOREN = [0.5, 1, 1.5, 2, 3, 0.25]


def main() -> int:
    befunde: list[str] = []
    rezepte: list[Rezept] = []

    print("\n1. Parsing der echten Daten")
    for titel, roh in ECHTE_DATEN:
        r = Rezept(titel=titel, status="verarbeitet")
        try:
            r.anwenden_zutaten_json(zutaten_json_parsen(roh))
        except RezeptParseError as exc:
            befunde.append(f"PARSE  {titel}: {exc}")
            continue
        if not r.ist_skalierbar:
            befunde.append(f"NICHT SKALIERBAR  {titel}")
            continue
        rezepte.append(r)
    print(f"   {len(rezepte)}/{len(ECHTE_DATEN)} Rezepte sauber geparst")

    print("\n2. Skalierung über alle Faktoren")
    zeilen_gesamt = 0
    for r in rezepte:
        for faktor in ZIELFAKTOREN:
            ziel = r.basis_menge * faktor
            if ziel <= 0:
                continue
            try:
                ergebnis = skalieren(r, ziel)
            except Exception as exc:
                befunde.append(f"CRASH  {r.titel} @ {ziel}: {exc}")
                continue

            for z in ergebnis:
                zeilen_gesamt += 1
                if not z.skaliert:
                    continue
                if z.menge_text in ("0", "", "0,0"):
                    befunde.append(
                        f"NULL   {r.titel} @ {ziel} {r.basis_einheit}: "
                        f"„{z.zutat}“ fällt auf {z.menge_text!r}"
                    )
                if z.menge_text.count(",") and len(z.menge_text.split(",")[1]) > 2:
                    befunde.append(
                        f"STELLEN {r.titel} @ {ziel}: „{z.zutat}“ = {z.menge_text}"
                    )
    print(f"   {zeilen_gesamt} Zutatenzeilen berechnet")

    print("\n3. Stichprobe: kleinste Mengen bei Halbierung")
    for r in rezepte:
        for z in skalieren(r, r.basis_menge * 0.5):
            if z.skaliert and z.einheit in ("TL", "EL", "Stück", "Bund", "Dose", "Pck."):
                print(f"   {r.titel:28.28} {z.menge_text:>6} {z.einheit:6} {z.zutat}")

    print("\n" + "=" * 64)
    if befunde:
        print(f"{len(befunde)} Befunde:\n")
        for b in befunde:
            print("  •", b)
        return 1
    print("Keine Auffälligkeiten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
