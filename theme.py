"""Visuelles Theme der App.

Palette "Beere & Creme": helles Creme-Rosa als Grund, gedecktes Beerenrot als
Akzent, Salbei fuer Kategorien. Grosszuegige Rundungen, Karten mit weichem
Schatten, Pill-Tags, Serif-Headlines gegen Sans-Fliesstext.
"""

FARBEN = {
    "bg": "#FBF6F7",
    "surface": "#FFFFFF",
    "surface_alt": "#F6EBEE",
    "accent": "#C15A76",
    "accent_dark": "#9E3F5A",
    "accent_soft": "#FAE3E9",
    "green": "#3C6F63",
    "green_soft": "#E6EFEA",
    "text": "#2C2126",
    "muted": "#8E7C82",
    "border": "#EFDDE2",
    "warn": "#A9762A",
    "warn_soft": "#F7EFDF",
    "error": "#B4483C",
    "error_soft": "#FAE4E1",
}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap');

@keyframes diceSpin {{
  0%   {{ transform: rotate(0) scale(1); }}
  30%  {{ transform: rotate(210deg) scale(1.1); }}
  60%  {{ transform: rotate(390deg) scale(0.94); }}
  100% {{ transform: rotate(720deg) scale(1); }}
}}
@keyframes cardFlipIn {{
  0%   {{ opacity: 0; transform: translateY(16px) scale(0.94); }}
  100% {{ opacity: 1; transform: translateY(0) scale(1); }}
}}

:root {{
  --bg: {FARBEN["bg"]};
  --surface: {FARBEN["surface"]};
  --surface-alt: {FARBEN["surface_alt"]};
  --accent: {FARBEN["accent"]};
  --accent-dark: {FARBEN["accent_dark"]};
  --accent-soft: {FARBEN["accent_soft"]};
  --green: {FARBEN["green"]};
  --green-soft: {FARBEN["green_soft"]};
  --text: {FARBEN["text"]};
  --muted: {FARBEN["muted"]};
  --border: {FARBEN["border"]};
}}

.stApp {{
  background: var(--bg);
  color: var(--text);
}}

html, body, [class*="css"], .stMarkdown, p, li, label, div {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}}

h1, h2, h3, h4 {{
  font-family: 'Fraunces', Georgia, serif !important;
  color: var(--text) !important;
  letter-spacing: -0.01em;
}}

h1 {{ font-size: 2.1rem !important; font-weight: 700 !important; }}
h2 {{ font-size: 1.5rem !important; font-weight: 600 !important; }}
h3 {{ font-size: 1.1rem !important; font-weight: 600 !important; }}

.block-container {{
  padding-top: 1.6rem;
  padding-bottom: 6rem; /* Platz fuer die fixierte Bottom-Nav */
  max-width: 640px;
}}

@media (max-width: 480px) {{
  .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
  h1 {{ font-size: 1.7rem !important; }}
}}

/* ---------------------------------------------------------------- Sidebar */
section[data-testid="stSidebar"] {{
  background: var(--surface-alt);
  border-right: 1px solid var(--border);
}}
section[data-testid="stSidebar"] .block-container {{ padding-top: 1.6rem; }}

/* ---------------------------------------------------------------- Buttons */
.stButton > button {{
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font-weight: 500;
  padding: 0.5rem 1.15rem;
  transition: all 0.15s ease;
  box-shadow: 0 1px 2px rgba(44,33,38,0.04);
}}
.stButton > button:hover {{
  border-color: var(--accent);
  color: var(--accent-dark);
  transform: translateY(-1px);
}}
.stButton > button[kind="primary"] {{
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}}
.stButton > button[kind="primary"]:hover {{
  background: var(--accent-dark);
  border-color: var(--accent-dark);
  color: #fff;
}}
.st-key-notion_refresh .stButton > button {{
  background: transparent;
  border: none;
  box-shadow: none;
  color: var(--muted);
  font-weight: 400;
  font-size: 0.85rem;
  padding: 0.2rem 0.4rem;
}}
.st-key-notion_refresh .stButton > button:hover {{
  color: var(--accent-dark);
  transform: none;
}}

