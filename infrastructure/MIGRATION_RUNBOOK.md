# Multi-Agent Architecture Migration Runbook

## Document Overview

**Purpose:** Guide operations teams through the safe rollout of FitAgent's multi-agent architecture using AWS Bedrock Agents (Strands SDK).

**Target Audience:** DevOps engineers, SREs, platform engineers

**Migration Timeline:** 8 weeks (phased rollout)

**Rollback Strategy:** Feature flag toggle with zero data migration required

---

## Table of Contents

1. [Pre-Migration Checklist](#pre-migration-checklist)
2. [Phased Rollout Strategy](#phased-rollout-strategy)
3. [Rollback Procedures](#rollback-procedures)
4. [Monitoring Metrics](#monitoring-metrics)
5. [Troubleshooting Guide](#troubleshooting-guide)
6. [Emergency Contacts](#emergency-contacts)

---

## Pre-Migration Checklist

### Infrastructure Verification

Complete these checks before starting the migration:

#### 1. DynamoDB Configuration

- [ ] Verify `session-confirmation-index` GSI exists on `fitagent-main` table
  ```bash
  aws dynamodb describe-table --table-name fitagent-main \
    --query 'Table.GlobalSecondaryIndexes[?IndexName==`session-confirmation-index`]'
  ```
  - Expected: GSI with PK=`trainer_id`, SK=`confirmation_status_datetime`
  - Status: ACTIVE
  - Provisioned throughput: 5 RCU / 5 WCU (minimum)

- [ ] Verify existing GSIs are healthy
  ```bash
  aws dynamodb describe-table --table-name fitagent-main \
    --query 'Table.GlobalSecondaryIndexes[*].[IndexName,IndexStatus]'
  ```
  - `phone-number-index`: ACTIVE
  - `session-date-index`: ACTIVE
  - `payment-status-index`: ACTIVE

#### 2. Lambda Functions Deployed

- [ ] Verify all Lambda functions exist and are current version
  ```bash
  aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `fitagent-`)].FunctionName'
  ```
  - Expected functions:
    - `fitagent-webhook-handler`
    - `fitagent-message-processor`
    - `fitagent-session-reminder`
    - `fitagent-payment-reminder`
    - `fitagent-notification-sender`
    - `fitagent-oauth-callback`
    - `fitagent-session-confirmation` (NEW)

- [ ] Verify Lambda runtime is Python 3.12
  ```bash
  aws lambda get-function --function-name fitagent-message-processor \
    --query 'Configuration.Runtime'
  ```

- [ ] Verify environment variables configured
  ```bash
  aws lambda get-function-configuration --function-name fitagent-message-processor \
    --query 'Environment.Variables'
  ```
  - Required: `DYNAMODB_TABLE`, `ENABLE_MULTI_AGENT`, `BEDROCK_MODEL_ID`, `BEDROCK_REGION`

#### 3. EventBridge Rules

- [ ] Verify session confirmation rule exists
  ```bash
  aws events describe-rule --name session-confirmation-trigger
  ```
  - Schedule: `cron(*/5 * * * ? *)` (every 5 minutes)
  - State: ENABLED
  - Target: `fitagent-session-confirmation` Lambda

- [ ] Verify existing reminder rules are active
  ```bash
  aws events list-rules --name-prefix fitagent-
  ```
  - `fitagent-session-reminder`: ENABLED
  - `fitagent-payment-reminder`: ENABLED

#### 4. Strands SDK Installation

- [ ] Verify Strands SDK installed in Lambda deployment package
  ```bash
  # Extract lambda.zip and check
  unzip -l lambda.zip | grep strands_agents
  ```
  - Expected: `strands_agents/` directory with SDK files

- [ ] Verify SDK version compatibility
  ```python
  # In Lambda console or locally
  import strands_agents
  print(strands_agents.__version__)
  # Expected: >= 1.0.0
  ```

#### 5. SwarmOrchestrator Implementation

- [ ] Verify `src/services/swarm_orchestrator.py` exists
- [ ] Verify all 6 agents implemented:
  - `coordinator_agent` (Entry_Agent)
  - `student_agent`
  - `session_agent`
  - `payment_agent`
  - `calendar_agent`
  - `notification_agent`

- [ ] Verify agent configuration parameters
  ```python
  # Check in swarm_orchestrator.py
  max_handoffs = 7
  node_timeout = 30  # seconds
  execution_timeout = 120  # seconds
  ```

#### 6. Feature Flag Configuration

- [ ] Verify feature flag exists in environment
  ```bash
  aws lambda get-function-configuration --function-name fitagent-message-processor \
    --query 'Environment.Variables.ENABLE_MULTI_AGENT'
  ```
  - Initial value: `false` (disabled)

- [ ] Verify per-trainer feature flag table exists (optional)
  ```bash
  aws dynamodb describe-table --table-name fitagent-feature-flags
  ```

#### 7. Monitoring Dashboards

- [ ] Verify CloudWatch dashboard `FitAgent-MultiAgent` exists
  - Metrics: Response time, error rate, handoff count, agent-specific metrics
  - Alarms configured for critical thresholds

- [ ] Verify CloudWatch Logs Insights queries saved
  - Agent handoff analysis
  - Error rate by agent
  - Performance bottleneck detection

#### 8. Testing Validation

- [ ] All unit tests passing
  ```bash
  pytest tests/unit/ -v
  ```

- [ ] All property-based tests passing
  ```bash
  pytest tests/property/ -v --hypothesis-show-statistics
  ```

- [ ] All integration tests passing
  ```bash
  pytest tests/integration/ -v
  ```

- [ ] Code coverage meets minimum 70%
  ```bash
  pytest --cov=src --cov-report=term --cov-fail-under=70
  ```

#### 9. Staging Environment Validation

- [ ] Deploy to staging environment
- [ ] Run smoke tests on staging
- [ ] Verify session confirmation flow works end-to-end
- [ ] Verify all agent handoffs work correctly
- [ ] Load test with 100 concurrent messages
- [ ] Verify response time < 10 seconds for 95th percentile

---

## Phased Rollout Strategy

### Overview

The migration uses a **phased canary deployment** approach with gradual traffic increase:

- **Phase 1:** Staging deployment (Week 1-2)
- **Phase 2:** 10% canary (Week 3)
- **Phase 3:** 50% rollout (Week 4)
- **Phase 4:** 100% rollout (Week 5)

Each phase includes success criteria that must be met before proceeding.

---

### Phase 1: Staging Deployment (Week 1-2)

**Objective:** Validate multi-agent architecture in staging environment

**Duration:** 2 weeks

**Actions:**

1. **Deploy Infrastructure**
   ```bash
   # Deploy CloudFormation stack to staging
   aws cloudformation deploy \
     --template-file infrastructure/template.yml \
     --stack-name fitagent-staging \
     --parameter-overrides Environment=staging \
     --capabilities CAPABILITY_IAM
   ```

2. **Enable Feature Flag in Staging**
   ```bash
   aws lambda update-function-configuration \
     --function-name fitagent-message-processor-staging \
     --environment "Variables={ENABLE_MULTI_AGENT=true,...}"
   ```

3. **Run Smoke Tests**
   ```bash
   # Execute staging test suite
   pytest tests/integration/ --env=staging -v
   ```

4. **Manual Testing Scenarios**
   - Test student registration → session scheduling → calendar sync flow
   - Test payment registration with receipt upload
   - Test session confirmation flow (create session → wait 1 hour → confirm)
   - Test broadcast notifications
   - Test error handling (invalid inputs, timeouts, API failures)

5. **Load Testing**
   ```bash
   # Use locust or similar tool
   locust -f tests/load/test_message_processing.py --host=https://staging-api.fitagent.com
   ```
   - Target: 100 concurrent users
   - Duration: 30 minutes
   - Success rate: > 99%

**Success Criteria:**

- [ ] All smoke tests pass
- [ ] Manual test scenarios complete successfully
- [ ] Response time p95 < 10 seconds
- [ ] Error rate < 1%
- [ ] No memory leaks or Lambda cold start issues
- [ ] Session confirmation flow works end-to-end
- [ ] All agent handoffs logged correctly

**Go/No-Go Decision:** Review with engineering team. If all criteria met, proceed to Phase 2.

---

### Phase 2: 10% Canary Deployment (Week 3)

**Objective:** Enable multi-agent for 10% of production trainers

**Duration:** 1 week

**Actions:**

1. **Select Canary Trainers**
   ```bash
   # Select 10% of trainers (prefer active users with diverse usage patterns)
   python scripts/select_canary_trainers.py --percentage 10 --output canary_trainers.json
   ```

2. **Enable Per-Trainer Feature Flags**
   ```bash
   # For each canary trainer
   python scripts/enable_multi_agent.py --trainer-ids-file canary_trainers.json
   ```
   - This updates DynamoDB `FEATURE_FLAGS` record for each trainer
   - Alternatively, use global flag with trainer whitelist

3. **Deploy to Production**
   ```bash
   aws cloudformation deploy \
     --template-file infrastructure/template.yml \
     --stack-name fitagent-production \
     --parameter-overrides Environment=production \
     --capabilities CAPABILITY_IAM
   ```

4. **Monitor Canary Metrics** (24/7 for first 48 hours)
   - Response time comparison (canary vs control group)
   - Error rate comparison
   - Handoff count distribution
   - Agent-specific performance metrics

5. **Daily Health Checks**
   ```bash
   # Run automated health check script
   python scripts/canary_health_check.py --canary-file canary_trainers.json
   ```

**Success Criteria:**

- [ ] Response time p95 < 10 seconds (no regression vs single-agent)
- [ ] Error rate < 1% (comparable to single-agent baseline)
- [ ] No critical bugs reported by canary trainers
- [ ] Handoff count average: 2-3 per conversation
- [ ] No timeout violations (execution_timeout, node_timeout)
- [ ] Session confirmation messages sent successfully
- [ ] CloudWatch alarms: No critical alerts

**Rollback Triggers:**

- Error rate > 5%
- Response time p95 > 15 seconds
- Critical bug affecting core functionality
- More than 3 customer complaints

**Go/No-Go Decision:** If success criteria met after 7 days, proceed to Phase 3. Otherwise, rollback and investigate.

---

### Phase 3: 50% Rollout (Week 4)

**Objective:** Expand multi-agent to 50% of production trainers

**Duration:** 1 week

**Actions:**

1. **Expand Canary Group**
   ```bash
   # Select additional trainers to reach 50% total
   python scripts/select_canary_trainers.py --percentage 50 --exclude canary_trainers.json \
     --output expanded_trainers.json
   ```

2. **Enable Feature Flags**
   ```bash
   python scripts/enable_multi_agent.py --trainer-ids-file expanded_trainers.json
   ```

3. **Monitor Expanded Rollout**
   - Continue 24/7 monitoring for first 48 hours
   - Daily health checks for remainder of week

4. **Capacity Planning Check**
   ```bash
   # Verify DynamoDB and Lambda capacity
   aws cloudwatch get-metric-statistics \
     --namespace AWS/DynamoDB \
     --metric-name ConsumedReadCapacityUnits \
     --dimensions Name=TableName,Value=fitagent-main \
     --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 300 \
     --statistics Average,Maximum
   ```

**Success Criteria:**

- [ ] Response time p95 < 10 seconds
- [ ] Error rate < 1%
- [ ] No DynamoDB throttling events
- [ ] Lambda concurrency within limits
- [ ] No increase in customer support tickets
- [ ] Session confirmation flow stable
- [ ] All agent handoffs functioning correctly

**Rollback Triggers:** Same as Phase 2

**Go/No-Go Decision:** If success criteria met after 7 days, proceed to Phase 4.

---

### Phase 4: 100% Rollout (Week 5)

**Objective:** Enable multi-agent for all production trainers

**Duration:** 1 week initial rollout + ongoing monitoring

**Actions:**

1. **Global Feature Flag Enable**
   ```bash
   # Option A: Enable globally via environment variable
   aws lambda update-function-configuration \
     --function-name fitagent-message-processor \
     --environment "Variables={ENABLE_MULTI_AGENT=true,...}"

   # Option B: Enable remaining trainers individually
   python scripts/enable_multi_agent.py --all-remaining
   ```

2. **Monitor Full Rollout**
   - 24/7 monitoring for first 72 hours
   - Daily health checks for 2 weeks
   - Weekly reviews for 1 month

3. **Performance Baseline Update**
   ```bash
   # Capture new performance baselines
   python scripts/update_performance_baselines.py --period 7days
   ```

4. **Documentation Update**
   - Update runbooks with multi-agent architecture
   - Update troubleshooting guides
   - Update customer support documentation

**Success Criteria:**

- [ ] Response time p95 < 10 seconds across all trainers
- [ ] Error rate < 1% globally
- [ ] No critical incidents
- [ ] Customer satisfaction maintained or improved
- [ ] All monitoring dashboards green
- [ ] Session confirmation adoption > 80%

**Post-Rollout Actions:**

- [ ] Remove single-agent code path (after 2 weeks of stability)
- [ ] Archive feature flag (keep for emergency rollback)
- [ ] Conduct post-mortem and document lessons learned
- [ ] Optimize agent prompts based on production data

---

## Rollback Procedures

### Global Rollback (All Trainers)

**When to Use:** Critical bug, widespread failures, error rate > 5%

**Steps:**

1. **Disable Feature Flag**
   ```bash
   aws lambda update-function-configuration \
     --function-name fitagent-message-processor \
     --environment "Variables={ENABLE_MULTI_AGENT=false,...}"
   ```

2. **Verify Rollback**
   ```bash
   # Check environment variable
   aws lambda get-function-configuration \
     --function-name fitagent-message-processor \
     --query 'Environment.Variables.ENABLE_MULTI_AGENT'
   # Expected: "false"
   ```

3. **Monitor Single-Agent Behavior**
   - Verify messages processed by single AIAgent
   - Check response times return to baseline
   - Verify error rate decreases

4. **Notify Stakeholders**
   - Engineering team
   - Customer support
   - Product management

**Expected Impact:**
- No data loss (both architectures use same DynamoDB schema)
- No user-visible disruption (seamless fallback)
- Response time may improve temporarily
- Session confirmation continues to work (independent feature)

**Recovery Time Objective (RTO):** < 5 minutes

---

### Per-Trainer Rollback (Selective)

**When to Use:** Issues affecting specific trainers, gradual rollback

**Steps:**

1. **Identify Affected Trainers**
   ```bash
   # Query CloudWatch Logs for errors by trainer_id
   aws logs filter-log-events \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --filter-pattern '{ $.error_type = "MaxHandoffsExceeded" }' \
     --start-time $(date -u -d '1 hour ago' +%s)000
   ```

2. **Disable Feature Flag for Specific Trainers**
   ```bash
   python scripts/disable_multi_agent.py --trainer-ids trainer_abc123,trainer_xyz789
   ```
   - Updates DynamoDB `FEATURE_FLAGS` record
   - Sets `enable_multi_agent: false` for each trainer

3. **Verify Rollback**
   ```bash
   # Check trainer feature flags
   aws dynamodb get-item \
     --table-name fitagent-main \
     --key '{"PK": {"S": "TRAINER#trainer_abc123"}, "SK": {"S": "FEATURE_FLAGS"}}'
   ```

4. **Monitor Affected Trainers**
   - Verify they're using single-agent architecture
   - Check for error resolution

**Recovery Time Objective (RTO):** < 10 minutes per trainer

---

### Emergency Rollback (Immediate)

**When to Use:** Production outage, data corruption risk, security incident

**Steps:**

1. **Execute Immediate Rollback**
   ```bash
   # Run emergency rollback script
   ./scripts/emergency_rollback.sh
   ```
   - Disables global feature flag
   - Sends alerts to on-call team
   - Creates incident ticket

2. **Verify System Stability**
   ```bash
   # Check error rate
   python scripts/check_error_rate.py --last 5m
   ```

3. **Initiate Incident Response**
   - Page on-call engineer
   - Start incident bridge
   - Begin root cause analysis

**Recovery Time Objective (RTO):** < 2 minutes

---

### Data Consistency Verification

After any rollback, verify data consistency:

1. **Check Session Records**
   ```bash
   # Verify no orphaned sessions
   python scripts/verify_session_consistency.py
   ```

2. **Check Confirmation Status**
   ```bash
   # Verify confirmation_status field integrity
   aws dynamodb scan \
     --table-name fitagent-main \
     --filter-expression "entity_type = :type AND attribute_not_exists(confirmation_status)" \
     --expression-attribute-values '{":type":{"S":"SESSION"}}'
   ```

3. **Check Agent Contributions**
   ```bash
   # Verify Shared_Context serialization
   python scripts/verify_context_integrity.py
   ```

**Expected Result:** No data inconsistencies (both architectures compatible)

---

## Monitoring Metrics

### Key Performance Indicators (KPIs)

#### 1. Response Time

**Metric:** `ResponseTime_P95`

**Target:** < 10 seconds (95th percentile)

**CloudWatch Query:**
```
fields @timestamp, @message
| filter @message like /response_time/
| stats percentile(@message.response_time, 95) as p95 by bin(5m)
```

**Alarm Configuration:**
```yaml
AlarmName: MultiAgent-ResponseTime-High
MetricName: ResponseTime_P95
Threshold: 10000  # milliseconds
EvaluationPeriods: 2
DatapointsToAlarm: 2
ComparisonOperator: GreaterThanThreshold
```

#### 2. Error Rate

**Metric:** `ErrorRate`

**Target:** < 1%

**CloudWatch Query:**
```
fields @timestamp
| filter @message like /error/
| stats count(*) as errors by bin(5m)
| stats sum(errors) / count(*) * 100 as error_rate
```

**Alarm Configuration:**
```yaml
AlarmName: MultiAgent-ErrorRate-High
MetricName: ErrorRate
Threshold: 1.0  # percent
EvaluationPeriods: 3
DatapointsToAlarm: 2
ComparisonOperator: GreaterThanThreshold
```

#### 3. Handoff Count

**Metric:** `HandoffCount_Average`

**Target:** 2-3 handoffs per conversation (typical)

**CloudWatch Query:**
```
fields @timestamp, @message.handoff_count
| filter @message like /handoff_count/
| stats avg(@message.handoff_count) as avg_handoffs by bin(5m)
```

**Alarm Configuration:**
```yaml
AlarmName: MultiAgent-HandoffCount-Anomaly
MetricName: HandoffCount_Average
Threshold: 5.0  # handoffs
EvaluationPeriods: 3
ComparisonOperator: GreaterThanThreshold
```

#### 4. Agent-Specific Metrics

**Metrics per Agent:**
- `Agent_Invocations` (count)
- `Agent_Duration` (milliseconds)
- `Agent_Errors` (count)
- `Agent_Timeouts` (count)

**CloudWatch Query:**
```
fields @timestamp, @message.agent_name, @message.duration
| filter @message like /agent_execution/
| stats count(*) as invocations, avg(@message.duration) as avg_duration by @message.agent_name, bin(5m)
```

**Dashboard Widgets:**
- Invocations by agent (bar chart)
- Duration by agent (line chart)
- Error rate by agent (heatmap)

#### 5. Session Confirmation Metrics

**Metrics:**
- `Confirmations_Sent` (count)
- `Confirmations_Completed` (count)
- `Confirmations_Missed` (count)
- `Confirmation_Response_Rate` (percentage)

**CloudWatch Query:**
```
fields @timestamp, @message.confirmation_status
| filter @message like /session_confirmation/
| stats count(*) by @message.confirmation_status, bin(1h)
```

---

### CloudWatch Dashboard Configuration

**Dashboard Name:** `FitAgent-MultiAgent-Production`

**Widgets:**

1. **Response Time (Line Chart)**
   - Metrics: P50, P95, P99
   - Period: 5 minutes
   - Statistic: Percentile

2. **Error Rate (Line Chart)**
   - Metric: ErrorRate
   - Period: 5 minutes
   - Threshold line at 1%

3. **Handoff Distribution (Bar Chart)**
   - X-axis: Handoff count (1-7)
   - Y-axis: Conversation count
   - Period: 1 hour

4. **Agent Invocations (Stacked Area Chart)**
   - Metrics: Invocations per agent
   - Period: 5 minutes
   - Shows agent usage patterns

5. **Agent Performance (Table)**
   - Columns: Agent, Invocations, Avg Duration, Error Rate
   - Period: 1 hour
   - Sorted by invocations

6. **Session Confirmations (Pie Chart)**
   - Segments: Completed, Missed, Pending
   - Period: 24 hours

7. **Lambda Metrics (Line Chart)**
   - Metrics: Invocations, Errors, Throttles, Duration
   - Period: 5 minutes

8. **DynamoDB Metrics (Line Chart)**
   - Metrics: ConsumedReadCapacity, ConsumedWriteCapacity, ThrottledRequests
   - Period: 5 minutes

**Create Dashboard:**
```bash
aws cloudwatch put-dashboard \
  --dashboard-name FitAgent-MultiAgent-Production \
  --dashboard-body file://infrastructure/dashboards/multi-agent-dashboard.json
```

---

### Log Analysis Queries

#### Query 1: Agent Handoff Path Analysis

```
fields @timestamp, @message.handoff_path
| filter @message like /handoff_path/
| stats count(*) by @message.handoff_path
| sort count desc
| limit 20
```

**Purpose:** Identify most common handoff patterns

#### Query 2: Error Analysis by Agent

```
fields @timestamp, @message.agent_name, @message.error_type, @message.error
| filter @message like /error/
| stats count(*) by @message.agent_name, @message.error_type
| sort count desc
```

**Purpose:** Identify which agents have most errors

#### Query 3: Performance Bottleneck Detection

```
fields @timestamp, @message.agent_name, @message.duration
| filter @message like /agent_execution/ and @message.duration > 5000
| stats count(*) as slow_executions, avg(@message.duration) as avg_duration by @message.agent_name
| sort slow_executions desc
```

**Purpose:** Find agents with slow execution times

#### Query 4: Timeout Analysis

```
fields @timestamp, @message.timeout_type, @message.agent_name
| filter @message like /timeout/
| stats count(*) by @message.timeout_type, @message.agent_name, bin(1h)
```

**Purpose:** Track timeout occurrences (node_timeout vs execution_timeout)

#### Query 5: Session Confirmation Success Rate

```
fields @timestamp, @message.confirmation_status
| filter @message like /confirmation_processed/
| stats count(*) by @message.confirmation_status, bin(1d)
```

**Purpose:** Monitor confirmation response rates

---

### Alerting Strategy

#### Critical Alerts (Page On-Call)

1. **Error Rate > 5%**
   - Severity: Critical
   - Action: Immediate rollback consideration

2. **Response Time P95 > 15 seconds**
   - Severity: Critical
   - Action: Investigate performance bottleneck

3. **Lambda Function Errors > 10 in 5 minutes**
   - Severity: Critical
   - Action: Check logs and consider rollback

4. **DynamoDB Throttling Events**
   - Severity: Critical
   - Action: Increase capacity or investigate query patterns

#### Warning Alerts (Notify Team)

1. **Error Rate > 1%**
   - Severity: Warning
   - Action: Monitor and investigate

2. **Response Time P95 > 10 seconds**
   - Severity: Warning
   - Action: Review agent performance

3. **Handoff Count Average > 5**
   - Severity: Warning
   - Action: Review agent handoff logic

4. **Agent Timeout Rate > 0.5%**
   - Severity: Warning
   - Action: Optimize slow agents

#### Info Alerts (Log Only)

1. **Session Confirmation Response Rate < 50%**
   - Severity: Info
   - Action: Review confirmation message clarity

2. **Agent Cache Miss Rate > 20%**
   - Severity: Info
   - Action: Review Lambda warm start optimization

---

## Troubleshooting Guide

### Issue 1: High Response Time

**Symptoms:**
- Response time P95 > 10 seconds
- Users complaining about slow responses
- CloudWatch alarm triggered

**Diagnosis:**

1. **Check Agent Performance**
   ```bash
   # Query slow agent executions
   aws logs filter-log-events \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --filter-pattern '{ $.duration > 5000 }' \
     --start-time $(date -u -d '1 hour ago' +%s)000
   ```

2. **Check DynamoDB Performance**
   ```bash
   # Check for throttling
   aws cloudwatch get-metric-statistics \
     --namespace AWS/DynamoDB \
     --metric-name UserErrors \
     --dimensions Name=TableName,Value=fitagent-main \
     --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 300 \
     --statistics Sum
   ```

3. **Check External API Latency**
   ```bash
   # Check calendar API calls
   aws logs filter-log-events \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --filter-pattern '{ $.api_call = "calendar_sync" }' \
     --start-time $(date -u -d '1 hour ago' +%s)000
   ```

**Resolution:**

- **If agent is slow:** Optimize agent prompt or model selection
- **If DynamoDB throttling:** Increase provisioned capacity or use on-demand mode
- **If external API slow:** Implement timeout and graceful degradation
- **If Lambda cold start:** Increase provisioned concurrency

**Prevention:**
- Monitor agent performance continuously
- Set up auto-scaling for DynamoDB
- Implement caching for frequent queries

---

### Issue 2: High Error Rate

**Symptoms:**
- Error rate > 1%
- Multiple failed message processing attempts
- Users reporting errors

**Diagnosis:**

1. **Identify Error Types**
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --filter-pattern '{ $.level = "ERROR" }' \
     --start-time $(date -u -d '1 hour ago' +%s)000 \
     | jq '.events[].message | fromjson | .error_type' \
     | sort | uniq -c | sort -rn
   ```

2. **Check Specific Agent Errors**
   ```bash
   # Query errors by agent
   aws logs insights query \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --start-time $(date -u -d '1 hour ago' +%s) \
     --end-time $(date -u +%s) \
     --query-string 'fields @timestamp, agent_name, error_type, error | filter level = "ERROR" | stats count() by agent_name, error_type'
   ```

3. **Check for Max Handoffs Violations**
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --filter-pattern '{ $.error_type = "MaxHandoffsExceeded" }'
   ```

**Resolution:**

- **If validation errors:** Review input validation logic
- **If max handoffs exceeded:** Review agent handoff logic, increase max_handoffs if appropriate
- **If timeout errors:** Optimize slow agents or increase timeout values
- **If external API errors:** Implement retry logic and graceful degradation

**Prevention:**
- Comprehensive input validation
- Proper error handling in all agents
- Circuit breakers for external APIs

---

### Issue 3: Excessive Handoffs

**Symptoms:**
- Handoff count average > 5
- Max handoffs exceeded errors
- Conversations taking too long

**Diagnosis:**

1. **Analyze Handoff Patterns**
   ```bash
   # Query handoff paths
   aws logs insights query \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --start-time $(date -u -d '1 hour ago' +%s) \
     --end-time $(date -u +%s) \
     --query-string 'fields handoff_path, handoff_count | filter handoff_count > 5 | stats count() by handoff_path'
   ```

2. **Check for Handoff Loops**
   ```bash
   # Look for repeated agent patterns
   aws logs filter-log-events \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --filter-pattern '{ $.handoff_path like "*Agent.*Agent.*Agent" }'
   ```

**Resolution:**

- **If handoff loops detected:** Fix agent handoff logic to prevent circular handoffs
- **If legitimate complex workflows:** Increase max_handoffs parameter
- **If unclear intent:** Improve Coordinator agent's intent classification

**Prevention:**
- Clear handoff guidelines in agent prompts
- Unit tests for handoff logic
- Monitor handoff patterns regularly

---

### Issue 4: Session Confirmation Not Sent

**Symptoms:**
- Sessions not receiving confirmation requests
- `confirmation_status` stuck at "scheduled"
- Students not receiving confirmation messages

**Diagnosis:**

1. **Check EventBridge Rule**
   ```bash
   aws events describe-rule --name session-confirmation-trigger
   ```
   - Verify State: ENABLED
   - Verify Schedule: `cron(*/5 * * * ? *)`

2. **Check Lambda Function**
   ```bash
   aws lambda get-function --function-name fitagent-session-confirmation
   ```
   - Verify function exists
   - Check last modified date

3. **Check Lambda Logs**
   ```bash
   aws logs tail /aws/lambda/fitagent-session-confirmation --follow
   ```
   - Look for execution errors
   - Check if sessions are being queried

4. **Check Session Records**
   ```bash
   # Query sessions that should have confirmations
   python scripts/check_pending_confirmations.py
   ```

**Resolution:**

- **If EventBridge rule disabled:** Enable the rule
- **If Lambda errors:** Fix code issues and redeploy
- **If no sessions found:** Verify query logic in `query_sessions_for_confirmation()`
- **If Twilio errors:** Check Twilio credentials and rate limits

**Prevention:**
- Monitor EventBridge rule invocations
- Set up alarms for Lambda function errors
- Test confirmation flow in staging regularly

---

### Issue 5: Agent Timeout

**Symptoms:**
- `NodeTimeoutError` or `ExecutionTimeoutError` in logs
- Incomplete conversations
- Users not receiving responses

**Diagnosis:**

1. **Identify Timeout Type**
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --filter-pattern '{ $.error_type like "Timeout" }'
   ```

2. **Check Agent Duration**
   ```bash
   # Find slow agents
   aws logs insights query \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --start-time $(date -u -d '1 hour ago' +%s) \
     --end-time $(date -u +%s) \
     --query-string 'fields agent_name, duration | filter duration > 30000 | stats count(), avg(duration) by agent_name'
   ```

**Resolution:**

- **If node_timeout:** Optimize specific agent (reduce tool calls, simplify logic)
- **If execution_timeout:** Review overall workflow, consider increasing timeout
- **If external API delay:** Implement timeout on API calls, use async where possible

**Prevention:**
- Set appropriate timeout values based on testing
- Monitor agent execution times
- Optimize slow agents proactively

---

### Issue 6: Multi-Tenant Data Leakage

**Symptoms:**
- Trainer seeing another trainer's data
- Cross-tenant access errors in logs
- Security incident reports

**Diagnosis:**

1. **Check Invocation State Usage**
   ```bash
   # Verify trainer_id is from Invocation_State
   grep -r "ctx.shared_context.get('trainer_id')" src/tools/
   # Should return NO results (insecure pattern)
   ```

2. **Check DynamoDB Queries**
   ```bash
   # Verify all queries include trainer_id filter
   grep -r "db_client.query" src/tools/ | grep -v "trainer_id"
   # Review any results for missing tenant isolation
   ```

3. **Check Logs for Cross-Tenant Attempts**
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --filter-pattern '{ $.error = "Cross-tenant access attempt" }'
   ```

**Resolution:**

- **If code issue:** Fix immediately and deploy hotfix
- **If data exposed:** Notify security team, assess impact, notify affected users
- **If false alarm:** Verify and document

**Prevention:**
- Code review for all tool functions
- Property-based tests for tenant isolation
- Regular security audits

---

### Issue 7: Calendar Sync Failures

**Symptoms:**
- Sessions created but not synced to calendar
- OAuth token errors
- Calendar API rate limit errors

**Diagnosis:**

1. **Check Calendar Agent Logs**
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --filter-pattern '{ $.agent_name = "Calendar_Agent" AND $.level = "ERROR" }'
   ```

2. **Check OAuth Token Status**
   ```bash
   # Query trainer calendar config
   aws dynamodb get-item \
     --table-name fitagent-main \
     --key '{"PK": {"S": "TRAINER#<trainer_id>"}, "SK": {"S": "CALENDAR_CONFIG"}}'
   ```

3. **Check API Rate Limits**
   ```bash
   # Look for rate limit errors
   aws logs filter-log-events \
     --log-group-name /aws/lambda/fitagent-message-processor \
     --filter-pattern '{ $.error like "rate limit" }'
   ```

**Resolution:**

- **If OAuth expired:** Implement token refresh logic
- **If rate limited:** Implement exponential backoff and retry
- **If API error:** Check Google/Microsoft API status, implement graceful degradation

**Prevention:**
- Proactive token refresh before expiration
- Rate limit monitoring and throttling
- Graceful degradation (session created even if sync fails)

---

## Emergency Contacts

### On-Call Rotation

**Primary On-Call:** Check PagerDuty schedule

**Escalation Path:**
1. On-call engineer (immediate)
2. Engineering manager (15 minutes)
3. VP Engineering (30 minutes)

### Key Personnel

**Engineering Team:**
- Lead Engineer: [Name] - [Email] - [Phone]
- Backend Engineer: [Name] - [Email] - [Phone]
- DevOps Engineer: [Name] - [Email] - [Phone]

**Product Team:**
- Product Manager: [Name] - [Email] - [Phone]

**Customer Support:**
- Support Lead: [Name] - [Email] - [Phone]

### External Contacts

**AWS Support:**
- Support Plan: Enterprise
- TAM: [Name] - [Email]
- Support Case Portal: https://console.aws.amazon.com/support/

**Twilio Support:**
- Account Manager: [Name] - [Email]
- Support Portal: https://www.twilio.com/console/support

---

## Appendix

### A. Useful Scripts

**Location:** `scripts/`

- `select_canary_trainers.py` - Select trainers for canary deployment
- `enable_multi_agent.py` - Enable multi-agent for specific trainers
- `disable_multi_agent.py` - Disable multi-agent for specific trainers
- `canary_health_check.py` - Automated health check for canary group
- `emergency_rollback.sh` - Emergency rollback script
- `verify_session_consistency.py` - Data consistency verification
- `check_error_rate.py` - Real-time error rate checker
- `update_performance_baselines.py` - Update performance baselines

### B. CloudWatch Log Groups

- `/aws/lambda/fitagent-webhook-handler`
- `/aws/lambda/fitagent-message-processor`
- `/aws/lambda/fitagent-session-confirmation`
- `/aws/lambda/fitagent-session-reminder`
- `/aws/lambda/fitagent-payment-reminder`
- `/aws/lambda/fitagent-notification-sender`

### C. CloudFormation Stacks

- `fitagent-staging` - Staging environment
- `fitagent-production` - Production environment

### D. DynamoDB Tables

- `fitagent-main` - Main data table
- `fitagent-feature-flags` - Per-trainer feature flags (optional)

### E. S3 Buckets

- `fitagent-receipts-production` - Payment receipt storage
- `fitagent-deployment-production` - Lambda deployment packages

### F. Key Metrics Summary

| Metric | Target | Critical Threshold | Warning Threshold |
|--------|--------|-------------------|-------------------|
| Response Time P95 | < 10s | > 15s | > 10s |
| Error Rate | < 1% | > 5% | > 1% |
| Handoff Count Avg | 2-3 | > 7 | > 5 |
| Confirmation Response Rate | > 80% | < 50% | < 70% |
| Lambda Duration P95 | < 8s | > 12s | > 10s |
| DynamoDB Throttles | 0 | > 10/min | > 1/min |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-01-XX | [Name] | Initial version |

---

**End of Migration Runbook**
