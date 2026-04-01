import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from web_scraper.search_agent import SearchAgent
from web_scraper import config_scraper as config

st.set_page_config(
    page_title="ConsultantIQ Research",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  #MainMenu, footer, header { visibility: hidden; }

  .top-bar {
    background: linear-gradient(135deg, #1E3A5F 0%, #2E5F8A 100%);
    color: white;
    padding: 18px 28px;
    border-radius: 10px;
    margin-bottom: 24px;
  }
  .top-bar h1 { margin: 0; font-size: 22px; font-weight: 700; }
  .top-bar span { font-size: 13px; color: #93C5FD; }

  .source-card {
    background: white;
    border: 1px solid #E2E8F0;
    border-left: 4px solid #1E3A5F;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 13px;
  }
  .source-card .src-name { font-weight: 700; color: #1E3A5F; font-size: 14px; }
  .source-card .src-title { color: #374151; margin-top: 2px; }
  .source-card .src-url { color: #6B7280; font-size: 11px; margin-top: 4px; }
  .source-card .src-snippet { color: #4B5563; margin-top: 8px; line-height: 1.5; }

  .trust-badge {
    display: inline-block;
    background: #DCFCE7;
    color: #166534;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 20px;
    margin-left: 8px;
  }
  .category-badge {
    display: inline-block;
    background: #EFF6FF;
    color: #1D4ED8;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 20px;
    margin-left: 4px;
  }
  .paywall-badge {
    display: inline-block;
    background: #FEF3C7;
    color: #92400E;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 20px;
    margin-left: 4px;
  }
  .answer-box {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 20px 24px;
    font-size: 14px;
    line-height: 1.7;
    color: #111827;
  }
  .plan-box {
    background: #F0F9FF;
    border: 1px solid #BAE6FD;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 12px;
    color: #0369A1;
    margin-bottom: 16px;
  }
  .sidebar-label {
    font-size: 11px;
    font-weight: 700;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 8px;
    margin-top: 16px;
  }
  .stButton > button {
    background: #1E3A5F;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 600;
    width: 100%;
  }
  .stButton > button:hover { background: #2E5F8A; }
  hr { border: none; border-top: 1px solid #E2E8F0; margin: 16px 0; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource(show_spinner=False)
def load_agent():
    try:
        return SearchAgent(), None
    except Exception as e:
        return None, str(e)

if "history" not in st.session_state:
    st.session_state.history = []

st.markdown("""
<div class="top-bar">
  <h1>ConsultantIQ Research</h1>
  <span>Live web research from trusted sources only &nbsp;·&nbsp; Azure OpenAI + Verified Publishers</span>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="sidebar-label">Source Categories</div>', unsafe_allow_html=True)
    selected_cats = []
    cat_map = {
        "consulting":     "Consulting & Business",
        "financial_news": "Financial News",
        "academic":       "Academic & Research",
        "news":           "News",
        "government":     "Government & Regulatory",
    }
    for cat, label in cat_map.items():
        if st.checkbox(label, value=True, key="cat_%s" % cat):
            selected_cats.append(cat)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="sidebar-label">Settings</div>', unsafe_allow_html=True)
    max_results = st.slider("Max sources to fetch", 2, 10, 5)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="sidebar-label">Trusted Sources</div>', unsafe_allow_html=True)
    for domain, info in config.TRUSTED_SOURCES.items():
        if info["category"] in selected_cats:
            st.markdown("• %s" % info["name"])

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("Clear history"):
        st.session_state.history = []
        st.rerun()

agent, agent_error = load_agent()
if agent_error:
    st.error("Could not load agent: %s" % agent_error)

# Show history
for item in st.session_state.history:
    st.markdown("**%s**" % item["question"])
    if item.get("plan"):
        st.markdown('<div class="plan-box">%s &nbsp;|&nbsp; Categories: %s &nbsp;|&nbsp; Queries: %s</div>' % (
            item["plan"].get("reasoning", ""),
            ", ".join(item["plan"].get("categories", [])),
            " · ".join(item["plan"].get("queries", [])),
        ), unsafe_allow_html=True)
    st.markdown('<div class="answer-box">%s</div>' % item["answer"].replace("\n", "<br>"),
                unsafe_allow_html=True)

    if item.get("sources"):
        with st.expander("%d sources retrieved" % len(item["sources"]), expanded=False):
            for i, src in enumerate(item["sources"], 1):
                cat_label = cat_map.get(src.category, src.category)
                st.markdown("""
                <div class="source-card">
                  <div class="src-name">[%d] %s
                    <span class="trust-badge">Trust %d</span>
                    <span class="category-badge">%s</span>
                  </div>
                  <div class="src-title">%s</div>
                  <div class="src-url"><a href="%s" target="_blank">%s</a></div>
                  <div class="src-snippet">%s</div>
                </div>
                """ % (i, src.source_name, src.trust, cat_label,
                       src.title, src.url, src.url[:60],
                       src.content[:300].replace("<","&lt;").replace(">","&gt;") + "..."),
                    unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
with st.form("search_form", clear_on_submit=True):
    cols = st.columns([5, 1])
    with cols[0]:
        question = st.text_input(
            "Research question",
            placeholder="e.g. What are the latest AI trends in management consulting?",
            label_visibility="collapsed",
        )
    with cols[1]:
        submitted = st.form_submit_button("Search →")

if submitted and question.strip():
    if not agent:
        st.error("Agent not loaded.")
    elif not selected_cats:
        st.warning("Please select at least one source category.")
    else:
        with st.spinner("Searching trusted sources..."):
            try:
                result = agent.search_and_answer(
                    question,
                    categories=selected_cats,
                )
                st.session_state.history.append({
                    "question": question,
                    "answer":   result["answer"],
                    "sources":  result["sources"],
                    "plan":     result["plan"],
                })
            except Exception as e:
                st.session_state.history.append({
                    "question": question,
                    "answer":   "Error: %s" % str(e),
                    "sources":  [],
                    "plan":     {},
                })
        st.rerun()

# Empty state
if not st.session_state.history:
    st.markdown("""
    <div style="text-align:center; color:#94A3B8; margin-top:60px;">
      <div style="font-size:40px; margin-bottom:12px;"></div>
      <div style="font-size:16px; font-weight:600; color:#475569;">Research from trusted sources only</div>
      <div style="font-size:13px; margin-top:6px;">
        Ask any business, financial, academic, or policy question.<br>
        ConsultantIQ will search verified publishers and synthesise a grounded answer.
      </div>
    </div>
    """, unsafe_allow_html=True)
