"""
KMS encryption utilities for OAuth tokens and sensitive data.

This module provides helpers for encrypting and decrypting sensitive data
using AWS KMS, specifically designed for OAuth refresh tokens stored in DynamoDB.
"""

import base64
from typing import Optional
import boto3
from botocore.exceptions import ClientError

from src.config import settings


class EncryptionError(Exception):
    """Base exception for encryption-related errors."""

    pass


class KMSEncryptionHelper:
    """Helper class for KMS encryption and decryption operations."""

    def __init__(
        self,
        kms_key_alias: Optional[str] = None,
        aws_region: Optional[str] = None,
        aws_endpoint_url: Optional[str] = None,
    ):
        """
        Initialize KMS encryption helper.

        Args:
            kms_key_alias: KMS key alias (e.g., 'alias/fitagent-oauth-key')
            aws_region: AWS region for KMS client
            aws_endpoint_url: Optional endpoint URL for LocalStack
        """
        self.kms_key_alias = kms_key_alias or settings.kms_key_alias
        self.aws_region = aws_region or settings.aws_region

        # Initialize KMS client
        client_config = {"region_name": self.aws_region}

        # Add endpoint URL for LocalStack
        if aws_endpoint_url or settings.aws_endpoint_url:
            client_config["endpoint_url"] = aws_endpoint_url or settings.aws_endpoint_url

        self.kms_client = boto3.client("kms", **client_config)

    def encrypt(self, plaintext: str) -> bytes:
        """
        Encrypt plaintext string using KMS.

        Args:
            plaintext: The plaintext string to encrypt (e.g., OAuth refresh token)

        Returns:
            bytes: Encrypted ciphertext blob

        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            raise EncryptionError("Cannot encrypt empty plaintext")

        try:
            response = self.kms_client.encrypt(
                KeyId=self.kms_key_alias, Plaintext=plaintext.encode("utf-8")
            )
            return response["CiphertextBlob"]
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            raise EncryptionError(f"KMS encryption failed: {error_code} - {error_message}") from e
        except Exception as e:
            raise EncryptionError(f"Unexpected encryption error: {str(e)}") from e

    def decrypt(self, ciphertext: bytes) -> str:
        """
        Decrypt ciphertext blob using KMS.

        Args:
            ciphertext: The encrypted ciphertext blob

        Returns:
            str: Decrypted plaintext string

        Raises:
            EncryptionError: If decryption fails
        """
        if not ciphertext:
            raise EncryptionError("Cannot decrypt empty ciphertext")

        try:
            response = self.kms_client.decrypt(CiphertextBlob=ciphertext)
            return response["Plaintext"].decode("utf-8")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            raise EncryptionError(f"KMS decryption failed: {error_code} - {error_message}") from e
        except Exception as e:
            raise EncryptionError(f"Unexpected decryption error: {str(e)}") from e

    def encrypt_to_base64(self, plaintext: str) -> str:
        """
        Encrypt plaintext and return as base64-encoded string.

        Useful for storing encrypted data as strings in DynamoDB.

        Args:
            plaintext: The plaintext string to encrypt

        Returns:
            str: Base64-encoded encrypted ciphertext

        Raises:
            EncryptionError: If encryption fails
        """
        ciphertext_blob = self.encrypt(plaintext)
        return base64.b64encode(ciphertext_blob).decode("utf-8")

    def decrypt_from_base64(self, base64_ciphertext: str) -> str:
        """
        Decrypt base64-encoded ciphertext.

        Args:
            base64_ciphertext: Base64-encoded encrypted ciphertext

        Returns:
            str: Decrypted plaintext string

        Raises:
            EncryptionError: If decryption fails
        """
        try:
            ciphertext_blob = base64.b64decode(base64_ciphertext)
        except Exception as e:
            raise EncryptionError(f"Invalid base64 encoding: {str(e)}") from e

        return self.decrypt(ciphertext_blob)


# Global instance for convenience
_default_helper: Optional[KMSEncryptionHelper] = None


def get_encryption_helper() -> KMSEncryptionHelper:
    """
    Get or create the default KMS encryption helper instance.

    Returns:
        KMSEncryptionHelper: Singleton encryption helper instance
    """
    global _default_helper
    if _default_helper is None:
        _default_helper = KMSEncryptionHelper()
    return _default_helper


def encrypt_oauth_token(refresh_token: str) -> bytes:
    """
    Encrypt OAuth refresh token for storage in DynamoDB.

    Args:
        refresh_token: OAuth refresh token to encrypt

    Returns:
        bytes: Encrypted token as binary blob

    Raises:
        EncryptionError: If encryption fails
    """
    helper = get_encryption_helper()
    return helper.encrypt(refresh_token)


def decrypt_oauth_token(encrypted_token: bytes) -> str:
    """
    Decrypt OAuth refresh token from DynamoDB storage.

    Args:
        encrypted_token: Encrypted token binary blob

    Returns:
        str: Decrypted refresh token

    Raises:
        EncryptionError: If decryption fails
    """
    helper = get_encryption_helper()
    return helper.decrypt(encrypted_token)


def encrypt_oauth_token_base64(refresh_token: str) -> str:
    """
    Encrypt OAuth refresh token and return as base64 string.

    Args:
        refresh_token: OAuth refresh token to encrypt

    Returns:
        str: Base64-encoded encrypted token

    Raises:
        EncryptionError: If encryption fails
    """
    helper = get_encryption_helper()
    return helper.encrypt_to_base64(refresh_token)


def decrypt_oauth_token_base64(base64_encrypted_token: str) -> str:
    """
    Decrypt base64-encoded OAuth refresh token.

    Args:
        base64_encrypted_token: Base64-encoded encrypted token

    Returns:
        str: Decrypted refresh token

    Raises:
        EncryptionError: If decryption fails
    """
    helper = get_encryption_helper()
    return helper.decrypt_from_base64(base64_encrypted_token)
