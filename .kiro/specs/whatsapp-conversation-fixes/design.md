# WhatsApp Conversation Fixes Bugfix Design

## Overview

This design addresses two critical bugs in FitAgent's WhatsApp conversation system:

1. **Message Ordering Bug**: Messages are processed in parallel via SQS, causing responses to arrive out of order and breaking conversational flow. The fix implements sequential processing per phone number using SQS message group IDs with FIFO queues.

2. **Missing Brazilian Portuguese Support**: All user-facing messages are in English instead of Brazilian Portuguese (pt-BR). The fix adds pt-BR language support to the AI agent system prompt, onboarding flow, error messages, and tool responses while keeping code and documentation in English.

The solution maintains the existing serverless architecture (webhook → SQS → Lambda) without requiring synchronous processing, using AWS SQS FIFO queues with message group IDs to ensure ordering guarantees per phone number.

## Glossary

- **Bug_Condition_Ordering (C1)**: The condition that triggers message ordering issues - when multiple messages from the same phone number are processed concurrently
- **Bug_Condition_Language (C2)**: The condition that triggers language issues - when the system generates user-facing text in English instead of Portuguese
- **Property_Ordering (P1)**: The desired behavior for message ordering - messages from the same phone number must be processed sequentially in arrival order
- **Property_Language (P2)**: The desired behavior for language - all user-facing text must be in Brazilian Portuguese (pt-BR)
- **Preservation**: Existing functionality that must remain unchanged - serverless architecture, tool functions, DynamoDB schema, code/documentation language
- **Message Group ID**: SQS FIFO feature that ensures messages with the same group ID are processed in order
- **FIFO Queue**: First-In-First-Out queue that guarantees message ordering and exactly-once processing
- **System Prompt**: Instructions given to the AI agent (Claude) that define its behavior and language
- **pt-BR**: Brazilian Portuguese language code (ISO 639-1 with regional variant)

## Bug Details

### Bug Condition 1: Message Ordering

The message ordering bug manifests when a user sends multiple WhatsApp messages in quick succession. The current architecture uses a standard SQS queue which processes messages in parallel without ordering guarantees. This causes race conditions where:
- Message B's response arrives before Message A's response
- Conversation state updates from concurrent processors overwrite each other (last write wins)
- The AI agent loses conversational context because messages are processed out of sequence

**Formal Specification:**
```
FUNCTION isBugCondition_Ordering(messages)
  INPUT: messages of type List[Message] where Message has {phone_number, timestamp, message_id}
  OUTPUT: boolean
  
  RETURN EXISTS i, j IN messages WHERE
         messages[i].phone_number == messages[j].phone_number
         AND messages[i].timestamp < messages[j].timestamp
         AND messages[j].processing_start_time < messages[i].processing_complete_time
         AND i != j
END FUNCTION
```

This condition identifies when two or more messages from the same phone number have overlapping processing windows, which can cause out-of-order responses.

### Bug Condition 2: Language Support

The language bug manifests whenever the system generates user-facing text. The AI agent's system prompt, onboarding flow messages, error messages, and tool responses are all hardcoded in English. Brazilian users cannot use the system effectively because they don't understand the prompts and responses.

**Formal Specification:**
```
FUNCTION isBugCondition_Language(output)
  INPUT: output of type UserFacingText where UserFacingText has {text, language, context}
  OUTPUT: boolean
  
  RETURN output.language == "en" 
         AND output.context IN ["ai_response", "onboarding_message", "error_message", "tool_response"]
         AND output.intended_audience == "end_user"
END FUNCTION
```

This condition identifies when user-facing text is generated in English instead of the required Brazilian Portuguese.

### Examples

**Message Ordering Bug:**
- User sends "Schedule session with John tomorrow at 2pm" (Message A, t=0)
- User sends "Actually make it 3pm" (Message B, t=2 seconds)
- System processes both in parallel
- Response to Message B arrives first: "I've updated the session to 3pm"
- Response to Message A arrives second: "I've scheduled a session with John at 2pm"
- User is confused - which time is correct?

**Language Bug:**
- Brazilian trainer sends first message to FitAgent
- System responds: "Welcome to FitAgent! 👋 I'm your AI assistant..."
- Expected: "Bem-vindo ao FitAgent! 👋 Sou seu assistente de IA..."
- Trainer cannot understand the English prompts and abandons the system

