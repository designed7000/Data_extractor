#  Price Tracker Quick Commands Reference

##  PRODUCT MANAGEMENT

###  Add New Product
```bash
aws dynamodb put-item \
    --table-name PriceTrackerProducts \
    --item '{
        "product_id": {"S": "YOUR-PRODUCT-ID"},
        "url": {"S": "https://YOUR-PRODUCT-URL"},
        "product_name": {"S": "Your Product Name"},
        "active": {"BOOL": true},
        "created_at": {"S": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"}
    }'
```

###  Remove Product
```bash
# Disable product (keeps history)
aws dynamodb update-item \
    --table-name PriceTrackerProducts \
    --key '{"product_id": {"S": "PRODUCT-ID"}}' \
    --update-expression "SET active = :false" \
    --expression-attribute-values '{":false": {"BOOL": false}}'

# Completely delete product
aws dynamodb delete-item \
    --table-name PriceTrackerProducts \
    --key '{"product_id": {"S": "PRODUCT-ID"}}'
```

###  Enable/Disable Product
```bash
# Enable product
aws dynamodb update-item \
    --table-name PriceTrackerProducts \
    --key '{"product_id": {"S": "PRODUCT-ID"}}' \
    --update-expression "SET active = :true" \
    --expression-attribute-values '{":true": {"BOOL": true}}'

# Disable product
aws dynamodb update-item \
    --table-name PriceTrackerProducts \
    --key '{"product_id": {"S": "PRODUCT-ID"}}' \
    --update-expression "SET active = :false" \
    --expression-attribute-values '{":false": {"BOOL": false}}'
```

## 👀 VIEW DATA

###  View All Products
```bash
aws dynamodb scan \
    --table-name PriceTrackerProducts \
    --query 'Items[*].[product_id.S,product_name.S,last_price.N,active.BOOL,last_updated.S]' \
    --output table
```

###  View Active Products Only
```bash
aws dynamodb scan \
    --table-name PriceTrackerProducts \
    --filter-expression "active = :true" \
    --expression-attribute-values '{":true": {"BOOL": true}}' \
    --query 'Items[*].[product_id.S,product_name.S,last_price.N,last_updated.S]' \
    --output table
```

###  View Price History
```bash
# All price history
aws dynamodb scan \
    --table-name PriceTrackerHistory \
    --query 'Items[*].[product_id.S,timestamp.S,price.N,price_change_percent.N]' \
    --output table

# Specific product history
aws dynamodb query \
    --table-name PriceTrackerHistory \
    --key-condition-expression "product_id = :pid" \
    --expression-attribute-values '{"​:pid": {"S": "PRODUCT-ID"}}' \
    --query 'Items[*].[timestamp.S,price.N,price_change.N,price_change_percent.N]' \
    --output table
```

###  View Recent Alerts
```bash
aws dynamodb scan \
    --table-name PriceTrackerAlerts \
    --query 'Items[*].[product_id.S,alert_type.S,previous_price.N,current_price.N,price_change_percent.N,timestamp.S]' \
    --output table
```

##  TESTING & MONITORING

###  Test Price Tracking
```bash
# Run price tracker manually
aws lambda invoke \
    --function-name price-tracker-function \
    response.json && cat response.json && rm response.json
```

###  Test Analytics API
```bash
# Test products endpoint
echo '{"httpMethod": "GET", "path": "/products"}' > test.json
aws lambda invoke \
    --function-name price-tracker-function \
    --payload file://test.json \
    response.json && cat response.json && rm test.json response.json

# Test analytics for specific product
echo '{"httpMethod": "GET", "path": "/analytics", "queryStringParameters": {"product_id": "PRODUCT-ID"}}' > test.json
aws lambda invoke \
    --function-name price-tracker-function \
    --payload file://test.json \
    response.json && cat response.json && rm test.json response.json
```

###  View Recent Logs
```bash
# Get latest log stream
LOG_STREAM=$(aws logs describe-log-streams \
    --log-group-name /aws/lambda/price-tracker-function \
    --order-by LastEventTime \
    --descending \
    --max-items 1 \
    --query 'logStreams[0].logStreamName' \
    --output text)

# View recent logs
aws logs get-log-events \
    --log-group-name /aws/lambda/price-tracker-function \
    --log-stream-name "$LOG_STREAM" \
    --query 'events[-15:].message' \
    --output text
```

