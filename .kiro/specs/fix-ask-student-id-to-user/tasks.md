# Plano de Implementação

- [x] 1. Escrever teste exploratório da condição do bug
  - **Property 1: Bug Condition** - Roteamento de Alteração de Vencimento
  - **IMPORTANTE**: Escrever este teste baseado em propriedades ANTES de implementar a correção
  - **CRÍTICO**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **NÃO tente corrigir o teste ou o código quando ele falhar**
  - **NOTA**: Este teste codifica o comportamento esperado — ele validará a correção quando passar após a implementação
  - **OBJETIVO**: Evidenciar contraexemplos que demonstram o bug
  - **Abordagem PBT com Escopo**: Gerar mensagens combinando palavras de vencimento ("vencimento", "dia de vencimento", "dia do pagamento") com ações de alteração ("alterar", "mudar", "trocar", "atualizar") e nomes de alunos
  - Arquivo de teste: `tests/property/test_vencimento_routing_bug.py`
  - Usar Hypothesis para gerar combinações de palavras_vencimento × acoes_alteracao × nomes_alunos × dias (1-31)
  - Condição do bug (isBugCondition): mensagem contém ALGUMA palavra de ["vencimento", "dia de vencimento", "dia do pagamento"] E ALGUMA ação de ["alterar", "mudar", "trocar", "atualizar"] E identifica aluno por nome
  - Assertar que o `orchestrator_prompt` roteia para `student_agent` (não `payment_agent`) para essas mensagens
  - Executar no código NÃO corrigido — esperar FALHA (confirma que o bug existe)
  - Documentar contraexemplos encontrados (ex: "alterar vencimento da mensalidade da juliana nano para dia 28" roteia para `payment_agent`)
  - Marcar tarefa como completa quando o teste estiver escrito, executado e a falha documentada
  - _Requirements: 1.1, 1.2_

- [x] 2. Escrever testes de preservação baseados em propriedades (ANTES de implementar a correção)
  - **Property 2: Preservation** - Operações de Pagamento Continuam no payment_agent
  - **IMPORTANTE**: Seguir metodologia de observação primeiro (observation-first)
  - Arquivo de teste: `tests/property/test_vencimento_routing_preservation.py`
  - Observar: "registrar pagamento de R$300 da Maria" roteia para `payment_agent` no código não corrigido
  - Observar: "ver pagamentos do João" roteia para `payment_agent` no código não corrigido
  - Observar: "confirmar pagamento abc123" roteia para `payment_agent` no código não corrigido
  - Observar: "status de pagamento da Ana" roteia para `payment_agent` no código não corrigido
  - Observar: "atualizar email do João" roteia para `student_agent` no código não corrigido
  - Usar Hypothesis para gerar mensagens de operações de pagamento (combinando verbos de pagamento × valores × nomes) e verificar que roteiam para `payment_agent`
  - Usar Hypothesis para gerar mensagens de atualização de dados do aluno SEM palavras de vencimento e verificar que roteiam para `student_agent`
  - Condição de não-bug (¬C): mensagens que NÃO contêm palavras de vencimento combinadas com ações de alteração
  - Verificar que testes PASSAM no código NÃO corrigido (confirma comportamento baseline a preservar)
  - Marcar tarefa como completa quando testes estiverem escritos, executados e passando no código não corrigido
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Correção do roteamento de alteração de vencimento no orchestrator_prompt

  - [x] 3.1 Implementar a correção no orchestrator_prompt
    - Arquivo: `src/services/strands_agent_service.py`, método `process_message`, variável `orchestrator_prompt`
    - Adicionar regra de prioridade para vencimento no `student_agent`: palavras como "vencimento", "dia de vencimento", "dia do pagamento" combinadas com ações de alteração → `student_agent`
    - Qualificar a regra do `payment_agent`: "mensalidade" → `payment_agent` APENAS para registrar/visualizar/confirmar pagamentos, NÃO para alterar vencimento
    - Adicionar regra de desambiguação: se a mensagem contém "vencimento"/"dia de vencimento"/"dia do pagamento" junto com ação de alteração, SEMPRE encaminhar para `student_agent`, mesmo que contenha "mensalidade"
    - Atualizar descrição do `student_agent` para incluir explicitamente "alterar vencimento/dia de pagamento"
    - Manter todas as regras de roteamento existentes intactas
    - _Bug_Condition: isBugCondition(input) onde input.mensagem contém palavras de vencimento + ações de alteração + nome do aluno_
    - _Expected_Behavior: orquestrador roteia para student_agent, que usa update_student para atualizar payment_due_day sem pedir ID_
    - _Preservation: Operações de pagamento (registrar, confirmar, visualizar, status) continuam roteando para payment_agent_
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 3.3, 3.4_

  - [x] 3.2 Verificar que o teste exploratório da condição do bug agora passa
    - **Property 1: Expected Behavior** - Roteamento de Alteração de Vencimento
    - **IMPORTANTE**: Re-executar o MESMO teste da tarefa 1 — NÃO escrever um novo teste
    - O teste da tarefa 1 codifica o comportamento esperado
    - Quando este teste passar, confirma que o comportamento esperado está satisfeito
    - Executar teste exploratório da tarefa 1 no código corrigido
    - **RESULTADO ESPERADO**: Teste PASSA (confirma que o bug foi corrigido)
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verificar que os testes de preservação continuam passando
    - **Property 2: Preservation** - Operações de Pagamento Continuam no payment_agent
    - **IMPORTANTE**: Re-executar os MESMOS testes da tarefa 2 — NÃO escrever novos testes
    - Executar testes de preservação da tarefa 2 no código corrigido
    - **RESULTADO ESPERADO**: Testes PASSAM (confirma que não houve regressão)
    - Confirmar que todos os testes continuam passando após a correção
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4. Checkpoint - Garantir que todos os testes passam
  - Executar suite completa de testes: `make test-property`
  - Garantir que todos os testes passam, perguntar ao usuário se surgirem dúvidas
