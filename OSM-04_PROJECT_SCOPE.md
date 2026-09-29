# OSM-04 — Escopo lógico do estado OSM

**Tipo de atividade:** diagnóstico, especificação e implementação parcial
**Estado atual:** IMPLEMENTAÇÃO PARCIAL — NÃO HOMOLOGADA. O escopo persistente SOB–Database e a validação de geração estão implementados e passaram pelas validações offline descritas abaixo; a homologação em AutoCAD continua pendente.

> As evidências e conclusões históricas abaixo registram a baseline do diagnóstico, antes da implementação parcial descrita em “Implementação e validação atual”. Onde houver divergência, essa seção representa o estado atual do código; ela não transforma validação offline em homologação de runtime.

## Decisão executiva

`SOB_ID` é a identidade lógica persistente mais forte disponível no fluxo SOB atual: é fornecida/validada como identificador da SOB, nomeia a pasta e o DWG canônicos, é gravada no manifesto `.sob_state.json` e é o campo de identidade do `ProjectWorkspace` (descrito no código como contexto da “SOB / Projeto”). Portanto, é uma **chave candidata apropriada para escopar um projeto no fluxo SOB**, desde que seja obtida do contexto autoritativo da SOB.

Não há evidência suficiente para tratá-la como uma identidade universal e invariável de todo projeto/intervenção: não foi demonstrada a cardinalidade entre SOB, projeto lógico e DWGs em todos os fluxos, nem o comportamento de `SaveAs`, cópias externas ou reaproveitamento de um mesmo identificador para outra intervenção. O scanner também pode inferir a SOB a partir de nomes de pasta/arquivos, o que não equivale a uma associação autoritativa.

**Na baseline do diagnóstico**, o módulo OSM não recebia nem persistia `SOB_ID`. A implementação parcial atual persiste o vínculo como metadata `AUXCAD_PROJECT_SCOPE` no Named Objects Dictionary do Database, separado do XData `AUXCAD_OSM`, e valida o escopo e a geração antes do desenho. Isso limita a conclusão ao fluxo SOB que valida o manifesto e o `BASE_DWG`; não demonstra uma identidade universal para todo projeto/intervenção.

## Evidências da baseline original do diagnóstico

Esta tabela registra o código **antes** da implementação parcial de ProjectScope descrita mais adiante. Suas conclusões sobre ausência de binding, troca de documento e proteção do bridge são históricas, não descrição do código atual.

| Evidência | O que o código comprova | Limite |
|---|---|---|
| `sob/sob_core.py`: `obter_sob_id`, `obter_sob_name`, `derivar_caminhos_sob` | O identificador é normalizado/validado e usado para construir `SOB_<ID>` e caminhos da SOB. A documentação do helper o descreve como número informado pelo usuário e usado para identificação interna. | Formato válido não prova unicidade corporativa ou semântica universal de projeto. |
| `sob/sob_manager.py` e `sob/sob_idempotencia.py` | O manifesto persiste `sob_id`, `sob_name`, `run_id` e estado da execução. O fluxo bloqueia uma repetição no mesmo destino quando encontra uma SOB existente, conforme o estado do manifesto. | Persistência do contexto da SOB não comprova que toda cópia ou DWG derivado mantenha uma relação verificável com ela. |
| `workspace/workspace_core.py`: `ProjectWorkspace` | O modelo declara explicitamente um contexto central “SOB / Projeto” e contém `sob_id`, `sob_name`, raiz e um `dwg_principal`. | Um campo do modelo não estabelece sozinho a política de identidade para DWGs externos, múltiplos desenhos ou `SaveAs`. |
| `workspace/workspace_scanner.py`: `scan`, `detectar_sob_em_diretorio`, `detectar_dwg_principal` | O scanner pode receber o ID ou inferi-lo do diretório/nomes; seleciona um DWG principal por heurísticas de nome. | Identidade inferida e escolha heurística não devem servir como prova de escopo para evitar mistura de estado. |
| `sob/sob_cad_launcher.lsp` | O launcher passa o identificador ao orquestrador, abre o caminho-base e compara o desenho ativo com o caminho esperado naquele fluxo. | Essa passagem termina no fluxo de preparação/abertura; não foi encontrado encaminhamento do ID para a paleta OSM. |
| `mapa_cad_paleta/MapaControl.xaml.cs`, `PaletteHost.cs` | A paleta mantém um controle/WebView estático durante seu ciclo de vida e processa mensagens do WebView. Não há associação observada com `SOB_ID` nem tratamento de troca de documento para resetar estado OSM. | Não comprova o comportamento em todas as sequências de abertura/fechamento no AutoCAD. |
| `mapa_cad_paleta/web/vias_obstrucoes.js` | `cacheGrid`, `waysProcessados` e `elementosAcumulados` são estado em memória da página; elementos são acumulados e enviados ao CAD. | O estado não tem partição por SOB ou desenho. O estado em memória pode ser reaproveitado enquanto a mesma página permanece ativa; não se afirma persistência entre reinicializações. |
| `mapa_cad_paleta/CadBridge.cs` | Na baseline, as operações usavam `MdiActiveDocument` e `Database.CurrentSpaceId`; entidades OSM eram indexadas e gravadas com `AUXCAD_OSM`. A chave é `osmType:osmId:categoria`, e o fingerprint é calculado separadamente. | A identidade OSM não inclui projeto. O estado atual do bridge e sua validação de escopo estão descritos em “Implementação e validação atual”. |

## Identidades distintas

| Conceito | Evidência/uso observado | Não confundir com |
|---|---|---|
| **Identidade lógica de projeto no fluxo SOB** | `SOB_ID`, persistido no manifesto e usado pelo `ProjectWorkspace`. É a chave candidata para partição do estado por projeto nesse fluxo. | Nome de arquivo, caminho, `BASE_DWG`, região geográfica ou ID de uma execução. |
| **Identidade da fonte OSM** | `osmType` + `osmId` + categoria, usada para reconhecer um elemento OSM; fingerprint distingue o conteúdo observado. | Identidade do projeto. Um mesmo way OSM pode aparecer legitimamente em mais de um projeto. |
| **Identidade física CAD** | Entidade/`ObjectId` dentro do Database e espaço corrente; metadados OSM são gravados em `AUXCAD_OSM`. | Identidade lógica SOB. Handle/ObjectId não deve ser chave de projeto nem de OSM. |
| **Identidade da execução** | `run_id` gerado pelo fluxo SOB. | Identidade estável do projeto. |

