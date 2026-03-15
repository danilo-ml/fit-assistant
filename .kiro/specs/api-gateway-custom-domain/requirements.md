# Documento de Requisitos

## Introdução

O FitAgent já possui um API Gateway (`WebhookApi`) configurado no CloudFormation para receber webhooks do Twilio e callbacks OAuth. Atualmente, a API é acessível apenas pela URL padrão do API Gateway (ex: `https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/`). Este feature adiciona um domínio personalizado `api.fitassistant.com.br` ao API Gateway existente, permitindo que a API seja acessada por uma URL amigável e profissional.

A infraestrutura já conta com uma Hosted Zone no Route 53 para `fitassistant.com.br` (`StaticWebsiteHostedZone`) e um certificado ACM (`StaticWebsiteCertificate`) que cobre `fitassistant.com.br` e `www.fitassistant.com.br`. O certificado existente precisa ser estendido para cobrir também `api.fitassistant.com.br`, ou um novo certificado dedicado deve ser criado para o subdomínio da API.

O nome do domínio é parametrizado via parâmetro `DomainName` do CloudFormation (default: `fitassistant.com.br`).

## Glossário

- **API_Gateway**: API Gateway REST existente (`WebhookApi`) que serve os endpoints de webhook e OAuth callback do FitAgent.
- **Domínio_Personalizado_API**: Subdomínio `api.fitassistant.com.br` a ser associado ao API_Gateway para acesso via URL amigável.
- **Hosted_Zone**: Zona hospedada existente no AWS Route 53 (`StaticWebsiteHostedZone`) que gerencia os registros DNS de `fitassistant.com.br`.
- **Certificado_SSL_API**: Certificado SSL/TLS no AWS Certificate Manager (ACM) que cobre o subdomínio `api.fitassistant.com.br`.
- **Custom_Domain_Name**: Recurso `AWS::ApiGateway::DomainName` que associa o Domínio_Personalizado_API ao certificado SSL e ao API_Gateway.
- **Base_Path_Mapping**: Recurso `AWS::ApiGateway::BasePathMapping` que conecta o Custom_Domain_Name ao stage de deploy do API_Gateway.
- **Registro_DNS_API**: Registro DNS (A alias) no Route 53 que aponta `api.fitassistant.com.br` para o Custom_Domain_Name do API_Gateway.

## Requisitos

### Requisito 1: Certificado SSL/TLS para o Subdomínio da API

**User Story:** Como operador do FitAgent, eu quero que o subdomínio `api.fitassistant.com.br` tenha cobertura SSL/TLS, para que a API seja acessível via HTTPS com o domínio personalizado.

#### Critérios de Aceitação

1. THE CloudFormation template SHALL estender o Certificado_SSL existente (`StaticWebsiteCertificate`) para incluir `api.fitassistant.com.br` na lista de SubjectAlternativeNames, OU criar um novo Certificado_SSL_API dedicado ao subdomínio da API.
2. THE Certificado_SSL_API SHALL utilizar validação por DNS para comprovação de propriedade do domínio.
3. THE CloudFormation template SHALL criar os registros DNS de validação do Certificado_SSL_API na Hosted_Zone existente do Route_53.
4. THE Certificado_SSL_API SHALL ser criado na região `us-east-1` para compatibilidade com o API Gateway regional, OU na mesma região do stack para endpoints regionais.

### Requisito 2: Custom Domain Name no API Gateway

**User Story:** Como operador do FitAgent, eu quero configurar um domínio personalizado no API Gateway, para que a API seja acessível via `api.fitassistant.com.br`.

#### Critérios de Aceitação

1. THE CloudFormation template SHALL criar um recurso Custom_Domain_Name do tipo `AWS::ApiGateway::DomainName` para o Domínio_Personalizado_API (`api.fitassistant.com.br`).
2. THE Custom_Domain_Name SHALL utilizar o Certificado_SSL_API para conexões HTTPS.
3. THE Custom_Domain_Name SHALL ser configurado com endpoint do tipo REGIONAL, consistente com a configuração existente do API_Gateway.
4. THE Custom_Domain_Name SHALL utilizar TLS versão 1.2 como protocolo mínimo de segurança.
5. THE nome do domínio SHALL ser derivado do parâmetro `DomainName` do CloudFormation usando `!Sub 'api.${DomainName}'` para manter a parametrização.

### Requisito 3: Base Path Mapping

**User Story:** Como operador do FitAgent, eu quero que o domínio personalizado da API esteja conectado ao stage de deploy do API Gateway, para que as requisições ao domínio personalizado sejam roteadas corretamente para os endpoints existentes.

