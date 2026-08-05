"""Legt aus einem Ordner mit Rezeptfotos je einen Notion-Datenbankeintrag an.

Ein Foto = ein neuer Eintrag mit Status "nicht verarbeitet". Der Titel wird
zunaechst aus dem Dateinamen abgeleitet (Notion verlangt einen Titel beim
Anlegen) -- danach liest die App die echten Zutaten per Vision-Extraktion
aus dem Foto selbst, ueber den bestehenden "Verarbeiten"-Reiter.

Aufruf:  python3 batch_foto_import.py /pfad/zum/fotoordner
"""

from __future__ import annotations

import mimetypes
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from bilder import verkleinern
from notion_repo import NotionRepo

BILD_ENDUNGEN = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
NOTION_UPLOAD_LIMIT = 5 * 1024 * 1024  # Notions Grenze fuer Single-Part-Uploads


def titel_aus_dateiname(pfad: Path) -> str:
    """"omas_apfelkuchen_2.jpg" -> "Omas Apfelkuchen 2" -- nur ein Startpunkt."""
    roh = re.sub(r"[_\-]+", " ", pfad.stem).strip()
    return roh[:1].upper() + roh[1:] if roh else pfad.stem


def main(ordner: str) -> None:
    load_dotenv()
    pfad = Path(ordner).expanduser()
    if not pfad.is_dir():
        sys.exit(f"Kein Ordner: {pfad}")

    dateien = sorted(
        p for p in pfad.iterdir() if p.suffix.lower() in BILD_ENDUNGEN
    )
    if not dateien:
        sys.exit(f"Keine Bilddateien ({', '.join(sorted(BILD_ENDUNGEN))}) in {pfad} gefunden.")

    repo = NotionRepo()
    bereits_importiert = repo.importierte_fotodateinamen()
    print(f"{len(dateien)} Fotos gefunden. Lege Eintraege an …\n")

    erfolge, fehler, uebersprungen = 0, [], 0
    for i, datei in enumerate(dateien, 1):
        if datei.name in bereits_importiert:
            print(f"[{i}/{len(dateien)}] ÜBERSPRUNGEN {datei.name} (schon importiert)")
            uebersprungen += 1
            continue

        titel = titel_aus_dateiname(datei)
        content_type = mimetypes.guess_type(datei.name)[0] or "application/octet-stream"
        dateiname = datei.name
        try:
            inhalt = datei.read_bytes()
            if len(inhalt) > NOTION_UPLOAD_LIMIT:
                # Handyfotos (v.a. "Motion Photos" mit eingebettetem Video) ueberschreiten
                # oft Notions 5-MB-Limit -- verlustarm auf JPEG runterrechnen statt abzubrechen.
                inhalt = verkleinern(inhalt, max_kante=2400, ziel_bytes=NOTION_UPLOAD_LIMIT)
                content_type = "image/jpeg"
                dateiname = Path(datei.stem + ".jpg").name
            upload_id = repo.foto_hochladen(inhalt, dateiname, content_type)
            page_id = repo.seite_aus_foto_erstellen(titel, upload_id, dateiname)
            print(f"[{i}/{len(dateien)}] OK   {titel!r}  ({datei.name})")
            erfolge += 1
        except Exception as exc:
            print(f"[{i}/{len(dateien)}] FEHLER {datei.name}: {exc}")
            fehler.append(datei.name)

    print(f"\n{erfolge} von {len(dateien)} Eintraegen angelegt ({uebersprungen} bereits vorhanden).")
    if fehler:
        print("Fehlgeschlagen:", ", ".join(fehler))
    print(
        "\nNaechster Schritt: App im Tab „Verarbeiten“ oeffnen und die neuen "
        "Eintraege verarbeiten lassen (Titel danach bei Bedarf in Notion korrigieren)."
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Aufruf: python3 batch_foto_import.py /pfad/zum/fotoordner")
    main(sys.argv[1])
