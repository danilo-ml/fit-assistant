# Requirements Document

## Introduction

This document specifies the requirements for the complete Google OAuth consent screen workflow in FitAgent. Google has rejected the app verification submission because the demo video did not show the OAuth consent screen workflow or sufficiently demonstrate app functionality. These requirements cover the end-to-end OAuth flow as experienced by a trainer via WhatsApp, including initiation, consent screen display, authorization callback, token management, calendar status visibility, token revocation (disconnect), and error handling. The goal is to ensure the implementation is complete and demonstrable for Google's verification review.

## Glossary

- **FitAgent**: The WhatsApp-based fitness trainer management platform
- **Trainer**: A personal trainer user who manages students and sessions via WhatsApp
- **OAuth_Flow_Initiator**: The component within FitAgent that generates Google OAuth2 authorization URLs when a trainer requests calendar connection via WhatsApp
- **OAuth_Callback_Handler**: The AWS Lambda function that receives the Google OAuth2 redirect after the trainer authorizes access on the Google consent screen
- **Token_Manager**: The component responsible for encrypting, storing, refreshing, and revoking OAuth2 tokens using AWS KMS and DynamoDB
- **WhatsApp_Messenger**: The Twilio-based component that sends and receives WhatsApp messages to and from trainers
- **Google_Consent_Screen**: The Google-hosted OAuth2 consent page where the trainer grants FitAgent access to their Google Calendar
- **Calendar_Sync_Service**: The service that creates, updates, and deletes Google Calendar events using OAuth2 access tokens
- **State_Token**: A unique, time-limited token stored in DynamoDB that ties an OAuth authorization request to a specific trainer and prevents CSRF attacks
- **Refresh_Token**: A long-lived OAuth2 token stored encrypted in DynamoDB, used to obtain new access tokens without re-authorization
- **Access_Token**: A short-lived OAuth2 token used to make Google Calendar API calls
- **Callback_Landing_Page**: The HTML page displayed to the trainer in their browser after the OAuth redirect completes

## Requirements

### Requirement 1: OAuth Flow Initiation via WhatsApp

**User Story:** As a trainer, I want to connect my Google Calendar by sending a message on WhatsApp, so that I can sync my training sessions without leaving the WhatsApp conversation.

#### Acceptance Criteria

1. WHEN a trainer sends a calendar connection request via WhatsApp, THE OAuth_Flow_Initiator SHALL generate a Google OAuth2 authorization URL with the scope `https://www.googleapis.com/auth/calendar`, `access_type=offline`, and `prompt=consent` parameters
2. WHEN the OAuth_Flow_Initiator generates an authorization URL, THE OAuth_Flow_Initiator SHALL create a State_Token with a unique identifier, associate it with the trainer's ID and the provider "google", and store it in DynamoDB with a TTL of 30 minutes
3. WHEN the authorization URL is generated, THE WhatsApp_Messenger SHALL send the complete clickable OAuth URL to the trainer via WhatsApp within 5 seconds of the request
4. THE OAuth_Flow_Initiator SHALL include the configured `oauth_redirect_uri` as the redirect URI in the authorization URL
5. IF the Google OAuth credentials (client_id or client_secret) are not configured, THEN THE OAuth_Flow_Initiator SHALL return an error message indicating that Google Calendar integration is not available

### Requirement 2: Google Consent Screen Interaction

**User Story:** As a trainer, I want to see a clear Google consent screen that explains what permissions FitAgent needs, so that I can make an informed decision about granting calendar access.

#### Acceptance Criteria

1. WHEN the trainer clicks the OAuth URL, THE Google_Consent_Screen SHALL display the FitAgent application name, the requested calendar scope, and the privacy policy URL as configured in the Google Cloud Console
2. WHEN the trainer grants consent on the Google_Consent_Screen, THE Google_Consent_Screen SHALL redirect the trainer's browser to the FitAgent OAuth callback URL with an authorization code and the original State_Token
3. WHEN the trainer denies consent on the Google_Consent_Screen, THE Google_Consent_Screen SHALL redirect the trainer's browser to the FitAgent OAuth callback URL with an `error` parameter set to `access_denied`

