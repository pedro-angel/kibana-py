# Status Monitoring

The Status API provides information about Kibana server health and operational metrics. This is essential for monitoring, alerting, and troubleshooting your Kibana deployment.

## Overview

The Status API allows you to:
- Check Kibana server health
- Monitor service availability
- Retrieve operational statistics
- Implement health checks for automation
- Track resource usage and performance

## Checking Kibana Status

### Basic Status Check

```python
from kibana import Kibana

client = Kibana("http://localhost:5601", api_key="your_api_key")

# Get current status
response = client.status.get_status()
status = response.body

# Check overall health
overall_status = status["status"]["overall"]["level"]
print(f"Kibana status: {overall_status}")

client.close()
```

### Status Levels

Kibana reports three status levels:

- **`available`**: All services are operational
- **`degraded`**: Some services are experiencing issues but Kibana is still functional
- **`unavailable`**: Kibana is not operational

### Detailed Status Information

```python
response = client.status.get_status()
status = response.body

# Overall status
print(f"Overall: {status['status']['overall']['level']}")
print(f"Summary: {status['status']['overall']['summary']}")

# Core services status
for service_name, service_info in status['status']['core'].items():
    print(f"{service_name}: {service_info['level']}")
    if service_info.get('summary'):
        print(f"  Summary: {service_info['summary']}")

# Plugin statuses
for plugin_name, plugin_info in status['status'].get('plugins', {}).items():
    print(f"Plugin {plugin_name}: {plugin_info['level']}")
```

### Version Information

```python
response = client.status.get_status()
status = response.body

# Kibana version
version_info = status['version']
print(f"Kibana version: {version_info['number']}")
print(f"Build number: {version_info['build_number']}")
print(f"Build hash: {version_info['build_hash']}")
```

## Getting Operational Statistics

### Basic Statistics

```python
# Get detailed statistics
response = client.status.get_stats()
stats = response.body

# Process information
process = stats['process']
print(f"Uptime: {process['uptime_in_millis'] / 1000:.2f} seconds")
print(f"Memory used: {process['memory']['heap']['used_bytes'] / (1024**2):.2f} MB")
print(f"Memory total: {process['memory']['heap']['total_bytes'] / (1024**2):.2f} MB")

# OS information
os_info = stats['os']
print(f"Platform: {os_info['platform']}")
print(f"Load average (1m): {os_info['load']['1m']}")
print(f"Load average (5m): {os_info['load']['5m']}")
print(f"Load average (15m): {os_info['load']['15m']}")
```

### Memory Statistics

```python
response = client.status.get_stats()
stats = response.body

memory = stats['process']['memory']
heap = memory['heap']

print(f"Heap used: {heap['used_bytes'] / (1024**2):.2f} MB")
print(f"Heap total: {heap['total_bytes'] / (1024**2):.2f} MB")
print(f"Heap limit: {heap['size_limit'] / (1024**2):.2f} MB")
print(f"Heap usage: {(heap['used_bytes'] / heap['size_limit']) * 100:.1f}%")
```

### Request Statistics

```python
response = client.status.get_stats()
stats = response.body

# HTTP request statistics
requests = stats.get('requests', {})
print(f"Total requests: {requests.get('total', 0)}")
print(f"Disconnects: {requests.get('disconnects', 0)}")
print(f"Status codes: {requests.get('statusCodes', {})}")
```

## Health Check Patterns

### Simple Health Check

```python
def is_kibana_healthy(client):
    """Check if Kibana is healthy."""
    try:
        response = client.status.get_status()
        status_level = response.body['status']['overall']['level']
        return status_level == 'available'
    except Exception:
        return False

# Usage
if is_kibana_healthy(client):
    print("✅ Kibana is healthy")
else:
    print("❌ Kibana is unhealthy")
```

### Detailed Health Check

