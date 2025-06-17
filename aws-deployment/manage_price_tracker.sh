#!/bin/bash

# Price Tracker Management Scripts
# Collection of useful commands for managing your AWS Price Tracker

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Function to print colored output
print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# ==================================================
# PRODUCT MANAGEMENT FUNCTIONS
# ==================================================

add_product() {
    print_header "ADD NEW PRODUCT"
    
    echo "Enter product details:"
    read -p "Product ID (e.g., 'macbook-pro-m3'): " product_id
    read -p "Product Name (e.g., 'MacBook Pro M3'): " product_name
    read -p "Product URL: " product_url
    
    # Validate inputs
    if [[ -z "$product_id" || -z "$product_name" || -z "$product_url" ]]; then
        print_error "All fields are required!"
        return 1
    fi
    
    # Add to DynamoDB
    aws dynamodb put-item \
        --table-name PriceTrackerProducts \
        --item "{
            \"product_id\": {\"S\": \"$product_id\"},
            \"url\": {\"S\": \"$product_url\"},
            \"product_name\": {\"S\": \"$product_name\"},
            \"active\": {\"BOOL\": true},
            \"created_at\": {\"S\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"}
        }" && \
    print_success "Product '$product_name' added successfully!" || \
    print_error "Failed to add product!"
}

remove_product() {
    print_header "REMOVE PRODUCT"
    
    # Show current products first
    view_products
    
    read -p "Enter Product ID to remove: " product_id
    
    if [[ -z "$product_id" ]]; then
        print_error "Product ID is required!"
        return 1
    fi
    
    # Ask for confirmation
    read -p "Are you sure you want to remove '$product_id'? (y/N): " confirm
    
    if [[ $confirm =~ ^[Yy]$ ]]; then
        aws dynamodb delete-item \
            --table-name PriceTrackerProducts \
            --key "{\"product_id\": {\"S\": \"$product_id\"}}" && \
        print_success "Product '$product_id' removed successfully!" || \
        print_error "Failed to remove product!"
    else
        print_warning "Operation cancelled."
    fi
}

disable_product() {
    print_header "DISABLE PRODUCT"
    
    # Show current active products
    view_active_products
    
    read -p "Enter Product ID to disable: " product_id
    
    if [[ -z "$product_id" ]]; then
        print_error "Product ID is required!"
        return 1
    fi
    
    aws dynamodb update-item \
        --table-name PriceTrackerProducts \
        --key "{\"product_id\": {\"S\": \"$product_id\"}}" \
        --update-expression "SET active = :false" \
        --expression-attribute-values '{":false": {"BOOL": false}}' && \
    print_success "Product '$product_id' disabled successfully!" || \
    print_error "Failed to disable product!"
}

enable_product() {
    print_header "ENABLE PRODUCT"
    
    # Show current inactive products
    view_inactive_products
    
    read -p "Enter Product ID to enable: " product_id
    
    if [[ -z "$product_id" ]]; then
        print_error "Product ID is required!"
        return 1
    fi
    
    aws dynamodb update-item \
        --table-name PriceTrackerProducts \
        --key "{\"product_id\": {\"S\": \"$product_id\"}}" \
        --update-expression "SET active = :true" \
        --expression-attribute-values '{":true": {"BOOL": true}}' && \
    print_success "Product '$product_id' enabled successfully!" || \
    print_error "Failed to enable product!"
}

# ==================================================
# VIEWING FUNCTIONS
# ==================================================

view_products() {
    print_header "ALL PRODUCTS"
    aws dynamodb scan \
        --table-name PriceTrackerProducts \
        --query 'Items[*].[product_id.S,product_name.S,last_price.N,active.BOOL,last_updated.S]' \
        --output table
}

view_active_products() {
    print_header "ACTIVE PRODUCTS (BEING TRACKED)"
    aws dynamodb scan \
        --table-name PriceTrackerProducts \
        --filter-expression "active = :true" \
        --expression-attribute-values '{":true": {"BOOL": true}}' \
        --query 'Items[*].[product_id.S,product_name.S,last_price.N,last_updated.S]' \
        --output table
}

view_inactive_products() {
    print_header "INACTIVE PRODUCTS (NOT BEING TRACKED)"
    aws dynamodb scan \
        --table-name PriceTrackerProducts \
        --filter-expression "active = :false" \
        --expression-attribute-values '{":false": {"BOOL": false}}' \
        --query 'Items[*].[product_id.S,product_name.S,last_price.N]' \
        --output table
}

