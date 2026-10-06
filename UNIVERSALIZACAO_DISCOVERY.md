# Universalização — Relatório Técnico de Descoberta de Autenticação

**Data da Auditoria:** 2026-10-03
**Última Atualização:** 2026-10-06
**Status Atual:** INTEGRAÇÃO APROVADA TECNICAMENTE; STAGING SUJEITO À REVISÃO DE ESCOPO
**Alvo Investigado:** `http://gtecprorio.enelint.global/sistemas/universalizacao/`
**Escopo:** Descoberta do fluxo real de autenticação observado no Firefox versus testes automatizados.

---

## 1. Conectividade e Papel da VPN

* **Conexão VPN Ativa:** A conectividade com a rede corporativa é provida pelo cliente VPN Palo Alto GlobalProtect; o endereço da estação foi omitido.
* **Resolução DNS:** O FQDN `gtecprorio.enelint.global` é resolvido internamente pelo túnel; o endereço privado foi omitido.
* **Alcance de Rede:** O túnel VPN é suficiente para alcançar o servidor IIS tanto na porta 80 (HTTP) quanto na porta 443 (HTTPS).
* **Independência de Domínio do SO:** A estação Windows de trabalho não precisa estar ingressada no domínio `ENELINT` para alcançar o servidor nem para que o navegador autentique.

---

## 2. Evidências Extraídas do Firefox (Sessão Operacional Real)

A auditoria direta dos artefatos do perfil ativo do Firefox, sem registrar seu identificador local, revelou evidências determinantes:

1. **Histórico de Navegação (`places.sqlite`):**
   * Registros confirmam acesso bem-sucedido a `http://gtecprorio.enelint.global/sistemas/universalizacao/` com título de página renderizado: **"Universalização"**.
   * O acesso ocorre na porta **HTTP 80** (`http://`), e não em HTTPS.
2. **Gerenciador de Credenciais (`logins.json`):**
   * O Firefox possui credencial salva com `hostname: "http://gtecprorio.enelint.global"` e `httpRealm: "http://gtecprorio.enelint.global"`.
   * O campo `formSubmitURL` é **estritamente `None` / `null`**, indicando uma credencial de autenticação HTTP, não de formulário. Esse registro, isoladamente, não identifica NTLM nem a implementação usada pelo Firefox.
   * Metadados de uso não foram mantidos neste relatório sanitizado.
3. **Cookies (`cookies.sqlite`):**
   * Total de cookies persistentes em disco para `gtecprorio.enelint.global`: **0**.
   * **OBSERVADO:** nenhum cookie persistente identificado nesse banco. Isso não demonstra ausência de cookies em memória ou de sessão da aplicação.

---

## 3. Comparação Sistemática entre Clientes

| Item | Firefox (Navegador Real) | Python (`requests_ntlm`) | C# (`HttpClientHandler`) | PowerShell (`Invoke-WebRequest`) |
| :--- | :---: | :---: | :---: | :---: |
| **VPN Conectada** | Sim (GlobalProtect) | Sim (GlobalProtect) | Sim (GlobalProtect) | Sim (GlobalProtect) |
| **Porta / Protocolo** | HTTP / Porta 80 | HTTP / Porta 80 | HTTP / Porta 80 | HTTP / Porta 80 |
| **401 Inicial Recebido** | Sim | Sim | Sim | Sim |
| **`WWW-Authenticate`** | `Negotiate, NTLM` | `Negotiate, NTLM` | `Negotiate, NTLM` | `Negotiate, NTLM` |
| **Mecanismo Negociado** | NTLMv2 segundo descoberta anterior; backend não confirmado | NTLMv2 / SSPI segundo teste anterior | NTLMv2 / SSPI segundo teste anterior | NTLMv2 / SSPI segundo teste anterior |
| **Origem da Credencial** | Salva no `httpRealm` do Firefox | Arquivo `.env` | Arquivo `.env` | Arquivo `.env` |
| **Header `Authorization`** | Etapas individuais não confirmadas neste experimento | Type 3 segundo teste anterior | Type 3 segundo teste anterior | Type 3 segundo teste anterior |
| **Cookie de Autenticação** | Ausente no banco em disco investigado | Não reavaliado | Não reavaliado | Não reavaliado |
| **Resultado da Requisição** | **`HTTP 200 OK`** | **`HTTP 401.1` (`0xc000006d`)** | **`HTTP 401.1`** | **`HTTP 401.1`** |
| **Sessão Persistente** | Mecanismo de persistência não confirmado | N/A | N/A | N/A |

---

## 4. Diagnóstico Técnico da Divergência

* **OBSERVADO (descoberta anterior):** Firefox autentica e recebe `HTTP 200`; os clientes baseados em SSPI testados chegam a Type 3 e recebem `401.1`.
* **REPRODUZIDO (2026-10-05):** cliente NTLMv2 puro, sem SSPI, enviou Type 3 e também recebeu `HTTP 401`. Substatus IIS não registrado pelo POC.
* **REPRODUZIDO NA REPETIÇÃO (2026-10-05):** o mesmo backend puro, com nova entrada interativa e confirmação dupla de credenciais, recebeu `HTTP 200` após Type 3; indicador de título Universalização presente. A primeira execução permanece registrada, mas não representa o resultado mais recente.
* **HIPÓTESE:** diferença entre a implementação NTLMv2 usada pelo Firefox e as pilhas SSPI utilizadas pelos clientes automatizados.
* **NÃO CONFIRMADO:** backend efetivamente usado pelo Firefox; restrições supostamente injetadas por SSPI; causalidade de SPN, EPA ou channel binding; divergência ou expiração de credenciais.
* **CONCLUSÃO:** a causa da divergência permanece não estabelecida. Estar fora do domínio não demonstra que o SSPI imponha uma restrição rejeitada pelo IIS.
* As atribuições causais anteriores foram retiradas por excederem a evidência disponível. Nenhuma senha do Firefox ou do `.env` foi consultada neste experimento; `GOMNET_SENHA` não foi reutilizada.

---

## 5. Respostas às Questões Específicas do Mecanismo

1. **É NTLM?** **REPRODUZIDO NO SERVIDOR**. A sondagem de 2026-10-05 recebeu NTLM Type 2. O backend específico do Firefox não foi confirmado.
2. **É Negotiate/Kerberos?** **OBSERVADO:** servidor oferece `Negotiate, NTLM`. **NÃO CONFIRMADO:** Kerberos ou fallback obrigatório no Firefox. O POC seleciona NTLM explicitamente.
3. **O Firefox utiliza autenticação HTTP nativa?** **CONFIRMADO**. Registro com `httpRealm` e `formSubmitURL: null` no `logins.json`.
4. **Existe proxy?** **NÃO OBSERVADO**. Conexão TCP direta ao servidor HTTP/80 via túnel GlobalProtect, sem registrar os endereços da sessão.
5. **Existe cookie de sessão posterior?** **NÃO CONFIRMADO**. Ausência no banco persistente não demonstra ausência após o login.
6. **A autenticação é feita somente uma vez?** **NÃO CONFIRMADO**. Não houve medição do cache nem do ciclo de conexões do Firefox neste experimento.
7. **O servidor emite algum identificador de sessão depois do login?** **NÃO CONFIRMADO**. A repetição obteve `200`, mas cookies e identificadores de sessão não foram inspecionados nem persistidos.
8. **O Firefox envia `Authorization` em requisições subsequentes?** **NÃO CONFIRMADO**. Um Type 3 durante o handshake não comprova envio nas requisições seguintes.
9. **O prompt apresentado é realmente um prompt de autenticação HTTP ou formulário HTML?** **CONFIRMADO COMO PROMPT HTTP NATIVO**. Inexistência de formulário HTML.

---

## 6. Próximos Passos e Recomendações

1. **Manter a Universalização Desativada nesta Fase:**
   * Não criar provider, conector, scraping ou registros no `IntegrationRegistry`.
   * O **Consulta SOB** e o **P3 Executor** continuam operando com 100% de autoridade restrita aos canais homologados: **SharePoint corporativo** e **GOMNET**.
2. **Caminho Técnico para Automação Futura:**
   * **REPRODUZIDO:** a primeira execução pura terminou em `401`; a repetição com nova entrada e confirmação dupla terminou em `200` e confirmou o título Universalização. A viabilidade do cliente puro foi demonstrada nesta repetição.
   * **NÃO CONFIRMADO:** viabilidade de WebView2 contra esse servidor. O resultado do Firefox não comprova funcionamento de WebView2.
   * Recomenda-se considerar futuramente um provider NTLM puro, sem implementá-lo nesta etapa. A causa da divergência com os testes SSPI continua dependente de comparação controlada com a mesma credencial.

---

## 7. POC Isolado de NTLM Puro — Primeira Execução em 2026-10-05

**Arquivo:** `scratch/universalizacao_ntlm_poc.py`, em diretório já ignorado pelo Git. Nenhum código produtivo foi alterado e nenhuma dependência foi instalada.

### Fatos Observados

* Bibliotecas locais: `pyspnego 0.12.1`, `requests 2.32.5`, `requests-ntlm 1.3.0`; `ntlm-auth` não instalado.
* O POC força `spnego.NegotiateOptions.use_ntlm`, verifica a classe `spnego._ntlm.NTLMProxy` e fixa `LM_COMPAT_LEVEL=3` apenas em seu processo.
* O código instalado de `NTLMProxy` calcula a resposta NTLMv2 em software. O POC não usa SSPI, não importa `requests_ntlm` e não acessa credenciais do sistema.
* Transporte: `http.client`, HTTP/80 direto, sem proxy de ambiente, redirecionamento ou envio de cookies. O POC verifica identidade do socket ao enviar Type 1 e Type 3.

### Reprodução Experimental

* Teste local com credenciais fictícias: **PASS**, Type 1 / Type 2 sintético / Type 3 NTLMv2; tamanhos 40 / 62 / 262 bytes. Não autentica no IIS.
* Sondagem real sem credenciais: GET sem Authorization recebeu **401**, com esquemas `Negotiate, NTLM`.
* Envio real de Type 1: **40 bytes**, Authorization presente; resposta **401** com Type 2 de **254 bytes**, target/domain **ENELINT**, na mesma conexão.
* Sondagem inicial: Type 3 não enviado; seu `401` não era rejeição de uma credencial.
* Execução autenticada posterior: usuário e senha fornecidos diretamente no terminal com entrada oculta. Nenhuma variável GOMNET foi reutilizada; a igualdade da credencial com a armazenada no Firefox não foi inspecionada.
* Fluxo real: **GET → 401 → Type 1 → 401/Type 2 → Type 3 → 401**. Authorization ausente no GET inicial e presente no envio de Type 1 e Type 3.
* **Type 3 enviado: 602 bytes.** A validação estrutural da resposta NT confirmou NTLMv2 antes do envio. Resultado final **HTTP 401**, com esquemas `Negotiate, NTLM`; indicador de título Universalização **ausente**.
* A verificação de identidade do socket passou também no envio de Type 3. Não houve reconexão entre as etapas do handshake observadas pelo POC.
* O POC registrou somente o status HTTP `401`; **NÃO CONFIRMADO:** substatus `401.1` ou código interno do IIS nesta execução.

