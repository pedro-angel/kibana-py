#!/usr/bin/env python3
"""
Debug example showing detailed Kibana status and statistics.

This example demonstrates how to retrieve and display comprehensive
status information and operational metrics from Kibana with enhanced
log forwarding and trace correlation.
"""

import logging

from utils import (
    configure_example_telemetry,
    create_kibana_client,
    demonstrate_log_trace_correlation,
    demonstrate_structured_logging,
    print_config_info,
    print_telemetry_info,
    setup_telemetry_cleanup,
    should_enable_telemetry,
)

# Set up logger for this example
logger = logging.getLogger("kibana.examples.debug_status")


def format_bytes(bytes_value):
    """Format bytes to human-readable format."""
    if bytes_value is None:
        return "N/A"

    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB"


def format_milliseconds(ms_value):
    """Format milliseconds to human-readable format."""
    if ms_value is None:
        return "N/A"

    seconds = ms_value / 1000
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.2f}m"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.2f}h"
    days = hours / 24
    return f"{days:.2f}d"


def display_status(client):
    """Display detailed Kibana status information."""
    print("\n" + "=" * 60)
    print("KIBANA STATUS")
    print("=" * 60)

    logger.info(
        "Requesting Kibana status information",
        extra={"operation": "get_status", "api_endpoint": "/api/status"},
    )

    response = client.status.get_status()
    status = response.body

    logger.info(
        "Kibana status retrieved successfully",
        extra={
            "operation": "get_status",
            "kibana_name": status.get("name"),
            "kibana_uuid": status.get("uuid"),
            "kibana_version": status.get("version", {}).get("number"),
            "overall_status": status.get("status", {}).get("overall", {}).get("level"),
            "api_endpoint": "/api/status",
        },
    )

    # Basic information
    print("\nServer Information:")
    print(f"  Name: {status.get('name', 'N/A')}")
    print(f"  UUID: {status.get('uuid', 'N/A')}")

    # Version information
    if "version" in status:
        version = status["version"]
        print("\nVersion:")
        print(f"  Number: {version.get('number', 'N/A')}")
        print(f"  Build Hash: {version.get('build_hash', 'N/A')}")
        print(f"  Build Number: {version.get('build_number', 'N/A')}")
        print(f"  Snapshot: {version.get('build_snapshot', 'N/A')}")

    # Overall status
    if "status" in status:
        overall = status["status"].get("overall", {})
        level = overall.get("level", "unknown")
        summary = overall.get("summary", "No summary available")

        # Color code the status
        if level == "available":
            status_icon = "✅"
        elif level == "degraded":
            status_icon = "⚠️ "
        else:
            status_icon = "❌"

        print(f"\nOverall Status: {status_icon} {level.upper()}")
        print(f"  Summary: {summary}")

        # Core services status
        if "core" in status["status"]:
            print("\nCore Services:")
            for service_name, service_info in status["status"]["core"].items():
                service_level = service_info.get("level", "unknown")
                service_summary = service_info.get("summary", "No summary")

                # Log service status
                if service_level != "available":
                    logger.warning(
                        f"Core service {service_name} is not available",
                        extra={
                            "service_name": service_name,
                            "service_level": service_level,
                            "service_summary": service_summary,
                            "operation": "status_check",
                        },
                    )
                else:
                    logger.info(
                        f"Core service {service_name} is available",
                        extra={
                            "service_name": service_name,
                            "service_level": service_level,
                            "operation": "status_check",
                        },
                    )

                if service_level == "available":
                    service_icon = "✅"
                elif service_level == "degraded":
                    service_icon = "⚠️ "
                else:
                    service_icon = "❌"

                print(f"  {service_icon} {service_name}: {service_level}")
                print(f"     {service_summary}")

        # Plugins status (if available)
        if "plugins" in status["status"]:
            print("\nPlugins Status:")
            for plugin_name, plugin_info in status["status"]["plugins"].items():
                plugin_level = plugin_info.get("level", "unknown")
                print(f"  • {plugin_name}: {plugin_level}")


