# Google Calendar Integration Setup

This guide walks you through setting up Google Calendar integration for FitAgent.

## Prerequisites

- Google Cloud Console account
- FitAgent infrastructure deployed (to get OAuth callback URL)

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your project ID

## Step 2: Enable Google Calendar API

1. In Google Cloud Console, navigate to **APIs & Services** → **Library**
2. Search for "Google Calendar API"
3. Click **Enable**

## Step 3: Create OAuth 2.0 Credentials

1. Navigate to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - User Type: **External** (for testing) or **Internal** (for organization)
   - App name: **FitAgent**
   - User support email: Your email
   - Developer contact: Your email
   - Scopes: Add `https://www.googleapis.com/auth/calendar`
   - Test users: Add trainer email addresses (if External)
4. Application type: **Web application**
5. Name: **FitAgent Calendar Integration**

## Step 4: Configure Authorized Redirect URIs

Add the following redirect URIs:

### Local Development
```
http://localhost:8000/oauth/callback
```

### Production
Get your production URL from CloudFormation outputs:
```bash
aws cloudformation describe-stacks \
  --stack-name fitagent-production \
  --query 'Stacks[0].Outputs[?OutputKey==`OAuthCallbackUrl`].OutputValue' \
  --output text
```

Example production URL:
```
https://abc123xyz.execute-api.us-east-1.amazonaws.com/production/oauth/callback
```

### Staging (if applicable)
```
https://abc123xyz.execute-api.us-east-1.amazonaws.com/staging/oauth/callback
```

## Step 5: Save Credentials

After creating the OAuth client:

1. Download the JSON credentials file
2. Note the **Client ID** and **Client Secret**

## Step 6: Configure FitAgent

### Local Development

Add to your `.env` file:
```bash
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
OAUTH_REDIRECT_URI=http://localhost:8000/oauth/callback
```

### Production

Update AWS Secrets Manager:
```bash
# Update Google OAuth secret
aws secretsmanager update-secret \
  --secret-id fitagent/google-oauth/production \
  --secret-string '{
    "client_id": "your_client_id_here.apps.googleusercontent.com",
    "client_secret": "your_client_secret_here"
  }'
```

The OAuth redirect URI is automatically set by CloudFormation.

## Step 7: Test the Integration

### Local Testing

1. Start your local environment:
   ```bash
   make start
   ```

2. Send a WhatsApp message to connect calendar:
   ```
   Connect my Google Calendar
   ```

3. The AI will generate an OAuth URL - click it to authorize
4. You'll be redirected back with a success message
5. Confirm you receive a WhatsApp confirmation

### Production Testing

1. Deploy your infrastructure:
   ```bash
   aws cloudformation deploy \
     --template-file infrastructure/template.yml \
     --stack-name fitagent-production \
     --parameter-overrides Environment=production \
     --capabilities CAPABILITY_NAMED_IAM
   ```

2. Update Secrets Manager with your Google credentials (see Step 6)

3. Send a WhatsApp message to your production number:
   ```
   Connect my Google Calendar
   ```

4. Follow the OAuth flow and verify the integration works

## Troubleshooting

### "Redirect URI mismatch" error

- Verify the redirect URI in Google Console exactly matches your environment
- Check for trailing slashes - they must match exactly
- Ensure you've saved changes in Google Console

### "Access blocked: This app's request is invalid"

- Verify Google Calendar API is enabled in your project
- Check that the OAuth consent screen is properly configured
- Ensure the scope `https://www.googleapis.com/auth/calendar` is added

### "Invalid client" error

- Verify Client ID and Client Secret are correct
- Check that credentials are properly loaded (Secrets Manager or .env)
- Ensure the OAuth client is for "Web application" type

### Calendar events not syncing

- Check Lambda logs for errors:
  ```bash
  aws logs tail /aws/lambda/fitagent-message-processor-production --follow
  ```
- Verify the trainer has connected their calendar (check DynamoDB for CALENDAR_CONFIG)
- Test token refresh by scheduling a session

## Security Best Practices

1. **Never commit credentials** to version control
2. **Use Secrets Manager** for production credentials
3. **Rotate secrets** periodically
4. **Limit OAuth scopes** to only what's needed (calendar read/write)
5. **Monitor API usage** in Google Cloud Console
6. **Set up billing alerts** to avoid unexpected charges

## API Quotas

Google Calendar API has the following quotas:
- **Queries per day**: 1,000,000
- **Queries per 100 seconds per user**: 1,000

For most trainers, these limits are more than sufficient. Monitor usage in Google Cloud Console.

## Next Steps

- Set up Microsoft Outlook integration (see `docs/OUTLOOK_CALENDAR_SETUP.md`)
- Configure calendar sync preferences
- Test session scheduling with calendar integration
- Monitor calendar sync performance

## Support

For issues with Google Calendar integration:
1. Check CloudWatch logs for error messages
2. Verify OAuth credentials are correct
3. Test the OAuth flow manually
4. Contact support with error logs
