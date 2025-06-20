#!/bin/bash

echo "🛑 Shutting down Price Tracker deployment..."

# Disable alarms
echo "📢 Disabling CloudWatch alarms..."
aws cloudwatch disable-alarm-actions --alarm-names PriceTracker-Lambda-Errors --region us-east-1 2>/dev/null
aws cloudwatch delete-alarms --alarm-names PriceTracker-Lambda-Errors --region us-east-1 2>/dev/null

# Disable EventBridge rules
echo "⏰ Disabling scheduled triggers..."
aws events disable-rule --name price-tracker-schedule --region us-east-1 2>/dev/null

# Delete Lambda
echo "🗑️  Deleting Lambda function..."
aws lambda delete-function --function-name price-tracker-function --region us-east-1 2>/dev/null

# Delete DynamoDB tables
echo "💾 Deleting DynamoDB tables..."
aws dynamodb delete-table --table-name PriceTrackerProducts --region us-east-1 2>/dev/null
aws dynamodb delete-table --table-name PriceTrackerHistory --region us-east-1 2>/dev/null
aws dynamodb delete-table --table-name PriceTrackerAlerts --region us-east-1 2>/dev/null

# Delete SNS topic
echo "📧 Deleting SNS topic..."
aws sns delete-topic --topic-arn arn:aws:sns:us-east-1:104299473694:price-alerts --region us-east-1 2>/dev/null

# Delete logs
echo "📝 Deleting CloudWatch logs..."
aws logs delete-log-group --log-group-name /aws/lambda/price-tracker-function --region us-east-1 2>/dev/null

echo "✅ Shutdown complete!"
echo ""
echo "Resources deleted:"
echo "- Lambda function: price-tracker-function"
echo "- DynamoDB tables: PriceTrackerProducts, PriceTrackerHistory, PriceTrackerAlerts"
echo "- SNS topic: price-alerts"
echo "- CloudWatch alarm: PriceTracker-Lambda-Errors"
echo "- CloudWatch logs: /aws/lambda/price-tracker-function"