| Cliente | Type 1 | Type 2 | Type 3 | HTTP final | SSPI |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Firefox (descoberta anterior) | ? | ? | ? | 200 | Não confirmado |
| requests_ntlm (teste anterior) | Sim | Sim | Sim | 401.1 | Sim, conforme teste anterior |
| C# (teste anterior) | Sim | Sim | Sim | 401.1 | Sim, conforme teste anterior |
| PowerShell (teste anterior) | Sim | Sim | Sim | 401.1 | Sim, conforme teste anterior |
| POC puro (execução autenticada) | Sim | Sim | Sim, NTLMv2 | 401; substatus não registrado | Não |
| POC puro (repetição com confirmação dupla) | Sim | Sim | Sim, NTLMv2 | 200; título Universalização presente | Não |

### Hipótese e Conclusão

* **HIPÓTESE NÃO CONFIRMADA:** diferença de implementação NTLMv2 versus SSPI como explicação do sucesso do Firefox. A digitação das credenciais da primeira execução não foi validada; seu `401` não deve ser usado como evidência de rejeição do protocolo.
* **CONCLUSÃO HISTÓRICA:** a primeira execução chegou ao Type 3 e recebeu `401`. A repetição registrada na seção 8 comprovou posteriormente o acesso com NTLMv2 puro; a causa da divergência entre clientes continua não estabelecida.
* Nenhuma diferença criptográfica entre Firefox, SSPI e POC foi inferida. Não há evidência causal de SPN, EPA ou channel binding.

### Diagnóstico Restrito a Metadados Observáveis

* **REPRODUZIDO:** NTLMv2 no POC, target `ENELINT`, Type 1/2/3 e reutilização da mesma conexão até Type 3.
* **OBSERVADO NO CÓDIGO EXECUTADO:** transporte direto ao hostname alvo em HTTP/80, sem proxy de ambiente ou redirecionamento; backend puro selecionado explicitamente.
* **INFERIDO DO CÓDIGO INSTALADO:** o backend constrói o SPN a partir de serviço `http` e hostname alvo e usa target information do desafio. Isso não demonstra requisito do IIS nem divergência com o Firefox.
* **NÃO CONFIRMADO:** diferenças de flags/negotiate flags, target information e AV pairs entre os três clientes; SPN efetivamente negociado pelo Firefox; requisitos específicos de IIS/EPA; proxy ou cache no fluxo atual do Firefox.
* Não foram capturados nem persistidos tokens para comparação retrospectiva. Um próximo experimento deverá comparar somente metadados sanitizados dessas superfícies, sem pressupor uma causa e sem implementação produtiva.

### Segurança

Somente metadados permitidos são exibidos. Tokens e respostas criptográficas são processados apenas em memória, nunca impressos ou gravados. Não houve leitura de `.env`, extração de senha do Firefox, cópia de cookies, alteração de secrets ou reutilização de `GOMNET_SENHA`. A etapa autenticada aceita entrada oculta ou variáveis dedicadas, nunca senha na linha de comando.

---

## 8. Repetição com Confirmação Dupla — 2026-10-05

### Observado e Reproduzido

* O usuário solicitou repetir porque não tinha certeza da digitação anterior. O POC passou a pedir login e senha duas vezes, mantendo todas as entradas ocultas.
* Teste local com entradas fictícias: **PASS**; divergências foram rejeitadas antes de qualquer acesso à rede, sem exposição de entradas.
* Na repetição real houve duas divergências de login, corrigidas localmente. A autenticação só iniciou depois que as duas entradas de login e as duas de senha coincidiram.
* Backend: `pyspnego 0.12.1`, `spnego._ntlm.NTLMProxy`, `use_ntlm`, NTLMv2 em software, **sem SSPI**.
* Fluxo: **GET → 401 → Type 1 → 401/Type 2 → Type 3 → 200**.
* Authorization ausente no GET inicial e presente nos envios de Type 1 e Type 3. Esquemas recebidos: `Negotiate, NTLM` inicialmente; `NTLM` com Type 2; nenhum `WWW-Authenticate` na resposta final.
* Tamanhos dos tokens: **40 / 254 / 470 bytes**. Target/domain: **ENELINT**. NTLMv2 validado estruturalmente antes do envio de Type 3.
* Verificação de identidade do socket passou até o envio de Type 3. **HTTP final 200**, indicador de título Universalização **presente**.

### Hipótese e Conclusão

* **HIPÓTESE CONFIRMADA COM EVIDÊNCIA EXPERIMENTAL**, limitada à capacidade de um cliente NTLMv2 puro reproduzir o acesso HTTP 200 à Universalização nesta execução.
* **CONCLUSÃO:** o cliente puro funcionou. Os testes SSPI históricos receberam `401.1`; não foram repetidos com as credenciais desta execução, portanto a implementação não foi isolada como causa da diferença.
* **NÃO CONFIRMADO:** se houve erro de digitação na primeira execução; igualdade das credenciais entre execuções e clientes; motivo do Type 3 ter 470 bytes nesta repetição versus 602 anteriormente. Nenhuma diferença criptográfica foi inferida.
* Nenhuma senha, hash, token completo ou cookie foi exposto ou persistido. As divergências foram reportadas somente como mensagens genéricas. Não houve novas tentativas automáticas após o resultado.

### Arquitetura Futura — Somente Proposta

`UniversalizaçãoClientNTLM` → `UniversalizacaoProvider` → `IntegrationExecutor` → `SyncQueue`.

O provider deverá reutilizar o contrato P3 existente e o executor atual, sem duplicação. Nenhum provider foi criado, nenhuma integração foi iniciada e nenhum código produtivo OXCAD foi alterado.

---

## 9. Cliente Isolado e Reutilizável — 2026-10-05

### Implementação e Contratos

* `workspace/workspace_universalizacao_client.py`: configuração, resultado e diagnóstico imutáveis; somente `UniversalizacaoClient.get_home(username, password)`, operação `GET_HOME` em `/sistemas/universalizacao/`.
* Credenciais são argumentos da operação, não campos da configuração nem estado do cliente. O resultado contém código de erro, status HTTP, URL, duração, indicador de autenticação, mensagem fixa e diagnóstico sanitizado; não contém corpo, credenciais, cookies, headers brutos ou tokens.
* Códigos distintos para usuário/senha ausentes, rejeição de autenticação, timeout, conexão indisponível, HTTP inesperado, desafio inválido, resposta inválida, identidade da página divergente, conexão trocada, configuração inválida e erro interno.
* `provider_status` apenas oferece mapeamento futuro para `AUTH_REQUIRED`, `REMOTE_ERROR`, `TIMEOUT`, `UNAVAILABLE`, `IDENTITY_MISMATCH` e `SUCCESS`; não importa nem ativa contratos, registros, executor ou fila P3.

### Transporte e NTLM

* `http.client` foi escolhido para controlar explicitamente o socket durante o handshake. HTTP direto na porta **80**, timeout de I/O configurável (padrão 20 segundos), sem redirects, proxy de ambiente, cookies ou retries automáticos.
* A origem configurada não aceita HTTPS, outra porta, userinfo, query ou fragmento. O caminho da operação é fixo; não existe método genérico para consulta, download, upload ou alteração de registros.
* `pyspnego==0.12.1` foi declarado como dependência direta, já instalada no Python 3.12. Nenhum pacote foi instalado nem atualizado.
* Backend `NTLMProxy/use_ntlm`, sem SSPI. Níveis LM incompatíveis com NTLMv2 são rejeitados sem alterar o ambiente; Type 3 é validado como NTLMv2 antes do envio. Buffers do Type 2 e comprimentos/terminação de AV pairs são validados.
* O contexto é marcado como encapsulado para impedir os logs DEBUG de tokens do `pyspnego`; esse detalhe interno depende da versão fixada. Não há supressão global de logging. O transporte é mantido com debug desativado.
* Validação da página usa parser HTML e título Universalização, com normalização de acentos; HTTP 200 de outra página não é sucesso. Há limite de 2 MiB por resposta.

### Testes Offline Comprovados

* `tests/test_workspace_universalizacao_client.py`: **155 testes passaram**, exclusivamente com transporte mockado e credenciais fictícias. O backend NTLM real em software é usado nos fluxos positivos; sockets reais são proibidos nesses testes.
* Cobertura inclui geração Type 1/2/3, NTLMv2, 200/401, timeout e conexão em cada etapa, redirects/HTTP inesperados, desafio inválido, credencial ausente, resposta inválida, limite de tamanho, charset/título, perda do socket, proxy de ambiente ignorado e classificação de falhas.
* Logs com DEBUG ativo e serialização do resultado foram testados para ausência de senha, login, Authorization completo, tokens, cookies e texto de exceções hostis. Credenciais/contexto/conexão não ficam no estado do cliente.
* `scratch/universalizacao_ntlm_poc.py` foi preservado integralmente nesta etapa; seu autoteste continuou passando. O POC não é importado pelo cliente.

### Interface do Teste Externo

* `workspace/workspace_universalizacao_check.py`, executado explicitamente com `python -m workspace.workspace_universalizacao_check --external-integration`.
* Login visível em `Usuário:` e senha oculta em `Senha:`. Não há recuperação de credencial do Firefox ou reutilização de GOMNET. Opcionalmente `--env-credentials` usa somente `UNIVERSALIZACAO_NTLM_USERNAME` e `UNIVERSALIZACAO_NTLM_PASSWORD`, sem ler `.env`.
* A interface executa uma única chamada e imprime somente o resultado sanitizado. Não faz retries. Se não puder garantir entrada oculta, cancela sem autenticar.
* Verificação local da interface com credenciais fictícias passou: prompts corretos, uma chamada, sem segredo ou login na saída estruturada.
* **Teste real do novo cliente: executado uma única vez, com sucesso.** Login digitado visivelmente e senha por entrada oculta; nenhum valor real foi incluído no resultado ou nesta documentação.
* **REPRODUZIDO:** GET sem Authorization recebeu `401` e `Negotiate, NTLM`; Type 1 de **40 bytes** recebeu `401` com Type 2 de **254 bytes**; Type 3 NTLMv2 de **470 bytes** recebeu **HTTP 200**. Target `ENELINT` reconhecido e identidade do socket preservada durante o handshake.
* Resultado estruturado: `SUCCESS`, `authenticated=true`, `page_confirmed=true`, `sspi=false`, transporte `DIRECT`, sem redirects. Duração aproximada **6,406 segundos**. A confirmação da página veio do título Universalização, sem registrar o corpo recebido.
* Essa evidência valida o novo cliente independentemente do POC preservado. Não houve segunda tentativa externa automática.

