import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

# Retrieve API Base URL
API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="MessyData | Observability Dashboard",
    page_icon="📊",
    layout="wide"
)

# Custom Styling (Premium Minimalist Dark Mode)
st.markdown("""
<style>
    /* Main container styling */
    .stApp {
        background-color: #0e1117;
        color: #f0f2f6;
    }
    
    /* Title and Header customizations */
    h1, h2, h3 {
        font-family: 'Outfit', 'Inter', sans-serif !important;
        font-weight: 700 !important;
        color: #ffffff !important;
        letter-spacing: -0.025em;
    }
    
    /* Tab headers */
    button[data-baseweb="tab"] {
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        color: #8a99ad !important;
        background-color: transparent !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #3b82f6 !important;
        border-bottom-color: #3b82f6 !important;
    }
    
    /* Custom metric container styling */
    .metric-card-custom {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.25rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        text-align: left;
        margin-bottom: 1rem;
    }
    .metric-value-custom {
        font-size: 2.2rem;
        font-weight: 800;
        color: #ffffff;
        margin: 0.2rem 0;
    }
    .metric-label-custom {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #9ca3af;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Helper to safe-rerun Streamlit app
def force_refresh():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# --- API Data Fetching Helpers ---

@st.cache_data(ttl=2)
def fetch_health():
    try:
        response = requests.get(f"{API_URL}/health", timeout=3)
        return response.status_code == 200, response.json()
    except Exception:
        return False, None

def fetch_runs():
    try:
        response = requests.get(f"{API_URL}/api/v1/pipeline/runs", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching pipeline runs: {e}")
    return []

def fetch_flagged_records():
    try:
        response = requests.get(f"{API_URL}/api/v1/flagged?resolved=false", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching flagged records: {e}")
    return []

def resolve_flagged_record(record_id: int, action: str, target_customer_id=None):
    try:
        payload = {"action": action}
        if target_customer_id:
            payload["target_customer_id"] = str(target_customer_id)
            
        res = requests.post(f"{API_URL}/api/v1/flagged/{record_id}/resolve", json=payload, timeout=5)
        return res.status_code == 200, res.json()
    except Exception as e:
        return False, str(e)

def search_customers(query_str: str):
    try:
        params = {}
        if query_str:
            params["q"] = query_str
        response = requests.get(f"{API_URL}/api/v1/customers", params=params, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching customer list: {e}")
    return []

def fetch_customer_detail(customer_id: str):
    try:
        response = requests.get(f"{API_URL}/api/v1/customers/{customer_id}", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching customer details: {e}")
    return None

def trigger_pipeline_ingestion():
    try:
        res = requests.post(f"{API_URL}/api/v1/pipeline/run", timeout=5)
        return res.status_code == 202
    except Exception:
        return False

# --- Dashboard Layout ---

st.title("📊 MessyData Ingestion & Reconciliation Dashboard")
st.caption("FDE Portfolio Project: CRM Deduplication Engine & Pipeline Observability")

# Global System Status Header
is_healthy, health_info = fetch_health()
if not is_healthy:
    st.error(f"🔴 System disconnected. Cannot connect to Unified API at `{API_URL}`. Ensure docker-compose backend is running.")
    st.stop()

# Load initial datasets
runs = fetch_runs()
flagged_queue = fetch_flagged_records()
total_customers = len(search_customers(""))

# Top-level Metric Cards Columns
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card-custom">
        <div class="metric-label-custom">API Connection Status</div>
        <div class="metric-value-custom" style="color: #10b981; font-size: 1.8rem; margin: 0.6rem 0;">🟢 CONNECTED</div>
        <div style="font-size: 0.8rem; color: #8a99ad;">Endpoint: {API_URL}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card-custom">
        <div class="metric-label-custom">Golden Profiles</div>
        <div class="metric-value-custom" style="color: #3b82f6;">{total_customers}</div>
        <div style="font-size: 0.8rem; color: #8a99ad;">Unified CRM target database</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    pending_count = len(flagged_queue)
    color = "#ef4444" if pending_count > 0 else "#10b981"
    st.markdown(f"""
    <div class="metric-card-custom">
        <div class="metric-label-custom">Pending Review</div>
        <div class="metric-value-custom" style="color: {color};">{pending_count}</div>
        <div style="font-size: 0.8rem; color: #8a99ad;">Flagged duplicate records</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    success_runs = sum(1 for r in runs if r["status"] == "success")
    total_runs = len(runs)
    st.markdown(f"""
    <div class="metric-card-custom">
        <div class="metric-label-custom">Pipeline Ingestion Runs</div>
        <div class="metric-value-custom" style="color: #a855f7;">{success_runs}/{total_runs}</div>
        <div style="font-size: 0.8rem; color: #8a99ad;">Successful executions</div>
    </div>
    """, unsafe_allow_html=True)

# Main Dashboard Navigation Tabs
tab1, tab2, tab3 = st.tabs(["📈 Run History & Analytics", "🧑‍⚖️ Resolution Queue", "🔍 Golden Directory"])

# ==================== TAB 1: RUN HISTORY & ANALYTICS ====================
with tab1:
    col_left, col_right = st.columns([2, 5])
    
    with col_left:
        st.subheader("Orchestration")
        st.write("Trigger the CRM extraction, deduplication, and matching engine pipeline on-demand:")
        if st.button("🚀 Trigger Ingestion Run", use_container_width=True):
            success = trigger_pipeline_ingestion()
            if success:
                st.toast("Pipeline execution triggered in background task!", icon="⚡")
                st.info("Pipeline is executing... refreshing dashboard in 3 seconds.")
                import time
                time.sleep(3)
                force_refresh()
            else:
                st.error("Failed to trigger pipeline execution.")
        
        st.divider()
        st.subheader("Pipeline Run History")
        if not runs:
            st.info("No runs found.")
        else:
            df_runs = pd.DataFrame(runs)
            st.dataframe(
                df_runs[["id", "status", "records_extracted", "records_processed", "started_at"]],
                use_container_width=True,
                hide_index=True
            )

    with col_right:
        st.subheader("Ingestion Telemetry Visualizations")
        if not runs:
            st.info("No telemetry logs available.")
        else:
            # Prepare runs history for Plotly rendering
            df_runs = pd.DataFrame(runs).sort_values("id")
            
            # Grouped bar chart showing run statistics
            fig_data = []
            for idx, r in df_runs.iterrows():
                # For success runs, show records allocation
                if r["status"] == "success":
                    fig_data.append({"Run ID": f"Run {r['id']}", "Metric": "Merged/Linked", "Count": r["records_merged"]})
                    fig_data.append({"Run ID": f"Run {r['id']}", "Metric": "Flagged Review", "Count": r["records_flagged"]})
                    # New created profiles = records_processed - merged - flagged
                    created = max(0, r["records_processed"] - r["records_merged"] - r["records_flagged"])
                    fig_data.append({"Run ID": f"Run {r['id']}", "Metric": "Created Profiles", "Count": created})
                    # Skipped records = extracted - processed
                    skipped = max(0, r["records_extracted"] - r["records_processed"])
                    fig_data.append({"Run ID": f"Run {r['id']}", "Metric": "Skipped (Idempotent)", "Count": skipped})
                else:
                    fig_data.append({"Run ID": f"Run {r['id']}", "Metric": "Failed Run", "Count": r["records_extracted"]})
            
            df_chart = pd.DataFrame(fig_data)
            
            # Render chart
            fig = px.bar(
                df_chart, 
                x="Run ID", 
                y="Count", 
                color="Metric", 
                title="Records Breakdown per ETL Execution Run",
                color_discrete_map={
                    "Merged/Linked": "#10b981", 
                    "Flagged Review": "#f59e0b", 
                    "Created Profiles": "#3b82f6",
                    "Skipped (Idempotent)": "#6b7280",
                    "Failed Run": "#ef4444"
                },
                barmode="stack",
                height=450
            )
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='#fafafa',
                title_font_size=18,
                title_x=0.0,
                xaxis_title="Pipeline Execution Index",
                yaxis_title="Record Counts",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            st.plotly_chart(fig, use_container_width=True)

# ==================== TAB 2: RESOLUTION QUEUE ====================
with tab2:
    st.subheader("Manual Matching Resolution Queue")
    st.write("Double-check ambiguous matches flagged by the reconciliation engine. Approve matches or reject and force profile creations:")
    
    if not flagged_queue:
        st.success("🎉 All flagged records resolved! Review queue is empty.")
    else:
        # Loop through pending review records
        for i, item in enumerate(flagged_queue):
            # Header block for each flagged record
            st.markdown(f"""
            <div style="background: rgba(245, 158, 11, 0.05); border-left: 5px solid #f59e0b; padding: 1rem; border-radius: 4px; margin-top: 1rem;">
                <h4 style="margin: 0; color: #f59e0b;">Flagged Conflict #{item['id']} — Ingested from '{item['source_system'].upper()}'</h4>
                <p style="margin: 0.3rem 0 0 0; font-size: 0.9rem; color: #d1d5db;">
                    <strong>Source ID:</strong> <code>{item['source_record_id']}</code> | 
                    <strong>Fuzzy Match Score:</strong> <code style="color: #f59e0b; font-weight: bold;">{item['confidence_score']}%</code>
                </p>
                <p style="margin: 0.2rem 0 0 0; font-size: 0.85rem; color: #9ca3af; font-style: italic;">
                    <strong>Reason:</strong> {item['reason']}
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            col_source, col_match, col_actions = st.columns([3, 3, 2])
            
            with col_source:
                st.caption("📥 Incoming Source Record Payload:")
                st.json(item["raw_data"])
                
            with col_match:
                st.caption("⚖️ Potential Target Unified Match in Database:")
                if item["potential_match_id"]:
                    target_profile = fetch_customer_detail(str(item["potential_match_id"]))
                    if target_profile:
                        st.json({
                            "unified_customer_id": target_profile["id"],
                            "full_name": target_profile["full_name"],
                            "email": target_profile["email"],
                            "phone": target_profile["phone"],
                            "address": target_profile["address"]
                        })
                    else:
                        st.warning("Potential match profile not found.")
                else:
                    st.info("No potential match profile linked.")
                    
            with col_actions:
                st.caption("⚡ Resolution Decisions:")
                # Resolution buttons
                merge_btn_key = f"merge_btn_{item['id']}"
                create_btn_key = f"create_btn_{item['id']}"
                
                st.write("")
                if st.button("🔗 Merge & Enrich Target Profile", key=merge_btn_key, use_container_width=True, type="primary"):
                    success, res_data = resolve_flagged_record(item["id"], "merge")
                    if success:
                        st.toast(f"Merged successfully with target profile!", icon="✅")
                        st.success("Reconciliation committed.")
                        import time
                        time.sleep(1)
                        force_refresh()
                    else:
                        st.error(f"Failed to merge: {res_data}")
                        
                if st.button("➕ Force Create Separate Profile", key=create_btn_key, use_container_width=True):
                    success, res_data = resolve_flagged_record(item["id"], "create")
                    if success:
                        st.toast(f"Created new golden customer profile!", icon="✅")
                        st.success("Profile created.")
                        import time
                        time.sleep(1)
                        force_refresh()
                    else:
                        st.error(f"Failed to create: {res_data}")
            st.markdown("<hr style='border: 1px solid rgba(255,255,255,0.05); margin: 1.5rem 0;'>", unsafe_allow_html=True)

# ==================== TAB 3: GOLDEN DIRECTORY ====================
with tab3:
    st.subheader("Unified CRM Golden Profiles")
    st.write("Browse consolidated customer profiles and trace their source mapping histories:")
    
    # Search controls
    search_q = st.text_input("🔍 Search Customers (by name, email, or phone):", value="")
    
    customers_list = search_customers(search_q)
    
    if not customers_list:
        st.warning("No golden records matching your search query were found.")
    else:
        st.write(f"Showing {len(customers_list)} unified customer records:")
        
        # Display customers as select list
        for cust in customers_list:
            # We use st.expander for each customer to show detail information
            expander_label = f"👤 {cust['full_name']} | ✉️ {cust['email'] or 'N/A'} | 📞 {cust['phone'] or 'N/A'}"
            with st.expander(expander_label):
                # Pull full detail + provenance lineage
                details = fetch_customer_detail(cust["id"])
                if details:
                    col_info, col_prov = st.columns([1, 1])
                    
                    with col_info:
                        st.markdown(f"#### Unified Golden Profile details")
                        st.write(f"**Customer ID:** `{details['id']}`")
                        st.write(f"**Full Name:** {details['full_name']}")
                        st.write(f"**Email:** {details['email'] or 'None'}")
                        st.write(f"**Phone:** {details['phone'] or 'None'}")
                        st.write(f"**Address:** {details['address'] or 'None'}")
                        st.caption(f"Profile created: {details['created_at']} | Last Updated: {details['updated_at']}")
                        
                    with col_prov:
                        st.markdown("#### 🔗 Data Provenance & Source Lineage")
                        st.write("This profile is consolidated from the following source system inputs:")
                        
                        for idx, p in enumerate(details.get("provenance", [])):
                            st.markdown(f"""
                            <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.05); padding: 0.75rem; border-radius: 6px; margin-bottom: 0.5rem;">
                                <span style="font-size: 0.85rem; text-transform: uppercase; font-weight: bold; color: #3b82f6;">Source #{idx + 1}: {p['source_system'].upper()}</span><br>
                                <span style="font-size: 0.8rem; color: #9ca3af;">Record ID: <code>{p['source_record_id']}</code> | Matched at: {p['matched_at']}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Expandable original payload
                            with st.expander(f"Inspect Original raw payload ({p['source_system']})", expanded=False):
                                st.json(p["raw_data"])
                else:
                    st.error("Could not fetch customer lineage details.")
