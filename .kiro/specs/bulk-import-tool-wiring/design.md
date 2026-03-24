# Bulk Import Tool Wiring Bugfix Design

## Overview

The `bulk_import_students` tool is fully implemented in `src/tools/bulk_import_tools.py` but is never wired into the `student_agent` inside `src/services/strands_agent_service.py`. When a trainer sends a bulk import message (e.g., "importar alunos" with a Google Sheets URL), the orchestrator either misroutes or routes to the `student_agent` which lacks the tool, causing a 30-second timeout or Bedrock error. The fix adds a closure-wrapped inner tool to `_build_domain_agent_tools()`, includes it in the `student_agent`'s tools list, updates the `student_agent` system prompt, and adds bulk import keywords to the orchestrator's routing rules.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug — when a trainer sends a bulk import message and the `student_agent` has no `bulk_import_students` tool
- **Property (P)**: The desired behavior — bulk import messages are handled by the `bulk_import_students` tool within the `student_agent`, returning an Import Report
- **Preservation**: Existing single-student registration, student listing, student updates, and all other domain agent routing must remain unchanged
- **`_build_domain_agent_tools()`**: The method in `StrandsAgentService` that creates closure-wrapped inner tools bound to `trainer_id` and assembles domain agents
- **`student_agent`**: The `@tool`-decorated function that creates a Strands `Agent` with student management tools (currently: `register_student`, `view_students`, `update_student`)
- **orchestrator**: The top-level Strands `Agent` that routes trainer messages to the correct domain agent based on keyword matching in its system prompt

## Bug Details

### Bug Condition

The bug manifests when a trainer sends a WhatsApp message requesting bulk student import. The `student_agent` does not have the `bulk_import_students` tool in its tools list, and the orchestrator's routing rules do not mention bulk import keywords. The agent either times out trying to fulfill the request with only `register_student`/`view_students`/`update_student`, or the orchestrator fails to route to the correct agent entirely.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type TrainerMessage
  OUTPUT: boolean

  RETURN (
    input.message_body contains "importar alunos"
    OR input.message_body contains "import students"
    OR (input.message_body contains Google Sheets URL AND input.message_body contains "importar" or "import")
    OR (input.media_urls contains CSV attachment AND input.message_body contains "importar" or "import")
  )
  AND student_agent.tools does NOT contain bulk_import_students
