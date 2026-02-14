#!/bin/bash
# Local testing script for Lambda functions
# Usage: ./test_local.sh [contact|deal|ticket|flow|cleanup]

set -e

# Load environment variables
if [ -f .env ]; then
    set -a
    source <(grep -v '^#' .env | sed 's/#.*//' | grep -v '^$')
    set +a
else
    echo "Warning: .env file not found. Make sure HUBSPOT_API_KEY is set."
fi

# Function to test a specific lambda
test_lambda() {
    local lambda_name=$1
    echo "========================================"
    echo "Testing lambda_${lambda_name}"
    echo "========================================"
    cd "lambda_${lambda_name}"
    PYTHONPATH=..:../shared python lambda_function.py
    cd ..
    echo ""
}

# Function to test complete happy path flow
test_flow() {
    echo "========================================"
    echo "Testing Complete Happy Path Flow"
    echo "========================================"
    echo ""
    echo "Step 1: Patient Registration (creates contacts)"
    echo "----------------------------------------"
    test_lambda "contact"

    echo "Step 2: Order Created (moves deal to active_subscription)"
    echo "----------------------------------------"
    test_lambda "deal"

    echo "========================================"
    echo "Complete Flow Test Finished!"
    echo "========================================"
    echo ""
    echo "Verify in HubSpot:"
    echo "  1. Two contacts created (guardian + patient) with association"
    echo "  2. Deal created in 'registration' stage"
    echo "  3. Deal moved to 'active_subscription' with subscription_external_id = 101"
}

# Main script
if [ -z "$1" ]; then
    # Test all lambdas individually
    test_lambda "contact"
    test_lambda "deal"
elif [ "$1" = "flow" ]; then
    test_flow
elif [ "$1" = "cleanup" ]; then
    echo "Running HubSpot cleanup script..."
    PYTHONPATH=.:shared python cleanup_hubspot.py
elif [ "$1" = "contact" ] || [ "$1" = "deal" ]; then
    test_lambda "$1"
else
    echo "Usage: $0 [contact|deal|flow|cleanup]"
    echo "  contact  - Test contact lambda only"
    echo "  deal     - Test deal lambda only"
    echo "  flow     - Test complete happy path flow"
    echo "  cleanup  - Delete all test data from HubSpot"
    echo "  (no arg) - Test all lambdas individually"
    exit 1
fi

echo "All tests completed!"