/* --------------------------------------------------------------- Bottom-Nav */
.st-key-bottom_nav {{
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 999;
  background: var(--surface);
  border-top: 1px solid var(--border);
  box-shadow: 0 -4px 16px rgba(44,33,38,0.06);
  padding: 0.5rem max(1rem, calc(50% - 320px)) calc(0.5rem + env(safe-area-inset-bottom));
}}
/* Streamlit gibt Spalten serverseitig ein min-width von "calc(100% - 24px)" mit,
   damit sie auf schmalen Viewports untereinander stapeln. Bei der Bottom-Nav ist
   genau das unerwuenscht -- drei Kacheln muessen auch auf 375px in einer Zeile
   bleiben, sonst verdeckt die auf drei Zeilen aufgeblaehte Nav den Chat-Input. */
.st-key-bottom_nav [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; }}
.st-key-bottom_nav [data-testid="stColumn"] {{ min-width: 0 !important; }}
.st-key-bottom_nav .stButton > button {{
  width: 100%;
  min-height: 44px;
  border: none;
  box-shadow: none;
  background: transparent;
  color: var(--muted);
  font-weight: 500;
  border-radius: 14px;
  padding: 0.55rem 0.3rem;
  white-space: nowrap;
  font-size: 0.85rem;
}}
.st-key-bottom_nav .stButton > button[kind="primary"] {{
  background: var(--accent-soft);
  color: var(--accent-dark);
  font-weight: 600;
}}
.st-key-bottom_nav .stButton > button:hover {{
  transform: none;
  color: var(--accent-dark);
}}

/* Streamlits eigener Chat-Input klebt nativ am Fensterrand (position: sticky) --
   ueber die Bottom-Nav heben, sonst ueberlappen sich beide. */
[data-testid="stBottom"] {{
  bottom: 4.5rem !important;
}}

/* ------------------------------------------- Segment (Upload: Radio-Zeile) */
.st-key-upload_bereich div[role="radiogroup"] {{
  display: flex;
  gap: 0.25rem;
  background: var(--surface-alt);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 3px;
  margin-bottom: 1rem;
}}
.st-key-upload_bereich div[role="radiogroup"] label {{
  flex: 1;
  justify-content: center;
  border-radius: 999px;
  padding: 0.5rem 0.9rem;
  margin: 0;
  color: var(--muted);
  font-weight: 500;
  font-size: 0.86rem;
  white-space: nowrap;
  cursor: pointer;
}}
.st-key-upload_bereich div[role="radiogroup"] label:has(input:checked) {{
  background: var(--surface);
  color: var(--accent-dark);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(44,33,38,0.08);
}}
.st-key-upload_bereich div[role="radiogroup"] label > div:first-child {{ display: none; }}

/* ------------------------------------------------------------------- Tabs */
.stTabs [data-baseweb="tab-list"] {{
  gap: 0.35rem;
  background: transparent;
  border-bottom: 1px solid var(--border);
}}
.stTabs [data-baseweb="tab"] {{
  border-radius: 999px 999px 0 0;
  padding: 0.55rem 1.1rem;
  font-weight: 500;
  color: var(--muted);
}}
.stTabs [aria-selected="true"] {{
  background: var(--surface);
  color: var(--accent-dark) !important;
  border-bottom: 2px solid var(--accent);
}}

/* ------------------------------------------------------------------ Cards */
.rezept-karte {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 1.1rem 1.25rem;
  margin-bottom: 0.7rem;
  box-shadow: 0 2px 10px rgba(44,33,38,0.05);
}}
.rezept-karte h3 {{ margin: 0 0 0.35rem 0 !important; }}

.hero {{
  background: linear-gradient(135deg, var(--accent-soft) 0%, var(--surface-alt) 100%);
  border: 1px solid var(--border);
  border-radius: 28px;
  padding: 1.6rem 1.9rem;
  margin-bottom: 1.4rem;
}}
.hero .eyebrow {{
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent-dark);
  margin-bottom: 0.3rem;
}}
.hero h1 {{ margin: 0 0 0.25rem 0 !important; }}
.hero .sub {{ color: var(--muted); font-size: 0.94rem; margin: 0; }}

/* ------------------------------------------------------------------- Pills */
.pill {{
  display: inline-block;
  padding: 0.22rem 0.72rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  margin-right: 0.35rem;
  margin-bottom: 0.25rem;
  border: 1px solid transparent;
}}
.pill-ok    {{ background: {FARBEN["green_soft"]};  color: {FARBEN["green"]};  }}
.pill-warn  {{ background: {FARBEN["warn_soft"]};   color: {FARBEN["warn"]};   }}
.pill-error {{ background: {FARBEN["error_soft"]};  color: {FARBEN["error"]};  }}
.pill-plain {{ background: var(--surface-alt);      color: var(--muted); border-color: var(--border); }}