## Cenários e política proposta

Estados da matriz: **CONFIRMADO** = comportamento demonstrado pelo código; **PARCIAL** = existe evidência de mecanismo, mas falta confirmar todo o cenário; **DESCONHECIDO** = repositório/evidência disponível não permite concluir.

| Cenário | Evidência na baseline original | Classificação | Política de escopo |
|---|---|---|---|
| Reabrir o mesmo DWG de uma SOB existente | O DWG retém XData por meio do mecanismo CAD implementado; o leitor indexa `AUXCAD_OSM` no Database ativo. A validação real no AutoCAD não foi executada. | **PARCIAL** | Pode reconciliar com o estado OSM daquele DWG, após confirmar o contexto de projeto. Não reutilizar cegamente o cache da WebView. |
| Repetir consulta/desenho no mesmo DWG e mesmo projeto | A página acumula elementos; o CAD ignora uma entidade existente com chave/fingerprint iguais e substitui conteúdo divergente. | **PARCIAL** | Reutilização idempotente fica limitada ao mesmo Database/DWG e à identidade OSM; não equivale a estado compartilhado entre projetos. |
| Novo projeto com `SOB_ID` diferente, mesma região e mesmo way OSM | A chave OSM não contém `SOB_ID`; o CAD escreve no documento atualmente ativo. A WebView não particiona o acumulado por projeto. | **CONFIRMADO quanto à ausência de partição no código; runtime não validado** | Não herdar estado de cache de outra SOB. A mesma referência OSM pode ser consultada/desenhada independentemente em cada projeto/DWG. |
| Alternar documentos enquanto a mesma paleta/página continua ativa | A paleta é estática; o estado JS é em memória; o bridge resolve o `MdiActiveDocument` ao executar operações. Não foi encontrado reset/escopo por documento. | **PARCIAL** | Exigir contexto explícito e invalidar/segregar o estado da WebView ao trocar de projeto/documento antes de qualquer reutilização. |
| Criar nova SOB copiando `modelos/prancha.dwg` | `sob_manager.py` copia o template; o código valida o cabeçalho DWG. | **CONFIRMADO quanto à cópia; DESCONHECIDO quanto a `AUXCAD_OSM` no conteúdo do template** | Até prova direta em cópia controlada, tratar o template como **OSM não confirmado**; não afirmar que está limpo nem que está contaminado. |
| Duas bases/DWGs ou DWG externo associados à mesma SOB | O modelo aponta um `dwg_principal`; scanner seleciona por heurísticas. O fluxo de preparação usa caminho canônico. | **PARCIAL** | `SOB_ID` sozinho não escolhe com segurança qual Database deve ser lido/escrito. Confirmar vínculo projeto–DWG e tratar cada Database como armazenamento físico separado. |
| `SaveAs`, cópia de DWG ou mesmo ID reutilizado para outra intervenção | Não foi localizado contrato que preserve/atualize vínculo lógico nesses casos. | **DESCONHECIDO** | Não deduzir equivalência de projeto pelo caminho, nome ou conteúdo espacial. Solicitar vínculo autoritativo antes de reutilizar estado. |
| Projetos diferentes com IDs distintos e elementos OSM iguais | Identidade OSM é externa ao projeto; cada DWG possui seu próprio Database. | **CONFIRMADO no modelo de identidade; escrita real não homologada** | Permitir a mesma identidade OSM em projetos independentes; nunca transportar entidades/estado de um projeto ao outro por coincidência de `osmId`. |

## Recomendações da baseline original e pendências remanescentes

Esta lista registra as recomendações formuladas antes do binding persistente. O binding SOB–Database, a validação de generation e a invalidação do estado da WebView foram implementados parcialmente desde então. Permanecem as seguintes regras/pendências:

1. Usar `SOB_ID` como escopo lógico somente no domínio SOB e após validação da fonte autoritativa. Não promover extração de nome de pasta/arquivo a prova de identidade universal.
2. Manter separadas a chave do projeto (`SOB_ID`), a chave da fonte OSM (`osmType`, `osmId`, categoria) e a identidade física CAD (entidade/Database). Não incorporar Handle, número visual, coordenadas ou caminho à identidade lógica.
3. Definir binding/rebinding para múltiplos DWGs, `SaveAs` e cópias. O comando atual valida `BASE_DWG` no momento do binding, mas não revalida o manifesto ao apenas carregar metadata já gravado no Database.
4. Corrigir o lifecycle do acumulador: reconsulta forçada não deve anexar duplicatas antigas sem política de cobertura/substituição.
5. Atualizar o índice `AUXCAD_OSM` durante a operação para reconhecer entidades criadas anteriormente no mesmo payload.
6. Manter o conteúdo de `modelos/prancha.dwg` classificado como **não confirmado** até inspeção em ambiente controlado/cópia, sem abrir ou alterar o DWG do usuário.

Essas recomendações não alteram a arquitetura vigente: DWG permanece fonte operacional; estado OSM em memória é transitório; qualquer projeção/cache de projeto é derivada e não deve reparar ou escrever fora do fluxo CAD explícito.

## OSM-04 — PROJECT SCOPE DECISION

### Rastreio de identidade e limites comprovados

