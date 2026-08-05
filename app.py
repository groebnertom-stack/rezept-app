"""Rezept-App der Familie -- Streamlit-Oberflaeche.

Primaernavigation (Bottom-Bar): Wuerfeln, Fragen, Upload.
Upload erscheint nur mit Schreibzugriff und buendelt in einem Segment:
  Verarbeiten Rezepte mit Status "nicht verarbeitet" extrahieren lassen
  Fehler      Problemfaelle sichten und manuell Text nachtragen

Start:  streamlit run app.py
"""

from __future__ import annotations

import html
import os
import random
import time
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

import bilder as bilder_modul
import llm
from models import (
    KATEGORIEN,
    SCHNELL_SCHWELLE_MINUTEN,
    STATUS_ERROR,
    STATUS_PROCESSED,
    STATUS_UNPROCESSED,
    Rezept,
    RezeptParseError,
    filtern,
    menge_formatieren,
    skalieren,
)
from notion_repo import NotionKonfigurationsFehler, NotionRepo
from scraper import ScrapingFehler, quelle_bestimmen, rezepttext_holen
from theme import CSS, STATUS_PILL

load_dotenv()


def _secrets_in_env_spiegeln() -> None:
    """Uebernimmt st.secrets nach os.environ.

    Lokal kommen die Werte aus der .env, in Streamlit Community Cloud aus den
    App-Secrets. Beide Module lesen danach einheitlich aus os.environ.
    """
    schluessel = (
        "NOTION_TOKEN",
        "NOTION_DATABASE_ID",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "REZEPTE_SCHREIBZUGRIFF",
        "REZEPTE_CHAT_LIMIT",
    )
    try:
        # st.secrets wirft erst beim Zugriff, nicht beim Attributzugriff --
        # deshalb muss der gesamte Lesevorgang im try-Block liegen.
        for name in schluessel:
            if name in st.secrets and not os.environ.get(name):
                os.environ[name] = str(st.secrets[name])
    except Exception:
        return  # keine secrets.toml vorhanden -- bei lokaler .env voellig normal


_secrets_in_env_spiegeln()


def _flag(name: str, standard: str = "false") -> bool:
    return os.environ.get(name, standard).strip().lower() in {"1", "true", "yes", "ja"}


# Schreibzugriff auf Notion (Verarbeiten-Pipeline, manueller Nachtrag).
# In einem oeffentlich erreichbaren Deployment ohne Login standardmaessig AUS --
# sonst koennte jeder Besucher die Datenbank veraendern.
SCHREIBZUGRIFF = _flag("REZEPTE_SCHREIBZUGRIFF", "false")

# Obergrenze fuer LLM-Aufrufe pro Browser-Session. Schuetzt das API-Budget,
# wenn die App oeffentlich erreichbar ist. 0 = kein Limit.
CHAT_LIMIT = int(os.environ.get("REZEPTE_CHAT_LIMIT", "25"))

st.set_page_config(
    page_title="Rezepte der Familie",
    page_icon="🍲",
    layout="centered",
    initial_sidebar_state="collapsed",
)
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------- Daten


@st.cache_resource(show_spinner=False)
def repo_holen() -> NotionRepo:
    return NotionRepo()


@st.cache_data(ttl=900, show_spinner="Rezepte werden aus Notion geladen …")
def rezepte_laden(_repo: NotionRepo, cache_schluessel: int) -> list[Rezept]:
    """cache_schluessel wird beim Aktualisieren hochgezaehlt und leert so den Cache."""
    return _repo.rezepte_laden()


def zustand_init() -> None:
    st.session_state.setdefault("aktive_ansicht", "wuerfeln")
    st.session_state.setdefault("cache_schluessel", 0)
    st.session_state.setdefault("chat_verlauf", [])
    st.session_state.setdefault("gewaehltes_rezept", None)
    st.session_state.setdefault("wuerfel_treffer", None)
    st.session_state.setdefault("wuerfel_rollt", False)
    st.session_state.setdefault("verarbeitung_log", [])
    st.session_state.setdefault("chat_aufrufe", 0)


def neu_laden() -> None:
    st.session_state.cache_schluessel += 1


# ------------------------------------------------------------------ Bausteine


def e(text: Optional[str]) -> str:
    """Escaped Nutzerinhalte, bevor sie in unsafe_allow_html-Markup landen."""
    return html.escape(text or "")