/* --------------------------------------------------------- Zutaten-Zeilen */
.zutat-zeile {{
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  padding: 0.55rem 0.2rem;
  border-bottom: 1px dashed var(--border);
}}
.zutat-zeile:last-child {{ border-bottom: none; }}
.zutat-menge {{
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 600;
  font-size: 1.02rem;
  color: var(--accent-dark);
  min-width: 96px;
  text-align: right;
  flex-shrink: 0;
}}
.zutat-menge.fix {{ color: var(--muted); font-style: italic; font-size: 0.9rem; }}
.zutat-name {{ flex: 1; }}

/* ------------------------------------------------------------- Statistiken */
.stat-reihe {{ display: flex; gap: 0.7rem; flex-wrap: wrap; margin-bottom: 1.2rem; }}
.stat {{
  flex: 1;
  min-width: 130px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 0.85rem 1.05rem;
}}
.stat .zahl {{
  font-family: 'Fraunces', Georgia, serif;
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1.1;
}}
.stat .zahl.warn {{ color: {FARBEN["warn"]}; }}
.stat .zahl.error {{ color: {FARBEN["error"]}; }}
.stat .label {{
  font-size: 0.75rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  margin-top: 0.15rem;
}}

/* ------------------------------------------------------------ Zubereitung */
.zubereitung-liste {{
  list-style: none;
  margin: 0.6rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}}
.zubereitung-liste li {{
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}}
.schritt-nr {{
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent-dark);
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 700;
  font-size: 0.82rem;
  display: flex;
  align-items: center;
  justify-content: center;
}}
.schritt-text {{ padding-top: 0.15rem; line-height: 1.5; }}

/* ---------------------------------------------------------- Schnellfilter */
.st-key-schnell_filter label {{
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--surface-alt);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.5rem 0.9rem;
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  width: 100%;
  justify-content: center;
}}
.st-key-schnell_filter label > div:not([data-testid="stWidgetLabel"]) {{
  width: 14px;
  height: 14px;
  min-width: 14px;
  border-radius: 4px;
  flex-shrink: 0;
}}
.st-key-schnell_filter [data-testid="stWidgetLabel"] {{ visibility: visible !important; }}
.st-key-schnell_filter [data-testid="stWidgetLabel"] p {{ margin: 0; }}
.st-key-schnell_filter:has(input:checked) label {{
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}}

/* ------------------------------------------------------------------ Inputs */
.stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {{
  border-radius: 14px !important;
  border-color: var(--border) !important;
  background: var(--surface) !important;
}}
.stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {{
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px var(--accent-soft) !important;
}}

/* -------------------------------------------------------------------- Chat */
[data-testid="stChatMessage"] {{
  gap: 0.6rem;
  align-items: flex-end;
  margin-bottom: 0.4rem;
}}
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {{
  flex-direction: row-reverse;
}}
[data-testid="stChatMessage"] > div:first-child {{
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--accent-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.05rem;
}}
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) > div:first-child {{
  background: var(--accent);
}}
[data-testid="stChatMessageContent"] {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 18px 18px 18px 4px;
  padding: 0.7rem 0.95rem;
  max-width: 88%;
}}
[aria-label="Chat message from user"] {{
  background: var(--accent) !important;
  border: none !important;
  border-radius: 18px 18px 4px 18px !important;
  margin-left: auto;
}}
[aria-label="Chat message from user"] p, [aria-label="Chat message from user"] li {{
  color: #fff !important;
}}
[data-testid="stChatMessageContent"] p:last-child {{ margin-bottom: 0; }}

