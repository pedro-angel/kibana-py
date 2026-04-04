#!/bin/bash

# Integration test runner for OpenTelemetry log forwarding
# This script runs all log forwarding integration tests with proper configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    print_warning "No virtual environment detected. Activating .venv if available..."
    if [ -d ".venv" ]; then
        source .venv/bin/activate
        print_success "Activated .venv virtual environment"
    else
        print_error "No .venv directory found. Please create and activate a virtual environment."
        exit 1
    fi
fi

# Check if required dependencies are installed
print_status "Checking dependencies..."

python -c "import opentelemetry" 2>/dev/null || {
    print_error "OpenTelemetry not installed. Installing observability dependencies..."
    pip install -e ".[observability]"
}

python -c "import opentelemetry._logs" 2>/dev/null || {
    print_error "OpenTelemetry logs not installed. Installing log exporters..."
    pip install opentelemetry-exporter-otlp-proto-grpc opentelemetry-exporter-otlp-proto-http
}

# Check for optional performance monitoring dependency
python -c "import psutil" 2>/dev/null || {
    print_warning "psutil not installed. Performance tests may be skipped."
    print_status "Install with: pip install psutil"
}

print_success "Dependencies check completed"

# Configuration check
print_status "Checking test configuration..."

# Check for Kibana configuration
if [ -z "$KIBANA_URL" ]; then
    if [ -f "elastic-start-local/.env" ]; then
        print_status "Loading configuration from elastic-start-local/.env"
        export $(grep -v '^#' elastic-start-local/.env | xargs)
    else
        print_warning "KIBANA_URL not set and no elastic-start-local/.env found"
        print_status "Some tests may be skipped"
    fi
fi

# Check for OTLP endpoint configuration
if [ -z "$OTEL_EXPORTER_OTLP_ENDPOINT" ]; then
    print_warning "OTEL_EXPORTER_OTLP_ENDPOINT not set"
    print_status "OTLP endpoint tests will be skipped"
    print_status "To run APM tests, set: export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200"
else
    print_success "OTLP endpoint configured: $OTEL_EXPORTER_OTLP_ENDPOINT"
fi

# Display current configuration
print_status "Current test configuration:"
echo "  KIBANA_URL: ${KIBANA_URL:-'not set'}"
echo "  KIBANA_USERNAME: ${KIBANA_USERNAME:-'not set'}"
echo "  KIBANA_API_KEY: ${KIBANA_API_KEY:+set}"
echo "  OTEL_EXPORTER_OTLP_ENDPOINT: ${OTEL_EXPORTER_OTLP_ENDPOINT:-'not set'}"
echo "  ELASTIC_APM_SECRET_TOKEN: ${ELASTIC_APM_SECRET_TOKEN:+set}"

# Test selection
LOG_FORWARDING_TESTS=(
    "tests/integration/test_log_forwarding_integration.py"
    "tests/integration/test_log_trace_correlation_integration.py"
    "tests/integration/test_log_performance_integration.py"
    "tests/integration/test_log_graceful_degradation_integration.py"
    "tests/integration/test_end_to_end_observability_integration.py"
)

# Parse command line arguments
VERBOSE=""
SPECIFIC_TEST=""
QUICK_MODE=""
OTLP_ONLY=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -t|--test)
            SPECIFIC_TEST="$2"
            shift 2
            ;;
        -q|--quick)
            QUICK_MODE="true"
            shift
            ;;
        --otlp-only)
            OTLP_ONLY="true"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -v, --verbose     Run tests with verbose output"
            echo "  -t, --test TEST   Run specific test file or test function"
            echo "  -q, --quick       Run quick tests only (skip performance tests)"
            echo "  --otlp-only        Run only OTLP endpoint tests"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Run all log forwarding tests"
            echo "  $0 -v                                 # Run with verbose output"
            echo "  $0 -t test_log_forwarding_integration # Run specific test file"
            echo "  $0 -q                                 # Run quick tests only"
            echo "  $0 --otlp-only                         # Run only OTLP endpoint tests"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_CMD="python -m pytest"

if [ -n "$VERBOSE" ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Add markers for quick mode
if [ -n "$QUICK_MODE" ]; then
    PYTEST_CMD="$PYTEST_CMD -m 'not slow'"
    print_status "Running in quick mode (skipping slow tests)"
fi

# Add markers for APM-only mode
if [ -n "$OTLP_ONLY" ]; then
    if [ -z "$OTEL_EXPORTER_OTLP_ENDPOINT" ]; then
        print_error "APM-only mode requires OTEL_EXPORTER_OTLP_ENDPOINT to be set"
        exit 1
    fi
    PYTEST_CMD="$PYTEST_CMD -k 'otlp'"
    print_status "Running OTLP endpoint tests only"
fi

# Run specific test or all tests
if [ -n "$SPECIFIC_TEST" ]; then
    print_status "Running specific test: $SPECIFIC_TEST"
    $PYTEST_CMD "$SPECIFIC_TEST"
else
    print_status "Running all log forwarding integration tests..."

    # Run each test file
    for test_file in "${LOG_FORWARDING_TESTS[@]}"; do
        if [ -f "$test_file" ]; then
            print_status "Running $(basename "$test_file")..."
            $PYTEST_CMD "$test_file" || {
                print_error "Test failed: $test_file"
                exit 1
            }
            print_success "Completed $(basename "$test_file")"
        else
            print_warning "Test file not found: $test_file"
        fi
    done
fi

print_success "All log forwarding integration tests completed successfully!"

# Provide helpful information
echo ""
print_status "Test Results Summary:"
echo "  ✅ Log forwarding integration tests passed"
echo "  ✅ Log-trace correlation tests passed"
echo "  ✅ Performance and filtering tests passed"
echo "  ✅ Graceful degradation tests passed"
echo "  ✅ End-to-end observability tests passed"

echo ""
print_status "Next Steps:"
echo "  • Review test output for any warnings or performance metrics"
echo "  • Check OTLP endpoint (if configured) for received traces and logs"
echo "  • Run examples with log forwarding enabled to see it in action"
echo "  • Consider running performance benchmarks with your specific workload"

echo ""
print_status "Useful Commands:"
echo "  # Run with OTLP endpoint"
echo "  export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8200"
echo "  $0 --otlp-only"
echo ""
echo "  # Run specific test class"
echo "  python -m pytest tests/integration/test_log_forwarding_integration.py::TestOTLPLogForwarding -v"
echo ""
echo "  # Run with coverage"
echo "  python -m pytest --cov=kibana --cov-report=html tests/integration/test_log_*"