### Limitações e Arquitetura Futura

Credenciais e tokens permanecem somente em memória durante a operação; Python não garante zerar strings imutáveis após liberar referências. HTTP/80 não oferece confidencialidade TLS e permanece igual ao fluxo comprovado da aplicação, sem alteração de HTTPS/443. Não há sessão ou cookies persistidos, scraping ou operações além da página inicial.

`UniversalizacaoClient` → `UniversalizacaoProvider` → `IntegrationExecutor` → `SyncQueue` é somente evolução conceitual. Um provider futuro poderá mapear o resultado tipado, reutilizando contrato e executor existentes. Nenhum provider, registro, executor, fila, worker, scheduler ou integração produtiva P3 foi criado ou alterado; SOB, mapa, GOMNET e OXCAD permanecem fora desta implementação.

---

## 10. Descoberta Funcional Read-Only — 2026-10-05

**Estado da primeira inspeção HTTP:** PARCIAL. Nessa inspeção a chamada de consulta OS/SOB não havia sido determinada. A evidência posterior do Firefox, registrada na seção 11, confirma agora a rota, o método e os nomes dos parâmetros; o conteúdo e a semântica da resposta ainda não estão fechados.

### Baseline e Escopo

Branch `dev`, HEAD `0b6ae135a03a945cab9201e9618249479e3f72af`, 10 commits à frente de `origin/dev`. Alterações anteriores em documentação, preferências ambientais e dependências, e arquivos do cliente/testes ainda não rastreados, foram preservados. Não houve commit ou push.

Os únicos acréscimos técnicos desta descoberta são `scratch/universalizacao_functional_discovery.py` e `scratch/test_universalizacao_functional_discovery.py`, em diretório já ignorado pelo Git. O helper deriva do cliente existente e reutiliza seu handshake, sem recriar o POC ou alterar o cliente produtivo. HTML/JS são processados apenas em memória; arquivos `scratch/universalizacao_metadata_*.jsonl` contêm somente metadados sanitizados, sem valores de formulário, parâmetros operacionais, usuários, senhas, tokens, cookies, headers sensíveis ou HTML bruto.

**Mudança de autorização pelo usuário:** o helper pode ler somente para esta descoberta as chaves `UNIVERSA_ID` e `UNIVERSA_SENHA` do `.env` existente. Usa `python-dotenv 1.2.2`, já instalado, com interpolação desativada; não exporta o arquivo ao ambiente, não faz fallback para GOMNET, não altera `.env` e não registra valores. Essa opção não foi incorporada ao cliente ou ao check produtivo.

### Evidência Externa Comprovada

* Com as chaves dedicadas autorizadas, a página inicial voltou a receber **HTTP 200** após **401 → Type 1 → Type 2 → Type 3 → 200**, na mesma conexão, usando NTLMv2 puro sem SSPI.
* A página inicial é um frameset HTML de **573 bytes** com referências `principal.asp` e `controle.asp`. Não contém formulário, controles, scripts ou campos de consulta na resposta observada.
* `principal.asp`: GET sem parâmetros recebeu **302**, resposta HTML de **135 bytes**, `Location` para `inicio_web.asp`, sem parâmetros. O redirect não foi seguido automaticamente.
* `controle.asp`: GET sem parâmetros recebeu **200**, `text/html`, **3718 bytes**; contém scripts inline, função `val_login` e referências a controles de `parent.mainFrame.document.frm1`. Não contém formulário HTML próprio, links externos de script ou chamadas AJAX identificadas pelos padrões inspecionados.
* `inicio_web.asp`: GET explícito ao destino observado recebeu **200**, HTML de **85 bytes**, com navegação JavaScript referenciando `inicio.asp`. O JavaScript não foi executado.
* `inicio.asp`: GET explícito à referência observada recebeu **200**, HTML de **573 bytes**, novamente o mesmo conjunto de frames. Esse percurso não apresentou uma tela de consulta.
* A primeira inspeção interativa perdeu a conexão durante a leitura posterior de um frame. A mensagem do helper havia confundido essa falha com o resultado do handshake; o helper foi corrigido e testado para separar falha pós-autenticação do **200 já recebido**. Isso não é evidência de rejeição de NTLM ou de credencial.
* Não foram capturados nem reaproveitados cookies para contornar o percurso. A causa do retorno ao frameset não foi estabelecida.

### Endpoints Observados

Todos os caminhos abaixo têm prefixo `/sistemas/universalizacao/` e autenticação HTTP NTLM no transporte. A confirmação de um GET não prova ausência de efeitos internos no servidor nem estabelece uma API de negócio.

| Rota | Método/parâmetros enviados | Resposta observada | Finalidade evidenciada | Classificação/confiança |
| :--- | :--- | :--- | :--- | :--- |
| `/sistemas/universalizacao/` | GET; nenhum | 200; HTML frameset | Entrada da aplicação | CONFIRMADO como leitura de navegação; não é consulta OS/SOB |
| `principal.asp` | GET; nenhum | 302 para `inicio_web.asp` | Frame principal referenciado pela entrada | CONFIRMADO acesso/redirect; finalidade de negócio NÃO CONFIRMADA |
| `controle.asp` | GET; nenhum | 200; HTML/scripts inline | Referências de controle sobre formulário de outro frame | CONFIRMADO acesso e referências DOM; navegação de leitura PROVÁVEL |
| `inicio_web.asp` | GET; nenhum | 200; HTML/JS | Referência de navegação para `inicio.asp` | CONFIRMADO acesso/referência; não é consulta comprovada |
| `inicio.asp` | GET; nenhum | 200; HTML frameset | Retorno ao conjunto inicial de frames | CONFIRMADO acesso; não é consulta comprovada |

### Campos e Mecanismos Observados

**CONFIRMADO no JavaScript de `controle.asp`:** referências a `frm1.numero_ordem_projeto`, `frm1.ref_projeto_interno`, `frm1.numero_cliente`, `frm1.nome`, `frm1.status_ordem`, `frm1.status_projeto`, `frm1.tipo_servico`, `frm1.tipo_projeto`, `frm1.area_tecnica`, `frm1.grupo`, `frm1.municipio`, `frm1.bairro`, `frm1.logradouro`, `frm1.notas_obs`, `frm1.notas_referencia`, componentes de data e outros controles técnicos.

Esses são **nomes de controles referenciados**, não parâmetros HTTP comprovados, colunas de resposta ou campos canônicos de identidade. Não houve observação do formulário `frm1` renderizado, de sua action, método, codificação ou submissão. `numero_ordem_projeto` é candidato de identidade de ordem, mas sua correspondência com OS/SOB, unicidade e formato são **NÃO CONFIRMADOS**. `numero_cliente` não foi promovido a identidade de OS/SOB.

* **CONFIRMADO:** navegação por frames, redirect HTTP e referência de navegação JS. As respostas lidas são HTML.
* **PROVÁVEL:** páginas ASP clássicas, pelos caminhos `.asp` e referências DOM legadas; não houve acesso ao código servidor.
* **NÃO CONFIRMADO para consulta:** GET/POST, action, parâmetros, ASP.NET postback, formulário clássico, AJAX/JSON/SOAP, formato do resultado, paginação, filtros, pesquisa incremental e comportamento de inexistentes/múltiplos/erros. Ausência desses mecanismos nos documentos inspecionados não demonstra ausência no restante da aplicação.

### Ações Potencialmente Mutáveis Bloqueadas

O JavaScript referencia `frm1.bt_gravar` e `frm1.bt_excluir`: controles de escrita/exclusão **PROVÁVEIS**, não acionados. Seus endpoints e métodos não foram observados. Nenhum formulário foi submetido, nenhum script executado, nenhuma chamada POST/PUT/PATCH/DELETE foi enviada e nenhuma operação de inclusão, alteração, exclusão, aprovação ou processamento foi realizada.

O helper bloqueia referências externas, query strings, caminhos com identificadores operacionais e nomes indicativos de mutação. Não segue redirects automaticamente; somente GETs explícitos às referências realmente observadas foram utilizados. Isso é uma barreira conservadora de inspeção, não comprovação universal de que qualquer GET da aplicação seja seguro.

### Limite e Evidência Necessária para Continuar

**Fechado:** leitura das chaves dedicadas sem digitação ou exposição; autenticação NTLMv2 pura funcional; estrutura inicial e cinco rotas de navegação; referências DOM relevantes; bloqueio dos controles de escrita.

**Não determinado:** qual chamada consulta uma OS/SOB e qual resposta retorna. Não foi inventado identificador, parâmetro ou endpoint; não houve consulta válida/inexistente, listagem de ordens ou extração de dados operacionais.

Para continuar, é necessário observar no **Firefox já operacional**, durante uma consulta exclusivamente de leitura: rota relativa, método HTTP, nomes dos parâmetros e content-type da requisição; sequência de chamadas; status, content-type e estrutura da resposta; nomes dos campos de identidade OS/SOB. Os valores dos identificadores podem ficar apenas na sessão do usuário; não enviar headers, cookies, Authorization, tokens ou conteúdo operacional ao relatório. Não exportar HAR bruto. Também é necessário estabelecer o caminho de navegação normal que apresenta `frm1`, em vez do retorno ao frameset observado no cliente sem cookies.

### Contrato Futuro do Provider — Ainda Condicionado à Evidência

Somente intenção conceitual: operação de leitura de ordem por identificador validado, retornando identidade canônica conferida, dados mínimos autorizados, ausência/ambiguidade e erros tipados. Assinatura definitiva, identificador aceito, mapeamento OS/SOB, campos obrigatórios, cardinalidade e paginação devem permanecer em aberto até observar a chamada real. Não confundir o `get_home` já validado com uma implementação de consulta.

Arquitetura permanece `UniversalizacaoClient` → `UniversalizacaoProvider` → `IntegrationExecutor` → `SyncQueue`, sem qualquer ativação nesta etapa.

### Validação

**169 testes específicos passaram:** 155 testes existentes do cliente intacto e 14 casos do helper em scratch, com valores fictícios e sem rede nos testes. Cobrem sanitização HTML/JS/rotas, relatório sem valores operacionais, credenciais dedicadas sem fallback/interpolação, confirmação local, redirects sem seguimento automático e isolamento de falhas pós-autenticação. Nenhuma dependência foi instalada. Não houve alteração .NET nem execução rotineira da suíte completa OXCAD.

---

## 11. Consulta Real Observada no Firefox — 2026-10-05

**Fonte:** imagens do Inspector e da aba Rede do Firefox operacional, mais exportação cURL fornecida pelo usuário. A requisição não foi reproduzida pelo agente, o cURL não foi executado e nenhum header sensível foi copiado para arquivos ou logs. Valores de SOB e cookies foram omitidos desta documentação.