#### Critérios de Aceitação

1. THE CloudFormation template SHALL criar um recurso Base_Path_Mapping do tipo `AWS::ApiGateway::BasePathMapping` conectando o Custom_Domain_Name ao API_Gateway.
2. THE Base_Path_Mapping SHALL mapear o caminho raiz (`/`) do Custom_Domain_Name para o stage de deploy do API_Gateway.
3. THE Base_Path_Mapping SHALL referenciar o stage parametrizado pelo parâmetro `Environment` do CloudFormation.
4. WHEN uma requisição é feita para `https://api.fitassistant.com.br/{path}`, THE API_Gateway SHALL rotear a requisição para o endpoint correspondente no stage configurado.

### Requisito 4: Registro DNS para o Subdomínio da API

**User Story:** Como operador do FitAgent, eu quero que `api.fitassistant.com.br` resolva para o API Gateway, para que visitantes e integrações acessem a API digitando o subdomínio no navegador ou em chamadas HTTP.

#### Critérios de Aceitação

1. THE CloudFormation template SHALL criar um registro DNS do tipo A (alias) na Hosted_Zone existente apontando `api.fitassistant.com.br` para o Custom_Domain_Name do API_Gateway.
2. THE registro DNS SHALL utilizar o `RegionalDomainName` do Custom_Domain_Name como alvo do alias.
3. THE registro DNS SHALL utilizar o `RegionalHostedZoneId` do Custom_Domain_Name como HostedZoneId do alias.
4. WHEN o registro DNS é criado, THE Domínio_Personalizado_API SHALL resolver para o endpoint regional do API_Gateway.

### Requisito 5: Atualização das Referências de URL da API

**User Story:** Como desenvolvedor, eu quero que as referências internas à URL da API sejam atualizadas para usar o domínio personalizado, para que a configuração seja consistente e profissional.

#### Critérios de Aceitação

1. THE CloudFormation template SHALL adicionar um novo Output `ApiCustomDomainUrl` com a URL base do Domínio_Personalizado_API (ex: `https://api.fitassistant.com.br`).
2. THE CloudFormation template SHALL adicionar um novo Output `ApiCustomWebhookUrl` com a URL completa do webhook (ex: `https://api.fitassistant.com.br/webhook`).
3. THE CloudFormation template SHALL adicionar um novo Output `ApiCustomOAuthCallbackUrl` com a URL completa do callback OAuth (ex: `https://api.fitassistant.com.br/oauth/callback`).
4. THE variável de ambiente `OAUTH_REDIRECT_URI` das funções Lambda (`MessageProcessorFunction` e `OAuthCallbackFunction`) SHALL ser atualizada para usar o Domínio_Personalizado_API em vez da URL padrão do API Gateway.

### Requisito 6: Preservação da Infraestrutura Existente

**User Story:** Como desenvolvedor, eu quero que todos os recursos existentes do CloudFormation permaneçam inalterados, para que a adição do domínio personalizado da API não quebre a infraestrutura atual.

#### Critérios de Aceitação

1. THE CloudFormation template SHALL manter todos os recursos existentes com seus tipos e propriedades inalterados, exceto as modificações explicitamente descritas neste documento.
2. THE API_Gateway existente (`WebhookApi`) SHALL continuar acessível pela URL padrão do API Gateway além do Domínio_Personalizado_API.
3. THE Hosted_Zone existente (`StaticWebsiteHostedZone`) SHALL ser reutilizada para os novos registros DNS sem alteração em seus registros existentes.
4. IF o Certificado_SSL existente (`StaticWebsiteCertificate`) for estendido, THEN THE cobertura existente para `fitassistant.com.br` e `www.fitassistant.com.br` SHALL ser mantida.

### Requisito 7: Documentação da Configuração

**User Story:** Como operador do FitAgent, eu quero que o guia de configuração do domínio seja atualizado, para que eu saiba como verificar o funcionamento do domínio personalizado da API.

#### Critérios de Aceitação

1. THE documentação existente (`docs/configuracao-dominio.md`) SHALL ser atualizada para incluir informações sobre o Domínio_Personalizado_API.
2. THE documentação SHALL conter instruções para verificar que o Domínio_Personalizado_API está resolvendo corretamente para o API_Gateway.
3. THE documentação SHALL conter instruções para testar os endpoints do webhook e OAuth callback usando o Domínio_Personalizado_API.
4. THE documentação SHALL ser escrita em Português-BR.
