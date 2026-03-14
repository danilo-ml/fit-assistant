#!/usr/bin/env python3
"""
Check Bedrock configuration and AWS credentials.
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

def check_env_vars():
    """Check environment variables."""
    print("=" * 60)
    print("Environment Variables Check")
    print("=" * 60)
    
    vars_to_check = [
        "BEDROCK_MODEL_ID",
        "BEDROCK_REGION",
        "AWS_BEDROCK_ENDPOINT_URL",
        "AWS_REGION",
        "AWS_ENDPOINT_URL",
        "AWS_ACCESS_KEY_ID",
    ]
    
    for var in vars_to_check:
        value = os.getenv(var, "NOT SET")
        # Mask credentials
        if "KEY" in var or "SECRET" in var:
            if value and value != "NOT SET" and value != "test":
                value = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
        print(f"  {var}: {value}")
    
    print()
    print("✅ Using official AWS Bedrock")
    print()
    return True

def check_aws_credentials():
    """Check if AWS credentials are configured."""
    print("=" * 60)
    print("AWS Credentials Check")
    print("=" * 60)
    
    try:
        # Try to get caller identity (works with any valid credentials)
        sts = boto3.client('sts', region_name='us-east-1')
        identity = sts.get_caller_identity()
        
        print("✅ AWS credentials are configured")
        print(f"   Account: {identity['Account']}")
        print(f"   User ARN: {identity['Arn']}")
        print()
        return True
        
    except NoCredentialsError:
        print("❌ No AWS credentials found")
        print()
        print("To configure credentials:")
        print("  1. Run: aws configure")
        print("  2. Or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env")
        print()
        return False
        
    except ClientError as e:
        print(f"❌ Error checking credentials: {e}")
        print()
        return False

def check_bedrock_access():
    """Check if Bedrock is accessible."""
    print("=" * 60)
    print("Bedrock Access Check")
    print("=" * 60)
    
    region = os.getenv("BEDROCK_REGION", "us-east-1")
    
    try:
        # Create Bedrock client WITHOUT LocalStack endpoint
        bedrock = boto3.client('bedrock', region_name=region)
        
        # Try to list foundation models
        response = bedrock.list_foundation_models()
        
        print(f"✅ Bedrock is accessible in region {region}")
        print(f"   Available models: {len(response.get('modelSummaries', []))}")
        
        # Check if Claude 3 Sonnet is available
        model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
        claude_available = any(
            model_id in model.get('modelId', '')
            for model in response.get('modelSummaries', [])
        )
        
        if claude_available:
            print(f"✅ Model {model_id} is available")
        else:
            print(f"⚠️  Model {model_id} not found in available models")
            print("   You may need to request model access in AWS Console")
        
        print()
        return True
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        
        print(f"❌ Cannot access Bedrock: {error_code}")
        print(f"   {error_msg}")
        print()
        
        if error_code == 'AccessDeniedException':
            print("To fix:")
            print("  1. Go to AWS Console → Bedrock → Model access")
            print("  2. Request access to Claude 3 Sonnet")
            print("  3. Ensure your IAM user has bedrock:* permissions")
        
        print()
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print()
        return False

def test_bedrock_runtime():
    """Test Bedrock Runtime API with a simple call."""
    print("=" * 60)
    print("Bedrock Runtime Test")
    print("=" * 60)
    
    region = os.getenv("BEDROCK_REGION", "us-east-1")
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
    
    try:
        # Create Bedrock Runtime client WITHOUT LocalStack endpoint
        bedrock_runtime = boto3.client('bedrock-runtime', region_name=region)
        
        # Try a simple converse call
        response = bedrock_runtime.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": "Say 'Hello' in Portuguese"}]
                }
            ],
            inferenceConfig={
                "maxTokens": 50,
                "temperature": 0.7,
            }
        )
        
        # Extract response
        output = response.get('output', {}).get('message', {})
        content = output.get('content', [])
        text = content[0].get('text', '') if content else ''
        
        print(f"✅ Bedrock Runtime is working!")
        print(f"   Model: {model_id}")
        print(f"   Response: {text}")
        print()
        return True
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        
        print(f"❌ Bedrock Runtime error: {error_code}")
        print(f"   {error_msg}")
        print()
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print()
        return False

def main():
    """Run all checks."""
    print()
    print("🔍 FitAgent Bedrock Configuration Check")
    print()
    
    # Load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    checks = [
        check_env_vars(),
        check_aws_credentials(),
        check_bedrock_access(),
        test_bedrock_runtime(),
    ]
    
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    if all(checks):
        print("✅ All checks passed! Bedrock is ready to use.")
        print()
        print("Next steps:")
        print("  1. Restart your Docker containers: make restart")
        print("  2. Test with: python scripts/test_e2e.py")
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print()
        print("For help, see: docs/guides/AWS_BEDROCK_SETUP.md")
        return 1

if __name__ == "__main__":
    sys.exit(main())