### Regras Funcionais Informadas pelo Usuário

* **Número Ordem de Projeto = SOB.** Essa equivalência é a definição funcional do usuário, não uma conclusão extraída de um HTTP 200.
* **Projetos Grupo:** somente `A` ou `B`. O grupo é um parâmetro separado da SOB; não se deve deduzi-lo do prefixo do identificador.
* **Escopo autorizado:** somente a tela **Dados Principais**. Consultas dos Projetos, Documentação e outras abas não fazem parte do uso informado e não devem ser exploradas nesta etapa.

### Evidência DOM Confirmada nas Imagens

* Controle de grupo: `<select name="grupo" onchange="javascript:valida_grupo(this.value)">`.
* Controle de SOB: `<input type="text" name="numero_ordem_projeto" onblur="buscar_num_proj(this,grupo.value);" onkeyup="trocar_campo(this);">`.
* Navegação Dados Principais: handler `pagina_go('principal.asp', 'Dados Principais')`.
* **CONFIRMADO:** nomes dos controles e eventos mostrados. **NÃO CONFIRMADO:** implementação interna das funções, ordem mínima de inicialização e efeitos de `trocar_campo`/`valida_grupo` além do mostrado no DOM.

### Contrato de Requisição Confirmado

```text
GET /sistemas/universalizacao/controle.asp
query: num_ordem_proj=<SOB_MASCARADA>&grupo=<A_OU_B>
Referer relativo observado: /sistemas/universalizacao/principal.asp
```

| Nome HTTP | Origem funcional | Tipo/domínio | Evidência/confiança |
| :--- | :--- | :--- | :--- |
| `num_ordem_proj` | Campo DOM `numero_ordem_projeto`, definido como SOB pelo usuário | String; formato/validação geral ainda não estabelecidos | CONFIRMADO na URL da consulta real |
| `grupo` | Controle DOM `grupo` | Enum funcional `A`/`B`; somente uma alternativa aparece na captura | CONFIRMADO como parâmetro; domínio A/B informado pelo usuário |

Na consulta capturada ambos são parâmetros da query string de um **GET**, não campos POST. Não foi observado corpo de requisição, AJAX/JSON/SOAP ou ASP.NET postback nessa chamada. Isso não define o comportamento de outras ações da aplicação.

### Resposta e Sequência Observadas

* A consulta parametrizada a `controle.asp` recebeu **HTTP 200**, tipo **html** na aba Rede, como **subdocument**. Tamanho de resposta reportado: aproximadamente **11,25 kB**. A captura não mostra o valor literal do header `Content-Type`; ele permanece por confirmar.
* A captura mostra primeiro a consulta parametrizada, depois `GET principal.asp` com **200**, tipo **html**, aproximadamente **34,95 kB**, nova consulta parametrizada, carregamento de `funcoes.js` e outras repetições da mesma consulta. Nas duas últimas, o iniciador mostrado é `principal.asp:56`.
* A lista inclui navegação inicial e recursos estáticos; ela não é uma captura isolada da menor sequência possível. Portanto, não se concluiu quantas chamadas são necessárias, se todas as repetições decorrem de um único evento ou qual é a sequência mínima de bootstrap.
* **CONFIRMADO:** pesquisa via GET de subdocument/frame e retorno HTML indicado pelo navegador. O corpo fornecido posteriormente, documentado na seção 12, confirma scripts de preenchimento do formulário principal e nomes dos campos. Permanecem abertas a sequência mínima e a semântica dos resultados negativos.
* O `404` visível pertence a um recurso de ícone, não à consulta OS/SOB; não é evidência de SOB inexistente.

### Segurança e Read-Only

O usuário apresentou essa captura como consulta normal na tela Dados Principais. A chamada observada é GET, sem parâmetro de operação de gravação/exclusão visível; nenhuma ação mutável foi executada pelo agente. Isso sustenta sua classificação como **consulta READ-ONLY no fluxo informado**, mas GET isoladamente não prova ausência de efeitos internos no servidor. Os controles `bt_gravar` e `bt_excluir` permanecem bloqueados; nenhum endpoint de escrita foi exercitado.

A exportação recebida inclui um header de cookie. Nenhum nome ou valor de cookie foi transcrito, armazenado ou reutilizado pelo agente. Sua presença não comprova que ele seja necessário à consulta nem que explique a diferença com a navegação anterior do helper. Não há conclusão nova sobre SSPI, SPN, EPA ou channel binding.

### Identidade e Limitações Restantes

**Fechado no lado da requisição:** `controle.asp` → GET → `num_ordem_proj` + `grupo` → HTTP 200, tipo HTML/subdocument, no fluxo de Dados Principais.

**Lacunas registradas antes do recebimento do corpo (atualizadas pela seção 12):**

* Header `Content-Type` literal, estrutura HTML/JS e nomes dos campos preenchidos/retornados, sem seus valores.
* Correspondência entre a SOB consultada e a identidade efetivamente devolvida, inclusive grupo, sem assumir que `200` comprova correspondência ou existência.
* Indicadores de sucesso, inexistência, erro e ambiguidade; comportamento de múltiplos resultados, filtros ou paginação.
* Fluxo mínimo entre frames e função `buscar_num_proj`, incluindo requisitos reais de sessão, sem copiar cookies ou presumir a causa do percurso anterior.

O corpo foi posteriormente fornecido e analisado sem persistir seu conteúdo integral. O header literal `Content-Type` e o comportamento negativo ainda não foram observados. Não exportar HAR, headers completos, respostas integrais ou “Copiar como cURL” com cookies. Para futuras evidências, fornecer somente metadados sanitizados.

### Provider Futuro — Sem Implementação

O futuro contrato de entrada pode ser descrito conceitualmente por **SOB + grupo A/B**, com separação explícita entre nome DOM e nome HTTP. O parsing, os campos de saída, a verificação de identidade e os estados de ausência/erro continuam dependentes da evidência de resposta. Nenhum Provider, Executor, Registry, SyncQueue, cliente produtivo ou UI foi alterado para incorporar a consulta nesta etapa.

---

## 12. Estrutura da Resposta de Consulta — 2026-10-05

**Fonte:** corpo de resposta fornecido pelo usuário, associado à consulta da seção 11. Somente estrutura, nomes de campos e tipos foram transcritos. Não foram persistidos dados pessoais, identificadores operacionais, observações livres, SQL bruto, informações de conexão ou valores de sessão. Nenhum SQL ou JavaScript recebido foi executado pelo agente; nenhuma consulta externa adicional foi feita.

### Contrato Positivo Observado

```text
GET /sistemas/universalizacao/controle.asp
query: num_ordem_proj=<SOB_MASCARADA>&grupo=<A_OU_B>
status observado: 200
corpo: texto/HTML com scripts JavaScript inline
destino DOM: parent.mainFrame.document.frm1
identidade retornada: numero_ordem_projeto + grupo
```

**CONFIRMADO:** não é um DTO JSON neste exemplo. O corpo mistura texto/HTML e scripts que atribuem literais às propriedades `.value` de controles de outro frame. O bloco principal é condicionado à existência de `parent.mainFrame.document.frm1`. Para o caminho feliz dessa consulta, rota, método, nomes de parâmetros, estrutura de retorno e pontos de identidade estão evidenciados. O valor literal do header `Content-Type` continua não observado.

### Identidade e Mapeamento

| Entrada HTTP | Campo retornado | Significado | Observação |
| :--- | :--- | :--- | :--- |
| `num_ordem_proj` | `numero_ordem_projeto` | SOB, pela definição funcional do usuário | No exemplo fornecido, a atribuição coincide com a SOB consultada; valor omitido |
| `grupo` | `grupo` e `select_grupo` | Grupo funcional A/B | No exemplo fornecido, as duas atribuições coincidem com o grupo da requisição |

**Requisito conceitual para o futuro parser:** conferir ambas as dimensões retornadas contra a requisição, sem inferir grupo pelo prefixo da SOB. Essa comparação é necessária, mas não suficiente para classificar existência: o material recebido não demonstra se esses campos poderiam ser preenchidos apenas por eco dos parâmetros em um resultado negativo. `numero_cliente` e `ref_projeto_interno` não substituem a identidade SOB/grupo.

### Campos Retornados no Exemplo

Todos os campos abaixo são nomes efetivamente observados em atribuições JavaScript, não nomes inventados a partir de rótulos. Os valores são strings de controles DOM, inclusive números, componentes de data e indicadores de falha.

| Categoria | Campos observados |
| :--- | :--- |
| Identidade | `numero_ordem_projeto`, `grupo`, `select_grupo` |
| Cadastro | `nome`, `numero_cliente`, `logradouro`, `bairro`, `municipio` |
| Projeto | `area_tecnica`, `enquad_tec`, `tipo_servico`, `ref_projeto_interno`, `tipo_projeto`, `status_projeto` |
| Observações | `notas_obs`, `notas_referencia` |
| Estado da ordem | `etapa_ordem_proj`, `estado_ordem_proj`, `status_ordem` |
| Primeira solicitação | `dia_pri_solic`, `mes_pri_solic`, `ano_pri_solic` |
| Abertura do projeto | `dia_abertura_projeto`, `mes_abertura_projeto`, `ano_abertura_projeto` |
| Despacho técnico | `dia_desp_tecnica`, `mes_desp_tecnica`, `ano_desp_tecnica` |
| Data/hora de status | `dia_status`, `mes_status`, `ano_status`, `hr_status`, `min_status` |
| Finalização da ordem | `dia_finalizacao_ordem`, `mes_finalizacao_ordem`, `ano_finalizacao_ordem` |
| Seletores auxiliares | `select_status_proj`, `select_area_tec` |
| Indicadores de falha | `falha_1`, `falha_2`, `falha_3`, `falha_4`, `falha_6`, `falha_7`, `falha_8` |

Há atribuições vazias no exemplo, incluindo alguns campos de projeto e datas. Portanto, não se deve exigir todos os campos preenchidos para aceitar uma resposta, nem confundir string vazia, string numérica e booleano. Não foi inferida uma propriedade `falha_5`, ausente no bloco fornecido.

Também foi observada substituição de HTML em `parent.mainFrame.document.all['td_select_status_proj']`, criando um `<select name='select_num_ordem_proj'>`. Essa alteração é estrutura auxiliar de UI, não coleção de resultados ou evidência de paginação.

### Sequência Funcional e Read-Only

As imagens anteriores mostram `buscar_num_proj(this,grupo.value)` no `onblur` do campo SOB. A rede fornecida mostra GET parametrizado de `controle.asp` como subdocument. O corpo agora confirma o preenchimento de `mainFrame.frm1` por script inline. A sequência funcional evidenciada é:

