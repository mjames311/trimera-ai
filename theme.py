"""Shared Trimera Health visual system for every Streamlit page."""

import base64
import json
from html import escape
from pathlib import Path
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components


TRIMERA_GREEN = "#78C94E"
TRIMERA_BLUE = "#0789DB"
TRIMERA_TEAL = "#087A78"
TRIMERA_NAVY = "#0D1B2E"
TRIMERA_TEXT = "#111D31"
TRIMERA_MUTED = "#687B91"
TRIMERA_BORDER = "#DCE5EC"
TRIMERA_BACKGROUND = "#F7F9FB"
TRIMERA_SURFACE = "#FFFFFF"

ICON_PATHS = {
    "home": '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10"/><path d="M9.5 20v-6h5v6"/>',
    "documentation": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4.5V3h6v1.5M8.5 10l2 2 4-4M8 16h8"/>',
    "authorization": '<path d="M12 3 20 6v5c0 5.2-3.3 8.3-8 10-4.7-1.7-8-4.8-8-10V6l8-3Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/>',
    "era": '<path d="M5 3h14v18l-2-1.4-2 1.4-2-1.4-2 1.4-2-1.4L5 21V3Z"/><path d="M8 8h8M8 12h3M15.5 11v4M17.2 12.2c-.5-.6-2.7-.5-2.7.6 0 1.4 3 .6 3 2 0 1.1-2.3 1.2-3 .5"/>',
    "ask": '<path d="M20 14a3 3 0 0 1-3 3H9l-5 4v-4a3 3 0 0 1-2-2.8V7a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v7Z"/><path d="M7 9h8M7 13h5"/>',
    "appeal": '<path d="M6 3h9l4 4v14H6V3Z"/><path d="M15 3v5h4M15.5 16H9m0 0 3-3m-3 3 3 3"/>',
    "medication": '<path d="m8.2 4.2 11.6 11.6a4.2 4.2 0 0 1-6 6L2.2 10.2a4.2 4.2 0 0 1 6-6Z"/><path d="m7 15 8-8M5.5 7.5l4 4M14.5 16.5l2 2"/>',
    "medlog": '<path d="M9 4h6"/><path d="M9 2h6v4H9z"/><rect x="5" y="4" width="14" height="18" rx="2"/><path d="M8 10h8M8 14h5M8 18h8"/><path d="m15 14 1.5 1.5L19 13"/>',
    "clinical": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 3.5V2h6v1.5M12 8v7M8.5 11.5h7"/>',
    "user": '<circle cx="12" cy="8" r="3.5"/><path d="M5 21c.5-4 3-6 7-6s6.5 2 7 6"/>',
    "security": '<path d="M12 3 20 6v5c0 5.2-3.3 8.3-8 10-4.7-1.7-8-4.8-8-10V6l8-3Z"/><rect x="9" y="10" width="6" height="5" rx="1"/><path d="M10.5 10V8.5a1.5 1.5 0 0 1 3 0V10"/>',
}


def icon_svg(name: str, class_name: str = "trimera-icon-svg") -> str:
    """Return a trusted, accessible icon from the shared Trimera icon set."""
    paths = ICON_PATHS.get(name, ICON_PATHS["clinical"])
    return (
        f'<svg class="{escape(class_name)}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{paths}</svg>'
    )


