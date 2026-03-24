# Implementation Plan: Google OAuth Consent Screen Workflow

## Overview

Implement the complete Google OAuth consent screen workflow for FitAgent, adding the missing `disconnect_calendar` and `get_calendar_status` tools, and comprehensive test coverage via property-based and unit tests. The existing codebase already handles OAuth flow initiation (`connect_calendar`), callback processing (`oauth_callback.py`), token refresh, and calendar sync with retry logic. This plan focuses on the new tools and thorough testing of all correctness properties.

## Tasks

- [x] 1. Implement `disconnect_calendar` tool
  - [x] 1.1 Add `disconnect_calendar` function to `src/tools/calendar_tools.py`
    - Retrieve calendar config from DynamoDB via `dynamodb_client.get_calendar_config(trainer_id)`
    - Return `success=False` if no calendar config exists
    - Decrypt refresh token using `decrypt_oauth_token_base64`
    - Call Google revocation endpoint `https://oauth2.googleapis.com/revoke` with the token
    - Delete CALENDAR_CONFIG from DynamoDB regardless of revocation success/failure
    - Log revocation failures but do not raise exceptions
    - Return `{'success': True, 'data': {'provider': str, 'disconnected': True}}`
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 1.2 Write property test for disconnect (Property 10)
    - **Property 10: Disconnect deletes config regardless of revocation outcome**
    - Create `tests/property/test_oauth_disconnect_properties.py`
    - Mock Google revocation endpoint to succeed and fail
    - Verify CALENDAR_CONFIG is deleted from DynamoDB in both cases
    - **Validates: Requirements 6.2, 6.4**

  - [ ]* 1.3 Write unit tests for `disconnect_calendar`
    - Add tests to `tests/unit/test_calendar_tools.py`
    - Test: no calendar config returns `success=False`
    - Test: successful revocation + config deletion
    - Test: failed revocation still deletes config
    - Test: WhatsApp confirmation message content
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 2. Implement `get_calendar_status` tool
  - [x] 2.1 Add `get_calendar_status` function to `src/tools/calendar_tools.py`
    - Retrieve calendar config from DynamoDB
    - Return `connected=True` with `provider` and `connected_at` when config exists
    - Return `connected=False` with `provider=None` and `connected_at=None` when no config
    - Validate trainer exists before querying config
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ]* 2.2 Write property test for calendar status (Property 11)
    - **Property 11: Calendar status reflects DynamoDB state**
    - Create `tests/property/test_oauth_status_properties.py`
    - Generate random trainer IDs with and without calendar configs
    - Verify `connected` field matches presence of CALENDAR_CONFIG in DynamoDB
    - Verify `provider` and `connected_at` values match stored config
    - **Validates: Requirements 7.1, 7.2, 7.3**

  - [ ]* 2.3 Write unit tests for `get_calendar_status`
    - Add tests to `tests/unit/test_calendar_tools.py`
    - Test: connected status returns provider and date
    - Test: not connected returns None fields
    - Test: trainer not found returns error
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 3. Checkpoint - Verify new tools
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Property tests for OAuth flow initiation
  - [ ]* 4.1 Write property test for OAuth URL parameters (Property 1)
    - **Property 1: OAuth URL contains all required parameters**
    - Create `tests/property/test_oauth_flow_properties.py`
    - Mock DynamoDB (trainer exists) and settings (Google credentials configured)
    - For random valid trainer IDs, verify returned URL contains `scope`, `access_type=offline`, `prompt=consent`, `redirect_uri`, `client_id`, `response_type=code`, and non-empty `state`
    - **Validates: Requirements 1.1, 1.4**

  - [ ]* 4.2 Write property test for state token storage (Property 2)
    - **Property 2: State token stored with correct association and TTL**
    - In same file `tests/property/test_oauth_flow_properties.py`
    - Verify DynamoDB write contains correct `trainer_id`, `provider="google"`, and `ttl` within 30 minutes (±5s) of current time
    - **Validates: Requirements 1.2**

  - [ ]* 4.3 Write property test for state token uniqueness (Property 13)
    - **Property 13: State tokens are unique per request**
    - In same file `tests/property/test_oauth_flow_properties.py`
    - Call `connect_calendar` twice for the same trainer, verify state tokens in URLs differ
    - **Validates: Requirements 9.1**

