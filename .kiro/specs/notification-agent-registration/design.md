# Notification Agent Registration Bugfix Design

## Overview

O agente orquestrador Strands em `src/services/strands_agent_service.py` utiliza o padrão Agents-as-Tools com 4 agentes de domínio (student, session, payment, calendar), mas não possui um `notification_agent`. A ferramenta `send_notification` já está totalmente implementada em `src/tools/notification_tools.py`, porém nunca é registrada como ferramenta acessível ao orquestrador. O fix consiste em criar um `notification_agent` seguindo o mesmo padrão dos agentes existentes e adicioná-lo à lista de tools do orquestrador.

## Glossary

- **Bug_Condition (C)**: O orquestrador recebe uma solicitação de notificação/mensagem para alunos, mas não possui `notification_agent` na sua lista de tools
- **Property (P)**: Quando o orquestrador recebe uma solicitação de notificação, ele deve delegar para o `notification_agent` que chama `send_notification()` e retorna confirmação
- **Preservation**: Os 4 agentes existentes (student, session, payment, calendar) e o comportamento de resposta direta para saudações devem continuar funcionando exatamente como antes
- **notification_tools.send_notification()**: Função em `src/tools/notification_tools.py` que valida trainer, seleciona destinatários, enfileira mensagens no SQS e retorna confirmação
- **_build_domain_agent_tools()**: Método em `StrandsAgentService` que cria os agentes de domínio como `@tool` functions vinculados ao `trainer_id`
- **orchestrator_prompt**: System prompt do agente orquestrador que define regras de roteamento para cada agente

## Bug Details

### Bug Condition

O bug se manifesta quando um trainer envia uma mensagem solicitando envio de notificação ou mensagem para alunos. O método `_build_domain_agent_tools()` cria apenas 4 agentes (student, session, payment, calendar) e o `notification_tools` nunca é importado nem utilizado. O orquestrador não tem como rotear solicitações de notificação.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type TrainerMessage
  OUTPUT: boolean
  
  RETURN input.intent IN ['send_notification', 'send_message', 'notify_students', 'broadcast']
         AND input.message MATCHES keywords ['notificação', 'notificar', 'avisar', 'mensagem para alunos', 'enviar mensagem']
         AND 'notification_agent' NOT IN orchestrator.tools
