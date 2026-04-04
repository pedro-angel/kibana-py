#!/bin/bash
# Helper script to run observability integration tests with local Elastic Stack

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Running Kibana Observability Integration Tests${NC}"
echo ""

# Check if docker-compose is running
if ! docker ps | grep -q "kibana-local-dev"; then
    echo -e "${YELLOW}Warning: Kibana container not running${NC}"
    echo "Starting local Elastic Stack..."
    cd elastic-start-local
    docker-compose up -d
    cd ..

    echo "Waiting for services to be healthy..."
    sleep 30
fi

# Check if elastic-agent is running
if ! docker ps | grep -q "elastic-agent"; then
    echo -e "${YELLOW}Warning: Elastic Agent (APM) container not running${NC}"
    echo "Please ensure elastic-agent is running for OTLP traces"
fi

# Load environment variables from .env file
if [ -f "elastic-start-local/.env" ]; then
    export $(grep -v '^#' elastic-start-local/.env | xargs)
fi

# Set test environment variables
export KIBANA_URL="http://localhost:${KIBANA_LOCAL_PORT}"
export KIBANA_USERNAME="elastic"
export KIBANA_PASSWORD="${ES_LOCAL_PASSWORD}"

echo -e "${GREEN}Configuration:${NC}"
echo "  KIBANA_URL: $KIBANA_URL"
echo "  KIBANA_USERNAME: $KIBANA_USERNAME"
echo "  OTLP Endpoint: $OTEL_EXPORTER_OTLP_ENDPOINT"
echo "  OpenTelemetry: $KIBANA_OTEL_ENABLED"
echo "  Service Name: $OTEL_SERVICE_NAME"
echo ""

# Check if Kibana is accessible
echo "Checking Kibana connectivity..."
if curl -s -f -u "$KIBANA_USERNAME:$KIBANA_PASSWORD" "$KIBANA_URL/api/status" > /dev/null; then
    echo -e "${GREEN}✓ Kibana is accessible${NC}"
else
    echo -e "${RED}✗ Cannot connect to Kibana${NC}"
    echo "Make sure the local stack is running: cd elastic-start-local && docker-compose up -d"
    exit 1
fi

# Check if OTLP endpoint is accessible
echo "Checking OTLP endpoint connectivity..."
if curl -s -f "$OTEL_EXPORTER_OTLP_ENDPOINT" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ OTLP endpoint is accessible${NC}"
else
    echo -e "${YELLOW}⚠ OTLP endpoint not accessible (some tests may be skipped)${NC}"
fi

# Check if OpenTelemetry is installed
echo "Checking OpenTelemetry installation..."
if .venv/bin/python -c "import opentelemetry" 2>/dev/null; then
    echo -e "${GREEN}✓ OpenTelemetry is installed${NC}"
else
    echo -e "${RED}✗ OpenTelemetry not installed${NC}"
    echo "Installing OpenTelemetry..."
    .venv/bin/pip install -q opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc
    echo -e "${GREEN}✓ OpenTelemetry installed${NC}"
fi

echo ""
echo -e "${GREEN}Running observability integration tests...${NC}"
echo ""

# Run pytest with observability tests
.venv/bin/pytest tests/integration/test_observability_integration.py -v "$@"

echo ""
echo -e "${GREEN}Observability integration tests complete!${NC}"
echo ""
echo -e "${YELLOW}To view traces in Kibana:${NC}"
echo "  1. Open Kibana: $KIBANA_URL"
echo "  2. Go to Observability > APM"
echo "  3. Look for service: $OTEL_SERVICE_NAME"
echo ""
