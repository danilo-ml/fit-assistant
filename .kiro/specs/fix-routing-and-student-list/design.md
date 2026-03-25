# Design do Bugfix: Roteamento de Vencimento e Exibição da Lista de Alunos

## Visão Geral

Este bugfix corrige dois problemas no assistente WhatsApp FitAgent:

1. **Roteamento de "vencimento" ainda quebrado**: Apesar de uma correção anterior ter adicionado regras de desambiguação no `orchestrator_prompt`, o LLM continua roteando mensagens como "alterar vencimento da mensalidade" para o `payment_agent`. A causa raiz é que a regra de desambiguação aparece DEPOIS das regras de roteamento no prompt, e o LLM prioriza instruções anteriores. Além disso, o `student_agent` pode usar `register_student` ao invés de `update_student`.

2. **Lista de alunos não exibida**: O `student_agent` chama `view_students` corretamente e recebe dados do DynamoDB, mas a resposta do LLM diz "aqui está a lista" sem incluir dados reais. O prompt do `student_agent` não instrui o LLM a formatar e exibir os dados retornados pelas ferramentas.

A estratégia de correção é reestruturar os prompts de forma mais agressiva: mover a desambiguação ANTES das regras de roteamento, adicionar exemplos concretos, e instruir explicitamente o `student_agent` a formatar resultados de ferramentas.

## Glossário

- **Bug_Condition (C)**: Condição que dispara o bug — mensagens sobre alterar vencimento são roteadas para `payment_agent`, ou lista de alunos é retornada sem dados
- **Property (P)**: Comportamento desejado — mensagens de vencimento vão para `student_agent` com `update_student`, e lista de alunos exibe dados formatados
- **Preservation**: Comportamento existente que deve permanecer inalterado — roteamento de pagamentos, sessões, e atualizações de aluno sem "vencimento"
- **orchestrator_prompt**: O prompt do sistema do agente orquestrador em `src/services/strands_agent_service.py` método `process_message` que define as regras de roteamento entre os 5 agentes de domínio
- **student_agent**: Agente de domínio definido como `@tool` em `_build_domain_agent_tools` que gerencia alunos (registrar, listar, atualizar, importar)
- **payment_agent**: Agente de domínio que gerencia pagamentos (registrar, confirmar, visualizar)
- **payment_due_day**: Campo do cadastro do aluno que armazena o dia de vencimento da mensalidade (1-31), atualizado via `update_student`

## Detalhes do Bug

### Condição do Bug 1: Roteamento de Vencimento

O bug se manifesta quando o trainer envia uma mensagem para alterar o vencimento/dia de pagamento de um aluno. O `orchestrator_prompt` contém regras de desambiguação, mas elas aparecem DEPOIS das regras de roteamento. O LLM prioriza a associação "mensalidade" → `payment_agent` que aparece primeiro, ignorando a regra de desambiguação posterior.

**Especificação Formal:**
```
FUNCTION isBugConditionRouting(input)
  INPUT: input do tipo MensagemDoTrainer
  OUTPUT: boolean

  RETURN input.mensagem contém ALGUMA palavra de ["vencimento", "dia de vencimento", "dia do pagamento"]
         E input.mensagem contém ALGUMA ação de ["alterar", "mudar", "trocar", "atualizar"]
         E o orchestrator_prompt roteia para payment_agent ao invés de student_agent
END FUNCTION
```

### Condição do Bug 2: Lista de Alunos Vazia

O bug se manifesta quando o trainer pede para listar alunos. O `student_agent` chama `view_students`, recebe os dados JSON, mas o LLM responde sem incluir os dados reais na resposta porque o prompt do `student_agent` não contém instrução explícita para formatar e exibir resultados de ferramentas.

