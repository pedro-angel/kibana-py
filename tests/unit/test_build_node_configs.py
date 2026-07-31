"""Unit tests for ``_build_node_configs`` host-string parsing.

Covers issue #71: a scheme-less host string (e.g. "myhost:5601") used to
silently mis-parse via ``urlparse`` into scheme='myhost', host='localhost',
port=5601 -- routing all traffic to localhost with a bogus scheme instead of
failing fast. The fix rejects scheme-less strings with a clear ``ValueError``
naming the offending input and the expected form, rather than guessing a
default scheme.
"""

import pytest
from elastic_transport import NodeConfig

from kibana._sync.client import _build_node_configs


class TestBuildNodeConfigsSchemeLessHosts:
    """Scheme-less string hosts must raise, not silently mis-parse."""

    @pytest.mark.parametrize(
        "host",
        [
            "localhost:5601",
            "myhost:5601",
            "myhost",
        ],
    )
    def test_scheme_less_string_raises_value_error(self, host):
        with pytest.raises(ValueError) as exc_info:
            _build_node_configs(host, None)

        message = str(exc_info.value)
        # Names the offending input.
        assert host in message
        # Names the expected form.
        assert "http://host:port" in message
        assert "https://host:port" in message

    def test_scheme_less_host_in_list_raises_value_error(self):
        with pytest.raises(ValueError) as exc_info:
            _build_node_configs(["http://good:5601", "bad-host:5601"], None)

        assert "bad-host:5601" in str(exc_info.value)

    def test_scheme_less_string_does_not_default_to_localhost(self):
        """Regression guard: previously this silently produced a localhost
        NodeConfig instead of raising."""
        with pytest.raises(ValueError):
            _build_node_configs("myhost:5601", None)


class TestBuildNodeConfigsValidHostsUnchanged:
    """Valid, previously-working forms must keep working identically."""

    def test_http_host_with_port(self):
        (config,) = _build_node_configs("http://localhost:5601", None)

        assert isinstance(config, NodeConfig)
        assert config.scheme == "http"
        assert config.host == "localhost"
        assert config.port == 5601

    def test_https_host_with_port(self):
        (config,) = _build_node_configs("https://example.com:9243", None)

        assert config.scheme == "https"
        assert config.host == "example.com"
        assert config.port == 9243

    def test_http_host_without_port_defaults_to_5601(self):
        (config,) = _build_node_configs("http://myhost", None)

        assert config.scheme == "http"
        assert config.host == "myhost"
        assert config.port == 5601

    def test_https_host_without_port_defaults_to_443(self):
        (config,) = _build_node_configs("https://myhost", None)

        assert config.scheme == "https"
        assert config.host == "myhost"
        assert config.port == 443

    def test_host_with_path_prefix(self):
        (config,) = _build_node_configs("http://localhost:5601/kibana", None)

        assert config.path_prefix == "/kibana"

    def test_multiple_valid_hosts(self):
        configs = _build_node_configs(
            ["http://localhost:5601", "https://localhost:5602"], None
        )

        assert len(configs) == 2
        assert configs[0].scheme == "http"
        assert configs[1].scheme == "https"

    @pytest.mark.parametrize(
        "host, expected",
        [
            # Userinfo (user:pass@) is accepted by urlparse but silently
            # dropped: the code never reads parsed_url.username/.password,
            # so it never reaches NodeConfig. Confirmed identical on main
            # (pre-#71-fix) before asserting this here.
            (
                "https://user:pass@host:9243/prefix/",
                {
                    "scheme": "https",
                    "host": "host",
                    "port": 9243,
                    "path_prefix": "/prefix",
                },
            ),
            # IPv6 literal: urlparse().hostname unwraps the brackets.
            (
                "https://[::1]:9200",
                {
                    "scheme": "https",
                    "host": "::1",
                    "port": 9200,
                    "path_prefix": "",
                },
            ),
            # Trailing-slash path prefix: NodeConfig normalizes away the
            # trailing slash (path_prefix == "/kibana", not "/kibana/").
            (
                "http://host:5601/kibana/",
                {
                    "scheme": "http",
                    "host": "host",
                    "port": 5601,
                    "path_prefix": "/kibana",
                },
            ),
        ],
    )
    def test_edge_case_forms_match_main_behavior(self, host, expected):
        """Regression guard: these edge forms must keep parsing exactly as
        they did on main before issue #71's fix -- the fix only rejects
        scheme-less strings and must not change parsing of anything that
        already had a scheme."""
        (config,) = _build_node_configs(host, None)

        assert config.scheme == expected["scheme"]
        assert config.host == expected["host"]
        assert config.port == expected["port"]
        assert config.path_prefix == expected["path_prefix"]


class TestBuildNodeConfigsNonStringHostsUnchanged:
    """Non-string host entries (dict) are untouched by the string-only check."""

    def test_dict_host_still_builds_node_config(self):
        (config,) = _build_node_configs(
            [{"host": "localhost", "port": 5601, "scheme": "http"}], None
        )

        assert isinstance(config, NodeConfig)
        assert config.host == "localhost"
        assert config.port == 5601
        assert config.scheme == "http"

    def test_dict_host_merges_node_options(self):
        (config,) = _build_node_configs(
            [{"host": "localhost", "port": 5601, "scheme": "http"}],
            None,
            node_options={"connections_per_node": 5},
        )

        assert config.connections_per_node == 5

    def test_invalid_non_string_non_dict_host_still_raises(self):
        """Non-string, non-dict entries were already rejected; unaffected by
        this fix."""
        with pytest.raises(ValueError, match="Invalid host specification"):
            _build_node_configs([12345], None)