```python
def check_kibana_health(client):
    """Perform detailed health check."""
    try:
        response = client.status.get_status()
        status = response.body

        overall = status['status']['overall']['level']

        result = {
            'healthy': overall == 'available',
            'status': overall,
            'version': status['version']['number'],
            'services': {}
        }

        # Check core services
        for service_name, service_info in status['status']['core'].items():
            result['services'][service_name] = {
                'level': service_info['level'],
                'summary': service_info.get('summary', '')
            }

        return result

    except Exception as e:
        return {
            'healthy': False,
            'error': str(e)
        }

# Usage
health = check_kibana_health(client)
print(f"Healthy: {health['healthy']}")
print(f"Status: {health.get('status', 'unknown')}")
for service, info in health.get('services', {}).items():
    print(f"  {service}: {info['level']}")
```

### Monitoring with Alerts

```python
import time

def monitor_kibana(client, check_interval=60, alert_threshold=3):
    """Monitor Kibana and alert on issues."""
    consecutive_failures = 0

    while True:
        try:
            response = client.status.get_status()
            status_level = response.body['status']['overall']['level']

            if status_level == 'available':
                consecutive_failures = 0
                print(f"✅ Kibana is healthy")
            elif status_level == 'degraded':
                consecutive_failures += 1
                print(f"⚠️  Kibana is degraded ({consecutive_failures}/{alert_threshold})")

                if consecutive_failures >= alert_threshold:
                    send_alert("Kibana is degraded")
            else:  # unavailable
                consecutive_failures += 1
                print(f"❌ Kibana is unavailable ({consecutive_failures}/{alert_threshold})")

                if consecutive_failures >= alert_threshold:
                    send_alert("Kibana is unavailable")

        except Exception as e:
            consecutive_failures += 1
            print(f"❌ Failed to check status: {e}")

            if consecutive_failures >= alert_threshold:
                send_alert(f"Cannot connect to Kibana: {e}")

        time.sleep(check_interval)

def send_alert(message):
    """Send alert notification."""
    print(f"🚨 ALERT: {message}")
    # Implement your alerting logic here
    # (email, Slack, PagerDuty, etc.)
```

## Performance Monitoring

### Memory Usage Monitoring

```python
def check_memory_usage(client, threshold_percent=80):
    """Check if memory usage exceeds threshold."""
    response = client.status.get_stats()
    stats = response.body

    heap = stats['process']['memory']['heap']
    used = heap['used_bytes']
    limit = heap['size_limit']
    usage_percent = (used / limit) * 100

    if usage_percent > threshold_percent:
        print(f"⚠️  High memory usage: {usage_percent:.1f}%")
        return False
    else:
        print(f"✅ Memory usage OK: {usage_percent:.1f}%")
        return True
```

### Load Average Monitoring

```python
def check_load_average(client, threshold=2.0):
    """Check if system load is high."""
    response = client.status.get_stats()
    stats = response.body

    load_1m = stats['os']['load']['1m']

    if load_1m > threshold:
        print(f"⚠️  High load average: {load_1m}")
        return False
    else:
        print(f"✅ Load average OK: {load_1m}")
        return True
```

## Integration with Monitoring Systems

### Prometheus Metrics

```python
def export_prometheus_metrics(client):
    """Export Kibana metrics in Prometheus format."""
    response = client.status.get_stats()
    stats = response.body

    metrics = []

    # Memory metrics
    heap = stats['process']['memory']['heap']
    metrics.append(f'kibana_heap_used_bytes {heap["used_bytes"]}')
    metrics.append(f'kibana_heap_total_bytes {heap["total_bytes"]}')
    metrics.append(f'kibana_heap_limit_bytes {heap["size_limit"]}')

    # Uptime metric
    uptime = stats['process']['uptime_in_millis'] / 1000
    metrics.append(f'kibana_uptime_seconds {uptime}')

    # Load average
    load = stats['os']['load']
    metrics.append(f'kibana_load_1m {load["1m"]}')
    metrics.append(f'kibana_load_5m {load["5m"]}')
    metrics.append(f'kibana_load_15m {load["15m"]}')

    return '\n'.join(metrics)

# Usage
metrics = export_prometheus_metrics(client)
print(metrics)
```