**Especificação Formal:**
```
FUNCTION isBugConditionStudentList(input)
  INPUT: input do tipo MensagemDoTrainer
  OUTPUT: boolean

  RETURN input.mensagem contém ALGUMA frase de ["listar alunos", "mostrar alunos", "ver alunos",
         "meus alunos", "lista de alunos", "quem são meus alunos"]
         E student_agent_prompt NÃO contém instrução de formatação de resultados
END FUNCTION
```

### Condição do Bug 3: update_student vs register_student

O bug se manifesta quando o `student_agent` recebe uma mensagem para alterar dados de um aluno existente mas tenta usar `register_student` ao invés de `update_student`, pois o prompt não diferencia claramente entre as duas operações.

**Especificação Formal:**
```
FUNCTION isBugConditionUpdateVsRegister(input)
  INPUT: input do tipo MensagemDoTrainer
  OUTPUT: boolean

  RETURN input.mensagem contém ação de alteração ("alterar", "mudar", "trocar", "atualizar")
         E input.mensagem referencia um aluno existente por nome
         E student_agent_prompt NÃO contém instrução explícita para usar update_student
           para alterações de dados de alunos existentes
END FUNCTION
```

### Exemplos

- **Exemplo 1**: Trainer envia "alterar vencimento da mensalidade da juliana nano para dia 28" → Sistema roteia para `payment_agent` (ERRADO). Esperado: rotear para `student_agent` que usa `update_student(student_name="juliana nano", payment_due_day=28)`.
- **Exemplo 2**: Trainer envia "mudar dia de vencimento do João para 15" → Sistema roteia para `payment_agent` (ERRADO). Esperado: rotear para `student_agent`.
- **Exemplo 3**: Trainer envia "Listar alunos" → `student_agent` chama `view_students`, recebe dados, mas responde "Esta é a lista de todos os alunos" sem dados (ERRADO). Esperado: resposta com lista numerada contendo nome, telefone, email, objetivo e dia de vencimento de cada aluno.
- **Exemplo 4**: Trainer envia "atualizar vencimento da Ana para dia 10" → `student_agent` pode tentar `register_student` (ERRADO). Esperado: usar `update_student(student_name="Ana", payment_due_day=10)`.

## Comportamento Esperado

### Requisitos de Preservação

**Comportamentos Inalterados:**
- Mensagens de registrar pagamento (ex: "registrar pagamento de R$300 da Maria") devem continuar sendo roteadas para `payment_agent`
- Mensagens de visualizar pagamentos (ex: "ver pagamentos do João") devem continuar sendo roteadas para `payment_agent`
- Mensagens de confirmar pagamento (ex: "confirmar pagamento abc123") devem continuar sendo roteadas para `payment_agent`
- Mensagens de atualizar dados do aluno SEM "vencimento" (ex: "atualizar email do João") devem continuar sendo roteadas para `student_agent`
- Mensagens de registrar novo aluno devem continuar usando `register_student`
- Mensagens de agendar/reagendar/cancelar sessões devem continuar sendo roteadas para `session_agent`

**Escopo:**
Todas as mensagens que NÃO envolvem alteração de vencimento ou listagem de alunos devem ser completamente não afetadas por esta correção. Isso inclui:
- Operações de pagamento (registrar, confirmar, visualizar)
- Operações de sessão (agendar, reagendar, cancelar)
- Operações de calendário (conectar, desconectar)
- Operações de notificação (enviar mensagens)
- Atualizações de aluno sem "vencimento" (email, telefone, objetivo, nome)

## Causa Raiz Hipotética

Com base na análise do código e dos bugs, as causas raiz mais prováveis são:

1. **Posicionamento da Regra de Desambiguação no orchestrator_prompt**: A regra "REGRA DE DESAMBIGUAÇÃO" aparece DEPOIS das "REGRAS DE ROTEAMENTO" no prompt. LLMs tendem a priorizar instruções que aparecem primeiro. Quando o LLM encontra "mensalidade" → `payment_agent` nas regras de roteamento, ele já tomou a decisão antes de chegar à regra de desambiguação.

