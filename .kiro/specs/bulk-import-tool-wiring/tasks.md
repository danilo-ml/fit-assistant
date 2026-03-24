# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Bulk Import Tool Missing from Student Agent
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to the concrete failing case: call `_build_domain_agent_tools(trainer_id)` and inspect the `student_agent` tool's inner Agent for `bulk_import_students`
  - Create test file `tests/property/test_bulk_import_wiring_bug.py`
  - Test 1: Build domain agent tools, inspect `student_agent`'s Agent `tools` list — assert `bulk_import_students` IS present (will FAIL on unfixed code, confirming the tool is missing)
  - Test 2: Inspect `student_agent` system prompt — assert it mentions "importar" or "bulk_import" (will FAIL on unfixed code)
  - Test 3: Inspect orchestrator system prompt — assert it contains bulk import routing keywords: "importar alunos", "planilha", "Google Sheets", "CSV" (will FAIL on unfixed code)
  - Use `unittest.mock.patch` to mock `BedrockModel` and `DynamoDBClient` to avoid real AWS calls
  - Use Hypothesis `@given` with `st.text(min_size=1, max_size=20)` for `trainer_id` to verify the bug exists for all trainer IDs
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found: `student_agent` tools list contains only `[register_student, view_students, update_student]`, no `bulk_import_students`; orchestrator prompt lacks "importar alunos", "planilha", "CSV" keywords
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.3, 2.1, 2.3_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Agent Tools and Routing Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Create test file `tests/property/test_bulk_import_wiring_preservation.py`
  - Observe on UNFIXED code: `student_agent` tools list is `[register_student, view_students, update_student]`
  - Observe on UNFIXED code: `session_agent` tools list contains 12 tools (schedule_session, schedule_recurring_session, reschedule_session, cancel_session, cancel_student_sessions, view_calendar, schedule_group_session, enroll_student, remove_student, cancel_group_session, reschedule_group_session, configure_group_size_limit)
  - Observe on UNFIXED code: `payment_agent` tools list contains 4 tools (register_payment, confirm_payment, view_payments, view_payment_status)
  - Observe on UNFIXED code: `calendar_agent` directly calls `connect_calendar` (no Agent tools list)
  - Observe on UNFIXED code: orchestrator routing keywords for session_agent, payment_agent, calendar_agent are present
  - Write property-based test: for all `trainer_id` values, `_build_domain_agent_tools()` returns agents where existing tools are preserved
  - Test 1 (PBT): For all trainer_id, `student_agent` Agent tools include `register_student`, `view_students`, `update_student`
  - Test 2 (PBT): For all trainer_id, `session_agent` Agent tools include all 12 session/group tools
  - Test 3 (PBT): For all trainer_id, `payment_agent` Agent tools include all 4 payment tools
  - Test 4: Orchestrator prompt contains existing routing keywords for all agents (session, payment, calendar)
  - Test 5 (PBT): For all trainer_id, closure-wrapped inner tools correctly bind trainer_id (call `register_student` inner tool and verify `trainer_id` is passed through)
  - Use `unittest.mock.patch` to mock `BedrockModel`, `DynamoDBClient`, and `Agent` to avoid real AWS calls
  - Verify all tests PASS on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Fix for bulk_import_students tool not wired into student_agent

  - [x] 3.1 Implement the fix in `src/services/strands_agent_service.py`
    - Add `bulk_import_tools` to the import statement: change `from tools import student_tools, session_tools, payment_tools, calendar_tools, group_session_tools` to include `bulk_import_tools`
    - Add closure-wrapped `bulk_import_students` inner tool in `_build_domain_agent_tools()` after the existing student domain inner tools section, following the same `@tool` decorator pattern:
      ```python
      @tool
      def bulk_import_students(message_body: str, media_urls: list = None) -> Dict[str, Any]:
          """Import multiple students from structured text, CSV file, or Google Sheets link. Use when the trainer wants to register many students at once via text starting with 'importar alunos', a CSV attachment, or a Google Sheets link."""
          return bulk_import_tools.bulk_import_students(trainer_id, message_body, media_urls)
      ```
    - Add `bulk_import_students` to `student_agent` tools list: change `tools=[register_student, view_students, update_student]` to `tools=[register_student, view_students, update_student, bulk_import_students]`
    - Update `student_agent` system prompt to mention bulk import capability: add "Importar múltiplos alunos de uma vez (bulk_import_students)" to the capabilities list and add instruction "Para importação em massa, use bulk_import_students passando a mensagem completa do usuário como message_body."
    - Update orchestrator routing rules: add "importar alunos", "import students", "planilha", "Google Sheets", "CSV" to the student_agent routing keywords
    - Update the logger.info agents list to include the new tool awareness
    - _Bug_Condition: isBugCondition(input) where input.message_body contains bulk import keywords AND student_agent.tools does NOT contain bulk_import_students_
    - _Expected_Behavior: student_agent.tools contains bulk_import_students, orchestrator routes bulk import messages to student_agent_
    - _Preservation: register_student, view_students, update_student still in student_agent tools; session_agent, payment_agent, calendar_agent unchanged; existing orchestrator routing preserved_
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Bulk Import Tool Available in Student Agent
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior (bulk_import_students in tools, prompt mentions import, orchestrator has routing keywords)
    - When this test passes, it confirms the expected behavior is satisfied
    - Run `pytest tests/property/test_bulk_import_wiring_bug.py -v`
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing Agent Tools and Routing Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run `pytest tests/property/test_bulk_import_wiring_preservation.py -v`
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all existing tools still present, all routing keywords preserved, closure binding still works
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. Checkpoint - Ensure all tests pass
  - Run `pytest tests/property/test_bulk_import_wiring_bug.py tests/property/test_bulk_import_wiring_preservation.py -v`
  - Ensure all tests pass, ask the user if questions arise.
