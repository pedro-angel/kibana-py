"""Unit tests for OpenTelemetry observability."""

import logging
from unittest.mock import patch

import pytest

# Check if OpenTelemetry is available
try:
    import importlib.util

    OTEL_AVAILABLE = importlib.util.find_spec("opentelemetry") is not None
except ImportError:
    OTEL_AVAILABLE = False


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestKibanaInstrumentor:
    """Tests for KibanaInstrumentor."""

    def test_get_instance_returns_singleton(self):
        """Test that get_instance returns the same instance."""
        from kibana.observability import KibanaInstrumentor

        instance1 = KibanaInstrumentor.get_instance()
        instance2 = KibanaInstrumentor.get_instance()

        assert instance1 is instance2

    def test_enable_sets_enabled_flag(self):
        """Test that enable() sets the enabled flag."""
        from kibana.observability import KibanaInstrumentor

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()  # Start disabled

        instrumentor.enable()

        assert instrumentor.is_enabled() is True

    def test_disable_clears_enabled_flag(self):
        """Test that disable() clears the enabled flag."""
        from kibana.observability import KibanaInstrumentor

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.enable()

        instrumentor.disable()

        assert instrumentor.is_enabled() is False

    def test_get_tracer_returns_none_when_disabled(self):
        """Test that get_tracer returns None when disabled."""
        from kibana.observability import KibanaInstrumentor

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        tracer = instrumentor.get_tracer()

        assert tracer is None

    def test_enable_with_custom_tracer_provider(self):
        """Test enabling with custom tracer provider."""
        from opentelemetry.sdk.trace import TracerProvider

        from kibana.observability import KibanaInstrumentor

        instrumentor = KibanaInstrumentor.get_instance()
        tracer_provider = TracerProvider()

        instrumentor.enable(tracer_provider=tracer_provider)

        assert instrumentor.is_enabled() is True
        assert instrumentor.get_tracer() is not None


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestConfigureOpenTelemetry:
    """Tests for configure_opentelemetry function."""

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._validate_apm_connectivity")
    def test_configure_with_defaults(self, mock_validate):
        """Test configuration with default values."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True

        # Disable first
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        # Configure with enabled=True
        configure_opentelemetry(enabled=True)

        assert instrumentor.is_enabled() is True

    @patch.dict("os.environ", {"KIBANA_OTEL_ENABLED": "true"}, clear=True)
    @patch("kibana.observability._validate_apm_connectivity")
    def test_configure_from_environment(self, mock_validate):
        """Test configuration from environment variables."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry()

        assert instrumentor.is_enabled() is True

    @patch.dict("os.environ", {"KIBANA_OTEL_ENABLED": "false"}, clear=True)
    def test_configure_disabled_from_environment(self):
        """Test that disabled environment variable prevents configuration."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry()

        assert instrumentor.is_enabled() is False

    def test_configure_with_console_exporter(self):
        """Test configuration with console exporter."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(enabled=True, exporter="console")

        assert instrumentor.is_enabled() is True

    @patch.dict("os.environ", {"OTEL_SERVICE_NAME": "test-service"}, clear=True)
    @patch("kibana.observability._validate_apm_connectivity")
    def test_configure_with_custom_service_name(self, mock_validate):
        """Test configuration with custom service name."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(enabled=True)

        assert instrumentor.is_enabled() is True


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestCreateSpan:
    """Tests for create_span function."""

    def test_create_span_returns_none_when_disabled(self):
        """Test that create_span returns None when instrumentation is disabled."""
        from kibana.observability import KibanaInstrumentor, create_span

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        span = create_span("test.span")

        assert span is None

    def test_create_span_with_attributes(self):
        """Test creating span with attributes."""
        from kibana.observability import configure_opentelemetry, create_span

        configure_opentelemetry(enabled=True, exporter="console")

        span = create_span("test.span", attributes={"test.key": "test.value"})

        assert span is not None
        span.end()

    def test_create_span_returns_span_when_enabled(self):
        """Test that create_span returns a span when enabled."""
        from kibana.observability import configure_opentelemetry, create_span

        configure_opentelemetry(enabled=True, exporter="console")

        span = create_span("test.span")

        assert span is not None
        span.end()


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestSetSpanError:
    """Tests for set_span_error function."""

    def test_set_span_error_with_none_span(self):
        """Test that set_span_error handles None span gracefully."""
        from kibana.observability import set_span_error

        # Should not raise
        set_span_error(None, Exception("test error"))

    def test_set_span_error_marks_span_as_error(self):
        """Test that set_span_error marks span as error."""
        from kibana.observability import (
            configure_opentelemetry,
            create_span,
            set_span_error,
        )

        configure_opentelemetry(enabled=True, exporter="console")

        span = create_span("test.span")
        error = Exception("test error")

        set_span_error(span, error)

        span.end()


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestAPMServerIntegration:
    """Tests for APM server integration features."""

    def test_parse_otlp_headers_from_env(self):
        """Test parsing OTLP headers from environment variables."""
        from kibana.observability import _parse_otlp_headers

        with patch.dict(
            "os.environ",
            {"OTEL_EXPORTER_OTLP_HEADERS": "key1=value1,key2=value2"},
            clear=False,
        ):
            # Remove any .env-injected token so only our test headers are parsed
            import os

            old_token = os.environ.pop("ELASTIC_APM_SECRET_TOKEN", None)
            try:
                headers = _parse_otlp_headers()
                assert headers == {"key1": "value1", "key2": "value2"}
            finally:
                if old_token is not None:
                    os.environ["ELASTIC_APM_SECRET_TOKEN"] = old_token

    def test_parse_otlp_headers_with_apm_token(self):
        """Test parsing OTLP headers with APM token."""
        from kibana.observability import _parse_otlp_headers

        with patch.dict(
            "os.environ",
            {"ELASTIC_APM_SECRET_TOKEN": "test-token-123"},
            clear=False,
        ):
            # Remove any .env-injected headers so only the token is used
            import os

            old_headers = os.environ.pop("OTEL_EXPORTER_OTLP_HEADERS", None)
            try:
                headers = _parse_otlp_headers()
                assert headers["authorization"] == "Bearer test-token-123"
            finally:
                if old_headers is not None:
                    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = old_headers

    def test_parse_otlp_headers_existing_auth_not_overridden(self):
        """Test that existing authorization header is not overridden."""
        from kibana.observability import _parse_otlp_headers

        with patch.dict(
            "os.environ",
            {
                "OTEL_EXPORTER_OTLP_HEADERS": "authorization=Bearer existing-token",
                "ELASTIC_APM_SECRET_TOKEN": "test-token-123",
            },
        ):
            headers = _parse_otlp_headers()
            assert headers["authorization"] == "Bearer existing-token"

    def test_create_otlp_exporter_grpc_protocol(self):
        """Test creating OTLP exporter with gRPC protocol."""
        from kibana.observability import _create_otlp_exporter

        exporter = _create_otlp_exporter(
            endpoint="http://localhost:4317",
            headers={"authorization": "Bearer test-token"},
            protocol="grpc",
        )
        assert exporter is not None

    def test_create_otlp_exporter_http_protocol(self):
        """Test creating OTLP exporter with HTTP protocol."""
        from kibana.observability import HTTP_EXPORTER_AVAILABLE, _create_otlp_exporter

        if HTTP_EXPORTER_AVAILABLE:
            exporter = _create_otlp_exporter(
                endpoint="http://localhost:4318",
                headers={"authorization": "Bearer test-token"},
                protocol="http/protobuf",
            )
            assert exporter is not None
        else:
            with pytest.raises(ImportError, match="HTTP OTLP exporter not available"):
                _create_otlp_exporter(
                    endpoint="http://localhost:4318",
                    headers={"authorization": "Bearer test-token"},
                    protocol="http/protobuf",
                )

    def test_create_otlp_exporter_invalid_protocol(self):
        """Test creating OTLP exporter with invalid protocol raises error."""
        from kibana.observability import _create_otlp_exporter

        with pytest.raises(ValueError, match="Unsupported OTLP protocol"):
            _create_otlp_exporter(
                endpoint="http://localhost:4317", headers={}, protocol="invalid"
            )

    @patch("socket.socket")
    def test_validate_apm_connectivity_success(self, mock_socket):
        """Test successful APM server connectivity validation."""
        from kibana.observability import _validate_apm_connectivity

        # Mock successful connection
        mock_sock_instance = mock_socket.return_value
        mock_sock_instance.connect_ex.return_value = 0

        result = _validate_apm_connectivity(
            endpoint="http://localhost:8200", headers={}, protocol="grpc"
        )
        assert result is True

    @patch("socket.socket")
    def test_validate_apm_connectivity_failure(self, mock_socket):
        """Test failed APM server connectivity validation."""
        from kibana.observability import _validate_apm_connectivity

        # Mock failed connection
        mock_sock_instance = mock_socket.return_value
        mock_sock_instance.connect_ex.return_value = 1

        result = _validate_apm_connectivity(
            endpoint="http://localhost:8200",
            headers={},
            protocol="grpc",
            max_retries=0,  # No retries for faster test
        )
        assert result is False

    @patch("socket.socket")
    def test_validate_amp_connectivity_with_retry(self, mock_socket):
        """Test APM connectivity validation with retry logic."""
        from kibana.observability import _validate_apm_connectivity

        # Mock first failure, then success
        mock_sock_instance = mock_socket.return_value
        mock_sock_instance.connect_ex.side_effect = [1, 0]  # Fail then succeed

        with patch("time.sleep"):  # Speed up test
            result = _validate_apm_connectivity(
                endpoint="http://localhost:8200",
                headers={},
                protocol="grpc",
                max_retries=1,
            )
        assert result is True

    def test_validate_apm_server_availability_public_function(self):
        """Test public APM server availability validation function."""
        from kibana.observability import validate_apm_server_availability

        with patch("kibana.observability._validate_apm_connectivity") as mock_validate:
            mock_validate.return_value = True

            result = validate_apm_server_availability("http://localhost:8200")
            assert result is True
            mock_validate.assert_called_once()

    def test_handle_telemetry_error_authentication(self, caplog):
        """Test handling authentication-related telemetry errors."""
        from kibana.observability import _handle_telemetry_error

        error = Exception("401 Unauthorized: Invalid token")

        with caplog.at_level(
            "ERROR", logger="kibana.observability"
        ):  # Both error and remediation are at ERROR level
            _handle_telemetry_error("test operation", error)

        assert "APM authentication failed" in caplog.text
        assert "Check ELASTIC_APM_SECRET_TOKEN" in caplog.text

    def test_handle_telemetry_error_network(self, caplog):
        """Test handling network-related telemetry errors."""
        from kibana.observability import _handle_telemetry_error

        error = Exception("Connection timeout")

        with caplog.at_level(
            "WARNING", logger="kibana.observability"
        ):  # Both error and remediation are at WARNING level
            _handle_telemetry_error("test operation", error)

        assert "APM network error" in caplog.text
        assert "Check APM server availability" in caplog.text

    def test_mask_sensitive_info_bearer_token(self):
        """Test masking Bearer tokens in sensitive information."""
        from kibana.observability import _mask_sensitive_info

        text = "Authorization: Bearer abc123def456"
        masked = _mask_sensitive_info(text)
        assert "Bearer [REDACTED]" in masked
        assert "abc123def456" not in masked

    def test_mask_sensitive_info_api_key(self):
        """Test masking API keys in sensitive information."""
        from kibana.observability import _mask_sensitive_info

        text = 'token="secret123456"'
        masked = _mask_sensitive_info(text)
        assert "[REDACTED]" in masked
        assert "secret123456" not in masked

    @patch("kibana.observability._create_otlp_exporter")
    def test_create_otlp_exporter_with_error_handling_success(self, mock_create):
        """Test successful OTLP exporter creation with error handling."""
        from kibana.observability import _create_otlp_exporter_with_error_handling

        mock_exporter = object()
        mock_create.return_value = mock_exporter

        result = _create_otlp_exporter_with_error_handling(
            endpoint="http://localhost:4317", headers={}, protocol="grpc"
        )
        assert result is mock_exporter

    @patch("kibana.observability._create_otlp_exporter")
    def test_create_otlp_exporter_with_error_handling_import_error(
        self, mock_create, caplog
    ):
        """Test OTLP exporter creation with ImportError."""
        from kibana.observability import _create_otlp_exporter_with_error_handling

        mock_create.side_effect = ImportError("Missing dependency")

        with caplog.at_level("ERROR", logger="kibana.observability"):
            result = _create_otlp_exporter_with_error_handling(
                endpoint="http://localhost:4317", headers={}, protocol="grpc"
            )

        assert result is None
        assert "Missing OpenTelemetry exporter dependency" in caplog.text

    @patch("kibana.observability._create_otlp_exporter")
    def test_create_otlp_exporter_with_error_handling_value_error(
        self, mock_create, caplog
    ):
        """Test OTLP exporter creation with ValueError."""
        from kibana.observability import _create_otlp_exporter_with_error_handling

        mock_create.side_effect = ValueError("Invalid configuration")

        with caplog.at_level("ERROR", logger="kibana.observability"):
            result = _create_otlp_exporter_with_error_handling(
                endpoint="http://localhost:4317", headers={}, protocol="invalid"
            )

        assert result is None
        assert "Invalid OTLP configuration" in caplog.text

    @patch.dict(
        "os.environ",
        {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:8200",
            "ELASTIC_APM_SECRET_TOKEN": "test-token",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
        },
    )
    @patch("kibana.observability._validate_apm_connectivity")
    @patch("kibana.observability._create_otlp_exporter_with_error_handling")
    def test_configure_opentelemetry_with_apm_integration(
        self, mock_create_exporter, mock_validate
    ):
        """Test configure_opentelemetry with APM server integration."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True
        mock_create_exporter.return_value = object()  # Mock exporter
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry()

        assert instrumentor.is_enabled() is True
        mock_validate.assert_called_once()

    @patch.dict(
        "os.environ",
        {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:8200",
        },
    )
    @patch("kibana.observability._validate_apm_connectivity")
    def test_configure_opentelemetry_apm_connectivity_failure(
        self, mock_validate, caplog
    ):
        """Test configure_opentelemetry when APM connectivity fails."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = False
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        with caplog.at_level("WARNING", logger="kibana.observability"):
            configure_opentelemetry()

        assert instrumentor.is_enabled() is False
        assert "APM server connectivity validation failed" in caplog.text


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestEnhancedSpanOperations:
    """Tests for enhanced span operations with error handling."""

    def test_create_span_with_error_handling(self):
        """Test create_span with enhanced error handling."""
        from kibana.observability import configure_opentelemetry, create_span

        configure_opentelemetry(enabled=True, exporter="console")

        # Should not raise even with invalid attributes
        span = create_span("test.span", attributes={"valid": "value"})
        assert span is not None
        span.end()

    def test_create_span_failure_returns_none(self):
        """Test that create_span returns None on failure."""
        from kibana.observability import KibanaInstrumentor, create_span

        # Disable instrumentation
        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        span = create_span("test.span")
        assert span is None

    def test_set_span_error_with_enhanced_handling(self):
        """Test set_span_error with enhanced error handling."""
        from kibana.observability import (
            configure_opentelemetry,
            create_span,
            set_span_error,
        )

        configure_opentelemetry(enabled=True, exporter="console")
        span = create_span("test.span")

        # Should not raise
        set_span_error(span, Exception("test error"))
        span.end()

    def test_safe_span_operation_success(self):
        """Test safe_span_operation with successful operation."""
        from kibana.observability import (
            configure_opentelemetry,
            create_span,
            safe_span_operation,
        )

        configure_opentelemetry(enabled=True, exporter="console")
        span = create_span("test.span")

        def test_func(value):
            return value * 2

        result = safe_span_operation(span, "test operation", test_func, 5)
        assert result == 10
        span.end()

    def test_safe_span_operation_failure(self):
        """Test safe_span_operation with failing operation."""
        from kibana.observability import (
            configure_opentelemetry,
            create_span,
            safe_span_operation,
        )

        configure_opentelemetry(enabled=True, exporter="console")
        span = create_span("test.span")

        def failing_func():
            raise Exception("Test failure")

        result = safe_span_operation(span, "failing operation", failing_func)
        assert result is None
        span.end()

    def test_safe_span_operation_with_none_span(self):
        """Test safe_span_operation with None span."""
        from kibana.observability import safe_span_operation

        def test_func():
            return "success"

        result = safe_span_operation(None, "test operation", test_func)
        assert result is None


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestOTelLogHandler:
    """Tests for OTelLogHandler."""

    def test_init_with_defaults(self):
        """Test OTelLogHandler initialization with default parameters."""
        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        assert handler.level == 30  # logging.WARNING
        assert handler._enabled is True
        assert handler._error_count == 0
        assert handler._max_errors == 10

    def test_init_with_custom_level(self):
        """Test OTelLogHandler initialization with custom log level."""
        import logging

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler(level=logging.ERROR)

        assert handler.level == logging.ERROR

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", True)
    def test_init_with_logger_provider(self):
        """Test OTelLogHandler initialization with logger provider."""
        from unittest.mock import Mock

        from kibana.observability import OTelLogHandler, _get_kibana_py_version

        mock_logger_provider = Mock()
        mock_logger = Mock()
        mock_logger_provider.get_logger.return_value = mock_logger

        handler = OTelLogHandler(logger_provider=mock_logger_provider)

        assert handler._otel_logger is mock_logger
        mock_logger_provider.get_logger.assert_called_once_with(
            "kibana-py",
            version=_get_kibana_py_version(),
            schema_url=None,
        )

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", False)
    def test_emit_when_logs_not_available(self):
        """Test emit method when OpenTelemetry logs not available."""
        import logging

        from kibana.observability import OTelLogHandler

        handler = OTelLogHandler()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Should not raise
        handler.emit(record)

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", True)
    def test_emit_forwards_log_record(self):
        """Test emit method forwards log record to OpenTelemetry."""
        import logging
        from unittest.mock import Mock, patch

        from kibana.observability import OTelLogHandler

        mock_logger_provider = Mock()
        mock_logger = Mock()
        mock_logger_provider.get_logger.return_value = mock_logger

        handler = OTelLogHandler(logger_provider=mock_logger_provider)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        with patch.object(handler, "_forward_log") as mock_forward:
            handler.emit(record)
            mock_forward.assert_called_once_with(record)

    def test_emit_handles_forwarding_errors(self):
        """Test emit method handles forwarding errors gracefully."""
        import logging
        from unittest.mock import Mock, patch

        from kibana.observability import OTelLogHandler

        mock_logger_provider = Mock()
        mock_logger = Mock()
        mock_logger_provider.get_logger.return_value = mock_logger

        handler = OTelLogHandler(logger_provider=mock_logger_provider)

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        with patch.object(handler, "_forward_log", side_effect=Exception("Test error")):
            with patch("sys.stderr"):  # Suppress stderr output during test
                handler.emit(record)

        assert handler._error_count == 1

    def test_emit_disables_handler_after_max_errors(self):
        """Test emit method disables handler after maximum errors."""
        import logging
        from unittest.mock import Mock, patch

        from kibana.observability import OTelLogHandler

        mock_logger_provider = Mock()
        mock_logger = Mock()
        mock_logger_provider.get_logger.return_value = mock_logger

        handler = OTelLogHandler(logger_provider=mock_logger_provider)
        handler._max_errors = 2  # Lower threshold for testing

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        with patch.object(handler, "_forward_log", side_effect=Exception("Test error")):
            with patch("sys.stderr"):  # Suppress stderr output during test
                # First two errors should increment count
                handler.emit(record)
                handler.emit(record)
                assert handler._error_count == 2
                assert handler._enabled is True

                # Third error should disable handler
                handler.emit(record)
                assert handler._error_count == 3
                assert handler._enabled is False

    def test_extract_attributes_basic(self):
        """Test _extract_attributes method with basic log record."""
        import logging

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/path/to/test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_function"
        record.module = "test_module"
        record.process = 12345
        record.thread = 67890
        record.threadName = "MainThread"

        attributes = handler._extract_attributes(record)

        assert attributes["log.logger"] == "test.logger"
        assert attributes["log.level"] == "ERROR"
        assert attributes["log.file.name"] == "/path/to/test.py"
        assert attributes["log.file.line"] == 123
        assert attributes["log.function"] == "test_function"
        assert attributes["log.module"] == "test_module"
        assert attributes["process.pid"] == 12345
        assert attributes["thread.id"] == 67890
        assert attributes["thread.name"] == "MainThread"
        assert attributes["service.name"] == "kibana-py"
        assert attributes["service.language.name"] == "python"

    def test_extract_attributes_with_custom_extras(self):
        """Test _extract_attributes method with custom log record extras."""
        import logging

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add custom attributes
        record.custom_string = "test_value"
        record.custom_int = 42
        record.custom_float = 3.14
        record.custom_bool = True
        record.custom_none = None
        record.custom_object = {"key": "value"}  # Should be converted to string

        attributes = handler._extract_attributes(record)

        assert attributes["custom.custom_string"] == "test_value"
        assert attributes["custom.custom_int"] == 42
        assert attributes["custom.custom_float"] == 3.14
        assert attributes["custom.custom_bool"] is True
        assert "custom.custom_none" not in attributes  # None values excluded
        assert attributes["custom.custom_object"] == "{'key': 'value'}"

    def test_map_log_level_to_severity(self):
        """Test _map_log_level_to_severity method."""
        import logging

        from opentelemetry._logs import SeverityNumber

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        assert (
            handler._map_log_level_to_severity(logging.CRITICAL) == SeverityNumber.FATAL
        )
        assert handler._map_log_level_to_severity(logging.ERROR) == SeverityNumber.ERROR
        assert (
            handler._map_log_level_to_severity(logging.WARNING) == SeverityNumber.WARN
        )
        assert handler._map_log_level_to_severity(logging.INFO) == SeverityNumber.INFO
        assert handler._map_log_level_to_severity(logging.DEBUG) == SeverityNumber.DEBUG
        assert handler._map_log_level_to_severity(5) == SeverityNumber.TRACE

    @patch("kibana.observability.OTEL_AVAILABLE", True)
    def test_get_trace_context_with_active_span(self):
        """Test _get_trace_context method with active span."""
        from unittest.mock import Mock, patch

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        # Mock active span
        mock_span = Mock()
        mock_span.is_recording.return_value = True
        mock_span_context = Mock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 0x12345678901234567890123456789012
        mock_span_context.span_id = 0x1234567890123456
        mock_span_context.trace_flags = 1
        mock_span.get_span_context.return_value = mock_span_context

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            context = handler._get_trace_context()

        assert context["trace_id"] == 0x12345678901234567890123456789012
        assert context["span_id"] == 0x1234567890123456
        assert context["trace_flags"] == 1
        assert context["trace_id_hex"] == "12345678901234567890123456789012"
        assert context["span_id_hex"] == "1234567890123456"

    @patch("kibana.observability.OTEL_AVAILABLE", True)
    def test_get_trace_context_no_active_span(self):
        """Test _get_trace_context method with no active span."""
        from unittest.mock import Mock, patch

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        # Mock no active span — span context is invalid
        mock_span_context = Mock()
        mock_span_context.is_valid = False
        mock_span = Mock()
        mock_span.get_span_context.return_value = mock_span_context

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            context = handler._get_trace_context()

        assert context == {}

    @patch("kibana.observability.OTEL_AVAILABLE", False)
    def test_get_trace_context_otel_not_available(self):
        """Test _get_trace_context method when OpenTelemetry not available."""
        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()
        context = handler._get_trace_context()

        assert context == {}

    def test_get_trace_context_handles_exceptions(self):
        """Test _get_trace_context method handles exceptions gracefully."""
        from unittest.mock import patch

        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()

        with patch(
            "opentelemetry.trace.get_current_span", side_effect=Exception("Test error")
        ):
            context = handler._get_trace_context()

        assert context == {}

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", True)
    def test_create_log_record(self):
        """Test _create_log_record method."""
        import logging
        from unittest.mock import Mock, patch

        from kibana.observability import OTelLogHandler

        handler = OTelLogHandler()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=123,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.created = 1234567890.123

        mock_resource = Mock()
        handler._resource = mock_resource

        with patch.object(
            handler, "_extract_attributes", return_value={"test": "attr"}
        ):
            with patch.object(
                handler, "_get_trace_context", return_value={"trace_id": 123}
            ):
                with patch("opentelemetry._logs.LogRecord") as mock_log_record:
                    handler._create_log_record(record)

                    mock_log_record.assert_called_once()
                    call_args = mock_log_record.call_args[1]

                    # Check timestamp is approximately correct (within 1ms due to floating point precision)
                    expected_timestamp = 1234567890123000000  # nanoseconds
                    actual_timestamp = call_args["timestamp"]
                    assert (
                        abs(actual_timestamp - expected_timestamp) < 1000000
                    )  # Within 1ms
                    assert call_args["severity_text"] == "ERROR"
                    from opentelemetry._logs import SeverityNumber

                    assert call_args["severity_number"] == SeverityNumber.ERROR
                    assert call_args["body"] == "Test message"
                    assert call_args["attributes"] == {"test": "attr"}
                    assert call_args["trace_id"] == 123

    def test_close_disables_handler(self):
        """Test close method disables the handler."""
        from kibana.observability import OTEL_LOGS_AVAILABLE, OTelLogHandler

        if not OTEL_LOGS_AVAILABLE:
            pytest.skip("OpenTelemetry logs not available")

        handler = OTelLogHandler()
        assert handler._enabled is True

        handler.close()
        assert handler._enabled is False


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestLogForwardingConfiguration:
    """Tests for log forwarding configuration in configure_opentelemetry."""

    @patch.dict("os.environ", {}, clear=True)
    @patch("kibana.observability._validate_apm_connectivity")
    @patch("kibana.observability._setup_log_forwarding")
    def test_configure_with_log_forwarding_enabled(
        self, mock_setup_logs, mock_validate
    ):
        """Test configure_opentelemetry with log forwarding enabled."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True
        mock_setup_logs.return_value = []

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(
            enabled=True,
            logs_enabled=True,
            logs_level="ERROR",
            logs_loggers=["kibana", "test"],
        )

        assert instrumentor.is_enabled() is True
        mock_setup_logs.assert_called_once()
        call_kwargs = mock_setup_logs.call_args[1]
        assert call_kwargs["logs_enabled"] is True
        assert call_kwargs["logs_level"] == "ERROR"
        assert call_kwargs["logs_loggers"] == ["kibana", "test"]

    @patch.dict(
        "os.environ",
        {
            "KIBANA_OTEL_LOGS_ENABLED": "true",
            "KIBANA_OTEL_LOGS_LEVEL": "WARNING",
            "KIBANA_OTEL_LOGS_LOGGERS": "kibana,myapp",
        },
        clear=True,
    )
    @patch("kibana.observability._validate_apm_connectivity")
    @patch("kibana.observability._setup_log_forwarding")
    def test_configure_log_forwarding_from_environment(
        self, mock_setup_logs, mock_validate
    ):
        """Test log forwarding configuration from environment variables."""
        from kibana.observability import KibanaInstrumentor, configure_opentelemetry

        mock_validate.return_value = True
        mock_setup_logs.return_value = []

        instrumentor = KibanaInstrumentor.get_instance()
        instrumentor.disable()

        configure_opentelemetry(enabled=True)

        mock_setup_logs.assert_called_once()
        call_kwargs = mock_setup_logs.call_args[1]
        assert call_kwargs["logs_enabled"] is True
        assert call_kwargs["logs_level"] == "WARNING"
        assert call_kwargs["logs_loggers"] == ["kibana", "myapp"]

    @patch.dict("os.environ", {"KIBANA_OTEL_LOGS_LEVEL": "invalid"}, clear=True)
    def test_configure_invalid_log_level_uses_default(self, caplog):
        """Test that invalid log level falls back to default."""
        from kibana.observability import configure_opentelemetry

        with caplog.at_level("WARNING", logger="kibana.observability"):
            configure_opentelemetry(enabled=True, logs_enabled=True)

        assert "Invalid log level 'INVALID', using 'WARNING'" in caplog.text

    def test_configure_invalid_logs_loggers_type_uses_default(self, caplog):
        """Test that invalid logs_loggers type falls back to default."""
        from kibana.observability import configure_opentelemetry

        with caplog.at_level("WARNING", logger="kibana.observability"):
            configure_opentelemetry(
                enabled=True,
                logs_enabled=True,
                logs_loggers="not_a_list",  # Should be a list
            )

        assert "logs_loggers must be a list" in caplog.text

    @patch("kibana.observability._cleanup_log_handlers")
    @patch("kibana.observability._setup_log_forwarding")
    @patch("kibana.observability._validate_apm_connectivity")
    def test_configure_cleans_up_existing_handlers(
        self, mock_validate, mock_setup_logs, mock_cleanup
    ):
        """Test that configure_opentelemetry cleans up existing log handlers."""
        from unittest.mock import Mock

        import kibana.observability
        from kibana.observability import configure_opentelemetry

        mock_validate.return_value = True
        mock_setup_logs.return_value = []

        # Simulate existing handlers by directly modifying the module variable
        original_handlers = kibana.observability._created_log_handlers
        kibana.observability._created_log_handlers = [Mock(), Mock()]

        try:
            configure_opentelemetry(enabled=True, logs_enabled=True)
            mock_cleanup.assert_called_once()
            mock_setup_logs.assert_called_once()
        finally:
            # Restore original state
            kibana.observability._created_log_handlers = original_handlers


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestLogExporterCreation:
    """Tests for log exporter creation functions."""

    def test_create_otlp_log_exporter_grpc(self):
        """Test creating OTLP log exporter with gRPC protocol."""
        from kibana.observability import (
            GRPC_LOG_EXPORTER_AVAILABLE,
            _create_otlp_log_exporter,
        )

        if not GRPC_LOG_EXPORTER_AVAILABLE:
            with pytest.raises(
                ImportError, match="gRPC OTLP log exporter not available"
            ):
                _create_otlp_log_exporter(
                    endpoint="http://localhost:4317",
                    headers={"authorization": "Bearer test-token"},
                    protocol="grpc",
                )
        else:
            exporter = _create_otlp_log_exporter(
                endpoint="http://localhost:4317",
                headers={"authorization": "Bearer test-token"},
                protocol="grpc",
            )
            assert exporter is not None

    def test_create_otlp_log_exporter_http(self):
        """Test creating OTLP log exporter with HTTP protocol."""
        from kibana.observability import (
            HTTP_LOG_EXPORTER_AVAILABLE,
            _create_otlp_log_exporter,
        )

        if not HTTP_LOG_EXPORTER_AVAILABLE:
            with pytest.raises(
                ImportError, match="HTTP OTLP log exporter not available"
            ):
                _create_otlp_log_exporter(
                    endpoint="http://localhost:4318",
                    headers={"authorization": "Bearer test-token"},
                    protocol="http/protobuf",
                )
        else:
            exporter = _create_otlp_log_exporter(
                endpoint="http://localhost:4318",
                headers={"authorization": "Bearer test-token"},
                protocol="http/protobuf",
            )
            assert exporter is not None

    def test_create_otlp_log_exporter_invalid_protocol(self):
        """Test creating OTLP log exporter with invalid protocol raises error."""
        from kibana.observability import _create_otlp_log_exporter

        with pytest.raises(ValueError, match="Unsupported OTLP protocol for logs"):
            _create_otlp_log_exporter(
                endpoint="http://localhost:4317", headers={}, protocol="invalid"
            )

    def test_get_log_endpoint_with_existing_path(self):
        """Test _get_log_endpoint with endpoint that already has logs path."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://localhost:4318/v1/logs"
        result = _get_log_endpoint(endpoint, "http/protobuf")
        assert result == "http://localhost:4318/v1/logs"

    def test_get_log_endpoint_http_protocol(self):
        """Test _get_log_endpoint with HTTP protocol appends path."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://localhost:4318"
        result = _get_log_endpoint(endpoint, "http/protobuf")
        assert result == "http://localhost:4318/v1/logs"

        endpoint_with_slash = "http://localhost:4318/"
        result = _get_log_endpoint(endpoint_with_slash, "http/protobuf")
        assert result == "http://localhost:4318/v1/logs"

    def test_get_log_endpoint_grpc_protocol(self):
        """Test _get_log_endpoint with gRPC protocol uses same endpoint."""
        from kibana.observability import _get_log_endpoint

        endpoint = "http://localhost:4317"
        result = _get_log_endpoint(endpoint, "grpc")
        assert result == "http://localhost:4317"

    @patch("kibana.observability._create_otlp_log_exporter")
    def test_create_otlp_log_exporter_with_error_handling_success(self, mock_create):
        """Test successful OTLP log exporter creation with error handling."""
        from kibana.observability import _create_otlp_log_exporter_with_error_handling

        mock_exporter = object()
        mock_create.return_value = mock_exporter

        result = _create_otlp_log_exporter_with_error_handling(
            endpoint="http://localhost:4317", headers={}, protocol="grpc"
        )
        assert result is mock_exporter

    @patch("kibana.observability._create_otlp_log_exporter")
    def test_create_otlp_log_exporter_with_error_handling_import_error(
        self, mock_create, caplog
    ):
        """Test OTLP log exporter creation with ImportError."""
        from kibana.observability import _create_otlp_log_exporter_with_error_handling

        mock_create.side_effect = ImportError("Missing log exporter dependency")

        with caplog.at_level(
            "ERROR", logger="kibana.observability"
        ):  # Both messages are now at ERROR level
            result = _create_otlp_log_exporter_with_error_handling(
                endpoint="http://localhost:4317", headers={}, protocol="grpc"
            )

        assert result is None
        assert "Missing OpenTelemetry log exporter dependency" in caplog.text
        assert "Install log exporters with:" in caplog.text


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestLogForwardingSetup:
    """Tests for log forwarding setup functions."""

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", False)
    def test_setup_log_forwarding_logs_not_available(self, caplog):
        """Test log forwarding setup when logs not available."""
        from kibana.observability import _setup_log_forwarding

        with caplog.at_level("WARNING", logger="kibana.observability"):
            handlers = _setup_log_forwarding(
                logs_enabled=True,
                logs_level="WARNING",
                logs_loggers=["kibana"],
                exporter="otlp",
                endpoint="http://localhost:4317",
                headers={},
                protocol="grpc",
                resource=None,
            )

        assert handlers == []
        assert (
            "Log forwarding requested but OpenTelemetry logs not available"
            in caplog.text
        )

    def test_setup_log_forwarding_disabled(self):
        """Test log forwarding setup when disabled."""
        from kibana.observability import _setup_log_forwarding

        handlers = _setup_log_forwarding(
            logs_enabled=False,
            logs_level="WARNING",
            logs_loggers=["kibana"],
            exporter="otlp",
            endpoint="http://localhost:4317",
            headers={},
            protocol="grpc",
            resource=None,
        )

        assert handlers == []

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", True)
    @patch("kibana.observability.LoggerProvider")
    @patch("kibana.observability.set_logger_provider")
    @patch("kibana.observability._create_otlp_log_exporter_with_error_handling")
    @patch("kibana.observability.BatchLogRecordProcessor")
    @patch("kibana.observability.OTelLogHandler")
    @patch("logging.getLogger")
    def test_setup_log_forwarding_success(
        self,
        mock_get_logger,
        mock_handler_class,
        mock_processor_class,
        mock_create_exporter,
        mock_set_provider,
        mock_provider_class,
    ):
        """Test successful log forwarding setup."""
        from unittest.mock import Mock

        from kibana.observability import _setup_log_forwarding

        # Mock objects
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_exporter = Mock()
        mock_create_exporter.return_value = mock_exporter
        mock_processor = Mock()
        mock_processor_class.return_value = mock_processor
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        mock_logger = Mock()
        mock_logger.level = logging.NOTSET
        mock_get_logger.return_value = mock_logger

        handlers = _setup_log_forwarding(
            logs_enabled=True,
            logs_level="WARNING",
            logs_loggers=["kibana", "test"],
            exporter="otlp",
            endpoint="http://localhost:4317",
            headers={"auth": "token"},
            protocol="grpc",
            resource=Mock(),
        )

        # Verify setup calls
        mock_provider_class.assert_called_once()
        mock_create_exporter.assert_called_once_with(
            "http://localhost:4317", {"auth": "token"}, "grpc"
        )
        mock_processor_class.assert_called_once_with(mock_exporter)
        mock_provider.add_log_record_processor.assert_called_once_with(mock_processor)
        mock_set_provider.assert_called_once_with(mock_provider)

        # Verify handler creation for each logger
        assert mock_handler_class.call_count == 2
        assert mock_get_logger.call_count == 2
        mock_get_logger.assert_any_call("kibana")
        mock_get_logger.assert_any_call("test")
        assert mock_logger.addHandler.call_count == 2
        assert len(handlers) == 2

        # Verify OTelLogHandler was called with correct arguments
        handler_call_kwargs = mock_handler_class.call_args_list[0].kwargs
        assert handler_call_kwargs["level"] == logging.WARNING
        assert handler_call_kwargs["logger_provider"] is mock_provider

    def test_cleanup_log_handlers(self):
        """Test cleanup of log handlers."""
        from unittest.mock import Mock

        from kibana.observability import _cleanup_log_handlers

        # Create mock handlers and loggers
        handler1 = Mock()
        handler2 = Mock()
        mock_logger = Mock()
        mock_logger.handlers = [handler1, handler2]

        with patch("logging.Logger.manager") as mock_manager:
            mock_manager.loggerDict = {"test.logger": None}
            with patch("logging.getLogger", return_value=mock_logger):
                _cleanup_log_handlers([handler1, handler2])

        # Verify handlers were removed and closed
        assert mock_logger.removeHandler.call_count == 2
        handler1.close.assert_called_once()
        handler2.close.assert_called_once()


