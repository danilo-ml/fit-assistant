# GitHub Actions CI/CD

This directory contains GitHub Actions workflows for automated testing and deployment.

## Workflows

### Deploy (`deploy.yml`)

Automated CI/CD pipeline that tests, packages, and deploys the FitAgent application to AWS.

**Triggers:**
- Push to `main` branch → deploys to production
- Manual workflow dispatch → deploys to production

**Jobs:**
1. **Test** - Runs linting, type checking, and unit tests
2. **Package** - Creates Lambda deployment package with correct structure
3. **Deploy Production** - Deploys to production environment

## Setup

### 1. Configure GitHub Secrets

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

### 2. Configure GitHub Environments

Create production environment in your repository (Settings → Environments):

**Production:**
- Enable "Required reviewers" (optional but recommended)
- Add deployment branch rule: `main` only
- Deploys on push to `main` branch or manual trigger

### 3. Branch Strategy

```
dev (local development) → test locally with docker-compose
  ↓ merge when ready
main (production) → production environment
```

**Workflow:**
- Work on `dev` branch → test locally with LocalStack
- Merge `dev` to `main` → auto-deploy to production

## Usage

### Local Development

```bash
# Work on dev branch
git checkout dev
git add .
git commit -m "feat: add new feature"

# Test locally with docker-compose
docker-compose up
```

### Deploy to Production

```bash
# Merge dev into main
git checkout main
git merge dev
git push origin main
```

The workflow will automatically:
1. Run tests
2. Package Lambda functions
3. Deploy to production
4. Update Lambda function code

Or use manual workflow dispatch:
1. Go to Actions tab
2. Select "Deploy to AWS"
3. Click "Run workflow"

### Manual Deployment

You can also trigger deployments manually from the GitHub Actions UI:

1. Navigate to **Actions** tab
2. Select **Deploy to AWS** workflow
3. Click **Run workflow**
4. Select branch and environment
5. Click **Run workflow** button

## Lambda Package Structure

The workflow creates a Lambda package with this structure:

```
lambda.zip
├── handlers/
│   ├── webhook_handler.py
│   ├── message_processor.py
│   └── ...
├── services/
│   ├── twilio_client.py
│   └── ...
├── tools/
├── models/
├── utils/
├── config.py
└── [dependencies]
```

**Important:** Source files are at the root level (not in `src/` folder) so Lambda can import them correctly.

## Monitoring

### View Deployment Status

- **Actions Tab**: See real-time deployment progress
- **Environments**: View deployment history and status
- **CloudFormation**: Check stack status in AWS Console

### View Logs

```bash
# Production
aws logs tail /aws/lambda/fitagent-webhook-handler-production --follow
```

## Troubleshooting

### Import Errors

If you see `No module named 'src'` errors:
- The package structure is correct in the workflow
- Check that Lambda handler is set to `handlers.webhook_handler.lambda_handler` (not `src.handlers...`)

### Deployment Failures

1. Check CloudFormation events:
   ```bash
   aws cloudformation describe-stack-events --stack-name fitagent-production
   ```

2. Check Lambda function logs:
   ```bash
   aws logs tail /aws/lambda/fitagent-webhook-handler-production
   ```

3. Verify secrets are updated:
   ```bash
   aws secretsmanager get-secret-value --secret-id fitagent/twilio/production
   ```

### Rollback

If deployment fails, CloudFormation automatically rolls back. To manually rollback:

```bash
# Rollback to previous version
aws cloudformation cancel-update-stack --stack-name fitagent-production
```

## Security

- AWS credentials are stored as GitHub secrets (encrypted)
- Production deployments require manual approval (if configured)
- Secrets Manager stores sensitive credentials (not in code)
- All deployments are logged and auditable

## Cost Optimization

- Artifacts are retained for 7 days only
- Lambda packages are versioned in S3 with timestamps
- Old S3 objects can be cleaned up with lifecycle policies

## Next Steps

1. Set up GitHub secrets (AWS credentials)
2. Configure production environment with protection rules (optional)
3. Push to `main` to deploy to production
4. Monitor CloudWatch logs for any issues
5. Update Twilio webhook URL with the API Gateway endpoint
