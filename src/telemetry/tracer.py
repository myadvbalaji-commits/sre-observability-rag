import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any

from src.config import settings

logger = logging.getLogger("sre_rag.telemetry")

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace import Status, StatusCode
    HAS_OTEL = True
except ImportError:
    trace = None
    HAS_OTEL = False

class DummySpan:
    def __init__(self, name: str):
        self.name = name
        self.attributes = {}

    def set_attribute(self, k: str, v: Any):
        self.attributes[k] = v

    def record_exception(self, ex: Exception):
        pass

    def set_status(self, status: Any, description: str = ""):
        pass

class DummyTracer:
    @contextmanager
    def start_as_current_span(self, name: str):
        span = DummySpan(name)
        yield span

def init_tracer(service_name: Optional[str] = None):
    svc_name = service_name or settings.otel_service_name
    if not HAS_OTEL:
        logger.info("OpenTelemetry SDK not installed in environment; using local trace stub.")
        return DummyTracer()

    resource = Resource.create({
        "service.name": svc_name,
        "service.version": "1.0.0",
        "deployment.environment": settings.otel_environment,
    })

    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            insecure=settings.otel_exporter_otlp_insecure,
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    except Exception as e:
        logger.warning(f"OTLP Exporter setup skipped ({e}). Using tracer provider.")

    trace.set_tracer_provider(provider)
    return trace.get_tracer(svc_name)

def get_tracer():
    if not HAS_OTEL:
        return DummyTracer()
    return trace.get_tracer(settings.otel_service_name)

@contextmanager
def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Context manager to create OpenTelemetry spans with standardized SRE GenAI attributes."""
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                if v is not None:
                    span.set_attribute(k, str(v) if not isinstance(v, (int, float, bool)) else v)
        try:
            yield span
        except Exception as ex:
            if hasattr(span, "record_exception"):
                span.record_exception(ex)
            raise
