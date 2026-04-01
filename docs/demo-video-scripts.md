# Roteiros de Vídeo de Demonstração — Google OAuth Verification

Roteiros para gravação dos vídeos exigidos pelo Google no processo de verificação OAuth do FitAgent.

---

## Vídeo 1: Fluxo OAuth (Vídeo_Demo_OAuth)

**Objetivo:** Demonstrar o fluxo completo de autorização OAuth, desde a solicitação no WhatsApp até a confirmação de conexão.

**Duração estimada:** 1–2 minutos

### Roteiro

| Passo | Ação | O que mostrar na tela |
|-------|------|-----------------------|
| 1 | Abrir WhatsApp com a conversa do FitAgent | Tela do WhatsApp com o chat do FitAgent visível |
| 2 | Enviar mensagem: **"Quero conectar meu Google Calendar"** | Mensagem enviada pelo trainer |
| 3 | Aguardar resposta do FitAgent | Mensagem com o link OAuth e os links de **Termos de Serviço** e **Política de Privacidade** |
| 4 | Clicar no link OAuth | Navegador abrindo a URL de autorização do Google |
| 5 | Mostrar a tela de consentimento do Google | Nome **"FitAgent"**, escopo de calendário (`Google Calendar`), links de privacidade e termos de serviço |
| 6 | Clicar em **"Permitir"** (ou "Allow") | Botão de autorização sendo clicado |
| 7 | Mostrar a página de sucesso (Callback Landing Page) | Página com mensagem de sucesso em PT-BR e links de **Termos de Serviço** e **Política de Privacidade** no rodapé |
| 8 | Voltar ao WhatsApp | Mensagem de confirmação do FitAgent com links de **Termos de Serviço** e **Política de Privacidade** |

### Pontos de atenção na gravação

- Garantir que os links de Termos e Privacidade estejam visíveis em **todas** as etapas (mensagem inicial, tela do Google, página de callback, mensagem de confirmação).
- Na tela de consentimento do Google (passo 5), pausar brevemente para que o revisor consiga ler o nome do app, os escopos e os links.
- Não cortar ou acelerar a transição entre o clique em "Permitir" e a página de sucesso — o Google quer ver o redirect completo.

---

## Vídeo 2: Funcionalidade do App (Vídeo_Demo_Funcionalidade)

**Objetivo:** Demonstrar que o FitAgent realmente utiliza o escopo de calendário solicitado — agendar, reagendar e cancelar sessões com reflexo no Google Calendar.

**Duração estimada:** 2–3 minutos

**Pré-requisito:** Google Calendar já conectado (fluxo do Vídeo 1 já realizado).

### Roteiro

| Passo | Ação | O que mostrar na tela |
|-------|------|-----------------------|
| 1 | Abrir WhatsApp com a conversa do FitAgent | Chat do FitAgent (calendário já conectado) |
| 2 | Enviar mensagem: **"Agendar sessão com João para amanhã às 14h"** | Mensagem enviada pelo trainer |
| 3 | Aguardar confirmação do FitAgent | Mensagem confirmando o agendamento |
| 4 | Abrir o Google Calendar | Evento criado visível no calendário, com data e horário corretos |
| 5 | Voltar ao WhatsApp e enviar: **"Reagendar sessão de João para depois de amanhã às 15h"** | Mensagem enviada pelo trainer |
| 6 | Aguardar confirmação do FitAgent | Mensagem confirmando o reagendamento |
| 7 | Abrir o Google Calendar | Evento atualizado com a nova data/horário |
| 8 | Voltar ao WhatsApp e enviar: **"Cancelar sessão de João"** | Mensagem enviada pelo trainer |
| 9 | Aguardar confirmação do FitAgent | Mensagem confirmando o cancelamento |
| 10 | Abrir o Google Calendar | Evento removido do calendário |

### Pontos de atenção na gravação

- Ao alternar entre WhatsApp e Google Calendar, mostrar claramente que é o **mesmo evento** sendo modificado.
- No passo 4, destacar o nome do aluno, data e horário no evento do calendário.
- No passo 7, mostrar que a data/horário mudou em relação ao passo 4.
- No passo 10, mostrar que o evento **não aparece mais** no calendário (navegar até a data original para confirmar).
- Usar nomes reais ou realistas para o aluno (ex: "João Silva") para dar credibilidade.

---

## Dicas gerais para ambos os vídeos

- Gravar em resolução mínima de **720p** (1280×720). Recomendado: 1080p.
- Não usar edição que oculte partes da tela — o Google pode rejeitar vídeos editados.
- Manter o vídeo **sem narração** ou com narração simples; o foco é na interface.
- Fazer upload como **vídeo não listado** no YouTube e enviar o link no formulário de verificação.