`Dados Principais → evento de busca → GET controle.asp com SOB/grupo → 200/HTML+JS → atribuições no formulário principal`.

Não foi estabelecida a sequência mínima de bootstrap, execução entre frames ou quantidade necessária de chamadas repetidas. A presença de atribuições DOM não significa escrita remota. No segundo bloco, o retorno habilita os controles `bt_gravar` e `bt_excluir` quando existem; habilitá-los não demonstra acionamento ou persistência. Ambos continuam intocados, e o conteúdo da resposta não deve ser executado pelo futuro cliente para evitar efeitos de interface ou scripts não autorizados.

O trecho fornecido exibe diagnósticos com consultas de leitura, mas isso não prova todos os efeitos internos do servidor. Classificação continua **consulta READ-ONLY no fluxo funcional informado**, com ação remota de escrita não observada e nenhuma escrita feita pelo agente. Não houve SQL direto, POST, alteração de registros ou integração P3.

### Diagnósticos Sensíveis na Resposta

**OBSERVADO:** a resposta mistura dados de cadastro/contato, observações livres e diagnósticos de SQL, conexão e sessão. Esse conteúdo deve ser tratado como sensível; não constitui uma API SQL, não deve ser utilizado como contrato estável e não pode ser transcrito em logs, exceções, fixtures ou documentos.

**Recomendação de segurança:** minimizar os campos efetivamente consumidos e manter somente diagnósticos estáticos sanitizados. A remoção de informações de depuração pelo responsável pelo sistema é recomendável, sem qualquer tentativa de alteração dessa aplicação nesta etapa. Para futuras evidências, enviar apenas nomes/estrutura, nunca o corpo integral.

### Limitações e Prontidão para o Próximo Nível

**Fechado para o exemplo positivo:** rota GET, query SOB/grupo, resposta HTML com atribuições literais em outro frame, nomes dos campos e correspondência de SOB/grupo no exemplo recebido.

**Ainda NÃO CONFIRMADO:**

* Resposta de SOB inexistente, erro, ambiguidade ou múltiplos resultados; não há classificador negativo comprovado.
* Comportamento do outro grupo permitido, filtros, paginação e pesquisa incremental.
* Charset e header `Content-Type` literais da consulta; o trecho não permite validar bytes/encoding original.
* Requisitos mínimos de sessão, cookies e navegação; sua necessidade não decorre de texto de depuração presente no corpo.
* Repetição da consulta pelo cliente NTLM puro, sem usar cookies do Firefox: não realizada nesta etapa de observação.

Um contrato mínimo futuro pode receber **SOB + grupo** e retornar identidade conferida, dados de Dados Principais explicitamente autorizados e resultado tipado. Os campos acima são inventário observado, não autorização para coletar todo o conteúdo. O futuro parsing deve extrair somente atribuições literais reconhecidas e permitidas, sem `eval`, execução de scripts, DOM real ou SQL. Não há implementação de parser/Provider/Executor nesta etapa.

**Critério de progresso:** o contrato estrutural do caminho feliz está documentado; isso não equivale a um Provider pronto para tratar todos os estados operacionais. Nenhum cliente produtivo, Provider, Executor, Registry, SyncQueue ou UI foi alterado.

---

## 13. Primeiro Provider Read-Only — 2026-10-05

**Estado:** implementado e validado localmente o caminho `UniversalizacaoClient` → `UniversalizacaoProvider`. As limitações de evidência dos estados negativos e da sessão remota permanecem explícitas. Não houve consulta externa do novo Provider nesta execução.

### Identidade Obrigatória e Contrato

* Operação concreta: `consultar_os_sob(sob, grupo, *, context=None, username=None, password=None)`.
* **Identidade mínima = `(grupo, SOB)`**. Grupo obrigatório, exclusivamente `A` ou `B`, sem normalização de minúsculas, padrão, fallback ou inferência pelo prefixo da SOB. A ausência do argumento na operação concreta é rejeitada localmente.
* SOB obrigatória. Validação sintática conservadora: identificador de 1 a 128 caracteres alfanuméricos, `_` ou `-`, sem URL, query string, espaços ou controles. Essa é uma restrição local de segurança, não descoberta de um formato universal da SOB.
* Validação de ambos acontece antes de obter credenciais e antes de qualquer HTTP. Contexto fornecido deve preservar a SOB soberana; correlation/execution IDs são mantidos no resultado, sem fabricar contexto DWG.
* O Provider implementa `IBusinessSystemProvider` e `IWorkOrderProvider`, herdando `IIntegrationProvider`. Os métodos genéricos mantêm seus argumentos originais e permitem `grupo` explícito por keyword; sem ele devolvem `INVALID_REQUEST`, sem consultar. Eles não oferecem consulta válida somente por SOB.
* O contrato P3 mantém `IntegrationResult` e `IntegrationStatus` existentes. `SUCCEEDED` é o outcome funcional de `IntegrationStatus.SUCCESS`; os demais outcomes ficam em `data.outcome` e `error_code`, sem modificar os estados compartilhados.

### Separação Client/Provider

* `workspace/workspace_universalizacao_client.py`: adicionada `read_order(sob, grupo, username, password, *, consume=...)`, exclusivamente GET ao endpoint confirmado. O mesmo fluxo NTLMv2 em software atende `get_home` e `read_order`; não existe segunda implementação de autenticação, transporte ou sessão.
* A query é construída pelo Client somente com `num_ordem_proj` e `grupo`. A origem da operação de ordem é restrita ao servidor confirmado. O consumidor não fornece URL, método, rota ou parâmetros arbitrários. O Referer relativo observado é usado; não há cookies, redirects automáticos, retries, cache ou chamadas de escrita.
* O corpo é decodificado e consumido por callback transitório em memória. Não faz parte do resultado estruturado do Client, não fica armazenado no Client e não é logado. O parser do Provider recebe o texto sem executar scripts.
* O Provider recebe credenciais explicitamente por operação ou por supplier fornecido pelo chamador. Não lê `.env`, não altera nomes de variáveis, não guarda usuário/senha e não tem fallback para GOMNET. O check manual anterior mantém seu mecanismo de credenciais.

### Parser Controlado e Dados Mínimos

* `workspace/workspace_universalizacao_provider.py`: parser HTML para scripts inline de tipo JavaScript, seguido por tokenização limitada de texto. Comentários e strings são reconhecidos como tokens; texto de diagnóstico fora dos scripts não é fonte de campos.
* Somente atribuições literais a `parent.mainFrame.document.frm1.<campo>.value` são reconhecidas. Expressões, concatenação, chamadas como RHS, literais inválidos, escapes não suportados, campos oversized, script/comentário truncados e atribuições conflitantes são rejeitados.
* Lista permitida: `numero_ordem_projeto`, `grupo`, `select_grupo`, `etapa_ordem_proj`, `estado_ordem_proj`, `status_ordem`. Não são extraídos nome, endereço, cliente, contatos, observações livres, SQL ou dados de conexão/sessão.
* Sucesso exige transporte autenticado com HTTP 200, estrutura válida, SOB e grupo retornados iguais aos solicitados, coerência de `select_grupo` se presente e ao menos um campo de estado da ordem não vazio. Eco de identidade sem estado não é sucesso.
* O vocabulário dos estados não foi fechado a partir de um único exemplo: os estados continuam strings. Campos desconhecidos são ignorados, não inferidos ou copiados indiscriminadamente.
* Não há `eval`, engine JavaScript, navegador, subprocesso de interpretação, execução DOM ou SQL. Habilitações de `bt_gravar`/`bt_excluir` no texto recebido são ignoradas e nunca executadas.
* O resultado preserva identidade solicitada/retornada, grupo, estados mínimos, status HTTP, indicador de autenticação e IDs de contexto quando disponíveis. Logs contêm somente outcome, operação, etapa e status HTTP, sem valores operacionais ou texto de exceções.

### Outcomes e Evidência

| Outcome do Provider | Status P3 | Regra implementada |
| :--- | :--- | :--- |
| `SUCCEEDED` | `SUCCESS` | Identidade composta e estado mínimo coerentes em resposta autenticada 200 |
| `INVALID_REQUEST` | `INVALID_REQUEST` | SOB/grupo inválidos ou não fornecidos, antes da rede |
| `IDENTITY_MISMATCH` | `IDENTITY_MISMATCH` | Divergência da SOB/grupo retornados ou do contexto soberano |
| `INVALID_RESPONSE` | `REMOTE_ERROR` | Desafio/resposta/estrutura inválidos ou identidade/estado ausentes |
| `AUTHENTICATION_REQUIRED` | `AUTH_REQUIRED` | Credencial ausente, HTTP 401/403 ou rejeição NTLM |
| `UNAVAILABLE` | `UNAVAILABLE` | Falha de conexão/configuração ou perda da conexão autenticada |
| `TIMEOUT` | `TIMEOUT` | Timeout do transporte |
| `ERROR` | `REMOTE_ERROR` | Falha não classificada, mensagem sempre sanitizada |
| `NOT_FOUND` | Reservado; futuro `REMOTE_ERROR` com código específico | Ainda sem classificador, porque não há resposta real negativa comprovada |

**CONFIRMADO por testes offline:** geração NTLMv2 pura e parsing juntos para A/B, validação pré-HTTP, identidade compatível/incompatível, callbacks sem persistência, erros HTTP/transporte, sanitização e compatibilidade contratual.

**AINDA NÃO CONFIRMADO externamente:** consulta do novo Provider no servidor real; resposta de ausência/ambiguidade/múltiplos; requisitos de sessão/cookies, charset/content-type literal e comportamento em outros exemplos reais. HTML vazio, ausência de identidade, HTTP 404 ou HTTP 200 isolado não são convertidos automaticamente em `NOT_FOUND`.

### Registry e Limites de Arquitetura

* Adicionado somente o valor declarativo `AuthenticationScheme.NTLM` ao contrato compartilhado, sem alteração de assinaturas/status existentes.
* O Provider declara somente `WORK_ORDER_READ` e `BUSINESS_DATA_READ`. Disponibilidade inicial é `UNKNOWN`; `check_availability` é local e não chama rede ou supplier.
* Registro manual em `IntegrationRegistry` é compatível e foi testado sem rede. **Não houve registro automático ou alteração de `create_default`**; a aplicação não ativa este Provider por importação ou inicialização.
* Executor, SyncQueue, UI, GOMNET, SOB existente e mapa não foram alterados. Nenhum scheduler, worker, daemon, sincronização ou workflow foi criado. Não há operação Gravar/Excluir/Alterar/Aprovar/Processar.

### Testes e Auditoria

**326 testes selecionados passaram:** 63 do Provider, 184 do Client e 79 de contratos/provedores/Executor existentes e helper de descoberta relacionados. Os 155 casos originais do Client permanecem passando. Fixtures novas são estritamente sintéticas, com a estrutura observada, sem nomes, SOBs ou contatos reais.

