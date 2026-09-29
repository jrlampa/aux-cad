# Universalização — descoberta técnica preliminar

**Status:** descoberta incompleta; contrato upstream não confirmado

**Escopo:** identificar evidências locais e estabelecer o que falta para especificar uma consulta somente leitura de ordens para `mapa_cad_paleta` e `OXCADOXCAD`.
**Implementação nesta fase:** nenhuma. Não foram criados cliente, automação de login, scraping, chamadas ao sistema remoto ou alterações nos módulos consumidores.

## Resumo executivo

O repositório contém uma URL intranet para o Sistema de Universalização e comentários que associam o acesso às credenciais do GOMNET. Isso é configuração/documentação local, não prova de autenticação, endpoints, parâmetros ou formato de resposta da Universalização.

Uma tentativa inicial de acesso terminou com `ERR_INVALID_AUTH_CREDENTIALS`. Em sessão posterior, a interface foi carregada e rótulos de consulta foram vistos, mas não houve submissão de formulário nem inspeção de corpo de requisição/resposta. Na auditoria atual, a aba aberta tinha o título “Universalização”, mas não expunha formulários HTML nem iframes. Assim, o contrato da consulta, os campos retornados, a identidade da ordem e as notas de observação continuam **não confirmados**. Não se deve implementar uma integração presumindo que a Universalização reutiliza o fluxo HTTP de GOMNET ou SGT.

## Evidências e grau de certeza

| Informação | Evidência | Situação |
|---|---|---|
| Endereço configurado | `.env.example` define `URL_SISTEMA_UNIVERSALIZACAO` como `http://gtecprorio.enelint.global/sistemas/universalizacao/`. | Confirmado no modelo de configuração; disponibilidade atual não confirmada. |
| Credenciais compartilhadas | Comentários no `.env.example` dizem que as credenciais `GOMNET_LOGIN`/`GOMNET_SENHA` também são usadas pela Universalização. | Afirmação no repositório; não verificada no sistema. |
| Login e autenticação | Uma tentativa inicial terminou com credencial inválida; uma sessão posterior carregou a interface, sem identificar como ocorreu a autenticação. | Mecanismo não observado; desconhecido. |
| Consulta de ordens | Em sessão posterior foram vistos rótulos de formulário, mas nenhuma consulta foi submetida e nenhuma resposta foi inspecionada. | Interface parcialmente observada; contrato da consulta não observado. |
| Método, rota e parâmetros | Não há código local de integração encontrado para a Universalização. | Desconhecidos. |
| Formato e campos de resposta | Não foi obtida resposta técnica do sistema. | Desconhecidos. |
| Identificador da ordem e semântica de busca | Não foi observada uma consulta real nem regra para identificar univocamente a ordem. | Desconhecidos. |
| Notas de observação, endereço e cliente | A amostra mencionada pelo usuário aparenta incluir informação pessoal e endereço; não foi possível confirmar rótulos, estrutura ou origem dos campos no sistema. | Relato do usuário, não evidência técnica observada. |
| Segurança de transporte | A URL configurada usa `http://`. | Confirmado na configuração; não permite concluir se há proteção adicional de rede, proxy ou túnel corporativo. |

## Matriz do contrato e evidências observadas