def apply_trimera_theme() -> None:
    """Apply the screenshot-aligned Trimera shell and component styling."""
    st.markdown(
        f"""
<style>
:root {{
  --trimera-green: {TRIMERA_GREEN};
  --trimera-blue: {TRIMERA_BLUE};
  --trimera-teal: {TRIMERA_TEAL};
  --trimera-navy: {TRIMERA_NAVY};
  --trimera-text: {TRIMERA_TEXT};
  --trimera-muted: {TRIMERA_MUTED};
  --trimera-border: {TRIMERA_BORDER};
  --trimera-bg: {TRIMERA_BACKGROUND};
  --trimera-card: {TRIMERA_SURFACE};
  --trimera-gradient: linear-gradient(100deg, #7dcc48 0%, #61c565 24%, #0ba1bd 61%, #0785db 100%);
}}

html, body {{
  background: {TRIMERA_BACKGROUND};
  color: var(--trimera-text);
}}

html, body, [class*="css"] {{
  font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}

[data-testid="stApp"], .stApp {{
  background: {TRIMERA_BACKGROUND};
}}

[data-testid="stAppViewContainer"] {{
  background:
    radial-gradient(circle at 96% 4%, rgba(7,137,219,.06), transparent 31rem),
    linear-gradient(180deg, #ffffff 0%, var(--trimera-bg) 100%);
  color: var(--trimera-text);
}}

[data-testid="stHeader"] {{
  height: 76px;
  background: transparent;
}}

.trimera-topbar {{
  position: fixed;
  inset: 0 0 auto 0;
  z-index: 1000000;
  height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 34px;
  color: white;
  background: var(--trimera-gradient);
  box-shadow: 0 5px 18px rgba(13,27,46,.12);
}}
.trimera-wordmark {{ display:flex; align-items:center; gap:12px; color:#fff !important; text-decoration:none !important; }}
.trimera-wordmark:hover {{ color:#fff !important; text-decoration:none !important; }}
.trimera-mark {{ width:38px; height:38px; flex:0 0 38px; display:block; }}
.trimera-brand-copy {{ display:flex; flex-direction:column; justify-content:center; line-height:1; }}
.trimera-brand-name {{ font-family:Georgia,serif; font-size:1.42rem; font-weight:700; letter-spacing:.005em; }}
.trimera-brand-tagline {{ margin-top:5px; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:.92rem; font-weight:750; letter-spacing:.035em; opacity:1; }}
.trimera-quote-rotator {{ position:absolute; left:50%; top:50%; width:min(43vw,680px); height:48px; transform:translate(-50%,-50%); pointer-events:none; }}
.trimera-quote {{
  position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center;
  text-align:center; opacity:0; animation:trimeraQuoteCycle 90s ease-in-out infinite;
  text-shadow:0 1px 4px rgba(13,27,46,.18);
}}
.trimera-quote-text {{ font-family:Georgia,serif; font-size:.96rem; font-style:italic; font-weight:650; line-height:1.22; }}
.trimera-quote-author {{ margin-top:3px; font-size:.66rem; font-weight:800; letter-spacing:.075em; text-transform:uppercase; opacity:.84; }}
@keyframes trimeraQuoteCycle {{
  0%, 1% {{ opacity:0; transform:translateY(3px); }}
  4%, 7% {{ opacity:1; transform:translateY(0); }}
  10%, 100% {{ opacity:0; transform:translateY(-3px); }}
}}
.trimera-suite {{ display:flex; align-items:center; gap:11px; font-size:.91rem; font-weight:800; letter-spacing:.025em; text-transform:uppercase; }}
.trimera-icon-svg {{ width:1em; height:1em; display:block; }}
.trimera-suite-icon {{ font-size:1.32rem; }}
.trimera-suite-icon .trimera-icon-svg {{ width:24px; height:24px; }}
.trimera-user {{ width:29px; height:29px; display:grid; place-items:center; border:2px solid white; border-radius:50%; margin-left:14px; }}
.trimera-user .trimera-icon-svg {{ width:18px; height:18px; }}

[data-testid="stMainBlockContainer"], .block-container {{
  max-width: 1320px;
  padding-top: 5.65rem !important;
  padding-bottom: 1.5rem;
  padding-left: 2rem;
  padding-right: 2rem;
}}

[data-testid="stSidebar"] {{
  width: 330px !important;
  min-width: 330px !important;
  background: #fff;
  border-right: 1px solid var(--trimera-border);
  padding-top: 84px;
}}
[data-testid="stSidebar"] > div:first-child {{ width:330px !important; }}
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
button[aria-label="Collapse sidebar"],
button[aria-label="Expand sidebar"] {{ display:none !important; visibility:hidden !important; pointer-events:none !important; }}
[data-testid="stSidebar"]::before {{
  content:"";
  position:absolute;
  top:76px;
  bottom:0;
  left:0;
  width:8px;
  background:linear-gradient(180deg, var(--trimera-green) 0%, var(--trimera-green) 47%, var(--trimera-blue) 53%, var(--trimera-blue) 100%);
}}
[data-testid="stSidebarContent"] {{ padding: .75rem 1rem 2rem 1.35rem; }}
[data-testid="stSidebar"] * {{ color:var(--trimera-text); }}
[data-testid="stSidebarNav"] {{ padding-top:.4rem; border-bottom:1px solid var(--trimera-border); padding-bottom:.85rem; margin-bottom:.9rem; }}
[data-testid="stSidebarNav"]::before {{
  content:"APPLICATIONS";
  display:block;
  margin:0 1rem .55rem;
  color:#66798d;
  font-size:.72rem;
  font-weight:850;
  letter-spacing:.08em;
}}
[data-testid="stSidebarNav"] a {{
  margin:.16rem .38rem;
  padding:.67rem .8rem;
  border-radius:11px;
  font-weight:650;
  white-space:normal;
  transition:background .15s ease, transform .15s ease;
}}
[data-testid="stSidebarNav"] a:hover {{ background:#f0f8ed; transform:translateX(2px); }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  background:linear-gradient(90deg, rgba(120,201,78,.18), rgba(120,201,78,.08));
  color:#0c522d !important;
}}
[data-testid="stSidebarNav"] a[href="http://127.0.0.1:8501/"] p,
[data-testid="stSidebarNav"] a[href="/"] p {{ font-size:0; }}
[data-testid="stSidebarNav"] a[href="http://127.0.0.1:8501/"] p::after,
[data-testid="stSidebarNav"] a[href="/"] p::after {{ content:"Home"; font-size:.875rem; }}
[data-testid="stSidebarNav"] ul li:first-child p {{ font-size:0 !important; }}
[data-testid="stSidebarNav"] ul li:first-child p::after {{ content:"Home"; font-size:.875rem !important; }}
[data-testid="stSidebar"] [data-testid="stButton"] button {{
  min-height:39px;
  justify-content:flex-start;
  padding-left:.75rem;
  background:transparent;
  color:var(--trimera-text);
  box-shadow:none;
  border:1px solid transparent;
}}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {{ background:#f0f8ed; border-color:#dcefd3; color:#174b30; }}

.trimera-side-label {{ margin:.6rem .25rem .45rem; color:#66798d; font-size:.72rem; font-weight:850; letter-spacing:.08em; }}
.trimera-model {{ display:inline-block; margin:.05rem 0 .85rem; padding:.55rem 1.2rem; border-radius:10px; background:linear-gradient(90deg,#eef8e9,#e8f7f1); color:#17263a; font-size:.83rem; font-weight:750; }}
.trimera-reminder {{ margin:.45rem 0; padding:1rem; border:1px solid var(--trimera-border); border-radius:13px; background:#fff; box-shadow:0 7px 20px rgba(13,27,46,.06); font-size:.86rem; line-height:1.55; }}
.trimera-reminder strong {{ display:block; color:#087ca9; margin-bottom:.42rem; }}

.trimera-home-intro {{ margin:.25rem auto 1.35rem; color:var(--trimera-muted); font-size:1.02rem; line-height:1.65; max-width:1080px; text-align:center; }}
.trimera-section-title {{ margin:1.05rem 0 .6rem; color:var(--trimera-text); font-size:1.22rem; font-weight:800; letter-spacing:-.02em; }}
.trimera-tool-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.85rem; margin-bottom:1.35rem; }}
.trimera-tool-card {{ display:block; min-height:156px; padding:1.05rem; color:var(--trimera-text) !important; text-decoration:none !important; background:#fff; border:1px solid var(--trimera-border); border-radius:13px; box-shadow:0 5px 16px rgba(13,27,46,.055); transition:transform .15s ease, box-shadow .15s ease, border-color .15s ease; }}
.trimera-tool-card:hover {{ transform:translateY(-2px); border-color:#80caa2; box-shadow:0 9px 22px rgba(13,27,46,.09); }}
.trimera-tool-icon {{ width:38px; height:38px; display:grid; place-items:center; margin-bottom:.65rem; color:#258f61; background:#edf8ed; border-radius:10px; font-size:1.2rem; }}
.trimera-tool-icon .trimera-icon-svg {{ width:23px; height:23px; }}
.trimera-tool-name {{ margin-bottom:.32rem; color:var(--trimera-text); font-size:.96rem; font-weight:800; }}
.trimera-tool-description {{ color:var(--trimera-muted); font-size:.82rem; line-height:1.48; }}
.trimera-source-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.8rem; margin-bottom:1.25rem; }}
.trimera-source-card {{ padding:1rem 1.05rem; background:linear-gradient(145deg,#fff,#f8fbfc); border:1px solid var(--trimera-border); border-radius:12px; }}
.trimera-source-card strong {{ display:block; margin-bottom:.3rem; color:#08766f; font-size:.9rem; }}
.trimera-source-card span {{ color:var(--trimera-muted); font-size:.82rem; line-height:1.5; }}
.trimera-home-note {{ padding:.9rem 1rem; color:#294257; background:#edf7f1; border-left:4px solid var(--trimera-green); border-radius:9px; font-size:.84rem; line-height:1.5; }}

.trimera-page-card {{
  position:relative;
  overflow:hidden;
  margin:0 0 .85rem;
  padding:1.25rem 1.5rem 1.25rem 6.7rem;
  min-height:112px;
  display:flex;
  flex-direction:column;
  justify-content:center;
  background:rgba(255,255,255,.96);
  border:1px solid #e5eaee;
  border-radius:15px;
  box-shadow:0 8px 24px rgba(13,27,46,.08);
}}
.trimera-page-card::before {{ content:""; position:absolute; inset:0 auto 0 0; width:8px; background:linear-gradient(180deg,var(--trimera-green),#38b66d 48%,var(--trimera-blue) 52%,var(--trimera-blue)); }}
.trimera-page-icon {{ position:absolute; left:1.3rem; top:50%; transform:translateY(-50%); width:66px; height:66px; display:grid; place-items:center; border-radius:13px; background:linear-gradient(145deg,#f1f8ee,#edf7f3); color:#48ad4d; font-size:2.2rem; }}
.trimera-page-icon .trimera-icon-svg {{ width:39px; height:39px; }}
.trimera-kicker {{ color:#087d76; font-size:.72rem; font-weight:850; letter-spacing:.095em; text-transform:uppercase; margin-bottom:.25rem; }}
.trimera-page-title {{ color:var(--trimera-text); font-size:2.1rem; line-height:1.06; font-weight:820; letter-spacing:-.035em; }}
.trimera-page-subtitle {{ color:var(--trimera-muted); margin:.3rem 0 0; font-size:.94rem; line-height:1.4; }}

h1, h2, h3, h4 {{ color:var(--trimera-text); letter-spacing:-.022em; }}
h1 {{ font-size:2.25rem; font-weight:800; }}
h2 {{ font-size:1.45rem; }}
h1, h2, h3 {{ margin-top:.8rem !important; margin-bottom:.38rem !important; }}
h4 {{ margin-top:.65rem !important; margin-bottom:.3rem !important; }}
p, label, .stMarkdown {{ color:var(--trimera-text); }}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] {{ gap:.52rem; }}
[data-testid="stMainBlockContainer"] [data-testid="stMarkdownContainer"] p {{ margin-bottom:.45rem; line-height:1.48; }}
hr {{ margin:1.05rem 0; border-color:var(--trimera-border); }}

[data-testid="stWidgetLabel"] p {{ font-weight:650; color:var(--trimera-text); }}
[data-baseweb="input"] > div, [data-baseweb="textarea"] > div, [data-baseweb="select"] > div,
.stTextInput input, .stTextArea textarea {{ border-radius:10px !important; border-color:#d4dee7 !important; background:#fff !important; color:var(--trimera-text) !important; }}
.stTextInput input, .stTextArea textarea,
[data-testid="stSelectbox"] input {{ -webkit-text-fill-color:var(--trimera-text) !important; opacity:1 !important; }}
[data-testid="stDateInput"] input {{
  background:#fff !important;
  color:var(--trimera-text) !important;
  -webkit-text-fill-color:var(--trimera-text) !important;
  caret-color:var(--trimera-text) !important;
  opacity:1 !important;
}}
[data-testid="stDateInput"] input::selection {{ background:#ccebd8 !important; color:var(--trimera-text) !important; }}
[data-testid="stDateInput"] svg {{ color:var(--trimera-text) !important; fill:var(--trimera-text) !important; }}
.stTextInput input[type="password"] {{
  background:#fff !important;
  color:var(--trimera-text) !important;
  -webkit-text-fill-color:var(--trimera-text) !important;
  caret-color:var(--trimera-text) !important;
  opacity:1 !important;
}}
.stTextInput [data-baseweb="input"] svg {{ color:var(--trimera-text) !important; fill:var(--trimera-text) !important; }}
.stTextInput input::placeholder, .stTextArea textarea::placeholder,
[data-testid="stSelectbox"] input::placeholder {{ color:#718398 !important; -webkit-text-fill-color:#718398 !important; opacity:1 !important; }}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{ background:#fff !important; color:var(--trimera-text) !important; border-color:#d4dee7 !important; }}
[data-testid="stSelectbox"] div[data-baseweb="select"] * {{ color:var(--trimera-text) !important; fill:var(--trimera-text) !important; }}
[data-testid="stSelectbox"] [role="group"],
[data-testid="stSelectbox"] [role="group"] input,
[data-testid="stSelectbox"] [role="group"] button {{ background:#fff !important; color:var(--trimera-text) !important; border-color:#d4dee7 !important; }}
[data-testid="stSelectbox"] [role="group"] {{ border:1px solid #d4dee7 !important; border-radius:10px !important; overflow:hidden; }}
[data-baseweb="input"] > div:focus-within, [data-baseweb="textarea"] > div:focus-within {{ border-color:var(--trimera-green) !important; box-shadow:0 0 0 1px var(--trimera-blue) !important; }}
.stTextInput input:focus, .stTextArea textarea:focus {{ background:var(--trimera-navy) !important; color:white !important; -webkit-text-fill-color:white !important; caret-color:white; }}
.stTextInput input:focus::placeholder, .stTextArea textarea:focus::placeholder {{ color:#c5d1dc !important; -webkit-text-fill-color:#c5d1dc !important; opacity:1 !important; }}
[data-baseweb="radio"] [aria-checked="true"] {{ background-color:var(--trimera-green) !important; border-color:var(--trimera-green) !important; }}
input[type="radio"] {{ accent-color:var(--trimera-green) !important; }}
[data-testid="stRadio"] [role="radio"][aria-checked="true"] {{ border-color:var(--trimera-green) !important; background:var(--trimera-green) !important; }}
[data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child {{ border-color:var(--trimera-green) !important; background:var(--trimera-green) !important; }}
[data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child > div {{ background:#fff !important; }}

[data-testid="stFileUploader"] {{ padding:.55rem; border:1.5px dashed #75bfe8; border-radius:12px; background:#fbfdff; }}
[data-testid="stFileUploaderDropzone"] {{ background:var(--trimera-navy); border:0; border-radius:9px; min-height:62px; padding:.65rem .8rem !important; }}
[data-testid="stFileUploaderDropzone"] *, [data-testid="stFileUploaderFile"] * {{ color:white !important; }}
[data-testid="stFileUploaderDropzone"] button {{ background:#fff !important; color:var(--trimera-text) !important; border-radius:8px; }}
[data-testid="stFileUploaderDropzone"] button *,
[data-testid="stFileUploaderDropzone"] button p,
[data-testid="stFileUploaderDropzone"] button span {{ color:var(--trimera-navy) !important; -webkit-text-fill-color:var(--trimera-navy) !important; opacity:1 !important; }}

div.stButton > button, div.stDownloadButton > button {{
  min-height:42px;
  border-radius:10px;
  border:1px solid #d4e1e8;
  background:#fff;
  color:var(--trimera-text);
  font-weight:720;
  box-shadow:0 3px 10px rgba(13,27,46,.04);
  transition:transform .15s ease, box-shadow .15s ease;
}}
div.stButton > button:hover, div.stDownloadButton > button:hover {{ transform:translateY(-1px); border-color:#63bda8; color:#08746d; box-shadow:0 7px 16px rgba(13,27,46,.09); }}
div.stButton > button[kind="primary"], div.stDownloadButton > button[kind="primary"] {{ color:#fff; border:0; background:var(--trimera-gradient); box-shadow:0 7px 16px rgba(7,137,219,.16); }}
[data-testid="stBaseButton-primary"] {{ color:#fff !important; border:0 !important; background:var(--trimera-gradient) !important; box-shadow:0 7px 16px rgba(7,137,219,.16) !important; }}
div.stButton > button:disabled,
[data-testid="stBaseButton-primary"]:disabled {{
  background:#eef2f5 !important;
  color:#7a8794 !important;
  -webkit-text-fill-color:#7a8794 !important;
  border:1px solid #d4dee7 !important;
  box-shadow:none !important;
  opacity:1 !important;
  cursor:not-allowed !important;
}}
div.stButton > button:disabled *,
[data-testid="stBaseButton-primary"]:disabled * {{
  color:#7a8794 !important;
  -webkit-text-fill-color:#7a8794 !important;
  opacity:1 !important;
}}

[data-testid="stAlert"] {{ border-radius:10px; border:0; box-shadow:none; }}
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {{ color:inherit; }}
[data-testid="stExpander"], [data-testid="stMetric"], [data-testid="stDataFrame"], [data-testid="stTable"] {{ border-radius:12px; overflow:hidden; border-color:var(--trimera-border); }}
[data-testid="stExpander"] {{ background:#fff !important; }}
[data-testid="stExpander"] details,
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary:hover,
[data-testid="stExpander"] summary:focus,
[data-testid="stExpander"] details[open] summary {{ background:#fff !important; color:var(--trimera-text) !important; }}
[data-testid="stExpander"] summary *,
[data-testid="stExpander"] details[open] summary * {{ color:var(--trimera-text) !important; fill:var(--trimera-text) !important; }}
[data-testid="stExpander"] summary:hover {{ background:#f3f8f5 !important; }}
[data-testid="stMetric"] {{ background:white; padding:1rem; border:1px solid var(--trimera-border); }}
[data-testid="stChatMessage"] {{ background:#fff; border:1px solid var(--trimera-border); border-radius:13px; margin:.55rem 0; padding:.55rem .75rem; }}
[data-testid="stBottom"], [data-testid="stBottomBlockContainer"] {{
  position:static !important; inset:auto !important; min-height:0 !important;
  max-width:1320px !important; margin:.75rem auto 1.25rem !important;
  padding:.55rem 2rem !important; background:transparent !important;
}}
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] > div {{ min-height:0 !important; padding:0 !important; }}
[data-testid="stChatInput"] {{ min-height:48px !important; border-radius:12px; border:1px solid #8a98aa !important; background:#252834 !important; }}
[data-testid="stChatInput"] textarea {{ min-height:46px !important; height:46px !important; color:white !important; -webkit-text-fill-color:white !important; caret-color:white !important; opacity:1 !important; }}
[data-testid="stChatInput"] textarea::placeholder {{ color:#c5d1dc !important; -webkit-text-fill-color:#c5d1dc !important; opacity:1 !important; }}
[data-testid="stChatInput"] button {{ color:white !important; }}
thead tr {{ background:var(--trimera-navy) !important; color:white !important; }}

@media (max-width: 900px) {{
  .trimera-topbar {{ padding:0 16px; }}
  .trimera-wordmark {{ font-size:1.05rem; }}
  .trimera-suite {{ font-size:.7rem; }}
  .trimera-user {{ display:none; }}
  [data-testid="stSidebar"] {{ width:290px !important; min-width:290px !important; }}
  [data-testid="stMainBlockContainer"], .block-container {{ padding-left:1rem; padding-right:1rem; }}
  .trimera-page-card {{ padding:1.25rem 1rem 1.25rem 5.4rem; min-height:112px; }}
  .trimera-page-icon {{ left:1rem; width:58px; height:58px; font-size:1.9rem; }}
  .trimera-page-title {{ font-size:1.75rem; }}
  .trimera-tool-grid, .trimera-source-grid {{ grid-template-columns:1fr; }}
}}
@media (max-width: 1180px) {{ .trimera-quote-rotator {{ display:none; }} }}
</style>
""",
        unsafe_allow_html=True,
    )
    _install_page_transition_loader()


