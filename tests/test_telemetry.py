from src.telemetry.tracer import init_tracer, trace_span


def test_trace_span_context():
    init_tracer("test-sre-service")
    with trace_span("test.operation", {"custom.tag": "value"}) as span:
        assert span is not None