| Aspecto | O que foi observado | Estado do contrato |
|---|---|---|
| URL base | `.env.example` contém `http://gtecprorio.enelint.global/sistemas/universalizacao/`. | Confirmada somente como configuração local; disponibilidade e uso atuais não confirmados. |
| Página da interface | Sessão anterior carregou conteúdo em `principal.asp`; foram vistos os rótulos `Número Ordem de Projeto`, `Projetos Grupo`, `Status do Projeto` e `Pólo Técnico`. | Evidência histórica de interface, não de endpoint de consulta. |
| Estado da aba nesta auditoria | Título “Universalização”; `document.readyState=complete`; zero formulários HTML e zero iframes; marcadores de login e dos rótulos de ordem não presentes no texto da página. | Observação limitada ao DOM da aba atual; não prova autenticação, indisponibilidade ou ausência de consulta implementada em outra camada. |
| Método HTTP da consulta | Nenhuma consulta foi submetida; o tráfego anteriormente observado era de carregamento GET. | **DESCONHECIDO**. |
| Rota da consulta | `principal.asp` foi observado como página carregada, não como destino confirmado de consulta. | **DESCONHECIDA**. |
| Parâmetros/campos enviados | Nenhum corpo de consulta foi observado. | **DESCONHECIDOS**. |
| Autenticação e sessão | Há uma falha histórica de credencial inválida e comentário local associando credenciais GOMNET; nenhum mecanismo foi confirmado. | **DESCONHECIDAS**. |
| Content-Type e formato da resposta | Nenhuma resposta de consulta foi capturada ou inspecionada. | **DESCONHECIDOS**. |
| Campos, identificador e semântica dos resultados | Nenhum resultado de consulta foi observado. | **DESCONHECIDOS**. |
| Erros e paginação | Não exercitados nem observados. | **DESCONHECIDOS**. |

Nenhuma consulta foi submetida nesta auditoria. Os valores de formulário, corpos de tráfego, cabeçalhos de autenticação, cookies e dados pessoais não foram coletados. A evidência necessária para fechar o contrato continua sendo uma única consulta somente leitura executada manualmente pelo usuário em sessão corporativa autorizada, compartilhada de forma sanitizada.

## Sistemas locais próximos, mas não equivalentes

- `unifilar/arvore_client.py` consulta o SGT/Caminho Elétrico. O código usa `requests.Session`, tenta autenticação NTLM, lê campos de estado ASP.NET e envia um POST. Isso descreve o cliente SGT, não a Universalização.
- `sob/sob_gomnet.py` implementa autenticação e consultas do GOMNET por formulário HTTP/ASP.NET, mantendo uma sessão. Isso descreve o GOMNET, não a Universalização.
- `.env.example` documenta credenciais compartilhadas, mas compartilhar um par de credenciais não demonstra que os sistemas compartilham protocolo, sessão, endpoint ou autorização.
- `oxcad/OxCadPaleta.csproj` e `mapa_cad_paleta/MapaCadPaleta.csproj` são consumidores .NET/AutoCAD; não foi encontrado neles um cliente ou contrato de Universalização. A compatibilidade de um futuro assembly compartilhado deve ser avaliada para os TFMs efetivos dos dois projetos antes de implementá-lo.

## Contrato upstream: estado da especificação

Não há dados suficientes para fixar um contrato HTTP sem especulação. Os seguintes itens devem permanecer em aberto:

1. Como uma sessão autenticada é estabelecida, renovada e encerrada.
2. Qual rota e método atendem à consulta, e se há redirecionamentos ou estado antifalsificação.
3. Quais campos de entrada são necessários e qual deles identifica a ordem.
4. Como distinguir ordem inexistente, múltiplos resultados, sessão expirada e erro transitório.
5. Se a resposta é HTML, JSON ou outro formato e onde aparecem endereço e notas de observação.
6. Regras de paginação, normalização, codificação e eventual restrição de consulta.
7. Quais campos podem ser usados legalmente e operacionalmente pelos módulos consumidores.

### Esboço interno compartilhável — proposta, não contrato confirmado

Quando o fluxo real estiver documentado, a integração deve ser exposta por uma abstração independente de AutoCAD e da interface:

```text
IUniversalizacaoClient
  ConsultarOrdemAsync(consulta, cancellationToken)
    -> resultado tipado da consulta
```

O contrato interno deve conter apenas o identificador de busca confirmado e os campos efetivamente retornados e autorizados para uso. Deve representar explicitamente “não encontrada”, erro de autenticação e falha de comunicação, sem confundir esses estados com uma resposta vazia válida. Os DTOs e os nomes finais dos campos ficam pendentes da captura sanitizada do upstream.

Como ambos os consumidores são projetos .NET orientados a AutoCAD, uma biblioteca de contratos multi-consumidor pode ser avaliada depois de confirmar os TFMs e limites de compatibilidade. O cliente de rede deve ficar separado dos view models e APIs específicas do AutoCAD. Não se recomenda copiar o fluxo GOMNET/SGT nem escolher agora um endpoint, pacote de autenticação ou parser.