@pytest.mark.skipif(not OTEL_AVAILABLE, reason="OpenTelemetry not installed")
class TestLogForwardingStatus:
    """Tests for log forwarding status and diagnostics functions."""

    @patch.dict(
        "os.environ",
        {
            "KIBANA_OTEL_LOGS_ENABLED": "true",
            "KIBANA_OTEL_LOGS_LEVEL": "ERROR",
            "KIBANA_OTEL_LOGS_LOGGERS": "kibana,test",
        },
    )
    def test_get_log_forwarding_status(self):
        """Test get_log_forwarding_status function."""
        from kibana.observability import get_log_forwarding_status

        status = get_log_forwarding_status()

        assert "logs_available" in status
        assert "grpc_exporter_available" in status
        assert "http_exporter_available" in status
        assert "handlers_configured" in status
        assert "active_loggers" in status
        assert "configuration" in status

        config = status["configuration"]
        assert config["logs_enabled"] == "true"
        assert config["logs_level"] == "ERROR"
        assert config["logs_loggers"] == "kibana,test"

    def test_validate_log_forwarding_configuration_valid(self):
        """Test validate_log_forwarding_configuration with valid config."""
        from kibana.observability import validate_log_forwarding_configuration

        result = validate_log_forwarding_configuration(
            logs_enabled=True,
            logs_level="WARNING",
            logs_loggers=["kibana", "test"],
            endpoint="http://localhost:4317",
            protocol="grpc",
        )

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    @patch("kibana.observability.OTEL_LOGS_AVAILABLE", False)
    def test_validate_log_forwarding_configuration_logs_not_available(self):
        """Test validation when logs not available."""
        from kibana.observability import validate_log_forwarding_configuration

        result = validate_log_forwarding_configuration(logs_enabled=True)

        assert result["valid"] is False
        assert any(
            "OpenTelemetry logs not available" in error for error in result["errors"]
        )

    def test_validate_log_forwarding_configuration_invalid_level(self):
        """Test validation with invalid log level."""
        from kibana.observability import validate_log_forwarding_configuration

        result = validate_log_forwarding_configuration(
            logs_enabled=True, logs_level="INVALID"
        )

        assert result["valid"] is False
        assert any("Invalid log level" in error for error in result["errors"])

    def test_validate_log_forwarding_configuration_invalid_loggers(self):
        """Test validation with invalid loggers."""
        from kibana.observability import validate_log_forwarding_configuration

        result = validate_log_forwarding_configuration(
            logs_enabled=True, logs_loggers="not_a_list"
        )

        assert result["valid"] is False
        assert any("logs_loggers must be a list" in error for error in result["errors"])

    def test_validate_log_forwarding_configuration_empty_loggers(self):
        """Test validation with empty loggers list."""
        from kibana.observability import validate_log_forwarding_configuration

        result = validate_log_forwarding_configuration(
            logs_enabled=True, logs_loggers=[]
        )

        assert result["valid"] is True  # Valid but with warning
        assert any(
            "Empty logs_loggers list" in warning for warning in result["warnings"]
        )

    @patch("kibana.observability._validate_apm_connectivity")
    @patch("kibana.observability._get_log_endpoint")
    def test_validate_log_forwarding_connectivity_success(
        self, mock_get_endpoint, mock_validate
    ):
        """Test successful log forwarding connectivity test."""
        from kibana.observability import validate_log_forwarding_connectivity

        mock_get_endpoint.return_value = "http://localhost:4317/v1/logs"
        mock_validate.return_value = True

        result = validate_log_forwarding_connectivity(
            endpoint="http://localhost:4317", headers={"auth": "token"}, protocol="grpc"
        )

        assert result["success"] is True
        assert result["endpoint"] == "http://localhost:4317"
        assert result["log_endpoint"] == "http://localhost:4317/v1/logs"
        assert result["protocol"] == "grpc"
        assert result["error"] is None
        assert result["response_time"] is not None

    @patch("kibana.observability._validate_apm_connectivity")
    @patch("kibana.observability._get_log_endpoint")
    def test_validate_log_forwarding_connectivity_failure(
        self, mock_get_endpoint, mock_validate
    ):
        """Test failed log forwarding connectivity test."""
        from kibana.observability import validate_log_forwarding_connectivity

        mock_get_endpoint.return_value = "http://localhost:4317/v1/logs"
        mock_validate.return_value = False

        result = validate_log_forwarding_connectivity(
            endpoint="http://localhost:4317", protocol="grpc"
        )

        assert result["success"] is False
        assert "Could not connect to log endpoint" in result["error"]


class TestObservabilityWithoutOpenTelemetry:
    """Tests for observability when OpenTelemetry is not installed."""

    @patch("kibana.observability.OTEL_AVAILABLE", False)
    def test_configure_without_otel_logs_warning(self, caplog):
        """Test that configure logs warning when OpenTelemetry not available."""
        from kibana.observability import configure_opentelemetry

        with caplog.at_level("WARNING", logger="kibana.observability"):
            configure_opentelemetry(enabled=True)

        assert "OpenTelemetry not available" in caplog.text

    @patch("kibana.observability.OTEL_AVAILABLE", False)
    def test_create_span_without_otel_returns_none(self):
        """Test that create_span returns None when OpenTelemetry not available."""
        from kibana.observability import create_span

        span = create_span("test.span")

        assert span is None

    @patch("kibana.observability.OTEL_AVAILABLE", False)
    def test_set_span_error_without_otel_does_nothing(self):
        """Test that set_span_error does nothing when OpenTelemetry not available."""
        from kibana.observability import set_span_error

        # Should not raise
        set_span_error(None, Exception("test"))
