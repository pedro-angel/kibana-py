StatusClient
============

Client for monitoring Kibana server health and statistics through the Status API.

The Status API provides information about the Kibana server's operational state,
including overall health status, individual service statuses, and detailed
operational metrics.

.. currentmodule:: kibana

.. autoclass:: kibana._sync.client.status.StatusClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Overview

   The StatusClient provides methods to check Kibana server health and retrieve
   operational statistics. This is useful for monitoring, alerting, and health checks.

   .. rubric:: Checking Server Status

   Get the current Kibana server status with the :meth:`~StatusClient.get_status` method:

   .. code-block:: python

      from kibana import Kibana

      client = Kibana("http://localhost:5601")

      # Get server status
      status = client.status.get_status()

      # Check overall status level
      overall_status = status.body["status"]["overall"]["level"]
      print(f"Kibana status: {overall_status}")

      # Status levels: "available", "degraded", or "unavailable"
      if overall_status == "available":
          print("✓ Kibana is healthy")
      elif overall_status == "degraded":
          print("⚠ Kibana is degraded")
      else:
          print("✗ Kibana is unavailable")

   .. rubric:: Status Response Structure

   The status response includes detailed information about each service:

   .. code-block:: python

      status = client.status.get_status()

      # Overall status
      overall = status.body["status"]["overall"]
      print(f"Overall: {overall['level']} - {overall['summary']}")

      # Individual service statuses
      for service_name, service_status in status.body["status"]["statuses"].items():
          level = service_status["level"]
          summary = service_status.get("summary", "")
          print(f"{service_name}: {level} - {summary}")

   Example status levels:

   - ``available`` - Service is fully operational
   - ``degraded`` - Service is operational but with issues
   - ``unavailable`` - Service is not operational

   .. rubric:: Retrieving Operational Statistics

   Get detailed operational metrics with the :meth:`~StatusClient.get_stats` method:

   .. code-block:: python

      # Get operational statistics
      stats = client.status.get_stats()

      # Process information
      process = stats.body["process"]
      print(f"Uptime: {process['uptime_in_millis']} ms")
      print(f"Memory usage: {process['memory']['heap']['used_in_bytes']} bytes")

      # OS information
      os_info = stats.body["os"]
      print(f"Platform: {os_info['platform']}")
      print(f"Load average: {os_info['load']}")

      # Response times
      response_times = stats.body["response_times"]
      print(f"Average response time: {response_times['avg_in_millis']} ms")
      print(f"Max response time: {response_times['max_in_millis']} ms")

   .. rubric:: Statistics Response Structure

   The statistics response includes:

   - **Process metrics**: Uptime, memory usage, event loop delay
   - **OS metrics**: Platform, CPU count, load average, memory
   - **Response times**: Average, max response times
   - **Requests**: Total requests, disconnects, status codes
   - **Concurrent connections**: Current connection count

   .. code-block:: python

      stats = client.status.get_stats()

      # Memory usage
      heap = stats.body["process"]["memory"]["heap"]
      print(f"Heap used: {heap['used_in_bytes'] / 1024 / 1024:.2f} MB")
      print(f"Heap total: {heap['total_in_bytes'] / 1024 / 1024:.2f} MB")
      print(f"Heap limit: {heap['size_limit'] / 1024 / 1024:.2f} MB")

      # Request statistics
      requests = stats.body["requests"]
      print(f"Total requests: {requests['total']}")
      print(f"Disconnects: {requests['disconnects']}")

      # Status code breakdown
      for code, count in requests["status_codes"].items():
          print(f"HTTP {code}: {count} requests")

   .. rubric:: Health Check Integration

   Use the Status API for health checks and monitoring:

   .. code-block:: python

      def check_kibana_health(client):
          """Check if Kibana is healthy."""
          try:
              status = client.status.get_status()
              level = status.body["status"]["overall"]["level"]

              if level == "available":
                  return True, "Kibana is healthy"
              elif level == "degraded":
                  return False, "Kibana is degraded"
              else:
                  return False, "Kibana is unavailable"
          except Exception as e:
              return False, f"Failed to check status: {e}"

      # Use in monitoring
      is_healthy, message = check_kibana_health(client)
      if not is_healthy:
          # Send alert
          print(f"ALERT: {message}")

   .. rubric:: Monitoring Best Practices

   Best practices for using the Status API:

   1. **Regular health checks**: Poll the status endpoint periodically
   2. **Alert on degradation**: Set up alerts for degraded or unavailable status
   3. **Track metrics over time**: Store statistics for trend analysis
   4. **Monitor response times**: Watch for increasing response times
   5. **Check memory usage**: Alert on high memory usage

   .. code-block:: python

      import time

      def monitor_kibana(client, interval=60):
          """Monitor Kibana health continuously."""
          while True:
              try:
                  # Check status
                  status = client.status.get_status()
                  level = status.body["status"]["overall"]["level"]

                  # Get stats
                  stats = client.status.get_stats()
                  uptime = stats.body["process"]["uptime_in_millis"]
                  heap_used = stats.body["process"]["memory"]["heap"]["used_in_bytes"]

                  print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]")
                  print(f"  Status: {level}")
                  print(f"  Uptime: {uptime / 1000 / 60:.2f} minutes")
                  print(f"  Heap: {heap_used / 1024 / 1024:.2f} MB")

                  if level != "available":
                      print(f"  WARNING: Kibana is {level}")

              except Exception as e:
                  print(f"  ERROR: Failed to get status: {e}")

              time.sleep(interval)

   .. rubric:: Error Handling

   Handle errors when checking status:

   .. code-block:: python

      from kibana.exceptions import (
          ConnectionError,
          AuthenticationException,
          TransportError
      )

      try:
          status = client.status.get_status()
      except AuthenticationException as e:
          print(f"Authentication failed: {e.message}")
      except ConnectionError as e:
          print(f"Cannot connect to Kibana: {e}")
      except TransportError as e:
          print(f"Transport error: {e}")