def status_pill(status: str) -> str:
    klasse, label = STATUS_PILL.get(status, ("pill-plain", status))
    return f'<span class="pill {klasse}">{e(label)}</span>'


def hero(eyebrow: str, titel: str, unterzeile: str = "") -> None:
    # Einzeilig aufbauen: eine Leerzeile mitten im HTML-Block laesst Streamlits
    # Markdown-Parser den Block vorzeitig beenden (CommonMark-Regel) und den
    # Rest als Text/Codeblock rendern statt als HTML.
    sub = f'<p class="sub">{e(unterzeile)}</p>' if unterzeile else ""
    st.markdown(
        f'<div class="hero"><div class="eyebrow">{e(eyebrow)}</div>'
        f'<h1>{e(titel)}</h1>{sub}</div>',
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------- Tab: Kochen


def rezept_detail(rezept: Rezept) -> None:
    tags = status_pill(rezept.status)
    if rezept.kategorie:
        titel_zusatz = " (automatisch eingeordnet)" if rezept.kategorie_geraten else ""
        tags += (
            f'<span class="pill pill-ok" title="{e(rezept.kategorie)}{titel_zusatz}">'
            f'{e(rezept.kategorie)}{"?" if rezept.kategorie_geraten else ""}</span>'
        )
    if rezept.zeit_label:
        tags += f'<span class="pill pill-plain">⏱ {e(rezept.zeit_label)}</span>'
    if rezept.basis_geschaetzt:
        tags += '<span class="pill pill-warn">Basismenge geschätzt</span>'
    if rezept.basis_einheit:
        tags += f'<span class="pill pill-plain">{e(rezept.basis_einheit)}</span>'

    st.markdown(f"### {e(rezept.titel)}", unsafe_allow_html=False)
    st.markdown(tags, unsafe_allow_html=True)

    if rezept.weblink:
        st.markdown(f'<p class="muted">Quelle: {e(rezept.weblink)}</p>', unsafe_allow_html=True)

    if rezept.parse_fehler:
        st.error(f"Zutaten-JSON nicht lesbar: {rezept.parse_fehler}")
        return

    if not rezept.ist_skalierbar:
        st.warning(
            "Für dieses Rezept liegen noch keine strukturierten Zutaten vor. "
            "Verarbeite es im Reiter „Verarbeiten“ oder trage im Reiter „Fehler“ Text nach."
        )
        return

    basis = float(rezept.basis_menge)
    schritt = 1.0 if basis >= 2 else 0.5

    links, rechts = st.columns([1, 2.1], gap="large")

    with links:
        obergrenze = basis * 20
        # Standardfall der Familie: sieben am Tisch. Passt die Sieben nicht in
        # den erlaubten Bereich (z. B. Gelee mit zwei Glaesern), bleibt die Basis.
        standard = 7.0 if obergrenze >= 7 else basis
        ziel = st.number_input(
            rezept.einheit_label,
            min_value=schritt,
            max_value=obergrenze,
            value=standard,
            step=schritt,
            key=f"ziel_{rezept.page_id or rezept.titel}",
        )
        faktor = ziel / basis
        st.markdown(
            f'<p class="muted">Original: {menge_formatieren(basis)} '
            f'{e(rezept.basis_einheit or "")} &nbsp;·&nbsp; Faktor {faktor:.2f}×</p>',
            unsafe_allow_html=True,
        )

        if rezept.basis_geschaetzt:
            st.markdown(
                '<div class="hinweis-box">Die Basismenge stammt nicht aus der Quelle, '
                "sondern ist geschätzt. Mengen entsprechend mit Augenmaß behandeln.</div>",
                unsafe_allow_html=True,
            )
        if rezept.hinweis:
            st.markdown(
                f'<div class="hinweis-box">{e(rezept.hinweis)}</div>', unsafe_allow_html=True
            )

    with rechts:
        st.markdown("**Zutaten**")
        zeilen = []
        for z in skalieren(rezept, ziel):
            menge = f"{z.menge_text} {z.einheit}".strip()
            klasse = "zutat-menge" if z.skaliert else "zutat-menge fix"
            anzeige = e(menge) if menge else "nach Gefühl"
            zeilen.append(
                f'<div class="zutat-zeile">'
                f'<div class="{klasse}">{anzeige}</div>'
                f'<div class="zutat-name">{e(z.zutat)}</div>'
                f"</div>"
            )
        st.markdown(
            f'<div class="rezept-karte">{"".join(zeilen)}</div>', unsafe_allow_html=True
        )

        einkaufsliste = "\n".join(
            f"- {f'{z.menge_text} {z.einheit}'.strip()} {z.zutat}".replace("  ", " ")
            for z in skalieren(rezept, ziel)
        )
        with st.expander("Als Einkaufsliste kopieren"):
            st.code(f"{rezept.titel} — {menge_formatieren(ziel)} "
                    f"{rezept.basis_einheit or ''}\n\n{einkaufsliste}", language=None)

    if rezept.zubereitung:
        st.markdown("**Zubereitung**")
        schritte = "".join(
            f'<li><span class="schritt-nr">{i}</span><span class="schritt-text">{e(s)}</span></li>'
            for i, s in enumerate(rezept.zubereitung, 1)
        )
        st.markdown(f'<ol class="zubereitung-liste">{schritte}</ol>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<p class="muted">Keine Zubereitung erfasst — im Reiter „Verarbeiten“ '
            "neu einlesen lassen, um sie nachzuholen.</p>",
            unsafe_allow_html=True,
        )


def zutaten_vorschau(rezept: Rezept, anzahl: int = 4) -> str:
    """Erste Zutaten als Chips -- ersetzt das Foto, das meist fehlt."""
    namen = [z.zutat for z in rezept.zutaten[:anzahl]]
    chips = "".join(f'<span class="zutat-chip">{e(n)}</span>' for n in namen)
    rest = len(rezept.zutaten) - len(namen)
    if rest > 0:
        chips += f'<span class="zutat-rest">+ {rest} weitere</span>'
    return chips


def wuerfel_karte(rezept: Rezept) -> None:
    """Wuerfel-Ergebnis als Typo-Karte: Titel gross, Zutaten als Vorschau."""
    basis = ""
    if rezept.basis_menge:
        basis = f"{menge_formatieren(rezept.basis_menge)} {rezept.basis_einheit or ''}".strip()
    meta = " · ".join(
        t for t in (
            rezept.zeit_label or "",
            f"Original: {basis}" if basis else "",
            f"{len(rezept.zutaten)} Zutaten",
        ) if t
    )
    kategorie = (
        f'<span class="pill pill-ok">{e(rezept.kategorie)}</span>' if rezept.kategorie else ""
    )
    st.markdown(
        f"""<div class="wuerfel-karte">
              <div class="wk-kopf">
                <div class="wk-zeile"><span class="pill pill-plain">🎲 Der Würfel sagt</span>{kategorie}</div>
                <div class="wk-titel">{e(rezept.titel)}</div>
                <div class="wk-meta">{e(meta)}</div>
              </div>
              <div class="wk-body">{zutaten_vorschau(rezept)}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def tab_kochen(rezepte: list[Rezept]) -> None:
    kochbereit = [r for r in rezepte if r.ist_skalierbar]

    hero("Familienküche", "Was kochen wir heute?")

    if not kochbereit:
        st.info("Noch kein Rezept mit strukturierten Zutaten. Starte im Reiter „Verarbeiten“.")
        return

    # Nur Kategorien anbieten, die tatsächlich belegt sind.
    vorhandene = [k for k in KATEGORIEN if any(r.kategorie == k for r in kochbereit)]

    suchspalte, katspalte, zeitspalte = st.columns([2, 2.4, 1.4], gap="medium")

    with suchspalte:
        suche = st.text_input(
            "Suchen", placeholder="Titel oder Zutat, z. B. Kartoffeln", label_visibility="collapsed"
        )
    with katspalte:
        gewaehlte_kats = st.multiselect(
            "Kategorien",
            vorhandene,
            default=[],
            placeholder="Alle Kategorien",
            label_visibility="collapsed",
        )
    with zeitspalte:
        with st.container(key="schnell_filter"):
            nur_schnell = st.checkbox(
                f"⚡ Muss schnell gehen (≤ {SCHNELL_SCHWELLE_MINUTEN} Min)"
            )

    treffer = filtern(kochbereit, suche=suche, kategorien=gewaehlte_kats or None,
                       nur_schnell=nur_schnell)

    # Der Würfel soll ein Abendessen vorschlagen, kein Gelee. Er zieht aus der
    # aktuellen Auswahl, beschränkt auf Mahlzeiten -- außer der Nutzer hat
    # ausdrücklich nach Nachspeisen oder Eingemachtem gefiltert.
    if gewaehlte_kats:
        wuerfel_topf = treffer
    else:
        wuerfel_topf = [r for r in treffer if r.ist_mahlzeit]

    if gewaehlte_kats:
        hinweis = (
            f"Der Würfel zieht aus <b>{len(wuerfel_topf)} Rezepten</b> der aktuellen Auswahl."
        )
    else:
        hinweis = (
            f"Der Würfel zieht aus <b>{len(wuerfel_topf)} Hauptgerichten, Suppen &amp; "
            "Salaten</b> — Nachspeisen, Gebäck und Eingemachtes bleiben außen vor."
        )

    with st.container(key="wuerfel_panel"):
        if st.session_state.wuerfel_rollt:
            st.markdown('<div class="wuerfel-dice-rolling">🎲</div>', unsafe_allow_html=True)
            st.markdown('<div class="wuerfel-panel-label">Würfeln</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="wuerfel-hinweis">{hinweis}</div>', unsafe_allow_html=True)
            time.sleep(0.85)
            st.session_state.wuerfel_rollt = False
            st.rerun()
        else:
            if st.button("🎲", key="wuerfel_dice", disabled=not wuerfel_topf):
                st.session_state.wuerfel_treffer = random.choice(wuerfel_topf).titel
                st.session_state.gewaehltes_rezept = st.session_state.wuerfel_treffer
                st.session_state.wuerfel_rollt = True
                st.rerun()
            st.markdown('<div class="wuerfel-panel-label">Würfeln</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="wuerfel-hinweis">{hinweis}</div>', unsafe_allow_html=True)

    if not treffer:
        hinweis = f"„{suche}“" if suche.strip() else "diesem Filter"
        st.info(f"Kein Rezept passt zu {hinweis}.")
        return

    titel_liste = [r.titel for r in treffer]
    vorauswahl = st.session_state.get("gewaehltes_rezept")
    index = titel_liste.index(vorauswahl) if vorauswahl in titel_liste else 0

    gewaehlt = st.selectbox("Rezept", titel_liste, index=index, label_visibility="collapsed")
    st.session_state.gewaehltes_rezept = gewaehlt

    if st.session_state.wuerfel_treffer == gewaehlt:
        wuerfel_karte(next(r for r in treffer if r.titel == gewaehlt))
        st.session_state.wuerfel_treffer = None

    st.divider()
    rezept_detail(next(r for r in treffer if r.titel == gewaehlt))


# -------------------------------------------------------------- Tab: Fragen


# Einstiege nach Absicht gruppiert -- ein Antippen fuellt die Frage, statt eine
# lange Reihe gleichwertiger Beispiele anzubieten.
FRAGE_GRUPPEN = {
    "Aus dem Vorrat": [
        "Was kann ich mit Kartoffeln und Zwiebeln kochen?",
        "Welche Rezepte sind vegetarisch?",
        "Wofür brauche ich Hefe?",
    ],
    "Für viele Gäste": [
        "Ich habe 12 Gäste — welches Rezept skaliert gut?",
        "Was kann ich vorbereiten?",
    ],
    "Schnell & einfach": [
        "Welches Rezept braucht die wenigsten Zutaten?",
        "Was ist in 30 Minuten fertig?",
    ],
}

ANSCHLUSS_FRAGEN = [
    "Mengen für 7 Personen?",
    "Nur vegetarisch",
    "Was fehlt im Vorrat?",
]


def chat_rezept_karten(antwort: str, rezepte: list[Rezept], grenze: int = 3) -> None:
    """Rezepte, die in der Antwort vorkommen, als Textkarten darunter zeigen."""
    text = antwort.lower()
    treffer = [r for r in rezepte if r.titel and r.titel.lower() in text][:grenze]
    for rezept in treffer:
        zeile = " · ".join(
            t for t in (
                rezept.kategorie or "",
                rezept.zeit_label or "",
                f"{len(rezept.zutaten)} Zutaten",
            ) if t
        )
        namen = ", ".join(z.zutat for z in rezept.zutaten[:4])
        if len(rezept.zutaten) > 4:
            namen += " …"
        st.markdown(
            f"""<div class="mini-karte">
                  <div class="mini-initial">{e(rezept.titel.strip()[:1].upper())}</div>
                  <div>
                    <div class="mini-titel">{e(rezept.titel)}</div>
                    <div class="mini-meta">{e(zeile)}</div>
                    <div class="mini-zutaten">{e(namen)}</div>
                  </div>
                </div>""",
            unsafe_allow_html=True,
        )


def tab_fragen(rezepte: list[Rezept]) -> None:
    nutzbar = [r for r in rezepte if r.zutaten]

    hero(
        "Küchen-Assistent",
        "Frag die Sammlung",
        f"Claude kennt alle {len(nutzbar)} strukturierten Rezepte und antwortet "
        "ausschließlich auf Basis dieser Daten.",
    )

    if not nutzbar:
        st.info("Noch keine strukturierten Rezepte vorhanden — der Assistent hätte keine Datenbasis.")
        return

    schnellfrage = None
    if not st.session_state.chat_verlauf:
        # Leerer Zustand: Einstiege gruppiert anbieten, damit die Eingabe nicht
        # vor einer leeren Flaeche steht.
        with st.container(key="beispielfragen"):
            for titel, fragen in FRAGE_GRUPPEN.items():
                st.markdown(
                    f'<p class="muted" style="text-transform:uppercase;letter-spacing:0.1em;'
                    f'font-size:0.7rem;font-weight:600;margin:0.7rem 0 0.35rem">{e(titel)}</p>',
                    unsafe_allow_html=True,
                )
                spalten = st.columns(len(fragen))
                for spalte, frage in zip(spalten, fragen):
                    with spalte:
                        if st.button(frage, use_container_width=True, key=f"bsp_{frage[:24]}"):
                            schnellfrage = frage
    else:
        # Im Gespraech: Anschlussfragen statt Einstiege.
        with st.container(key="anschlussfragen"):
            spalten = st.columns(len(ANSCHLUSS_FRAGEN))
            for spalte, frage in zip(spalten, ANSCHLUSS_FRAGEN):
                with spalte:
                    if st.button(frage, use_container_width=True, key=f"anschluss_{frage[:24]}"):
                        schnellfrage = frage
        if st.button("Verlauf leeren"):
            st.session_state.chat_verlauf = []
            st.rerun()

    for eintrag in st.session_state.chat_verlauf:
        with st.chat_message(eintrag["role"], avatar="🍲" if eintrag["role"] == "assistant" else "🧑‍🍳"):
            st.markdown(eintrag["content"])
            if eintrag["role"] == "assistant":
                chat_rezept_karten(eintrag["content"], nutzbar)

    verbleibend = CHAT_LIMIT - st.session_state.chat_aufrufe if CHAT_LIMIT else None
    if verbleibend is not None and verbleibend <= 3:
        st.markdown(
            f'<p class="muted">Noch {max(verbleibend, 0)} Fragen in dieser Sitzung.</p>',
            unsafe_allow_html=True,
        )

    eingabe = st.chat_input("Frag mich etwas über eure Rezepte …") or schnellfrage

    if not eingabe:
        return

    if verbleibend is not None and verbleibend <= 0:
        st.warning(
            f"Das Fragen-Limit von {CHAT_LIMIT} pro Sitzung ist erreicht. "
            "Lade die Seite neu, um weiterzufragen."
        )
        return

    with st.chat_message("user", avatar="🧑‍🍳"):
        st.markdown(eingabe)

    with st.chat_message("assistant", avatar="🍲"):
        with st.spinner("Durchsuche die Sammlung …"):
            try:
                antwort = llm.chat_antwort(
                    eingabe, nutzbar, verlauf=st.session_state.chat_verlauf
                )
            except llm.LLMKonfigurationsFehler as exc:
                st.error(str(exc))
                return
            except Exception as exc:  # Netzwerk, Rate-Limit, Modellfehler
                st.error(f"Anfrage fehlgeschlagen: {exc}")
                return
        st.markdown(antwort)
        chat_rezept_karten(antwort, nutzbar)

    st.session_state.chat_aufrufe += 1
    st.session_state.chat_verlauf.append({"role": "user", "content": eingabe})
    st.session_state.chat_verlauf.append({"role": "assistant", "content": antwort})


# ---------------------------------------------------------- Tab: Verarbeiten


def ein_rezept_verarbeiten(repo: NotionRepo, rezept: Rezept) -> tuple[bool, str]:
    """Holt die Quelle, extrahiert das Schema und schreibt es nach Notion zurueck."""
    quelle = quelle_bestimmen(rezept.rezepttext, rezept.weblink, rezept.hat_foto)

    if quelle == "keine":
        grund = "Keine auswertbare Quelle: weder Rezepttext noch Weblink noch Foto hinterlegt."
        repo.fehler_markieren(rezept.page_id, grund)
        return False, grund

    if quelle == "foto":
        try:
            bilder = [bilder_modul.bild_laden(u) for u in rezept.foto_urls]
        except ScrapingFehler as exc:
            repo.fehler_markieren(rezept.page_id, str(exc))
            return False, str(exc)

        try:
            daten = llm.zutaten_aus_bildern_extrahieren(rezept.titel, bilder)
        except llm.ExtraktionsFehler as exc:
            repo.fehler_markieren(rezept.page_id, f"Extraktion fehlgeschlagen: {exc}")
            return False, f"Extraktion fehlgeschlagen: {exc}"
        except Exception as exc:
            return False, f"LLM-Aufruf fehlgeschlagen: {exc}"

        titel_erkannt = daten.pop("titel_erkannt", None)
        if isinstance(titel_erkannt, str):
            titel_erkannt = titel_erkannt.strip() or None
        if titel_erkannt:
            repo.titel_setzen(rezept.page_id, titel_erkannt)

        repo.zutaten_schreiben(rezept.page_id, daten, status=STATUS_PROCESSED)
        anzahl = len(daten.get("zutaten", []))
        titel_hinweis = f' als "{titel_erkannt}"' if titel_erkannt else ""
        return True, f"{anzahl} Zutaten erkannt (Quelle: Foto){titel_hinweis}"

    if quelle == "text":
        rohtext, methode = rezept.rezepttext or "", "manueller Text"
    else:
        try:
            rohtext, methode = rezepttext_holen(rezept.weblink or "")
        except ScrapingFehler as exc:
            repo.fehler_markieren(rezept.page_id, str(exc))
            return False, str(exc)

    try:
        daten = llm.zutaten_extrahieren(rezept.titel, rohtext, rezept.weblink or "")
    except llm.ExtraktionsFehler as exc:
        repo.fehler_markieren(rezept.page_id, f"Extraktion fehlgeschlagen: {exc}")
        return False, f"Extraktion fehlgeschlagen: {exc}"
    except Exception as exc:
        return False, f"LLM-Aufruf fehlgeschlagen: {exc}"

    repo.zutaten_schreiben(rezept.page_id, daten, status=STATUS_PROCESSED)
    anzahl = len(daten.get("zutaten", []))
    return True, f"{anzahl} Zutaten erkannt (Quelle: {methode})"


def verarbeiten_bereich(repo: NotionRepo, rezepte: list[Rezept]) -> None:
    offen = [r for r in rezepte if r.status == STATUS_UNPROCESSED]
    fehlerhaft = [r for r in rezepte if r.status == STATUS_ERROR]

    linke, rechte = st.columns(2, gap="large")
    with linke:
        st.markdown(f"**{len(offen)} Rezepte offen**")
        auch_fehler = st.checkbox(
            f"Die {len(fehlerhaft)} Fehlerfälle erneut versuchen", value=False
        )
    with rechte:
        st.markdown('<p class="muted">Jeder Durchlauf kostet einen LLM-Aufruf pro Rezept.</p>',
                    unsafe_allow_html=True)
        starten = st.button("Verarbeitung starten", type="primary", use_container_width=True)

    warteschlange = offen + (fehlerhaft if auch_fehler else [])

    if warteschlange:
        with st.expander(f"Warteschlange ({len(warteschlange)})", expanded=False):
            for r in warteschlange:
                quelle = quelle_bestimmen(r.rezepttext, r.weblink, r.hat_foto)
                st.markdown(
                    f'<div class="rezept-karte"><b>{e(r.titel)}</b><br>'
                    f'<span class="pill pill-plain">Quelle: {e(quelle)}</span>'
                    f"{status_pill(r.status)}</div>",
                    unsafe_allow_html=True,
                )

    if starten:
        if not warteschlange:
            st.info("Nichts zu tun — alle Rezepte sind verarbeitet.")
        else:
            fortschritt = st.progress(0.0, text="Starte …")
            protokoll = []
            erfolge = 0

            for i, rezept in enumerate(warteschlange, 1):
                fortschritt.progress(
                    (i - 1) / len(warteschlange), text=f"{rezept.titel} ({i}/{len(warteschlange)})"
                )
                try:
                    ok, meldung = ein_rezept_verarbeiten(repo, rezept)
                except Exception as exc:
                    ok, meldung = False, f"Unerwarteter Fehler: {exc}"
                erfolge += int(ok)
                protokoll.append((ok, rezept.titel, meldung))

            fortschritt.progress(1.0, text="Fertig")
            st.session_state.verarbeitung_log = protokoll
            neu_laden()
            st.success(f"{erfolge} von {len(warteschlange)} Rezepten erfolgreich verarbeitet.")

    if st.session_state.verarbeitung_log:
        st.divider()
        st.markdown("**Letzter Durchlauf**")
        for ok, titel, meldung in st.session_state.verarbeitung_log:
            pill = '<span class="pill pill-ok">ok</span>' if ok else '<span class="pill pill-error">Fehler</span>'
            st.markdown(
                f'<div class="rezept-karte">{pill} <b>{e(titel)}</b>'
                f'<br><span class="muted">{e(meldung)}</span></div>',
                unsafe_allow_html=True,
            )


# -------------------------------------------------- Upload: Fehler-Nacharbeit


def fehler_bereich(repo: NotionRepo, rezepte: list[Rezept]) -> None:
    problemfaelle = [
        r for r in rezepte if r.status == STATUS_ERROR or r.parse_fehler
    ]

    st.markdown(
        '<div class="hinweis-box">Quellen, die sich nicht automatisch auswerten ließen. '
        "Rezepttext hier einfügen — beim nächsten Durchlauf wird er bevorzugt "
        "verwendet.</div>",
        unsafe_allow_html=True,
    )

    if not problemfaelle:
        st.success("Keine Fehlerfälle. Die ganze Sammlung ist sauber.")
        return

    for rezept in sorted(problemfaelle, key=lambda r: r.titel.lower()):
        with st.expander(f"{rezept.titel}", expanded=False):
            st.markdown(status_pill(rezept.status), unsafe_allow_html=True)

            if rezept.weblink:
                st.markdown(f'<p class="muted">Quelle: {e(rezept.weblink)}</p>',
                            unsafe_allow_html=True)
            if rezept.parse_fehler:
                st.error(rezept.parse_fehler)
            if rezept.rezepttext:
                st.markdown(f'<p class="muted">Bisheriger Eintrag: {e(rezept.rezepttext[:300])}</p>',
                            unsafe_allow_html=True)

            neuer_text = st.text_area(
                "Rezepttext einfügen",
                key=f"text_{rezept.page_id}",
                height=180,
                placeholder="Zutatenliste und Portionsangabe aus der Quelle hier hineinkopieren …",
            )

            spalte_a, spalte_b = st.columns(2)
            with spalte_a:
                if st.button("Text speichern", key=f"save_{rezept.page_id}",
                             use_container_width=True):
                    if len(neuer_text.strip()) < 30:
                        st.warning("Der Text ist zu kurz für eine sinnvolle Extraktion.")
                    else:
                        repo.rezepttext_setzen(rezept.page_id, neuer_text)
                        neu_laden()
                        st.success("Gespeichert, Status auf „nicht verarbeitet“ gesetzt.")
                        st.rerun()
            with spalte_b:
                if st.button("Speichern und sofort verarbeiten", key=f"proc_{rezept.page_id}",
                             type="primary", use_container_width=True):
                    if len(neuer_text.strip()) < 30:
                        st.warning("Der Text ist zu kurz für eine sinnvolle Extraktion.")
                    else:
                        repo.rezepttext_setzen(rezept.page_id, neuer_text)
                        rezept.rezepttext = neuer_text
                        with st.spinner("Extrahiere Zutaten …"):
                            ok, meldung = ein_rezept_verarbeiten(repo, rezept)
                        neu_laden()
                        (st.success if ok else st.error)(meldung)
                        if ok:
                            st.rerun()


# --------------------------------------------------------------- Tab: Upload


def tab_upload(repo: NotionRepo, rezepte: list[Rezept]) -> None:
    """Steuerung der Verarbeitung und Nacharbeit der Fehlerfaelle in einem Reiter."""
    offen = [r for r in rezepte if r.status == STATUS_UNPROCESSED]
    problemfaelle = [r for r in rezepte if r.status == STATUS_ERROR or r.parse_fehler]

    hero(
        "Datenbasis",
        "Upload & Verarbeitung",
        "Quelle abrufen, Zutaten ins feste Schema übersetzen, Ergebnis zurück nach Notion "
        "schreiben. Priorität: manueller Text vor Weblink vor Foto.",
    )

    st.markdown(
        '<div class="stat-reihe">'
        f'<div class="stat"><div class="zahl">{len(rezepte)}</div>'
        '<div class="label">Rezepte</div></div>'
        f'<div class="stat"><div class="zahl warn">{len(offen)}</div>'
        '<div class="label">offen</div></div>'
        f'<div class="stat"><div class="zahl error">{len(problemfaelle)}</div>'
        '<div class="label">Fehler</div></div>'
        "</div>",
        unsafe_allow_html=True,
    )

    bereich = st.radio(
        "Bereich",
        ["Verarbeiten", f"Fehler · {len(problemfaelle)}"],
        horizontal=True,
        label_visibility="collapsed",
        key="upload_bereich",
    )

    if bereich == "Verarbeiten":
        verarbeiten_bereich(repo, rezepte)
    else:
        fehler_bereich(repo, rezepte)


# ------------------------------------------------------------------- Sidebar


def sidebar(rezepte: Optional[list[Rezept]]) -> None:
    with st.sidebar:
        st.markdown("## 🍲 Rezepte")
        st.markdown('<p class="muted">Familiensammlung · Quelle: Notion</p>',
                    unsafe_allow_html=True)
        st.divider()

        if st.button("↻ Aktualisieren", key="notion_refresh"):
            neu_laden()
            st.rerun()

        if rezepte:
            st.markdown(
                f'<p class="muted">{len(rezepte)} Rezepte geladen</p>',
                unsafe_allow_html=True,
            )


def bottom_nav() -> None:
    aktiv = st.session_state.aktive_ansicht
    ziele = [("wuerfeln", "🎲 Würfeln"), ("fragen", "💬 Fragen")]
    if SCHREIBZUGRIFF:
        ziele.append(("upload", "📥 Upload"))

    with st.container(key="bottom_nav"):
        spalten = st.columns(len(ziele))
        for spalte, (name, label) in zip(spalten, ziele):
            with spalte:
                if st.button(
                    label, key=f"nav_{name}", use_container_width=True,
                    type="primary" if aktiv == name else "secondary",
                ):
                    st.session_state.aktive_ansicht = name
                    st.rerun()




# ---------------------------------------------------------------------- Main


def main() -> None:
    zustand_init()

    try:
        repo = repo_holen()
    except NotionKonfigurationsFehler as exc:
        sidebar(None)
        hero("Einrichtung fehlt", "Rezepte der Familie", "Die App braucht Zugang zu Notion.")
        st.error(str(exc))
        st.stop()

    try:
        rezepte = rezepte_laden(repo, st.session_state.cache_schluessel)
    except NotionKonfigurationsFehler as exc:
        sidebar(None)
        hero("Verbindung fehlgeschlagen", "Rezepte der Familie", "Notion antwortet nicht wie erwartet.")
        st.error(str(exc))
        st.stop()

    sidebar(rezepte)

    # Primaernavigation als Bottom-Bar (Wuerfeln/Fragen/Upload), wie im
    # Design-Prototyp beschrieben. Upload (Verarbeiten + Fehler als Segment)
    # erscheint nur mit Schreibzugriff.
    ansicht = st.session_state.aktive_ansicht
    if ansicht == "upload" and SCHREIBZUGRIFF:
        tab_upload(repo, rezepte)
    elif ansicht == "fragen":
        tab_fragen(rezepte)
    else:
        tab_kochen(rezepte)

    bottom_nav()


if __name__ == "__main__":
    main()