### Requirement 3: OAuth Callback Processing

**User Story:** As a trainer, I want the authorization to complete automatically after I grant consent, so that I do not need to perform additional manual steps.

#### Acceptance Criteria

1. WHEN the OAuth_Callback_Handler receives a redirect with a valid authorization code and State_Token, THE OAuth_Callback_Handler SHALL validate the State_Token against DynamoDB to confirm it exists and has not expired
2. WHEN the State_Token is valid, THE OAuth_Callback_Handler SHALL exchange the authorization code for an access token and a refresh token by calling the Google OAuth2 token endpoint (`https://oauth2.googleapis.com/token`)
3. WHEN the token exchange succeeds and a refresh token is received, THE Token_Manager SHALL encrypt the refresh token using AWS KMS and store the encrypted token in DynamoDB as part of the trainer's calendar configuration
4. WHEN the calendar configuration is stored, THE OAuth_Callback_Handler SHALL delete the used State_Token from DynamoDB to prevent replay attacks
5. WHEN the OAuth flow completes successfully, THE OAuth_Callback_Handler SHALL return a Callback_Landing_Page with an HTTP 200 status code displaying a success message that includes the provider name "Google Calendar"
6. WHEN the OAuth flow completes successfully, THE WhatsApp_Messenger SHALL send a confirmation message to the trainer's WhatsApp number indicating that Google Calendar has been connected

### Requirement 4: OAuth Callback Error Handling

**User Story:** As a trainer, I want to see clear error messages if something goes wrong during authorization, so that I know what happened and can try again.

#### Acceptance Criteria

1. IF the OAuth_Callback_Handler receives a redirect with an `error` parameter, THEN THE OAuth_Callback_Handler SHALL return a Callback_Landing_Page with an HTTP 400 status code displaying the error description
2. IF the OAuth_Callback_Handler receives a redirect without a `code` or `state` parameter, THEN THE OAuth_Callback_Handler SHALL return a Callback_Landing_Page with an HTTP 400 status code indicating missing parameters
3. IF the State_Token is not found in DynamoDB or has expired, THEN THE OAuth_Callback_Handler SHALL return a Callback_Landing_Page with an HTTP 400 status code instructing the trainer to request a new calendar connection link
4. IF the token exchange with Google fails, THEN THE OAuth_Callback_Handler SHALL return a Callback_Landing_Page with an HTTP 400 status code instructing the trainer to try again
5. IF the token exchange does not return a refresh token, THEN THE OAuth_Callback_Handler SHALL return a Callback_Landing_Page with an HTTP 400 status code indicating that offline access was not granted

### Requirement 5: Token Refresh and Access Token Management

**User Story:** As a trainer, I want my calendar to stay connected without needing to re-authorize, so that session sync works continuously.

#### Acceptance Criteria

1. WHEN the Calendar_Sync_Service needs to make a Google Calendar API call, THE Token_Manager SHALL decrypt the stored refresh token using AWS KMS and use it to obtain a new access token from the Google OAuth2 token endpoint
2. IF the token refresh request to Google fails with an HTTP error, THEN THE Token_Manager SHALL raise a TokenRefreshError with a descriptive message including the error details
3. IF the token refresh response does not contain an access token, THEN THE Token_Manager SHALL raise a TokenRefreshError indicating that no access token was received
4. THE Calendar_Sync_Service SHALL use retry logic with exponential backoff (3 attempts: 1s, 2s, 4s delays) for all Google Calendar API calls

### Requirement 6: Calendar Disconnection and Token Revocation

**User Story:** As a trainer, I want to disconnect my Google Calendar and revoke FitAgent's access, so that I can control my data and permissions.

