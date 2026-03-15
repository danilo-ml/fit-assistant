# Implementation Plan: API Gateway Custom Domain

## Overview

Add a custom domain `api.fitassistant.com.br` to the existing API Gateway REST API (`WebhookApi`) by creating a dedicated ACM certificate, configuring an API Gateway custom domain name with regional endpoint, setting up base path mapping, creating a DNS A-alias record, updating Lambda environment variables, adding new CloudFormation outputs, and updating the domain configuration documentation. Implementation uses Python for tests and YAML for CloudFormation.

## Tasks

- [x] 1. Add API certificate and custom domain resources to CloudFormation
  - [x] 1.1 Add ACM certificate for API subdomain
    - Add `ApiCertificate` resource (`AWS::CertificateManager::Certificate`) to `infrastructure/template.yml`
    - Configure `DomainName: !Sub 'api.${DomainName}'` with `ValidationMethod: DNS`
    - Set `DomainValidationOptions` pointing to `StaticWebsiteHostedZone`
    - Do NOT modify the existing `StaticWebsiteCertificate`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Add API Gateway custom domain name resource
    - Add `ApiGatewayCustomDomain` resource (`AWS::ApiGateway::DomainName`) to `infrastructure/template.yml`
    - Configure `DomainName: !Sub 'api.${DomainName}'`
    - Set `RegionalCertificateArn: !Ref ApiCertificate`
    - Set `EndpointConfiguration.Types: [REGIONAL]` and `SecurityPolicy: TLS_1_2`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 1.3 Add base path mapping
    - Add `ApiBasePathMapping` resource (`AWS::ApiGateway::BasePathMapping`) to `infrastructure/template.yml`
    - Set `DomainName: !Ref ApiGatewayCustomDomain`, `RestApiId: !Ref WebhookApi`, `Stage: !Ref Environment`
    - Do NOT specify `BasePath` (maps root `/`)
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 1.4 Add DNS A-alias record for API subdomain
    - Add `ApiDnsRecord` resource (`AWS::Route53::RecordSet`) to `infrastructure/template.yml`
    - Configure `Name: !Sub 'api.${DomainName}'`, `Type: A`, in `StaticWebsiteHostedZone`
    - Set `AliasTarget` with `RegionalDomainName` and `RegionalHostedZoneId` from `ApiGatewayCustomDomain`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 1.5 Write property test: API subdomain derived from DomainName parameter (Property 1)
    - **Property 1: API subdomain derived from DomainName parameter**
    - Parse `infrastructure/template.yml`, generate random valid domain strings, verify `ApiCertificate` and `ApiGatewayCustomDomain` DomainName resolve to `api.{domain}`
    - Test file: `tests/property/test_api_gateway_custom_domain_properties.py`
    - **Validates: Requirements 1.1, 2.5**

  - [ ]* 1.6 Write property test: API certificate uses DNS validation via existing hosted zone (Property 2)
    - **Property 2: API certificate uses DNS validation via existing hosted zone**
    - Parse template YAML, verify `ApiCertificate` has `ValidationMethod: DNS` and `DomainValidationOptions` references `StaticWebsiteHostedZone`
    - Test file: `tests/property/test_api_gateway_custom_domain_properties.py`
    - **Validates: Requirements 1.2, 1.3**

  - [ ]* 1.7 Write property test: Custom domain resource configuration (Property 3)
    - **Property 3: Custom domain resource configuration**
    - Parse template YAML, verify `ApiGatewayCustomDomain` has `REGIONAL` endpoint, `TLS_1_2` security policy, and `RegionalCertificateArn` referencing `ApiCertificate`
    - Test file: `tests/property/test_api_gateway_custom_domain_properties.py`
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

  - [ ]* 1.8 Write property test: Base path mapping connects custom domain to API stage (Property 4)
    - **Property 4: Base path mapping connects custom domain to API stage**
    - Parse template YAML, verify `ApiBasePathMapping` references `ApiGatewayCustomDomain`, `WebhookApi`, `Environment` parameter, and has no `BasePath`
    - Test file: `tests/property/test_api_gateway_custom_domain_properties.py`
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ]* 1.9 Write property test: DNS A-alias record points to API Gateway regional endpoint (Property 5)
    - **Property 5: DNS A-alias record points to API Gateway regional endpoint**
    - Parse template YAML, verify `ApiDnsRecord` is type `A`, references `StaticWebsiteHostedZone`, Name resolves to `api.{DomainName}`, and `AliasTarget` uses `RegionalDomainName` and `RegionalHostedZoneId`
    - Test file: `tests/property/test_api_gateway_custom_domain_properties.py`
    - **Validates: Requirements 4.1, 4.2, 4.3**

  - [ ]* 1.10 Write unit tests for new CloudFormation resources
    - Test `ApiCertificate` resource exists with type `AWS::CertificateManager::Certificate`
    - Test `ApiGatewayCustomDomain` resource exists with type `AWS::ApiGateway::DomainName`
    - Test `ApiBasePathMapping` resource exists with type `AWS::ApiGateway::BasePathMapping`
    - Test `ApiDnsRecord` resource exists with type `AWS::Route53::RecordSet`
    - Test existing `StaticWebsiteCertificate` SANs still contain only apex and www domains
    - Test `ApiCertificate` only covers `api.${DomainName}`, not the apex domain
    - Test file: `tests/unit/test_api_gateway_custom_domain.py`
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 6.1, 6.4_

