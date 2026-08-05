"""Diagnose für den Notion-Zugang.

Neben app.py legen und ausführen:  python notion_check.py

Prüft der Reihe nach: wird die .env gefunden, ist der Token plausibel,
akzeptiert Notion ihn, und sieht die Integration die Datenbank.
Der Token wird nie vollständig ausgegeben.
"""

import pathlib
import sys

HIER = pathlib.Path(__file__).parent


def zeile(ok: bool | None, text: str) -> None:
    symbol = {True: "✓", False: "✗", None: "·"}[ok]
    print(f"  {symbol} {text}")


print("\nNotion-Diagnose")
print("=" * 60)

# --- 1. .env vorhanden und lesbar --------------------------------------
print("\n1. Konfigurationsdatei")

env_datei = HIER / ".env"
if not env_datei.exists():
    zeile(False, f".env fehlt in {HIER}")
    print("\n     → cp .env.example .env   und Werte eintragen")
    sys.exit(1)
zeile(True, f".env gefunden: {env_datei}")

try:
    from dotenv import load_dotenv
except ImportError:
    zeile(False, "python-dotenv nicht installiert")
    print("\n     → pip install -r requirements.txt")
    sys.exit(1)

load_dotenv(env_datei)

import os  # noqa: E402  (erst nach load_dotenv sinnvoll)

# --- 2. Token plausibel ------------------------------------------------
print("\n2. Token")

token = os.environ.get("NOTION_TOKEN", "")

if not token:
    zeile(False, "NOTION_TOKEN ist leer oder fehlt in der .env")
    print("\n     → Zeile muss exakt so aussehen (keine Anführungszeichen nötig):")
    print("       NOTION_TOKEN=ntn_xxxxxxxxxxxx")
    sys.exit(1)

zeile(True, f"NOTION_TOKEN gesetzt, Länge {len(token)}, Anfang „{token[:4]}…“")

if token != token.strip():
    zeile(False, "Token hat Leerzeichen oder Zeilenumbruch am Rand — bitte entfernen")
if token.startswith(("secret_", "ntn_")):
    zeile(True, "Präfix sieht nach einem Integration-Secret aus")
else:
    zeile(False, "Unerwartetes Präfix — erwartet wird „ntn_“ oder „secret_“")
    print("     → Vermutlich der OAuth Client Secret statt des Internal Integration Secret.")
    print("       Settings → Connections → Develop or manage integrations →")
    print("       deine Integration → Configuration → Internal Integration Secret")
if len(token) < 40:
    zeile(False, "Token wirkt zu kurz — beim Kopieren abgeschnitten?")

db_id = os.environ.get("NOTION_DATABASE_ID", "").strip()
if db_id:
    nur_hex = db_id.replace("-", "")
    zeile(len(nur_hex) == 32, f"NOTION_DATABASE_ID: {len(nur_hex)} Zeichen (erwartet 32)")
else:
    zeile(False, "NOTION_DATABASE_ID fehlt")

# --- 3. Token gegen die API prüfen -------------------------------------
print("\n3. Antwort von Notion")

try:
    from notion_client import Client
    from notion_client.errors import APIResponseError
except ImportError:
    zeile(False, "notion-client nicht installiert  →  pip install -r requirements.txt")
    sys.exit(1)

client = Client(auth=token)

try:
    ich = client.users.me()
except APIResponseError as exc:
    if exc.code == "unauthorized":
        zeile(False, "Token wird abgelehnt (401 unauthorized)")
        print("\n     Der Token selbst ist ungültig. Häufigste Gründe:")
        print("       • Secret wurde neu generiert → alter Token ist sofort tot")
        print("       • Integration gelöscht")
        print("       • beim Kopieren gekürzt (Copy-Button statt Maus benutzen)")
        print("       • OAuth Client Secret statt Internal Integration Secret erwischt")
    else:
        zeile(False, f"Fehler {exc.code}: {exc}")
    sys.exit(1)
except Exception as exc:
    zeile(False, f"Verbindung fehlgeschlagen: {exc}")
    sys.exit(1)

name = ich.get("name") or ich.get("bot", {}).get("workspace_name") or "unbenannt"
zeile(True, f"Token gültig — angemeldet als Integration „{name}“")

# --- 4. Zugriff auf die Datenbank --------------------------------------
print("\n4. Zugriff auf die Datenbank")

if not db_id:
    zeile(None, "übersprungen, keine NOTION_DATABASE_ID gesetzt")
    sys.exit(1)

try:
    db = client.databases.retrieve(database_id=db_id)
except APIResponseError as exc:
    if exc.code == "object_not_found":
        zeile(False, "Datenbank nicht sichtbar für diese Integration")
        print("\n     → Das ist kein Token-Problem. Die Datenbank in Notion öffnen,")
        print("       rechts oben ··· → Verbindungen → Integration hinzufügen.")
    else:
        zeile(False, f"Fehler {exc.code}: {exc}")
    sys.exit(1)

titel = "".join(t.get("plain_text", "") for t in db.get("title", [])) or "(ohne Titel)"
zeile(True, f"Datenbank erreichbar: „{titel}“")

# Seit API-Version 2025-09-03 haengen Properties und Eintraege nicht mehr an der
# Datenbank selbst, sondern an ihrer Data Source. Gleiche Logik wie notion_repo.
quellen = db.get("data_sources") or []
if not quellen:
    zeile(False, "Datenbank enthält keine Data Source")
    print("\n     → In Notion: ··· → Manage data sources → Copy data source ID,")
    print("       dann NOTION_DATA_SOURCE_ID in die .env eintragen.")
    sys.exit(1)

data_source_id = os.environ.get("NOTION_DATA_SOURCE_ID", "").strip() or quellen[0]["id"]
zeile(True, f"Data Source gefunden ({len(quellen)} vorhanden)")

try:
    quelle = client.data_sources.retrieve(data_source_id=data_source_id)
except APIResponseError as exc:
    zeile(False, f"Data Source nicht lesbar ({exc.code}): {exc}")
    sys.exit(1)

erwartet = {
    "Titel", "Weblink", "Foto", "Rezepttext (manuell)",
    "Zutaten (strukturiert)", "Status",
}
vorhanden = set(quelle.get("properties", {}))
fehlend = erwartet - vorhanden

if fehlend:
    zeile(False, f"Fehlende Properties: {', '.join(sorted(fehlend))}")
else:
    zeile(True, "Alle erwarteten Properties vorhanden")

anzahl = len(
    client.data_sources.query(data_source_id=data_source_id, page_size=100).get("results", [])
)
zeile(True, f"{anzahl} Einträge gelesen")

print("\n" + "=" * 60)
print("Alles in Ordnung. Die App sollte starten.\n")