| Etapa | Evidência no código | Conclusão |
|---|---|---|
| `SOB` → `SOB_ID` | `sob_core.obter_sob_id` valida/normaliza o identificador; `sob_manager` recebe esse valor e deriva a pasta/caminhos da SOB. | `SOB_ID` identifica a SOB no fluxo SOB. A semântica como ID universal de qualquer projeto/intervenção não está provada. |
| Criação/abertura → `BASE_DWG` | `sob_manager` copia o template configurado para o caminho canônico `BASE_DWG` e persiste o estado no `.sob_state.json`; `sob_idempotencia` grava `sob_id` e `run_id` como valores distintos. | O contexto SOB sobrevive no manifesto. `RUN_ID` é de execução, não de projeto. |
| `BASE_DWG` → `ProjectWorkspace` | `ProjectWorkspace` contém `sob_id`, raiz e `dwg_principal`. `workspace_scanner.scan` pode inferir ID a partir do diretório/nome e escolhe um DWG principal por padrões/heurísticas. | Recuperação existe no subsistema Python, mas pode ser inferida; não prova que o desenho ativo no AutoCAD seja aquele DWG. A cardinalidade de um ou vários DWGs por projeto não está definida. |
| `ProjectWorkspace` → AutoCAD `Database` | `ProjectWorkspace` é usado nos fluxos Python; o launcher SOB passa `SOB_ID` e `BASE_DWG` ao comando `AUXCAD_BIND_SOB`. O comando confere o manifesto concluído, o `sob_id` e o `base_dwg`, valida que o DWG ativo corresponde ao caminho e grava `AUXCAD_PROJECT_SCOPE` no Database. | Há binding persistido no fluxo SOB coberto, mas não um transporte geral de `ProjectWorkspace`; reabertura relê o metadata sem revalidar o manifesto. Não resolve associação de múltiplos DWGs, cópia ou `SaveAs`. |
| `PaletteHost` → `MapaControl` → WebView | `PaletteHost` conserva instâncias estáticas; ocultar a paleta só muda visibilidade. `Plugin` observa `DocumentActivated`; o bridge relê o scope do Database ativo e incrementa a geração. `MapaControl` envia `project_scope_changed` à WebView com `sobId`, status e generation; a página invalida estado OSM quando o contexto muda. | A página pode sobreviver à troca de documento, mas o estado OSM da geração anterior é invalidado no fluxo observado. A eficácia do sequenciamento e dos eventos ainda depende de homologação em AutoCAD; preferências do mesmo origin podem continuar no `localStorage`. |
| WebView → `CadBridge` → Database | `desenhar_elementos_urbanos` envia `projectScope.sobId` e `generation`; o bridge lê o scope do Database MDI ativo e valida binding, identidade e geração antes de iniciar o desenho em `CurrentSpaceId`. | O código rejeita payload sem binding, de projeto divergente ou de geração obsoleta. A proteção depende de os eventos de ativação ocorrerem como esperado em runtime; ainda não foi homologada no AutoCAD. |

`SOB_ID` é **CONFIRMADO como identificador persistido do domínio SOB** e como chave de `ProjectScope` no fluxo coberto pelo binding validado. Não está confirmado como identidade universal de projeto. O vínculo com o Database é validado contra o manifesto e o `BASE_DWG` durante o binding; ao reabrir, o valor persistido é relido, mas o manifesto não é revalidado. A abertura, o salvamento e a reabertura ainda não foram homologados no AutoCAD.

### Contrato de escopo implementado parcialmente

```text
ProjectScope = ("SOB", SOB_ID normalizado persistido em AUXCAD_PROJECT_SCOPE)
DocumentScope = Database/DWG que contém esse binding
```

`AUXCAD_BIND_SOB` valida o manifesto concluído e a correspondência do documento ativo com `BASE_DWG` antes de gravar `AUXCAD_PROJECT_SCOPE` no Database. Na ativação, o bridge carrega o valor do Database ativo; não há fallback por nome de pasta/arquivo. O binding distingue o projeto do Database físico, mas não define política para múltiplos DWGs, cópias ou `SaveAs`.

- **Criar/carregar:** o launcher valida a associação SOB–`BASE_DWG`; o comando grava o binding. Ao ativar documento, o bridge carrega o `ProjectScope` persistido no Database ativo.
- **Mudar:** a ativação de documento incrementa a geração e notifica a WebView. `SaveAs`, cópia e fechamento sem ativação subsequente não possuem política/homologação específica.
- **Preservar:** o binding fica no Database; o estado OSM da WebView é transitório, não é cacheado por projeto e não autoriza escrita em outro DWG.
- **Descartar/bloquear:** a WebView limpa caches, acumuladores e camadas ao receber mudança de escopo/geração e descarta resultados assíncronos obsoletos; o bridge bloqueia payload sem escopo correspondente ou com geração antiga.
- **Voltar ao projeto A:** o binding persistido pode ser relido do Database A. O cache OSM anterior não é restaurado; uma nova consulta/reconciliação é necessária para reconstruir o estado da página.

**Resposta ao critério de saída, limitada ao código e ao fluxo SOB:** na troca A→B, a ativação incrementa a geração, a WebView limpa o estado OSM associado à geração anterior e o bridge recusa payload de A quando B está ativo ou a geração diverge. No retorno a A, o binding é relido do Database A; o estado OSM não é reaproveitado do cache e precisa ser reconstruído por consulta/reconciliação. Há validações offline; falta homologação em runtime AutoCAD.

### Estado observado e classificação por ciclo de vida

Referências principais: `mapa_cad_paleta/web/vias_obstrucoes.js` (`ViasObstrucoesState`, `executarConsultaOsm`, `desenharViasNoCad`, `renderizarElementosOsm`, `converterEEnviarParaCad`), `mapa_cad_paleta/MapaControl.xaml.cs` (`CoreWebView2_WebMessageReceived`) e `mapa_cad_paleta/CadBridge.cs` (`DesenharElementosUrbanos`, `IndexarEntidadesOsm`, `GravarXDataOsm`).

