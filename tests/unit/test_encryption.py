"""
Unit tests for KMS encryption utilities.

Tests encryption and decryption of OAuth tokens using AWS KMS.
"""

import base64
import pytest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError

from src.utils.encryption import (
    KMSEncryptionHelper,
    EncryptionError,
    encrypt_oauth_token,
    decrypt_oauth_token,
    encrypt_oauth_token_base64,
    decrypt_oauth_token_base64,
    get_encryption_helper,
)


@pytest.fixture
def mock_kms_client():
    """Create a mock KMS client."""
    return Mock()


@pytest.fixture
def encryption_helper(mock_kms_client):
    """Create an encryption helper with mocked KMS client."""
    with patch("boto3.client", return_value=mock_kms_client):
        helper = KMSEncryptionHelper(kms_key_alias="alias/test-key", aws_region="us-east-1")
    return helper


class TestKMSEncryptionHelper:
    """Tests for KMSEncryptionHelper class."""

    def test_initialization_with_defaults(self):
        """Test helper initialization with default settings."""
        with patch("boto3.client") as mock_boto_client:
            helper = KMSEncryptionHelper()

            assert helper.kms_key_alias == "alias/fitagent-oauth-key"
            assert helper.aws_region == "us-east-1"
            mock_boto_client.assert_called_once()

    def test_initialization_with_custom_values(self):
        """Test helper initialization with custom values."""
        with patch("boto3.client") as mock_boto_client:
            helper = KMSEncryptionHelper(
                kms_key_alias="alias/custom-key",
                aws_region="us-west-2",
                aws_endpoint_url="http://localhost:4566",
            )

            assert helper.kms_key_alias == "alias/custom-key"
            assert helper.aws_region == "us-west-2"

            # Verify endpoint URL was passed to boto3 client
            call_kwargs = mock_boto_client.call_args[1]
            assert call_kwargs["endpoint_url"] == "http://localhost:4566"

    def test_encrypt_success(self, encryption_helper, mock_kms_client):
        """Test successful encryption."""
        plaintext = "my-oauth-refresh-token"
        expected_ciphertext = b"encrypted-data-blob"

        mock_kms_client.encrypt.return_value = {"CiphertextBlob": expected_ciphertext}

        result = encryption_helper.encrypt(plaintext)

        assert result == expected_ciphertext
        mock_kms_client.encrypt.assert_called_once_with(
            KeyId="alias/test-key", Plaintext=plaintext.encode("utf-8")
        )

    def test_encrypt_empty_plaintext(self, encryption_helper):
        """Test encryption with empty plaintext raises error."""
        with pytest.raises(EncryptionError, match="Cannot encrypt empty plaintext"):
            encryption_helper.encrypt("")

    def test_encrypt_kms_client_error(self, encryption_helper, mock_kms_client):
        """Test encryption handles KMS client errors."""
        mock_kms_client.encrypt.side_effect = ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "Key not found"}}, "Encrypt"
        )

        with pytest.raises(EncryptionError, match="KMS encryption failed: NotFoundException"):
            encryption_helper.encrypt("test-token")

    def test_encrypt_unexpected_error(self, encryption_helper, mock_kms_client):
        """Test encryption handles unexpected errors."""
        mock_kms_client.encrypt.side_effect = Exception("Unexpected error")

        with pytest.raises(EncryptionError, match="Unexpected encryption error"):
            encryption_helper.encrypt("test-token")

    def test_decrypt_success(self, encryption_helper, mock_kms_client):
        """Test successful decryption."""
        ciphertext = b"encrypted-data-blob"
        expected_plaintext = "my-oauth-refresh-token"

        mock_kms_client.decrypt.return_value = {"Plaintext": expected_plaintext.encode("utf-8")}

        result = encryption_helper.decrypt(ciphertext)

        assert result == expected_plaintext
        mock_kms_client.decrypt.assert_called_once_with(CiphertextBlob=ciphertext)

    def test_decrypt_empty_ciphertext(self, encryption_helper):
        """Test decryption with empty ciphertext raises error."""
        with pytest.raises(EncryptionError, match="Cannot decrypt empty ciphertext"):
            encryption_helper.decrypt(b"")

    def test_decrypt_kms_client_error(self, encryption_helper, mock_kms_client):
        """Test decryption handles KMS client errors."""
        mock_kms_client.decrypt.side_effect = ClientError(
            {"Error": {"Code": "InvalidCiphertextException", "Message": "Invalid ciphertext"}},
            "Decrypt",
        )

        with pytest.raises(
            EncryptionError, match="KMS decryption failed: InvalidCiphertextException"
        ):
            encryption_helper.decrypt(b"invalid-ciphertext")

    def test_decrypt_unexpected_error(self, encryption_helper, mock_kms_client):
        """Test decryption handles unexpected errors."""
        mock_kms_client.decrypt.side_effect = Exception("Unexpected error")

        with pytest.raises(EncryptionError, match="Unexpected decryption error"):
            encryption_helper.decrypt(b"test-ciphertext")

    def test_encrypt_to_base64_success(self, encryption_helper, mock_kms_client):
        """Test encryption to base64 string."""
        plaintext = "my-oauth-refresh-token"
        ciphertext_blob = b"encrypted-data-blob"

        mock_kms_client.encrypt.return_value = {"CiphertextBlob": ciphertext_blob}

        result = encryption_helper.encrypt_to_base64(plaintext)

        # Verify result is base64-encoded
        expected_base64 = base64.b64encode(ciphertext_blob).decode("utf-8")
        assert result == expected_base64

        # Verify it can be decoded back
        decoded = base64.b64decode(result)
        assert decoded == ciphertext_blob

    def test_decrypt_from_base64_success(self, encryption_helper, mock_kms_client):
        """Test decryption from base64 string."""
        ciphertext_blob = b"encrypted-data-blob"
        base64_ciphertext = base64.b64encode(ciphertext_blob).decode("utf-8")
        expected_plaintext = "my-oauth-refresh-token"

        mock_kms_client.decrypt.return_value = {"Plaintext": expected_plaintext.encode("utf-8")}

        result = encryption_helper.decrypt_from_base64(base64_ciphertext)

        assert result == expected_plaintext
        mock_kms_client.decrypt.assert_called_once_with(CiphertextBlob=ciphertext_blob)

    def test_decrypt_from_base64_invalid_encoding(self, encryption_helper):
        """Test decryption from invalid base64 raises error."""
        with pytest.raises(EncryptionError, match="Invalid base64 encoding"):
            encryption_helper.decrypt_from_base64("not-valid-base64!!!")

    def test_encrypt_decrypt_roundtrip(self, encryption_helper, mock_kms_client):
        """Test encryption and decryption roundtrip."""
        original_token = "my-oauth-refresh-token-12345"
        ciphertext_blob = b"encrypted-data-blob"

        # Mock encrypt
        mock_kms_client.encrypt.return_value = {"CiphertextBlob": ciphertext_blob}

        # Mock decrypt
        mock_kms_client.decrypt.return_value = {"Plaintext": original_token.encode("utf-8")}

        # Encrypt
        encrypted = encryption_helper.encrypt(original_token)
        assert encrypted == ciphertext_blob

        # Decrypt
        decrypted = encryption_helper.decrypt(encrypted)
        assert decrypted == original_token

    def test_encrypt_decrypt_base64_roundtrip(self, encryption_helper, mock_kms_client):
        """Test base64 encryption and decryption roundtrip."""
        original_token = "my-oauth-refresh-token-12345"
        ciphertext_blob = b"encrypted-data-blob"

        # Mock encrypt
        mock_kms_client.encrypt.return_value = {"CiphertextBlob": ciphertext_blob}

        # Mock decrypt
        mock_kms_client.decrypt.return_value = {"Plaintext": original_token.encode("utf-8")}

        # Encrypt to base64
        encrypted_base64 = encryption_helper.encrypt_to_base64(original_token)
        assert isinstance(encrypted_base64, str)

        # Decrypt from base64
        decrypted = encryption_helper.decrypt_from_base64(encrypted_base64)
        assert decrypted == original_token


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_encryption_helper_singleton(self):
        """Test that get_encryption_helper returns singleton instance."""
        with patch("boto3.client"):
            helper1 = get_encryption_helper()
            helper2 = get_encryption_helper()

            assert helper1 is helper2

    def test_encrypt_oauth_token(self):
        """Test encrypt_oauth_token convenience function."""
        token = "test-refresh-token"
        expected_ciphertext = b"encrypted-blob"

        with patch("src.utils.encryption.get_encryption_helper") as mock_get_helper:
            mock_helper = Mock()
            mock_helper.encrypt.return_value = expected_ciphertext
            mock_get_helper.return_value = mock_helper

            result = encrypt_oauth_token(token)

            assert result == expected_ciphertext
            mock_helper.encrypt.assert_called_once_with(token)

    def test_decrypt_oauth_token(self):
        """Test decrypt_oauth_token convenience function."""
        ciphertext = b"encrypted-blob"
        expected_token = "test-refresh-token"

        with patch("src.utils.encryption.get_encryption_helper") as mock_get_helper:
            mock_helper = Mock()
            mock_helper.decrypt.return_value = expected_token
            mock_get_helper.return_value = mock_helper

            result = decrypt_oauth_token(ciphertext)

            assert result == expected_token
            mock_helper.decrypt.assert_called_once_with(ciphertext)

    def test_encrypt_oauth_token_base64(self):
        """Test encrypt_oauth_token_base64 convenience function."""
        token = "test-refresh-token"
        expected_base64 = "ZW5jcnlwdGVkLWJsb2I="

        with patch("src.utils.encryption.get_encryption_helper") as mock_get_helper:
            mock_helper = Mock()
            mock_helper.encrypt_to_base64.return_value = expected_base64
            mock_get_helper.return_value = mock_helper

            result = encrypt_oauth_token_base64(token)

            assert result == expected_base64
            mock_helper.encrypt_to_base64.assert_called_once_with(token)

    def test_decrypt_oauth_token_base64(self):
        """Test decrypt_oauth_token_base64 convenience function."""
        base64_ciphertext = "ZW5jcnlwdGVkLWJsb2I="
        expected_token = "test-refresh-token"

        with patch("src.utils.encryption.get_encryption_helper") as mock_get_helper:
            mock_helper = Mock()
            mock_helper.decrypt_from_base64.return_value = expected_token
            mock_get_helper.return_value = mock_helper

            result = decrypt_oauth_token_base64(base64_ciphertext)

            assert result == expected_token
            mock_helper.decrypt_from_base64.assert_called_once_with(base64_ciphertext)


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_encrypt_unicode_characters(self, encryption_helper, mock_kms_client):
        """Test encryption with unicode characters."""
        plaintext = "token-with-émojis-🔐-and-spëcial-çhars"
        ciphertext_blob = b"encrypted-unicode-data"

        mock_kms_client.encrypt.return_value = {"CiphertextBlob": ciphertext_blob}

        result = encryption_helper.encrypt(plaintext)

        assert result == ciphertext_blob
        # Verify UTF-8 encoding was used
        mock_kms_client.encrypt.assert_called_once()
        call_args = mock_kms_client.encrypt.call_args[1]
        assert call_args["Plaintext"] == plaintext.encode("utf-8")

    def test_encrypt_very_long_token(self, encryption_helper, mock_kms_client):
        """Test encryption with very long token."""
        plaintext = "x" * 10000  # 10KB token
        ciphertext_blob = b"encrypted-long-data"

        mock_kms_client.encrypt.return_value = {"CiphertextBlob": ciphertext_blob}

        result = encryption_helper.encrypt(plaintext)

        assert result == ciphertext_blob

    def test_decrypt_binary_with_null_bytes(self, encryption_helper, mock_kms_client):
        """Test decryption of ciphertext containing null bytes."""
        ciphertext = b"\x00\x01\x02\x03encrypted-data\x00"
        expected_plaintext = "test-token"

        mock_kms_client.decrypt.return_value = {"Plaintext": expected_plaintext.encode("utf-8")}

        result = encryption_helper.decrypt(ciphertext)

        assert result == expected_plaintext