**Edge Cases:**
- Single message from user: No ordering issue (only one message to process)
- Messages from different phone numbers: Can be processed in parallel (no shared state)
- Message arrives while previous message is still processing: Must wait for completion before starting

## Expected Behavior

### Bug Fix 1: Message Ordering

**For any** sequence of messages from the same phone number, the system SHALL process them sequentially in the order they were received, ensuring:
- Message N+1 does not start processing until Message N completes
- Conversation state updates are applied in order without race conditions
- AI agent responses reflect the correct conversational context
- Users receive responses in the same order as their questions

**Implementation Approach:**
Use SQS FIFO queue with message group ID set to the phone number. This ensures:
- Messages with the same phone number (group ID) are processed in strict order
- Messages from different phone numbers can still be processed in parallel
- No changes required to Lambda function logic (SQS handles ordering)
- Maintains serverless architecture without synchronous processing

### Bug Fix 2: Language Support

**For any** user-facing text generated by the system, the output SHALL be in Brazilian Portuguese (pt-BR), including:
- AI agent responses to trainer and student messages
- Onboarding flow prompts and instructions
- Error messages and validation feedback
- Tool execution confirmations and results
- Session reminders and notifications

**Implementation Approach:**
- Update AI agent system prompt to instruct Claude to respond in pt-BR
- Translate all hardcoded strings in OnboardingHandler to Portuguese
- Add pt-BR error message templates
- Update tool response formatting to use Portuguese
- Keep code comments, variable names, logs, and documentation in English

### Preservation Requirements

**Unchanged Behaviors:**
- Serverless architecture with webhook → SQS → Lambda flow continues to work
- All 10 tool functions execute with the same parameters and validation
- DynamoDB schema and conversation state structure remain unchanged
- Phone number lookup via phone-number-index GSI continues to work
- Calendar integration, payment tracking, and receipt storage work as before
- Code, comments, logs, and documentation remain in English for developers

**Scope:**
All functionality not directly related to message ordering or user-facing language must remain completely unaffected. This includes:
- Tool function implementations (register_student, schedule_session, etc.)
- DynamoDB queries and data structures
- Twilio API integration
- AWS Bedrock API calls (only system prompt changes)
- Infrastructure configuration
- Test suite structure

## Hypothesized Root Cause

### Message Ordering Bug

Based on the architecture analysis, the root cause is:

1. **Standard SQS Queue Without Ordering**: The current implementation uses a standard SQS queue which does not guarantee message ordering. Standard queues optimize for throughput and allow parallel processing of messages.

2. **Parallel Lambda Invocations**: When multiple messages arrive in quick succession, SQS invokes multiple Lambda instances in parallel. Each instance processes its message independently without coordination.

3. **Race Condition in State Updates**: The ConversationStateManager uses simple put_item operations without optimistic locking. When two Lambda instances update conversation state concurrently, the last write wins, potentially losing context from the earlier message.

4. **No Message Sequencing Logic**: The message_processor.py Lambda handler has no logic to detect or prevent concurrent processing of messages from the same phone number.

### Language Bug

Based on the code analysis, the root cause is:

1. **English System Prompt**: The AI agent's system prompt in `_build_system_prompt()` is hardcoded in English with no language specification for Claude.

2. **Hardcoded English Strings**: The OnboardingHandler class contains hardcoded English strings for all onboarding messages (welcome, prompts, confirmations).

3. **No Localization Framework**: The codebase has no i18n/l10n framework or language configuration. All user-facing strings are inline English text.

4. **Missing Language Context**: The AI agent does not receive any instruction about the target language for responses, so Claude defaults to English.

## Correctness Properties

Property 1: Message Ordering - Sequential Processing Per Phone Number

_For any_ sequence of messages M1, M2, ..., Mn from the same phone number where M1 arrives before M2 before ... before Mn, the fixed system SHALL process message Mi+1 only after message Mi has completed processing, ensuring responses are sent in the same order as the questions and conversation state updates are applied sequentially without race conditions.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Language Support - Brazilian Portuguese Responses

