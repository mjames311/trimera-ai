"""Shared Trimera Health visual system for every Streamlit page."""

from html import escape
from typing import Optional

import streamlit as st


TRIMERA_GREEN = "#78C94E"
TRIMERA_BLUE = "#0789DB"
TRIMERA_TEAL = "#087A78"
TRIMERA_NAVY = "#0D1B2E"
TRIMERA_TEXT = "#111D31"
TRIMERA_MUTED = "#687B91"
TRIMERA_BORDER = "#DCE5EC"
TRIMERA_BACKGROUND = "#F7F9FB"
TRIMERA_SURFACE = "#FFFFFF"


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
.trimera-wordmark {{ display:flex; align-items:center; gap:13px; font-family:Georgia,serif; font-size:1.42rem; font-weight:700; }}
.trimera-mark {{ position:relative; width:31px; height:31px; display:inline-grid; place-items:center; font-family:Arial,sans-serif; font-size:2.3rem; line-height:1; font-weight:300; transform:translateY(-1px); }}
.trimera-suite {{ display:flex; align-items:center; gap:11px; font-size:.91rem; font-weight:800; letter-spacing:.025em; text-transform:uppercase; }}
.trimera-suite-icon {{ font-size:1.32rem; }}
.trimera-user {{ width:29px; height:29px; display:grid; place-items:center; border:2px solid white; border-radius:50%; font-size:.82rem; margin-left:14px; }}

