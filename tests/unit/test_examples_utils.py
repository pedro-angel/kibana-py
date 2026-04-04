"""Tests for examples/utils.py configuration detection."""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Load examples/utils.py explicitly by file path so that the integration
# tests' own utils.py (tests/integration/utils.py) does not shadow it when
# the full test suite is collected together (e.g. via ``nox`` / ``make test-python-matrix``).
_examples_utils_path = str(
    Path(__file__).parent.parent.parent / "examples" / "utils.py"
)
_spec = importlib.util.spec_from_file_location("utils", _examples_utils_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
# Register in sys.modules so that ``patch("utils.xxx", ...)`` works correctly.
sys.modules["utils"] = _mod

from utils import (
    _expand_variables,
    _validate_endpoint_format,
    _validate_log_level,
    _validate_logger_names,
    _validate_otel_config,
    cleanup_telemetry,
    configure_example_telemetry,
    get_otel_config,
    load_local_env,
    print_telemetry_info,
    setup_telemetry_cleanup,
    should_enable_telemetry,
)


class TestVariableExpansion:
    """Test variable expansion functionality."""

    def test_simple_variable_expansion(self):
        """Test basic variable expansion."""
        env_vars = {"PORT": "8200", "HOST": "localhost"}

        result = _expand_variables("http://${HOST}:${PORT}", env_vars)
        assert result == "http://localhost:8200"

    def test_variable_expansion_with_default(self):
        """Test variable expansion with default values."""
        env_vars = {"HOST": "localhost"}

        result = _expand_variables("http://${HOST}:${PORT:-8200}", env_vars)
        assert result == "http://localhost:8200"

    def test_variable_expansion_missing_no_default(self):
        """Test variable expansion with missing variable and no default."""
        env_vars = {"HOST": "localhost"}

        result = _expand_variables("http://${HOST}:${PORT}", env_vars)
        assert result == "http://localhost:${PORT}"

    def test_variable_expansion_with_existing_default(self):
        """Test variable expansion where variable exists but default is provided."""
        env_vars = {"HOST": "localhost", "PORT": "9200"}

        result = _expand_variables("http://${HOST}:${PORT:-8200}", env_vars)
        assert result == "http://localhost:9200"

    def test_multiple_variable_expansion(self):
        """Test expansion of multiple variables."""
        env_vars = {"PROTO": "https", "HOST": "example.com", "PORT": "443"}

        result = _expand_variables("${PROTO}://${HOST}:${PORT}/api", env_vars)
        assert result == "https://example.com:443/api"

    def test_invalid_variable_syntax(self):
        """Test handling of invalid variable syntax."""
        env_vars = {"HOST": "localhost"}

        # Should handle gracefully and return original
        result = _expand_variables("http://${HOST:8200", env_vars)
        assert result == "http://${HOST:8200"


class TestLoadLocalEnv:
    """Test loading of local environment files."""

    def test_load_env_file_not_exists(self):
        """Test loading when .env file doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            result = load_local_env()
            assert result == {}

    def test_load_env_file_basic(self):
        """Test loading basic .env file."""
        # Test the parsing logic directly with a mock file
        env_vars = {
            "KIBANA_URL": "http://localhost:5601",
            "ES_PASSWORD": "changeme",
            "EMPTY_LINE": "",
            "OTEL_ENDPOINT": "http://localhost:8200",
        }

        # Mock file content
        file_content = [
            "# Comment line\n",
            "KIBANA_URL=http://localhost:5601\n",
            "ES_PASSWORD=changeme\n",
            "EMPTY_LINE=\n",
            "\n",
            "OTEL_ENDPOINT=http://localhost:8200\n",
        ]

        # Create a proper mock file that supports context manager
        mock_file = Mock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=None)
        mock_file.__iter__ = Mock(return_value=iter(file_content))

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", return_value=mock_file):
                result = load_local_env()

        assert result == env_vars

    def test_load_env_file_with_variable_expansion(self):
        """Test loading .env file with variable expansion."""
        # Mock file content with variable expansion
        file_content = [
            "APM_LOCAL_PORT=8200\n",
            "OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:${APM_LOCAL_PORT}\n",
            "OTEL_EXPORTER_OTLP_HEADERS=authorization=Bearer ${ELASTIC_APM_SECRET_TOKEN:-default-token}\n",
        ]

        # Create a proper mock file that supports context manager
        mock_file = Mock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=None)
        mock_file.__iter__ = Mock(return_value=iter(file_content))

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", return_value=mock_file):
                result = load_local_env()

        expected = {
            "APM_LOCAL_PORT": "8200",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:8200",
            "OTEL_EXPORTER_OTLP_HEADERS": "authorization=Bearer default-token",
        }
        assert result == expected


class TestEndpointValidation:
    """Test endpoint format validation."""

    def test_valid_http_endpoint(self):
        """Test valid HTTP endpoint."""
        assert _validate_endpoint_format("http://localhost:8200") is True

    def test_valid_https_endpoint(self):
        """Test valid HTTPS endpoint."""
        assert _validate_endpoint_format("https://apm.example.com:8200") is True

    def test_valid_grpc_endpoint(self):
        """Test valid gRPC endpoint."""
        assert _validate_endpoint_format("grpc://localhost:4317") is True

    def test_invalid_endpoint_no_scheme(self):
        """Test invalid endpoint without scheme."""
        assert _validate_endpoint_format("localhost:8200") is False

    def test_invalid_endpoint_no_host(self):
        """Test invalid endpoint without host."""
        assert _validate_endpoint_format("http://") is False

    def test_invalid_endpoint_empty(self):
        """Test invalid empty endpoint."""
        assert _validate_endpoint_format("") is False

    def test_invalid_endpoint_none(self):
        """Test invalid None endpoint."""
        assert _validate_endpoint_format(None) is False


class TestLogValidation:
    """Test log configuration validation functions."""

    def test_validate_log_level_valid(self):
        """Test validation of valid log levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            assert _validate_log_level(level) is True
            assert _validate_log_level(level.lower()) is True

    def test_validate_log_level_invalid(self):
        """Test validation of invalid log levels."""
        invalid_levels = ["TRACE", "VERBOSE", "FATAL", "INVALID", ""]
        for level in invalid_levels:
            assert _validate_log_level(level) is False

    def test_validate_logger_names_valid(self):
        """Test validation of valid logger names."""
        valid_names = [
            "kibana",
            "kibana.actions",
            "my_logger",
            "test-logger",
            "app.module.submodule",
        ]
        invalid_names = _validate_logger_names(valid_names)
        assert invalid_names == []

    def test_validate_logger_names_invalid(self):
        """Test validation of invalid logger names."""
        invalid_names = [
            "",
            "logger with spaces",
            "logger/with/slashes",
            "logger@with@symbols",
            None,
            123,
        ]
        result = _validate_logger_names(invalid_names)
        assert len(result) == len(invalid_names)

    def test_validate_logger_names_mixed(self):
        """Test validation of mixed valid and invalid logger names."""
        mixed_names = ["kibana", "", "valid.logger", "invalid name", "another.valid"]
        invalid_names = _validate_logger_names(mixed_names)
        assert len(invalid_names) == 2
        assert "" in invalid_names
        assert "invalid name" in invalid_names


class TestOtelConfigValidation:
    """Test OpenTelemetry configuration validation."""

    def test_valid_config(self):
        """Test validation of valid configuration."""
        config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
        }

        errors = _validate_otel_config(config)
        assert errors == []

    def test_valid_config_with_logs(self):
        """Test validation of valid configuration with log forwarding."""
        config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": True,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana", "kibana.examples"],
            "logs_endpoint": "http://localhost:8200/v1/logs",
            "logs_protocol": "grpc",
        }

        errors = _validate_otel_config(config)
        assert errors == []

    def test_invalid_endpoint(self):
        """Test validation with invalid endpoint."""
        config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "invalid-endpoint",
            "protocol": "grpc",
            "headers": {},
        }

        errors = _validate_otel_config(config)
        assert len(errors) == 1
        assert "Invalid OTLP endpoint format" in errors[0]

    def test_empty_service_name(self):
        """Test validation with empty service name."""
        config = {
            "enabled": True,
            "service_name": "",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
        }

        errors = _validate_otel_config(config)
        assert len(errors) == 1
        assert "Service name cannot be empty" in errors[0]

    def test_invalid_protocol(self):
        """Test validation with invalid protocol."""
        config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "invalid-protocol",
            "headers": {},
        }

        errors = _validate_otel_config(config)
        assert len(errors) == 1
        assert "Invalid protocol" in errors[0]

    def test_invalid_log_level(self):
        """Test validation with invalid log level."""
        config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": True,
            "logs_level": "INVALID",
            "logs_loggers": ["kibana"],
        }

        errors = _validate_otel_config(config)
        assert len(errors) == 1
        assert "Invalid log level" in errors[0]

    def test_invalid_logger_names(self):
        """Test validation with invalid logger names."""
        config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": True,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana", "", "invalid name"],
        }

        errors = _validate_otel_config(config)
        assert len(errors) == 1
        assert "Invalid logger names" in errors[0]

    def test_invalid_logs_endpoint(self):
        """Test validation with invalid logs endpoint."""
        config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": True,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
            "logs_endpoint": "invalid-endpoint",
        }

        errors = _validate_otel_config(config)
        assert len(errors) == 1
        assert "Invalid logs endpoint format" in errors[0]

    def test_invalid_logs_protocol(self):
        """Test validation with invalid logs protocol."""
        config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": True,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
            "logs_protocol": "invalid-protocol",
        }

        errors = _validate_otel_config(config)
        assert len(errors) == 1
        assert "Invalid logs protocol" in errors[0]

    def test_multiple_validation_errors(self):
        """Test validation with multiple errors."""
        config = {
            "enabled": True,
            "service_name": "",
            "endpoint": "invalid-endpoint",
            "protocol": "invalid-protocol",
            "headers": {},
        }

        errors = _validate_otel_config(config)
        assert len(errors) == 3

    def test_multiple_log_validation_errors(self):
        """Test validation with multiple log-related errors."""
        config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": True,
            "logs_level": "INVALID",
            "logs_loggers": ["", "invalid name"],
            "logs_endpoint": "invalid-endpoint",
            "logs_protocol": "invalid-protocol",
        }

        errors = _validate_otel_config(config)
        assert len(errors) == 4