| Estado | Classificação atual | Escopo/observação |
|---|---|---|
| `cacheGrid` | Sessão da WebView / deduplicação de consulta | Grid geográfico em memória, sem chave de projeto; é limpo ao receber mudança de escopo/geração. |
| `inFlightRequests`, `carregando`, `ultimaFalha` | Estado de consulta | Referências/resultados/erros em memória. A invalidação limpa o registro da página, mas não aborta necessariamente o `fetch`; resultados tardios são descartados pela checagem de geração antes de renderizar/enviar. |
| `waysProcessados` | Sessão da WebView / deduplicação derivada de consulta | Guarda IDs OSM de ways, sem chave própria de projeto; é limpo na mudança de escopo/geração. |
| `elementosAcumulados` | Acumulador da sessão WebView | `vias`, `calcadas` e `obstrucoes` recebem `push`; é união de resultados da página, não persistência por projeto. É limpo na mudança de escopo/geração, mas não pela reconsulta forçada. |
| Camadas Leaflet de vias, calçadas e obstruções | Estado visual da sessão WebView | Camadas e dados associados são removidos/limpos na invalidação do escopo/geração. |
| Seleção OSM | Não identificado como estado separado neste módulo | Não há seleção persistida de feature OSM com identidade de projeto observada. |
| Preferências/formulários em `localStorage` | Persistência de interface, não estado OSM do projeto | Chave/origin global da paleta; não está particionada por `SOB_ID`. Não é cache de geometria OSM. |
| Entidades CAD e `AUXCAD_OSM` | Estado derivado/persistente do DWG | XData identifica elemento OSM e fingerprint no Database. O binding de projeto separado é `AUXCAD_PROJECT_SCOPE`; o índice em memória é construído por operação/`CurrentSpaceId`. |
| Marcadores/resultados do comando de escaneamento do DWG | Estado derivado do Database lido | Resposta do documento corrente no instante da leitura; não constitui cache OSM por projeto. |
| Payload aguardando desenho | Mensagem WebView → bridge, sem fila durável | Payload OSM inclui `projectScope.sobId` e `generation`; o bridge valida ambos contra o Database ativo antes do desenho. Uma resposta tardia de geração antiga é descartada antes de renderização/envio. |

O ciclo implementado parcialmente é: `Project Open/Bind` → binding SOB validado e persistido no Database → ativação carrega escopo e incrementa generation → WebView vincula a generation e limpa estado OSM anterior → consulta → payload com escopo/generation → bridge valida Database ativo antes de desenhar. Na ativação seguinte, a geração anterior é invalidada. Persistência/reabertura, fechamento e outros modos de associação ainda dependem de homologação/política.

### Matriz dos cenários obrigatórios

| Cenário | Estado atual (evidência/classificação) | Risco | Comportamento correto requerido |
|---|---|---|---|
| A. Abrir novamente o mesmo projeto | Escopo é lido do Database ao ativá-lo e a generation é atualizada; o cache OSM não é restaurado por projeto. **PARCIAL** | Falta homologar persistência/reabertura em AutoCAD; reuso silencioso de cache não ocorre pelo contrato implementado. | Confirmar binding ao abrir; reconsultar/reconciliar o estado OSM da página. |
| B. Fechar e reabrir o mesmo projeto | O binding persiste no Database e será relido na ativação; não há cache OSM persistente na WebView. O close/reopen real não foi homologado. **PARCIAL** | Persistência e sequenciamento dos eventos AutoCAD ainda não confirmados em runtime. | Recarregar binding, invalidar geração anterior e reconstruir estado OSM por consulta/reconciliação. |
| C. Abrir dois DWGs do mesmo projeto | Cada Database tem binding próprio; o fluxo de binding valida o `BASE_DWG`, mas não há política para associar outros DWGs da mesma SOB. **DESCONHECIDO/PARCIAL** | Outro DWG pode estar sem binding ou fora da associação pretendida. | Definir e validar separadamente o binding e o Database de destino para cada DWG. |
| D. Abrir projeto diferente com a mesma WebView | Ativação muda generation; a WebView limpa estado OSM anterior e o bridge valida scope + generation. **CONFIRMADO no código; runtime não homologado** | Se o evento não ocorrer/for atrasado em runtime, eficácia precisa ser verificada. | Manter a invalidação e a validação do bridge; homologar A→B no AutoCAD. |
| E. Outro projeto contém a mesma rua OSM | O binding OSM e o ProjectScope são identidades distintas; a mudança de escopo limpa `waysProcessados` e acumuladores. **CONFIRMADO no código** | Nenhum cache de fonte é compartilhado; não há risco de identidade de projeto ser inferida do way. | Consultar/reconciliar separadamente em cada Database; `osmType+osmId` não define projeto. |
| F. Criar projeto novo pelo template | `BASE_DWG` é copiado do template; conteúdo interno OSM/XData não foi inspecionado. **CONFIRMADO quanto à cópia; NÃO CONFIRMADO quanto ao conteúdo** | Binding ou XData pré-existente no template não pode ser excluído nem afirmado. | Não presumir template limpo/contaminado; validar em cópia controlada numa fase própria. |
| G. Copiar/`SaveAs` um DWG | Não há política específica para atualizar/revalidar binding; propagação do metadata não foi testada. **DESCONHECIDO** | Cópia pode manter um binding que não representa o novo projeto. | Definir regra explícita de reassociação e validar cópias/`SaveAs`; não inferir identidade pelo caminho. |
| H. Trocar documento ativo no AutoCAD | Handler de ativação incrementa generation; WebView invalida estado anterior e bridge valida scope + generation. **CONFIRMADO no código; runtime não homologado** | Falha/ordem do evento em runtime precisa ser validada. | Homologar ativação e confirmar validação imediatamente antes do desenho. |
| I. Fechar documento e abrir outro | O caminho coberto observa ativação de documento, não comprova um detach específico no close. A nova ativação atualiza generation. **PARCIAL** | Janela sem documento ativo e ordenação close/activate não foram homologadas. | Testar close/open e garantir invalidation e binding do próximo Database antes de desenho. |
| J. Nova consulta OSM no mesmo projeto | Consultas usam os deduplicadores/acumulador da sessão vinculada à generation atual. **PARCIAL** | Cobertura e acumulador continuam sendo estado de sessão, não armazenamento por projeto. | Preservar isolamento de geração; definir lifecycle de cache/cobertura separadamente. |
| K. Reexecutar a mesma consulta | Cache normal pode impedir nova consulta; com `forcarReconsulta=true`, limpa `cacheGrid` e `waysProcessados`, mas não `elementosAcumulados`. **CONFIRMADO no código** | Resultado idêntico é anexado outra vez; payload posterior pode conter duplicatas. | Reconsulta forçada substitui snapshot/contribuição atingida, ou limpa e reconstrói o acumulador do projeto; nunca duplica por append. |
| L. Reabrir a paleta depois de alterar o projeto | Hide/show mantém `PaletteSet`/`MapaControl`; a generation atual e o escopo são enviados à WebView, e mudança de contexto invalida estado OSM. Preferências em `localStorage` continuam globais ao origin. **PARCIAL** | O estado OSM só será limpo se a mudança tiver sido observada pela ativação; runtime ainda não homologado. | Confirmar binding/generation ao mostrar ou carregar a página; sem escopo, bloquear desenho. |

