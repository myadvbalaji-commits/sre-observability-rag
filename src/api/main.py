import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from src.config import settings
from src.telemetry.tracer import init_tracer, trace_span
from src.rag.document_loader import DocumentLoader
from src.rag.vector_store import SREVectorStore
from src.engine.incident_analyzer import IncidentAnalyzer

# Initialize telemetry
init_tracer()
logger = logging.getLogger("sre_rag.api")

app = FastAPI(
    title="SRE Observability RAG API",
    description="Production-ready Incident Root Cause Analysis and Runbook Retrieval with OpenTelemetry and Google Gemini",
    version="1.0.0"
)

# Global instances
vector_store = SREVectorStore()
analyzer = IncidentAnalyzer(vector_store=vector_store)

# Load sample data on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Initializing SRE Knowledge Base from sample data...")
    docs = DocumentLoader.load_all_sample_data(settings.sample_data_dir)
    vector_store.add_documents(docs)
    logger.info(f"Loaded {len(docs)} documents into vector index.")

class AlertPayload(BaseModel):
    incident_id: str
    title: str
    severity: str
    service: str
    status: Optional[str] = "FIRING"
    environment: Optional[str] = "production"
    metrics: Optional[Dict[str, Any]] = None
    trace_sample: Optional[Dict[str, Any]] = None

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.otel_service_name,
        "environment": settings.otel_environment,
        "indexed_documents": len(vector_store.documents)
    }

@app.post("/api/v1/incidents/analyze")
def analyze_incident_endpoint(payload: AlertPayload):
    with trace_span("api.analyze_incident", {"incident.id": payload.incident_id, "service": payload.service}):
        try:
            result = analyzer.analyze_incident(payload.dict())
            return result
        except Exception as e:
            logger.error(f"Incident analysis failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/search")
def search_knowledge_base(
    q: str = Query(..., description="Query string for postmortems and runbooks"),
    top_k: int = Query(3, ge=1, le=10),
    doc_type: Optional[str] = Query(None, description="Filter by 'postmortem' or 'runbook'")
):
    with trace_span("api.search_knowledge", {"query": q, "top_k": top_k}):
        return {
            "query": q,
            "results": vector_store.search(query=q, top_k=top_k, filter_doc_type=doc_type)
        }

@app.post("/api/v1/knowledge/ingest")
def reload_knowledge_base():
    docs = DocumentLoader.load_all_sample_data(settings.sample_data_dir)
    vector_store.add_documents(docs)
    return {"message": "Knowledge base refreshed successfully", "indexed_count": len(docs)}
