# CI/CD Setup Guide

## Quick Setup (5 minutes)

### 1. Add AWS Credentials to GitHub

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add these two secrets:

```
Name: AWS_ACCESS_KEY_ID
Value: <your-aws-access-key-id>

Name: AWS_SECRET_ACCESS_KEY
Value: <your-aws-secret-access-key>
```

### 2. Configure GitHub Environments (Optional but Recommended)

1. Go to **Settings** → **Environments**
2. Create **production** environment with:
   - ✅ Required reviewers (add yourself) - optional
   - ✅ Deployment branches: `main` only

### 3. Commit and Push

```bash
git add .
git commit -m "ci: add GitHub Actions CI/CD pipeline"
git push origin main
```

### 4. Watch the Magic ✨

1. Go to **Actions** tab
2. Watch your deployment run automatically
3. Check the summary for the webhook URL

## How It Works

### Automatic Deployments

```
Push to main → Tests → Package → Deploy to Production
```

### Manual Deployments

1. Go to **Actions** tab
2. Select **Deploy to AWS**
3. Click **Run workflow**
4. Click **Run workflow** button

## What Gets Deployed

The pipeline:
1. ✅ Runs tests (linting, type checking, unit tests)
2. ✅ Packages Lambda with correct structure (no `src/` prefix)
3. ✅ Uploads to S3 with timestamp
4. ✅ Deploys CloudFormation stack
5. ✅ Updates all Lambda functions
6. ✅ Shows webhook URL in summary

## Fixed Issues

✅ **Lambda Import Error** - Package structure now correct (modules at root)
✅ **Handler Paths** - Changed from `src.handlers.X` to `handlers.X`
✅ **Twilio Signature Validation** - Enabled and working
✅ **Secrets Management** - Using AWS Secrets Manager

## Next Steps

After first deployment:

1. **Update Twilio Webhook URL** (shown in deployment summary)
2. **Update Secrets**:
   ```bash
   ./scripts/update_secrets.sh production twilio
   ```
3. **Test** by sending a WhatsApp message

## Monitoring

View logs in real-time:
```bash
aws logs tail /aws/lambda/fitagent-webhook-handler-production --follow
```

## Troubleshooting

If deployment fails, check:
1. GitHub Actions logs (Actions tab)
2. CloudFormation events (AWS Console)
3. Lambda function logs (CloudWatch)

## Branch Strategy

```
dev (local development)
  ↓ test locally with docker-compose
  ↓ merge when ready
main (production)
  ↓ auto-deploy
production environment
```

**Workflow:**
- Work on `dev` branch
- Test locally with LocalStack
- Merge `dev` to `main` → deploys to production

## Security

- ✅ AWS credentials encrypted in GitHub
- ✅ Production requires approval (optional)
- ✅ Secrets in AWS Secrets Manager
- ✅ All deployments audited

That's it! Your CI/CD is ready. Just push to `main` to deploy to production.