### Acumulador e índice CAD

**`elementosAcumulados`:** seu uso como união de dados de áreas consultadas durante a vida da página parece intencional, pois o caminho de cache pode reenviar o acumulado. Não há evidência de que seja intencional manter duplicatas após uma reconsulta forçada. A sequência reproduzível por código é: consultar área → acumular elementos → chamar `desenharViasNoCad(true)` → limpar `cacheGrid`/`waysProcessados` → retornar elementos iguais → fazer `push` no acumulador sem limpá-lo. Isso duplica itens em memória e pode reenviar dados antigos. O lifecycle correto é por `ProjectScope`; uma atualização forçada deve substituir o snapshot da cobertura consultada (com proveniência de cobertura) ou reconstruir o acumulado do projeto. Se a proveniência não existir, a opção conservadora é limpar o acumulador do projeto antes de reconstruí-lo.

**Índice `AUXCAD_OSM`:** `IndexarEntidadesOsm` cria o mapa a partir do espaço corrente antes de iterar o payload. A chave observada é `osmType:osmId:categoria`; `GravarXDataOsm` persiste essa chave/fingerprint, sem identidade de projeto. O índice não recebe as referências das entidades criadas durante a mesma iteração. Logo, se um payload repetir uma chave que ainda não existia no Database, o segundo item também pode passar pela verificação inicial e criar entidades novamente; fingerprints divergentes para a mesma chave também podem produzir duplicidade/inconsistência na mesma chamada. A fonte normal OSM tende a fornecer ways únicos, mas a proteção contra payload repetido não está garantida.

Correção arquitetural recomendada: validar/agrupar o payload antes de criar entidades e manter um índice de trabalho atualizado a cada criação/remoção dentro da transação. Preservar o fato de uma feature OSM poder resultar em múltiplas entidades CAD: o índice precisa guardar o grupo de referências por chave OSM, não reduzir necessariamente a feature a uma única entidade. Não alterar `AUXCAD_OSM` para incluir identidade de projeto; ele continua sendo identidade do elemento OSM.

### `CurrentSpaceId` e template

`CurrentSpaceId` expressa o espaço de desenho corrente no Database; não é `ProjectScope`. Como o índice OSM é lido nesse espaço, entidades em outros espaços/layouts podem não participar da reconciliação e uma operação em espaço diferente pode criar duplicatas em relação às entidades já existentes em outro espaço. O efeito real depende do uso de Model Space/Paper Space/layouts. Manter fora da correção de ProjectScope e abrir fase própria para decidir se o índice deve ser por Database inteiro, por espaço ou por política de desenho.

`BASE_DWG`: o código aponta para `modelos/prancha.dwg`, copia-o para `BASE_DWG` e valida o resultado da cópia/hash no fluxo SOB. Isso comprova o mecanismo de cópia, não o conteúdo de regapps/XData do arquivo binário. Presença/ausência de `AUXCAD_OSM` ou estado OSM no template: **NÃO CONFIRMADO**. A cópia do template pode explicar estado inicial somente se esse conteúdo vier a ser comprovado; não explica, por si só, a ausência de isolamento da WebView.

### Decisão arquitetural numerada

