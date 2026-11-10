from src.engine.incident_analyzer import IncidentAnalyzer
from src.rag.vector_store import SREVectorStore


def test_incident_analyzer_pipeline():
    store = SREVectorStore()
    analyzer = IncidentAnalyzer(vector_store=store)

    alert = {
        "incident_id": "INC-TEST-01",
        "title": "Pod CrashLoopBackOff",
        "service": "checkout-service",
        "trace_sample": {
            "error_message": "Exit status 137 OOMKilled",
            "failing_span": "checkout.process"
        }
    }

    result = analyzer.analyze_incident(alert)
    assert result["incident_id"] == "INC-TEST-01"
    assert "root_cause_summary" in result
    assert "mitigation_commands" in result
    assert len(result["mitigation_commands"]) > 0
    assert result["confidence_score"] >= 0.8