def render_topbar(home_quotes: bool = False) -> None:
    quotes = [
        ("Act as if what you do makes a difference. It does.", "William James"),
        ("Nothing will work unless you do.", "Maya Angelou"),
        ("Well done is better than well said.", "Benjamin Franklin"),
        ("Alone we can do so little; together we can do so much.", "Helen Keller"),
        ("Start where you are. Use what you have. Do what you can.", "Arthur Ashe"),
        ("The future depends on what you do today.", "Mahatma Gandhi"),
        ("No act of kindness, no matter how small, is ever wasted.", "Aesop"),
        ("Happiness depends upon ourselves.", "Aristotle"),
        ("Energy and persistence conquer all things.", "Benjamin Franklin"),
        ("You must do the thing you think you cannot do.", "Eleanor Roosevelt"),
    ]
    quote_markup = ""
    if home_quotes:
        quote_items = "".join(
            f'<div class="trimera-quote" style="animation-delay:{index * 9}s">'
            f'<span class="trimera-quote-text">“{escape(quote)}”</span>'
            f'<span class="trimera-quote-author">— {escape(author)}</span></div>'
            for index, (quote, author) in enumerate(quotes)
        )
        quote_markup = f'<div class="trimera-quote-rotator" aria-live="polite">{quote_items}</div>'
    st.markdown(
        f"""
<div class="trimera-topbar">
  <a class="trimera-wordmark" href="/" target="_self" aria-label="Go to Trimera AI Home">
    <svg class="trimera-mark" viewBox="0 0 100 88" role="img" aria-label="Trimera Health logo">
      <path d="M50 4 L96 84 H4 Z" fill="none" stroke="white" stroke-width="7" stroke-linejoin="round"/>
      <path d="M50 8 L73 47 H27 Z" fill="white" opacity=".30"/>
      <path d="M27 47 L50 84 H4 Z" fill="white" opacity=".24"/>
      <path d="M73 47 L96 84 H50 Z" fill="white" opacity=".38"/>
      <path d="M27 47 H73 L50 84 Z" fill="white" opacity=".88"/>
    </svg>
    <span class="trimera-brand-copy"><span class="trimera-brand-name">Trimera Health</span><span class="trimera-brand-tagline">Offering Hope for Healing</span></span>
  </a>
  {quote_markup}
  <div class="trimera-suite"><span class="trimera-suite-icon">{icon_svg("clinical")}</span><span>Trimera AI&nbsp; · &nbsp;Clinical Intelligence</span><span class="trimera-user">{icon_svg("user")}</span></div>
</div>
""",
        unsafe_allow_html=True,
    )


