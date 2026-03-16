# Implementation Plan: Páginas Estáticas do Website

## Overview

Implementar páginas HTML estáticas (Política de Privacidade, Termos de Serviço, Página de Erro) hospedadas via S3 + CloudFront, com infraestrutura definida em CloudFormation. As páginas são em Português-BR com branding FitAgent consistente e navegação cruzada.

## Tasks

- [x] 1. Adicionar infraestrutura S3 + CloudFront ao template CloudFormation
  - [x] 1.1 Adicionar recurso `StaticWebsiteBucket` (S3) ao `infrastructure/template.yml`
    - Bucket com nome `fitagent-static-website-${Environment}-${AWS::AccountId}`
    - `PublicAccessBlockConfiguration` com tudo bloqueado
    - `BucketEncryption` com AES256
    - _Requirements: 1.1, 1.5, 5.1, 5.2, 5.3_
  - [x] 1.2 Adicionar recurso `StaticWebsiteCloudFrontOAC` e `StaticWebsiteBucketPolicy`
    - OAC com `OriginAccessControlOriginType: s3`, `SigningBehavior: always`, `SigningProtocol: sigv4`
    - Bucket policy permitindo acesso somente via CloudFront OAC
    - _Requirements: 1.5, 5.1_
  - [x] 1.3 Adicionar recurso `StaticWebsiteDistribution` (CloudFront)
    - `ViewerProtocolPolicy: redirect-to-https`
    - `DefaultRootObject: privacidade.html`
    - Custom error responses: 403 → `/erro.html` (404), 404 → `/erro.html` (404)
    - Origin apontando para o `StaticWebsiteBucket` com OAC
    - _Requirements: 1.2, 1.3, 1.4, 5.1, 5.4, 6.1_
  - [x] 1.4 Adicionar Outputs para `StaticWebsiteBucketName` e `StaticWebsiteUrl`
    - Output com nome do bucket para deploy dos arquivos HTML
    - Output com URL do CloudFront (domain name da distribuição)
    - _Requirements: 5.1_

- [-] 2. Checkpoint - Validar template CloudFormation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Criar páginas HTML estáticas
  - [x] 3.1 Criar `static-website/privacidade.html` — Página de Política de Privacidade
    - HTML com `lang="pt-BR"`, meta charset UTF-8, meta viewport, CSS embedded responsivo
    - Header com nome "FitAgent" e navegação (link para `termos.html`)
    - Seções obrigatórias: coleta de dados, uso de dados, compartilhamento de dados, armazenamento e segurança, direitos do usuário, informações de contato
    - Identificar FitAgent como responsável pelo tratamento dos dados
    - Descrever tipos de dados coletados: número de telefone, nome, mensagens, comprovantes de pagamento
    - Informar que dados são armazenados na AWS com criptografia
    - Mencionar integrações com Twilio (WhatsApp), Google Calendar, Microsoft Outlook
    - Footer com link para `termos.html` e copyright
    - Layout responsivo com max-width, system fonts, CSS flexbox/media queries
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 4.1, 4.3_
  - [x] 3.2 Criar `static-website/termos.html` — Página de Termos de Serviço
    - HTML com `lang="pt-BR"`, meta charset UTF-8, meta viewport, CSS embedded responsivo (mesmo estilo)
    - Header com nome "FitAgent" e navegação (link para `privacidade.html`)
    - Seções obrigatórias: descrição do serviço, condições de uso, responsabilidades do usuário, limitações de responsabilidade, propriedade intelectual, disposições gerais
    - Descrever FitAgent como plataforma de gestão para personal trainers via WhatsApp
    - Informar sobre dependência de serviços de terceiros (WhatsApp, AWS, provedores de calendário)
    - Footer com link para `privacidade.html` e copyright
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.2, 4.3_
  - [x] 3.3 Criar `static-website/erro.html` — Página de erro 404
    - HTML com `lang="pt-BR"`, meta charset UTF-8, meta viewport, CSS embedded responsivo (mesmo estilo)
    - Header com nome "FitAgent"
    - Mensagem amigável de página não encontrada em Português-BR
    - Links para `privacidade.html` e `termos.html`
    - _Requirements: 6.1, 6.2, 4.3_