2. **Falta de Exemplos Concretos no Prompt**: O prompt atual usa regras abstratas sem exemplos concretos. LLMs respondem melhor a exemplos do que a regras abstratas. Adicionar exemplos como "alterar vencimento da mensalidade da juliana → student_agent" tornaria o roteamento mais confiável.

3. **Descrição do student_agent Tool Não Menciona "vencimento"**: A docstring do `@tool student_agent` diz apenas "Handle student management queries: register new students, view student list, update student information." Não menciona explicitamente "vencimento" ou "dia de pagamento", o que faz o LLM não considerar o `student_agent` para essas mensagens.

4. **Prompt do student_agent Não Instrui Formatação de Resultados**: O system prompt do `student_agent` lista as ferramentas disponíveis e regras para registrar alunos, mas não contém nenhuma instrução sobre como formatar e exibir os dados retornados por `view_students`. O LLM recebe o JSON mas não sabe que deve incluir os dados na resposta.

5. **Prompt do student_agent Não Diferencia update_student de register_student**: O prompt não instrui explicitamente que para alterar dados de alunos existentes (incluindo vencimento) deve-se usar `update_student` com `student_name`, não `register_student`.

## Propriedades de Corretude

Property 1: Bug Condition - Roteamento de Vencimento para student_agent

_Para qualquer_ mensagem do trainer que contenha uma palavra de vencimento ("vencimento", "dia de vencimento", "dia do pagamento") combinada com uma ação de alteração ("alterar", "mudar", "trocar", "atualizar"), o `orchestrator_prompt` corrigido DEVERÁ conter regras de roteamento que direcionem essas mensagens para `student_agent`, com a regra de desambiguação posicionada ANTES das regras gerais de roteamento e com exemplos concretos.

**Valida: Requisitos 2.1, 2.2**

Property 2: Bug Condition - Prompt do student_agent Instrui Formatação de Resultados

_Para qualquer_ mensagem que solicite listagem de alunos, o prompt do `student_agent` corrigido DEVERÁ conter instruções explícitas para formatar e exibir TODOS os dados retornados por `view_students` (nome, telefone, email, objetivo, dia de vencimento) em formato legível, e NUNCA omitir dados retornados pelas ferramentas.

**Valida: Requisitos 2.3, 2.4**

Property 3: Bug Condition - Prompt do student_agent Instrui Uso de update_student

_Para qualquer_ mensagem sobre alterar dados de um aluno existente, o prompt do `student_agent` corrigido DEVERÁ conter instruções explícitas para usar `update_student` (não `register_student`) para atualizar dados de alunos existentes, identificando o aluno pelo nome via `student_name`.

**Valida: Requisitos 2.1, 2.2**

Property 4: Preservation - Roteamento de Pagamentos Inalterado

_Para qualquer_ mensagem sobre operações de pagamento (registrar, confirmar, visualizar pagamentos) que NÃO contenha palavras de vencimento com ação de alteração, o `orchestrator_prompt` corrigido DEVERÁ CONTINUAR contendo regras de roteamento que direcionem essas mensagens para `payment_agent`, preservando o comportamento existente.

**Valida: Requisitos 3.1, 3.2, 3.4**

Property 5: Preservation - Roteamento de Atualizações de Aluno Sem Vencimento Inalterado

_Para qualquer_ mensagem sobre atualizar dados do aluno que NÃO contenha palavras de vencimento (ex: "atualizar email", "mudar telefone"), o `orchestrator_prompt` corrigido DEVERÁ CONTINUAR contendo regras que direcionem essas mensagens para `student_agent`.

**Valida: Requisitos 3.3, 3.5**

## Implementação da Correção

### Mudanças Necessárias

Assumindo que nossa análise de causa raiz está correta:

**Arquivo**: `src/services/strands_agent_service.py`

**Função**: `process_message` — reestruturar `orchestrator_prompt`

