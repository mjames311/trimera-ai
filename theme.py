from typing import Optional
import streamlit as st

# -----------------------------
# Trimera Brand Palette
# -----------------------------
TRIMERA_DARK_TEAL = "#075B63"
TRIMERA_DEEP_TEAL = "#064A52"
TRIMERA_BLUE = "#28A9D6"
TRIMERA_LIGHT_BLUE = "#DDF4FB"
TRIMERA_GREEN = "#79B52D"
TRIMERA_LIGHT_GREEN = "#EDF7DF"
TRIMERA_GOLD = "#C9A51B"

TRIMERA_BACKGROUND = "#F5F8FA"
TRIMERA_SURFACE = "#FFFFFF"
TRIMERA_TEXT = "#163238"
TRIMERA_MUTED = "#60777C"
TRIMERA_BORDER = "#D9E4E7"

def apply_trimera_theme():
    st.markdown(f"""
<style>

:root {{
 --trimera-dark-teal:{TRIMERA_DARK_TEAL};
 --trimera-deep-teal:{TRIMERA_DEEP_TEAL};
 --trimera-blue:{TRIMERA_BLUE};
 --trimera-green:{TRIMERA_GREEN};
 --trimera-gold:{TRIMERA_GOLD};
 --trimera-bg:{TRIMERA_BACKGROUND};
 --trimera-card:{TRIMERA_SURFACE};
 --trimera-text:{TRIMERA_TEXT};
 --trimera-muted:{TRIMERA_MUTED};
 --trimera-border:{TRIMERA_BORDER};
}}

html, body, [class*="css"] {{
 font-family: Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}}

.stApp {{
 background:
 radial-gradient(circle at top right, rgba(40,169,214,.08), transparent 35rem),
 var(--trimera-bg);
 color:var(--trimera-text);
}}

.block-container {{
 max-width:1280px;
 padding-top:2rem;
 padding-bottom:4rem;
}}

h1,h2,h3,h4 {{
 color:var(--trimera-text);
 letter-spacing:-0.02em;
}}

h1 {{
 font-size:2.4rem;
 font-weight:750;
}}

[data-testid="stSidebar"] {{
 background:linear-gradient(180deg,var(--trimera-deep-teal),var(--trimera-dark-teal));
}}

[data-testid="stSidebar"] * {{
 color:white;
}}

[data-testid="stSidebarNav"] a {{
 border-radius:10px;
 margin:4px 8px;
 transition:.15s;
}}

[data-testid="stSidebarNav"] a:hover {{
 background:rgba(255,255,255,.10);
}}

[data-testid="stSidebarNav"] a[aria-current="page"] {{
 background:rgba(255,255,255,.15);
 border-left:4px solid var(--trimera-green);
}}

div.stButton > button,
div.stDownloadButton > button {{
 border-radius:12px;
 background:var(--trimera-dark-teal);
 color:white;
 border:none;
 min-height:46px;
 font-weight:600;
 transition:.15s;
}}

div.stButton > button:hover,
div.stDownloadButton > button:hover {{
 background:var(--trimera-blue);
}}

[data-testid="stFileUploader"] {{
 border:2px dashed var(--trimera-blue);
 border-radius:16px;
 background:white;
 padding:12px;
}}

.stTextInput input,
.stTextArea textarea,
.stSelectbox select {{
 border-radius:12px !important;
 border:1px solid var(--trimera-border) !important;
}}

[data-testid="stMetric"] {{
 background:white;
 border:1px solid var(--trimera-border);
 border-radius:16px;
 padding:16px;
}}

table {{
 border-radius:12px;
 overflow:hidden;
}}

thead tr {{
 background:var(--trimera-dark-teal);
 color:white;
}}

hr {{
 margin:2rem 0;
}}

</style>
""", unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: Optional[str] = None):
    st.markdown(f"""
<div style="padding-bottom:1rem;">
<h1>{icon} {title}</h1>
<p style="color:{TRIMERA_MUTED};font-size:1.05rem;margin-top:-8px;">
{subtitle or ""}
</p>
</div>
""", unsafe_allow_html=True)
