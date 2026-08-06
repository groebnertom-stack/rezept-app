"""Datenmodell und Skalierungslogik der Rezept-App.

Kern der App: Ein Rezept liegt in Notion als JSON-String im Property
"Zutaten (strukturiert)" mit vorangestelltem "JSON:"-Praefix (siehe Abschnitt 2.3
des Statusdokuments). Dieses Modul kapselt Parsing, Validierung und die
rein rechnerische Skalierung -- ohne LLM-Aufruf.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

JSON_PREFIX = "JSON:"

STATUS_UNPROCESSED = "nicht verarbeitet"
STATUS_PROCESSED = "verarbeitet"
STATUS_ERROR = "Fehler"

# Kategorien. Reihenfolge = Anzeigereihenfolge in der UI.
KAT_HAUPT = "Hauptgericht"
KAT_SUPPE = "Suppe"
KAT_SALAT = "Salat"
KAT_BEILAGE = "Beilage"
KAT_NACHSPEISE = "Nachspeise"
KAT_GEBAECK = "Gebäck"
KAT_EINGEMACHTES = "Eingemachtes"
KAT_GETRAENK = "Getränk"

KATEGORIEN = [
    KAT_HAUPT, KAT_SUPPE, KAT_SALAT, KAT_BEILAGE,
    KAT_NACHSPEISE, KAT_GEBAECK, KAT_EINGEMACHTES, KAT_GETRAENK,
]

# Was auf einen Teller zum Abendessen kommt -- danach würfelt die App.
KATEGORIEN_MAHLZEIT = {KAT_HAUPT, KAT_SUPPE, KAT_SALAT}

# Ab wann ein Rezept als "muss schnell gehen" zaehlt (Gesamtzeit lt. Quelle).
SCHNELL_SCHWELLE_MINUTEN = 30

# Titel-Stichwörter zur Einordnung, wenn das Rezept noch keine Kategorie hat.
# Reihenfolge ist bedeutsam: das erste Treffer-Muster gewinnt, deshalb stehen
# die eindeutigen Fälle (Gelee, Sirup) vor den mehrdeutigen (Kuchen).
_KATEGORIE_MUSTER: list[tuple[str, tuple[str, ...]]] = [
    (KAT_EINGEMACHTES, (
        "gelee", "marmelade", "konfitüre", "konfituere", "chutney", "kompott",
        "eingelegt", "eingemacht", "einmach", "relish", "sauerkraut", "pesto",
    )),
    (KAT_GETRAENK, (
        "limonade", "sirup", "saft", "smoothie", "punsch", "bowle", "glühwein",
        "eistee", "cocktail", "shake", "likör", "likoer",
    )),
    (KAT_NACHSPEISE, (
        "kuchen", "torte", "dessert", "nachspeise", "nachtisch", "pudding",
        "mousse", "tiramisu", "strudel", "speiseeis", "eiscreme",
        "kaiserschmarrn", "apfelmus", "muffin", "waffel", "keks", "plätzchen",
        "praline", "tarte", "cheesecake", "brownie", "crumble",
    )),
    (KAT_GEBAECK, (
        "semmel", "brötchen", "broetchen", "brot", "baguette", "focaccia",
        "brioche", "weckerl", "striezel", "laib", "zopf", "cracker", "knäcke",
    )),
    (KAT_SUPPE, (
        "suppe", "eintopf", "brühe", "bruehe", "kraftbrühe", "keitto",
        "ramen", "bouillon", "consommé", "gulaschsuppe",
    )),
    (KAT_SALAT, ("salat", "coleslaw", "bowl")),
    # "Sauce" und "Soße" fehlen bewusst: zu viele Hauptgerichte tragen sie
    # im Titel ("Ofenlachs in cremiger Sauce").
    (KAT_BEILAGE, (
        "knödel", "knoedel", "klöße", "kloesse", "spätzle", "spaetzle",
        "kartoffelbrei", "püree", "puree", "rotkohl", "blaukraut",
        "beilage", "dip", "brotaufstrich",
    )),
]

# Manche Basiseinheiten verraten die Kategorie zuverlässiger als der Titel.
_EINHEIT_KATEGORIE: dict[str, str] = {
    "gläser": KAT_EINGEMACHTES,
    "glaeser": KAT_EINGEMACHTES,
    "glas": KAT_EINGEMACHTES,
    "semmeln": KAT_GEBAECK,
    "brötchen": KAT_GEBAECK,
    "laibe": KAT_GEBAECK,
    "flaschen": KAT_GETRAENK,
}


def _muster(wort: str) -> "re.Pattern[str]":
    """Baut ein Suchmuster, das am Wortende endet.

    Der Anfang bleibt offen, damit deutsche Komposita greifen: „suppe“ soll
    „Hühnersuppe“ treffen. Das Ende ist dagegen streng, sonst würde „pesto“
    auch „Pestofisch“ und „saft“ auch „Saftiger Ofenlachs“ erwischen.
    Übliche Pluralendungen sind erlaubt („semmel“ trifft „Handsemmeln“).
    """
    return re.compile(re.escape(wort) + r"(?:e|en|n|s|es)?(?![a-zäöüß])")


_MUSTER_CACHE: dict[str, "re.Pattern[str]"] = {
    wort: _muster(wort)
    for _, woerter in _KATEGORIE_MUSTER
    for wort in woerter
}


def kategorie_raten(titel: str, basis_einheit: Optional[str] = None) -> str:
    """Ordnet ein Rezept ein, wenn keine Kategorie hinterlegt ist.

    Nur ein Notbehelf für Altbestand: neu verarbeitete Rezepte bekommen die
    Kategorie vom LLM, das den ganzen Rezepttext kennt und nicht nur den Titel.
    """
    if basis_einheit:
        # "Gläser (à 250 ml)" -> "gläser"
        kopf = basis_einheit.strip().lower().split("(")[0].strip()
        if kopf in _EINHEIT_KATEGORIE:
            return _EINHEIT_KATEGORIE[kopf]

    text = titel.lower()
    for kategorie, stichwoerter in _KATEGORIE_MUSTER:
        if any(_MUSTER_CACHE[wort].search(text) for wort in stichwoerter):
            return kategorie

    return KAT_HAUPT


class RezeptParseError(ValueError):
    """Das JSON eines Rezepts liess sich nicht in das Zielschema ueberfuehren."""


@dataclass
class Zutat:
    zutat: str
    menge: Optional[float] = None
    einheit: Optional[str] = None
    skalierbar: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Zutat":
        name = (raw.get("zutat") or "").strip()
        if not name:
            raise RezeptParseError("Zutat ohne Namen im JSON gefunden.")

        menge = raw.get("menge")
        if menge is not None:
            try:
                menge = float(menge)
            except (TypeError, ValueError):
                # Freitextmengen ("etwas", "1-2") werden als nicht skalierbar behandelt.
                menge = None

        einheit = raw.get("einheit")
        if isinstance(einheit, str):
            einheit = einheit.strip() or None

        # Ohne Menge ist eine Skalierung rechnerisch nicht moeglich, egal was das Flag sagt.
        skalierbar = bool(raw.get("skalierbar", True)) and menge is not None

        return cls(zutat=name, menge=menge, einheit=einheit, skalierbar=skalierbar)

    def to_dict(self) -> dict[str, Any]:
        return {
            "menge": self.menge,
            "einheit": self.einheit,
            "zutat": self.zutat,
            "skalierbar": self.skalierbar,
        }


@dataclass
class Rezept:
    titel: str
    page_id: str = ""
    url: str = ""
    weblink: Optional[str] = None
    status: str = STATUS_UNPROCESSED
    rezepttext: Optional[str] = None
    foto_urls: list[str] = field(default_factory=list)

    basis_menge: Optional[float] = None
    basis_einheit: Optional[str] = None
    basis_geschaetzt: bool = False
    hinweis: Optional[str] = None
    zutaten: list[Zutat] = field(default_factory=list)
    zubereitung: list[str] = field(default_factory=list)
    zeit_minuten: Optional[int] = None

    kategorie: Optional[str] = None
    kategorie_geraten: bool = False

    parse_fehler: Optional[str] = None

    @property
    def hat_foto(self) -> bool:
        return bool(self.foto_urls)

    @property
    def ist_mahlzeit(self) -> bool:
        """Taugt als Abendessen -- Gelee, Sirup und Kuchen fallen raus."""
        return self.kategorie in KATEGORIEN_MAHLZEIT

    @property
    def ist_skalierbar(self) -> bool:
        """Nur mit gueltiger, positiver Basismenge und Zutaten laesst sich rechnen."""
        return (
            self.status == STATUS_PROCESSED
            and self.basis_menge is not None
            and self.basis_menge > 0
            and bool(self.zutaten)
            and self.parse_fehler is None
        )

    @property
    def einheit_label(self) -> str:
        """Beschriftung des Skalierungs-Inputs -- nie hart 'Personen' annehmen."""
        if not self.basis_einheit:
            return "Menge"
        return f"Anzahl {self.basis_einheit}"

    @property
    def zeit_label(self) -> Optional[str]:
        if not self.zeit_minuten:
            return None
        if self.zeit_minuten >= 60:
            stunden, rest = divmod(self.zeit_minuten, 60)
            return f"{stunden} Std {rest} Min" if rest else f"{stunden} Std"
        return f"{self.zeit_minuten} Min"

    @property
    def ist_schnell(self) -> bool:
        return self.zeit_minuten is not None and self.zeit_minuten <= SCHNELL_SCHWELLE_MINUTEN

    def anwenden_zutaten_json(self, data: dict[str, Any]) -> None:
        basis_menge = data.get("basis_menge")
        try:
            self.basis_menge = float(basis_menge) if basis_menge is not None else None
        except (TypeError, ValueError):
            self.basis_menge = None

        einheit = data.get("basis_einheit")
        self.basis_einheit = einheit.strip() if isinstance(einheit, str) and einheit.strip() else None
        self.basis_geschaetzt = bool(data.get("basis_geschaetzt", False))

        hinweis = data.get("hinweis")
        self.hinweis = hinweis.strip() if isinstance(hinweis, str) and hinweis.strip() else None

        rohe_zutaten = data.get("zutaten") or []
        if not isinstance(rohe_zutaten, list):
            raise RezeptParseError("Feld 'zutaten' ist keine Liste.")

        self.zutaten = [Zutat.from_dict(z) for z in rohe_zutaten if isinstance(z, dict)]

        rohe_schritte = data.get("zubereitung") or []
        if isinstance(rohe_schritte, list):
            self.zubereitung = [s.strip() for s in rohe_schritte if isinstance(s, str) and s.strip()]
        else:
            self.zubereitung = []

        try:
            zeit = int(data.get("zeit_minuten"))
            self.zeit_minuten = zeit if zeit > 0 else None
        except (TypeError, ValueError):
            self.zeit_minuten = None

        kategorie = data.get("kategorie")
        if isinstance(kategorie, str) and kategorie.strip() in KATEGORIEN:
            self.kategorie = kategorie.strip()
            self.kategorie_geraten = False
        else:
            # Altbestand ohne Kategorie: aus Titel und Basiseinheit erschließen.
            self.kategorie = kategorie_raten(self.titel, self.basis_einheit)
            self.kategorie_geraten = True

    def als_llm_kontext(self, mit_zubereitung: bool = False) -> dict[str, Any]:
        """Kompakte Darstellung fuer den Chat-Kontext -- ohne Ballast wie page_id.

        Die Zubereitungsschritte bleiben standardmaessig draussen: sie machen
        rund ein Drittel des Kontexts aus, den der Chat bei jeder Frage
        mitschleppt, waehrend die typische Frage ("was kann ich aus Kartoffeln
        kochen") nur Titel, Kategorie und Zutaten braucht. Die Schritte stehen
        weiterhin vollstaendig in der Rezeptansicht.
        """
        daten: dict[str, Any] = {
            "titel": self.titel,
            "kategorie": self.kategorie,
            "quelle": self.weblink,
            "basis_menge": self.basis_menge,
            "basis_einheit": self.basis_einheit,
            "basis_geschaetzt": self.basis_geschaetzt,
            "hinweis": self.hinweis,
            "zeit_minuten": self.zeit_minuten,
            "zutaten": [
                {"menge": z.menge, "einheit": z.einheit, "zutat": z.zutat}
                for z in self.zutaten
            ],
        }
        if mit_zubereitung:
            daten["zubereitung"] = self.zubereitung
        return daten


def zutaten_json_parsen(roh: Optional[str]) -> dict[str, Any]:
    """Entfernt den 'JSON:'-Praefix und parst den Rest.

    Der Praefix existiert, weil die Notion-API einen Property-Wert, der wie
    gueltiges JSON aussieht, sonst als Objekt statt als Text interpretiert.
    """
    if not roh or not roh.strip():
        raise RezeptParseError("Feld 'Zutaten (strukturiert)' ist leer.")

    text = roh.strip()
    if text.startswith(JSON_PREFIX):
        text = text[len(JSON_PREFIX):].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RezeptParseError(f"JSON nicht lesbar: {exc.msg} (Position {exc.pos})") from exc

    if not isinstance(data, dict):
        raise RezeptParseError("Erwartet wurde ein JSON-Objekt.")
    return data


def zutaten_json_serialisieren(data: dict[str, Any]) -> str:
    """Serialisiert mit 'JSON:'-Praefix -- Pflicht beim Zurueckschreiben nach Notion."""
    return JSON_PREFIX + json.dumps(data, ensure_ascii=False, separators=(",", ":"))


# Einheiten, bei denen nur ganze oder halbe Stueck sinnvoll sind. Niemand
# kauft 0,06 Knollensellerie oder wiegt 0,75 Gewuerznelken ab.
ZAEHLBARE_EINHEITEN = {
    "stück", "stk", "stk.", "stueck", "st",
    "dose", "dosen", "glas", "gläser", "packung", "pck", "pck.", "pkg",
    "bund", "zehe", "zehen", "blatt", "blätter", "stiel", "stiele",
    "scheibe", "scheiben", "kugel", "kugeln", "semmel", "semmeln",
    "burrito", "burritos", "ei", "eier", "zweig", "zweige",
}

# Loeffelmasse: Viertelschritte sind abmessbar, alles darunter nicht mehr.
LOEFFEL_EINHEITEN = {"tl", "el", "msp", "msp.", "teelöffel", "esslöffel"}

# Unterhalb dieser Werte ist eine Zahl irrefuehrend -- dann lieber Worte.
SCHWELLE_ZAEHLBAR = 0.25
SCHWELLE_LOEFFEL = 0.125

BRUCHZEICHEN = {0.25: "¼", 0.5: "½", 0.75: "¾", 0.33: "⅓", 0.67: "⅔"}


def _einheit_klasse(einheit: Optional[str]) -> str:
    if not einheit:
        return "roh"
    schluessel = einheit.strip().lower()
    if schluessel in ZAEHLBARE_EINHEITEN:
        return "zaehlbar"
    if schluessel in LOEFFEL_EINHEITEN:
        return "loeffel"
    return "masse"


def _runde_auf(wert: float, schritt: float) -> float:
    """Kaufmaennisch auf ein Vielfaches von schritt runden.

    Nicht round() verwenden: Python rundet 0.5 auf 0 (Banker's Rounding),
    was aus einem halben Porree nichts machen wuerde.
    """
    return math.floor(wert / schritt + 0.5) * schritt


def menge_runden(wert: float, einheit: Optional[str] = None) -> Optional[float]:
    """Rundet auf eine in der Kueche brauchbare Genauigkeit.

    None bedeutet: die Menge ist zu klein für eine sinnvolle Zahl -- der
    Aufrufer soll stattdessen einen Text wie "etwas" anzeigen.
    """
    klasse = _einheit_klasse(einheit)

    if klasse == "zaehlbar":
        if wert < SCHWELLE_ZAEHLBAR:
            return None
        if wert >= 10:
            return float(math.floor(wert + 0.5))
        return _runde_auf(wert, 0.5)

    if klasse == "loeffel":
        if wert < SCHWELLE_LOEFFEL:
            return None
        return _runde_auf(wert, 0.25)

    # Gewicht, Volumen und alles Uebrige: stufenweise nach Groessenordnung
    if wert >= 100:
        return float(math.floor(wert + 0.5))
    if wert >= 10:
        return round(wert, 1)
    if wert >= 1:
        return _runde_auf(wert, 0.25)
    return round(wert, 2)


def menge_formatieren(wert: Optional[float]) -> str:
    """Formatiert eine Menge küchentauglich, mit Bruchzeichen statt Dezimalstellen."""
    if wert is None:
        return ""

    ganz = math.floor(wert + 1e-9)
    rest = round(wert - ganz, 2)

    if math.isclose(rest, 0, abs_tol=1e-9):
        return str(int(ganz))

    if rest in BRUCHZEICHEN:
        bruch = BRUCHZEICHEN[rest]
        return bruch if ganz == 0 else f"{int(ganz)}{bruch}"

    return f"{wert:.2f}".rstrip("0").rstrip(".").replace(".", ",")


@dataclass
class SkalierteZutat:
    zutat: str
    menge_text: str
    einheit: str
    skaliert: bool


def skalieren(rezept: Rezept, ziel_menge: float) -> list[SkalierteZutat]:
    """Rechnet alle Zutaten auf die Zielmenge hoch. Rein lokal, kein LLM.

    Zutaten mit skalierbar=False ("Prise Salz") werden unveraendert uebernommen.
    """
    if not rezept.ist_skalierbar:
        raise RezeptParseError(f"Rezept '{rezept.titel}' ist nicht skalierbar.")

    faktor = ziel_menge / float(rezept.basis_menge)

    ergebnis: list[SkalierteZutat] = []
    for z in rezept.zutaten:
        if z.skalierbar and z.menge is not None:
            neue_menge = menge_runden(z.menge * faktor, z.einheit)

            if neue_menge is None:
                # Zu wenig für eine ehrliche Zahl (0,06 Sellerie, 0,12 TL).
                ergebnis.append(
                    SkalierteZutat(
                        zutat=z.zutat,
                        menge_text="etwas",
                        einheit="",
                        skaliert=True,
                    )
                )
                continue

            ergebnis.append(
                SkalierteZutat(
                    zutat=z.zutat,
                    menge_text=menge_formatieren(neue_menge),
                    einheit=z.einheit or "",
                    skaliert=True,
                )
            )
        else:
            ergebnis.append(
                SkalierteZutat(
                    zutat=z.zutat,
                    menge_text=menge_formatieren(z.menge),
                    einheit=z.einheit or "",
                    skaliert=False,
                )
            )
    return ergebnis


def filtern(
    rezepte: Iterable[Rezept],
    status: Optional[str] = None,
    suche: str = "",
    kategorien: Optional[Iterable[str]] = None,
    nur_schnell: bool = False,
) -> list[Rezept]:
    treffer = list(rezepte)
    if status:
        treffer = [r for r in treffer if r.status == status]
    if kategorien:
        erlaubt = set(kategorien)
        treffer = [r for r in treffer if r.kategorie in erlaubt]
    if nur_schnell:
        treffer = [r for r in treffer if r.ist_schnell]
    if suche.strip():
        needle = suche.strip().lower()
        treffer = [
            r
            for r in treffer
            if needle in r.titel.lower()
            or any(needle in z.zutat.lower() for z in r.zutaten)
        ]
    return sorted(treffer, key=lambda r: r.titel.lower())