O teste de pipeline completo usa backend NTLMv2 real em software, transporte HTTP mockado e parser real do Provider. Testes adicionais proíbem eval/exec, subprocessos, navegador e escrita de arquivos durante a operação e verificam ausência de HTML bruto, dados pessoais, SQL, credenciais e tokens em resultados/logs.

Também foi comprovada a precedência dos erros tipados do Client: timeout, falha de conexão ou desafio inválido depois do `401` inicial não são classificados como rejeição de autenticação apenas pelo último status HTTP. O mapeamento local `INVALID_REQUEST` do Client e do Provider é coerente, sem chamada HTTP.

Não houve instalação de pacote ou mudança de dependências nesta etapa, build C#, suíte completa OXCAD, commit ou push. A única consulta externa permitida é opcional e não foi realizada; não se declara validação de sessão real do Provider com base nos mocks.

---

## 14. Homologação Real Controlada do Provider — 2026-10-05

**Resultado:** uma única operação real `UniversalizacaoProvider.consultar_os_sob(sob, grupo)` concluiu com **`SUCCEEDED`**, mapeado para `IntegrationStatus.SUCCESS`, após autenticação NTLMv2 pura e parsing da resposta real. Essa evidência é posterior à validação offline da seção 13; não houve segunda consulta ou fallback.

### Entrada Legítima e Identidade Composta

* Grupo escolhido explicitamente: **B**. Não houve tentativa com A, inferência pelo prefixo da SOB ou grupo padrão.
* SOB de teste: **`A0******38`**, a mesma ordem legítima anteriormente consultada pelo usuário no Firefox. O valor integral não é registrado nesta documentação.
* `requested_grupo` e `requested_sob` permaneceram iguais à entrada fornecida.
* `grupo` retornado **igual** ao grupo solicitado; `numero_ordem_projeto` retornado **igual** à SOB solicitada. `select_grupo` também foi extraído e sua coerência foi verificada pelo Provider.

### Caminho Executado e Evidência Sanitizada

`Provider → Client.read_order → NTLMv2/use_ntlm → GET controle.asp → HTML/JS real → parser → identidade e estados mínimos → SUCCEEDED`.

* Rota única: `/sistemas/universalizacao/controle.asp`, método **GET**, somente parâmetros `num_ordem_proj` e `grupo` construídos pelo Client.
* Uma operação funcional, com três requisições HTTP do handshake na mesma rota: **401 → 401 → 200**. As etapas Type 1/Type 2/Type 3 foram executadas pelo Client existente; nenhum token foi exposto ou persistido.
* Status final **HTTP 200**, `authenticated=true`, `ntlm_version=NTLMv2`, `sspi=false`, `connection_reused=true`.
* Media type observado nas respostas HTTP: **`text/html`**. Charset e header completo não foram registrados.
* Parser real retornou estrutura válida e somente os campos permitidos: `numero_ordem_projeto`, `grupo`, `select_grupo`, `etapa_ordem_proj`, `estado_ordem_proj`, `status_ordem`.
* O sucesso não foi baseado apenas em HTTP 200 ou eco de SOB: o Provider confirmou ambas as identidades e extraiu estado mínimo não vazio.

### Estados Mínimos Extraídos

| Campo | Valor mínimo necessário à homologação |
| :--- | :--- |
| `etapa_ordem_proj` | `ESTUDO DE REDE` |
| `estado_ordem_proj` | `ORDEM EM EXECUÇÃO` |
| `status_ordem` | `NO PRAZO` |

Não foram registrados nome, cadastro/contato do cliente, endereço, observações, SQL, informações de conexão ou valores de sessão.

### Controles de Segurança

* Credenciais lidas exclusivamente das chaves dedicadas já autorizadas `UNIVERSA_ID`/`UNIVERSA_SENHA`, em memória, sem interpolação, fallback GOMNET ou modificação do `.env`.
* O wrapper transitório de auditoria bloqueava método diferente de GET, corpo de requisição, rota diferente e query que divergisse do par fornecido. As três requisições observadas respeitaram esses limites.
* Nenhum cookie foi copiado do Firefox, enviado ou persistido; não houve captura/reutilização de Authorization ou tokens. HTML bruto permaneceu somente em memória para o parser e não foi gravado.
* Nenhum JavaScript ou SQL da aplicação foi executado. O Provider usou exclusivamente o parser controlado implementado na etapa anterior.
* **Zero requisições de escrita.** Nenhum controle Gravar/Excluir/Alterar/Aprovar/Processar foi acionado. Não houve navegador ou UI na homologação.
* Auditoria/instrumentação transitórias foram restauradas ao final do processo. Nenhum arquivo de código, contrato, parser ou credencial foi alterado para acomodar a resposta.

### Validação Pós-Consulta e Limites

**326 testes selecionados passaram novamente** após a chamada real: Client, Provider, contratos/integrações relacionados e helper de descoberta. A resposta real foi reconhecida sem nova heurística; não foi necessário ampliar a suíte ou criar fixture com dados reais.

**CONFIRMADO:** o caminho positivo do Provider foi homologado para o par legítimo `(B, SOB mascarada)` e funcionou sem cookies nesse teste. Não houve diferença impeditiva entre a resposta recebida e o contrato implementado.

**AINDA NÃO CONFIRMADO:** homologação externa com grupo A; ausência/erro/ambiguidade/múltiplos; paginação; comportamento em outras ordens e requisitos de sessão em todos os cenários. O sucesso sem cookies neste teste não é prova universal de que cookies nunca sejam necessários. `NOT_FOUND` permanece reservado, sem classificador inventado.

Provider não registrado automaticamente ou manualmente no catálogo da aplicação. Executor, SyncQueue e UI continuam intocados. Não houve retry, sincronização, cache persistente, build C#, commit ou push.

---

## 15. Fechamento Offline de Dados de Negócio e Negativos — 2026-10-05

**Escopo:** evolução incremental do Provider para os dados de Dados Principais autorizados pelo usuário, usando somente as atribuições literais já observadas. Nenhuma nova consulta externa, leitura de credenciais reais, escrita remota ou alteração do Client foi necessária nesta etapa.

### Contrato Final Compatível

`consultar_os_sob(sob, grupo)` mantém **`(grupo, SOB)` obrigatório**, sem normalização, inferência, grupo padrão ou fallback. Entradas inválidas continuam rejeitadas antes de credentials supplier ou HTTP. Parâmetros recebidos não são alterados.

O resultado conserva as chaves anteriores (`requested_sob`, `requested_grupo`, `returned_sob`, `returned_grupo`, `order_status`, HTTP, autenticação, outcome e IDs de contexto) e acrescenta:

* `identity`: grupo e SOB solicitados, mantendo a rastreabilidade; os valores retornados continuam separados para comparação.
* `project_data`: oito campos canônicos em ordem determinística. Só expõe dados extraídos em `SUCCEEDED`; falhas, resposta inválida ou identidade divergente retornam todos esses campos como `null`.
* Ausência, string vazia ou apenas whitespace de um campo opcional são `null`. Valores não vazios são preservados literalmente, incluindo espaços significativos, Unicode, aspas e quebras escapadas, sem preenchimento por inferência.

### Campos de Negócio Autorizados

| Campo canônico | Atribuição literal da fonte observada | Regra |
| :--- | :--- | :--- |
| `nome` | `frm1.nome.value` | Valor da fonte ou `null` |
| `endereco` | `frm1.logradouro.value` | Sem compor ou inferir endereço |
| `bairro` | `frm1.bairro.value` | Valor da fonte ou `null` |
| `municipio` | `frm1.municipio.value` | Valor da fonte ou `null` |
| `polo_tecnico` | `frm1.area_tecnica.value` | Um único conceito Pólo Técnico/BASE; sem duplicar campo `base` |
| `tipo_servico` | `frm1.tipo_servico.value` | Sem classificação inventada |
| `notas_observacao` | `frm1.notas_obs.value` | Texto autorizado, jamais enviado a logs |
| `referencia` | `frm1.notas_referencia.value` | Opcional; ausência não é erro |

**Limite da evidência:** a nomenclatura efetivamente disponível é `area_tecnica`. Não foi observado um campo de fonte `base` ou `polo_tecnico`, nem uma tabela para converter código de área em nome de pólo. Esses aliases não foram inventados; referências desconhecidas são ignoradas. `ref_projeto_interno` não foi confundido com `notas_referencia` ou com a SOB.

Todos os campos de negócio são opcionais do ponto de vista do sucesso da consulta. A presença de dados pessoais/projeto não substitui a verificação de identidade e estado mínimo. Os estados continuam `etapa_ordem_proj`, `estado_ordem_proj` e `status_ordem`, sem catálogo fechado de valores a partir de um único exemplo.

### Parsing e Segurança

* Whitelist ampliada somente para os oito campos de fonte acima. Campos de cliente/contato, diagnóstico, conexão, sessão, SQL e controles de escrita continuam fora do contrato.
* Atribuições suportadas exigem literal válido e terminador. Corrigida uma inconsistência local: atribuição reconhecida truncada não é mais ignorada como se fosse campo opcional ausente; produz `INVALID_RESPONSE` conservador.
* Campos de negócio têm limite explícito de **16.384 caracteres**, sem truncamento. Identidade e estados mantêm o limite anterior de 256 caracteres. Corpo HTTP mantém seu limite de 2 MiB.
* Escapes de quebra de linha, retorno e tabulação são aceitos para dados de negócio. Controles crus, NUL, surrogate inválido, literais não suportados, expressões, concatenação, scripts/comentários truncados e atribuições conflitantes continuam rejeitados.
* Nenhum JavaScript, eval/exec, SQL, subprocesso ou navegador é utilizado. Não há dependência de DOM real, armazenamento de HTML bruto ou persistência nova de dados de negócio.
* Dados de negócio autorizados aparecem apenas no resultado para o consumidor. Logs permanecem restritos a outcome, etapa/HTTP e operação; não contêm nome, endereço, notas, credenciais, tokens, cookies ou texto de exceções.
* Nenhuma capacidade de escrita, retry, worker, scheduler, registro automático, UI, Executor ou SyncQueue foi acrescentada. O Client e os contratos compartilhados não foram alterados nesta etapa.

### Contrato Negativo Determinístico

**Coberto apenas por testes offline:** grupo ausente/inválido ou minúsculo, SOB vazia/inválida, identidade incompatível A/B ou SOB, echo de identidade sem estado, estrutura/literal truncados, campos mínimos ausentes, campos opcionais vazios/ausentes, campos desconhecidos, 401/403 após handshake, HTTP inesperado, timeout e indisponibilidade. Erros tipados após o primeiro 401 preservam sua classificação, sem virar falha de autenticação pelo status anterior.

