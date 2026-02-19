#!/bin/bash

# API Test Script
# Tests if all API endpoints are working correctly

API_URL="http://localhost:3000"
CUSTOMER_ID="test-customer-123"

echo "========================================"
echo "AWS Bookstore API Test"
echo "========================================"
echo ""

# Color definitions
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test function
test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4
    
    echo -n "Test: $description ... "
    
    if [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X $method \
            -H "x-customer-id: $CUSTOMER_ID" \
            "$API_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X $method \
            -H "Content-Type: application/json" \
            -H "x-customer-id: $CUSTOMER_ID" \
            -d "$data" \
            "$API_URL$endpoint")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    
    if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 201 ]; then
        echo -e "${GREEN}✓ Success (HTTP $http_code)${NC}"
    else
        echo -e "${RED}✗ Failed (HTTP $http_code)${NC}"
    fi
}

echo "1. Test Root Path"
test_endpoint "GET" "/" "" "Get API Info"
echo ""

echo "2. Test Books API"
test_endpoint "GET" "/books" "" "Get All Books"
test_endpoint "GET" "/books?category=programming" "" "Get Books by Category"
test_endpoint "GET" "/books/book-001" "" "Get Single Book Details"
echo ""

echo "3. Test Cart API"
test_endpoint "POST" "/cart" '{"bookId":"book-001","quantity":2,"price":99.00}' "Add to Cart"
test_endpoint "GET" "/cart" "" "Get Cart"
test_endpoint "GET" "/cart/book-001" "" "Get Single Book in Cart"
test_endpoint "PUT" "/cart" '{"bookId":"book-001","quantity":3}' "Update Cart"
echo ""

echo "4. Test Orders API"
test_endpoint "POST" "/orders" '{"books":[{"bookId":"book-001","quantity":1,"price":99.00}]}' "Create Order"
test_endpoint "GET" "/orders" "" "Get Order List"
echo ""

echo "5. Test Other Feature APIs"
test_endpoint "GET" "/bestsellers" "" "Get Bestsellers List"
test_endpoint "GET" "/recommendations" "" "Get Recommended Books"
test_endpoint "GET" "/search?q=javascript" "" "Search Books"
echo ""

echo "6. Test Cart Cleanup"
test_endpoint "DELETE" "/cart" '{"bookId":"book-001"}' "Remove from Cart"
echo ""

echo "========================================"
echo "Test Completed"
echo "========================================"
