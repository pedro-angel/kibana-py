#!/usr/bin/env python3
"""
Error Handling Example

This example demonstrates comprehensive error handling patterns for the Kibana
Python client. It covers:

1. Handling specific HTTP status code exceptions
2. Accessing error details and metadata
3. Retry strategies for transient errors
4. Connection and timeout errors
5. Authentication and authorization errors
6. Best practices for production error handling

Run this example:
    python examples/error_handling.py
"""

import time

from utils import create_kibana_client, print_config_info

from kibana.exceptions import (
    ApiError,
    AuthenticationException,
    AuthorizationException,
    BadRequestError,
    ConflictError,
    ConnectionError,
    ConnectionTimeout,
    KibanaException,
    NotFoundError,
)


def example_not_found_error(client):
    """Example 1: Handling NotFoundError (404)."""
    print("\n=== Example 1: NotFoundError (404) ===")

    try:
        # Try to get a non-existent connector
        response = client.actions.get(id="non-existent-connector-id")
        print(f"Connector found: {response.body}")
    except NotFoundError as e:
        print("✓ Caught NotFoundError as expected")
        print(f"  Message: {e.message}")
        print(f"  Status Code: {e.status_code}")
        print(f"  Response Body: {e.body}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def example_conflict_error(client):
    """Example 2: Handling ConflictError (409)."""
    print("\n=== Example 2: ConflictError (409) ===")

    connector_id = None

    try:
        # Create a connector with a specific ID
        response = client.actions.create(
            name="Conflict Test Connector",
            connector_type_id=".server-log",
            config={},
        )
        connector_id = response.body["id"]
        print(f"✓ Created connector: {connector_id}")

        # Try to create another connector with the same configuration
        # (This may or may not cause a conflict depending on Kibana version)
        response = client.actions.create(
            name="Conflict Test Connector",
            connector_type_id=".server-log",
            config={},
        )
        print(f"✓ Created second connector: {response.body['id']}")

    except ConflictError as e:
        print("✓ Caught ConflictError as expected")
        print(f"  Message: {e.message}")
        print(f"  Status Code: {e.status_code}")
    except Exception as e:
        print(f"Note: {type(e).__name__}: {e}")
    finally:
        # Cleanup
        if connector_id:
            try:
                client.actions.delete(id=connector_id)
                print(f"✓ Cleaned up connector: {connector_id}")
            except Exception:
                pass


def example_bad_request_error(client):
    """Example 3: Handling BadRequestError (400)."""
    print("\n=== Example 3: BadRequestError (400) ===")

    try:
        # Try to create a connector with invalid configuration
        response = client.actions.create(
            name="Invalid Connector",
            connector_type_id=".index",
            config={
                # Missing required 'index' field
                "refresh": True,
            },
        )
        print(f"Connector created: {response.body}")
    except BadRequestError as e:
        print("✓ Caught BadRequestError as expected")
        print(f"  Message: {e.message}")
        print(f"  Status Code: {e.status_code}")
        print(f"  Response Body: {e.body}")
    except Exception as e:
        print(f"Note: {type(e).__name__}: {e}")


def example_authentication_error():
    """Example 4: Handling AuthenticationException (401)."""
    print("\n=== Example 4: AuthenticationException (401) ===")

    from kibana import Kibana

    try:
        # Try to connect with invalid credentials
        client = Kibana(
            "http://localhost:5601", basic_auth=("invalid_user", "invalid_password")
        )

        # Try to make a request
        response = client.actions.list_types()
        print(f"Types: {len(response.body)}")
        client.close()
    except AuthenticationException as e:
        print("✓ Caught AuthenticationException as expected")
        print(f"  Message: {e.message}")
        print(f"  Status Code: {e.status_code}")
    except Exception as e:
        print(f"Note: {type(e).__name__}: {e}")


def example_authorization_error():
    """Example 5: Handling AuthorizationException (403)."""
    print("\n=== Example 5: AuthorizationException (403) ===")

    # Note: This example requires a user with limited permissions
    print("Note: This example requires a user with limited permissions")
    print("      Skipping demonstration (would require specific setup)")


def example_generic_api_error(client):
    """Example 6: Handling generic ApiError."""
    print("\n=== Example 6: Generic ApiError ===")

    try:
        # Try an operation that might fail
        response = client.actions.get(id="test-error-handling")
        print(f"Response: {response.body}")
    except ApiError as e:
        # ApiError is the base class for all API errors
        print("✓ Caught ApiError")
        print(f"  Error Type: {type(e).__name__}")
        print(f"  Message: {e.message}")
        print(f"  Status Code: {e.status_code}")
        print(f"  HTTP Version: {e.meta.http_version}")

        # Access response metadata
        print(f"  Response Headers: {dict(e.meta.headers)}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def example_connection_error():
    """Example 7: Handling ConnectionError."""
    print("\n=== Example 7: ConnectionError ===")

    from kibana import Kibana

    try:
        # Try to connect to a non-existent host
        client = Kibana("http://non-existent-host:5601")
        response = client.actions.list_types()
        print(f"Types: {len(response.body)}")
        client.close()
    except ConnectionError as e:
        print("✓ Caught ConnectionError as expected")
        print(f"  Message: {e}")
    except Exception as e:
        print(f"Note: {type(e).__name__}: {e}")


def example_timeout_error():
    """Example 8: Handling ConnectionTimeout."""
    print("\n=== Example 8: ConnectionTimeout ===")

    from kibana import Kibana

    try:
        # Create client with very short timeout
        client = Kibana("http://localhost:5601", request_timeout=0.001)

        # This should timeout
        response = client.actions.list_types()
        print(f"Types: {len(response.body)}")
        client.close()
    except ConnectionTimeout as e:
        print("✓ Caught ConnectionTimeout as expected")
        print(f"  Message: {e}")
    except Exception as e:
        print(f"Note: {type(e).__name__}: {e}")


def example_retry_strategy(client):
    """Example 9: Implementing retry strategy."""
    print("\n=== Example 9: Retry Strategy ===")

    max_retries = 3
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1}/{max_retries}...")

            # Try to get a connector
            response = client.actions.get(id="test-retry")
            print(f"✓ Success: {response.body}")
            break

        except NotFoundError as e:
            print(f"  NotFoundError: {e.message}")
            break  # Don't retry for 404

        except (ConnectionError, ConnectionTimeout) as e:
            print(f"  Connection error: {e}")
            if attempt < max_retries - 1:
                print(f"  Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print("  Max retries reached")
                raise

        except ApiError as e:
            # Retry on 5xx errors
            if e.status_code >= 500:
                print(f"  Server error ({e.status_code}): {e.message}")
                if attempt < max_retries - 1:
                    print(f"  Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print("  Max retries reached")
                    raise
            else:
                # Don't retry on 4xx errors
                print(f"  Client error ({e.status_code}): {e.message}")
                raise


def example_exception_hierarchy():
    """Example 10: Understanding exception hierarchy."""
    print("\n=== Example 10: Exception Hierarchy ===")

    print("Exception hierarchy:")
    print("  KibanaException (base)")
    print("  ├── ApiError")
    print("  │   ├── BadRequestError (400)")
    print("  │   ├── AuthenticationException (401)")
    print("  │   ├── AuthorizationException (403)")
    print("  │   ├── NotFoundError (404)")
    print("  │   └── ConflictError (409)")
    print("  ├── TransportError")
    print("  │   ├── ConnectionError")
    print("  │   ├── ConnectionTimeout")
    print("  │   └── SSLError")
    print("  └── SerializationError")

    print("\nCatching exceptions:")
    print("  - Catch specific exceptions first (NotFoundError, BadRequestError, etc.)")
    print("  - Then catch broader exceptions (ApiError, TransportError)")
    print("  - Finally catch KibanaException for any client error")


def example_production_error_handling(client):
    """Example 11: Production-ready error handling pattern."""
    print("\n=== Example 11: Production Error Handling ===")

    import logging

    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    def safe_get_connector(connector_id):
        """
        Production-ready function to get a connector with comprehensive error handling.
        """
        try:
            response = client.actions.get(id=connector_id)
            logger.info(f"Successfully retrieved connector: {connector_id}")
            return response.body

        except NotFoundError:
            logger.warning(f"Connector not found: {connector_id}")
            return None

        except AuthenticationException as e:
            logger.error(f"Authentication failed: {e.message}")
            raise  # Re-raise authentication errors

        except AuthorizationException as e:
            logger.error(f"Authorization failed: {e.message}")
            raise  # Re-raise authorization errors

        except ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise  # Re-raise connection errors

        except ApiError as e:
            logger.error(
                f"API error: {e.message} (status: {e.status_code})", exc_info=True
            )
            if e.status_code >= 500:
                # Server error - might be transient
                raise
            else:
                # Client error - probably not transient
                return None

        except KibanaException as e:
            logger.error(f"Kibana client error: {e}", exc_info=True)
            raise

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise

    # Test the function
    print("Testing production error handling...")
    result = safe_get_connector("non-existent-id")
    if result:
        print(f"✓ Connector found: {result}")
    else:
        print("✓ Connector not found (handled gracefully)")


def main():
    """Run all error handling examples."""
    print("=" * 70)
    print("Kibana Python Client - Error Handling Examples")
    print("=" * 70)

    # Print configuration info
    print_config_info()

    # Configure telemetry with production-ready error handling
    import logging

    from utils import (
        configure_example_telemetry,
        print_telemetry_info,
        setup_telemetry_cleanup,
        should_enable_telemetry,
    )

    logger = logging.getLogger(__name__)

    try:
        telemetry_enabled = should_enable_telemetry()
        traces_configured, logs_configured = configure_example_telemetry(
            enabled=telemetry_enabled,
            logs_enabled=telemetry_enabled,  # Enable log forwarding when telemetry is enabled
        )
        print_telemetry_info()

        # Set up automatic telemetry cleanup
        setup_telemetry_cleanup()

        if traces_configured or logs_configured:
            logger.info(
                "Error handling example started",
                extra={
                    "traces_enabled": traces_configured,
                    "logs_enabled": logs_configured,
                    "example": "error_handling",
                },
            )
    except Exception as e:
        logger.warning(
            f"Telemetry configuration failed: {e}",
            extra={"error_type": "telemetry_config_error", "example": "error_handling"},
        )
        print("⚠️  Continuing without telemetry...")

    # Initialize client
    client = create_kibana_client()

    try:
        # Run examples
        example_not_found_error(client)
        example_conflict_error(client)
        example_bad_request_error(client)
        example_authentication_error()
        example_authorization_error()
        example_generic_api_error(client)
        example_connection_error()
        example_timeout_error()
        example_retry_strategy(client)
        example_exception_hierarchy()
        example_production_error_handling(client)

        print("\n" + "=" * 70)
        print("✅ Error Handling Examples Completed!")
        print("=" * 70)
        print("\nKey Takeaways:")
        print("  1. Always catch specific exceptions first")
        print("  2. Use ApiError for generic API error handling")
        print("  3. Implement retry logic for transient errors")
        print("  4. Log errors with appropriate context")
        print("  5. Re-raise authentication/authorization errors")
        print("  6. Handle connection errors gracefully")

    except Exception as e:
        print(f"\n❌ Unexpected error in examples: {e}")
        import traceback

        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
