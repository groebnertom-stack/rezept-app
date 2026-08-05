"""Relevante Ausschnitte aus app.py (Streamlit) -- Design-Referenz fuer den Handoff.

Enthalten: Wuerfel-Ergebniskarte, Zutaten-Vorschau, Personen-Default 7,
Fragen-Reiter mit gruppierten Einstiegen, Upload-Reiter (Verarbeitung + Fehler).
Vollstaendige Datei liegt in quellcode/app.py.
"""

def rezept_detail(rezept: Rezept) -> None:
    tags = status_pill(rezept.status)
    if rezept.kategorie:
        titel_zusatz = " (automatisch eingeordnet)" if rezept.kategorie_geraten else ""
        tags += (
            f'<span class="pill pill-ok" title="{e(rezept.kategorie)}{titel_zusatz}">'
            f'{e(rezept.kategorie)}{"?" if rezept.kategorie_geraten else ""}</span>'
        )
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
        t for t in (f"Original: {basis}" if basis else "", f"{len(rezept.zutaten)} Zutaten") if t
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

    hero(
        "Familienküche",
        "Was kochen wir heute?",
        f"{len(kochbereit)} von {len(rezepte)} Rezepten sind kochbereit und lassen sich "
        "auf jede Menge hochrechnen.",
    )
    statistik_reihe(rezepte)

    if not kochbereit:
        st.info("Noch kein Rezept mit strukturierten Zutaten. Starte im Reiter „Verarbeiten“.")
        return

    # Nur Kategorien anbieten, die tatsächlich belegt sind.
    vorhandene = [k for k in KATEGORIEN if any(r.kategorie == k for r in kochbereit)]

    suchspalte, katspalte = st.columns([2, 3], gap="medium")

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

    treffer = filtern(kochbereit, suche=suche, kategorien=gewaehlte_kats or None)

    # Der Würfel soll ein Abendessen vorschlagen, kein Gelee. Er zieht aus der
    # aktuellen Auswahl, beschränkt auf Mahlzeiten -- außer der Nutzer hat
    # ausdrücklich nach Nachspeisen oder Eingemachtem gefiltert.
    if gewaehlte_kats:
        wuerfel_topf = treffer
        wuerfel_label = "🎲  Aus der Auswahl"
    else:
        wuerfel_topf = [r for r in treffer if r.ist_mahlzeit]
        wuerfel_label = "🎲  Was koche ich heute?"

    links, rechts = st.columns([3, 1], gap="medium")
    with rechts:
        if st.button(wuerfel_label, use_container_width=True, type="primary",
                     disabled=not wuerfel_topf):
            st.session_state.wuerfel_treffer = random.choice(wuerfel_topf).titel
            st.session_state.gewaehltes_rezept = st.session_state.wuerfel_treffer
    with links:
        if wuerfel_topf:
            if gewaehlte_kats:
                hinweis = (
                    f"Der Würfel zieht aus <b>{len(wuerfel_topf)} Rezepten</b> "
                    "der aktuellen Auswahl."
                )
            else:
                hinweis = (
                    f"Der Würfel zieht aus <b>{len(wuerfel_topf)} Hauptgerichten, Suppen "
                    "&amp; Salaten</b> — Nachspeisen, Gebäck und Eingemachtes bleiben außen vor."
                )
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
            t for t in (rezept.kategorie or "", f"{len(rezept.zutaten)} Zutaten") if t
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
        "Was willst du wissen?",
        f"Tippe unten frei — beantwortet wird ausschließlich aus euren "
        f"{len(nutzbar)} strukturierten Rezepten.",
    )

    if not nutzbar:
        st.info("Noch keine strukturierten Rezepte vorhanden — der Assistent hätte keine Datenbasis.")
        return

    schnellfrage = None
    if not st.session_state.chat_verlauf:
        # Leerer Zustand: Einstiege gruppiert anbieten, damit die Eingabe nicht
        # vor einer leeren Flaeche steht.
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
        spalten = st.columns(3)
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


# ------------------------------------------------ Upload: Verarbeitungslauf


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