_For any_ user-facing text generated by the system (AI responses, onboarding messages, error messages, tool confirmations), the fixed system SHALL output text in Brazilian Portuguese (pt-BR) with culturally appropriate phrasing, while maintaining English for all code, comments, logs, and developer documentation.

**Validates: Requirements 2.5, 2.6, 2.7, 2.8**

Property 3: Preservation - Parallel Processing Across Phone Numbers

_For any_ set of messages from different phone numbers, the fixed system SHALL continue to process them in parallel without artificial serialization, maintaining the same throughput and performance characteristics as the original system for non-conflicting messages.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

Property 4: Preservation - Tool Function Behavior

_For any_ tool function invocation (register_student, schedule_session, etc.), the fixed system SHALL execute it with the same parameters, validation logic, and return values as the original system, preserving all existing functionality for trainers and students.

**Validates: Requirements 3.5, 3.6, 3.7, 3.8**

Property 5: Preservation - Developer Language

_For any_ code file, log message, or documentation, the fixed system SHALL continue to use English for all developer-facing content, ensuring maintainability and consistency with software development best practices.

**Validates: Requirements 3.9, 3.10, 3.11**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

#### Fix 1: Message Ordering (SQS FIFO Queue)

**File**: `infrastructure/template.yml` (CloudFormation)

**Resource**: SQS Queue Definition

**Specific Changes**:
1. **Convert to FIFO Queue**: Change queue type from Standard to FIFO
   - Add `.fifo` suffix to queue name
   - Set `FifoQueue: true` property
   - Enable `ContentBasedDeduplication: true` for automatic deduplication

2. **Configure Dead Letter Queue**: Update DLQ to FIFO type as well
   - FIFO queues require FIFO DLQs
   - Maintain existing retry policy (3 attempts)

**File**: `src/handlers/webhook_handler.py`

**Function**: Message sending to SQS

**Specific Changes**:
1. **Add Message Group ID**: Set MessageGroupId to phone number when sending to SQS
   - Extract phone number from webhook payload
   - Use phone number as MessageGroupId (ensures ordering per user)
   - This groups all messages from the same phone number for sequential processing

2. **Add Message Deduplication ID**: Set MessageDeduplicationId to message_sid
   - Prevents duplicate processing if Twilio retries webhook
   - Uses Twilio's unique message_sid as deduplication key

**File**: `src/handlers/message_processor.py`

**Function**: Lambda handler

**Specific Changes**:
1. **Update Batch Processing**: Ensure batch size is set to 1 for FIFO queues
   - FIFO queues with message groups work best with batch size 1
   - Prevents head-of-line blocking across different phone numbers
   - Configure in Lambda event source mapping

2. **Add Logging**: Log message group ID for debugging
   - Track which phone number's messages are being processed
   - Monitor ordering behavior in CloudWatch

#### Fix 2: Language Support (Brazilian Portuguese)

**File**: `src/services/ai_agent.py`

**Function**: `_build_system_prompt`

**Specific Changes**:
1. **Add Language Instruction**: Prepend language directive to system prompt
   - Add: "IMPORTANT: You MUST respond in Brazilian Portuguese (pt-BR) for all user-facing messages."
   - Add: "Use natural, conversational Brazilian Portuguese with appropriate cultural context."
   - Add: "Keep technical terms in Portuguese when common Brazilian equivalents exist."

