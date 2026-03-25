# Plano de Implementação

- [x] 1. Escrever teste exploratório da condição do bug (roteamento de vencimento)
  - **Property 1: Bug Condition** - Roteamento de Vencimento para student_agent
  - **CRITICAL**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **NÃO tente corrigir o teste ou o código quando ele falhar**
  - **NOTA**: Este teste codifica o comportamento esperado — ele validará a correção quando passar após a implementação
  - **OBJETIVO**: Surfar contraexemplos que demonstrem que o bug existe
  - **Abordagem PBT com Escopo**: Gerar combinações de palavras de vencimento × ações de alteração × nomes de alunos e verificar que o `orchestrator_prompt` contém regras que roteiam essas mensagens para `student_agent`
  - Atualizar `tests/property/test_vencimento_routing_bug.py` para verificar:
    - A regra de desambiguação ("REGRA PRIORITÁRIA" ou equivalente) aparece ANTES das regras gerais de roteamento no prompt
    - A docstring do `@tool student_agent` menciona "vencimento" ou "dia de pagamento"
    - O prompt contém exemplos concretos de roteamento (ex: "alterar vencimento da mensalidade da juliana → student_agent")
  - Usar `_get_orchestrator_prompt` e `_build_domain_agent_tools` para extrair prompts do código não corrigido
  - Executar teste no código NÃO corrigido
  - **RESULTADO ESPERADO**: Teste FALHA (isso é correto — prova que o bug existe)
  - Documentar contraexemplos encontrados para entender a causa raiz
  - Marcar tarefa como completa quando o teste estiver escrito, executado e a falha documentada
  - _Requirements: 1.1, 1.2_

- [x] 2. Escrever teste exploratório da condição do bug (prompt do student_agent)
  - **Property 1: Bug Condition** - Prompt do student_agent Sem Instrução de Formatação e Diferenciação
  - **CRITICAL**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **NÃO tente corrigir o teste ou o código quando ele falhar**
  - **OBJETIVO**: Surfar contraexemplos que demonstrem que o prompt do `student_agent` não contém instruções adequadas
  - Criar `tests/property/test_student_agent_prompt.py` com testes baseados em propriedades que verificam:
    - O prompt do `student_agent` contém instrução explícita para formatar e exibir TODOS os dados retornados por `view_students` (nome, telefone, email, objetivo, dia de vencimento)
    - O prompt do `student_agent` contém instrução para NUNCA omitir dados retornados pelas ferramentas
    - O prompt do `student_agent` diferencia explicitamente `update_student` de `register_student` (usar `update_student` para alunos existentes, `register_student` apenas para novos)
    - O prompt do `student_agent` menciona `payment_due_day` para alteração de vencimento
  - Extrair o prompt do `student_agent` via mock do `Agent()` em `_build_domain_agent_tools`
  - Executar teste no código NÃO corrigido
  - **RESULTADO ESPERADO**: Teste FALHA (isso é correto — prova que o bug existe)
  - Documentar contraexemplos encontrados
  - Marcar tarefa como completa quando o teste estiver escrito, executado e a falha documentada
  - _Requirements: 1.3, 1.4_

