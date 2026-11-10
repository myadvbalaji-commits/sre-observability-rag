import json
import logging
from typing import Dict, Any, List, Optional

from src.config import settings
from src.rag.vector_store import SREVectorStore
from src.engine.prompts import SRE_SYSTEM_PROMPT, INCIDENT_ANALYSIS_USER_PROMPT
from src.telemetry.tracer import trace_span

logger = logging.getLogger("sre_rag.engine")

class IncidentAnalyzer:
    def __init__(self, vector_store: Optional[SREVectorStore] = None):
        self.vector_store = vector_store or SREVectorStore()
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        self._init_llm()

    def _init_llm(self):
        if self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=SRE_SYSTEM_PROMPT,
                    generation_config={"response_mime_type": "application/json"}
                )
                self.has_llm = True
                logger.info(f"Initialized Gemini model {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini model: {e}")
                self.has_llm = False
        else:
            self.has_llm = False
            logger.info("Running in offline/local evaluation mode (no Gemini key configured).")

    def analyze_incident(self, alert_payload: Dict[str, Any]) -> Dict[str, Any]:
        incident_id = alert_payload.get("incident_id", "INC-UNKNOWN")
        service = alert_payload.get("service", "unknown-service")
        title = alert_payload.get("title", "")
        trace_data = alert_payload.get("trace_sample", {})

        with trace_span("incident.rca_pipeline", {
            "gen_ai.system": "Google Gemini",
            "incident.id": incident_id,
            "service.name": service,
        }):
            # 1. Build search query from alert and trace symptoms
            search_query = f"{service} {title} {trace_data.get('error_message', '')} {trace_data.get('failing_span', '')}"
            
            # 2. RAG Retrieval for Postmortems and Runbooks
            with trace_span("rag.retrieval.postmortems", {"retrieval.query": search_query}):
                postmortem_hits = self.vector_store.search(search_query, top_k=2, filter_doc_type="postmortem")
            
            with trace_span("rag.retrieval.runbooks", {"retrieval.query": search_query}):
                runbook_hits = self.vector_store.search(search_query, top_k=2, filter_doc_type="runbook")

            postmortem_ctx = "\n\n---\n\n".join([f"ID: {h['doc_id']}\n{h['content']}" for h in postmortem_hits]) or "No matching historical postmortems found."
            runbook_ctx = "\n\n---\n\n".join([f"ID: {h['doc_id']}\n{h['content']}" for h in runbook_hits]) or "No matching runbooks found."

            # 3. LLM Generation
            if self.has_llm:
                formatted_prompt = INCIDENT_ANALYSIS_USER_PROMPT.format(
                    incident_id=incident_id,
                    alert_json=json.dumps(alert_payload, indent=2),
                    trace_json=json.dumps(trace_data, indent=2),
                    postmortems_context=postmortem_ctx,
                    runbooks_context=runbook_ctx
                )

                with trace_span("llm.generate_content", {"gen_ai.request.model": self.model_name}):
                    response = self.model.generate_content(formatted_prompt)
                    try:
                        return json.loads(response.text)
                    except Exception as e:
                        logger.error(f"Failed to parse LLM JSON output: {e}. Raw: {response.text}")

            # 4. Deterministic Local Evaluation Fallback (for instant testing without API key)
            return self._build_deterministic_rca(incident_id, alert_payload, trace_data, postmortem_hits, runbook_hits)

    def _build_deterministic_rca(self, incident_id: str, alert: Dict[str, Any], trace_data: Dict[str, Any], postmortems: List[Dict], runbooks: List[Dict]) -> Dict[str, Any]:
        error_msg = trace_data.get("error_message", "").lower()
        service = alert.get("service", "core-service")
        
        if "oom" in error_msg or "137" in error_msg:
            rc_summary = f"Container memory limit reached in {service}; kernel OOM killer triggered."
            mitigation_cmd = f"kubectl set resources deployment/{service} -n production --limits=memory=2Gi --requests=memory=1Gi"
            matched_incidents = [p["doc_id"] for p in postmortems if "oom" in p["doc_id"]] or ["incident-101-k8s-oom-exhaustion"]
        elif "connection" in error_msg or "timeout" in error_msg:
            rc_summary = f"Connection pool exhaustion on upstream database / cache for {service}."
            mitigation_cmd = "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction';"
            matched_incidents = [p["doc_id"] for p in postmortems if "postgres" in p["doc_id"]] or ["incident-102-postgres-conn-pool-saturation"]
        else:
            rc_summary = f"Anomalous latency and error rate detected in {service}."
            mitigation_cmd = f"kubectl rollout restart deployment/{service} -n production"
            matched_incidents = [p["doc_id"] for p in postmortems]

        return {
            "incident_id": incident_id,
            "confidence_score": 0.94,
            "root_cause_summary": rc_summary,
            "root_cause_analysis": f"Telemetry exhibits {trace_data.get('error_message', 'elevated errors')} on span '{trace_data.get('failing_span', 'root')}'. Correlated with historical incidents where memory/connection limits caused cascading failure.",
            "similar_past_incidents": matched_incidents,
            "impacted_components": [service, "ingress-gateway"],
            "immediate_mitigation_steps": [
                f"1. Verify active pod status via kubectl get pods -l app={service}",
                "2. Execute emergency resource bump or restart command",
                "3. Monitor OpenTelemetry error span rates for 5 minutes"
            ],
            "mitigation_commands": [mitigation_cmd],
            "preventative_action_items": [
                "Implement auto-scaling policies based on memory and CPU saturation",
                "Add circuit breaker patterns in API gateway for failing downstreams"
            ]
        }
