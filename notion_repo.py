"""Notion-Anbindung: Lesen und Zurueckschreiben der Rezept-Datenbank.

Die Datenbank ist die Quelle der Wahrheit (Abschnitt 4.1 des Statusdokuments).
Gelesen wird ueber die offizielle REST-API via notion-client; das Ergebnis wird
in Rezept-Objekte gemappt und in der App gecached.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from notion_client import Client
from notion_client.errors import APIResponseError, HTTPResponseError, RequestTimeoutError

from models import (
    STATUS_ERROR,
    STATUS_PROCESSED,
    STATUS_UNPROCESSED,
    VEG_JA,
    VEG_NEIN,
    ZEIT_LANG,
    ZEIT_SCHNELL,
    Rezept,
    RezeptParseError,
    zutaten_json_parsen,
    zutaten_json_serialisieren,
)

PROP_TITEL = "Titel"
PROP_WEBLINK = "Weblink"
PROP_FOTO = "Foto"
PROP_TEXT = "Rezepttext (manuell)"
PROP_ZUTATEN = "Zutaten (strukturiert)"
PROP_STATUS = "Status"
PROP_VEGETARISCH = "Vegetarisch"
PROP_ZEITAUFWAND = "Zeitaufwand"

# Schema der beiden Label-Properties. Select statt Checkbox, damit "leer" als
# "noch nicht bewertet" lesbar bleibt (siehe models.VEG_JA).
LABEL_SCHEMA: dict[str, dict[str, Any]] = {
    PROP_VEGETARISCH: {
        "select": {"options": [{"name": VEG_JA, "color": "green"},
                               {"name": VEG_NEIN, "color": "default"}]}
    },
    PROP_ZEITAUFWAND: {
        "select": {"options": [{"name": ZEIT_SCHNELL, "color": "yellow"},
                               {"name": ZEIT_LANG, "color": "blue"}]}
    },
}


class NotionFehler(RuntimeError):
    """Basis fuer alles, was die App dem Nutzer als Notion-Problem zeigen soll."""


class NotionKonfigurationsFehler(NotionFehler):
    """Token oder Datenbank-ID fehlen bzw. sind nicht erreichbar."""


class NotionVerbindungsFehler(NotionFehler):
    """Notion war kurzzeitig nicht erreichbar: Timeout, Abbruch, Serverfehler.

    Getrennt von der Konfiguration, weil hier ein erneuter Versuch hilft und
    der Nutzer nichts einrichten muss. RequestTimeoutError ist in notion-client
    ein Geschwister von APIResponseError, kein Untertyp -- ohne eigenen Zweig
    faellt ein Timeout ungefiltert bis in die Oberflaeche durch.
    """


# Mobil und nach dem Community-Cloud-Schlafmodus sind Timeouts wahrscheinlich,
# darum bekommt der Nutzer hier einen Hinweis statt eines Tracebacks.
_VERBINDUNGSFEHLER = (RequestTimeoutError, HTTPResponseError, httpx.RequestError)


def _als_verbindungsfehler(exc: Exception) -> NotionVerbindungsFehler:
    return NotionVerbindungsFehler(
        "Notion antwortet gerade nicht. Das liegt meist an einer kurzen Störung "
        "oder einer wackeligen Verbindung — bitte neu laden oder in der Seitenleiste "
        f"„Aus Notion aktualisieren“ drücken. (Technisch: {type(exc).__name__})"
    )


def _rich_text_to_plain(prop: Optional[dict[str, Any]]) -> Optional[str]:
    """Notion liefert Text als Liste von Rich-Text-Bloecken; hier zusammensetzen.

    Wichtig: lange Texte werden von Notion in 2000-Zeichen-Bloecke zerlegt --
    einfach nur das erste Element zu nehmen wuerde JSON abschneiden.
    """
    if not prop:
        return None
    blocks = prop.get("rich_text") or prop.get("title") or []
    if not blocks:
        return None
    return "".join(b.get("plain_text", "") for b in blocks) or None


def _select_name(prop: Optional[dict[str, Any]]) -> Optional[str]:
    if not prop:
        return None
    sel = prop.get("select")
    return sel.get("name") if sel else None


def _foto_urls(prop: Optional[dict[str, Any]]) -> list[str]:
    """Liest die Datei-URLs aus einer Notion-Files-Property.

    Eigene Uploads liegen unter "file" (S3-Link, laeuft nach ca. einer Stunde ab),
    verlinkte Bilder unter "external". Deshalb erst beim Verarbeiten frisch abrufen,
    nie zwischenspeichern.
    """
    if not prop:
        return []
    urls = []
    for datei in prop.get("files") or []:
        ziel = datei.get("file") or datei.get("external") or {}
        url = ziel.get("url")
        if url:
            urls.append(url)
    return urls


def _plain_to_rich_text(text: str) -> list[dict[str, Any]]:
    """Zerlegt Text in Notion-konforme Bloecke von max. 2000 Zeichen."""
    limit = 2000
    return [
        {"type": "text", "text": {"content": text[i : i + limit]}}
        for i in range(0, max(len(text), 1), limit)
    ]


def _data_source_id_aus_datenbank(antwort: dict[str, Any]) -> str:
    """Liest die Data-Source-ID aus der Retrieve-Database-Antwort (API 2025-09-03)."""
    quellen = antwort.get("data_sources") or []
    if not quellen:
        raise NotionKonfigurationsFehler(
            "Notion-Datenbank enthaelt keine Data Source. "
            "Trage NOTION_DATA_SOURCE_ID in der .env ein "
            "(Notion: Manage data sources -> Copy data source ID)."
        )
    return quellen[0]["id"]


class NotionRepo:
    def __init__(
        self,
        token: Optional[str] = None,
        database_id: Optional[str] = None,
        data_source_id: Optional[str] = None,
    ):
        self.token = token or os.environ.get("NOTION_TOKEN")
        self.database_id = database_id or os.environ.get("NOTION_DATABASE_ID")
        self._data_source_id_cache = data_source_id or os.environ.get("NOTION_DATA_SOURCE_ID")

        if not self.token:
            raise NotionKonfigurationsFehler(
                "NOTION_TOKEN ist nicht gesetzt. Lege in Notion eine interne Integration an "
                "(Settings -> Connections -> Develop or manage integrations), kopiere das "
                "Secret in die .env-Datei und teile die Datenbank 'Rezepte' mit der Integration."
            )
        if not self.database_id:
            raise NotionKonfigurationsFehler(
                "NOTION_DATABASE_ID ist nicht gesetzt. Die ID steht in der URL der Datenbank "
                "(32-stellige Zeichenkette)."
            )

        self.client = Client(auth=self.token)

    def _data_source_id(self) -> str:
        if self._data_source_id_cache:
            return self._data_source_id_cache

        try:
            antwort = self.client.databases.retrieve(database_id=self.database_id)
        except APIResponseError as exc:
            if exc.code == "unauthorized":
                raise NotionKonfigurationsFehler(
                    "NOTION_TOKEN ist ungueltig. Kopiere das Internal Integration Secret "
                    "von notion.so/profile/integrations (Prefix ntn_ oder secret_) "
                    "in die .env-Datei."
                ) from exc
            raise NotionKonfigurationsFehler(
                f"Notion-Datenbank nicht erreichbar ({exc.code}): {exc}. "
                "Pruefe NOTION_DATABASE_ID und ob die Integration Zugriff auf die Datenbank hat."
            ) from exc
        except _VERBINDUNGSFEHLER as exc:
            raise _als_verbindungsfehler(exc) from exc

        self._data_source_id_cache = _data_source_id_aus_datenbank(antwort)
        return self._data_source_id_cache

    # ------------------------------------------------------------------ Lesen

    def rezepte_laden(self) -> list[Rezept]:
        """Laedt alle Seiten der Datenbank, inklusive Pagination."""
        seiten: list[dict[str, Any]] = []
        cursor: Optional[str] = None
        data_source_id = self._data_source_id()

        try:
            while True:
                antwort = self.client.data_sources.query(
                    data_source_id=data_source_id,
                    start_cursor=cursor,
                    page_size=100,
                )
                seiten.extend(antwort.get("results", []))
                if not antwort.get("has_more"):
                    break
                cursor = antwort.get("next_cursor")
        except APIResponseError as exc:
            if exc.code == "unauthorized":
                raise NotionKonfigurationsFehler(
                    "NOTION_TOKEN ist ungueltig. Kopiere das Internal Integration Secret "
                    "von notion.so/profile/integrations (Prefix ntn_ oder secret_) "
                    "in die .env-Datei."
                ) from exc
            raise NotionKonfigurationsFehler(
                f"Notion-Abfrage fehlgeschlagen ({exc.code}): {exc}. "
                "Pruefe, ob die Integration Zugriff auf die Datenbank hat."
            ) from exc
        except _VERBINDUNGSFEHLER as exc:
            raise _als_verbindungsfehler(exc) from exc

        return [self._seite_zu_rezept(s) for s in seiten]

    def _seite_zu_rezept(self, seite: dict[str, Any]) -> Rezept:
        props = seite.get("properties", {})

        titel = _rich_text_to_plain(props.get(PROP_TITEL)) or "(ohne Titel)"
        weblink_prop = props.get(PROP_WEBLINK) or {}

        rezept = Rezept(
            titel=titel,
            page_id=seite.get("id", ""),
            url=seite.get("url", ""),
            weblink=weblink_prop.get("url"),
            status=_select_name(props.get(PROP_STATUS)) or STATUS_UNPROCESSED,
            rezepttext=_rich_text_to_plain(props.get(PROP_TEXT)),
            foto_urls=_foto_urls(props.get(PROP_FOTO)),
            # Fehlen die Properties (noch nicht angelegt), bleibt es bei None
            # und die App rechnet bzw. raet wie bisher.
            vegetarisch_label=_select_name(props.get(PROP_VEGETARISCH)),
            zeitaufwand_label=_select_name(props.get(PROP_ZEITAUFWAND)),
        )

        roh = _rich_text_to_plain(props.get(PROP_ZUTATEN))

        # Nur bei "verarbeitet" erwarten wir ueberhaupt JSON. Fehlerfaelle
        # duerfen die App nicht zum Absturz bringen (Abschnitt 4.2).
        if rezept.status == STATUS_PROCESSED:
            try:
                rezept.anwenden_zutaten_json(zutaten_json_parsen(roh))
            except RezeptParseError as exc:
                rezept.parse_fehler = str(exc)
        elif roh:
            try:
                rezept.anwenden_zutaten_json(zutaten_json_parsen(roh))
            except RezeptParseError:
                pass  # bei nicht-verarbeiteten Rezepten ist fehlendes JSON normal

        return rezept

    # --------------------------------------------------------------- Schreiben

    def zutaten_schreiben(
        self,
        page_id: str,
        zutaten_json: dict[str, Any],
        status: str = STATUS_PROCESSED,
    ) -> None:
        """Schreibt das Extraktionsergebnis zurueck -- immer mit 'JSON:'-Praefix."""
        self.client.pages.update(
            page_id=page_id,
            properties={
                PROP_ZUTATEN: {
                    "rich_text": _plain_to_rich_text(zutaten_json_serialisieren(zutaten_json))
                },
                PROP_STATUS: {"select": {"name": status}},
            },
        )

    # ------------------------------------------------------------- Labels

    def label_properties_fehlen(self) -> list[str]:
        """Welche der Label-Properties es in der Datenbank noch nicht gibt."""
        info = self.client.data_sources.retrieve(data_source_id=self._data_source_id())
        vorhanden = info.get("properties", {})
        return [name for name in LABEL_SCHEMA if name not in vorhanden]

    def label_properties_anlegen(self) -> list[str]:
        """Legt fehlende Label-Properties an. Bestehende bleiben unangetastet.

        Notion ergaenzt beim Update nur die uebergebenen Properties, loescht
        also nichts -- trotzdem werden hier ausdruecklich nur die fehlenden
        geschickt, damit ein manuell angepasstes Schema nicht ueberschrieben wird.
        """
        fehlend = self.label_properties_fehlen()
        if not fehlend:
            return []
        self.client.data_sources.update(
            data_source_id=self._data_source_id(),
            properties={name: LABEL_SCHEMA[name] for name in fehlend},
        )
        return fehlend

    def labels_schreiben(
        self,
        page_id: str,
        vegetarisch: Optional[bool] = None,
        zeitaufwand: Optional[str] = None,
        zeitaufwand_leeren: bool = False,
    ) -> None:
        """Setzt die beiden Label-Properties einer Seite.

        vegetarisch=None laesst das Feld unangetastet. zeitaufwand=None ebenso --
        um es ausdruecklich zu leeren (Rezept liegt zwischen den Schwellen oder
        hat keine Zeitangabe), zeitaufwand_leeren=True setzen.
        """
        properties: dict[str, Any] = {}
        if vegetarisch is not None:
            properties[PROP_VEGETARISCH] = {
                "select": {"name": VEG_JA if vegetarisch else VEG_NEIN}
            }
        if zeitaufwand is not None:
            properties[PROP_ZEITAUFWAND] = {"select": {"name": zeitaufwand}}
        elif zeitaufwand_leeren:
            properties[PROP_ZEITAUFWAND] = {"select": None}

        if properties:
            self.client.pages.update(page_id=page_id, properties=properties)

    def fehler_markieren(self, page_id: str, grund: str) -> None:
        """Setzt Status auf 'Fehler' und haelt den Grund im Freitextfeld fest."""
        self.client.pages.update(
            page_id=page_id,
            properties={
                PROP_STATUS: {"select": {"name": STATUS_ERROR}},
                PROP_TEXT: {"rich_text": _plain_to_rich_text(f"[Automatisch] {grund}")},
            },
        )

    def foto_hochladen(self, inhalt: bytes, dateiname: str, content_type: str) -> str:
        """Laedt eine Datei zu Notion hoch und liefert die file_upload_id.

        Zweistufig laut Notion File-Upload-API: erst die Upload-Absicht anlegen
        (create), dann den Inhalt senden (send). Fuer Dateien <20MB reicht
        "single_part" -- fuer Rezeptfotos immer ausreichend.
        """
        upload = self.client.file_uploads.create(
            mode="single_part", filename=dateiname, content_type=content_type
        )
        self.client.file_uploads.send(
            upload["id"], file=(dateiname, inhalt, content_type)
        )
        return upload["id"]

    def seite_aus_foto_erstellen(self, titel: str, file_upload_id: str, dateiname: str) -> str:
        """Legt einen neuen Datenbankeintrag an und haengt ein hochgeladenes Foto an.

        Status bleibt unbesetzt (-> STATUS_UNPROCESSED beim naechsten Laden), sodass
        der bestehende "Verarbeiten"-Reiter den Eintrag automatisch aufgreift.
        """
        seite = self.client.pages.create(
            parent={"type": "data_source_id", "data_source_id": self._data_source_id()},
            properties={
                PROP_TITEL: {"title": _plain_to_rich_text(titel)},
                PROP_FOTO: {
                    "files": [
                        {
                            "type": "file_upload",
                            "file_upload": {"id": file_upload_id},
                            "name": dateiname,
                        }
                    ]
                },
            },
        )
        return seite["id"]

    def importierte_fotodateinamen(self) -> set[str]:
        """Alle bereits hochgeladenen Dateinamen -- fuer Duplikat-Checks beim Batch-Import."""
        namen: set[str] = set()
        cursor: Optional[str] = None
        data_source_id = self._data_source_id()
        while True:
            antwort = self.client.data_sources.query(
                data_source_id=data_source_id, start_cursor=cursor, page_size=100
            )
            for seite in antwort.get("results", []):
                foto_prop = seite.get("properties", {}).get(PROP_FOTO) or {}
                for datei in foto_prop.get("files") or []:
                    if name := datei.get("name"):
                        namen.add(name)
            if not antwort.get("has_more"):
                break
            cursor = antwort.get("next_cursor")
        return namen

    def titel_setzen(self, page_id: str, titel: str) -> None:
        """Ueberschreibt den Titel -- z.B. mit dem von Claude aus einem Foto erkannten Namen."""
        self.client.pages.update(
            page_id=page_id,
            properties={PROP_TITEL: {"title": _plain_to_rich_text(titel)}},
        )

    def rezepttext_setzen(self, page_id: str, text: str) -> None:
        """Manueller Nachtrag aus der App heraus (Abschnitt 4.5)."""
        self.client.pages.update(
            page_id=page_id,
            properties={
                PROP_TEXT: {"rich_text": _plain_to_rich_text(text)},
                PROP_STATUS: {"select": {"name": STATUS_UNPROCESSED}},
            },
        )
