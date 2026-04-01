# Checklist: Configuração da Tela de Consentimento Google

Guia passo a passo para configurar a tela de consentimento OAuth no Google Cloud Console, necessária para a verificação do FitAgent.

## Pré-requisitos

- Acesso ao [Google Cloud Console](https://console.cloud.google.com/) com permissões de editor no projeto
- Logo do FitAgent em formato PNG, 120x120px
- Páginas de Termos de Serviço e Política de Privacidade publicadas e acessíveis via HTTPS
- Domínio `fitassistant.com.br` verificado no Google Search Console

## Passo a passo

1. Acesse **Google Cloud Console → APIs & Services → OAuth consent screen**
2. Selecione **External** como tipo de usuário (se ainda não configurado)
3. Preencha os campos conforme a tabela abaixo
4. Na seção **Scopes**, adicione o escopo listado na tabela
5. Salve e envie para verificação

## Campos obrigatórios

| Campo | Valor esperado | Observações |
|-------|---------------|-------------|
| App name | `FitAgent` | Nome exibido na tela de consentimento |
| User support email | *(email de suporte do projeto)* | Email visível para usuários que precisam de ajuda |
| App logo | Logo do FitAgent (120x120px, PNG) | Deve seguir as [diretrizes de branding do Google](https://developers.google.com/identity/branding-guidelines) |
| Application home page | `{WEBSITE_BASE_URL}` | Ex: `https://www.fitassistant.com.br` |
| Application privacy policy link | `{WEBSITE_BASE_URL}/privacidade.html` | Página pública, acessível sem autenticação |
| Application terms of service link | `{WEBSITE_BASE_URL}/termos.html` | Página pública, acessível sem autenticação |
| Authorized domains | `fitassistant.com.br` | Domínio verificado no Google Search Console |
| Scopes | `https://www.googleapis.com/auth/calendar` | Escopo sensível — requer verificação do Google |

## Validação

Antes de submeter para verificação, confirme que:

- [ ] O nome "FitAgent" aparece corretamente na preview da tela de consentimento
- [ ] O logo está nítido e dentro das dimensões exigidas (120x120px)
- [ ] Os links de Política de Privacidade e Termos de Serviço abrem corretamente em uma nova aba
- [ ] O domínio autorizado está verificado no Google Search Console
- [ ] O escopo `https://www.googleapis.com/auth/calendar` está listado como escopo solicitado
- [ ] O email de suporte é válido e monitorado pela equipe