**Mudanças Específicas**:
1. **Mover desambiguação para ANTES das regras de roteamento**: Criar uma seção "REGRA PRIORITÁRIA" no início do prompt, antes de qualquer regra de roteamento, que estabeleça que "vencimento" + ação de alteração → `student_agent` SEMPRE.

2. **Adicionar exemplos concretos no prompt**: Incluir 3-4 exemplos reais de mensagens e para qual agente devem ser roteadas, especialmente os casos ambíguos com "mensalidade" + "vencimento".

3. **Atualizar a docstring do @tool student_agent**: Mudar de "Handle student management queries: register new students, view student list, update student information" para incluir explicitamente "change payment due date (vencimento)" na descrição da ferramenta.

**Função**: `_build_domain_agent_tools` — atualizar prompt do `student_agent`

**Mudanças Específicas**:
4. **Adicionar instrução de formatação de resultados**: Incluir no system prompt do `student_agent` uma regra explícita: "Quando uma ferramenta retornar dados (ex: view_students), você DEVE formatar e exibir TODOS os dados na resposta. NUNCA diga 'aqui está a lista' sem incluir os dados."

5. **Adicionar instrução para diferenciar update_student de register_student**: Incluir regra: "Para ALTERAR dados de alunos existentes (incluindo vencimento/dia de pagamento), use SEMPRE update_student com student_name. Use register_student APENAS para cadastrar alunos NOVOS."

6. **Adicionar instrução sobre vencimento no student_agent**: Incluir regra: "Para alterar o dia de vencimento, use update_student com o parâmetro payment_due_day (1-31)."

## Estratégia de Testes

### Abordagem de Validação

A estratégia de testes segue uma abordagem em duas fases: primeiro, surfar contraexemplos que demonstrem o bug no código não corrigido, depois verificar que a correção funciona e preserva o comportamento existente.

### Verificação Exploratória da Condição do Bug

**Objetivo**: Surfar contraexemplos que demonstrem o bug ANTES de implementar a correção. Confirmar ou refutar a análise de causa raiz. Se refutarmos, precisaremos re-hipotizar.

**Plano de Teste**: Extrair o `orchestrator_prompt` e o prompt do `student_agent` do código não corrigido e verificar que:
- O prompt NÃO contém regra de desambiguação posicionada antes das regras de roteamento
- O prompt do `student_agent` NÃO contém instrução de formatação de resultados
- O prompt do `student_agent` NÃO diferencia claramente `update_student` de `register_student`

**Casos de Teste**:
1. **Teste de Roteamento de Vencimento**: Gerar mensagens combinando palavras de vencimento × ações de alteração × nomes de alunos e verificar que o prompt NÃO roteia corretamente (vai falhar no código não corrigido)
2. **Teste de Formatação de Lista**: Verificar que o prompt do `student_agent` NÃO contém instrução de formatação (vai falhar no código não corrigido)
3. **Teste de update_student vs register_student**: Verificar que o prompt do `student_agent` NÃO diferencia as operações (vai falhar no código não corrigido)

**Contraexemplos Esperados**:
- O `orchestrator_prompt` contém "mensalidade" → `payment_agent` ANTES da regra de desambiguação
- O prompt do `student_agent` não menciona formatação de resultados de ferramentas
- Causas possíveis: posicionamento da regra, falta de exemplos, docstring incompleta

### Fix Checking

**Objetivo**: Verificar que para todas as entradas onde a condição do bug se aplica, a função corrigida produz o comportamento esperado.

