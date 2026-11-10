import json
from pathlib import Path
import streamlit as st
import pandas as pd

from src.config import settings
from src.rag.document_loader import DocumentLoader
from src.rag.vector_store import SREVectorStore
from src.engine.incident_analyzer import IncidentAnalyzer

st.set_page_config(
    page_title="SRE Incident RAG & Observability Studio",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom header styling
st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: #1E88E5; }
    .stAlert { border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🛡️ SRE Incident RAG & Observability Studio</div>', unsafe_allow_html=True)
st.caption("AI-Augmented Incident Commander powered by Google Gemini & OpenTelemetry")

@st.cache_resource
def load_system():
    vs = SREVectorStore()
    docs = DocumentLoader.load_all_sample_data(settings.sample_data_dir)
    vs.add_documents(docs)
    an = IncidentAnalyzer(vector_store=vs)
    return vs, an

vector_store, analyzer = load_system()

# Sidebar
with st.sidebar:
    st.header("⚙️ Telemetry & System Config")
    st.write(f"**Service:** `{settings.otel_service_name}`")
    st.write(f"**Collector:** `{settings.otel_exporter_otlp_endpoint}`")
    st.write(f"**Indexed Docs:** {len(vector_store.documents)}")
    
    st.divider()
    st.subheader("Preset Incidents")
    preset_choice = st.selectbox(
        "Load sample alert payload:",
        ["Kubernetes OOMKilled (checkout-service)", "Postgres Pool Saturation (billing-api)", "Custom JSON"]
    )

# Sample payloads
presets = {
    "Kubernetes OOMKilled (checkout-service)": {
        "incident_id": "INC-8941",
        "title": "High HTTP 502 Rate and Pod Restarts in checkout-service",
        "severity": "P1",
        "service": "checkout-service",
        "status": "FIRING",
        "metrics": {"error_rate": "18.4%", "p99_latency_ms": 4200, "restart_count_5m": 14},
        "trace_sample": {
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
            "failing_span": "checkout-service.processOrder",
            "error_message": "Command terminated: exit status 137 (OOMKilled)",
            "span_attributes": {"http.status_code": 502, "service.name": "checkout-service"}
        }
    },
    "Postgres Pool Saturation (billing-api)": {
        "incident_id": "INC-8942",
        "title": "Connection timeout and query queue saturation",
        "severity": "P1",
        "service": "billing-api",
        "status": "FIRING",
        "metrics": {"error_rate": "42.1%", "p99_latency_ms": 32000, "waiting_clients": 180},
        "trace_sample": {
            "trace_id": "9df76b2189a14de8b2fe919c0f0f5821",
            "failing_span": "billing.executeTransaction",
            "error_message": "FATAL: remaining connection slots are reserved",
            "span_attributes": {"db.system": "postgresql", "db.statement": "SELECT ... FOR UPDATE"}
        }
    }
}

tab1, tab2, tab3 = st.tabs(["🚨 Incident Diagnosis Studio", "📚 RAG Knowledge Base", "📈 OpenTelemetry Spans"])

with tab1:
    col_input, col_output = st.columns([1, 1])
    
    with col_input:
        st.subheader("1. Incident Alert & Telemetry Payload")
        if preset_choice in presets:
            default_text = json.dumps(presets[preset_choice], indent=2)
        else:
            default_text = '{\n  "incident_id": "INC-NEW",\n  "title": "",\n  "service": "",\n  "trace_sample": {}\n}'
            
        payload_str = st.text_area("Alert JSON:", value=default_text, height=380)
        run_btn = st.button("🚀 Analyze Incident with RAG", type="primary", use_container_width=True)

    with col_output:
        st.subheader("2. AI SRE Diagnosis & Mitigation")
        if run_btn:
            try:
                alert_dict = json.loads(payload_str)
                with st.spinner("Retrieving historical postmortems & synthesizing RCA..."):
                    rca_result = analyzer.analyze_incident(alert_dict)
                
                st.success(f"**Confidence Score:** {int(rca_result.get('confidence_score', 0.9) * 100)}%")
                st.markdown(f"### 🎯 Root Cause Summary\n{rca_result.get('root_cause_summary')}")
                
                with st.expander("🔍 Deep Technical Analysis", expanded=True):
                    st.write(rca_result.get("root_cause_analysis"))
                
                st.markdown("### 🛠️ Immediate Mitigations")
                for step in rca_result.get("immediate_mitigation_steps", []):
                    st.markdown(f"- {step}")

                st.markdown("### 💻 Recommended Commands")
                for cmd in rca_result.get("mitigation_commands", []):
                    st.code(cmd, language="bash")
                    
                st.markdown("### 📋 Correlated Historical Incidents")
                for inc in rca_result.get("similar_past_incidents", []):
                    st.info(f"Matched Postmortem: `{inc}`")
            except Exception as e:
                st.error(f"Error parsing or analyzing payload: {e}")
        else:
            st.info("Select a preset alert on the left and click **Analyze Incident** to trigger the RAG pipeline.")

with tab2:
    st.subheader("Indexed Postmortems and Runbooks")
    query = st.text_input("Semantic Search across SRE Documents:", value="OOMKilled memory limit")
    if query:
        results = vector_store.search(query, top_k=5)
        for r in results:
            with st.expander(f"📄 {r['doc_id']} (Similarity: {r['similarity_score']})"):
                st.write(f"**Type:** `{r['metadata'].get('doc_type', 'unknown')}`")
                st.markdown(r["content"])

with tab3:
    st.subheader("OpenTelemetry Tracing Integration")
    st.markdown("""
    This service exports spans complying with **OpenTelemetry GenAI & SRE Semantic Conventions**:
    - `gen_ai.system`: Google Gemini
    - `gen_ai.request.model`: gemini-1.5-pro-latest
    - `incident.id`: Tagged to root trace span
    - `service.name`: Tagged to impacted microservice
    
    Start the local OpenTelemetry Collector & Jaeger with:
    ```bash
    docker-compose up otel-collector jaeger
    ```
    Then view your live trace waterfall at [http://localhost:16686](http://localhost:16686).
    """)