view_price_history() {
    print_header "PRICE HISTORY"
    
    read -p "Enter Product ID (or press Enter for all): " product_id
    
    if [[ -z "$product_id" ]]; then
        # Show all price history
        aws dynamodb scan \
            --table-name PriceTrackerHistory \
            --query 'Items[*].[product_id.S,timestamp.S,price.N,price_change.N,price_change_percent.N]' \
            --output table
    else
        # Show history for specific product
        aws dynamodb query \
            --table-name PriceTrackerHistory \
            --key-condition-expression "product_id = :pid" \
            --expression-attribute-values "{\":pid\": {\"S\": \"$product_id\"}}" \
            --query 'Items[*].[timestamp.S,price.N,price_change.N,price_change_percent.N]' \
            --output table
    fi
}

view_alerts() {
    print_header "RECENT PRICE ALERTS"
    aws dynamodb scan \
        --table-name PriceTrackerAlerts \
        --query 'Items[*].[product_id.S,alert_type.S,previous_price.N,current_price.N,price_change_percent.N,timestamp.S]' \
        --output table
}

# ==================================================
# TESTING AND MONITORING FUNCTIONS
# ==================================================

test_price_tracking() {
    print_header "TESTING PRICE TRACKING"
    
    print_warning "Running price tracker manually..."
    
    aws lambda invoke \
        --function-name price-tracker-function \
        response.json && \
    cat response.json && \
    rm -f response.json && \
    print_success "Price tracking test completed!" || \
    print_error "Price tracking test failed!"
    
    echo ""
    print_warning "Updated product prices:"
    view_active_products
}

test_analytics_api() {
    print_header "TESTING ANALYTICS API"
    
    echo '{"httpMethod": "GET", "path": "/products"}' > /tmp/test_analytics.json
    
    aws lambda invoke \
        --function-name price-tracker-function \
        --payload file:///tmp/test_analytics.json \
        /tmp/analytics_response.json && \
    echo "Analytics API Response:" && \
    cat /tmp/analytics_response.json && \
    rm -f /tmp/test_analytics.json /tmp/analytics_response.json && \
    print_success "Analytics API test completed!" || \
    print_error "Analytics API test failed!"
}

view_recent_logs() {
    print_header "RECENT LAMBDA LOGS"
    
    # Get the latest log stream
    LOG_STREAM=$(aws logs describe-log-streams \
        --log-group-name /aws/lambda/price-tracker-function \
        --order-by LastEventTime \
        --descending \
        --max-items 1 \
        --query 'logStreams[0].logStreamName' \
        --output text)
    
    if [[ "$LOG_STREAM" != "None" && "$LOG_STREAM" != "" ]]; then
        print_warning "Latest log stream: $LOG_STREAM"
        echo ""
        aws logs get-log-events \
            --log-group-name /aws/lambda/price-tracker-function \
            --log-stream-name "$LOG_STREAM" \
            --query 'events[-15:].message' \
            --output text
    else
        print_error "No recent logs found!"
    fi
}

check_system_status() {
    print_header "SYSTEM STATUS CHECK"
    
    echo -e "${YELLOW}📊 Lambda Function Status:${NC}"
    aws lambda get-function \
        --function-name price-tracker-function \
        --query '{FunctionName:Configuration.FunctionName,State:Configuration.State,LastModified:Configuration.LastModified,CodeSize:Configuration.CodeSize}' \
        --output table
    
    echo ""
    echo -e "${YELLOW}📅 Scheduled Events:${NC}"
    aws events list-rules \
        --query 'Rules[?contains(Name, `price-tracker`)].{Name:Name,State:State,Schedule:ScheduleExpression}' \
        --output table
    
    echo ""
    echo -e "${YELLOW}📈 Active Products Count:${NC}"
    ACTIVE_COUNT=$(aws dynamodb scan \
        --table-name PriceTrackerProducts \
        --filter-expression "active = :true" \
        --expression-attribute-values '{":true": {"BOOL": true}}' \
        --select "COUNT" \
        --query 'Count' \
        --output text)
    echo "Active Products: $ACTIVE_COUNT"
    
    echo ""
    echo -e "${YELLOW}📧 SNS Topic Status:${NC}"
    aws sns list-topics \
        --query 'Topics[?contains(TopicArn, `price-alerts`)].TopicArn' \
        --output table
}

# ==================================================
# ANALYTICS AND INSIGHTS
# ==================================================

show_product_analytics() {
    print_header "PRODUCT ANALYTICS"
    
    read -p "Enter Product ID for analytics: " product_id
    
    if [[ -z "$product_id" ]]; then
        print_error "Product ID is required!"
        return 1
    fi
    
    # Test analytics API for specific product
    echo "{\"httpMethod\": \"GET\", \"path\": \"/analytics\", \"queryStringParameters\": {\"product_id\": \"$product_id\"}}" > /tmp/analytics_test.json
    
    aws lambda invoke \
        --function-name price-tracker-function \
        --payload file:///tmp/analytics_test.json \
        /tmp/analytics_result.json && \
    echo "Analytics for $product_id:" && \
    cat /tmp/analytics_result.json | jq '.body | fromjson' 2>/dev/null || cat /tmp/analytics_result.json && \
    rm -f /tmp/analytics_test.json /tmp/analytics_result.json || \
    print_error "Failed to get analytics for $product_id"
}

