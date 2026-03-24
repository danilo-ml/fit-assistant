# Bugfix Design: Corrigir Roteamento de Alteração de Vencimento

## Visão Geral

Quando o trainer envia uma mensagem como "alterar vencimento da mensalidade da juliana nano para dia 28", o orquestrador roteia para o `payment_agent` ao invés do `student_agent`. O `payment_agent` não possui a ferramenta `update_student`, então pede o ID interno do aluno ao trainer — algo que o trainer não deveria precisar saber.

A correção consiste em ajustar as regras de roteamento no prompt do orquestrador (`orchestrator_prompt` em `strands_agent_service.py`) para que mensagens sobre alteração de vencimento/dia de pagamento sejam encaminhadas ao `student_agent`, que possui a ferramenta `update_student` e resolve nomes de alunos automaticamente.

## Glossário

- **Bug_Condition (C)**: Mensagem do trainer contém palavras-chave de vencimento ("vencimento", "dia de vencimento", "dia do pagamento") combinadas com ação de alteração ("alterar", "mudar", "trocar", "atualizar") — o orquestrador roteia incorretamente para `payment_agent`
- **Property (P)**: Mensagens sobre alteração de vencimento devem ser roteadas para `student_agent`, que usa `update_student` para atualizar `payment_due_day` sem pedir ID ao trainer
- **Preservation**: Operações de pagamento (registrar, confirmar, visualizar pagamentos e status) devem continuar sendo roteadas para `payment_agent`
- **orchestrator_prompt**: String de system prompt do agente orquestrador em `src/services/strands_agent_service.py` (método `process_message`) que define as regras de roteamento entre os 5 agentes de domínio
- **student_agent**: Agente de domínio com ferramentas `register_student`, `view_students`, `update_student`, `bulk_import_students`
- **payment_agent**: Agente de domínio com ferramentas `register_payment`, `confirm_payment`, `view_payments`, `view_payment_status`

## Detalhes do Bug

### Condição do Bug

O bug se manifesta quando o trainer envia uma mensagem contendo palavras como "mensalidade" ou "vencimento" combinadas com uma ação de alteração de dados cadastrais do aluno. O orquestrador, ao encontrar "mensalidade" na mensagem, aplica a regra de roteamento `"mensalidade" → payment_agent`, ignorando que a ação solicitada (alterar `payment_due_day`) é uma atualização de dados do aluno que requer `student_agent`.

**Especificação Formal:**
```
FUNCTION isBugCondition(input)
  INPUT: input do tipo MensagemDoTrainer
  OUTPUT: boolean

  palavras_vencimento := ["vencimento", "dia de vencimento", "dia do pagamento"]
  acoes_alteracao := ["alterar", "mudar", "trocar", "atualizar"]

  RETURN input.mensagem contém ALGUMA palavra de palavras_vencimento
         E input.mensagem contém ALGUMA ação de acoes_alteracao
         E input.mensagem identifica aluno por nome (não por ID interno)
END FUNCTION
```

### Exemplos

- "alterar vencimento da mensalidade da juliana nano para dia 28" → Esperado: `student_agent` / Atual: `payment_agent` (pede ID)
- "mudar dia de vencimento do João para 15" → Esperado: `student_agent` / Atual: `payment_agent` (pede ID)
- "trocar o dia do pagamento da Maria para dia 5" → Esperado: `student_agent` / Atual: `payment_agent` (pede ID)
- "atualizar vencimento da Ana para dia 10" → Esperado: `student_agent` / Atual: `payment_agent` (pede ID)

## Comportamento Esperado

### Requisitos de Preservação

**Comportamentos Inalterados:**
- Registrar pagamento (ex: "registrar pagamento de R$300 da Maria") deve continuar roteando para `payment_agent`
- Visualizar pagamentos (ex: "ver pagamentos do João") deve continuar roteando para `payment_agent`
- Confirmar pagamento (ex: "confirmar pagamento abc123") deve continuar roteando para `payment_agent`
- Ver status de pagamento mensal (ex: "status de pagamento da Ana") deve continuar roteando para `payment_agent`
- Atualizar outros dados do aluno sem mencionar "mensalidade" (ex: "atualizar email do João") deve continuar roteando para `student_agent`

**Escopo:**
Todas as mensagens que NÃO envolvem alteração de vencimento/dia de pagamento devem ser completamente não afetadas pela correção. Isso inclui:
- Operações de pagamento (registrar, confirmar, visualizar, status)
- Operações de sessão (agendar, reagendar, cancelar)
- Operações de calendário (conectar, desconectar)
- Operações de notificação (enviar mensagens)
- Atualizações de outros campos do aluno (email, telefone, objetivo)

