# Documento de Requisitos

## Introdução

O FitAgent já possui um website estático hospedado via S3 + CloudFront (páginas de Política de Privacidade, Termos de Serviço e Erro). Atualmente, o website é acessível apenas pela URL padrão do CloudFront (ex: `d1234.cloudfront.net`). Este feature adiciona um domínio personalizado comprado no registro.br (provável `fitassistant.com.br`) ao website estático, utilizando Route 53 para gerenciamento de DNS e ACM para certificado SSL/TLS.

Como o domínio foi comprado no registro.br (registrador brasileiro), será necessário configurar os nameservers do registro.br para apontar para o Route 53 da AWS — um passo manual que será documentado.

## Glossário

- **Domínio_Personalizado**: Nome de domínio comprado no registro.br (ex: `fitassistant.com.br`) a ser associado ao website estático do FitAgent.
- **Hosted_Zone**: Zona hospedada no AWS Route 53 que gerencia os registros DNS do Domínio_Personalizado.
- **Certificado_SSL**: Certificado SSL/TLS emitido pelo AWS Certificate Manager (ACM) na região `us-east-1` para uso com CloudFront.
- **CloudFront_Distribution**: Distribuição CDN existente que serve o conteúdo estático do FitAgent.
- **Route_53**: Serviço de DNS gerenciado da AWS utilizado para resolver o Domínio_Personalizado para a CloudFront_Distribution.
- **Registro_BR**: Registrador de domínios brasileiro (registro.br) onde o Domínio_Personalizado foi adquirido.
- **Script_Deploy**: Script de automação para upload de arquivos estáticos ao S3 e invalidação do cache do CloudFront.
- **Guia_Passos_Manuais**: Documento com instruções para passos que requerem intervenção manual (ex: configuração de nameservers no registro.br).

## Requisitos

### Requisito 1: Zona Hospedada no Route 53

**User Story:** Como operador do FitAgent, eu quero uma zona hospedada no Route 53 para o domínio personalizado, para que os registros DNS sejam gerenciados pela AWS.

#### Critérios de Aceitação

1. THE CloudFormation template SHALL criar uma Hosted_Zone no Route_53 para o Domínio_Personalizado.
2. THE Hosted_Zone SHALL ser parametrizada para aceitar o nome do domínio como parâmetro do CloudFormation.
3. WHEN o stack CloudFormation é implantado, THE Hosted_Zone SHALL ser criada com os nameservers atribuídos pela AWS.
4. THE CloudFormation template SHALL exportar os nameservers da Hosted_Zone como Output para facilitar a configuração no Registro_BR.

### Requisito 2: Certificado SSL/TLS via ACM

**User Story:** Como operador do FitAgent, eu quero um certificado SSL/TLS válido para o domínio personalizado, para que o website seja acessível via HTTPS com o domínio próprio.

#### Critérios de Aceitação

1. THE CloudFormation template SHALL criar um Certificado_SSL no AWS Certificate Manager na região `us-east-1`.
2. THE Certificado_SSL SHALL cobrir o Domínio_Personalizado (ex: `fitassistant.com.br`).
3. THE Certificado_SSL SHALL utilizar validação por DNS para comprovação de propriedade do domínio.
4. THE CloudFormation template SHALL criar os registros DNS de validação do Certificado_SSL na Hosted_Zone do Route_53.
5. THE Certificado_SSL SHALL também cobrir o subdomínio `www` do Domínio_Personalizado (ex: `www.fitassistant.com.br`).

### Requisito 3: Configuração do CloudFront com Domínio Personalizado

**User Story:** Como operador do FitAgent, eu quero que a distribuição CloudFront existente aceite requisições pelo domínio personalizado, para que visitantes acessem o website pelo domínio próprio.

#### Critérios de Aceitação

1. THE CloudFront_Distribution SHALL incluir o Domínio_Personalizado e o subdomínio `www` como Alternate Domain Names (CNAMEs).
2. THE CloudFront_Distribution SHALL utilizar o Certificado_SSL emitido pelo ACM para conexões HTTPS.
3. WHEN um visitante acessa o Domínio_Personalizado via HTTPS, THE CloudFront_Distribution SHALL servir o conteúdo do website estático.
4. THE CloudFront_Distribution SHALL continuar redirecionando requisições HTTP para HTTPS.

### Requisito 4: Registros DNS Apontando para CloudFront