1. **Identidade disponível no fluxo coberto:** `SOB_ID` é a chave persistida no manifesto e no metadata do Database, mas sua semântica universal para todo projeto continua não comprovada.
2. **Fonte:** o comando `AUXCAD_BIND_SOB` valida o par `SOB_ID`/`BASE_DWG` contra o manifesto concluído do projeto; nomes e caminhos inferidos não são fonte de identidade.
3. **Lifecycle implementado:** o binding é gravado no Database pelo comando do launcher; o bridge lê o escopo persistido do Database ativo ao atualizar o contexto de documento. Essa leitura não revalida o manifesto. Trocas observadas incrementam uma geração; o comportamento de fechamento, `SaveAs` e runtime ainda requer homologação.
4. **Escopo da WebView:** `PaletteHost`/`MapaControl` podem permanecer singleton. A notificação de mudança chega à página, que invalida o estado ligado à geração anterior; recriar a WebView não substitui a validação de identidade.
5. **Escopo OSM atual:** caches e acumuladores são de sessão da página, não persistência por projeto. São limpos quando a página recebe mudança de escopo/geração; não há reaproveitamento automático de uma partição de cache por projeto.
6. **Troca de documento/projeto:** para Database A e B corretamente vinculados a identidades distintas, a ativação de B incrementa a geração, a WebView limpa estado anterior e o bridge valida `SOB_ID` e geração antes de aceitar o payload. Database sem binding é bloqueado. Se uma cópia/`SaveAs` de A for tratada como outro projeto mas conservar o mesmo metadata, o código não tem fonte independente para detectar essa divergência lógica; esta política está pendente. A eficácia em runtime ainda não foi homologada.
7. **Reaproveitamento:** ao retornar a A, o metadata persistido no Database A é relido, sem revalidação do manifesto. O cache OSM da sessão anterior não é restaurado; uma nova consulta/reconciliação é necessária.
8. **Invalidação:** escopo ausente/inválido, identidade divergente ou generation obsoleta bloqueiam o desenho no handler OSM. Não foi comprovado tratamento específico para `SaveAs`, cópia externa ou fechamento sem ativação subsequente.
9. **`AUXCAD_OSM`:** manter exclusivamente como identificação OSM/categoria/fingerprint da entidade CAD; não o transformar em chave de projeto.
10. **`CurrentSpaceId`:** problema diferente do escopo lógico; não alterar nesta fase, investigar separadamente.
11. **`BASE_DWG`:** cópia confirmada; conteúdo OSM interno não confirmado e não deve ser presumido.
12. **Problemas confirmados no código atual:** `SOB_ID` não foi provado como identidade universal; `SaveAs`, cópias e múltiplos DWGs não têm política completa; caches OSM não são persistidos/particionados por projeto; a reconsulta forçada pode deixar `elementosAcumulados` duplicado; o índice `AUXCAD_OSM` pode não refletir entidades criadas antes do fim do payload.
13. **Não confirmados:** semântica/unicidade universal de `SOB_ID`; comportamento de cópias/`SaveAs` e múltiplos DWGs; conteúdo OSM do template; durabilidade do Xrecord após salvar/reabrir no AutoCAD; ordenação e eficácia dos eventos em runtime.
14. **Correções/validações restantes:** homologar binding, salvamento, reabertura e troca de documento no AutoCAD; definir política para `SaveAs`/cópias/cardinalidade; corrigir o lifecycle do acumulador e atualizar o índice dentro da transação em fase própria.
15. **Fora do escopo desta etapa:** persistir cache OSM completo por projeto; alterar `CurrentSpaceId`; alterar o template/DWG; integrar Universalização; homologar em AutoCAD sem ambiente autorizado.
16. **Estado da decisão:** invalidação A→B e leitura do binding ao retornar A estão implementadas para o fluxo coberto, mas não resolvem cópias com metadata herdado nem restauram cache OSM. A decisão global permanece **IMPLEMENTAÇÃO PARCIAL — NÃO HOMOLOGADA**, condicionada à validação em runtime e às políticas ainda ausentes.

### Implementação existente e testes/decisões restantes

- **Já implementado parcialmente:** comando de binding SOB ao `BASE_DWG` validado, metadata `AUXCAD_PROJECT_SCOPE`, geração por ativação, invalidação da sessão WebView e validação de escopo/generation no bridge.
- **Ainda requer implementação/decisão:** política independente para múltiplos DWGs, `SaveAs` e cópias; decidir se o manifesto deve ser revalidado ao reabrir; lifecycle de `elementosAcumulados`; atualização incremental do índice `AUXCAD_OSM`.
- **Homologação necessária:** testar ida A→B→A com WebView viva, projeto sem binding, close/open e reload no AutoCAD. Confirmar que payload obsoleto é recusado e que, ao retornar a A, o binding é relido sem alegar restauração de cache.
- **Em cópias controladas:** validar dois DWGs do mesmo projeto, projetos distintos com a mesma rua OSM, `SaveAs`, layouts/`CurrentSpaceId` e conteúdo `AUXCAD_OSM` do template.

## Limitações atuais e fora do escopo

- A implementação funcional de escopo SOB–Database e proteção por geração foi feita parcialmente; não foi criado cliente ou serviço de integração externo.
- Nenhum DWG foi aberto, alterado ou inspecionado no AutoCAD. O conteúdo OSM/XData de `modelos/prancha.dwg` continua **DESCONHECIDO**.
- Não foi executado teste real de AutoCAD; persistência e comportamento runtime continuam sem homologação.
- `OSM-01R` continua **PENDENTE**; não se afirma idempotência real/homologação.
- Não houve consultas OSM adicionais nem teste de outros projetos.
- `DT-01H` e validação runtime do Digital Twin não são abrangidas nem alteradas por esta investigação.
- O contrato da Universalização permanece independente e incompleto; nenhum dado ou integração foi alterado.

## Próximos passos recomendados

1. Em ambiente controlado, homologar binding, salvamento, fechamento/reabertura e troca de documento/projeto com DWGs de teste.
2. Definir a política de associação para `SaveAs`, cópias e múltiplos DWGs por projeto antes de ampliar o fluxo coberto.
3. Em cópia de teste, verificar o conteúdo OSM do template sem modificar o arquivo original.
4. Corrigir em fase própria o lifecycle de `elementosAcumulados` e a atualização incremental do índice `AUXCAD_OSM`.

## Investigação complementar — baseline anterior ao binding persistente

Esta seção registra a investigação feita antes da implementação parcial do binding. Suas conclusões de ausência de metadata e de proteção no bridge são históricas; o mecanismo presente no código e seus limites estão descritos em “Implementação e validação atual”. Nenhum DWG foi aberto nem inspecionado.

### Evidência adicional