- [ ] 5. Property tests for OAuth callback processing
  - [ ]* 5.1 Write property test for state token expiry validation (Property 3)
    - **Property 3: State token validation rejects expired tokens**
    - Create `tests/property/test_oauth_callback_properties.py`
    - Generate tokens with past TTLs → `_validate_state_token` returns `None`
    - Generate tokens with future TTLs → returns trainer data
    - **Validates: Requirements 3.1, 9.5**

  - [ ]* 5.2 Write property test for state token deletion after callback (Property 5)
    - **Property 5: State token deleted after successful callback**
    - In same file `tests/property/test_oauth_callback_properties.py`
    - Mock token exchange to succeed, verify state token is deleted from DynamoDB after callback
    - **Validates: Requirements 3.4, 9.4**

  - [ ]* 5.3 Write property test for success HTML response (Property 6)
    - **Property 6: Success HTML response format**
    - In same file `tests/property/test_oauth_callback_properties.py`
    - For provider in `{"google", "outlook"}`, verify `statusCode=200`, `Content-Type=text/html`, body contains provider display name
    - **Validates: Requirements 3.5, 10.3**

  - [ ]* 5.4 Write property test for error callback response (Property 7)
    - **Property 7: Error callback returns HTTP 400 with error description**
    - In same file `tests/property/test_oauth_callback_properties.py`
    - For random error description strings, verify `statusCode=400` and body contains the description
    - **Validates: Requirements 4.1**

  - [ ]* 5.5 Write property test for invalid state token (Property 8)
    - **Property 8: Invalid state token returns HTTP 400**
    - In same file `tests/property/test_oauth_callback_properties.py`
    - For random state tokens not in DynamoDB, verify callback returns `statusCode=400` with "new link" instruction
    - **Validates: Requirements 4.3**

- [ ] 6. Property tests for token management and resilience
  - [ ]* 6.1 Write property test for encryption round-trip (Property 4)
    - **Property 4: Token encryption round-trip**
    - Create `tests/property/test_oauth_token_properties.py`
    - Generate random non-empty strings (ASCII + Unicode), verify `decrypt_oauth_token_base64(encrypt_oauth_token_base64(token)) == token`
    - **Validates: Requirements 3.3, 5.1, 9.2**

  - [ ]* 6.2 Write property test for retry decorator (Property 9)
    - **Property 9: Retry decorator applies correct backoff configuration**
    - In same file `tests/property/test_oauth_token_properties.py`
    - Decorate a mock function with `@retry_with_backoff(max_attempts=3, ...)`, have it always raise, verify it is called exactly 3 times
    - **Validates: Requirements 5.4**

  - [ ]* 6.3 Write property test for graceful degradation (Property 12)
    - **Property 12: Graceful degradation on calendar sync failures**
    - In same file `tests/property/test_oauth_token_properties.py`
    - Mock various failure modes (no config, token refresh error, API error), verify `create_event` returns `None` without raising
    - **Validates: Requirements 8.1, 8.2, 8.3**

- [ ] 7. Checkpoint - Verify all property tests
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Unit tests for OAuth callback edge cases
  - [ ]* 8.1 Write unit tests for callback error paths
    - Add tests to `tests/unit/test_oauth_callback.py`
    - Test: missing `code` parameter returns 400
    - Test: missing `state` parameter returns 400
    - Test: `error=access_denied` parameter returns 400 with description
    - Test: token exchange returns no refresh token → 400
    - Test: token exchange HTTP failure → 400
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 8.2 Write unit tests for successful callback flow
    - Add tests to `tests/unit/test_oauth_callback.py`
    - Test: valid callback stores encrypted token in CALENDAR_CONFIG
    - Test: WhatsApp confirmation sent after success
    - Test: state token deleted after success
    - Test: success HTML contains "Google Calendar"
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 9. Unit tests for token refresh and calendar sync
  - [ ]* 9.1 Write unit tests for token refresh
    - Add tests to `tests/unit/test_calendar_sync.py`
    - Test: successful Google token refresh returns access token
    - Test: Google token refresh HTTP error raises `TokenRefreshError`
    - Test: refresh response missing access token raises `TokenRefreshError`
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ]* 9.2 Write unit tests for graceful degradation
    - Add tests to `tests/unit/test_calendar_sync.py`
    - Test: `create_event` with no calendar config returns `None`
    - Test: `create_event` with token refresh failure returns `None`
    - Test: `create_event` with API failure after retries returns `None`
    - _Requirements: 8.1, 8.2, 8.3_

- [x] 10. Wire disconnect and status tools into agent tool definitions
  - [x] 10.1 Register `disconnect_calendar` and `get_calendar_status` in agent tool list
    - Update the tool registration module that exposes tools to the Strands agent
    - Ensure both new tools are available for the AI agent to call
    - _Requirements: 6.1, 7.1_

  - [ ]* 10.2 Write unit test for tool registration
    - Verify `disconnect_calendar` and `get_calendar_status` appear in the agent's tool list
    - _Requirements: 6.1, 7.1_

- [x] 11. Final checkpoint - Full test suite
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The existing `connect_calendar`, `oauth_callback`, `CalendarSyncService`, and `encryption` modules are already implemented and only need test coverage
- Property tests use Hypothesis (already in the project) with a maximum of 10 examples per test (consistent with existing project convention)
- Mocking strategy: `moto` for DynamoDB/KMS, `responses` or `requests_mock` for Google endpoints, mock for Twilio
- Each task references specific requirements for traceability