## Captura manual segura necessária

Em uma sessão corporativa autorizada, controlada pelo usuário e já autenticada, observar uma única consulta somente leitura pela interface normal do sistema. Compartilhar apenas:

- método HTTP, host e caminho, removendo query values que contenham identificadores pessoais ou segredos;
- nomes dos parâmetros/campos enviados, com valores removidos ou substituídos;
- tipo de conteúdo, status HTTP e indicação de redirecionamento;
- mecanismo de autenticação em nível conceitual (por exemplo, SSO, NTLM ou formulário), sem copiar credenciais nem detalhes de sessão;
- formato e nomes dos campos da resposta, com valores pessoais removidos;
- como a interface identifica a ordem e apresenta observações/endereço, usando rótulos e exemplos sintéticos;
- paginação e mensagens de “não encontrado”/erro, se presentes.

**Não compartilhar nem registrar** senhas, `.env`, cookies, cabeçalhos `Authorization`, tokens, `__VIEWSTATE`/`__EVENTVALIDATION`, HAR bruto, nomes/endereço de clientes ou respostas integrais com dados pessoais. Não automatizar login, repetir requisições fora da interface ou enviar consultas em lote nesta etapa.

## Observação de sessão posterior

Em uma sessão posterior, a página configurada carregou conteúdo da aplicação em `principal.asp` e exibiu um formulário com os rótulos `Número Ordem de Projeto`, `Projetos Grupo`, `Status do Projeto` e `Pólo Técnico`. A lista de tráfego observada nessa navegação continha apenas requisições GET de carregamento das páginas, incluindo uma resposta 302 seguida de respostas 200. Nenhum formulário foi submetido e nenhum corpo de requisição/resposta foi inspecionado.

Isso confirma que a interface e esses rótulos estão visíveis nesta sessão; não confirma o mecanismo de autenticação, o contrato da consulta, a semântica dos campos nem o formato dos resultados. A captura de uma única consulta permanece pendente de execução manual pelo usuário.

### Rechecagem da aba atual

Na auditoria atual, a aba selecionada continuava com o título “Universalização” e o documento carregado (`readyState=complete`), mas o DOM não continha formulários HTML ou iframes e não apresentava os marcadores textuais do formulário histórico. Não houve clique, preenchimento, submissão ou inspeção de requisições/respostas. A observação anterior dos rótulos permanece evidência histórica da interface; a consulta real permanece **não observada**.

## Limitações e decisão

- Uma sessão anterior carregou a interface, mas a rechecagem atual não encontrou formulário HTML padrão e nenhuma consulta foi feita; sem observar uma consulta real, não é possível confirmar o contrato nem produzir uma integração implementável.
- A tentativa anterior de acesso sem autenticação válida não demonstra indisponibilidade do sistema.
- Não foram lidos arquivos `.env` reais nem coletados segredos.
- Nenhuma consulta foi submetida nem alterados os consumidores nesta fase.
- O endereço configurado é HTTP; confirme com a equipe responsável se o acesso depende de um canal corporativo protegido antes de transmitir dados.

**Conclusão:** descoberta preliminar; contrato upstream **INCOMPLETO**. A integração deve aguardar evidência manual sanitizada do fluxo real. Até lá, autenticação, método/rota da consulta, campos, semântica da ordem e tratamento de observações permanecem bloqueados e não devem ser inventados.

## Referências do repositório

- [`.env.example`](./.env.example) — URL e comentários de configuração.
- [`unifilar/arvore_client.py`](./unifilar/arvore_client.py) — integração SGT, usada apenas como contraste.
- [`sob/sob_gomnet.py`](./sob/sob_gomnet.py) — integração GOMNET, usada apenas como contraste.
- [`oxcad/OxCadPaleta.csproj`](./oxcad/OxCadPaleta.csproj) — configuração do consumidor OXCADOXCAD.
- [`mapa_cad_paleta/MapaCadPaleta.csproj`](./mapa_cad_paleta/MapaCadPaleta.csproj) — configuração do consumidor mapa_cad_paleta.
