# Bugfix Requirements Document

## Introduction

The `bulk_import_students` tool function is fully implemented in `src/tools/bulk_import_tools.py` but is never registered as a tool in the `student_agent` inside `src/services/strands_agent_service.py`. When a trainer sends "importar alunos do google sheets [URL]" via WhatsApp, the orchestrator routes the message to the `student_agent`, which has no bulk import capability. The agent either times out (30-second `FuturesTimeoutError`) or hits a Bedrock error on retry, producing generic error messages instead of performing the import. Additionally, the orchestrator's routing rules do not mention bulk import keywords, so routing itself may be unreliable.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a trainer sends a message containing "importar alunos" with a Google Sheets URL or CSV data THEN the system returns a timeout error ("A solicitação demorou muito para processar") because the `student_agent` has no `bulk_import_students` tool and cannot fulfill the request within 30 seconds

1.2 WHEN the trainer retries the same bulk import message after a timeout THEN the system returns a Bedrock availability error ("O serviço de IA está temporariamente indisponível") due to cascading failures from the previous failed attempt

1.3 WHEN the orchestrator receives a message containing bulk import keywords ("importar alunos", "planilha", "Google Sheets", "CSV") THEN the orchestrator may fail to route the message to the `student_agent` because its routing rules only mention "registrar aluno, listar alunos, atualizar aluno" and do not include bulk import terminology

### Expected Behavior (Correct)

2.1 WHEN a trainer sends a message containing "importar alunos" with a Google Sheets URL, CSV data, or structured text THEN the system SHALL invoke the `bulk_import_students` tool within the `student_agent`, parse the input, validate and import the students, and return an Import Report

2.2 WHEN the trainer retries a bulk import message THEN the system SHALL process it normally through the `bulk_import_students` tool without cascading errors from previous attempts

2.3 WHEN the orchestrator receives a message containing bulk import keywords ("importar alunos", "import students", "planilha", "Google Sheets", "CSV") THEN the orchestrator SHALL route the message to the `student_agent`

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a trainer sends a message to register a single student (e.g., "registrar aluno João") THEN the system SHALL CONTINUE TO route to the `student_agent` and use the `register_student` tool as before

3.2 WHEN a trainer sends a message to list students (e.g., "listar alunos") THEN the system SHALL CONTINUE TO route to the `student_agent` and use the `view_students` tool as before

3.3 WHEN a trainer sends a message to update a student (e.g., "atualizar aluno") THEN the system SHALL CONTINUE TO route to the `student_agent` and use the `update_student` tool as before

3.4 WHEN a trainer sends a message about sessions, payments, or calendar THEN the system SHALL CONTINUE TO route to the respective `session_agent`, `payment_agent`, or `calendar_agent` as before

3.5 WHEN a trainer sends a general greeting or help message THEN the orchestrator SHALL CONTINUE TO respond directly without calling any domain agent

---

### Bug Condition

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type TrainerMessage
  OUTPUT: boolean
  
  // Returns true when the message is a bulk import request
  RETURN X.message_body contains "importar alunos" OR "import students"
         AND (X.message_body contains Google Sheets URL
              OR X.media_urls contains CSV attachment
              OR X.message_body contains structured text with student records)
END FUNCTION
```

### Fix Checking Property

```pascal
// Property: Fix Checking - Bulk import messages are handled by bulk_import_students tool
FOR ALL X WHERE isBugCondition(X) DO
  result ← student_agent(X)
  ASSERT bulk_import_students tool is available in student_agent's tools
  ASSERT orchestrator routes X to student_agent
  ASSERT result contains Import Report (not timeout or availability error)
END FOR
```

### Preservation Property

```pascal
// Property: Preservation Checking - Non-bulk-import messages behave identically
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT F(X) = F'(X)
END FOR
```
