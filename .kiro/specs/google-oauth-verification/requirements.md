# Documento de Requisitos

## Introdução

O Google rejeitou a verificação do app FitAgent por dois motivos principais: (1) o vídeo de demonstração não mostra o fluxo do OAuth consent screen, e (2) o vídeo não demonstra suficientemente a funcionalidade do app. Além disso, é necessário incluir os Termos de Serviço e a Política de Privacidade no fluxo de sincronização do Google Calendar para que o Google valide o app.

Este documento especifica os requisitos para adequar o FitAgent ao processo de verificação do Google, cobrindo: inclusão de links de Termos de Serviço e Política de Privacidade nas mensagens e páginas do fluxo OAuth, configuração correta da tela de consentimento no Google Cloud Console, e preparação do vídeo de demonstração que atenda aos critérios do Google.

O FitAgent já possui páginas estáticas de Termos de Serviço (`termos.html`) e Política de Privacidade (`privacidade.html`) hospedadas via S3/CloudFront. O fluxo OAuth já está implementado (geração de URL, callback, troca de tokens, sincronização). O foco desta spec é preencher as lacunas de conformidade exigidas pelo Google.

## Glossário

- **FitAgent**: Plataforma SaaS de gestão para personal trainers via WhatsApp
- **Tela_Consentimento_Google**: Página de consentimento OAuth2 hospedada pelo Google que exibe nome do app, escopos solicitados, links de política de privacidade e termos de serviço
- **OAuth_Callback_Handler**: Função AWS Lambda que recebe o redirect do Google após o trainer autorizar acesso ao calendário
- **WhatsApp_Messenger**: Componente baseado em Twilio que envia e recebe mensagens WhatsApp para trainers
- **Callback_Landing_Page**: Página HTML exibida ao trainer no navegador após o redirect OAuth completar (sucesso ou erro)
- **Página_Termos**: Página HTML pública contendo os Termos de Serviço do FitAgent (`termos.html`)
- **Página_Privacidade**: Página HTML pública contendo a Política de Privacidade do FitAgent (`privacidade.html`)
- **URL_Base_Website**: URL base do website estático do FitAgent hospedado via CloudFront (ex: `https://www.fitassistant.com.br`)
- **Calendar_Sync_Service**: Serviço que cria, atualiza e deleta eventos no Google Calendar usando tokens OAuth2
- **Vídeo_Demo_OAuth**: Vídeo de demonstração que mostra o fluxo completo do OAuth consent screen
- **Vídeo_Demo_Funcionalidade**: Vídeo de demonstração que mostra a funcionalidade completa do app

## Requisitos

### Requisito 1: Links de Termos de Serviço e Privacidade na Mensagem de Conexão do Calendário

**User Story:** Como trainer, eu quero ver os links dos Termos de Serviço e Política de Privacidade quando inicio a conexão do Google Calendar, para que eu saiba quais condições estou aceitando ao autorizar o acesso.

#### Critérios de Aceitação

1. WHEN o trainer solicita a conexão do Google Calendar via WhatsApp, THE WhatsApp_Messenger SHALL incluir na mensagem de resposta os links para a Página_Termos e a Página_Privacidade junto com o link de autorização OAuth
2. THE WhatsApp_Messenger SHALL formatar a mensagem de conexão com o link OAuth, seguido de uma nota informando que ao conectar o calendário o trainer concorda com os Termos de Serviço e a Política de Privacidade do FitAgent
3. THE WhatsApp_Messenger SHALL utilizar as URLs completas da Página_Termos e da Página_Privacidade baseadas na URL_Base_Website configurada

### Requisito 2: Links de Termos de Serviço e Privacidade na Callback Landing Page

**User Story:** Como trainer, eu quero ver os links dos Termos de Serviço e Política de Privacidade na página de sucesso após autorizar o Google Calendar, para que eu possa consultá-los a qualquer momento.

#### Critérios de Aceitação

1. WHEN o OAuth flow completa com sucesso, THE Callback_Landing_Page SHALL exibir links clicáveis para a Página_Termos e a Página_Privacidade no rodapé da página de sucesso
2. WHEN o OAuth flow falha com erro, THE Callback_Landing_Page SHALL exibir links clicáveis para a Página_Termos e a Página_Privacidade no rodapé da página de erro
3. THE Callback_Landing_Page SHALL exibir os links de Termos e Privacidade como texto clicável com rótulos "Termos de Serviço" e "Política de Privacidade"

### Requisito 3: Links de Termos na Mensagem de Confirmação WhatsApp