Ausência de dados de negócio opcionais não produz erro. Resposta sem identidade/estado mínimo continua `INVALID_RESPONSE`; HTTP 404/200 vazio ou texto não reconhecido não são promovidos a `NOT_FOUND`. Nenhum estado funcional novo foi criado.

### Evidência Real vs. Offline

* **Real homologado anteriormente:** somente o caminho positivo `(B, SOB mascarada)` da seção 14, com identidade e estados mínimos confirmados. O corpo já recebido durante a descoberta mostrou os nomes/estrutura dos dados de negócio, inclusive atribuições vazias; seus valores pessoais não foram transcritos.
* **Offline nesta etapa:** novo mapeamento canônico, opcionais `null`, preservação dos valores, notas longas/escapes, ausência de inferência, sigilo nos logs e negativos. O resultado ampliado com `project_data` não foi re-homologado externamente.
* **Não homologado externamente:** grupo A, `NOT_FOUND`, ambiguidade, múltiplos resultados, demais exemplos reais e equivalências de nomenclatura de fonte não observadas.

### Validação Executada

* Provider: **103 testes passaram**.
* Conjunto relacionado solicitado (Provider, Client, integrações/GOMNET/Executor e helper pertinente): **366 testes passaram**; nenhuma chamada externa nos testes.
* Suíte Python oficial `tests/`, conforme o gate da CI: **1.275 passaram, 2 ignorados**, cobertura global **88,09%**, acima de **80%**. Client e Provider: **95%** de cobertura cada.
* Execução oficial protegida por barreiras de rede externa e carregamento de `.env` real desabilitado no processo de testes; fixtures temporárias/sintéticas continuam permitidas. Nenhuma senha, SOB real ou HTML real foi usado como fixture.
* Não houve alteração de dependência, build .NET, commit ou push. A prontidão para aprovação refere-se a este fechamento offline, não à homologação externa dos cenários ainda desconhecidos.

## 16. Integracao Vertical Transitoria ao OXCAD (Offline)

### Baseline e Escopo

Branch `dev`, 10 commits a frente de `origin/dev`; HEAD antes e depois:
`0b6ae135a03a945cab9201e9618249479e3f72af`. O worktree ja estava sujo:
documento de descoberta, preferencias ambientais, requirements e contrato NTLM,
alem do Client/Provider/check e respectivos testes ainda nao rastreados.
Essas alteracoes foram preservadas. Nenhum commit, push, branch ou tag foi criado.

Esta etapa adiciona somente consulta sincrona, explicita e transitoria. Nao
integra SyncQueue, persistencia no DWG, UI, worker, retry ou sincronizacao.
O NTLM/HTTP e o parser existentes continuam exclusivamente no Client/Provider.
Nao houve nova consulta externa nem uso de dados reais como fixtures.

### Cadeia e Contratos

```text
Contexto soberano OXCAD + WorkOrderQuery(grupo, SOB)
   -> WorkspaceService.ConsultarUniversalizacaoAsync
   -> mesmo ExecutarComandoIntegracaoAsync / subprocesso existente
   -> workspace_integration_cli --action consultar --grupo --query-sob
   -> IntegrationExecutor.execute_query (transitorio)
   -> UniversalizacaoProvider.query_work_order / consultar_os_sob
   -> IntegrationResult + identity + project_data + order_status + IDs
   -> JSON da mesma CLI
   -> WorkspaceService / IntegrationResult<UniversalizacaoQueryData>
   -> consumidor C# recebe dados tipados, sem aplicar ao DWG
```

* `grupo` nasce da consulta explicita; nao ha inferencia pela SOB, valor padrao,
   tentativa A/B ou fallback. Consulta ausente/invalida e rejeitada localmente.
* A SOB ativa vem do contexto soberano; a SOB solicitada permanece em outro
   objeto e em `--query-sob`, separado de `--sob`. Nesta etapa, SOB solicitada
   diferente da ativa e rejeitada; nao altera, associa ou reconfigura o projeto.
* `WorkOrderQuery` e imutavel em Python e C#. Ambos os valores viajam juntos na
   consulta, `query_identity`, identidade do resultado e ecos solicitado/retornado.
   Nao existe chave operacional nova baseada apenas em SOB ou cache de consulta.
* `ProjectScope`, `ProjectContext` e `IntegrationContext` nao recebem grupo.
   A projecao Python de contexto passa a preservar os IDs fornecidos pelo host.
* Validacoes: servico C# antes do processo; CLI antes do Provider; Executor
   antes da consulta e depois do resultado; Provider antes/depois da resposta;
   consumidor C# confere identidade composta, ecos, autenticacao/HTTP e IDs.
   IDs de correlacao/execucao sao limitados a caracteres seguros antes de entrar
   na linha de comando do processo.
* O Registry padrao continua sem Universalizacao. A CLI registra o Provider
   somente para a acao explicita `consultar`; as acoes de fila/GOMNET permanecem.
* Credenciais nao entram em argumentos, contexto ou resultado. O adapter da
   CLI fornece apenas `UNIVERSA_ID`/`UNIVERSA_SENHA`, de ambiente ou `.env` dedicado,
   sob demanda. Nenhuma credencial ou resposta bruta e persistida pela consulta.

### Dados Entregues ao Consumidor

O resultado C# preserva exatamente os campos canonicos `nome`, `endereco`,
`bairro`, `municipio`, `polo_tecnico`, `tipo_servico`, `notas_observacao` e
`referencia`; opcionais ausentes continuam `null`, nao string vazia ou inferencia.
Estados preservados: `etapa_ordem_proj`, `estado_ordem_proj`, `status_ordem`.
Tambem preserva status/error_code, identidade solicitada/retornada, HTTP,
authenticated, outcome, correlation_id e execution_id.

O objeto tipado `transport` tambem entrega evidencia operacional sanitizada:
`GET`, rota fixa `controle.asp`, operacao, backend/protocolo NTLMv2, `sspi`,
target, proxy, redirects, reutilizacao de conexao, flags de envio/nao persistencia
de cookies e etapas HTTP com tipos/tamanhos de token. Nenhum token/header/cookie
ou corpo acompanha esses metadados. O parser C# recusa SUCCESS se esses campos
nao comprovarem Type 1/Type 2/Type 3, HTTP 200 e socket reutilizado.

Nenhum JavaScript ou SQL e executado. Dados de negocio nao sao enviados a logs.
Erros de subprocesso da nova consulta sao sanitizados, sem stderr/excecao brutos.
Nao ha segunda infraestrutura de processo, HTTP, NTLM ou parsing de negocio.

### Prova Executada

`tests/test_universalizacao_vertical.py`: **51 testes passaram**, com tres niveis:

1. CLI/Executor/Provider reais, leitura HTTP sintetica, nenhuma fila ou arquivo.
2. Mesmo JSON entregue ao `WorkspaceService` C# real compilado no harness de
    contexto existente, com igualdade integral dos dados recebidos.
3. Metodo publico do `WorkspaceService` executando seu subprocesso real,
    argumentos reais, CLI/Executor/Provider de producao e retorno tipado C#.
    Adaptador temporario troca somente credenciais/HTTP por valores sinteticos
    e bloqueia sockets. `AUXCAD_ROOT` fixa a instalacao temporaria; nao ha flag
    de fixture ou bypass de seguranca na CLI de producao.

Casos: sucesso B; retorno A para a mesma SOB; retorno B para outra SOB; grupo
ausente/vazio/C/minusculo; consulta de outra SOB preservando contexto; todos os
dados e estados; referencia/polo/bairro ausentes como null; campos desconhecidos;
resposta truncada; divergencia de identidade/IDs/handshake no JSON; injeção em
ID de correlação; entrada CLI por arquivo.
Consultas invalidas nao acessam Provider/rede. Falhas nao entregam dados de negocio.

A prova identificou e corrigiu a entrada por arquivo da CLI: faltava inserir
a raiz em `sys.path`, causando `ModuleNotFoundError` no primeiro import, antes
de Provider/credenciais. Identificou tambem `IsValid` serializado no DTO; a
propriedade calculada agora e ignorada e a identidade permanece `{grupo, sob}`.

Build OXCAD: `net48` e `net8.0-windows` passaram. O alvo net8 apresenta dois
avisos MSB3277 de referencias AutoCAD (`Microsoft.VisualBasic`/`System.Drawing`).
Regressao relacionada: **434 passaram**. Suite Python oficial: **1.325 passaram,
3 ignorados**, cobertura **88,17%**. Assertions do harness C# de contexto,
governanca e fila passaram.

### Limites da Evidencia

O round trip offline prova entrega ao servico/consumidor C# por seu transporte
real, nao apenas sucesso isolado do Provider. A fronteira externa foi simulada;
nao equivale a homologacao de rede ou de UI dentro do AutoCAD. Runtime net48
nao foi executado, apenas compilado. A homologacao real continua restrita ao
positivo B da secao 14. Grupo A real, NOT_FOUND e demais cenarios externos
continuam nao homologados; nao foram reabertos nesta etapa.

Na auditoria final de 2026-10-05, o caller de producao foi ligado em
`OxCadControl.Integracoes.cs`: ele chama `CapturarContextoVerificado()`, coleta
grupos explicitamente e chama `UniversalizacaoOxCadCaller`, que despacha pelo
`WorkspaceService`. O modo normal exige igualdade do par de referencia; o modo
independente exige opt-in e SOB destino explícitos. Nenhum caminho altera
`ProjectScope`.

Uma instância AutoCAD apareceu ativa durante a auditoria, mas o processo tinha
`OxCadPaleta.dll` carregado de `bin/Release` (gravado em 2026-10-01), enquanto o
caller foi compilado em `bin/Debug` (2026-10-05). O attach COM foi rejeitado com
`RPC_E_CALL_REJECTED`, e a árvore UIA não expôs os controles novos. O processo
ativo, portanto, não continha o caller que precisa ser homologado e não permitiu
ler um `ProjectScope` verificado através do host. Não foi feito NETLOAD,
NETUNLOAD ou restart, nem construída uma identidade a partir do título DWG.
Nenhuma consulta externa foi feita; a homologação integrada real permanece
bloqueada até o OXCAD atualizado estar carregado e fornecer contexto verificado.

Gates offline desta rodada: `pytest -q` passou com 1.342 testes e 3 skips; os
TFMs `net8.0-windows` e `net48` compilaram; o harness C# passou todas as
assertions. O build net8 reportou dois warnings de conflito entre assemblies
Autodesk e referências do framework. Resultado: caller validado offline, mas
não homologado contra o host AutoCAD em execução; não pronto para aprovação do
commit.

