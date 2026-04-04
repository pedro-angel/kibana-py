#!/bin/bash

# Integration test runner for space support functionality
# This script runs all space-related integration tests

set -e

echo "=== Space Support Integration Tests ==="
echo "Running comprehensive integration tests for space support functionality"
echo

# Check if Kibana is available
echo "Checking Kibana availability..."
python tests/integration/utils.py
echo

# Run space validation tests
echo "Running space validation tests..."
python -m pytest tests/integration/test_space_validation_integration.py -v --tb=short

echo

# Run space-scoped operations tests
echo "Running space-scoped operations tests..."
python -m pytest tests/integration/test_space_scoped_operations_integration.py -v --tb=short

echo

# Run space performance tests
echo "Running space performance tests..."
python -m pytest tests/integration/test_space_performance_integration.py -v --tb=short

echo
echo "=== All Space Integration Tests Complete ==="
