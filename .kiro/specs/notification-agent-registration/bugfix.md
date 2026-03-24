# Bugfix Requirements Document

## Introduction

O AI Agent (orquestrador Strands) não consegue enviar notificações/mensagens para os alunos dos personal trainers. A ferramenta `send_notification` existe e está totalmente implementada em `src/tools/notification_tools.py`, mas nunca é registrada como ferramenta do agente orquestrador. Falta criar um `notification_agent` seguindo o padrão Agents-as-Tools e adicioná-lo à lista de tools do orquestrador em `src/services/strands_agent_service.py`.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN um trainer pede para enviar uma notificação para alunos (ex: "envie uma notificação para todos os alunos") THEN o agente orquestrador não possui um `notification_agent` na sua lista de tools e não consegue executar o comando, respondendo que não tem essa capacidade ou ignorando a solicitação

1.2 WHEN um trainer pede para enviar uma mensagem via WhatsApp para alunos com sessões próximas (ex: "avise os alunos com treino amanhã que a academia estará fechada") THEN o agente orquestrador não tem acesso à ferramenta de notificação e não consegue enfileirar mensagens no SQS para envio

### Expected Behavior (Correct)

2.1 WHEN um trainer pede para enviar uma notificação para alunos THEN o agente orquestrador SHALL delegar a solicitação para um `notification_agent` que chama `send_notification()`, validando o trainer, selecionando destinatários, enfileirando mensagens no SQS e retornando confirmação com o número de mensagens enfileiradas

2.2 WHEN um trainer pede para enviar uma mensagem via WhatsApp para alunos com sessões próximas THEN o agente orquestrador SHALL delegar para o `notification_agent` que chama `send_notification()` com o critério de destinatários adequado (ex: "upcoming_sessions") e retornar confirmação do envio

### Unchanged Behavior (Regression Prevention)

3.1 WHEN um trainer pede para registrar, listar ou atualizar alunos THEN o sistema SHALL CONTINUE TO delegar corretamente para o `student_agent` e executar a operação com sucesso

3.2 WHEN um trainer pede para agendar, reagendar ou cancelar sessões de treino THEN o sistema SHALL CONTINUE TO delegar corretamente para o `session_agent` e executar a operação com sucesso

3.3 WHEN um trainer pede para registrar, confirmar ou visualizar pagamentos THEN o sistema SHALL CONTINUE TO delegar corretamente para o `payment_agent` e executar a operação com sucesso

3.4 WHEN um trainer pede para conectar Google Calendar ou Outlook THEN o sistema SHALL CONTINUE TO delegar corretamente para o `calendar_agent` e retornar o link OAuth

3.5 WHEN um trainer envia uma saudação ou pergunta geral THEN o sistema SHALL CONTINUE TO responder diretamente sem chamar nenhum agente especialista