def page_header(icon: str, title: str, subtitle: Optional[str] = None) -> None:
    st.markdown(
        f"""
<section class="trimera-page-card">
  <div class="trimera-page-icon">{icon_svg(icon)}</div>
  <div class="trimera-kicker">Trimera AI · Clinical Intelligence</div>
  <div class="trimera-page-title">{escape(title)}</div>
  <p class="trimera-page-subtitle">{escape(subtitle or "")}</p>
</section>
""",
        unsafe_allow_html=True,
    )


def render_app_shell(icon: str, title: str, subtitle: str) -> None:
    """Render the common top bar and page card after authentication."""
    apply_trimera_theme()
    render_topbar()
    page_header(icon, title, subtitle)


def _available_puppies() -> list[tuple[str, Path, str]]:
    assets_dir = Path(__file__).resolve().parent / "Assets"
    ozzie_path = assets_dir / "ozzie_head.png"
    tucker_path = assets_dir / "tucker_head.png"
    puppies = []
    if ozzie_path.exists():
        puppies.append(("Ozzie", ozzie_path, "Ozzie is fetching the tool"))
    if tucker_path.exists():
        puppies.append(("Tucker", tucker_path, "Tucker is sniffing out a solution"))
    return puppies


def _install_page_transition_loader() -> None:
    """Display a puppy immediately after an internal page link is selected."""
    puppies = _available_puppies()
    if not puppies:
        return
    puppy_data = [
        {
            "name": name,
            "src": "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii"),
            "message": message,
        }
        for name, path, message in puppies
    ]
    components.html(
        f"""
<script>
(() => {{
  const doc = window.parent.document;
  const overlayId = "trimera-page-transition";
  const puppies = {json.dumps(puppy_data)};
  const prior = doc.getElementById(overlayId);
  if (prior) {{
    const shownAt = Number(prior.dataset.shownAt || Date.now());
    const remaining = Math.max(0, 700 - (Date.now() - shownAt));
    window.setTimeout(() => prior.remove(), remaining);
  }}

  if (!doc.getElementById("trimera-page-transition-style")) {{
    const style = doc.createElement("style");
    style.id = "trimera-page-transition-style";
    style.textContent = `
      @keyframes trimeraPuppySpin {{ to {{ transform:rotate(360deg); }} }}
      #trimera-page-transition {{
        position:fixed; inset:0; z-index:2147483647; display:flex;
        align-items:center; justify-content:center; background:#081322;
        color:#fff; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      }}
      #trimera-page-transition div {{ text-align:center; padding:24px; }}
      #trimera-page-transition img {{
        display:block; width:108px; height:108px; margin:auto; border-radius:50%;
        object-fit:cover; border:5px solid #78c94e;
        box-shadow:0 0 0 5px rgba(7,137,219,.28);
        animation:trimeraPuppySpin 2.2s linear infinite;
      }}
      #trimera-page-transition strong {{ display:block; margin-top:18px; font-size:1.08rem; }}
      #trimera-page-transition span {{ display:block; margin-top:5px; color:#bdcad8; font-size:.85rem; }}
    `;
    doc.head.appendChild(style);
  }}

  const show = () => {{
    if (doc.getElementById(overlayId)) return;
    const priorIndex = Number(doc.documentElement.dataset.trimeraLastPuppyIndex);
    const puppyIndex = puppies.length < 2
      ? 0
      : Number.isInteger(priorIndex)
        ? (priorIndex + 1) % puppies.length
        : Math.floor(Math.random() * puppies.length);
    doc.documentElement.dataset.trimeraLastPuppyIndex = String(puppyIndex);
    const puppy = puppies[puppyIndex];
    const overlay = doc.createElement("div");
    overlay.id = overlayId;
    overlay.dataset.shownAt = String(Date.now());
    overlay.setAttribute("role", "status");
    overlay.innerHTML = `<div><img src="${{puppy.src}}" alt="${{puppy.name}}"><strong>Loading Trimera AI…</strong><span>${{puppy.message}}</span></div>`;
    doc.body.appendChild(overlay);
  }};

  if (!doc.documentElement.dataset.trimeraTransitionBound) {{
    doc.documentElement.dataset.trimeraTransitionBound = "true";
    doc.addEventListener("click", (event) => {{
      const anchor = event.target.closest("a[href]");
      if (!anchor || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("javascript:")) return;
      let destination;
      try {{ destination = new URL(anchor.href, window.parent.location.href); }} catch (_) {{ return; }}
      if (destination.origin !== window.parent.location.origin || destination.href === window.parent.location.href) return;
      show();
    }}, true);
  }}
}})();
</script>
""",
        height=0,
        width=0,
    )


def sidebar_label(label: str) -> None:
    st.sidebar.markdown(f'<div class="trimera-side-label">{escape(label.upper())}</div>', unsafe_allow_html=True)


def sidebar_model(model: str) -> None:
    sidebar_label("Model")
    st.sidebar.markdown(f'<div class="trimera-model">{escape(model)}</div>', unsafe_allow_html=True)


def sidebar_reminder(title: str, body: str) -> None:
    st.sidebar.markdown(
        f'<div class="trimera-reminder"><strong>◆ &nbsp;{escape(title)}</strong>{escape(body)}</div>',
        unsafe_allow_html=True,
    )
