# C:\bdo-orders-platform\backend\app\services\alerts.py
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

from app.core.settings import settings

# Initialize AWS clients for LocalStack
def get_sns_client():
    return boto3.client(
        'sns',
        endpoint_url=settings.aws_endpoint_url,
        region_name=settings.aws_region,
        aws_access_key_id='test',
        aws_secret_access_key='test'
    )

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=settings.aws_endpoint_url,
        region_name=settings.aws_region,
        aws_access_key_id='test',
        aws_secret_access_key='test'
    )

def sns_notify(subject: str, data: Dict[str, Any]) -> bool:
    """Send SNS notification"""
    try:
        sns = get_sns_client()
        message = json.dumps(data, default=str, indent=2)
        
        response = sns.publish(
            TopicArn=settings.aws_sns_topic_arn,
            Subject=subject,
            Message=message
        )
        print(f"[SNS] Notification sent: {subject} - MessageId: {response.get('MessageId')}")
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NotFound':
            print(f"[SNS] Topic not found: {settings.aws_sns_topic_arn}")
        else:
            print(f"[SNS] Error: {e}")
        return False
    except Exception as e:
        print(f"[SNS] Unexpected error: {e}")
        return False

def s3_put_object(prefix: str, data: Dict[str, Any]) -> str:
    """Store data in S3 and return the key"""
    try:
        s3 = get_s3_client()
        
        # First check if bucket exists, create if not
        try:
            s3.head_bucket(Bucket=settings.aws_s3_bucket)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                print(f"[S3] Bucket doesn't exist, creating: {settings.aws_s3_bucket}")
                s3.create_bucket(
                    Bucket=settings.aws_s3_bucket,
                    CreateBucketConfiguration={'LocationConstraint': settings.aws_region}
                    if settings.aws_region != 'us-east-1' else {}
                )
            else:
                raise
        
        # Generate unique key
        timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H")
        unique_id = str(uuid.uuid4())[:8]
        key = f"{prefix}/{timestamp}/{unique_id}.json"
        
        # Convert data to JSON
        content = json.dumps(data, default=str, indent=2)
        
        # Put object
        s3.put_object(
            Bucket=settings.aws_s3_bucket,
            Key=key,
            Body=content,
            ContentType='application/json'
        )
        
        print(f"[S3] Object stored: s3://{settings.aws_s3_bucket}/{key}")
        return key
        
    except Exception as e:
        print(f"[S3] Error: {e}")
        raise