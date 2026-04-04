#!/bin/bash
# Helper script to run integration tests with local Elastic Stack

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Running Kibana Integration Tests${NC}"
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

echo ""
echo -e "${GREEN}Running integration tests...${NC}"
echo ""

# Run pytest with integration tests
.venv/bin/pytest tests/integration/ -v "$@"

echo ""
echo -e "${GREEN}Integration tests complete!${NC}"