#### Acceptance Criteria

1. WHEN a trainer requests to disconnect their Google Calendar via WhatsApp, THE Token_Manager SHALL revoke the refresh token by calling the Google OAuth2 revocation endpoint (`https://oauth2.googleapis.com/revoke`)
2. WHEN the revocation request completes (regardless of success or failure), THE Token_Manager SHALL delete the trainer's calendar configuration from DynamoDB
3. WHEN the calendar is disconnected, THE WhatsApp_Messenger SHALL send a confirmation message to the trainer indicating that Google Calendar has been disconnected
4. IF the revocation request to Google fails, THEN THE Token_Manager SHALL log the error and proceed with deleting the local calendar configuration

### Requirement 7: Calendar Connection Status

**User Story:** As a trainer, I want to check whether my Google Calendar is connected, so that I know if my sessions are being synced.

#### Acceptance Criteria

1. WHEN a trainer requests their calendar connection status via WhatsApp, THE FitAgent SHALL retrieve the trainer's calendar configuration from DynamoDB and report whether a Google Calendar is connected
2. WHEN a Google Calendar is connected, THE FitAgent SHALL include the provider name and the connection date in the status response
3. WHEN no calendar is connected, THE FitAgent SHALL inform the trainer that no calendar is connected and suggest using the connect calendar command

### Requirement 8: Graceful Degradation of Calendar Sync

**User Story:** As a trainer, I want session scheduling to work even if calendar sync fails, so that my core workflow is not blocked by calendar issues.

#### Acceptance Criteria

1. IF a Google Calendar API call fails after all retry attempts, THEN THE Calendar_Sync_Service SHALL log the error and return a failure indicator without raising an exception to the calling session operation
2. WHEN a session is created, updated, or cancelled and no calendar is connected, THE Calendar_Sync_Service SHALL skip the calendar sync operation and log an informational message
3. IF the token refresh fails during a calendar sync operation, THEN THE Calendar_Sync_Service SHALL log the error and return a failure indicator without blocking the session operation

### Requirement 9: OAuth Security Controls

**User Story:** As a platform operator, I want the OAuth flow to be secure against common attacks, so that trainer accounts and tokens are protected.

#### Acceptance Criteria

1. THE OAuth_Flow_Initiator SHALL generate a cryptographically random State_Token for each OAuth authorization request using UUID4
2. THE Token_Manager SHALL encrypt all refresh tokens at rest using AWS KMS before storing them in DynamoDB
3. THE OAuth_Callback_Handler SHALL validate the State_Token on every callback request before processing the authorization code
4. WHEN a State_Token is successfully used, THE OAuth_Callback_Handler SHALL delete the State_Token from DynamoDB to prevent reuse
5. THE State_Token SHALL expire after 30 minutes, enforced by both DynamoDB TTL and explicit timestamp validation in the OAuth_Callback_Handler

### Requirement 10: Demo-Ready End-to-End Flow Visibility

**User Story:** As a platform operator, I want the complete OAuth flow to be demonstrable in a video recording, so that Google's verification team can see the full consent screen workflow and app functionality.

#### Acceptance Criteria

1. THE WhatsApp_Messenger SHALL send a clear, user-facing message containing the OAuth URL when a trainer initiates calendar connection, visible in the WhatsApp conversation for video recording
2. THE Google_Consent_Screen SHALL display the FitAgent app name and requested permissions, visible in the browser for video recording
3. THE Callback_Landing_Page SHALL display a clear success message with the provider name after authorization completes, visible in the browser for video recording
4. THE WhatsApp_Messenger SHALL send a confirmation message back to the trainer's WhatsApp after successful authorization, visible in the WhatsApp conversation for video recording
5. WHEN a trainer creates a session after connecting Google Calendar, THE Calendar_Sync_Service SHALL create a corresponding event in Google Calendar, demonstrating the functional use of the OAuth-granted permissions
