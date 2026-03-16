# Documento de Requisitos

## Introdução

O FitAgent precisa de páginas web estáticas para atender requisitos legais e de conformidade. Duas páginas são necessárias: Política de Privacidade e Termos de Serviço, ambas em Português-BR. Essas páginas serão hospedadas como conteúdo estático via AWS (S3 + CloudFront) e acessíveis publicamente por URL, permitindo que sejam referenciadas nas conversas do WhatsApp e em integrações externas (ex: Twilio, Google OAuth).

## Glossário

- **Website_Estático**: Conjunto de páginas HTML estáticas hospedadas em um bucket S3 com distribuição CloudFront para servir conteúdo público do FitAgent.
- **Página_Privacidade**: Página HTML contendo a Política de Privacidade do FitAgent em Português-BR.
- **Página_Termos**: Página HTML contendo os Termos de Serviço do FitAgent em Português-BR.
- **S3_Bucket_Website**: Bucket S3 configurado para hospedagem de website estático.
- **CloudFront_Distribution**: Distribuição CDN da AWS que serve o conteúdo do S3 com HTTPS.
- **Visitante**: Qualquer pessoa que acessa as páginas estáticas do FitAgent via navegador web.

## Requisitos

### Requisito 1: Hospedagem de Website Estático

**User Story:** Como operador do FitAgent, eu quero hospedar páginas estáticas na AWS, para que visitantes possam acessar documentos legais via navegador web.

#### Critérios de Aceitação

1. THE S3_Bucket_Website SHALL armazenar os arquivos HTML das páginas estáticas do FitAgent.
2. THE CloudFront_Distribution SHALL servir o conteúdo do S3_Bucket_Website via HTTPS.
3. THE CloudFront_Distribution SHALL redirecionar requisições HTTP para HTTPS.
4. THE Website_Estático SHALL estar acessível publicamente sem necessidade de autenticação.
5. THE S3_Bucket_Website SHALL bloquear acesso público direto, permitindo acesso somente via CloudFront_Distribution usando Origin Access Control (OAC).

### Requisito 2: Página de Política de Privacidade

**User Story:** Como visitante, eu quero acessar a Política de Privacidade do FitAgent, para que eu possa entender como meus dados pessoais são coletados, usados e protegidos.

#### Critérios de Aceitação

1. THE Página_Privacidade SHALL estar acessível na rota `/privacidade.html`.
2. THE Página_Privacidade SHALL ser escrita inteiramente em Português-BR.
3. THE Página_Privacidade SHALL conter seções sobre: coleta de dados, uso de dados, compartilhamento de dados, armazenamento e segurança, direitos do usuário e informações de contato.
4. THE Página_Privacidade SHALL identificar o FitAgent como responsável pelo tratamento dos dados.
5. THE Página_Privacidade SHALL descrever os tipos de dados coletados via WhatsApp, incluindo número de telefone, nome, mensagens e comprovantes de pagamento.
6. THE Página_Privacidade SHALL informar que dados são armazenados na infraestrutura AWS com criptografia.
7. THE Página_Privacidade SHALL informar sobre a integração com serviços de terceiros: Twilio (mensagens WhatsApp), Google Calendar e Microsoft Outlook (sincronização de agenda).
8. THE Página_Privacidade SHALL ser renderizada corretamente em dispositivos móveis e desktop.

### Requisito 3: Página de Termos de Serviço

**User Story:** Como visitante, eu quero acessar os Termos de Serviço do FitAgent, para que eu possa entender as condições de uso da plataforma.

#### Critérios de Aceitação

1. THE Página_Termos SHALL estar acessível na rota `/termos.html`.
2. THE Página_Termos SHALL ser escrita inteiramente em Português-BR.
3. THE Página_Termos SHALL conter seções sobre: descrição do serviço, condições de uso, responsabilidades do usuário, limitações de responsabilidade, propriedade intelectual e disposições gerais.
4. THE Página_Termos SHALL descrever o FitAgent como uma plataforma de gestão para personal trainers via WhatsApp.
5. THE Página_Termos SHALL informar que o serviço depende de disponibilidade de serviços de terceiros (WhatsApp, AWS, provedores de calendário).
6. THE Página_Termos SHALL ser renderizada corretamente em dispositivos móveis e desktop.

### Requisito 4: Navegação entre Páginas

**User Story:** Como visitante, eu quero navegar entre as páginas de Política de Privacidade e Termos de Serviço, para que eu possa consultar ambos os documentos facilmente.

#### Critérios de Aceitação

1. THE Página_Privacidade SHALL conter um link para a Página_Termos.
2. THE Página_Termos SHALL conter um link para a Página_Privacidade.
3. THE Website_Estático SHALL exibir o nome "FitAgent" e o logotipo ou identidade visual em todas as páginas.

### Requisito 5: Infraestrutura como Código

**User Story:** Como desenvolvedor, eu quero que a infraestrutura do website estático seja definida em CloudFormation, para que o deploy seja automatizado e reproduzível.

#### Critérios de Aceitação

1. THE Website_Estático SHALL ter seus recursos de infraestrutura (S3, CloudFront) definidos no template CloudFormation existente.
2. THE CloudFormation template SHALL parametrizar o nome do bucket S3 usando o padrão de nomenclatura existente com Environment e AccountId.
3. WHEN o stack CloudFormation é implantado, THE S3_Bucket_Website SHALL ser criado com a configuração de website estático habilitada.
4. WHEN o stack CloudFormation é implantado, THE CloudFront_Distribution SHALL ser criada apontando para o S3_Bucket_Website.

### Requisito 6: Página de Erro

**User Story:** Como visitante, eu quero ver uma página de erro amigável quando acesso uma rota inexistente, para que eu tenha uma experiência consistente.

#### Critérios de Aceitação

1. WHEN um Visitante acessa uma rota inexistente no Website_Estático, THE CloudFront_Distribution SHALL retornar uma página de erro personalizada em Português-BR.
2. THE página de erro SHALL conter links para a Página_Privacidade e a Página_Termos.