END FUNCTION
```

### Examples

- Trainer sends "importar alunos\nJoão;+5511999999999;joao@email.com;Perder peso" → Expected: Import Report with 1 student imported. Actual: 30-second timeout error.
- Trainer sends "importar alunos do google sheets https://docs.google.com/spreadsheets/d/abc123/edit" → Expected: Import Report from Google Sheets data. Actual: Timeout or Bedrock error on retry.
- Trainer sends CSV attachment with caption "importar alunos" → Expected: CSV parsed and Import Report returned. Actual: Timeout because `student_agent` cannot handle CSV imports.
- Trainer sends "planilha de alunos https://docs.google.com/spreadsheets/d/abc123/edit" → Expected: Orchestrator routes to `student_agent` which invokes bulk import. Actual: Orchestrator may not route correctly because "planilha" is not in routing rules.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Single student registration via `register_student` tool must continue to work exactly as before
- Student listing via `view_students` tool must continue to work exactly as before
- Student updates via `update_student` tool must continue to work exactly as before
- Session, payment, and calendar agent routing and behavior must remain unchanged
- General greetings and help messages must continue to be handled directly by the orchestrator
- The `process_message` method signature and return format must remain unchanged

**Scope:**
All inputs that do NOT involve bulk import keywords or bulk import intent should be completely unaffected by this fix. This includes:
- Single student registration messages (e.g., "registrar aluno João")
- Student listing messages (e.g., "listar alunos")
- Student update messages (e.g., "atualizar aluno")
- Session, payment, and calendar messages
- General conversation (greetings, help requests)

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **Missing Inner Tool**: `_build_domain_agent_tools()` in `strands_agent_service.py` creates closure-wrapped inner tools for `register_student`, `view_students`, and `update_student`, but never creates a corresponding `bulk_import_students` inner tool. The tool in `src/tools/bulk_import_tools.py` expects `trainer_id`, `message_body`, and `media_urls` as parameters, but `trainer_id` must be injected via closure (same pattern as other tools).

2. **Missing Tool in student_agent Tools List**: The `student_agent` function creates an `Agent` with `tools=[register_student, view_students, update_student]`. Even if the inner tool existed, it would need to be added to this list.

3. **Incomplete student_agent System Prompt**: The `student_agent`'s system prompt only mentions "Registrar novos alunos", "Listar alunos cadastrados", and "Atualizar informações de alunos". It does not mention bulk import capability, so the sub-agent would not know when to invoke the tool.

4. **Missing Orchestrator Routing Keywords**: The orchestrator's system prompt routing rules for `student_agent` only list "aluno", "aluna", "registrar aluno", "listar alunos", "atualizar aluno". Keywords like "importar alunos", "import students", "planilha", "Google Sheets", "CSV" are absent, so the orchestrator may not route bulk import messages to the `student_agent`.

5. **`message_body` and `media_urls` Not Available to Inner Tool**: The current `process_message` method passes only `message` (text string) to the orchestrator. The `bulk_import_students` tool needs the raw `message_body` text and `media_urls` list. The inner tool closure must capture these from the orchestrator's query context or they must be passed as tool parameters by the LLM. Since the tool's `message_body` and `media_urls` parameters are declared in the tool signature, the LLM agent will pass them from the query context.

## Correctness Properties

Property 1: Bug Condition - Bulk Import Tool Available in Student Agent

_For any_ trainer message where the bug condition holds (message contains bulk import keywords with student data, Google Sheets URL, or CSV attachment), the `student_agent` SHALL have the `bulk_import_students` tool in its tools list, and the orchestrator SHALL route the message to the `student_agent`, which SHALL invoke `bulk_import_students` and return an Import Report (not a timeout or availability error).

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation - Non-Bulk-Import Behavior Unchanged

_For any_ trainer message where the bug condition does NOT hold (message does not contain bulk import keywords), the fixed code SHALL produce exactly the same routing and tool invocation behavior as the original code, preserving single-student registration, student listing, student updates, and all other domain agent functionality.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `src/services/strands_agent_service.py`

**Method**: `_build_domain_agent_tools()`

**Specific Changes**:

1. **Add import for bulk_import_tools**: Add `from tools import bulk_import_tools` to the existing tools import line at the top of the file (or within the method).

2. **Create closure-wrapped `bulk_import_students` inner tool**: Following the same pattern as `register_student`, `view_students`, and `update_student`, add a new `@tool`-decorated inner function that binds `trainer_id` via closure and passes `message_body` and `media_urls` through to `bulk_import_tools.bulk_import_students`:
   ```python
   @tool
   def bulk_import_students(message_body: str, media_urls: list = None) -> Dict[str, Any]:
       """Import multiple students from structured text, CSV file, or Google Sheets link. Use when the trainer wants to register many students at once via text starting with 'importar alunos', a CSV attachment, or a Google Sheets link."""
       return bulk_import_tools.bulk_import_students(trainer_id, message_body, media_urls)
   ```

3. **Add `bulk_import_students` to student_agent tools list**: Change the `student_agent` Agent creation from `tools=[register_student, view_students, update_student]` to `tools=[register_student, view_students, update_student, bulk_import_students]`.

4. **Update student_agent system prompt**: Add bulk import capability description to the system prompt:
   - Add "Importar múltiplos alunos de uma vez (bulk_import_students)" to the list of capabilities
   - Add instruction: "Para importação em massa, use bulk_import_students passando a mensagem completa do usuário como message_body."

5. **Update orchestrator routing rules**: Add bulk import keywords to the `student_agent` routing rule in the orchestrator system prompt:
   - Change: `Palavras como "aluno", "aluna", "registrar aluno", "listar alunos", "atualizar aluno" → student_agent`
   - To: `Palavras como "aluno", "aluna", "registrar aluno", "listar alunos", "atualizar aluno", "importar alunos", "import students", "planilha", "Google Sheets", "CSV" → student_agent`

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Inspect the `student_agent` tools list and orchestrator system prompt on UNFIXED code to confirm the tool is missing and routing keywords are absent. Then simulate a bulk import message and observe the failure mode.

**Test Cases**:
1. **Tool Availability Test**: Build domain agent tools and inspect `student_agent`'s Agent tools list — assert `bulk_import_students` is NOT present (will pass on unfixed code, confirming the bug)
2. **Orchestrator Routing Test**: Inspect orchestrator system prompt for bulk import keywords — assert keywords like "importar alunos", "planilha", "CSV" are NOT present (will pass on unfixed code)
3. **Student Agent Prompt Test**: Inspect `student_agent` system prompt for bulk import mention — assert it does NOT mention bulk import (will pass on unfixed code)

**Expected Counterexamples**:
- `student_agent` tools list contains only `[register_student, view_students, update_student]` — no `bulk_import_students`
- Orchestrator routing rules do not contain "importar alunos", "planilha", "Google Sheets", or "CSV"

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  tools = _build_domain_agent_tools(input.trainer_id)
  student_agent_tools = inspect tools.student_agent.Agent.tools
  ASSERT bulk_import_students IN student_agent_tools
  ASSERT orchestrator_prompt CONTAINS "importar alunos"
  ASSERT orchestrator_prompt CONTAINS "planilha"
  ASSERT orchestrator_prompt CONTAINS "Google Sheets"
  ASSERT orchestrator_prompt CONTAINS "CSV"
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT _build_domain_agent_tools_original(input) tools == _build_domain_agent_tools_fixed(input) tools (minus bulk_import_students addition)
  ASSERT student_agent still has register_student, view_students, update_student
  ASSERT session_agent, payment_agent, calendar_agent are unchanged
  ASSERT orchestrator still routes non-bulk-import messages identically
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many trainer message variations automatically across the input domain
- It catches edge cases where routing keywords might accidentally overlap
- It provides strong guarantees that non-bulk-import behavior is unchanged

**Test Plan**: Observe the tool lists and system prompts on UNFIXED code first, then write property-based tests verifying that the fix only adds the new tool and keywords without removing or altering existing ones.

**Test Cases**:
1. **Existing Tools Preservation**: Verify `register_student`, `view_students`, `update_student` are still present in `student_agent` tools after fix
2. **Other Agents Preservation**: Verify `session_agent`, `payment_agent`, `calendar_agent` tools lists are identical before and after fix
3. **Orchestrator Routing Preservation**: Verify existing routing keywords for all agents are still present in the orchestrator prompt after fix

### Unit Tests

- Test that `_build_domain_agent_tools()` returns a `student_agent` whose Agent includes `bulk_import_students` in its tools
- Test that the `bulk_import_students` inner tool correctly binds `trainer_id` via closure and delegates to `bulk_import_tools.bulk_import_students`
- Test that the `student_agent` system prompt mentions bulk import
- Test that the orchestrator system prompt contains all bulk import routing keywords
- Test that existing tools (`register_student`, `view_students`, `update_student`) are still present

### Property-Based Tests

- Generate random non-bulk-import trainer messages and verify they route to the same agent as before the fix
- Generate random trainer_id values and verify the closure correctly binds each one to the inner `bulk_import_students` tool
- Generate random message variations with bulk import keywords and verify the orchestrator prompt would match them to `student_agent`

### Integration Tests

- End-to-end: Send a structured text bulk import message through `process_message` and verify the `bulk_import_students` tool is invoked (with mocked Bedrock)
- End-to-end: Send a Google Sheets URL bulk import message and verify routing and tool invocation
- Verify that a single student registration message still works correctly after the fix