## Causa Raiz Hipotética

Com base na análise do código em `src/services/strands_agent_service.py`, a causa raiz é:

1. **Regra de roteamento genérica para "mensalidade"**: No `orchestrator_prompt` (linha ~800 do método `process_message`), a regra de roteamento define:
   ```
   Palavras como "pagamento", "pagar", "valor", "recibo", "mensalidade", "confirmar pagamento" → payment_agent
   ```
   A palavra "mensalidade" é mapeada diretamente para `payment_agent` sem considerar o contexto da ação solicitada.

2. **Ausência de regra de prioridade para ações de atualização de vencimento**: Não existe uma regra que reconheça que "alterar vencimento da mensalidade" é uma operação sobre dados cadastrais do aluno (`payment_due_day`), não uma operação de pagamento.

3. **O `payment_agent` não possui `update_student`**: O `payment_agent` tem apenas `register_payment`, `confirm_payment`, `view_payments` e `view_payment_status`. Sem a ferramenta correta, ele tenta resolver a solicitação pedindo o ID interno do aluno.

4. **O `student_agent` já suporta a operação**: A ferramenta `update_student` aceita `payment_due_day` como parâmetro e resolve nomes de alunos automaticamente via `student_name`.

## Propriedades de Corretude

Property 1: Bug Condition - Roteamento de Alteração de Vencimento para student_agent

_Para qualquer_ mensagem do trainer onde a condição do bug é verdadeira (isBugCondition retorna true), o orquestrador corrigido DEVERÁ rotear a mensagem para o `student_agent`, que usará a ferramenta `update_student` para atualizar o campo `payment_due_day` do aluno identificado por nome, sem solicitar o ID interno ao trainer.

**Valida: Requisitos 2.1, 2.2**

Property 2: Preservation - Operações de Pagamento Continuam no payment_agent

_Para qualquer_ mensagem do trainer onde a condição do bug NÃO é verdadeira (isBugCondition retorna false), o orquestrador corrigido DEVERÁ produzir o mesmo resultado que o orquestrador original, preservando o roteamento correto de operações de pagamento (registrar, confirmar, visualizar, status) para o `payment_agent` e de outras operações para seus respectivos agentes.

**Valida: Requisitos 3.1, 3.2, 3.3, 3.4**

## Implementação da Correção

### Alterações Necessárias

Assumindo que a análise de causa raiz está correta:

**Arquivo**: `src/services/strands_agent_service.py`

**Função**: `process_message` (variável `orchestrator_prompt`)

**Alterações Específicas**:

1. **Adicionar regra de prioridade para vencimento no `student_agent`**: Na seção de regras de roteamento do `orchestrator_prompt`, adicionar uma regra explícita que mapeia mensagens sobre alteração de vencimento para `student_agent`:
   ```
   - Palavras como "vencimento", "dia de vencimento", "dia do pagamento" combinadas com ações de alteração ("alterar", "mudar", "trocar") → student_agent (pois payment_due_day é um dado cadastral do aluno)
   ```

2. **Qualificar a regra do `payment_agent`**: Ajustar a regra existente do `payment_agent` para excluir explicitamente ações de alteração de vencimento:
   ```
   - Palavras como "pagamento", "pagar", "valor", "recibo", "confirmar pagamento" → payment_agent
   - "mensalidade" → payment_agent APENAS para registrar/visualizar/confirmar pagamentos, NÃO para alterar vencimento
   ```

3. **Adicionar regra de desambiguação**: Incluir uma regra explícita de desambiguação no prompt:
   ```
   REGRA DE DESAMBIGUAÇÃO: Se a mensagem contém "vencimento" ou "dia de vencimento" ou "dia do pagamento" junto com ação de alteração, SEMPRE encaminhe para student_agent, mesmo que contenha "mensalidade".
   ```

4. **Atualizar descrição do `student_agent`**: Expandir a descrição do `student_agent` no prompt para incluir explicitamente "alterar vencimento/dia de pagamento":
   ```
   - student_agent: Para QUALQUER assunto sobre alunos (registrar, listar, atualizar alunos, alterar vencimento/dia de pagamento)
   ```

5. **Manter regras existentes intactas**: Todas as outras regras de roteamento devem permanecer inalteradas para garantir preservação do comportamento existente.

## Estratégia de Testes

### Abordagem de Validação

A estratégia de testes segue uma abordagem em duas fases: primeiro, evidenciar contraexemplos que demonstram o bug no código não corrigido, depois verificar que a correção funciona e preserva o comportamento existente.