### Health Check Endpoint

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/health')
def health_check():
    """Health check endpoint for load balancers."""
    try:
        response = client.status.get_status()
        status_level = response.body['status']['overall']['level']

        if status_level == 'available':
            return jsonify({'status': 'healthy'}), 200
        elif status_level == 'degraded':
            return jsonify({'status': 'degraded'}), 200
        else:
            return jsonify({'status': 'unhealthy'}), 503

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 503

@app.route('/metrics')
def metrics():
    """Metrics endpoint for monitoring."""
    try:
        response = client.status.get_stats()
        stats = response.body

        return jsonify({
            'uptime_seconds': stats['process']['uptime_in_millis'] / 1000,
            'memory_used_mb': stats['process']['memory']['heap']['used_bytes'] / (1024**2),
            'memory_limit_mb': stats['process']['memory']['heap']['size_limit'] / (1024**2),
            'load_1m': stats['os']['load']['1m']
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

## Best Practices

### 1. Implement Regular Health Checks

```python
# Check health before critical operations
if not is_kibana_healthy(client):
    print("Kibana is unhealthy, skipping operation")
    return

# Proceed with operation
result = client.actions.create(...)
```

### 2. Monitor Key Metrics

```python
def monitor_key_metrics(client):
    """Monitor key Kibana metrics."""
    response = client.status.get_stats()
    stats = response.body

    # Memory usage
    heap = stats['process']['memory']['heap']
    memory_usage = (heap['used_bytes'] / heap['size_limit']) * 100

    # Load average
    load_1m = stats['os']['load']['1m']

    # Uptime
    uptime_hours = stats['process']['uptime_in_millis'] / (1000 * 60 * 60)

    return {
        'memory_usage_percent': memory_usage,
        'load_1m': load_1m,
        'uptime_hours': uptime_hours
    }
```

### 3. Set Up Alerts

```python
def check_and_alert(client):
    """Check metrics and send alerts if needed."""
    metrics = monitor_key_metrics(client)

    if metrics['memory_usage_percent'] > 80:
        send_alert(f"High memory usage: {metrics['memory_usage_percent']:.1f}%")

    if metrics['load_1m'] > 2.0:
        send_alert(f"High load average: {metrics['load_1m']}")
```

### 4. Log Status Information

```python
import logging

logger = logging.getLogger(__name__)

def log_status(client):
    """Log Kibana status information."""
    try:
        response = client.status.get_status()
        status = response.body

        logger.info(
            "Kibana status check",
            extra={
                'status': status['status']['overall']['level'],
                'version': status['version']['number'],
                'uptime': status.get('metrics', {}).get('process', {}).get('uptime_in_millis')
            }
        )
    except Exception as e:
        logger.error(f"Failed to check Kibana status: {e}")
```

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to Kibana

**Solutions**:
- Verify Kibana URL is correct
- Check network connectivity
- Verify authentication credentials
- Check firewall rules

### Degraded Status

**Problem**: Kibana reports degraded status

**Solutions**:
- Check individual service statuses
- Review Kibana server logs
- Verify Elasticsearch connectivity
- Check resource availability (memory, disk)

### High Memory Usage

**Problem**: Memory usage is consistently high

**Solutions**:
- Increase heap size in Kibana configuration
- Review and optimize dashboards and visualizations
- Check for memory leaks
- Consider scaling horizontally

## Next Steps

- Learn about [Error Handling](error-handling.md) for comprehensive error management
- Explore [Observability](observability.md) for distributed tracing
- Check [Advanced Usage](advanced-usage.md) for performance optimization
- See [Examples](../examples/index.md) for practical code samples
