# Implementation Plan: Custom Domain Deployment

## Overview

Add custom domain support (`fitassistant.com.br`) to the FitAgent static website by extending the existing CloudFormation template with Route 53, ACM, and DNS resources, creating a new landing page, updating navigation across all pages, building a deploy script, and documenting manual steps. Implementation uses Python for tests, Bash for the deploy script, and YAML for CloudFormation.

## Tasks

- [x] 1. Update CloudFormation template with domain infrastructure
  - [x] 1.1 Add DomainName parameter and Route 53 Hosted Zone
    - Add `DomainName` parameter (Type: String, Default: `fitassistant.com.br`) to `infrastructure/template.yml`
    - Add `StaticWebsiteHostedZone` resource (`AWS::Route53::HostedZone`) referencing the `DomainName` parameter
    - Add `HostedZoneNameServers` output exporting the hosted zone nameservers
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 8.2_

  - [x] 1.2 Add ACM certificate with DNS validation
    - Add `StaticWebsiteCertificate` resource (`AWS::CertificateManager::Certificate`) in us-east-1
    - Configure `DomainName` for apex and `SubjectAlternativeNames` for `www.{DomainName}`
    - Set `ValidationMethod: DNS` with `DomainValidationOptions` pointing to the hosted zone
    - Add `CertificateArn` output
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 8.3_

  - [x] 1.3 Add DNS records (A + AAAA for apex and www)
    - Add `StaticWebsiteApexARecord` (A alias → CloudFront distribution)
    - Add `StaticWebsiteWwwARecord` (A alias → CloudFront distribution)
    - Add `StaticWebsiteApexAAAARecord` (AAAA alias → CloudFront distribution)
    - Add `StaticWebsiteWwwAAAARecord` (AAAA alias → CloudFront distribution)
    - All records in the `StaticWebsiteHostedZone`
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 1.4 Update CloudFront distribution with aliases and certificate
    - Add `Aliases` list with apex domain and www subdomain to `StaticWebsiteDistribution`
    - Add `ViewerCertificate` with `AcmCertificateArn` referencing the ACM certificate and `SslSupportMethod: sni-only`
    - Change `DefaultRootObject` from `privacidade.html` to `index.html`
    - Ensure `ViewerProtocolPolicy: redirect-to-https` is preserved
    - Add `StaticWebsiteCustomUrl` and `StaticWebsiteDistributionId` outputs
    - _Requirements: 3.1, 3.2, 3.4, 7.7, 8.1, 8.3_

  - [ ]* 1.5 Write property test: Hosted Zone uses domain parameter (Property 1)
    - **Property 1: Hosted Zone uses domain parameter**
    - Parse `infrastructure/template.yml`, generate random valid domain strings, verify `StaticWebsiteHostedZone` Name references the `DomainName` parameter
    - Test file: `tests/property/test_custom_domain_deployment_properties.py`
    - **Validates: Requirements 1.1, 1.2**

  - [ ]* 1.6 Write property test: CloudFront Aliases contain both domain variants (Property 2)
    - **Property 2: CloudFront Aliases contain both domain variants**
    - Parse template YAML, verify CloudFront `Aliases` list contains apex domain and `www.{domain}` for any valid domain string
    - Test file: `tests/property/test_custom_domain_deployment_properties.py`
    - **Validates: Requirements 3.1**

  - [ ]* 1.7 Write property test: Original CloudFormation resources preserved (Property 7)
    - **Property 7: Original CloudFormation resources preserved**
    - Parse original and updated template YAML, verify all original resource logical IDs are still present with unchanged `Type`
    - Test file: `tests/property/test_custom_domain_deployment_properties.py`
    - **Validates: Requirements 8.1**

  - [ ]* 1.8 Write unit tests for CloudFormation template changes
    - Test `DomainName` parameter exists with correct type and default
    - Test `DefaultRootObject` is `index.html`
    - Test ACM certificate uses DNS validation and covers www subdomain
    - Test outputs exist: `HostedZoneNameServers`, `CertificateArn`, `StaticWebsiteCustomUrl`
    - Test `ViewerProtocolPolicy` remains `redirect-to-https`
    - Test file: `tests/unit/test_custom_domain_deployment.py`
    - _Requirements: 1.2, 1.4, 2.3, 2.5, 3.4, 7.7, 8.3_