| Origem | O que o código demonstra | Limite |
|---|---|---|
| `sob/sob_core.py` (`obter_sob_id`, `derivar_caminhos_sob`, `copiar_arquivo_base`) | Valida `SOB_ID`, deriva a pasta/caminho canônico `BASE_DWG` e copia o template com validação de hash. | Demonstra identidade e integridade no fluxo de preparação SOB, não identidade gravada/validada pelo `Database` em execução. |
| `sob/sob_manager.py` (gravação de `.sob_state.json` após conclusão) | Persiste `sob_id`, `sob_name`, `base_dwg`, `base_dwg_hash` e `run_id` no manifesto localizado na raiz SOB. | É um vínculo de manifesto entre execução/SOB e o arquivo-base. Não foi encontrado consumidor na paleta OSM que carregue esse manifesto e valide o documento ativo contra ele. |
| `sob/sob_cad_launcher.lsp` (abertura e validação do `ActiveDocument`) | Durante a abertura solicitada, compara `ActiveDocument.FullName` com o caminho esperado de `BASE_DWG` e reporta divergência. | Validação pontual por caminho nessa operação; não grava associação no DWG nem estabelece binding recuperável após fechar, `SaveAs` ou troca de documento. |
| `workspace/__init__.py` (`abrir_workspace_dwg`) e `workspace/workspace_scanner.py` (`extrair_sob_de_texto`, `detectar_dwg_principal`) | Obtêm a SOB de texto/nome e selecionam `dwg_principal` por convenções e fallback de arquivos encontrados no diretório. | É resolução de workspace por convenção/heurística. Um `ProjectWorkspace` Python não é transmitido para o `Database` da paleta. |
| `workspace/workspace_context_cli.py` (`extrair_contexto_operacional`) | Compara a SOB extraída do nome do DWG com a do workspace e sinaliza inconsistência quando os valores divergem. | A verificação detecta divergência entre valores inferidos/fornecidos; não autentica a associação nem impede que o bridge OSM escreva em outro documento. |
| `oxcad/DwgContext.cs` (`ExtrairSob`, `ConstruirContexto`) | Extrai SOB de padrões no nome do DWG e, como fallback, no diretório. | Confirma que o contexto exibido pelo OXCAD pode ser heurístico; não é metadata persistente do desenho. |
| `oxcad/OxCadControl.xaml.cs` (`AtualizarContextoAsync`) / `oxcad/WorkspaceService.cs` | Obtêm o `Database.Filename` do documento MDI ativo e consultam o contexto do workspace a partir do caminho. | `Database.Filename` identifica o arquivo físico; a consulta de contexto não o associa de forma persistente a uma SOB dentro do Database. |
| `mapa_cad_paleta/Plugin.cs` e `mapa_cad_paleta/CadBridge.cs` | A paleta é aberta por comando; as operações do bridge resolvem `MdiActiveDocument` no momento da operação. | Não foi encontrado handler de ativação/fechamento que faça rebind/invalidação, nem verificação de identidade de projeto antes de desenhar. |
| Busca no código por metadata de projeto em DWG (`NamedObjectsDictionary`, `XRecord`, `ExtensionDictionary`, `SummaryInfo`, propriedades customizadas) | Não foi localizado mecanismo usado para gravar/ler uma identidade SOB/projeto do `Database`. O mecanismo encontrado é `AUXCAD_OSM` em entidades. | Conclusão limitada ao código pesquisado; o conteúdo do template não foi inspecionado. `AUXCAD_OSM` identifica elemento OSM/CAD, não projeto. |

### Candidatos de identidade e decisão

| Candidato | Avaliação para `ProjectScope` |
|---|---|
| `SOB_ID` | Identificador persistido e validado no domínio SOB; candidato de identidade lógica apenas quando recebido de fonte SOB autoritativa. Isoladamente, não prova que o documento MDI ativo pertence àquela SOB nem que seja identificador universal de projeto. |
| Nome/caminho de pasta ou DWG | Não autoritativo: o código extrai SOB por regex e usa padrões/fallbacks para localizar DWG. Cópia e `SaveAs` podem preservar ou alterar nomes sem provar a identidade lógica. |
| Caminho completo do `BASE_DWG` | Permite a comparação pontual do launcher; identifica localização física e não sobrevive necessariamente a movimentação, cópia ou `SaveAs`. Não é chave de projeto. |
| Hash do DWG | O manifesto o usa para integridade do arquivo-base. Hash identifica conteúdo exato naquele instante, pode mudar com edição e pode ser idêntico entre cópias/projetos; não substitui identidade de projeto nem associação. |
| `.sob_state.json` / `ProjectWorkspace` | O manifesto persiste dados do fluxo SOB e o workspace agrega artefatos; nenhum foi encontrado como fonte consumida pelo bridge OSM para validar o Database ativo. |
| Metadata persistente dentro do DWG | Seria um mecanismo possível para estabelecer/revalidar associação, mas não existe no código examinado. Cópia/`SaveAs` ainda exigiriam regra explícita de manter ou reassociar o vínculo. |

**Conclusão de identidade:** não há no código uma associação persistente e autoritativa já implementada entre o `SOB_ID` e o `Database` usado pela paleta OSM. O launcher valida temporariamente um caminho esperado durante a abertura; o contexto OXCAD/workspace deriva ou compara identificadores por convenções de caminho/nome; o bridge usa o documento MDI atual sem binding de projeto. Portanto, não é possível definir agora um `ProjectScope` implementado que possa ser carregado ao retornar ao Projeto A. A proposta restrita ao domínio SOB continua dependendo da definição e implementação de uma fonte autoritativa de vínculo.

### Respostas aos critérios de saída

- **Troca A → B com a paleta aberta:** atualmente, nenhum mecanismo impede que estado OSM da sessão WebView de A seja enviado ao documento B. A mensagem não carrega vínculo verificável de projeto/documento e o bridge seleciona o `MdiActiveDocument` no processamento.
- **Retorno B → A:** atualmente, nenhum mecanismo recupera uma partição legítima de A. Se a WebView permaneceu viva, o estado em memória pode continuar, mas não está associado a A e pode conter mistura; se foi recarregada, o cache em memória desaparece. Não há cache persistente por projeto demonstrado.
- **Dois DWGs na mesma SOB:** o manifesto da preparação referencia um `BASE_DWG` e o workspace expõe um `dwg_principal`; não foi encontrado contrato oficial para múltiplos DWGs da mesma SOB nem associação por Database. Suporte a essa cardinalidade permanece **DESCONHECIDO**.
- **Template:** está confirmado que `modelos/prancha.dwg` é copiado e que o arquivo-base resultante é validado por hash. Presença ou ausência de `AUXCAD_OSM`/estado OSM interno ao template permanece **NÃO CONFIRMADO**, pois nenhum DWG foi inspecionado.

