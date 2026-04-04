#!/usr/bin/env python3
"""
Simple example demonstrating Kibana Status API.

This example shows how to check Kibana's health status with log forwarding support.
"""

import logging

from utils import (
    configure_example_telemetry,
    create_kibana_client,
    print_config_info,
    print_telemetry_info,
    setup_telemetry_cleanup,
    should_enable_telemetry,
)

# Set up logger for this example
logger = logging.getLogger("kibana.examples.simple_status")


def main():
    """Check Kibana status."""
    # Print configuration information
    print_config_info()

    # Configure telemetry with log forwarding
    telemetry_enabled = should_enable_telemetry()
    traces_configured, logs_configured = configure_example_telemetry(
        enabled=telemetry_enabled,
        logs_enabled=telemetry_enabled,  # Enable logs when telemetry is enabled
    )
    print_telemetry_info()

    # Set up automatic telemetry cleanup
    setup_telemetry_cleanup()

    # Log example start
    logger.info(
        "Starting Kibana status check example",
        extra={
            "example": "simple_status",
            "traces_enabled": traces_configured,
            "logs_enabled": logs_configured,
        },
    )

    # Initialize Kibana client with automatic configuration
    client = create_kibana_client()

    try:
        # Get Kibana status
        print("Checking Kibana status...")
        logger.info("Requesting Kibana status", extra={"api_endpoint": "/api/status"})

        response = client.status.get_status()
        status = response.body

        # Log status information
        logger.info(
            "Kibana status retrieved successfully",
            extra={
                "kibana_name": status["name"],
                "kibana_version": status["version"]["number"],
                "status_level": status["status"]["overall"]["level"],
                "api_endpoint": "/api/status",
            },
        )

        # Display status information
        print("\n✅ Kibana Status Check")
        print(f"   Name: {status['name']}")
        print(f"   Version: {status['version']['number']}")
        print(f"   Status: {status['status']['overall']['level']}")
        print(f"   Summary: {status['status']['overall']['summary']}")

        # Check if Kibana is healthy
        if status["status"]["overall"]["level"] == "available":
            print("\n✅ Kibana is healthy and available")
            logger.info(
                "Kibana health check passed", extra={"health_status": "available"}
            )
        elif status["status"]["overall"]["level"] == "degraded":
            print("\n⚠️  Kibana is degraded but operational")
            logger.warning("Kibana is degraded", extra={"health_status": "degraded"})
        else:
            print("\n❌ Kibana is unavailable")
            logger.error(
                "Kibana is unavailable", extra={"health_status": "unavailable"}
            )

    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(
            "Failed to check Kibana status",
            extra={"error": str(e), "api_endpoint": "/api/status"},
        )
    finally:
        logger.info("Kibana status check example completed")
        client.close()


if __name__ == "__main__":
    main()
