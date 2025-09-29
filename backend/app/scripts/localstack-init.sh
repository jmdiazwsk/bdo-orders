#!/bin/bash
# scripts/localstack-init.sh

echo "Initializing LocalStack resources..."

# Create SNS Topic
aws --endpoint-url=http://localhost:4566 sns create-topic \
  --name bdo-alerts \
  --region eu-west-1

# Create S3 Bucket
aws --endpoint-url=http://localhost:4566 s3 mb \
  s3://bdo-orders \
  --region eu-west-1

echo "LocalStack initialization completed."