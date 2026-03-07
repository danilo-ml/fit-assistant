"""
Example usage of KMS encryption utilities for OAuth tokens.

This example demonstrates how to encrypt and decrypt OAuth refresh tokens
using the encryption utilities.
"""

from src.utils.encryption import (
    KMSEncryptionHelper,
    encrypt_oauth_token,
    decrypt_oauth_token,
    encrypt_oauth_token_base64,
    decrypt_oauth_token_base64,
    EncryptionError,
)


def example_basic_usage():
    """Example: Basic encryption and decryption."""
    print("=== Basic Usage Example ===\n")

    # Simulate an OAuth refresh token
    refresh_token = "ya29.a0AfH6SMBx_example_refresh_token_12345"

    try:
        # Encrypt the token (returns bytes)
        encrypted_token = encrypt_oauth_token(refresh_token)
        print(f"Original token: {refresh_token}")
        print(f"Encrypted (bytes): {encrypted_token[:50]}...")
        print(f"Encrypted length: {len(encrypted_token)} bytes\n")

        # Decrypt the token
        decrypted_token = decrypt_oauth_token(encrypted_token)
        print(f"Decrypted token: {decrypted_token}")
        print(f"Tokens match: {refresh_token == decrypted_token}\n")

    except EncryptionError as e:
        print(f"Encryption error: {e}\n")


def example_base64_usage():
    """Example: Base64 encoding for string storage."""
    print("=== Base64 Encoding Example ===\n")

    refresh_token = "ya29.a0AfH6SMBx_example_refresh_token_67890"

    try:
        # Encrypt to base64 string (useful for DynamoDB string attributes)
        encrypted_base64 = encrypt_oauth_token_base64(refresh_token)
        print(f"Original token: {refresh_token}")
        print(f"Encrypted (base64): {encrypted_base64[:50]}...")
        print(f"Type: {type(encrypted_base64)}\n")

        # Decrypt from base64
        decrypted_token = decrypt_oauth_token_base64(encrypted_base64)
        print(f"Decrypted token: {decrypted_token}")
        print(f"Tokens match: {refresh_token == decrypted_token}\n")

    except EncryptionError as e:
        print(f"Encryption error: {e}\n")


def example_custom_helper():
    """Example: Using KMSEncryptionHelper with custom configuration."""
    print("=== Custom Helper Example ===\n")

    # Create helper with custom configuration (e.g., for LocalStack)
    helper = KMSEncryptionHelper(
        kms_key_alias="alias/fitagent-oauth-key",
        aws_region="us-east-1",
        aws_endpoint_url="http://localhost:4566",  # LocalStack endpoint
    )

    refresh_token = "ya29.a0AfH6SMBx_custom_example_token"

    try:
        # Encrypt
        encrypted = helper.encrypt(refresh_token)
        print(f"Encrypted with custom helper: {encrypted[:50]}...")

        # Decrypt
        decrypted = helper.decrypt(encrypted)
        print(f"Decrypted: {decrypted}")
        print(f"Tokens match: {refresh_token == decrypted}\n")

    except EncryptionError as e:
        print(f"Encryption error: {e}\n")


def example_dynamodb_storage():
    """Example: Simulating DynamoDB storage pattern."""
    print("=== DynamoDB Storage Pattern Example ===\n")

    trainer_id = "550e8400-e29b-41d4-a716-446655440000"
    refresh_token = "ya29.a0AfH6SMBx_google_refresh_token"

    try:
        # Encrypt for storage
        encrypted_token = encrypt_oauth_token(refresh_token)

        # Simulate DynamoDB item
        dynamodb_item = {
            "PK": f"TRAINER#{trainer_id}",
            "SK": "CALENDAR_CONFIG",
            "entity_type": "CALENDAR_CONFIG",
            "trainer_id": trainer_id,
            "provider": "google",
            "encrypted_refresh_token": encrypted_token,
            "scope": "https://www.googleapis.com/auth/calendar",
        }

        print("DynamoDB Item (simulated):")
        print(f"  PK: {dynamodb_item['PK']}")
        print(f"  SK: {dynamodb_item['SK']}")
        print(f"  provider: {dynamodb_item['provider']}")
        print(f"  encrypted_refresh_token: {str(encrypted_token[:50])}...")
        print()

        # Simulate retrieval and decryption
        retrieved_encrypted = dynamodb_item["encrypted_refresh_token"]
        decrypted_token = decrypt_oauth_token(retrieved_encrypted)

        print(f"Retrieved and decrypted token: {decrypted_token}")
        print(f"Tokens match: {refresh_token == decrypted_token}\n")

    except EncryptionError as e:
        print(f"Encryption error: {e}\n")


def example_error_handling():
    """Example: Error handling."""
    print("=== Error Handling Example ===\n")

    try:
        # Attempt to encrypt empty string
        encrypt_oauth_token("")
    except EncryptionError as e:
        print(f"Expected error for empty plaintext: {e}\n")

    try:
        # Attempt to decrypt empty bytes
        decrypt_oauth_token(b"")
    except EncryptionError as e:
        print(f"Expected error for empty ciphertext: {e}\n")

    try:
        # Attempt to decrypt invalid base64
        decrypt_oauth_token_base64("not-valid-base64!!!")
    except EncryptionError as e:
        print(f"Expected error for invalid base64: {e}\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("KMS Encryption Utilities - Usage Examples")
    print("=" * 70 + "\n")

    print("NOTE: These examples require a running KMS service.")
    print("For local development, ensure LocalStack is running with KMS enabled.\n")

    # Run examples
    example_basic_usage()
    example_base64_usage()
    example_custom_helper()
    example_dynamodb_storage()
    example_error_handling()

    print("=" * 70)
    print("Examples completed!")
    print("=" * 70 + "\n")