**User Story:** Como operador do FitAgent, eu quero que o domínio personalizado resolva para a distribuição CloudFront, para que visitantes acessem o website digitando o domínio no navegador.

#### Critérios de Aceitação

1. THE CloudFormation template SHALL criar um registro DNS do tipo A (alias) na Hosted_Zone apontando o Domínio_Personalizado para a CloudFront_Distribution.
2. THE CloudFormation template SHALL criar um registro DNS do tipo A (alias) na Hosted_Zone apontando `www.fitassistant.com.br` para a CloudFront_Distribution.
3. THE CloudFormation template SHALL criar registros AAAA (alias IPv6) correspondentes para o Domínio_Personalizado e o subdomínio `www`.

### Requisito 5: Documentação de Passos Manuais

**User Story:** Como operador do FitAgent, eu quero um guia documentado dos passos manuais necessários, para que eu possa completar a configuração do domínio no registro.br.

#### Critérios de Aceitação

1. THE Guia_Passos_Manuais SHALL ser criado como um arquivo no repositório do projeto.
2. THE Guia_Passos_Manuais SHALL conter instruções para atualizar os nameservers no Registro_BR para apontar para os nameservers do Route_53.
3. THE Guia_Passos_Manuais SHALL conter instruções para verificar a propagação DNS após a alteração dos nameservers.
4. THE Guia_Passos_Manuais SHALL conter instruções para verificar que o Certificado_SSL foi validado com sucesso após a propagação DNS.
5. THE Guia_Passos_Manuais SHALL ser escrito em Português-BR.
6. THE Guia_Passos_Manuais SHALL incluir a ordem correta de execução: primeiro deploy do stack, depois configuração dos nameservers, depois aguardar propagação e validação do certificado.

### Requisito 6: Script de Deploy

**User Story:** Como desenvolvedor, eu quero um script automatizado para fazer deploy dos arquivos estáticos, para que o processo de publicação seja rápido e reproduzível.

#### Critérios de Aceitação

1. THE Script_Deploy SHALL fazer upload de todos os arquivos HTML do diretório `static-website/` para o S3 bucket do website estático.
2. THE Script_Deploy SHALL definir o Content-Type correto (`text/html`) para arquivos HTML enviados ao S3.
3. WHEN o upload é concluído, THE Script_Deploy SHALL criar uma invalidação no CloudFront para limpar o cache.
4. THE Script_Deploy SHALL aceitar o nome do stack CloudFormation como parâmetro para obter automaticamente o nome do bucket e o ID da distribuição CloudFront.
5. IF o upload ou a invalidação falhar, THEN THE Script_Deploy SHALL exibir uma mensagem de erro descritiva e encerrar com código de saída diferente de zero.

### Requisito 7: Página Inicial (Landing Page)

**User Story:** Como visitante, eu quero ver uma página inicial ao acessar o domínio raiz, para que eu tenha uma apresentação do FitAgent e possa navegar para as páginas legais.

#### Critérios de Aceitação

1. THE Website_Estático SHALL ter uma página inicial acessível na rota `/` (index.html).
2. THE página inicial SHALL ser escrita em Português-BR.
3. THE página inicial SHALL apresentar o FitAgent com uma breve descrição do serviço.
4. THE página inicial SHALL conter links para a Página_Privacidade e a Página_Termos.
5. THE página inicial SHALL ser renderizada corretamente em dispositivos móveis e desktop.
6. THE página inicial SHALL seguir o mesmo estilo visual das demais páginas do website.
7. THE CloudFront_Distribution SHALL usar `index.html` como DefaultRootObject em vez de `privacidade.html`.

### Requisito 8: Infraestrutura como Código

**User Story:** Como desenvolvedor, eu quero que toda a infraestrutura de domínio personalizado seja definida no CloudFormation existente, para que o deploy seja automatizado e reproduzível.

#### Critérios de Aceitação

1. THE CloudFormation template SHALL manter todos os recursos existentes inalterados ao adicionar os novos recursos de domínio personalizado.
2. THE CloudFormation template SHALL parametrizar o nome do domínio para permitir uso em diferentes ambientes.
3. THE CloudFormation template SHALL exportar como Outputs: os nameservers da Hosted_Zone, o ARN do Certificado_SSL e a URL final do website com domínio personalizado.
4. THE Página_Privacidade, Página_Termos e página de erro SHALL conter links de navegação para a página inicial (index.html).