END FUNCTION
```

### Examples

- Trainer envia "envie uma notificação para todos os alunos avisando que a academia fecha amanhã" → Esperado: notification_agent enfileira mensagens no SQS. Atual: orquestrador responde que não tem essa capacidade
- Trainer envia "avise os alunos com treino amanhã que a academia estará fechada" → Esperado: notification_agent chama send_notification com recipients="upcoming_sessions". Atual: orquestrador ignora ou tenta usar outro agente
- Trainer envia "mande uma mensagem para o aluno João sobre o horário novo" → Esperado: notification_agent envia para aluno específico. Atual: orquestrador não consegue executar
- Trainer envia "notifique todos os alunos" sem mensagem → Esperado: notification_agent solicita o conteúdo da mensagem. Atual: orquestrador não tem agente para rotear

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- student_agent deve continuar gerenciando alunos (registrar, listar, atualizar, importar) exatamente como antes
- session_agent deve continuar gerenciando sessões (agendar, reagendar, cancelar, ver calendário) exatamente como antes
- payment_agent deve continuar gerenciando pagamentos (registrar, confirmar, visualizar) exatamente como antes
- calendar_agent deve continuar gerenciando integração de calendário (Google Calendar, Outlook) exatamente como antes
- Saudações e perguntas gerais devem continuar sendo respondidas diretamente sem chamar nenhum agente

**Scope:**
Todas as mensagens que NÃO envolvem notificações/mensagens para alunos devem ser completamente não afetadas pelo fix. Isso inclui:
- Mensagens sobre gerenciamento de alunos (registrar, listar, atualizar)
- Mensagens sobre sessões de treino (agendar, reagendar, cancelar)
- Mensagens sobre pagamentos (registrar, confirmar, visualizar)
- Mensagens sobre integração de calendário
- Saudações e perguntas gerais

## Hypothesized Root Cause

A causa raiz é clara e confirmada pela análise do código:

1. **notification_tools não importado**: O arquivo `src/services/strands_agent_service.py` importa `student_tools`, `session_tools`, `payment_tools`, `calendar_tools`, `group_session_tools` e `bulk_import_tools`, mas NÃO importa `notification_tools`

2. **Inner tool wrapper ausente**: O método `_build_domain_agent_tools()` cria inner tools para cada domínio (ex: `register_student`, `schedule_session`, etc.) mas não cria um wrapper `send_notification_inner` que chame `notification_tools.send_notification(trainer_id, ...)`

3. **notification_agent @tool não existe**: Não existe uma função `notification_agent` decorada com `@tool` que crie um `Agent` especializado com a inner tool de notificação, seguindo o padrão dos outros agentes

4. **Orquestrador não inclui notification_agent**: A lista de tools do orquestrador (`tools=[student_agent, session_agent, payment_agent, calendar_agent]`) não inclui `notification_agent`

5. **System prompt não menciona notificações**: O `orchestrator_prompt` não contém regras de roteamento para o `notification_agent` nem palavras-chave relacionadas a notificações

## Correctness Properties

Property 1: Bug Condition - Notification Agent Disponível e Funcional

_For any_ mensagem de trainer onde a intenção é enviar notificação/mensagem para alunos (isBugCondition returns true), o método `_build_domain_agent_tools()` corrigido SHALL retornar um `notification_agent` na tupla de agentes, e o orquestrador SHALL incluí-lo na lista de tools, permitindo que solicitações de notificação sejam delegadas e executadas via `send_notification()`.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - Agentes Existentes Inalterados

_For any_ mensagem de trainer onde a intenção NÃO é enviar notificação (isBugCondition returns false), o orquestrador corrigido SHALL produzir o mesmo comportamento que o orquestrador original, preservando o roteamento correto para student_agent, session_agent, payment_agent e calendar_agent, e respondendo diretamente a saudações/perguntas gerais.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

A causa raiz é confirmada. As mudanças são localizadas em um único arquivo.

**File**: `src/services/strands_agent_service.py`

**Method**: `_build_domain_agent_tools()` e `process_message()`

**Specific Changes**:

1. **Adicionar import de notification_tools**: Na seção de imports do arquivo, adicionar `from tools import notification_tools` (ou incluir `notification_tools` no import existente)
   - Linha atual: `from tools import student_tools, session_tools, payment_tools, calendar_tools, group_session_tools, bulk_import_tools`
   - Linha corrigida: `from tools import student_tools, session_tools, payment_tools, calendar_tools, group_session_tools, bulk_import_tools, notification_tools`

2. **Criar inner tool send_notification_inner**: Dentro de `_build_domain_agent_tools()`, criar um wrapper `@tool` que chame `notification_tools.send_notification(trainer_id, ...)` com os parâmetros adequados (message, recipients, specific_student_ids)

3. **Criar notification_agent @tool**: Criar uma função `notification_agent` decorada com `@tool` que instancie um `Agent` especializado com system prompt focado em notificações e a inner tool `send_notification_inner`

4. **Atualizar retorno de _build_domain_agent_tools()**: Alterar o return para incluir `notification_agent` na tupla retornada, e atualizar o log de agentes construídos

5. **Atualizar process_message()**: 
   - Alterar o destructuring da tupla para incluir `notification_agent`
   - Adicionar `notification_agent` à lista `tools=[...]` do orquestrador

6. **Atualizar orchestrator_prompt**: Adicionar `notification_agent` à lista de agentes disponíveis e incluir regras de roteamento para palavras-chave de notificação (notificação, notificar, avisar, mensagem para alunos, broadcast)

## Testing Strategy

### Validation Approach

A estratégia de testes segue duas fases: primeiro, demonstrar o bug no código não corrigido, depois verificar que o fix funciona e preserva o comportamento existente.

### Exploratory Bug Condition Checking

**Goal**: Demonstrar que o bug existe no código não corrigido. Confirmar que `notification_agent` não está na lista de tools do orquestrador.

**Test Plan**: Escrever testes que verifiquem a estrutura do `_build_domain_agent_tools()` e a lista de tools do orquestrador. Executar no código não corrigido para observar falhas.

**Test Cases**:
1. **Verificar retorno de _build_domain_agent_tools()**: Verificar que a tupla retornada NÃO contém notification_agent (vai falhar no código não corrigido)
2. **Verificar tools do orquestrador**: Verificar que a lista de tools do orquestrador NÃO inclui notification_agent (vai falhar no código não corrigido)
3. **Verificar import de notification_tools**: Verificar que notification_tools NÃO é importado no módulo (vai falhar no código não corrigido)
4. **Verificar system prompt**: Verificar que o orchestrator_prompt NÃO menciona notification_agent (vai falhar no código não corrigido)

**Expected Counterexamples**:
- `_build_domain_agent_tools()` retorna tupla de 4 elementos sem notification_agent
- Lista de tools do orquestrador contém apenas 4 agentes
- Possíveis causas: notification_tools não importado, inner tool não criada, notification_agent não definido

### Fix Checking

**Goal**: Verificar que para todas as entradas onde o bug condition é verdadeiro, a função corrigida produz o comportamento esperado.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := _build_domain_agent_tools_fixed(trainer_id)
  ASSERT 'notification_agent' IN result
  ASSERT notification_agent IS callable
  ASSERT orchestrator.tools CONTAINS notification_agent
  ASSERT orchestrator_prompt CONTAINS 'notification_agent'
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todas as entradas onde o bug condition NÃO é verdadeiro, a função corrigida produz o mesmo resultado que a original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT _build_domain_agent_tools_original(input).student_agent = _build_domain_agent_tools_fixed(input).student_agent
  ASSERT _build_domain_agent_tools_original(input).session_agent = _build_domain_agent_tools_fixed(input).session_agent
  ASSERT _build_domain_agent_tools_original(input).payment_agent = _build_domain_agent_tools_fixed(input).payment_agent
  ASSERT _build_domain_agent_tools_original(input).calendar_agent = _build_domain_agent_tools_fixed(input).calendar_agent
END FOR
```