### Verificação Exploratória da Condição do Bug

**Objetivo**: Evidenciar contraexemplos que demonstram o bug ANTES de implementar a correção. Confirmar ou refutar a análise de causa raiz. Se refutarmos, precisaremos re-hipotizar.

**Plano de Teste**: Simular chamadas ao `process_message` com mensagens sobre alteração de vencimento e verificar qual agente é invocado. Executar no código NÃO corrigido para observar falhas.

**Casos de Teste**:
1. **Teste de Vencimento com Mensalidade**: Enviar "alterar vencimento da mensalidade da juliana nano para dia 28" (vai falhar no código não corrigido — roteará para `payment_agent`)
2. **Teste de Dia de Vencimento**: Enviar "mudar dia de vencimento do João para 15" (vai falhar no código não corrigido)
3. **Teste de Dia do Pagamento**: Enviar "trocar o dia do pagamento da Maria para dia 5" (vai falhar no código não corrigido)
4. **Teste de Atualizar Vencimento**: Enviar "atualizar vencimento da Ana para dia 10" (vai falhar no código não corrigido)

**Contraexemplos Esperados**:
- O orquestrador invoca `payment_agent` ao invés de `student_agent`
- O `payment_agent` responde pedindo o ID interno do aluno
- Causa: a palavra "mensalidade"/"vencimento" na regra de roteamento mapeia para `payment_agent` sem considerar o contexto de alteração

### Verificação da Correção (Fix Checking)

**Objetivo**: Verificar que para todas as entradas onde a condição do bug é verdadeira, o orquestrador corrigido produz o comportamento esperado.

**Pseudocódigo:**
```
PARA TODA mensagem ONDE isBugCondition(mensagem) FAÇA
  resultado := orquestrador_corrigido(mensagem)
  ASSERT resultado.agente_chamado = "student_agent"
         E resultado.ferramenta_usada = "update_student"
         E resultado.resposta NÃO contém "ID"
FIM PARA
```

### Verificação de Preservação (Preservation Checking)

**Objetivo**: Verificar que para todas as entradas onde a condição do bug NÃO é verdadeira, o orquestrador corrigido produz o mesmo resultado que o original.

**Pseudocódigo:**
```
PARA TODA mensagem ONDE NÃO isBugCondition(mensagem) FAÇA
  ASSERT orquestrador_original(mensagem) = orquestrador_corrigido(mensagem)
FIM PARA
```

**Abordagem de Teste**: Testes baseados em propriedades são recomendados para verificação de preservação porque:
- Geram muitos casos de teste automaticamente no domínio de entrada
- Capturam casos extremos que testes manuais podem perder
- Fornecem garantias fortes de que o comportamento não mudou para entradas não-bugadas

**Plano de Teste**: Observar o comportamento no código NÃO corrigido para operações de pagamento e outras interações, depois escrever testes baseados em propriedades capturando esse comportamento.

**Casos de Teste**:
1. **Preservação de Registro de Pagamento**: Verificar que "registrar pagamento de R$300 da Maria" continua roteando para `payment_agent`
2. **Preservação de Visualização de Pagamentos**: Verificar que "ver pagamentos do João" continua roteando para `payment_agent`
3. **Preservação de Confirmação de Pagamento**: Verificar que "confirmar pagamento abc123" continua roteando para `payment_agent`
4. **Preservação de Atualização de Aluno**: Verificar que "atualizar email do João" continua roteando para `student_agent`

### Testes Unitários

- Testar que o `orchestrator_prompt` contém a regra de desambiguação para vencimento
- Testar parsing de mensagens com palavras-chave de vencimento combinadas com ações de alteração
- Testar que mensagens de pagamento puro (sem ação de alteração de vencimento) continuam mapeando para `payment_agent`

### Testes Baseados em Propriedades

- Gerar mensagens aleatórias combinando palavras de vencimento com ações de alteração e verificar roteamento para `student_agent`
- Gerar mensagens aleatórias de operações de pagamento e verificar preservação do roteamento para `payment_agent`
- Gerar mensagens aleatórias de outros domínios e verificar que o roteamento não é afetado

### Testes de Integração

- Testar fluxo completo: mensagem de alteração de vencimento → `student_agent` → `update_student` → resposta sem pedir ID
- Testar fluxo de pagamento após correção: mensagem de registro de pagamento → `payment_agent` → `register_payment`
- Testar mensagens ambíguas contendo "mensalidade" em contextos diferentes (pagamento vs. vencimento)
