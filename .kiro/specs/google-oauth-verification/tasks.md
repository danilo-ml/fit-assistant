# Plano de Implementação: Google OAuth Verification

## Visão Geral

Implementação das alterações necessárias para o FitAgent passar na verificação do Google OAuth. As mudanças incluem: adicionar `website_base_url` ao Settings com propriedades helper para URLs legais, incluir links de Termos de Serviço e Política de Privacidade em todas as mensagens e páginas do fluxo OAuth, traduzir conteúdo para PT-BR, e criar documentação de roteiros de vídeo e configuração do Google Cloud Console.

## Tarefas

- [x] 1. Adicionar configuração `website_base_url` ao Settings
  - [x] 1.1 Adicionar campo `website_base_url` e propriedades `terms_url`/`privacy_url` em `src/config.py`
    - Adicionar `website_base_url: str = ""` à classe `Settings`
    - Implementar `@property terms_url` que retorna `{base.rstrip("/")}/termos.html` ou string vazia
    - Implementar `@property privacy_url` que retorna `{base.rstrip("/")}/privacidade.html` ou string vazia
    - _Requisitos: 4.1, 4.2, 4.3_

  - [ ]* 1.2 Escrever teste property-based para construção de URLs legais
    - **Propriedade 1: Construção de URLs legais a partir da URL base**
    - Usar Hypothesis para gerar `base_url` aleatórias (com/sem trailing slash, diferentes protocolos)
    - Verificar que para `base_url` não-vazia, `terms_url` e `privacy_url` seguem o padrão esperado
    - Verificar que para `base_url` vazia, ambas retornam string vazia
    - Criar arquivo `tests/property/test_oauth_verification_properties.py`
    - **Valida: Requisitos 1.3, 4.1, 4.3**

  - [ ]* 1.3 Escrever testes unitários para `website_base_url` no Settings
    - Verificar que `Settings` carrega `WEBSITE_BASE_URL` do ambiente
    - Verificar que `terms_url` retorna vazio quando `website_base_url` está vazia
    - Verificar que `privacy_url` retorna vazio quando `website_base_url` está vazia
    - Criar testes em `tests/unit/test_oauth_verification.py`
    - _Requisitos: 4.1, 4.2, 4.3_

- [x] 2. Atualizar mensagem de conexão do calendário com links legais
  - [x] 2.1 Modificar `calendar_agent()` em `src/services/strands_agent_service.py`
    - Importar `settings` de `config.py`
    - Após construir a mensagem com `oauth_url`, adicionar parágrafo com links de Termos e Privacidade quando `settings.terms_url` não estiver vazio
    - Manter mensagem original quando `website_base_url` estiver vazia (graceful degradation)
    - _Requisitos: 1.1, 1.2, 1.3, 7.1_

  - [ ]* 2.2 Escrever teste property-based para mensagem de conexão
    - **Propriedade 2: Mensagem de conexão contém links legais**
    - Gerar `base_url` aleatórias não-vazias e providers válidos
    - Verificar que a mensagem de conexão contém ambas as URLs legais
    - Adicionar ao arquivo `tests/property/test_oauth_verification_properties.py`
    - **Valida: Requisitos 1.1, 1.2, 7.1**

- [x] 3. Checkpoint - Verificar testes até aqui
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [x] 4. Atualizar callback landing pages com links legais e conteúdo em PT-BR
  - [x] 4.1 Modificar `_success_html_response()` em `src/handlers/oauth_callback.py`
    - Receber `terms_url` e `privacy_url` como parâmetros (obtidos de `settings`)
    - Traduzir todo o conteúdo da página para PT-BR (título, mensagens, texto de fechar)
    - Adicionar rodapé com links clicáveis "Termos de Serviço" e "Política de Privacidade" com `target="_blank"`
    - Renderizar rodapé apenas quando `terms_url` não estiver vazio
    - Atualizar a chamada em `lambda_handler` para passar as URLs
    - _Requisitos: 2.1, 2.3, 7.3, 7.4_

  - [x] 4.2 Modificar `_error_html_response()` em `src/handlers/oauth_callback.py`
    - Receber `terms_url` e `privacy_url` como parâmetros
    - Traduzir todo o conteúdo da página para PT-BR
    - Adicionar rodapé com links clicáveis "Termos de Serviço" e "Política de Privacidade" com `target="_blank"`
    - Renderizar rodapé apenas quando `terms_url` não estiver vazio
    - Atualizar todas as chamadas de `_error_html_response()` no `lambda_handler` para passar as URLs
    - _Requisitos: 2.2, 2.3, 7.3, 7.4_

  - [ ]* 4.3 Escrever teste property-based para callback landing pages
    - **Propriedade 3: Callback landing pages contêm links legais com rótulos em PT-BR**
    - Gerar `base_url` aleatórias não-vazias, providers e mensagens de erro aleatórias
    - Verificar que o HTML de sucesso e erro contém `<a>` com `href` correto e rótulos "Termos de Serviço" e "Política de Privacidade"
    - Adicionar ao arquivo `tests/property/test_oauth_verification_properties.py`
    - **Valida: Requisitos 2.1, 2.2, 2.3, 7.3, 7.4**

  - [ ]* 4.4 Escrever testes unitários para conteúdo em PT-BR nas páginas
    - Verificar que a página de sucesso contém texto em PT-BR (não inglês)
    - Verificar que a página de erro contém texto em PT-BR
    - Adicionar ao arquivo `tests/unit/test_oauth_verification.py`
    - _Requisitos: 7.3, 7.4_