class TestGetOtelConfig:
    """Test OpenTelemetry configuration detection."""

    def test_default_config(self):
        """Test default configuration when no environment variables are set."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("utils.load_local_env", return_value={}):
                config = get_otel_config()

                assert config["enabled"] is False
                assert config["service_name"] == "kibana-py-example"
                assert config["endpoint"] == "http://localhost:8200"
                assert config["protocol"] == "grpc"
                assert config["headers"] == {}
                # Test log forwarding defaults
                assert config["logs_enabled"] is False
                assert config["logs_loggers"] == ["kibana", "kibana.examples"]
                assert config["logs_endpoint"] is None
                assert config["logs_protocol"] is None

    def test_environment_variable_precedence(self):
        """Test that environment variables take precedence over .env file."""
        env_vars = {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_SERVICE_NAME": "env-service",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://env-host:9200",
        }

        local_env = {
            "KIBANA_OTEL_ENABLED": "false",
            "OTEL_SERVICE_NAME": "local-service",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://local-host:8200",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with patch("utils.load_local_env", return_value=local_env):
                config = get_otel_config()

                assert config["enabled"] is True
                assert config["service_name"] == "env-service"
                assert config["endpoint"] == "http://env-host:9200"

    def test_local_env_fallback(self):
        """Test fallback to local .env file when environment variables not set."""
        local_env = {
            "KIBANA_OTEL_ENABLED": "true",
            "OTEL_SERVICE_NAME": "local-service",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://local-host:8200",
            "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        }

        with patch.dict(os.environ, {}, clear=True):
            with patch("utils.load_local_env", return_value=local_env):
                config = get_otel_config()

                assert config["enabled"] is True
                assert config["service_name"] == "local-service"
                assert config["endpoint"] == "http://local-host:8200"
                assert config["protocol"] == "http/protobuf"

    def test_headers_parsing(self):
        """Test parsing of OTLP headers."""
        env_vars = {
            "OTEL_EXPORTER_OTLP_HEADERS": "authorization=Bearer token123,x-custom=value"
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with patch("utils.load_local_env", return_value={}):
                config = get_otel_config()

                expected_headers = {
                    "authorization": "Bearer token123",
                    "x-custom": "value",
                }
                assert config["headers"] == expected_headers

    def test_apm_token_fallback(self):
        """Test fallback to APM token for authorization header."""
        local_env = {"ELASTIC_APM_SECRET_TOKEN": "secret-token-123"}

        with patch.dict(os.environ, {}, clear=True):
            with patch("utils.load_local_env", return_value=local_env):
                config = get_otel_config()

                expected_headers = {"authorization": "Bearer secret-token-123"}
                assert config["headers"] == expected_headers

    def test_headers_variable_expansion(self):
        """Test variable expansion in headers."""
        env_vars = {
            "OTEL_EXPORTER_OTLP_HEADERS": "authorization=Bearer ${ELASTIC_APM_SECRET_TOKEN}"
        }

        local_env = {"ELASTIC_APM_SECRET_TOKEN": "expanded-token"}

        with patch.dict(os.environ, env_vars, clear=True):
            with patch("utils.load_local_env", return_value=local_env):
                config = get_otel_config()

                expected_headers = {"authorization": "Bearer expanded-token"}
                assert config["headers"] == expected_headers

    def test_log_forwarding_configuration(self):
        """Test log forwarding configuration parsing."""
        env_vars = {
            "KIBANA_OTEL_LOGS_ENABLED": "true",
            "KIBANA_OTEL_LOGS_LEVEL": "ERROR",
            "KIBANA_OTEL_LOGS_LOGGERS": "app,app.module,custom.logger",
            "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": "http://localhost:8200/v1/logs",
            "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "http/protobuf",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with patch("utils.load_local_env", return_value={}):
                config = get_otel_config()

                assert config["logs_enabled"] is True
                assert config["logs_level"] == "ERROR"
                assert config["logs_loggers"] == ["app", "app.module", "custom.logger"]
                assert config["logs_endpoint"] == "http://localhost:8200/v1/logs"
                assert config["logs_protocol"] == "http/protobuf"

    def test_log_forwarding_local_env_fallback(self):
        """Test log forwarding configuration fallback to local .env file."""
        local_env = {
            "KIBANA_OTEL_LOGS_ENABLED": "true",
            "KIBANA_OTEL_LOGS_LEVEL": "INFO",
            "KIBANA_OTEL_LOGS_LOGGERS": "local.logger",
        }

        with patch.dict(os.environ, {}, clear=True):
            with patch("utils.load_local_env", return_value=local_env):
                config = get_otel_config()

                assert config["logs_enabled"] is True
                assert config["logs_level"] == "INFO"
                assert config["logs_loggers"] == ["local.logger"]

    def test_log_forwarding_environment_precedence(self):
        """Test that environment variables take precedence over .env file for log settings."""
        env_vars = {
            "KIBANA_OTEL_LOGS_ENABLED": "true",
            "KIBANA_OTEL_LOGS_LEVEL": "ERROR",
        }

        local_env = {
            "KIBANA_OTEL_LOGS_ENABLED": "false",
            "KIBANA_OTEL_LOGS_LEVEL": "DEBUG",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with patch("utils.load_local_env", return_value=local_env):
                config = get_otel_config()

                assert config["logs_enabled"] is True  # From env var
                assert config["logs_level"] == "ERROR"  # From env var

    def test_log_loggers_parsing(self):
        """Test parsing of comma-separated logger names."""
        test_cases = [
            ("kibana,kibana.examples", ["kibana", "kibana.examples"]),
            ("single", ["single"]),
            ("  spaced  ,  names  ", ["spaced", "names"]),
            ("", []),
            ("one,,three", ["one", "three"]),  # Empty entries filtered out
        ]

        for input_str, expected in test_cases:
            env_vars = {"KIBANA_OTEL_LOGS_LOGGERS": input_str}

            with patch.dict(os.environ, env_vars, clear=True):
                with patch("utils.load_local_env", return_value={}):
                    config = get_otel_config()
                    assert config["logs_loggers"] == expected


class TestShouldEnableTelemetry:
    """Test telemetry enable/disable logic."""

    def test_enabled_true(self):
        """Test when telemetry is explicitly enabled."""
        with patch("utils.get_otel_config", return_value={"enabled": True}):
            assert should_enable_telemetry() is True

    def test_enabled_false(self):
        """Test when telemetry is explicitly disabled."""
        with patch("utils.get_otel_config", return_value={"enabled": False}):
            assert should_enable_telemetry() is False

    def test_various_true_values(self):
        """Test various string values that should be interpreted as True."""
        true_values = ["true", "True", "TRUE", "1", "yes", "Yes", "on", "On"]

        for value in true_values:
            with patch.dict(os.environ, {"KIBANA_OTEL_ENABLED": value}, clear=True):
                with patch("utils.load_local_env", return_value={}):
                    config = get_otel_config()
                    assert config["enabled"] is True, f"Value '{value}' should be True"

    def test_various_false_values(self):
        """Test various string values that should be interpreted as False."""
        false_values = ["false", "False", "FALSE", "0", "no", "No", "off", "Off", ""]

        for value in false_values:
            with patch.dict(os.environ, {"KIBANA_OTEL_ENABLED": value}, clear=True):
                with patch("utils.load_local_env", return_value={}):
                    config = get_otel_config()
                    assert (
                        config["enabled"] is False
                    ), f"Value '{value}' should be False"


class TestConfigureExampleTelemetry:
    """Test configure_example_telemetry() function."""

    def test_configure_telemetry_disabled(self):
        """Test configuration when telemetry is disabled."""

        mock_config = {
            "enabled": False,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": False,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            traces_configured, logs_configured = configure_example_telemetry()
            assert traces_configured is False
            assert logs_configured is False

    def test_configure_telemetry_enabled_override(self):
        """Test configuration with enabled override."""

        mock_config = {
            "enabled": False,  # Will be overridden
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": False,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("utils._validate_otel_config", return_value=[]):
                with patch("utils._test_apm_connectivity", return_value=True):
                    with patch(
                        "kibana.observability.configure_opentelemetry"
                    ) as mock_configure:
                        traces_configured, logs_configured = (
                            configure_example_telemetry(enabled=True)
                        )
                        assert traces_configured is True
                        assert logs_configured is False
                        mock_configure.assert_called_once()

    def test_configure_telemetry_validation_errors(self):
        """Test configuration with validation errors."""

        mock_config = {
            "enabled": True,
            "service_name": "",  # Invalid
            "endpoint": "invalid-endpoint",  # Invalid
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": False,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch(
                "utils._validate_otel_config",
                return_value=["Service name cannot be empty"],
            ):
                traces_configured, logs_configured = configure_example_telemetry()
                assert traces_configured is False
                assert logs_configured is False

    def test_configure_telemetry_import_error(self):
        """Test configuration when OpenTelemetry is not available."""

        mock_config = {"enabled": True}

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'kibana.observability'"),
            ):
                traces_configured, logs_configured = configure_example_telemetry()
                assert traces_configured is False
                assert logs_configured is False

    def test_configure_telemetry_configuration_error(self):
        """Test configuration when OpenTelemetry configuration fails."""

        mock_config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": False,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("utils._validate_otel_config", return_value=[]):
                with patch("utils._test_apm_connectivity", return_value=True):
                    with patch(
                        "kibana.observability.configure_opentelemetry",
                        side_effect=Exception("Config failed"),
                    ):
                        traces_configured, logs_configured = (
                            configure_example_telemetry()
                        )
                        assert traces_configured is False
                        assert logs_configured is False

    def test_configure_telemetry_with_logs_enabled(self):
        """Test configuration with log forwarding enabled."""

        mock_config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": True,
            "logs_level": "ERROR",
            "logs_loggers": ["kibana", "app"],
            "logs_endpoint": "http://localhost:8200/v1/logs",
            "logs_protocol": "http/protobuf",
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("utils._validate_otel_config", return_value=[]):
                with patch("utils._test_apm_connectivity", return_value=True):
                    with patch(
                        "kibana.observability.configure_opentelemetry"
                    ) as mock_configure:
                        traces_configured, logs_configured = (
                            configure_example_telemetry()
                        )
                        assert traces_configured is True
                        assert logs_configured is True

                        # Verify configure_opentelemetry was called with log parameters
                        mock_configure.assert_called_once()
                        call_args = mock_configure.call_args
                        assert call_args.kwargs["logs_enabled"] is True
                        assert call_args.kwargs["logs_level"] == "ERROR"
                        assert call_args.kwargs["logs_loggers"] == ["kibana", "app"]
                        assert (
                            call_args.kwargs["logs_endpoint"]
                            == "http://localhost:8200/v1/logs"
                        )
                        assert call_args.kwargs["logs_protocol"] == "http/protobuf"

    def test_configure_telemetry_logs_override(self):
        """Test configuration with logs_enabled override."""

        mock_config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": False,  # Will be overridden
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
            "logs_endpoint": None,
            "logs_protocol": None,
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("utils._validate_otel_config", return_value=[]):
                with patch("utils._test_apm_connectivity", return_value=True):
                    with patch(
                        "kibana.observability.configure_opentelemetry"
                    ) as mock_configure:
                        traces_configured, logs_configured = (
                            configure_example_telemetry(logs_enabled=True)
                        )
                        assert traces_configured is True
                        assert logs_configured is True

                        # Verify configure_opentelemetry was called with overridden log parameters
                        mock_configure.assert_called_once()
                        call_args = mock_configure.call_args
                        assert call_args.kwargs["logs_enabled"] is True


class TestPrintTelemetryInfo:
    """Test print_telemetry_info() function."""

    def test_print_telemetry_info_basic(self, capsys):
        """Test basic telemetry info printing."""

        mock_config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": False,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
            "logs_endpoint": None,
            "logs_protocol": None,
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("pathlib.Path.exists", return_value=True):
                print_telemetry_info()

        captured = capsys.readouterr()
        assert "Telemetry Configuration" in captured.out
        assert "Traces Enabled: True" in captured.out
        assert "Service Name: test-service" in captured.out
        assert "OTLP Endpoint: http://localhost:8200" in captured.out
        assert "Protocol: grpc" in captured.out
        assert "Log Forwarding Enabled: False" in captured.out
        assert "Headers: None" in captured.out

    def test_print_telemetry_info_with_headers(self, capsys):
        """Test telemetry info printing with headers."""

        mock_config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {
                "authorization": "Bearer very-long-secret-token-12345",
                "x-custom": "custom-value",
            },
            "logs_enabled": False,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
            "logs_endpoint": None,
            "logs_protocol": None,
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("pathlib.Path.exists", return_value=False):
                print_telemetry_info()

        captured = capsys.readouterr()
        assert "Headers:" in captured.out
        assert "authorization: Bearer ver...2345" in captured.out  # Masked token
        assert "x-custom: custom-value" in captured.out  # Non-sensitive header
        assert "Local .env file not found" in captured.out

    def test_print_telemetry_info_short_token(self, capsys):
        """Test telemetry info printing with short token."""

        mock_config = {
            "enabled": False,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "http/protobuf",
            "headers": {"authorization": "Bearer short"},
            "logs_enabled": False,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
            "logs_endpoint": None,
            "logs_protocol": None,
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("pathlib.Path.exists", return_value=True):
                print_telemetry_info()

        captured = capsys.readouterr()
        assert "Traces Enabled: False" in captured.out
        assert "Protocol: http/protobuf" in captured.out
        assert "authorization: ***" in captured.out  # Short token masked completely

    def test_print_telemetry_info_with_logs_enabled(self, capsys):
        """Test telemetry info printing with log forwarding enabled."""

        mock_config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": True,
            "logs_level": "ERROR",
            "logs_loggers": ["kibana", "app.module"],
            "logs_endpoint": "http://localhost:8200/v1/logs",
            "logs_protocol": "http/protobuf",
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("pathlib.Path.exists", return_value=True):
                print_telemetry_info()

        captured = capsys.readouterr()
        assert "Log Forwarding Enabled: True" in captured.out
        assert "Log Level: ERROR" in captured.out
        assert "Log Loggers: kibana, app.module" in captured.out
        assert "Logs Endpoint: http://localhost:8200/v1/logs" in captured.out
        assert "Logs Protocol: http/protobuf" in captured.out

    def test_print_telemetry_info_logs_inherit_settings(self, capsys):
        """Test telemetry info printing when logs inherit trace settings."""

        mock_config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": True,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
            "logs_endpoint": None,  # Inherits from traces
            "logs_protocol": None,  # Inherits from traces
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("pathlib.Path.exists", return_value=True):
                print_telemetry_info()

        captured = capsys.readouterr()
        assert "Log Forwarding Enabled: True" in captured.out
        assert "Log Level: WARNING" in captured.out
        assert "Log Loggers: kibana" in captured.out
        assert "Logs Endpoint: (inherits from traces)" in captured.out
        assert "Logs Protocol: (inherits from traces)" in captured.out


class TestTelemetryCleanup:
    """Test telemetry cleanup functions."""

    def test_cleanup_telemetry_success(self):
        """Test successful telemetry cleanup."""

        # Mock tracer provider with shutdown method
        mock_tracer_provider = Mock()
        mock_tracer_provider.shutdown = Mock()

        with patch(
            "opentelemetry.trace.get_tracer_provider", return_value=mock_tracer_provider
        ):
            cleanup_telemetry()
            mock_tracer_provider.shutdown.assert_called_once()

    def test_cleanup_telemetry_no_shutdown_method(self):
        """Test cleanup when tracer provider has no shutdown method."""

        # Mock tracer provider without shutdown method
        mock_tracer_provider = Mock(spec=[])  # No shutdown method

        with patch(
            "opentelemetry.trace.get_tracer_provider", return_value=mock_tracer_provider
        ):
            # Should not raise an exception
            cleanup_telemetry()

    def test_cleanup_telemetry_import_error(self):
        """Test cleanup when OpenTelemetry is not available."""

        with patch(
            "builtins.__import__",
            side_effect=ImportError("No module named 'opentelemetry'"),
        ):
            # Should not raise an exception
            cleanup_telemetry()

    def test_cleanup_telemetry_exception(self):
        """Test cleanup when shutdown raises an exception."""

        mock_tracer_provider = Mock()
        mock_tracer_provider.shutdown = Mock(side_effect=Exception("Shutdown failed"))

        with patch(
            "opentelemetry.trace.get_tracer_provider", return_value=mock_tracer_provider
        ):
            # Should not raise an exception
            cleanup_telemetry()

    def test_setup_telemetry_cleanup(self):
        """Test setup of telemetry cleanup."""

        with patch("atexit.register") as mock_register:
            setup_telemetry_cleanup()
            mock_register.assert_called_once()
            # Verify the cleanup function was registered
            args, kwargs = mock_register.call_args
            assert len(args) == 1
            assert callable(args[0])  # Should be the cleanup_telemetry function


class TestStructuredLoggingExamples:
    """Test structured logging example functions."""

    def test_demonstrate_structured_logging(self, capsys):
        """Test structured logging demonstration."""
        from utils import demonstrate_structured_logging

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            demonstrate_structured_logging()

            # Verify logger was obtained
            mock_get_logger.assert_called_with("kibana.examples.demo")

            # Verify log messages were called with structured data
            assert mock_logger.info.call_count >= 2
            assert mock_logger.error.call_count >= 1
            assert mock_logger.warning.call_count >= 1

            # Check that extra parameters were used
            for call in mock_logger.info.call_args_list:
                args, kwargs = call
                assert "extra" in kwargs
                assert isinstance(kwargs["extra"], dict)

        # Check console output
        captured = capsys.readouterr()
        assert "Structured Logging Examples" in captured.out
        assert "Structured logging examples completed" in captured.out

    def test_demonstrate_log_trace_correlation_no_otel(self, capsys):
        """Test log-trace correlation when OpenTelemetry is not available."""
        from utils import demonstrate_log_trace_correlation

        with patch(
            "builtins.__import__",
            side_effect=ImportError("No module named 'kibana.observability'"),
        ):
            demonstrate_log_trace_correlation()

        captured = capsys.readouterr()
        assert "OpenTelemetry not available" in captured.out

    def test_demonstrate_log_trace_correlation_with_span(self, capsys):
        """Test log-trace correlation with span creation."""
        from utils import demonstrate_log_trace_correlation

        mock_span = Mock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)

        with patch("kibana.observability.span_context", return_value=mock_span):
            with patch("logging.getLogger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                with patch("time.sleep"):  # Speed up the test
                    demonstrate_log_trace_correlation()

                # Verify span was used as context manager
                mock_span.__enter__.assert_called_once()
                mock_span.__exit__.assert_called_once()

                # Verify logging occurred within span
                assert mock_logger.info.call_count >= 3

        captured = capsys.readouterr()
        assert "Log-Trace Correlation Example" in captured.out
        assert "Log-trace correlation example completed" in captured.out

    def test_demonstrate_log_trace_correlation_no_span(self, capsys):
        """Test log-trace correlation when span creation fails."""
        from utils import demonstrate_log_trace_correlation

        with patch("kibana.observability._tracing.create_span", return_value=None):
            demonstrate_log_trace_correlation()

        captured = capsys.readouterr()
        assert "Could not create span" in captured.out

    def test_demonstrate_log_level_filtering(self, capsys):
        """Test log level filtering demonstration."""
        from utils import demonstrate_log_level_filtering

        mock_config = {"logs_level": "WARNING"}

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("logging.getLogger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                demonstrate_log_level_filtering()

                # Verify all log levels were demonstrated
                mock_logger.debug.assert_called_once()
                mock_logger.info.assert_called_once()
                mock_logger.warning.assert_called_once()
                mock_logger.error.assert_called_once()
                mock_logger.critical.assert_called_once()

        captured = capsys.readouterr()
        assert "Log Level Filtering Example" in captured.out
        assert "Current log forwarding level: WARNING" in captured.out

    def test_demonstrate_logger_selection(self, capsys):
        """Test logger selection demonstration."""
        from utils import demonstrate_logger_selection

        mock_config = {"logs_loggers": ["kibana", "kibana.examples"]}

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("logging.getLogger") as mock_get_logger:
                mock_logger = Mock()
                mock_get_logger.return_value = mock_logger

                demonstrate_logger_selection()

                # Verify multiple loggers were tested
                assert mock_get_logger.call_count >= 6
                assert mock_logger.info.call_count >= 6

        captured = capsys.readouterr()
        assert "Logger Selection Example" in captured.out
        assert (
            "Configured loggers for forwarding: kibana, kibana.examples" in captured.out
        )

    def test_run_structured_logging_examples_enabled(self, capsys):
        """Test running all structured logging examples with log forwarding enabled."""
        from utils import run_structured_logging_examples

        mock_config = {
            "logs_enabled": True,
            "endpoint": "http://localhost:8200",
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("utils.demonstrate_structured_logging"):
                with patch("utils.demonstrate_log_level_filtering"):
                    with patch("utils.demonstrate_logger_selection"):
                        with patch("utils.demonstrate_log_trace_correlation"):
                            run_structured_logging_examples()

        captured = capsys.readouterr()
        assert "Log forwarding is ENABLED" in captured.out
        assert "OTLP Endpoint: http://localhost:8200" in captured.out
        assert "All structured logging examples completed!" in captured.out

    def test_run_structured_logging_examples_disabled(self, capsys):
        """Test running all structured logging examples with log forwarding disabled."""
        from utils import run_structured_logging_examples

        mock_config = {
            "logs_enabled": False,
            "endpoint": "http://localhost:8200",
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("utils.demonstrate_structured_logging"):
                with patch("utils.demonstrate_log_level_filtering"):
                    with patch("utils.demonstrate_logger_selection"):
                        with patch("utils.demonstrate_log_trace_correlation"):
                            run_structured_logging_examples()

        captured = capsys.readouterr()
        assert "Log forwarding is DISABLED" in captured.out
        assert "Set KIBANA_OTEL_LOGS_ENABLED=true" in captured.out


class TestEnhancedTelemetryConfiguration:
    """Test enhanced telemetry configuration with log forwarding."""

    def test_configure_example_telemetry_return_tuple_on_import_error(self):
        """Test that configure_example_telemetry returns tuple on ImportError."""

        with patch(
            "builtins.__import__",
            side_effect=ImportError("No module named 'kibana.observability'"),
        ):
            result = configure_example_telemetry()
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert result == (False, False)

    def test_configure_example_telemetry_logs_enabled_override(self):
        """Test configure_example_telemetry with logs_enabled override."""

        mock_config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": False,  # Will be overridden
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
            "logs_endpoint": None,
            "logs_protocol": None,
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("utils._validate_otel_config", return_value=[]):
                with patch("utils._test_apm_connectivity", return_value=True):
                    with patch(
                        "kibana.observability.configure_opentelemetry"
                    ) as mock_configure:
                        traces_configured, logs_configured = (
                            configure_example_telemetry(logs_enabled=True)
                        )

                        assert traces_configured is True
                        assert logs_configured is True

                        # Verify configure_opentelemetry was called with log parameters
                        mock_configure.assert_called_once()
                        call_args = mock_configure.call_args
                        assert call_args.kwargs["logs_enabled"] is True

    def test_configure_example_telemetry_logs_disabled_by_config(self):
        """Test configure_example_telemetry with logs disabled in config."""

        mock_config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": False,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
            "logs_endpoint": None,
            "logs_protocol": None,
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("utils._validate_otel_config", return_value=[]):
                with patch("utils._test_apm_connectivity", return_value=True):
                    with patch(
                        "kibana.observability.configure_opentelemetry"
                    ) as mock_configure:
                        traces_configured, logs_configured = (
                            configure_example_telemetry()
                        )

                        assert traces_configured is True
                        assert logs_configured is False

                        # Verify configure_opentelemetry was called without log parameters
                        mock_configure.assert_called_once()
                        call_args = mock_configure.call_args
                        assert "logs_enabled" not in call_args.kwargs

    def test_configure_example_telemetry_with_log_endpoint_and_protocol(self):
        """Test configure_example_telemetry with log-specific endpoint and protocol."""

        mock_config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": True,
            "logs_level": "ERROR",
            "logs_loggers": ["kibana", "app"],
            "logs_endpoint": "http://localhost:8200/v1/logs",
            "logs_protocol": "http/protobuf",
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("utils._validate_otel_config", return_value=[]):
                with patch("utils._test_apm_connectivity", return_value=True):
                    with patch(
                        "kibana.observability.configure_opentelemetry"
                    ) as mock_configure:
                        traces_configured, logs_configured = (
                            configure_example_telemetry()
                        )

                        assert traces_configured is True
                        assert logs_configured is True

                        # Verify configure_opentelemetry was called with log-specific parameters
                        mock_configure.assert_called_once()
                        call_args = mock_configure.call_args
                        assert call_args.kwargs["logs_enabled"] is True
                        assert call_args.kwargs["logs_level"] == "ERROR"
                        assert call_args.kwargs["logs_loggers"] == ["kibana", "app"]
                        assert (
                            call_args.kwargs["logs_endpoint"]
                            == "http://localhost:8200/v1/logs"
                        )
                        assert call_args.kwargs["logs_protocol"] == "http/protobuf"

    def test_configure_example_telemetry_graceful_error_handling(self):
        """Test configure_example_telemetry handles configuration errors gracefully."""

        mock_config = {
            "enabled": True,
            "service_name": "test-service",
            "endpoint": "http://localhost:8200",
            "protocol": "grpc",
            "headers": {},
            "logs_enabled": True,
            "logs_level": "WARNING",
            "logs_loggers": ["kibana"],
            "logs_endpoint": None,
            "logs_protocol": None,
        }

        with patch("utils.get_otel_config", return_value=mock_config):
            with patch("utils._validate_otel_config", return_value=[]):
                with patch("utils._test_apm_connectivity", return_value=True):
                    with patch(
                        "kibana.observability.configure_opentelemetry",
                        side_effect=Exception("Config failed"),
                    ):
                        traces_configured, logs_configured = (
                            configure_example_telemetry()
                        )

                        # Should return False for both on error
                        assert traces_configured is False
                        assert logs_configured is False