def display_stats(client):
    """Display detailed Kibana statistics."""
    print("\n" + "=" * 60)
    print("KIBANA STATISTICS")
    print("=" * 60)

    logger.info(
        "Requesting Kibana statistics",
        extra={"operation": "get_stats", "api_endpoint": "/api/stats"},
    )

    response = client.status.get_stats()
    stats = response.body

    # Log key statistics
    process_info = stats.get("process", {})
    memory_info = process_info.get("memory", {})
    heap_info = memory_info.get("heap", {})

    logger.info(
        "Kibana statistics retrieved successfully",
        extra={
            "operation": "get_stats",
            "heap_used_bytes": heap_info.get("used_bytes")
            or heap_info.get("used_in_bytes"),
            "heap_total_bytes": heap_info.get("total_bytes")
            or heap_info.get("total_in_bytes"),
            "uptime_millis": process_info.get("uptime_in_millis"),
            "api_endpoint": "/api/stats",
        },
    )

    # Kibana information
    if "kibana" in stats:
        kibana = stats["kibana"]
        print("\nKibana Instance:")
        print(f"  Name: {kibana.get('name', 'N/A')}")
        print(f"  UUID: {kibana.get('uuid', 'N/A')}")
        print(f"  Version: {kibana.get('version', 'N/A')}")
        print(f"  Status: {kibana.get('status', 'N/A')}")
        print(f"  Host: {kibana.get('host', 'N/A')}")
        print(f"  Transport: {kibana.get('transport_address', 'N/A')}")

    # Process information
    if "process" in stats:
        process = stats["process"]
        print("\nProcess Information:")

        # Memory
        if "memory" in process:
            memory = process["memory"]
            print("  Memory:")

            if "heap" in memory:
                heap = memory["heap"]
                heap_used = heap.get("used_bytes") or heap.get("used_in_bytes")
                heap_total = heap.get("total_bytes") or heap.get("total_in_bytes")
                heap_limit = heap.get("size_limit")

                if heap_used and heap_total:
                    heap_percent = (heap_used / heap_total) * 100
                    print(
                        f"    Heap Used: {format_bytes(heap_used)} / {format_bytes(heap_total)} ({heap_percent:.1f}%)"
                    )
                    if heap_limit:
                        print(f"    Heap Limit: {format_bytes(heap_limit)}")

            if "resident_set_size_bytes" in memory:
                rss = memory["resident_set_size_bytes"]
                print(f"    RSS: {format_bytes(rss)}")

        # Uptime (if available)
        if "uptime_in_millis" in process:
            uptime = process["uptime_in_millis"]
            print(f"  Uptime: {format_milliseconds(uptime)}")

        # Event loop metrics (if available)
        if "event_loop_delay" in process:
            print(f"  Event Loop Delay: {process['event_loop_delay']:.2f}ms")

        if "event_loop_utilization" in process:
            util = process["event_loop_utilization"]
            if "utilization" in util:
                print(f"  Event Loop Utilization: {util['utilization'] * 100:.2f}%")

    # OS information
    if "os" in stats:
        os_info = stats["os"]
        print("\nOperating System:")
        print(f"  Platform: {os_info.get('platform', 'N/A')}")
        print(f"  Release: {os_info.get('platformRelease', 'N/A')}")

        if "load" in os_info:
            load = os_info["load"]
            print("  Load Average:")
            print(f"    1m:  {load.get('1m', 'N/A')}")
            print(f"    5m:  {load.get('5m', 'N/A')}")
            print(f"    15m: {load.get('15m', 'N/A')}")

        if "memory" in os_info:
            os_memory = os_info["memory"]
            total = os_memory.get("total_in_bytes")
            free = os_memory.get("free_in_bytes")
            used = os_memory.get("used_in_bytes")

            if total and used:
                used_percent = (used / total) * 100
                print("  System Memory:")
                print(f"    Total: {format_bytes(total)}")
                print(f"    Used:  {format_bytes(used)} ({used_percent:.1f}%)")
                print(f"    Free:  {format_bytes(free)}")

    # Response times (if available)
    if "response_times" in stats:
        response_times = stats["response_times"]
        print("\nResponse Times:")
        if "avg_in_millis" in response_times:
            print(f"  Average: {response_times['avg_in_millis']}ms")
        if "max_in_millis" in response_times:
            print(f"  Maximum: {response_times['max_in_millis']}ms")

    # Request statistics (if available)
    if "requests" in stats:
        requests = stats["requests"]
        print("\nRequests:")
        if "total" in requests:
            print(f"  Total: {requests['total']}")
        if "disconnects" in requests:
            print(f"  Disconnects: {requests['disconnects']}")

    if "concurrent_connections" in stats:
        print(f"  Concurrent Connections: {stats['concurrent_connections']}")


def main():
    """Display comprehensive Kibana status and statistics."""
    # Print configuration information
    print_config_info()

    # Configure telemetry with enhanced log forwarding for debugging
    telemetry_enabled = should_enable_telemetry()
    traces_configured, logs_configured = configure_example_telemetry(
        enabled=telemetry_enabled,
        logs_enabled=telemetry_enabled,  # Enable logs when telemetry is enabled
    )
    print_telemetry_info()

    # Set up automatic telemetry cleanup
    setup_telemetry_cleanup()

    # Log example start with detailed context
    logger.info(
        "Starting debug status example",
        extra={
            "example": "debug_status",
            "traces_enabled": traces_configured,
            "logs_enabled": logs_configured,
            "log_level": "DEBUG" if logs_configured else "N/A",
        },
    )

    # Demonstrate structured logging capabilities
    if logs_configured:
        print("\n" + "=" * 60)
        print("LOG FORWARDING DEMONSTRATIONS")
        print("=" * 60)

        demonstrate_structured_logging()
        demonstrate_log_trace_correlation()

    # Initialize Kibana client with automatic configuration
    client = create_kibana_client()

    try:
        # Create a span for the entire status check operation
        try:
            from kibana.observability import create_span

            with create_span(
                "kibana_debug_status_check",
                attributes={
                    "operation.type": "debug",
                    "operation.name": "status_and_stats_check",
                    "service.component": "debug_example",
                },
            ) as span:
                logger.info(
                    "Starting comprehensive status check within trace span",
                    extra={
                        "operation": "status_check_start",
                        "span_active": span is not None,
                    },
                )

                # Display status
                display_status(client)

                # Display statistics
                display_stats(client)

                logger.info(
                    "Completed comprehensive status check",
                    extra={"operation": "status_check_complete", "status": "success"},
                )
        except ImportError:
            # OpenTelemetry not available, continue without spans
            logger.info("OpenTelemetry not available, continuing without trace spans")

            # Display status
            display_status(client)

            # Display statistics
            display_stats(client)

        print("\n" + "=" * 60)
        print("✅ Status and statistics retrieved successfully")
        print("=" * 60)

        if logs_configured:
            print("📊 Check your APM server for detailed logs and trace correlation")
            print(
                "🔗 Logs should include trace IDs for correlation with this operation"
            )

    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(
            "Debug status example failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "example": "debug_status",
            },
        )
        import traceback

        traceback.print_exc()
    finally:
        logger.info("Debug status example completed")
        client.close()


if __name__ == "__main__":
    main()
