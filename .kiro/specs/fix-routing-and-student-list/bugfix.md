# Documento de Requisitos do Bugfix

## Introdução

O assistente WhatsApp FitAgent apresenta dois bugs que afetam a experiência do personal trainer:

1. **Roteamento de "vencimento" ainda quebrado**: Apesar de uma correção anterior ter adicionado regras de desambiguação no `orchestrator_prompt`, o LLM continua roteando mensagens como "alterar vencimento da mensalidade da juliana nano para dia 28" para o `payment_agent` em produção. As regras existentes não são suficientemente agressivas — o LLM prioriza a palavra "mensalidade" sobre as regras de desambiguação que aparecem depois no prompt. Além disso, o `student_agent` pode tentar registrar um novo aluno ao invés de usar `update_student` para atualizar o vencimento de um aluno existente.

2. **Lista de alunos não exibida**: Quando o trainer pede "Listar alunos" ou "Mostrar alunos", o `student_agent` chama `view_students` corretamente e recebe os dados do DynamoDB, mas a resposta do LLM diz "Esta é a lista de todos os alunos" sem incluir nenhum dado real. O prompt do `student_agent` não instrui o LLM a formatar e exibir os dados retornados pelas ferramentas.

## Análise do Bug

### Comportamento Atual (Defeito)

1.1 QUANDO o trainer envia uma mensagem para alterar o vencimento contendo "mensalidade" (ex: "alterar vencimento da mensalidade da juliana nano para dia 28") ENTÃO o sistema roteia para o `payment_agent` apesar das regras de desambiguação existentes, porque a regra de desambiguação aparece DEPOIS das regras de roteamento no prompt e o LLM prioriza a associação "mensalidade" → `payment_agent`.

1.2 QUANDO o trainer envia uma mensagem para alterar o vencimento de um aluno existente (ex: "mudar dia de vencimento do João para 15") ENTÃO o `student_agent` pode tentar usar `register_student` ao invés de `update_student`, pois o prompt do `student_agent` não diferencia claramente entre registrar um novo aluno e atualizar dados de um aluno existente.

1.3 QUANDO o trainer pede para listar alunos (ex: "Listar alunos", "Mostrar alunos") ENTÃO o `student_agent` chama `view_students`, recebe os dados JSON dos alunos, mas responde com "Esta é a lista de todos os alunos" sem incluir nenhuma informação real dos alunos na resposta.

1.4 QUANDO o trainer insiste pedindo a lista (ex: "Cadê a lista?") ENTÃO o sistema repete a mesma resposta vazia sem exibir os dados dos alunos.

### Comportamento Esperado (Correto)

2.1 QUANDO o trainer envia uma mensagem para alterar o vencimento contendo "mensalidade" (ex: "alterar vencimento da mensalidade da juliana nano para dia 28") ENTÃO o sistema DEVERÁ rotear para o `student_agent`, que usará `update_student` para atualizar o campo `payment_due_day` do aluno identificado por nome.

2.2 QUANDO o trainer envia uma mensagem para alterar o vencimento de um aluno existente ENTÃO o `student_agent` DEVERÁ usar a ferramenta `update_student` (não `register_student`) para atualizar o campo `payment_due_day`, identificando o aluno pelo nome via parâmetro `student_name`.

2.3 QUANDO o trainer pede para listar alunos ENTÃO o `student_agent` DEVERÁ formatar e exibir TODOS os dados dos alunos retornados por `view_students`, incluindo nome, telefone, email, objetivo de treino e dia de vencimento, em formato legível (lista numerada).

2.4 QUANDO `view_students` retorna uma lista vazia ENTÃO o `student_agent` DEVERÁ informar claramente que não há alunos cadastrados, ao invés de dizer "aqui está a lista" sem dados.

### Comportamento Inalterado (Prevenção de Regressão)

3.1 QUANDO o trainer envia uma mensagem para registrar um pagamento (ex: "registrar pagamento de R$300 da Maria") ENTÃO o sistema DEVERÁ CONTINUAR encaminhando para o `payment_agent` normalmente.

3.2 QUANDO o trainer envia uma mensagem para visualizar pagamentos ou status de mensalidade (ex: "ver pagamentos do João", "status de pagamento da Ana") ENTÃO o sistema DEVERÁ CONTINUAR encaminhando para o `payment_agent` normalmente.

3.3 QUANDO o trainer envia uma mensagem para atualizar outros dados do aluno sem mencionar "vencimento" (ex: "atualizar email do João") ENTÃO o sistema DEVERÁ CONTINUAR encaminhando para o `student_agent` normalmente.

3.4 QUANDO o trainer envia uma mensagem para confirmar um pagamento (ex: "confirmar pagamento abc123") ENTÃO o sistema DEVERÁ CONTINUAR encaminhando para o `payment_agent` normalmente.

3.5 QUANDO o trainer envia uma mensagem para registrar um novo aluno com todos os dados necessários ENTÃO o `student_agent` DEVERÁ CONTINUAR usando `register_student` normalmente.

3.6 QUANDO o trainer envia uma mensagem para agendar, reagendar ou cancelar sessões ENTÃO o sistema DEVERÁ CONTINUAR encaminhando para o `session_agent` normalmente.

---

### Condição do Bug 1: Roteamento de Vencimento (Pseudocódigo)

```pascal
FUNCTION isBugConditionRouting(X)
  INPUT: X do tipo MensagemDoTrainer
  OUTPUT: boolean

  // Retorna true quando a mensagem é sobre alterar vencimento/dia de pagamento
  RETURN X.mensagem contém ("vencimento" OU "dia de vencimento" OU "dia do pagamento")
         E X.mensagem contém ação de alteração ("alterar" OU "mudar" OU "trocar" OU "atualizar")
END FUNCTION
```

### Propriedade: Verificação da Correção do Roteamento

```pascal
// Propriedade: Fix Checking - Roteamento correto para alteração de vencimento
FOR ALL X WHERE isBugConditionRouting(X) DO
  resultado ← orquestrador'(X)
  ASSERT resultado.agente_chamado = "student_agent"
END FOR
```

### Condição do Bug 2: Lista de Alunos Vazia (Pseudocódigo)

```pascal
FUNCTION isBugConditionStudentList(X)
  INPUT: X do tipo MensagemDoTrainer
  OUTPUT: boolean

  // Retorna true quando a mensagem pede para listar/mostrar alunos
  RETURN X.mensagem contém ("listar alunos" OU "mostrar alunos" OU "ver alunos"
         OU "meus alunos" OU "lista de alunos" OU "quem são meus alunos")
END FUNCTION
```

### Propriedade: Verificação da Correção da Lista de Alunos

```pascal
// Propriedade: Fix Checking - student_agent exibe dados dos alunos
FOR ALL X WHERE isBugConditionStudentList(X) DO
  resultado ← student_agent'(X)
  // O prompt do student_agent DEVE conter instrução explícita para formatar
  // e exibir os dados retornados por view_students
  ASSERT student_agent_prompt contém instrução de formatação de resultados
         E student_agent_prompt contém instrução para NUNCA omitir dados retornados
END FOR
```

### Propriedade: Verificação de Preservação

```pascal
// Propriedade: Preservation Checking
FOR ALL X WHERE NOT isBugConditionRouting(X) AND NOT isBugConditionStudentList(X) DO
  ASSERT orquestrador(X) = orquestrador'(X)
END FOR
```