[data-testid="stMainBlockContainer"], .block-container {{
  max-width: 1320px;
  padding-top: 6.7rem !important;
  padding-bottom: 4rem;
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

.trimera-home-intro {{ margin:.2rem 0 1.2rem; color:var(--trimera-muted); font-size:1.02rem; line-height:1.65; max-width:980px; }}
.trimera-section-title {{ margin:1.4rem 0 .75rem; color:var(--trimera-text); font-size:1.3rem; font-weight:800; letter-spacing:-.02em; }}
.trimera-tool-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.85rem; margin-bottom:1.35rem; }}
.trimera-tool-card {{ display:block; min-height:156px; padding:1.05rem; color:var(--trimera-text) !important; text-decoration:none !important; background:#fff; border:1px solid var(--trimera-border); border-radius:13px; box-shadow:0 5px 16px rgba(13,27,46,.055); transition:transform .15s ease, box-shadow .15s ease, border-color .15s ease; }}
.trimera-tool-card:hover {{ transform:translateY(-2px); border-color:#80caa2; box-shadow:0 9px 22px rgba(13,27,46,.09); }}
.trimera-tool-icon {{ width:38px; height:38px; display:grid; place-items:center; margin-bottom:.65rem; color:#258f61; background:#edf8ed; border-radius:10px; font-size:1.2rem; }}
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
  margin:0 0 1.15rem;
  padding:1.55rem 1.7rem 1.55rem 7.7rem;
  min-height:132px;
  display:flex;
  flex-direction:column;
  justify-content:center;
  background:rgba(255,255,255,.96);
  border:1px solid #e5eaee;
  border-radius:15px;
  box-shadow:0 8px 24px rgba(13,27,46,.08);
}}
.trimera-page-card::before {{ content:""; position:absolute; inset:0 auto 0 0; width:8px; background:linear-gradient(180deg,var(--trimera-green),#38b66d 48%,var(--trimera-blue) 52%,var(--trimera-blue)); }}
.trimera-page-icon {{ position:absolute; left:1.45rem; top:50%; transform:translateY(-50%); width:78px; height:78px; display:grid; place-items:center; border-radius:14px; background:linear-gradient(145deg,#f1f8ee,#edf7f3); color:#48ad4d; font-size:2.55rem; }}
.trimera-kicker {{ color:#087d76; font-size:.72rem; font-weight:850; letter-spacing:.095em; text-transform:uppercase; margin-bottom:.25rem; }}
.trimera-page-title {{ color:var(--trimera-text); font-size:2.35rem; line-height:1.08; font-weight:820; letter-spacing:-.035em; }}
.trimera-page-subtitle {{ color:var(--trimera-muted); margin:.42rem 0 0; font-size:1rem; line-height:1.45; }}

h1, h2, h3, h4 {{ color:var(--trimera-text); letter-spacing:-.022em; }}
h1 {{ font-size:2.25rem; font-weight:800; }}
h2 {{ font-size:1.45rem; }}
h1, h2, h3 {{ margin-top:.8rem !important; margin-bottom:.38rem !important; }}
h4 {{ margin-top:.65rem !important; margin-bottom:.3rem !important; }}
p, label, .stMarkdown {{ color:var(--trimera-text); }}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] {{ gap:.72rem; }}
[data-testid="stMainBlockContainer"] [data-testid="stMarkdownContainer"] p {{ margin-bottom:.45rem; line-height:1.48; }}
hr {{ margin:1.5rem 0; border-color:var(--trimera-border); }}

[data-testid="stWidgetLabel"] p {{ font-weight:650; color:var(--trimera-text); }}
[data-baseweb="input"] > div, [data-baseweb="textarea"] > div, [data-baseweb="select"] > div,
.stTextInput input, .stTextArea textarea {{ border-radius:10px !important; border-color:#d4dee7 !important; background:#fff !important; color:var(--trimera-text) !important; }}
.stTextInput input, .stTextArea textarea,
[data-testid="stSelectbox"] input {{ -webkit-text-fill-color:var(--trimera-text) !important; opacity:1 !important; }}
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

[data-testid="stFileUploader"] {{ padding:.7rem; border:1.5px dashed #75bfe8; border-radius:12px; background:#fbfdff; }}
[data-testid="stFileUploaderDropzone"] {{ background:var(--trimera-navy); border:0; border-radius:9px; min-height:74px; }}
[data-testid="stFileUploaderDropzone"] *, [data-testid="stFileUploaderFile"] * {{ color:white !important; }}
[data-testid="stFileUploaderDropzone"] button {{ background:#fff !important; color:var(--trimera-text) !important; border-radius:8px; }}
[data-testid="stFileUploaderDropzone"] button *,
[data-testid="stFileUploaderDropzone"] button p,
[data-testid="stFileUploaderDropzone"] button span {{ color:var(--trimera-navy) !important; -webkit-text-fill-color:var(--trimera-navy) !important; opacity:1 !important; }}

div.stButton > button, div.stDownloadButton > button {{
  min-height:48px;
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

[data-testid="stAlert"] {{ border-radius:10px; border:0; box-shadow:none; }}
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {{ color:inherit; }}
[data-testid="stExpander"], [data-testid="stMetric"], [data-testid="stDataFrame"], [data-testid="stTable"] {{ border-radius:12px; overflow:hidden; border-color:var(--trimera-border); }}
[data-testid="stMetric"] {{ background:white; padding:1rem; border:1px solid var(--trimera-border); }}
[data-testid="stChatMessage"] {{ background:#fff; border:1px solid var(--trimera-border); border-radius:13px; margin:.55rem 0; padding:.55rem .75rem; }}
[data-testid="stBottom"] {{ min-height:72px !important; padding:.5rem 1.25rem !important; background:#0b1019 !important; }}
[data-testid="stBottom"] > div {{ min-height:0 !important; padding:.2rem 0 !important; }}
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
</style>
""",
        unsafe_allow_html=True,
    )


def render_topbar() -> None:
    st.markdown(
        """
<div class="trimera-topbar">
  <div class="trimera-wordmark"><span class="trimera-mark">△</span><span>Trimera Health</span></div>
  <div class="trimera-suite"><span class="trimera-suite-icon">▣</span><span>Trimera AI&nbsp; · &nbsp;Clinical Intelligence</span><span class="trimera-user">○</span></div>
</div>
""",
        unsafe_allow_html=True,
    )


def page_header(icon: str, title: str, subtitle: Optional[str] = None) -> None:
    st.markdown(
        f"""
<section class="trimera-page-card">
  <div class="trimera-page-icon">{escape(icon)}</div>
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
