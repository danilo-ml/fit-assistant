# Documento de Requisitos do Bugfix

## Introdução

Quando um personal trainer envia uma mensagem como "alterar vencimento da mensalidade da juliana nano para dia 28", o assistente de IA (FitAgent) pede o ID interno da aluna ao invés de resolver o nome automaticamente e executar a alteração. O trainer não deveria precisar saber ou informar IDs internos do sistema.

A causa raiz é um problema de roteamento no orquestrador: mensagens contendo "vencimento" e "mensalidade" são encaminhadas para o `payment_agent`, que não possui ferramenta para alterar o dia de vencimento (atributo `payment_due_day` do aluno). A ferramenta correta (`update_student`) está no `student_agent`, que já resolve nomes de alunos para IDs internamente.

## Análise do Bug

### Comportamento Atual (Defeito)

1.1 QUANDO o trainer envia uma mensagem para alterar o vencimento da mensalidade de um aluno identificado pelo nome (ex: "alterar vencimento da mensalidade da juliana nano para dia 28") ENTÃO o sistema encaminha a solicitação para o `payment_agent` que não possui ferramenta para alterar `payment_due_day`, resultando em uma resposta pedindo o ID interno do aluno ao trainer.

1.2 QUANDO o trainer envia uma mensagem contendo palavras-chave como "mensalidade" ou "vencimento" combinadas com uma ação de atualização de dados do aluno ENTÃO o orquestrador roteia incorretamente para o `payment_agent` ao invés do `student_agent`, pois as regras de roteamento priorizam "mensalidade" como domínio de pagamento.

### Comportamento Esperado (Correto)

2.1 QUANDO o trainer envia uma mensagem para alterar o vencimento da mensalidade de um aluno identificado pelo nome (ex: "alterar vencimento da mensalidade da juliana nano para dia 28") ENTÃO o sistema DEVERÁ encaminhar a solicitação para o `student_agent`, que usará a ferramenta `update_student` para resolver o nome do aluno e atualizar o campo `payment_due_day` sem pedir o ID ao trainer.

2.2 QUANDO o trainer envia uma mensagem contendo palavras-chave como "vencimento" ou "dia de vencimento" combinadas com uma ação de alteração ENTÃO o orquestrador DEVERÁ reconhecer que se trata de uma atualização de dados cadastrais do aluno e rotear para o `student_agent`.

### Comportamento Inalterado (Prevenção de Regressão)

3.1 QUANDO o trainer envia uma mensagem para registrar um pagamento (ex: "registrar pagamento de R$300 da Maria") ENTÃO o sistema DEVERÁ CONTINUAR encaminhando para o `payment_agent` normalmente.

3.2 QUANDO o trainer envia uma mensagem para visualizar pagamentos ou status de mensalidade (ex: "ver pagamentos do João", "status de pagamento da Ana") ENTÃO o sistema DEVERÁ CONTINUAR encaminhando para o `payment_agent` normalmente.

3.3 QUANDO o trainer envia uma mensagem para atualizar outros dados do aluno sem mencionar "mensalidade" (ex: "atualizar email do João") ENTÃO o sistema DEVERÁ CONTINUAR encaminhando para o `student_agent` normalmente.

3.4 QUANDO o trainer envia uma mensagem para confirmar um pagamento (ex: "confirmar pagamento abc123") ENTÃO o sistema DEVERÁ CONTINUAR encaminhando para o `payment_agent` normalmente.

---

### Condição do Bug (Pseudocódigo)

```pascal
FUNCTION isBugCondition(X)
  INPUT: X do tipo MensagemDoTrainer
  OUTPUT: boolean

  // Retorna true quando a mensagem é sobre alterar vencimento/dia de pagamento de um aluno
  RETURN X.mensagem contém ("vencimento" OU "dia de vencimento" OU "dia do pagamento")
         E X.mensagem contém ação de alteração ("alterar" OU "mudar" OU "trocar" OU "atualizar")
         E X.mensagem identifica o aluno por nome (não por ID)
END FUNCTION
```

### Propriedade: Verificação da Correção

```pascal
// Propriedade: Fix Checking - Roteamento correto para alteração de vencimento
FOR ALL X WHERE isBugCondition(X) DO
  resultado ← orquestrador'(X)
  ASSERT resultado.agente_chamado = "student_agent"
         E resultado.ferramenta_usada = "update_student"
         E resultado.resposta NÃO contém "ID"
         E resultado.resposta NÃO contém "informar o ID"
END FOR
```

### Propriedade: Verificação de Preservação

```pascal
// Propriedade: Preservation Checking - Pagamentos continuam no payment_agent
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT orquestrador(X) = orquestrador'(X)
END FOR
```
