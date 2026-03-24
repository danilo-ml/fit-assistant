# Bugfix Requirements Document

## Introduction

When a trainer sends "Conectar calendário google" via WhatsApp, the AI orchestrator agent responds with a message like "clique no link acima para autorizar" (click the link above to authorize) but never actually includes the Google Calendar OAuth authorization URL in the response. The trainer sees instructions to click a non-existent link, making it impossible to connect their Google Calendar.

The root cause is in the multi-agent architecture: the `calendar_agent` tool function correctly generates the OAuth URL and returns it as a string, but the orchestrator LLM (which receives this as a tool result) paraphrases the response instead of passing the URL through verbatim. The LLM refers to "the link above" without actually including the URL in its generated output.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a trainer requests to connect Google Calendar (e.g., "Conectar calendário google") THEN the orchestrator agent responds with text referencing a link (e.g., "clique no link acima") but the OAuth authorization URL is not included in the final response sent to the user.

1.2 WHEN a trainer requests to connect Outlook Calendar (e.g., "Conectar calendário outlook") THEN the orchestrator agent may similarly respond referencing a link without actually including the OAuth authorization URL in the final response.

1.3 WHEN the `calendar_agent` tool returns a response string containing the OAuth URL to the orchestrator THEN the orchestrator LLM paraphrases or summarizes the tool result instead of preserving the complete URL, resulting in the link being lost.

### Expected Behavior (Correct)

2.1 WHEN a trainer requests to connect Google Calendar THEN the system SHALL return a response that contains the complete Google Calendar OAuth authorization URL (starting with `https://accounts.google.com/o/oauth2/v2/auth?`) so the trainer can click it to authorize.

2.2 WHEN a trainer requests to connect Outlook Calendar THEN the system SHALL return a response that contains the complete Outlook OAuth authorization URL (starting with `https://login.microsoftonline.com/`) so the trainer can click it to authorize.

2.3 WHEN the `calendar_agent` tool generates an OAuth URL THEN the system SHALL ensure the URL is present verbatim in the final response delivered to the trainer, regardless of LLM paraphrasing behavior.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a trainer sends a non-calendar message (e.g., student management, session scheduling, payments) THEN the system SHALL CONTINUE TO route to the appropriate domain agent and return correct responses.

3.2 WHEN the `connect_calendar` tool fails (e.g., invalid provider, missing OAuth credentials, trainer not found) THEN the system SHALL CONTINUE TO return an appropriate error message to the trainer.

3.3 WHEN a trainer sends a general greeting or help request THEN the system SHALL CONTINUE TO respond directly without calling any domain agent tools.

3.4 WHEN the OAuth state token is stored in DynamoDB during calendar connection THEN the system SHALL CONTINUE TO store it with the correct trainer_id, provider, and TTL expiration.