**Status final da investigação original:** DIAGNÓSTICO INCOMPLETO — BLOQUEIO: faltava definir e implementar uma associação autoritativa, persistente e recuperável entre a identidade lógica do projeto e cada Database CAD permitido. A implementação parcial posterior abaixo resolve o vínculo para o fluxo SOB coberto, sem comprovar a semântica universal de `SOB_ID`, cópias/`SaveAs` nem o suporte a múltiplos DWGs por projeto.

Não selecionar silenciosamente caminho, nome, hash ou `SOB_ID` inferido como substituto desse contrato. Antes da implementação OSM-04, a decisão de produto/arquitetura precisa estabelecer: fonte de verdade do projeto, vínculo persistente por DWG, comportamento de cópia/`SaveAs`, cardinalidade de DWGs e como o bridge valida esse vínculo em cada operação. Até lá, o comportamento seguro especificado é não reutilizar nem desenhar estado OSM quando o vínculo não estiver confirmado.

## Implementação e validação atual

### Mecanismo implementado

- `ProjectScopeContract` normaliza `SOB_ID`, representa os estados bound/unbound/invalid/ambiguous e rejeita metadados inválidos.
- `DwgProjectScopeStore` persiste/recupera o identificador em um `Xrecord` `AUXCAD_PROJECT_SCOPE` no Named Objects Dictionary do Database. Isso é metadata de projeto e não altera a identidade OSM `AUXCAD_OSM`.
- `AUXCAD_BIND_SOB` aceita somente o `SOB_ID` e `BASE_DWG` passados pelo launcher, confere documento ativo, manifesto concluído, `sob_id` e `base_dwg` do manifesto antes de gravar. Um DWG já ligado a outro `SOB_ID` não é sobrescrito.
- A escrita normaliza e valida o `SOB_ID` antes da comparação com um vínculo existente; repetição do mesmo identificador normalizado é idempotente, e binding conflitante ou metadata inválida é recusado.
- `CadBridge` relê o escopo do Database MDI ativo quando o documento muda, incrementa uma geração por ativação e rejeita payload sem escopo, com identidade divergente ou geração diferente da ativa.
- Durante a reconciliação CAD, o índice `AUXCAD_OSM` é atualizado conforme cada entidade é marcada na transação, mantendo todas as entidades geradas para a mesma chave. Assim, uma repetição da mesma chave no mesmo payload é reconhecida antes de criar nova geometria; conteúdo divergente remove as entidades anteriores da transação antes da substituição.
- O caminho OSM de desenho observado é único: `vias_obstrucoes.js` envia `action: "desenhar_elementos_urbanos"`, o handler correspondente em `MapaControl` chama `CadBridge.DesenharElementosUrbanos`, e esse método valida o escopo antes do desenho. Não foi encontrado outro handler OSM de desenho no percurso pesquisado.
- `MapaControl` encaminha o estado à WebView; `app.js` despacha a mensagem; `vias_obstrucoes.js` limpa caches, acumuladores e camadas quando o vínculo/geração muda, bloqueia operações sem escopo e abandona resultados assíncronos obsoletos. Uma reconsulta forçada bem-sucedida também substitui os acumuladores e camadas OSM antes de renderizar; se a consulta falha, o estado anterior é preservado.
- O loader agora considera a carga bem-sucedida somente quando `AUXCAD_BIND_SOB` está registrado após `NETLOAD`, em vez de confiar no retorno do carregador.

### Limites e estado de validação

- `SOB_ID` permanece identidade comprovada somente no fluxo SOB; associação de projetos externos, `SaveAs`, cópia de DWG e múltiplos DWGs da mesma SOB continuam sem política completa.
- O retorno ao mesmo `SOB_ID` pode recuperar o binding persistido no Database reaberto; caches de sessão da WebView são invalidados ao trocar a geração/documento e não são persistidos por projeto. A nova consulta/reconciliação do mesmo projeto é necessária para reconstruir a sessão OSM.
- `AUXCAD_OSM` não inclui identidade de projeto; permanece identidade da feature OSM no DWG. `CurrentSpaceId` continua sendo escopo de desenho/espaço e não substitui ProjectScope.
- As duas correções de duplicação foram implementadas no código e ainda exigem validação em runtime no AutoCAD: substituição do acumulado/camadas em reconsulta forçada bem-sucedida e atualização incremental do índice CAD na transação.
- O estado do salvamento é verificado pelo launcher via `QSAVE`/`DBMOD == 0`; isso não valida persistência por reabertura.
- Validação offline atual: `dotnet build mapa_cad_paleta/MapaCadPaleta.csproj --configuration Release` concluiu com sucesso para `net48` e `net8.0-windows`, com avisos `MSB3277` de conflito de referências `Microsoft.VisualBasic`; o aviso `CS8602` em `ProjectScope.TryNormalizeSobId` foi corrigido com uma guarda explícita de null e não reapareceu no build final. `dotnet run --project tests/dt02_harness/DT02Harness.csproj` passou nas 44 verificações; `node --check` passou para `app.js` e `vias_obstrucoes.js`; `git diff --check` não reportou erros. Isso não substitui a homologação em AutoCAD.
- A sintaxe/execução do AutoLISP e o comportamento dos comandos não foram homologados em AutoCAD. Nenhum teste offline equivale a homologação no AutoCAD.

### Pendências objetivas

1. Em ambiente autorizado, homologar binding, salvamento, fechamento/reabertura e troca de documento/projeto com DWGs de teste; essa etapa requer interação de runtime e não foi executada.
2. Definir tratamento de cópia/`SaveAs` e cardinalidade de DWGs por projeto antes de ampliar a associação para além do fluxo `BASE_DWG` validado.

**Critério de segurança implementado em código:** durante troca de A para B, o estado da WebView é invalidado por geração e o bridge rejeita mensagens cuja geração ou `SOB_ID` não corresponda ao Database ativo. Ao retornar a A, o vínculo é recuperado do metadata persistido no Database A; o cache de sessão anterior não é reaproveitado e precisa ser reconstruído. **Estado global:** IMPLEMENTAÇÃO PARCIAL — NÃO HOMOLOGADA.
