# Configuração do Domínio Personalizado — fitassistant.com.br

Guia operacional para configurar o domínio personalizado no FitAgent.

**Pré-requisitos:**
- AWS CLI configurado com credenciais válidas
- Acesso ao painel do [registro.br](https://registro.br)
- Domínio `fitassistant.com.br` registrado no registro.br

**Ordem de execução:**
1. Deploy do stack CloudFormation
2. Obtenção dos nameservers
3. Configuração dos nameservers no registro.br
4. Verificação da propagação DNS
5. Verificação da validação do certificado SSL
6. Execução do script de deploy

---

## 1. Deploy do Stack CloudFormation

O stack cria a Hosted Zone no Route 53, solicita o certificado SSL no ACM (com validação DNS automática), configura os registros DNS (A e AAAA para apex e www) e atualiza a distribuição CloudFront com aliases e certificado.

> **Importante:** O stack deve ser implantado na região `us-east-1`, pois certificados ACM para CloudFront precisam estar nessa região.

Validar o template antes do deploy:

```bash
aws cloudformation validate-template \
  --template-body file://infrastructure/template.yml \
  --region us-east-1
```

Deploy do stack:

```bash
aws cloudformation deploy \
  --template-file infrastructure/template.yml \
  --stack-name fitagent-production \
  --parameter-overrides \
    Environment=production \
    DomainName=fitassistant.com.br \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

> **Nota:** O CloudFormation ficará aguardando a validação do certificado SSL. Isso é esperado — a validação só será concluída após a configuração dos nameservers no registro.br e a propagação DNS. O stack pode levar até 30+ minutos para concluir.

---

## 2. Obtenção dos Nameservers

Após o stack iniciar a criação (não precisa esperar concluir), obtenha os nameservers da Hosted Zone:

```bash
aws cloudformation describe-stacks \
  --stack-name fitagent-production \
  --query "Stacks[0].Outputs[?OutputKey=='HostedZoneNameServers'].OutputValue" \
  --output text \
  --region us-east-1
```

O retorno será uma lista de 4 nameservers separados por vírgula, por exemplo:

```
ns-123.awsdns-45.com,ns-678.awsdns-90.net,ns-111.awsdns-22.org,ns-333.awsdns-44.co.uk
```

Anote esses valores — eles serão usados no próximo passo.

Alternativamente, consulte diretamente via Route 53:

```bash
HOSTED_ZONE_ID=$(aws route53 list-hosted-zones-by-name \
  --dns-name fitassistant.com.br \
  --query "HostedZones[0].Id" \
  --output text \
  --region us-east-1)

aws route53 get-hosted-zone \
  --id "${HOSTED_ZONE_ID}" \
  --query "DelegationSet.NameServers" \
  --output table \
  --region us-east-1
```

---

## 3. Configuração dos Nameservers no registro.br

Este é o único passo manual que não pode ser automatizado.

1. Acesse [https://registro.br](https://registro.br) e faça login
2. Selecione o domínio `fitassistant.com.br`
3. Vá em **DNS** → **Alterar servidores DNS**
4. Remova os nameservers atuais
5. Adicione os 4 nameservers obtidos no passo anterior, um por campo:
   - `ns-123.awsdns-45.com`
   - `ns-678.awsdns-90.net`
   - `ns-111.awsdns-22.org`
   - `ns-333.awsdns-44.co.uk`
6. Salve as alterações

> **Atenção:** Use os nameservers exatos retornados pelo seu stack, não os exemplos acima.

---

## 4. Verificação da Propagação DNS

A propagação DNS pode levar de alguns minutos até 48 horas. Verifique o progresso com:

```bash
dig fitassistant.com.br NS +short
```

O resultado deve listar os 4 nameservers da AWS. Se o comando `dig` não estiver disponível:

```bash
nslookup -type=NS fitassistant.com.br
```

Para verificar se o domínio já resolve para o CloudFront:

```bash
dig fitassistant.com.br A +short
```

O resultado deve retornar IPs da rede CloudFront.

---

## 5. Verificação da Validação do Certificado SSL

Após a propagação DNS, o ACM validará automaticamente o certificado. Verifique o status:

```bash
CERT_ARN=$(aws cloudformation describe-stacks \
  --stack-name fitagent-production \
  --query "Stacks[0].Outputs[?OutputKey=='CertificateArn'].OutputValue" \
  --output text \
  --region us-east-1)

aws acm describe-certificate \
  --certificate-arn "${CERT_ARN}" \
  --query "Certificate.Status" \
  --output text \
  --region us-east-1
```

O status esperado é `ISSUED`. Se ainda estiver `PENDING_VALIDATION`, aguarde a propagação DNS e tente novamente.

Verifique também se o stack CloudFormation concluiu com sucesso:

```bash
aws cloudformation describe-stacks \
  --stack-name fitagent-production \
  --query "Stacks[0].StackStatus" \
  --output text \
  --region us-east-1
```

O status esperado é `CREATE_COMPLETE` ou `UPDATE_COMPLETE`.

---

## 6. Execução do Script de Deploy

Com o stack concluído e o certificado validado, faça o deploy dos arquivos estáticos:

```bash
./scripts/deploy.sh fitagent-production
```

O script irá:
1. Consultar os outputs do stack para obter o nome do bucket S3 e o ID da distribuição CloudFront
2. Fazer upload de todos os arquivos `.html` de `static-website/` para o S3 com `Content-Type: text/html`
3. Criar uma invalidação no CloudFront (`/*`) para limpar o cache

Após a conclusão, acesse `https://fitassistant.com.br` para verificar o website.

---

## Solução de Problemas

| Problema | Causa provável | Solução |
|---|---|---|
| Stack travado em `CREATE_IN_PROGRESS` | Certificado aguardando validação DNS | Configure os nameservers no registro.br e aguarde a propagação |
| Certificado em `PENDING_VALIDATION` | DNS ainda não propagou | Verifique com `dig` se os nameservers estão corretos e aguarde |
| `ERR_CERT_COMMON_NAME_INVALID` no navegador | Certificado ainda não foi associado ao CloudFront | Aguarde o stack concluir completamente |
| Script de deploy falha com "stack not found" | Nome do stack incorreto | Verifique o nome exato com `aws cloudformation list-stacks` |
| Site retorna erro 403 | Arquivos não foram enviados ao S3 | Execute `./scripts/deploy.sh <stack-name>` novamente |


---

## 7. Domínio Personalizado da API — api.fitassistant.com.br

Além do website estático, o FitAgent utiliza um domínio personalizado para a API Gateway: `api.fitassistant.com.br`. Esse domínio é configurado automaticamente pelo stack CloudFormation, que cria um certificado SSL dedicado (`ApiCertificate`), um custom domain name no API Gateway, o mapeamento de base path e o registro DNS no Route 53.

### 7.1 Verificação da Resolução DNS

Após o deploy do stack, verifique se o subdomínio da API está resolvendo corretamente:

```bash
dig api.fitassistant.com.br A +short
```

O resultado deve retornar um ou mais IPs do endpoint regional do API Gateway. Se o comando `dig` não estiver disponível:

```bash
nslookup api.fitassistant.com.br
```

Caso o subdomínio não resolva, aguarde a propagação DNS (pode levar alguns minutos) e verifique se o stack CloudFormation concluiu com sucesso.

### 7.2 Verificação do Certificado SSL da API

Verifique se o certificado SSL do subdomínio da API foi emitido com sucesso:

```bash
API_CERT_ARN=$(aws cloudformation describe-stacks \
  --stack-name fitagent-production \
  --query "Stacks[0].Outputs[?OutputKey=='ApiCertificateArn'].OutputValue" \
  --output text \
  --region us-east-1)

aws acm describe-certificate \
  --certificate-arn "${API_CERT_ARN}" \
  --query "Certificate.Status" \
  --output text \
  --region us-east-1
```

O status esperado é `ISSUED`.

### 7.3 Teste do Endpoint de Webhook

Teste o endpoint de webhook usando o domínio personalizado:

```bash
curl -X POST https://api.fitassistant.com.br/webhook
```

O endpoint deve responder com um código HTTP (ex: 200 ou 400 dependendo do payload). Se retornar erro de conexão ou certificado, verifique os passos anteriores.

### 7.4 Teste do Callback OAuth

Teste o endpoint de callback OAuth:

```bash
curl https://api.fitassistant.com.br/oauth/callback
```

O endpoint deve responder (mesmo que com erro de parâmetros ausentes, o importante é que a conexão HTTPS funcione e a rota seja encontrada).

### 7.5 Atualização das URIs de Redirecionamento OAuth

> **Importante:** Após o deploy com o domínio personalizado da API, é necessário atualizar as URIs de redirecionamento OAuth nos provedores externos.

**Google Cloud Console:**
1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
2. Navegue até **APIs e Serviços** → **Credenciais**
3. Edite o cliente OAuth 2.0 do FitAgent
4. Em **URIs de redirecionamento autorizados**, adicione:
   ```
   https://api.fitassistant.com.br/oauth/callback
   ```
5. Salve as alterações

**Azure AD (Microsoft):**
1. Acesse o [Portal do Azure](https://portal.azure.com/)
2. Navegue até **Azure Active Directory** → **Registros de aplicativo**
3. Selecione o aplicativo do FitAgent
4. Em **Autenticação** → **URIs de redirecionamento**, adicione:
   ```
   https://api.fitassistant.com.br/oauth/callback
   ```
5. Salve as alterações

> **Nota:** Tokens OAuth existentes não são afetados pela mudança de URI. Apenas novos fluxos de autorização utilizarão a URL atualizada.

### 7.6 Solução de Problemas — Domínio da API

| Problema | Causa provável | Solução |
|---|---|---|
| `dig api.fitassistant.com.br` não retorna resultado | Registro DNS ainda não propagou ou stack não concluiu | Verifique o status do stack com `aws cloudformation describe-stacks` e aguarde a propagação |
| Erro de certificado SSL ao acessar a API | Certificado `ApiCertificate` ainda não foi validado | Verifique o status do certificado com o comando da seção 7.2 |
| `curl` retorna `Could not resolve host` | DNS não propagou ou nameservers incorretos | Verifique se os nameservers no registro.br estão corretos (seção 3) |
| Erro 403 Forbidden na API | Base path mapping não configurado corretamente | Verifique se o recurso `ApiBasePathMapping` foi criado no stack |
| OAuth callback falha com "redirect_uri_mismatch" | URI de redirecionamento não atualizada no provedor | Atualize as URIs conforme a seção 7.5 |
| API responde na URL antiga mas não no domínio personalizado | Custom domain name não associado ao API Gateway | Verifique se `ApiGatewayCustomDomain` foi criado com sucesso no stack |