2. **Translate System Prompt Content**: Convert all user-facing instructions to Portuguese
   - "You are FitAgent..." → "Você é o FitAgent..."
   - "Your capabilities:" → "Suas capacidades:"
   - "Guidelines:" → "Diretrizes:"
   - Keep tool names and parameters in English (they're code identifiers)

3. **Add Examples**: Include Portuguese response examples in system prompt
   - Show Claude how to format confirmations in Portuguese
   - Demonstrate appropriate tone and formality level for Brazilian context

**File**: `src/services/conversation_handlers.py`

**Class**: `OnboardingHandler`

**Specific Changes**:
1. **Translate Welcome Message**: Convert `_send_welcome_message()` to Portuguese
   - "Welcome to FitAgent!" → "Bem-vindo ao FitAgent!"
   - "I'm your AI assistant..." → "Sou seu assistente de IA..."
   - "Are you a:" → "Você é:"
   - "Personal Trainer" → "Personal Trainer" (keep as is - common term in Brazil)
   - "Student" → "Aluno"

2. **Translate User Type Selection**: Convert `_handle_user_type_selection()` responses
   - "Great! Let's get you set up..." → "Ótimo! Vamos configurar sua conta..."
   - "What's your full name?" → "Qual é o seu nome completo?"
   - "Thanks for your interest!" → "Obrigado pelo seu interesse!"

3. **Translate Registration Flow**: Convert all prompts in name/email/business handlers
   - "Nice to meet you" → "Prazer em conhecê-lo"
   - "What's your email address?" → "Qual é o seu endereço de e-mail?"
   - "Please provide a valid email..." → "Por favor, forneça um e-mail válido..."
   - "What's your business name?" → "Qual é o nome do seu negócio?"

4. **Translate Validation Messages**: Convert all error/validation messages
   - "I didn't understand that" → "Não entendi isso"
   - "Please provide..." → "Por favor, forneça..."
   - "at least 2 characters" → "pelo menos 2 caracteres"

**File**: `src/services/conversation_handlers.py`

**Classes**: `TrainerHandler`, `StudentHandler`

**Specific Changes**:
1. **Translate Menu Messages**: Convert menu options and instructions to Portuguese
   - Student menu: "View upcoming sessions" → "Ver próximas sessões"
   - Confirmation prompts: "Did you complete this session?" → "Você completou esta sessão?"

2. **Translate Error Messages**: Convert error responses to Portuguese
   - "Sorry, I encountered an error" → "Desculpe, encontrei um erro"
   - "Please try again" → "Por favor, tente novamente"

**File**: `src/tools/*.py` (all tool modules)

**Functions**: All tool functions

**Specific Changes**:
1. **Add Portuguese Response Formatting**: Update return messages to Portuguese
   - Success messages: "Student registered successfully" → "Aluno registrado com sucesso"
   - Error messages: "Student not found" → "Aluno não encontrado"
   - Validation errors: "Invalid date format" → "Formato de data inválido"

2. **Keep Code in English**: Maintain English for:
   - Function names, variable names, parameter names
   - Code comments and docstrings
   - Log messages
   - Error types and exception messages (for developers)

**File**: `src/utils/validation.py`

**Functions**: Validation error messages

**Specific Changes**:
1. **Create Portuguese Error Messages**: Add pt-BR error message templates
   - Phone number validation: "Invalid phone number format" → "Formato de número de telefone inválido"
   - Email validation: "Invalid email address" → "Endereço de e-mail inválido"
   - Date validation: "Invalid date" → "Data inválida"

2. **Add Language Parameter**: Allow validation functions to return Portuguese messages
   - Add optional `language='pt-BR'` parameter to validation functions
   - Return appropriate language based on parameter

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bugs on unfixed code, then verify the fixes work correctly and preserve existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate both bugs BEFORE implementing the fixes. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan for Message Ordering**: Write integration tests that send multiple messages from the same phone number in rapid succession to the webhook endpoint. Observe the order of responses and conversation state updates on the UNFIXED code to confirm out-of-order processing.

**Test Cases for Message Ordering**:
1. **Rapid Sequential Messages**: Send 3 messages from same phone number with 100ms delay (will show out-of-order responses on unfixed code)
2. **State Update Race Condition**: Send 2 messages that both update conversation context, verify last-write-wins behavior (will show lost context on unfixed code)
3. **Conversation Context Loss**: Send follow-up question that depends on previous message context (will show context loss on unfixed code)
4. **Different Phone Numbers**: Send messages from 2 different phone numbers simultaneously (should work correctly even on unfixed code - parallel processing is desired)

**Expected Counterexamples for Ordering**:
- Responses arrive in different order than questions
- Conversation state shows only the last message's context, losing earlier updates
- AI agent responds without context from previous message in sequence
- Possible causes: parallel Lambda invocations, standard SQS queue, no message group ID

**Test Plan for Language**: Write tests that trigger onboarding flow and AI agent responses on the UNFIXED code. Capture the actual English responses and verify they match the hardcoded English strings.

**Test Cases for Language**:
1. **Onboarding Welcome**: Send first message from unregistered number (will show English welcome on unfixed code)
2. **AI Agent Response**: Send trainer message requesting student list (will show English response on unfixed code)
3. **Error Message**: Send invalid input to trigger validation error (will show English error on unfixed code)
4. **Tool Confirmation**: Schedule a session and verify confirmation message (will show English confirmation on unfixed code)

**Expected Counterexamples for Language**:
- All user-facing text is in English
- Onboarding flow shows "Welcome to FitAgent!" instead of "Bem-vindo ao FitAgent!"
- AI responses are in English instead of Portuguese
- Possible causes: English system prompt, hardcoded English strings, no language configuration

### Fix Checking

**Goal**: Verify that for all inputs where the bug conditions hold, the fixed system produces the expected behavior.

**Pseudocode for Message Ordering:**
```
FOR ALL message_sequence WHERE isBugCondition_Ordering(message_sequence) DO
  responses := process_messages_fixed(message_sequence)
  ASSERT responses are in same order as message_sequence
  ASSERT conversation_state reflects all messages in sequence
  ASSERT no race conditions in state updates
END FOR
```

**Pseudocode for Language:**
```
FOR ALL user_interaction WHERE isBugCondition_Language(user_interaction) DO
  output := generate_response_fixed(user_interaction)
  ASSERT output.language == "pt-BR"
  ASSERT output.text contains Portuguese words and grammar
  ASSERT output.text is culturally appropriate for Brazilian users
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug conditions do NOT hold, the fixed system produces the same result as the original system.

**Pseudocode for Ordering Preservation:**
```
FOR ALL message WHERE is_single_message(message) OR is_different_phone_numbers(messages) DO
  ASSERT process_messages_original(message) == process_messages_fixed(message)
END FOR
```

**Pseudocode for Language Preservation:**
```
FOR ALL code_element WHERE code_element.type IN ["code", "comment", "log", "documentation"] DO
  ASSERT code_element.language == "en"
  ASSERT code_element.language_fixed == "en"
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan for Ordering Preservation**: Observe behavior on UNFIXED code for single messages and different phone numbers, then write property-based tests capturing that behavior.

**Test Cases for Ordering Preservation**:
1. **Single Message Processing**: Verify single messages are processed with same latency and behavior
2. **Parallel Phone Numbers**: Verify messages from different phone numbers still process in parallel
3. **Tool Execution**: Verify all tool functions execute with same results
4. **Conversation State**: Verify state structure and TTL behavior unchanged

**Test Plan for Language Preservation**: Verify code, logs, and documentation remain in English after fix.

**Test Cases for Language Preservation**:
1. **Code Language**: Verify function names, variables, comments remain in English
2. **Log Messages**: Verify CloudWatch logs are still in English for debugging
3. **Documentation**: Verify README, docstrings, and comments unchanged
4. **Infrastructure**: Verify CloudFormation templates and parameters in English

### Unit Tests

**Message Ordering:**
- Test SQS message group ID assignment based on phone number
- Test FIFO queue configuration in CloudFormation
- Test message deduplication ID assignment
- Test batch size configuration for Lambda event source

**Language Support:**
- Test system prompt contains Portuguese language instruction
- Test onboarding messages are in Portuguese
- Test AI agent responses are in Portuguese
- Test error messages are in Portuguese
- Test tool confirmations are in Portuguese
- Test code and logs remain in English

### Property-Based Tests

**Message Ordering:**
- Generate random sequences of messages from same phone number, verify sequential processing
- Generate random message arrival patterns, verify no race conditions in state updates
- Generate random phone number combinations, verify parallel processing for different numbers

**Language Support:**
- Generate random user inputs, verify all responses are in Portuguese
- Generate random error conditions, verify all error messages are in Portuguese
- Generate random tool invocations, verify all confirmations are in Portuguese
- Generate random code files, verify all code remains in English

### Integration Tests

**Message Ordering:**
- Test full flow: webhook → FIFO SQS → Lambda with multiple rapid messages
- Test conversation state updates with sequential messages
- Test AI agent context preservation across message sequence
- Test different phone numbers process in parallel

**Language Support:**
- Test full onboarding flow in Portuguese from first message to completion
- Test trainer conversation flow with AI agent in Portuguese
- Test student conversation flow in Portuguese
- Test error handling and validation messages in Portuguese
- Test that logs and CloudWatch metrics remain in English