- [x] 2. Checkpoint - Validate new infrastructure resources
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Update Lambda environment variables and add CloudFormation outputs
  - [x] 3.1 Update OAUTH_REDIRECT_URI in Lambda functions
    - Update `OAUTH_REDIRECT_URI` in `MessageProcessorFunction` from `https://${WebhookApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}/oauth/callback` to `!Sub 'https://api.${DomainName}/oauth/callback'`
    - Update `OAUTH_REDIRECT_URI` in `OAuthCallbackFunction` with the same change
    - _Requirements: 5.4_

  - [x] 3.2 Add new CloudFormation outputs
    - Add `ApiCustomDomainUrl` output: `!Sub 'https://api.${DomainName}'`
    - Add `ApiCustomWebhookUrl` output: `!Sub 'https://api.${DomainName}/webhook'`
    - Add `ApiCustomOAuthCallbackUrl` output: `!Sub 'https://api.${DomainName}/oauth/callback'`
    - Add `ApiCertificateArn` output: `!Ref ApiCertificate`
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ]* 3.3 Write property test: API custom domain outputs present with correct values (Property 6)
    - **Property 6: API custom domain outputs present with correct values**
    - Parse template YAML, generate random domain strings, verify outputs `ApiCustomDomainUrl`, `ApiCustomWebhookUrl`, `ApiCustomOAuthCallbackUrl` resolve to correct URL patterns
    - Test file: `tests/property/test_api_gateway_custom_domain_properties.py`
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [ ]* 3.4 Write property test: Lambda OAUTH_REDIRECT_URI uses custom domain (Property 7)
    - **Property 7: Lambda OAUTH_REDIRECT_URI uses custom domain**
    - Parse template YAML, generate random domain strings, verify `OAUTH_REDIRECT_URI` in both `MessageProcessorFunction` and `OAuthCallbackFunction` resolves to `https://api.{domain}/oauth/callback`
    - Test file: `tests/property/test_api_gateway_custom_domain_properties.py`
    - **Validates: Requirements 5.4**

  - [ ]* 3.5 Write property test: Existing CloudFormation resources preserved (Property 8)
    - **Property 8: Existing CloudFormation resources preserved**
    - Parse original and updated template YAML, verify all original resource logical IDs still present with unchanged `Type`, and `StaticWebsiteCertificate` SANs unchanged
    - Test file: `tests/property/test_api_gateway_custom_domain_properties.py`
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

  - [ ]* 3.6 Write unit tests for Lambda env vars and outputs
    - Test neither Lambda function's `OAUTH_REDIRECT_URI` contains `execute-api`
    - Test `ApiCustomDomainUrl` output exists
    - Test `ApiCustomWebhookUrl` output exists
    - Test `ApiCustomOAuthCallbackUrl` output exists
    - Test `ApiCertificateArn` output exists
    - Test file: `tests/unit/test_api_gateway_custom_domain.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 4. Checkpoint - Validate Lambda and output changes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update domain configuration documentation
  - [x] 5.1 Update `docs/configuracao-dominio.md` with API subdomain section
    - Append new section covering the API custom domain `api.fitassistant.com.br`
    - Include instructions to verify DNS resolution with `dig api.fitassistant.com.br A +short`
    - Include instructions to test webhook endpoint: `curl -X POST https://api.fitassistant.com.br/webhook`
    - Include instructions to test OAuth callback: `curl https://api.fitassistant.com.br/oauth/callback`
    - Include note about updating OAuth redirect URIs in Google Cloud Console and Azure AD
    - Include troubleshooting section for API custom domain issues
    - Write in Português-BR
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 5.2 Write unit tests for documentation update
    - Test `docs/configuracao-dominio.md` contains `api.fitassistant.com.br`
    - Test documentation contains `dig` or `curl` commands for the API subdomain
    - Test file: `tests/unit/test_api_gateway_custom_domain.py`
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 6. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- All 8 correctness properties from the design are covered as property test sub-tasks
- Property tests use Hypothesis and parse the CloudFormation template YAML
- Unit tests validate specific examples and edge cases
- The existing `StaticWebsiteCertificate` is NOT modified — a dedicated `ApiCertificate` is created instead
- Checkpoints ensure incremental validation between major task groups