AsyncStatusClient
-----------------

Asynchronous version of the StatusClient for use with async/await syntax.

.. autoclass:: kibana._async.client.status.AsyncStatusClient
   :members:
   :inherited-members:
   :show-inheritance:
   :special-members: __init__

   .. rubric:: Usage

   The AsyncStatusClient provides the same methods as StatusClient but all methods
   are async and must be awaited:

   .. code-block:: python

      from kibana import AsyncKibana
      import asyncio

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              # Get status (async)
              status = await client.status.get_status()
              print(f"Status: {status.body['status']['overall']['level']}")

              # Get stats (async)
              stats = await client.status.get_stats()
              print(f"Uptime: {stats.body['process']['uptime_in_millis']} ms")

      asyncio.run(main())

   .. rubric:: Concurrent Monitoring

   Monitor multiple Kibana instances concurrently:

   .. code-block:: python

      import asyncio
      from kibana import AsyncKibana

      async def check_instance(url):
          """Check status of a single Kibana instance."""
          async with AsyncKibana(url) as client:
              status = await client.status.get_status()
              return {
                  "url": url,
                  "level": status.body["status"]["overall"]["level"]
              }

      async def monitor_cluster():
          """Monitor multiple Kibana instances."""
          instances = [
              "http://kibana1:5601",
              "http://kibana2:5601",
              "http://kibana3:5601"
          ]

          # Check all instances concurrently
          results = await asyncio.gather(
              *[check_instance(url) for url in instances],
              return_exceptions=True
          )

          for result in results:
              if isinstance(result, Exception):
                  print(f"Error: {result}")
              else:
                  print(f"{result['url']}: {result['level']}")

      asyncio.run(monitor_cluster())

   .. rubric:: Async Health Monitoring

   Implement continuous async health monitoring:

   .. code-block:: python

      import asyncio
      from kibana import AsyncKibana

      async def monitor_health(client, interval=60):
          """Monitor Kibana health continuously (async)."""
          while True:
              try:
                  # Get status and stats concurrently
                  status, stats = await asyncio.gather(
                      client.status.get_status(),
                      client.status.get_stats()
                  )

                  level = status.body["status"]["overall"]["level"]
                  uptime = stats.body["process"]["uptime_in_millis"]

                  print(f"Status: {level}, Uptime: {uptime / 1000:.2f}s")

                  if level != "available":
                      print(f"WARNING: Kibana is {level}")

              except Exception as e:
                  print(f"ERROR: {e}")

              await asyncio.sleep(interval)

      async def main():
          async with AsyncKibana("http://localhost:5601") as client:
              await monitor_health(client, interval=30)

      asyncio.run(main())
