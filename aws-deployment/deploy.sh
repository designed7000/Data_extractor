#!/bin/bash

# Quick fix for CloudFormation deployment
# Run this after the package has been created successfully

set -e

echo "🔧 Quick CloudFormation Deployment Fix"
echo "======================================"

STACK_NAME="price-tracker-stack"

# Check if CloudFormation template exists
if [ ! -f "cloudformation.yaml" ]; then
    echo "❌ cloudformation.yaml not found in current directory"
    echo "Please make sure you're in the aws-deployment directory"
    exit 1
fi

echo "📋 Deploying CloudFormation stack without parameters..."

# Deploy stack without the problematic parameters
if aws cloudformation describe-stacks --stack-name $STACK_NAME >/dev/null 2>&1; then
    echo "📋 Stack exists, updating..."
    aws cloudformation update-stack \
        --stack-name $STACK_NAME \
        --template-body file://cloudformation.yaml \
        --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
else
    echo "📋 Creating new stack..."
    aws cloudformation create-stack \
        --stack-name $STACK_NAME \
        --template-body file://cloudformation.yaml \
        --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
fi

echo "⏳ Waiting for stack deployment to complete..."
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME 2>/dev/null || \
aws cloudformation wait stack-update-complete --stack-name $STACK_NAME

echo "✅ Stack deployment completed!"

# Get the Lambda function name from stack outputs
LAMBDA_FUNCTION_NAME=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
    --output text 2>/dev/null || echo "price-tracker-function")

echo "📋 Lambda function name: $LAMBDA_FUNCTION_NAME"

# Update Lambda function code (the package should already exist)
if [ -f "lambda-deployment-package.zip" ]; then
    echo "🔄 Updating Lambda function code..."
    aws lambda update-function-code \
        --function-name $LAMBDA_FUNCTION_NAME \
        --zip-file fileb://lambda-deployment-package.zip

    echo "⚙️  Updating Lambda function configuration..."
    aws lambda update-function-configuration \
        --function-name $LAMBDA_FUNCTION_NAME \
        --timeout 300 \
        --memory-size 512 \
        --environment Variables='{
            "ENVIRONMENT":"production",
            "LOG_LEVEL":"INFO"
        }'
else
    echo "❌ lambda-deployment-package.zip not found!"
    echo "Please run the main deploy script first to create the package"
    exit 1
fi

# Set up Parameter Store values
echo "📝 Configuring Parameter Store..."
aws ssm put-parameter \
    --name "/price-tracker/scraping/user-agent" \
    --value "Mozilla/5.0 (compatible; PriceTracker/1.0)" \
    --type "String" \
    --overwrite >/dev/null 2>&1 || echo "Note: Parameter may already exist"

aws ssm put-parameter \
    --name "/price-tracker/scraping/delay-seconds" \
    --value "2" \
    --type "String" \
    --overwrite >/dev/null 2>&1 || echo "Note: Parameter may already exist"

aws ssm put-parameter \
    --name "/price-tracker/alerts/price-change-threshold" \
    --value "0.05" \
    --type "String" \
    --overwrite >/dev/null 2>&1 || echo "Note: Parameter may already exist"

# Test the Lambda function
echo "🧪 Testing Lambda function..."
aws lambda invoke \
    --function-name $LAMBDA_FUNCTION_NAME \
    --payload '{"test": true}' \
    response.json

echo "📋 Test response:"
cat response.json
echo ""

# Get stack outputs
echo "📊 Deployment Summary:"
echo "======================"
aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

echo ""
echo "✅ Quick deployment fix completed successfully!"
echo ""
echo "🎯 Next Steps:"
echo "1. Update the NotificationEmail parameter in your CloudFormation template"
echo "2. Check your email for SNS subscription confirmation"
echo "3. Add products to track using the DynamoDB console"
echo "4. Monitor CloudWatch logs for execution details"

# Cleanup
rm -f response.json
echo "🧹 Cleanup completed"