- [x] 4. Checkpoint - Verificar páginas HTML
  - Ensure all tests pass, ask the user if questions arise.

- [-] 5. Escrever testes para conteúdo das páginas e propriedades
  - [x] 5.1 Criar `tests/unit/test_static_pages_content.py` com testes de conteúdo
    - Verificar que `privacidade.html` contém seções obrigatórias (coleta de dados, uso de dados, compartilhamento, segurança, direitos, contato)
    - Verificar menção ao FitAgent como responsável pelo tratamento dos dados
    - Verificar menção aos tipos de dados (telefone, nome, mensagens, comprovantes)
    - Verificar menção à AWS e criptografia
    - Verificar menção a Twilio, Google Calendar, Microsoft Outlook
    - Verificar que `termos.html` contém seções obrigatórias (descrição do serviço, condições de uso, responsabilidades, limitações, propriedade intelectual, disposições gerais)
    - Verificar descrição do FitAgent como plataforma para personal trainers
    - Verificar menção a dependência de serviços de terceiros
    - Verificar que todas as páginas têm `lang="pt-BR"`
    - Verificar que todas as páginas têm meta viewport
    - Verificar que `privacidade.html`, `termos.html` e `erro.html` existem no diretório `static-website/`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
  - [ ]* 5.2 Escrever property test para cross-linking entre páginas
    - **Property 1: Cross-linking entre páginas**
    - Para qualquer página HTML do website, verificar que contém links (`<a href="...">`) para todas as outras páginas de conteúdo
    - Criar `tests/property/test_static_pages_properties.py`
    - Usar Hypothesis com `@given(sampled_from([...]))` para selecionar páginas aleatoriamente
    - Mínimo 100 iterações via `@settings(max_examples=100)`
    - **Validates: Requirements 4.1, 4.2, 6.2**
  - [ ]* 5.3 Escrever property test para branding consistente
    - **Property 2: Branding consistente**
    - Para qualquer página HTML do website, verificar que contém "FitAgent" no conteúdo visível
    - Adicionar ao `tests/property/test_static_pages_properties.py`
    - Usar Hypothesis com `@given(sampled_from([...]))` para selecionar páginas aleatoriamente
    - Mínimo 100 iterações via `@settings(max_examples=100)`
    - **Validates: Requirements 4.3**

- [x] 6. Escrever testes para template CloudFormation
  - [x] 6.1 Criar `tests/unit/test_static_website_cloudformation.py`
    - Verificar que o template contém recurso `StaticWebsiteBucket` com naming pattern `fitagent-static-website-${Environment}-${AWS::AccountId}`
    - Verificar que o template contém `PublicAccessBlockConfiguration` com tudo bloqueado
    - Verificar que o template contém `StaticWebsiteDistribution` com `ViewerProtocolPolicy: redirect-to-https`
    - Verificar que o template contém custom error responses para 403 e 404 apontando para `/erro.html`
    - Verificar que o template contém OAC com `SigningBehavior: always` e `SigningProtocol: sigv4`
    - Verificar que existem Outputs para `StaticWebsiteBucketName` e `StaticWebsiteUrl`
    - _Requirements: 1.2, 1.3, 1.5, 5.1, 5.2, 5.4, 6.1_

- [x] 7. Final checkpoint - Garantir que todos os testes passam
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marcadas com `*` são opcionais e podem ser puladas para um MVP mais rápido
- Cada task referencia requisitos específicos para rastreabilidade
- Checkpoints garantem validação incremental
- Property tests validam propriedades universais de cross-linking e branding
- Unit tests validam conteúdo específico de cada página e configuração CloudFormation
- Os arquivos HTML ficam em `static-website/` na raiz do projeto para deploy ao S3
