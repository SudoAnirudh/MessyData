import os
import streamlit as st
import requests

# Retrieve API Base URL
API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="MessyData | Observability Dashboard",
    page_icon="📊",
    layout="wide"
)

# Custom Premium Styling (Dark Minimalist CSS)
st.markdown("""
<style>
    /* Main app container */
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    
    /* Header customizations */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 700 !important;
        color: #ffffff !important;
    }
    
    /* Custom metric card container */
    .metric-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 MessyData Ingestion Dashboard")
st.caption("FDE Portfolio Project: CRM Data Consolidation & Deduplication Monitoring")

st.divider()

# API Health Status Card
st.subheader("System Status")
try:
    response = requests.get(f"{API_URL}/health", timeout=3)
    if response.status_code == 200:
        st.success(f"🟢 Connected to Unified API at `{API_URL}`")
        health_data = response.json()
        st.json(health_data)
    else:
        st.error(f"🔴 Unified API at `{API_URL}` returned status `{response.status_code}`")
except Exception as e:
    st.error(f"🔴 Cannot connect to Unified API at `{API_URL}`. Details: {e}")