# ==================================================
# QUICK SETUP FUNCTIONS
# ==================================================

quick_add_examples() {
    print_header "ADD EXAMPLE PRODUCTS"
    
    echo "Adding example products for testing..."
    
    # Example 1: eBay product (usually more reliable)
    aws dynamodb put-item \
        --table-name PriceTrackerProducts \
        --item '{
            "product_id": {"S": "ebay-example"},
            "url": {"S": "https://www.ebay.co.uk/itm/123456789"},
            "product_name": {"S": "eBay Example Product"},
            "active": {"BOOL": true},
            "created_at": {"S": "'"$(date -u +"%Y-%m-%dT%H:%M:%SZ")"'"}
        }' 2>/dev/null && print_success "Added eBay example product"
    
    # Example 2: Test product
    aws dynamodb put-item \
        --table-name PriceTrackerProducts \
        --item '{
            "product_id": {"S": "test-product"},
            "url": {"S": "https://httpbin.org/status/200"},
            "product_name": {"S": "Test Product (Always Available)"},
            "active": {"BOOL": true},
            "created_at": {"S": "'"$(date -u +"%Y-%m-%dT%H:%M:%SZ")"'"}
        }' 2>/dev/null && print_success "Added test product"
    
    print_warning "Note: Update the URLs with real product pages for actual tracking!"
}

cleanup_test_products() {
    print_header "CLEANUP TEST PRODUCTS"
    
    echo "Removing test and inactive products..."
    
    # Remove common test products
    aws dynamodb delete-item --table-name PriceTrackerProducts --key '{"product_id": {"S": "test-httpbin"}}' 2>/dev/null
    aws dynamodb delete-item --table-name PriceTrackerProducts --key '{"product_id": {"S": "test-simple"}}' 2>/dev/null
    aws dynamodb delete-item --table-name PriceTrackerProducts --key '{"product_id": {"S": "amazon-monitors-search"}}' 2>/dev/null
    aws dynamodb delete-item --table-name PriceTrackerProducts --key '{"product_id": {"S": "test-product"}}' 2>/dev/null
    
    print_success "Test products cleaned up!"
}

# ==================================================
# MAIN MENU
# ==================================================

show_menu() {
    clear
    echo -e "${PURPLE}"
    echo "  ____       _              _____               _               "
    echo " |  _ \ _ __(_) ___ ___     |_   _| __ __ _  ___| | _____ _ __  "
    echo " | |_) | '__| |/ __/ _ \      | || '__/ _\` |/ __| |/ / _ \ '__| "
    echo " |  __/| |  | | (_|  __/      | || | | (_| | (__|   <  __/ |    "
    echo " |_|   |_|  |_|\___\___|      |_||_|  \__,_|\___|_|\_\___|_|    "
    echo "                                                               "
    echo -e "${NC}"
    echo -e "${BLUE}AWS Price Tracker Management Console${NC}"
    echo ""
    echo -e "${GREEN}PRODUCT MANAGEMENT:${NC}"
    echo "  1) Add Product"
    echo "  2) Remove Product"
    echo "  3) Disable Product"
    echo "  4) Enable Product"
    echo ""
    echo -e "${GREEN}VIEW DATA:${NC}"
    echo "  5) View All Products"
    echo "  6) View Active Products"
    echo "  7) View Price History"
    echo "  8) View Recent Alerts"
    echo ""
    echo -e "${GREEN}TESTING & MONITORING:${NC}"
    echo "  9) Test Price Tracking"
    echo " 10) Test Analytics API"
    echo " 11) View Recent Logs"
    echo " 12) Check System Status"
    echo " 13) Product Analytics"
    echo ""
    echo -e "${GREEN}UTILITIES:${NC}"
    echo " 14) Add Example Products"
    echo " 15) Cleanup Test Products"
    echo ""
    echo -e "${RED} 0) Exit${NC}"
    echo ""
}

# Main execution
main() {
    while true; do
        show_menu
        read -p "Select an option (0-15): " choice
        
        case $choice in
            1) add_product ;;
            2) remove_product ;;
            3) disable_product ;;
            4) enable_product ;;
            5) view_products ;;
            6) view_active_products ;;
            7) view_price_history ;;
            8) view_alerts ;;
            9) test_price_tracking ;;
            10) test_analytics_api ;;
            11) view_recent_logs ;;
            12) check_system_status ;;
            13) show_product_analytics ;;
            14) quick_add_examples ;;
            15) cleanup_test_products ;;
            0) print_success "Goodbye!"; exit 0 ;;
            *) print_error "Invalid option. Please try again." ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
}

# If script is run directly, show menu
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main
fi