###  System Health Check
```bash
# Lambda function status
aws lambda get-function \
    --function-name price-tracker-function \
    --query '{State:Configuration.State,LastModified:Configuration.LastModified,CodeSize:Configuration.CodeSize}'

# Scheduled events
aws events list-rules \
    --query 'Rules[?contains(Name, `price-tracker`)].{Name:Name,State:State,Schedule:ScheduleExpression}' \
    --output table

# SNS topic
aws sns list-topics \
    --query 'Topics[?contains(TopicArn, `price-alerts`)].TopicArn'
```

##  CONFIGURATION

###  Update Alert Threshold
```bash
# Set to 10% change threshold
aws ssm put-parameter \
    --name "/price-tracker/alerts/price-change-threshold" \
    --value "0.10" \
    --type "String" \
    --overwrite

# Set to 3% change threshold  
aws ssm put-parameter \
    --name "/price-tracker/alerts/price-change-threshold" \
    --value "0.03" \
    --type "String" \
    --overwrite
```

###  Update Scraping Delay
```bash
# Set 3 second delay between requests
aws ssm put-parameter \
    --name "/price-tracker/scraping/delay-seconds" \
    --value "3" \
    --type "String" \
    --overwrite
```

##  QUICK EXAMPLES

### Example: Add Amazon Product
```bash
aws dynamodb put-item \
    --table-name PriceTrackerProducts \
    --item '{
        "product_id": {"S": "macbook-pro-m3"},
        "url": {"S": "https://www.amazon.co.uk/dp/B0CM5JV268"},
        "product_name": {"S": "MacBook Pro M3"},
        "active": {"BOOL": true},
        "created_at": {"S": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"}
    }'
```

### Example: Add eBay Product
```bash
aws dynamodb put-item \
    --table-name PriceTrackerProducts \
    --item '{
        "product_id": {"S": "ebay-laptop"},
        "url": {"S": "https://www.ebay.co.uk/itm/123456789"},
        "product_name": {"S": "Gaming Laptop"},
        "active": {"BOOL": true},
        "created_at": {"S": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"}
    }'
```

##  CLEANUP COMMANDS

### Remove Test Products
```bash
# Remove common test products
aws dynamodb delete-item --table-name PriceTrackerProducts --key '{"product_id": {"S": "test-httpbin"}}'
aws dynamodb delete-item --table-name PriceTrackerProducts --key '{"product_id": {"S": "test-simple"}}'
aws dynamodb delete-item --table-name PriceTrackerProducts --key '{"product_id": {"S": "amazon-monitors-search"}}'
```

### Clear All Alerts
```bash
# This will remove all alert history (use carefully!)
aws dynamodb scan --table-name PriceTrackerAlerts --query 'Items[*].alert_id.S' --output text | \
xargs -I {} aws dynamodb delete-item --table-name PriceTrackerAlerts --key '{"alert_id": {"S": "{}"}}'
```

##  USEFUL ONE-LINERS

### Quick Status Summary
```bash
echo "Active Products: $(aws dynamodb scan --table-name PriceTrackerProducts --filter-expression "active = :true" --expression-attribute-values '{":true": {"BOOL": true}}' --select "COUNT" --query 'Count' --output text)"
echo "Total Price Records: $(aws dynamodb scan --table-name PriceTrackerHistory --select "COUNT" --query 'Count' --output text)"
echo "Total Alerts: $(aws dynamodb scan --table-name PriceTrackerAlerts --select "COUNT" --query 'Count' --output text)"
```

### Find Products with Recent Price Changes
```bash
aws dynamodb scan \
    --table-name PriceTrackerProducts \
    --filter-expression "attribute_exists(last_updated) AND last_updated > :yesterday" \
    --expression-attribute-values '{"​:yesterday": {"S": "'$(date -u -d '1 day ago' +"%Y-%m-%dT%H:%M:%SZ")'"}}' \
    --query 'Items[*].[product_id.S,last_price.N,last_updated.S]' \
    --output table
```

---

##  Tips

- **Product IDs**: Use lowercase with hyphens (e.g., `macbook-pro-m3`)
- **URLs**: Use direct product URLs, avoid search pages
- **Testing**: Always test new products with manual price tracking
- **Monitoring**: Check logs after adding new products
- **Alerts**: Adjust threshold based on product volatility

##  Related Files

- **Management Script**: `manage_price_tracker.sh` (interactive menu)
- **Lambda Function**: `lambda_function.py` (main code)
- **Infrastructure**: `cloudformation.yaml` (AWS resources)