[data-testid="stChatInput"] {{
  background: var(--surface-alt) !important;
  border: 1px solid var(--border) !important;
  border-radius: 999px !important;
  padding: 0.15rem 0.15rem 0.15rem 0.9rem !important;
}}
[data-testid="stChatInput"] textarea {{ background: transparent !important; }}
[data-testid="stChatInputSubmitButton"] {{
  background: var(--accent) !important;
  border-radius: 50% !important;
  width: 34px !important;
  height: 34px !important;
}}
[data-testid="stChatInputSubmitButton"] svg {{ fill: #fff !important; }}

/* ------------------------------------------------ Beispiel-/Anschlussfragen */
.st-key-beispielfragen .stButton > button, .st-key-anschlussfragen .stButton > button {{
  background: var(--surface-alt);
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 400;
  padding: 0.45rem 0.9rem;
}}

/* --------------------------------------------------- Wuerfel & Chatkarten */
.st-key-wuerfel_panel {{
  background: linear-gradient(135deg, var(--accent-soft) 0%, var(--bg) 100%);
  border: 1px solid var(--border);
  border-radius: 26px;
  padding: 1.4rem 1.25rem 1.2rem;
  text-align: center;
  max-width: 320px;
  margin: 0 auto 1.4rem;
}}
.st-key-wuerfel_panel .stButton {{ display: flex; justify-content: center; }}
.st-key-wuerfel_panel .stButton button {{
  width: 92px;
  height: 92px;
  border-radius: 28px;
  background: linear-gradient(135deg, var(--accent), var(--accent-dark));
  border: none;
  box-shadow: 0 8px 20px rgba(158,63,90,0.3);
  font-size: 40px;
  line-height: 1;
  padding: 0;
  transition: transform 0.15s ease;
}}
.st-key-wuerfel_panel .stButton button:hover {{
  background: linear-gradient(135deg, var(--accent), var(--accent-dark));
  color: initial;
  border-color: transparent;
  transform: translateY(-2px);
}}
.st-key-wuerfel_panel .stButton button:disabled {{
  opacity: 0.45;
  box-shadow: none;
}}
.wuerfel-dice-rolling {{
  width: 92px;
  height: 92px;
  margin: 0 auto;
  border-radius: 28px;
  background: linear-gradient(135deg, var(--accent), var(--accent-dark));
  box-shadow: 0 8px 20px rgba(158,63,90,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  animation: diceSpin 0.85s ease-in-out;
}}
.wuerfel-panel-label {{
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 600;
  font-size: 1rem;
  color: var(--text);
  margin-top: 0.7rem;
}}
.wuerfel-hinweis {{
  font-size: 0.76rem;
  color: var(--muted);
  line-height: 1.5;
  max-width: 260px;
  margin: 0.5rem auto 0;
}}
.wuerfel-hinweis b {{ color: var(--text); }}

.wuerfel-karte {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 6px 20px rgba(44,33,38,0.06);
  margin: 0.5rem 0 1rem;
  animation: cardFlipIn 0.5s ease;
}}
.wuerfel-karte .wk-kopf {{
  background: linear-gradient(135deg, var(--accent-soft) 0%, var(--surface-alt) 100%);
  border-bottom: 1px solid var(--border);
  padding: 1.05rem 1.25rem 1.15rem;
}}
.wuerfel-karte .wk-zeile {{ margin-bottom: 0.45rem; }}
.wuerfel-karte .wk-titel {{
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 700;
  font-size: 1.7rem;
  line-height: 1.15;
  color: var(--text);
}}
.wuerfel-karte .wk-meta {{
  font-size: 0.8rem;
  color: var(--muted);
  margin-top: 0.3rem;
}}
.wuerfel-karte .wk-body {{
  padding: 0.95rem 1.25rem 1.1rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}}

.zutat-chip {{
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.3rem 0.72rem;
  font-size: 0.82rem;
  color: var(--text);
}}
.zutat-rest {{ font-size: 0.82rem; color: var(--muted); padding: 0.3rem 0.2rem; }}

.mini-karte {{
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 0.75rem 0.9rem;
  margin-top: 0.5rem;
  box-shadow: 0 2px 8px rgba(44,33,38,0.05);
}}
.mini-initial {{
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 12px;
  background: var(--accent-soft);
  color: var(--accent-dark);
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 700;
  font-size: 1.05rem;
  display: flex;
  align-items: center;
  justify-content: center;
}}
.mini-titel {{
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 600;
  font-size: 1rem;
  color: var(--text);
  line-height: 1.2;
}}
.mini-meta {{ font-size: 0.75rem; color: var(--muted); margin-top: 0.15rem; }}
.mini-zutaten {{ font-size: 0.8rem; color: var(--text); margin-top: 0.25rem; }}

/* ------------------------------------------------------------- Kleinkram */
hr {{ border-color: var(--border); }}
.muted {{ color: var(--muted); font-size: 0.87rem; }}
.hinweis-box {{
  background: {FARBEN["warn_soft"]};
  border-left: 3px solid {FARBEN["warn"]};
  border-radius: 0 12px 12px 0;
  padding: 0.65rem 0.9rem;
  font-size: 0.87rem;
  color: {FARBEN["warn"]};
  margin: 0.6rem 0;
}}
#MainMenu, footer {{ visibility: hidden; }}
</style>
"""

STATUS_PILL = {
    "verarbeitet": ("pill-ok", "verarbeitet"),
    "Fehler": ("pill-error", "Fehler"),
    "nicht verarbeitet": ("pill-warn", "offen"),
}