- [x] 5. Atualizar mensagem de confirmação WhatsApp com links legais e PT-BR
  - [x] 5.1 Modificar `_send_confirmation_message()` em `src/handlers/oauth_callback.py`
    - Traduzir mensagem de confirmação para PT-BR
    - Adicionar links de Termos de Serviço e Política de Privacidade quando `settings.terms_url` não estiver vazio
    - _Requisitos: 3.1, 3.2, 7.2_

  - [ ]* 5.2 Escrever teste property-based para mensagem de confirmação
    - **Propriedade 4: Mensagem de confirmação contém links legais**
    - Gerar `base_url` aleatórias não-vazias e providers válidos
    - Verificar que a mensagem de confirmação contém ambas as URLs legais
    - Adicionar ao arquivo `tests/property/test_oauth_verification_properties.py`
    - **Valida: Requisitos 3.1, 3.2, 7.2**

  - [ ]* 5.3 Escrever testes unitários para mensagem de confirmação em PT-BR
    - Verificar que a mensagem de confirmação está em PT-BR
    - Verificar que a mensagem de conexão está em PT-BR
    - Adicionar ao arquivo `tests/unit/test_oauth_verification.py`
    - _Requisitos: 7.1, 7.2_

- [x] 6. Checkpoint - Verificar testes de links legais e PT-BR
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [x] 7. Teste de graceful degradation e integração
  - [ ]* 7.1 Escrever teste property-based para graceful degradation
    - **Propriedade 5: Graceful degradation — links omitidos quando URL base vazia**
    - Gerar mensagens e páginas com `website_base_url` vazia
    - Verificar ausência de referências a `termos.html` e `privacidade.html` em todas as saídas
    - Adicionar ao arquivo `tests/property/test_oauth_verification_properties.py`
    - **Valida: Requisitos 4.2**

  - [x] 7.2 Conectar tudo e validar fluxo completo
    - Verificar que `lambda_handler` em `oauth_callback.py` passa `settings.terms_url` e `settings.privacy_url` para todas as funções de resposta HTML
    - Verificar que `calendar_agent()` em `strands_agent_service.py` usa `settings.terms_url` e `settings.privacy_url`
    - Verificar que `_send_confirmation_message()` usa `settings.terms_url` e `settings.privacy_url`
    - Adicionar `WEBSITE_BASE_URL` ao `.env.example`
    - _Requisitos: 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2, 4.3_

- [x] 8. Criar documentação de configuração e roteiros de vídeo
  - [x] 8.1 Criar documento de checklist para configuração da tela de consentimento Google
    - Criar arquivo `docs/google-consent-screen-setup.md`
    - Documentar campos obrigatórios: nome do app, email de suporte, logo, URLs de privacidade e termos, domínios autorizados, escopos
    - Incluir tabela com valores esperados conforme design
    - _Requisitos: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 8.2 Criar roteiros de vídeo de demonstração
    - Criar arquivo `docs/demo-video-scripts.md`
    - Documentar roteiro do Vídeo_Demo_OAuth: fluxo completo desde mensagem WhatsApp até confirmação
    - Documentar roteiro do Vídeo_Demo_Funcionalidade: agendar, reagendar e cancelar sessão com reflexo no Google Calendar
    - _Requisitos: 6.1, 6.2_

- [x] 9. Checkpoint final - Garantir que todos os testes passam
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

## Notas

- Tarefas marcadas com `*` são opcionais e podem ser puladas para um MVP mais rápido
- Cada tarefa referencia requisitos específicos para rastreabilidade
- Checkpoints garantem validação incremental
- Testes property-based validam propriedades universais de corretude
- Testes unitários validam exemplos específicos e edge cases
- Linguagem de implementação: Python 3.12 (conforme design e stack existente)
- Biblioteca de testes property-based: Hypothesis (já utilizada no projeto)