**Testing Approach**: Property-based testing é recomendado para preservation checking porque:
- Gera muitos casos de teste automaticamente cobrindo o domínio de entrada
- Captura edge cases que testes manuais podem perder
- Fornece garantias fortes de que o comportamento é inalterado para todas as entradas não-buggy

**Test Plan**: Observar o comportamento no código não corrigido para os 4 agentes existentes, depois escrever property-based tests verificando que esse comportamento continua após o fix.

**Test Cases**:
1. **Student Agent Preservation**: Verificar que student_agent continua sendo criado com as mesmas inner tools (register_student, view_students, update_student, bulk_import_students)
2. **Session Agent Preservation**: Verificar que session_agent continua sendo criado com as mesmas 12 inner tools
3. **Payment Agent Preservation**: Verificar que payment_agent continua sendo criado com as mesmas 4 inner tools
4. **Calendar Agent Preservation**: Verificar que calendar_agent continua funcionando com connect_calendar

### Unit Tests

- Testar que `_build_domain_agent_tools()` retorna notification_agent na tupla
- Testar que a inner tool `send_notification_inner` chama `notification_tools.send_notification()` com trainer_id correto
- Testar que notification_agent é callable e aceita parâmetro `query: str`
- Testar que o orchestrator_prompt contém regras de roteamento para notificações
- Testar que a lista de tools do orquestrador inclui notification_agent

### Property-Based Tests

- Gerar trainer_ids aleatórios e verificar que notification_agent é sempre incluído na tupla de retorno
- Gerar mensagens aleatórias de notificação e verificar que o orquestrador tem notification_agent disponível
- Gerar configurações aleatórias e verificar que os 4 agentes existentes continuam presentes e funcionais após o fix

### Integration Tests

- Testar fluxo completo: trainer envia mensagem de notificação → orquestrador delega para notification_agent → send_notification é chamado → mensagens enfileiradas no SQS
- Testar que mensagens de alunos continuam sendo roteadas para student_agent após o fix
- Testar que mensagens de sessão continuam sendo roteadas para session_agent após o fix