- [x] 2. Checkpoint - Validate infrastructure changes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Create landing page and update navigation
  - [x] 3.1 Create `static-website/index.html` landing page
    - Create new `index.html` with `lang="pt-BR"`, FitAgent description, and navigation links to `privacidade.html` and `termos.html`
    - Use embedded CSS matching the existing style (same reset, body, `.container`, `header`, `footer`, `main`, responsive media query as `privacidade.html`)
    - Include header with logo and nav, main content with service description, footer with copyright and nav links
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 3.2 Update navigation in `static-website/privacidade.html`
    - Add link to `index.html` (Início) in header nav and footer nav
    - _Requirements: 8.4_

  - [x] 3.3 Update navigation in `static-website/termos.html`
    - Add link to `index.html` (Início) in header nav and footer nav
    - _Requirements: 8.4_

  - [x] 3.4 Update navigation in `static-website/erro.html`
    - Add link to `index.html` (Início) in the error page links
    - _Requirements: 8.4_

  - [ ]* 3.5 Write property test: Cross-page navigation completeness (Property 5)
    - **Property 5: Cross-page navigation completeness**
    - Parse all HTML files, extract `<a href>` values, verify each non-error page links to all other non-error pages, and `erro.html` links to all three non-error pages
    - Test file: `tests/property/test_custom_domain_deployment_properties.py`
    - **Validates: Requirements 7.4, 8.4**

  - [ ]* 3.6 Write property test: CSS consistency across all pages (Property 6)
    - **Property 6: CSS consistency across all pages**
    - Parse all HTML files, extract `<style>` blocks, compare base CSS rules across pages to ensure visual consistency
    - Test file: `tests/property/test_custom_domain_deployment_properties.py`
    - **Validates: Requirements 7.6**

  - [ ]* 3.7 Write unit tests for HTML pages
    - Test `index.html` has `lang="pt-BR"` attribute
    - Test `index.html` contains FitAgent service description
    - Test `erro.html` links to `index.html`
    - Test file: `tests/unit/test_custom_domain_deployment.py`
    - _Requirements: 7.2, 7.3, 8.4_

- [x] 4. Checkpoint - Validate static pages
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Create deploy script
  - [x] 5.1 Create `scripts/deploy.sh`
    - Accept CloudFormation stack name as `$1` argument
    - Query stack outputs for bucket name (`StaticWebsiteBucketName`) and distribution ID (`StaticWebsiteDistributionId`)
    - Upload all `.html` files from `static-website/` to S3 with `--content-type text/html`
    - Create CloudFront invalidation for `/*`
    - Use `set -e` for error handling; print descriptive error messages to stderr on failure
    - Make script executable (`chmod +x`)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 5.2 Write property test: Deploy script uploads all HTML files (Property 3)
    - **Property 3: Deploy script uploads all HTML files with correct Content-Type**
    - Generate random sets of `.html` files, parse script logic, verify all files are targeted with correct Content-Type
    - Test file: `tests/property/test_custom_domain_deployment_properties.py`
    - **Validates: Requirements 6.1, 6.2**

  - [ ]* 5.3 Write property test: Deploy script exits non-zero on failure (Property 4)
    - **Property 4: Deploy script exits non-zero on failure**
    - Mock AWS CLI commands to return various non-zero exit codes, verify script exits non-zero with descriptive error
    - Test file: `tests/property/test_custom_domain_deployment_properties.py`
    - **Validates: Requirements 6.5**

  - [ ]* 5.4 Write unit tests for deploy script
    - Test script is executable
    - Test script accepts stack name argument (`$1`)
    - Test file: `tests/unit/test_custom_domain_deployment.py`
    - _Requirements: 6.4, 6.5_

- [x] 6. Create manual steps guide
  - [x] 6.1 Create `docs/configuracao-dominio.md` in PT-BR
    - Write step-by-step instructions covering: deploy do stack CloudFormation, obtenção dos nameservers, configuração dos nameservers no registro.br, verificação da propagação DNS, verificação da validação do certificado SSL, execução do script de deploy
    - Ensure correct execution order: deploy stack → configure nameservers → wait for propagation → validate certificate
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 6.2 Write unit tests for manual steps guide
    - Test guide contains nameserver configuration instructions
    - Test guide contains DNS propagation verification instructions
    - Test deploy stack section appears before nameserver section (correct execution order)
    - Test file: `tests/unit/test_custom_domain_deployment.py`
    - _Requirements: 5.2, 5.3, 5.6_

- [x] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All 7 correctness properties from the design are covered as property test sub-tasks
- The deploy script and manual guide are wired into the overall flow via checkpoints