**User Story:** Como trainer, eu quero receber os links dos Termos de Serviço e Política de Privacidade na mensagem de confirmação do WhatsApp após conectar o calendário, para que eu tenha fácil acesso aos documentos legais.

#### Critérios de Aceitação

1. WHEN o OAuth flow completa com sucesso, THE WhatsApp_Messenger SHALL incluir na mensagem de confirmação enviada ao trainer os links para a Página_Termos e a Página_Privacidade
2. THE WhatsApp_Messenger SHALL formatar a mensagem de confirmação com o status de sucesso da conexão, seguido dos links dos Termos de Serviço e Política de Privacidade

### Requisito 4: Configuração da URL Base do Website

**User Story:** Como desenvolvedor, eu quero que a URL base do website estático seja configurável via variável de ambiente, para que os links de Termos e Privacidade funcionem em todos os ambientes (local, staging, produção).

#### Critérios de Aceitação

1. THE FitAgent SHALL carregar a URL_Base_Website a partir de uma variável de ambiente `WEBSITE_BASE_URL`
2. IF a variável de ambiente `WEBSITE_BASE_URL` não estiver configurada, THEN THE FitAgent SHALL utilizar um valor padrão vazio e omitir os links de Termos e Privacidade das mensagens
3. THE FitAgent SHALL construir as URLs da Página_Termos como `{URL_Base_Website}/termos.html` e da Página_Privacidade como `{URL_Base_Website}/privacidade.html`

### Requisito 5: Configuração da Tela de Consentimento no Google Cloud Console

**User Story:** Como operador da plataforma, eu quero que a tela de consentimento do Google esteja configurada com todos os campos obrigatórios, para que o Google aprove a verificação do app.

#### Critérios de Aceitação

1. THE Tela_Consentimento_Google SHALL exibir o nome "FitAgent" como nome do aplicativo
2. THE Tela_Consentimento_Google SHALL exibir o link da Página_Privacidade como URL de política de privacidade
3. THE Tela_Consentimento_Google SHALL exibir o link da Página_Termos como URL de termos de serviço
4. THE Tela_Consentimento_Google SHALL listar o escopo `https://www.googleapis.com/auth/calendar` como permissão solicitada
5. THE Tela_Consentimento_Google SHALL exibir um logotipo do FitAgent aprovado pelo Google

### Requisito 6: Documentação do Vídeo de Demonstração OAuth

**User Story:** Como operador da plataforma, eu quero ter um roteiro documentado para gravar o vídeo de demonstração do fluxo OAuth, para que o vídeo atenda aos critérios de verificação do Google.

#### Critérios de Aceitação

1. THE FitAgent SHALL possuir um documento de roteiro que descreva passo a passo o fluxo a ser gravado no Vídeo_Demo_OAuth, incluindo: (a) trainer envia mensagem no WhatsApp solicitando conexão do calendário, (b) trainer recebe link OAuth com referência aos Termos e Privacidade, (c) trainer clica no link e visualiza a Tela_Consentimento_Google com nome do app, escopos e links legais, (d) trainer autoriza o acesso, (e) trainer visualiza a Callback_Landing_Page de sucesso com links de Termos e Privacidade, (f) trainer recebe mensagem de confirmação no WhatsApp
2. THE FitAgent SHALL possuir um documento de roteiro que descreva passo a passo o fluxo a ser gravado no Vídeo_Demo_Funcionalidade, incluindo: (a) trainer agenda uma sessão via WhatsApp, (b) sessão aparece no Google Calendar do trainer, (c) trainer reagenda a sessão via WhatsApp, (d) evento é atualizado no Google Calendar, (e) trainer cancela a sessão via WhatsApp, (f) evento é removido do Google Calendar

### Requisito 7: Mensagens em Português-BR

**User Story:** Como trainer brasileiro, eu quero que todas as mensagens e páginas do fluxo OAuth estejam em Português-BR, para que eu entenda claramente o que está acontecendo.

#### Critérios de Aceitação

1. THE WhatsApp_Messenger SHALL enviar a mensagem de conexão do calendário em Português-BR
2. THE WhatsApp_Messenger SHALL enviar a mensagem de confirmação de conexão em Português-BR
3. THE Callback_Landing_Page SHALL exibir todo o conteúdo de sucesso e erro em Português-BR
4. THE Callback_Landing_Page SHALL exibir os rótulos dos links de Termos e Privacidade em Português-BR ("Termos de Serviço" e "Política de Privacidade")
