#!/bin/bash

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
run_all=true
service=""

show_help() {
    echo -e "${BLUE}Gmail Automation Test Runner${NC}"
    echo "Usage: ./run_tests.sh [options]"
    echo ""
    echo "Options:"
    echo "  -a, --auth       Run only auth_service tests"
    echo "  -e, --email      Run only email_service tests"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Without options, all tests will be run."
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -a|--auth)
            run_all=false
            service="auth"
            shift
            ;;
        -e|--email)
            run_all=false
            service="email"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${YELLOW}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Function to run tests for a specific service
run_service_tests() {
    service_name=$1
    echo -e "${BLUE}Running $service_name Service tests...${NC}"
    cd "services/${service_name}_service" && python -m pytest tests/
    return $?
}

# Run the tests based on arguments
if [ "$run_all" = true ]; then
    echo -e "${BLUE}Running all tests...${NC}"
    # Run each service's tests in their own directory to avoid import conflicts
    
    echo -e "${BLUE}Running Auth Service tests...${NC}"
    cd services/auth_service && python -m pytest tests/ && cd ../../
    auth_result=$?
    
    echo -e "${BLUE}Running Email Service tests...${NC}"
    cd services/email_service && python -m pytest tests/ && cd ../../
    email_result=$?

    # Determine overall exit code
    if [ $auth_result -eq 0 ] && [ $email_result -eq 0 ]; then
        exit_code=0
    else
        exit_code=1
    fi
else
    if [ "$service" = "auth" ]; then
        run_service_tests "auth"
        exit_code=$?
    elif [ "$service" = "email" ]; then
        run_service_tests "email"
        exit_code=$?
    fi
fi

# Final message
if [ $exit_code -eq 0 ]; then
    echo -e "\n${GREEN}All tests completed successfully!${NC}"
else
    echo -e "\n${YELLOW}Tests completed with failures. Exit code: $exit_code${NC}"
fi

exit $exit_code