**Pseudocódigo:**
```
PARA TODA mensagem ONDE isBugConditionRouting(mensagem) FAÇA
  prompt ← orchestrator_prompt_corrigido
  ASSERT prompt contém regra prioritária de vencimento → student_agent ANTES das regras gerais
  ASSERT prompt contém exemplos concretos de roteamento
  ASSERT student_agent_tool_description menciona "vencimento"
FIM PARA

PARA TODA mensagem ONDE isBugConditionStudentList(mensagem) FAÇA
  prompt ← student_agent_prompt_corrigido
  ASSERT prompt contém instrução de formatação de resultados
  ASSERT prompt contém instrução para NUNCA omitir dados retornados
FIM PARA

PARA TODA mensagem ONDE isBugConditionUpdateVsRegister(mensagem) FAÇA
  prompt ← student_agent_prompt_corrigido
  ASSERT prompt contém instrução para usar update_student para alunos existentes
  ASSERT prompt contém instrução para usar register_student APENAS para novos alunos
FIM PARA
```

### Preservation Checking

**Objetivo**: Verificar que para todas as entradas onde a condição do bug NÃO se aplica, a função corrigida produz o mesmo resultado que a função original.

**Pseudocódigo:**
```
PARA TODA mensagem ONDE NÃO isBugConditionRouting(mensagem) FAÇA
  ASSERT orchestrator_prompt_original roteia para mesmo agente que orchestrator_prompt_corrigido
FIM PARA
```

**Abordagem de Teste**: Testes baseados em propriedades são recomendados para preservation checking porque:
- Geram muitos casos de teste automaticamente no domínio de entrada
- Capturam edge cases que testes manuais podem perder
- Fornecem garantias fortes de que o comportamento é inalterado para entradas não-buggy

**Plano de Teste**: Observar o comportamento no código NÃO corrigido primeiro para operações de pagamento, sessão e atualizações de aluno sem vencimento, depois escrever testes baseados em propriedades capturando esse comportamento.

**Casos de Teste**:
1. **Preservação de Roteamento de Pagamentos**: Verificar que mensagens de registrar/confirmar/visualizar pagamentos continuam sendo roteadas para `payment_agent` após a correção
2. **Preservação de Roteamento de Sessões**: Verificar que mensagens de agendar/reagendar/cancelar sessões continuam sendo roteadas para `session_agent`
3. **Preservação de Atualizações de Aluno**: Verificar que mensagens de atualizar email/telefone/objetivo continuam sendo roteadas para `student_agent`
4. **Preservação de Registro de Aluno**: Verificar que mensagens de registrar novo aluno continuam funcionando normalmente

### Testes Unitários

- Testar que o `orchestrator_prompt` contém regra prioritária de vencimento antes das regras gerais
- Testar que o prompt do `student_agent` contém instrução de formatação de resultados
- Testar que o prompt do `student_agent` diferencia `update_student` de `register_student`
- Testar que a docstring do `@tool student_agent` menciona "vencimento"

### Testes Baseados em Propriedades

- Gerar combinações aleatórias de palavras de vencimento × ações × nomes e verificar que o prompt roteia para `student_agent` (atualizar `tests/property/test_vencimento_routing_bug.py`)
  - **Mudança vs. versão anterior**: Adicionar verificação de que a regra de desambiguação aparece ANTES das regras de roteamento no prompt, não apenas que existe uma regra
  - **Mudança vs. versão anterior**: Verificar que a docstring do `@tool student_agent` menciona "vencimento"
  - **Mudança vs. versão anterior**: Adicionar verificação de exemplos concretos no prompt
- Gerar combinações aleatórias de operações de pagamento e verificar que continuam roteando para `payment_agent` (atualizar `tests/property/test_vencimento_routing_preservation.py`)
  - **Mudança vs. versão anterior**: Manter os testes existentes, que já passam no código não corrigido
- Adicionar testes de propriedade para o prompt do `student_agent`:
  - Verificar presença de instrução de formatação de resultados
  - Verificar presença de instrução de diferenciação `update_student` vs `register_student`

### Testes de Integração

- Testar fluxo completo de alteração de vencimento: mensagem → orquestrador → `student_agent` → `update_student`
- Testar fluxo completo de listagem de alunos: mensagem → orquestrador → `student_agent` → `view_students` → resposta formatada
- Testar que fluxo de pagamento continua funcionando após a correção