Retomada em 2026-10-05 após liberação da sessão pelo operador: nenhum processo
AutoCAD estava ativo, e `dotnet build oxcad/OxCadPaleta.csproj -c Release
--no-restore -v quiet` terminou com sucesso. Os artefatos Release usados pelo
loader foram atualizados; permanecem os dois avisos MSB3277 conhecidos. Isso
remove o bloqueio do artefato antigo em disco, mas não comprova seu carregamento
no host. O operador estava indisponível para indicar ou reabrir o DWG da mesma
SOB homologada. Nenhum desenho foi escolhido por inferência e nenhuma consulta
externa foi executada. A retomada exige abrir esse DWG, carregar OXCAD e validar
o contexto real antes da única consulta autorizada no grupo B.

### Evidencia do Caller Real Recebida em 2026-10-05

Após carregar o Release atualizado, o operador forneceu uma captura da paleta
com os grupos B/B, consulta independente desmarcada e resultado
`Consulta concluída: Success · HTTP 200`. A tela exibiu identidade composta do
grupo B, dados de negocio, etapa/estado/status e IDs de correlation/execution.
O diagnóstico exibido foi GET na rota `/sistemas/universalizacao/controle.asp`,
NTLMv2 e `SSPI=False`. Dados pessoais, SOB e IDs completos não foram
transcritos neste registro. O agente não repetiu a consulta.

Essa evidência demonstra consumo do resultado no caller de produção dentro
do AutoCAD, superando o bloqueio anterior de DLL antiga. Pelo caminho do
handler, a consulta normal exige `CapturarContextoVerificado()` antes do
despacho e valida a identidade retornada; o sucesso não foi inferido do nome
do desenho nem dos painéis auxiliares que anteriormente mostravam `SOB: -`.
A evidência é uma captura fornecida pelo operador, não uma inspeção direta do
ProjectScope ou um trace de rede coletado pelo agente. A equivalência com a
SOB mascarada da homologação anterior ainda não foi confirmada pelo operador.

Limitação observada: alguns textos acentuados de tipo de serviço e estado
aparecem corrompidos na tela. A origem da corrupção de caracteres ainda não
foi isolada. Resultado atual: caminho positivo real do caller evidenciado;
aprovação final do commit permanece pendente da confirmação do par de
homologação e do tratamento dessa limitação. Nenhum commit ou push realizado.

### Segunda Captura e Correcao do Transporte Unicode

O operador forneceu uma segunda captura com outra SOB, grupos B/B e consulta
independente desmarcada. O caller novamente exibiu `Success` e HTTP 200,
GET, NTLMv2 e `SSPI=False`, com dados da identidade correspondente. Isso não
confirma equivalência com a SOB da homologação histórica. Dados pessoais e
identificadores completos não foram copiados. Nenhuma nova consulta foi
executada pelo agente.

A corrupção de acentos se repetiu no estado exibido. Uma reprodução sintética
isolou uma falha na fronteira CLI/C#: o Python escrevia JSON com
`ensure_ascii=False` no encoding do stdout do Windows, enquanto o serviço C#
decodifica UTF-8. Com CP1252, o transporte pode corromper acentos ou gerar
`UnicodeEncodeError` para caracteres fora da página de código.

Somente o JSON da ação `consultar` passou a usar `ensure_ascii=True`.
Os escapes JSON preservam os valores Unicode originais após desserialização;
não houve normalização de dados, mudança de identidade ou alteração do cliente
HTTP. A reprodução corrigida preservou exatamente acentos, caracteres fora do
BMP e campos nulos com stdout CP1252, UTF-8 e ASCII e rede bloqueada.
Caller e integração vertical: 67 testes passaram. A correção está validada
offline; sua exibição em uma resposta real posterior ainda não foi verificada.
Não se solicitou outra consulta nem reinício do AutoCAD, pois a alteração está
na CLI Python executada por chamada, não na DLL carregada.

## 17. Gate Final Pos-Correcao Unicode - 2026-10-05

Esta seção atualiza os bloqueios históricos das seções anteriores. Nenhuma
funcionalidade, refatoração ou alteração contratual foi adicionada nesta rodada.

### Transporte e Gates Offline

O fluxo auditado foi caller OXCAD, WorkspaceService, CLI, Executor, Provider,
JSON e consumidor C#. A ação `consultar` serializa com `ensure_ascii=True`:
o JSON contém somente ASCII, independentemente do codec de stdout selecionado
pelo Python no Windows. O C# lê stdout como UTF-8 e desserializa uma vez por
`System.Text.Json`. Não há dupla conversão de encoding nem `errors="replace"`
no código Python desse fluxo. O cliente HTTP decodifica estritamente o charset
informado, ou tenta UTF-8 e Windows-1252 quando o charset está ausente.
Ressalva preexistente: `Encoding.UTF8` no C# admite fallback de substituição
para bytes malformados; não é um decoder fail-fast. O JSON ASCII produzido
pela correção não aciona esse fallback. Não se declara sua remoção.

Os oito mapeamentos de negócio, três estados e campos `null` permanecem no
contrato; Provider e Executor não reconvertem os valores. Os 67 testes de
caller/vertical pós-correção e o round-trip CP1252/UTF-8/ASCII já comprovados
foram reutilizados, sem repetição. Client/Provider/Executor não foram alterados.
Suíte oficial completa executada uma vez nesta rodada: 1.343 passaram e
2 skips. Build Release multi-target `net8.0-windows;net48` passou, e o harness
C# compilado pela suíte passou todas as assertions.

### Uma Consulta Real Pos-Correcao

AutoCAD PID 26784 carregava o Release `net8.0-windows`. O arquivo da DLL,
gravado em 2026-10-05 23:28:06, manteve antes/depois do build o SHA-256
`D53B01C3CF5D656AEDED4308E5852F5C0BB1742FE0182D3327BC922BFCD127FA`.
O build incremental não substituiu esse artefato, já atualizado; a mudança
Unicode reside na CLI Python, executada por chamada.

A automação leu os controles OXCAD: B/B selecionados, independência Off,
contexto identificado e SOB presente, igual à identidade do resultado anterior.
Foi feita exatamente uma invocação de `BtnConsultarUniversalizacao` para
validar a correção, sem chamada direta a Client, Provider ou CLI e sem retry.
O handler executou `CapturarContextoVerificado()`, exigindo ProjectScope Bound,
SOB, DWG, fingerprint e geração coerentes antes do despacho. O sucesso exige
também que a geração continue atual após o retorno. Os painéis auxiliares
com SOB ausente não foram usados como fonte de autoridade.

Solicitado e retornado: `(B, A0******38)`, comparados integralmente em memória,
com igualdade confirmada e SOB do contexto inalterada. Resultado consumido
pelo C#: `Success`, HTTP 200, GET `/sistemas/universalizacao/controle.asp`,
NTLMv2 e `SSPI=False`; correlation/execution presentes, sem transcrever IDs.
O texto recebido não contém U+FFFD, e `ORDEM EM EXECUÇÃO` foi confirmado
com seus caracteres Unicode corretos.

| Campo no consumidor C# | Resultado |
| :--- | :--- |
| Nome | Presente |
| Endereço | Presente |
| Bairro | Presente |
| Município | Presente |
| Pólo Técnico | `null` |
| Tipo de Serviço | Presente |
| Notas de Observação | Presente |
| Referência | `null` |
| Etapa da ordem | `ESTUDO DE REDE` |
| Estado da ordem | `ORDEM EM EXECUÇÃO` |
| Status da ordem | `NO PRAZO` |

Os oito campos e os três estados foram lidos da apresentação do DTO C# por
UI Automation; nenhum valor pessoal foi transcrito. A operação consultada
é read-only: o caminho auditado não altera DWG/ProjectScope, não cria fila,
cache ou persistência de dados de negócio. Os controles de transporte
validados pelo contrato C# exigem GET, ausência de redirects e cookies.
Não houve acionamento de ação de escrita, captura de HTML bruto, credenciais,
tokens NTLM, Authorization, cookies ou headers sensíveis pelo agente.

### Identidade Historica, Diagnostics e Decisao

Mesmo grupo entre Provider histórico e caller: B, confirmado. Mesma SOB e
mesma identidade composta histórica: não demonstráveis pela documentação
mascarada `A0******38`. A coincidência da máscara e dos estados não prova
igualdade dos identificadores integrais.

IDENTIDADE ENTRE AS HOMOLOGAÇÕES: NÃO CONFIRMADA

Diagnostics restritos à CLI e ao dossiê: nenhum erro real novo nem warning
relevante introduzido. Permanecem avisos preexistentes de linhas longas,
imports não usados e captura genérica na CLI, headings duplicados no dossiê,
dois MSB3277 Autodesk no build e RequestsDependencyWarning ambiental.
Nenhuma limpeza geral foi feita. A ressalva do decoder UTF-8 foi documentada.

**PRONTO PARA APROVAÇÃO DO COMMIT**, restrito ao fechamento da integração
Universalização: os gates offline e real Unicode passaram, os contratos e
identidades da chamada foram preservados e a incerteza histórica foi
explicitamente registrada. Isso não aprova alterações paralelas do worktree.
Branch `dev`, HEAD `0b6ae135a03a945cab9201e9618249479e3f72af` preservados.
Nenhum commit, push, reset, checkout destrutivo ou limpeza de mudanças paralelas.

## 18. Revisao de Escopo para Staging - 2026-10-06

Preparação do índice somente para Universalização, sem commit ou push.
Baseline preservado: branch `dev` e HEAD da seção 17. A preferência ambiental
permanece excluída. Em `requirements.txt`, o único acréscimo revisado é
`pyspnego==0.12.1`, necessário ao backend NTLMv2 em software; não há mudança
de dependência ambiental ou não relacionada para incluir.

Foram encontrados e tratados dois resíduos antes do staging: o segundo
branch `--oxcad-universalizacao-process`, duplicado e inalcançável no harness,
foi removido; o dossiê deixou de registrar identificador local do perfil
Firefox e endereços da sessão VPN. Contratos e código produtivo não foram
alterados nesta revisão, incluindo o transporte Unicode já homologado.

Validação diretamente afetada pela remoção do branch: caller e integração
vertical, 67 testes passaram. Os gates completos, build Release/net48 e
homologação real da seção 17 permanecem a referência, sem repetir a suíte
completa ou fazer nova consulta externa. Sanitização documental exige apenas
verificação do diff. Fixtures e mensagens revisadas permanecem sintéticas;
não foram incluídos segredos, tokens reais, cookies reais, HTML real, valores
pessoais ou caminhos específicos da estação. Caminhos `C:/synthetic/...`
nos testes são exemplos artificiais, não referências ao ambiente operacional.

O staging deve conter somente os arquivos causais aprovados: caller e UI,
WorkspaceService e contratos C#, projeção de IDs de contexto, contratos/CLI/
executor Python, Client/Provider/check relacionado, testes/harness, dependência
NTLMv2 e este dossiê. Artefatos de build, temporários, locks DWG e alterações
ambientais permanecem fora do índice. A autorização desta etapa não permite
executar commit, push ou limpar o worktree.