- [x] 3. Escrever testes de preservação baseados em propriedades (ANTES de implementar a correção)
  - **Property 2: Preservation** - Roteamento de Pagamentos e Atualizações de Aluno Inalterado
  - **IMPORTANTE**: Seguir metodologia observation-first
  - Observar: mensagens de registrar pagamento (ex: "registrar pagamento de R$300 da Maria") roteiam para `payment_agent` no código não corrigido
  - Observar: mensagens de visualizar pagamentos (ex: "ver pagamentos do João") roteiam para `payment_agent` no código não corrigido
  - Observar: mensagens de confirmar pagamento (ex: "confirmar pagamento abc123") roteiam para `payment_agent` no código não corrigido
  - Observar: mensagens de status de pagamento (ex: "status de pagamento da Ana") roteiam para `payment_agent` no código não corrigido
  - Observar: mensagens de atualizar aluno SEM vencimento (ex: "atualizar email do João") roteiam para `student_agent` no código não corrigido
  - Os testes em `tests/property/test_vencimento_routing_preservation.py` já existem e já passam — verificar que continuam passando
  - Executar testes no código NÃO corrigido
  - **RESULTADO ESPERADO**: Testes PASSAM (isso confirma o comportamento baseline a preservar)
  - Marcar tarefa como completa quando os testes estiverem executados e passando no código não corrigido
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. Correção do roteamento de vencimento e prompt do student_agent

  - [x] 4.1 Reestruturar `orchestrator_prompt` no método `process_message`
    - Mover a regra de desambiguação ("REGRA PRIORITÁRIA") para ANTES das regras de roteamento no prompt
    - Adicionar 3-4 exemplos concretos de decisões de roteamento no prompt, especialmente os casos ambíguos com "mensalidade" + "vencimento"
    - Manter todas as regras de roteamento existentes, apenas reestruturar a ordem
    - _Bug_Condition: isBugConditionRouting(input) onde input.mensagem contém palavras de vencimento + ação de alteração_
    - _Expected_Behavior: orchestrator_prompt contém regra prioritária de vencimento → student_agent ANTES das regras gerais, com exemplos concretos_
    - _Preservation: Roteamento de pagamentos, sessões e atualizações de aluno sem vencimento deve permanecer inalterado_
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 4.2 Atualizar docstring do `@tool student_agent` em `_build_domain_agent_tools`
    - Mudar de "Handle student management queries: register new students, view student list, update student information"
    - Para incluir explicitamente "change payment due date (vencimento/dia de pagamento)" na descrição
    - _Bug_Condition: student_agent tool description não menciona "vencimento"_
    - _Expected_Behavior: docstring do student_agent menciona "vencimento" ou "dia de pagamento"_
    - _Requirements: 2.1, 2.2_

  - [x] 4.3 Atualizar system prompt do `student_agent` em `_build_domain_agent_tools`
    - Adicionar instrução para formatar e exibir TODOS os dados retornados por ferramentas (especialmente `view_students`)
    - Adicionar instrução para diferenciar `update_student` de `register_student` (usar `update_student` para alunos existentes, `register_student` apenas para novos)
    - Adicionar instrução sobre usar `update_student` com `payment_due_day` para alterações de vencimento
    - Adicionar instrução para NUNCA dizer "aqui está a lista" sem incluir os dados reais
    - _Bug_Condition: isBugConditionStudentList(input) onde student_agent_prompt não contém instrução de formatação_
    - _Expected_Behavior: student_agent_prompt contém instruções de formatação, diferenciação update/register, e vencimento_
    - _Preservation: Registro de novos alunos deve continuar funcionando normalmente_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.5_

  - [x] 4.4 Verificar que teste exploratório de roteamento agora passa
    - **Property 1: Expected Behavior** - Roteamento de Vencimento para student_agent
    - **IMPORTANTE**: Re-executar o MESMO teste da tarefa 1 — NÃO escrever um novo teste
    - O teste da tarefa 1 codifica o comportamento esperado
    - Quando este teste passar, confirma que o comportamento esperado é satisfeito
    - Executar `tests/property/test_vencimento_routing_bug.py`
    - **RESULTADO ESPERADO**: Teste PASSA (confirma que o bug de roteamento foi corrigido)
    - _Requirements: 2.1, 2.2_

  - [x] 4.5 Verificar que teste exploratório do prompt do student_agent agora passa
    - **Property 1: Expected Behavior** - Prompt do student_agent Com Instruções Adequadas
    - **IMPORTANTE**: Re-executar o MESMO teste da tarefa 2 — NÃO escrever um novo teste
    - Executar `tests/property/test_student_agent_prompt.py`
    - **RESULTADO ESPERADO**: Teste PASSA (confirma que o prompt do student_agent foi corrigido)
    - _Requirements: 2.3, 2.4_

  - [x] 4.6 Verificar que testes de preservação ainda passam
    - **Property 2: Preservation** - Roteamento de Pagamentos e Atualizações de Aluno Inalterado
    - **IMPORTANTE**: Re-executar os MESMOS testes da tarefa 3 — NÃO escrever novos testes
    - Executar `tests/property/test_vencimento_routing_preservation.py`
    - **RESULTADO ESPERADO**: Testes PASSAM (confirma que não houve regressões)
    - Confirmar que todos os testes ainda passam após a correção (sem regressões)

- [x] 5. Checkpoint - Garantir que todos os testes passam
  - Executar todos os testes de propriedade relacionados ao bugfix:
    - `tests/property/test_vencimento_routing_bug.py` (deve PASSAR)
    - `tests/property/test_student_agent_prompt.py` (deve PASSAR)
    - `tests/property/test_vencimento_routing_preservation.py` (deve PASSAR)
  - Garantir que todos os testes passam, perguntar ao usuário se surgirem dúvidas
