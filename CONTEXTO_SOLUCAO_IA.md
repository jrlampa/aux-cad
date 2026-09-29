# Contexto da solução para futuras sessões de IA

## Finalidade deste documento

Este documento reúne o contexto de produto, arquitetura, decisões, pedidos, trabalho relatado e pendências que uma futura IA precisa conhecer antes de atuar neste repositório. Ele é um mapa de contexto, não substitui a leitura do código ou a verificação do estado atual do Git. Os números de testes e builds abaixo são resultados históricos da sessão indicada, não garantias do estado atual.

## Solução e repositório

- Repositório local: `aux cad`.
- Solução central: ferramentas auxiliares de CAD/AutoCAD, incluindo `mapa_cad_paleta` e `oxcad`.
- Branch observada em verificações recentes: `dev`.
- Último commit registrado no contexto anterior: `b358b67` (`chore(oxcad): finalize release 0.6.0`). Reconfirme HEAD antes de qualquer operação.
- O worktree já estava sujo, com mudanças tracked e arquivos untracked de trabalho anterior. Não limpar, reverter ou sobrescrever alterações sem pedido explícito.
- Projetos .NET relevantes incluem targets `net8.0-windows` e `net48`; os testes de apoio também incluem Python e um harness .NET para DT-02.
- O módulo usa AutoCAD e WebView2; existência de executável/compilação não comprova comportamento real no AutoCAD.

## Princípios e limites de arquitetura

1. **DWG é a fonte de verdade operacional.** O Digital Twin é projeção/read model derivado do scanner do DWG.
2. **DT-01/DT-02 são somente leitura.** Não devem reparar o desenho, escrever no DWG, gerar identidades ou sincronizar automaticamente.
3. **Identidade de poste:** `DomainId` é a identidade lógica persistente; `Numero` é atributo visual/editável; `Handle` é referência física CAD.
4. **Identidade de vão:** `VaoId`, `PosteOrigemId` e `PosteDestinoId`; `Handle` apenas referencia a entidade CAD.
5. Não inferir relações elétricas por distância/coordenada, número, Handle, ordem da lista ou ordem de criação quando a topologia deve vir de relações semânticas explícitas.
6. Não introduzir banco de dados, persistência do grafo, sincronização bidirecional, eventos CAD, telemetria ou atributos sem fonte comprovada sem nova solicitação.
7. Não abrir/fechar/manipular sessões AutoCAD nem modificar DWGs de usuário automaticamente. Homologações manuais devem usar sessão controlada e cópias de DWG.

## Histórico dos pedidos e trabalho

### Digital Twin DT-01 e DT-02

- Foi solicitado um read model semântico, construído a partir do fluxo existente:
  `DWG → LerEstadoDwg() → ReconciliarTopologiaDwg() → EscanearDwgResultado → DigitalTwinBuilder → DigitalTwin`.
- A DT-02 deveria acrescentar um grafo em memória, determinístico e somente leitura: postes, vãos, incidência, conectividade, postes isolados, vãos órfãos, relações inválidas, componentes conexos e diagnósticos.
- Foram adicionadas consultas equivalentes a obter poste/vão, vãos incidentes, postes conectados, postes isolados, vãos órfãos e componentes conexos. Consulte `mapa_cad_paleta/DigitalTwin.cs` para a API real.
- Diagnósticos considerados incluem `TWIN_ORPHAN_POSTE_REFERENCE`, `TWIN_SELF_LOOP`, `TWIN_ISOLATED_POSTE`, `TWIN_DUPLICATE_RELATION` e `TWIN_INVALID_TOPOLOGY`; confirmar implementação e nomes no código.
- Um feedback apontou inconsistência potencial para vãos `IsOrphan`; a correção registrada faz a topologia explicitamente órfã não conectar componentes.
- Foi solicitado um conjunto extenso de testes, incluindo vazio, isolamento, cadeia, ramificação, órfãos, endpoints inexistentes, self-loop, duplicidade, componentes separados, preservação de identidade, não mutação do input, ordem de entrada, diagnósticos do scanner e ausência de conectividade inferida por proximidade.
- O construtor/builder deve continuar recebendo `EscanearDwgResultado`, sem scanner alternativo, geração de IDs ou mutação/reparo da entrada.
- Roadmap antigo que descrevia DT-02 como exportação GeoJSON foi marcado como histórico/substituído; não tratar essa proposta histórica como funcionalidade entregue.

### OSM e geometria urbana

- A fase OSM-01 corrigiu offline a duplicação pelo reenvio de payload: namespace XData independente `AUXCAD_OSM`, identidade determinística usando dados OSM, fingerprint SHA-256 e tratamento idempotente do payload repetido.
- Regra de segurança: atualização/remoção abrange apenas entidades criadas/identificadas pelo módulo (`AUXCAD_OSM`); entidades sem essa marca não devem ser removidas. Identidades elétricas `AUXCAD_POSTE` e `AUXCAD_VAO` não devem ser alteradas por esse fluxo.
- O frontend transporta `osmId`/`osmType`. O `*Cancel` de captura é comportamento normal; não pode iniciar desenho com payload parcial.
- Houve trabalho offline de política geométrica: edificações (`EDIFICACAO`) fechadas e barreiras (`BARREIRA`) abertas, com validação de coordenadas. Confirmar nomes e implementação no código antes de alterar.
- Logs que o usuário forneceu mostravam resultados de desenho de vias, calçadas e obstruções, inclusive repetição com totais idênticos, mas foram obtidos antes da correção. São evidência histórica de operação, não prova de idempotência depois da correção.
- O usuário pediu também verificar se as obstruções aparecem no lugar correto. O posicionamento no DWG ainda não foi comprovado em sessão real; um desenho executado e uma contagem de polylines não bastam para confirmar alinhamento geográfico.

### Universalização

- Foi pedido descobrir como consultar ordens no sistema interno Universalização e preparar eventual contrato compartilhável para consumidores CAD, mas sem implementar integração até observar evidência upstream real.
- `.env.example` contém a URL `http://gtecprorio.enelint.global/sistemas/universalizacao/` e comentários que associam credenciais de GOMNET à Universalização. Isso comprova apenas o que consta no modelo local, não autenticação, endpoint ou protocolo do serviço.
- Clientes do SGT (`unifilar/arvore_client.py`) e GOMNET (`sob/sob_gomnet.py`) são sistemas distintos. Não presumir que a Universalização use o mesmo fluxo ou copiar sua autenticação por analogia.
- Foi criado `UNIVERSALIZACAO_DISCOVERY.md` como relatório preliminar, com evidências, limitações e roteiro de captura segura. O contrato técnico upstream permanece incompleto.
- Em sessão posterior, o navegador exibiu interface da aplicação e rótulos `Número Ordem de Projeto`, `Projetos Grupo`, `Status do Projeto` e `Pólo Técnico`. O tráfego observado nessa navegação foi de carregamento GET, com respostas 200 e um redirecionamento 302. Nenhum formulário foi submetido e nenhum corpo de requisição/resposta foi inspecionado.
- Portanto ainda faltam método/rota da consulta, parâmetros enviados, autenticação confirmada, estrutura da resposta, semântica da ordem, paginação e cenários de erro. A interface visível não equivale a captura do contrato.
- Não automatizar login, enumeração ou consulta em lote. Não solicitar/registrar senha, token, cookie, cabeçalho Authorization, session ID, `__VIEWSTATE`, `__EVENTVALIDATION`, `.env` real ou HAR bruto. Compartilhar apenas evidência técnica sanitizada de uma consulta autorizada, removendo valores pessoais/identificadores.
- Não integrar Universalização ao Digital Twin nem persistir no DWG informações externas como endereço/notas sem solicitação e evidência suficientes.

## Estado de validação conhecido

Os seguintes totais são históricos e vieram de diferentes momentos/etapas; não os some nem os apresente como baseline atual:

- DT-02 teve uma execução de suíte documentada como **603 passed, 2 skipped** após correção de coerência de vão órfão.
- Em outro ponto, houve execução **602 passed, 2 skipped, 1 failed** por erro de tipo no teste `DirectTwinExposesGraphDiagnostics` (`PosteDto[]` passado ao construtor que requer `IEnumerable<PosteTwin>`), seguida de tentativas de correção. Um checkpoint posterior relata 603/2 passados, mas builds podem ter sido bloqueados pela DLL em uso pelo AutoCAD.
- Para OSM/obstruções, foi relatada execução offline de **604 passed, 2 skipped**, harness de 30 cenários e testes direcionados 2 passed. Em registros anteriores da OSM-01 foram citados 602/2 e 67 testes direcionados. São estados históricos distintos.
- Builds anteriores de Release registraram `net48` sem erros/warnings e `net8.0-windows` sem erros com dois warnings MSB3277 relativos a `Microsoft.VisualBasic`. Em uma tentativa, cópia da DLL foi bloqueada por AutoCAD ativo (PID 53244); não encerre o processo para contornar bloqueio.
- Antes de declarar teste/build válido, execute no estado atual e registre comando e resultado exatos. Não declarar runtime AutoCAD homologado com base em build, harness, mock ou teste offline.

## Pendências explícitas — não declarar concluídas

| Item | Estado atual conhecido | Evidência necessária |
|---|---|---|
| DT-01H | PENDENTE | Homologação manual controlada no AutoCAD com cópias de DWG |
| OSM-01R | PENDENTE | Repetição real de contexto OSM no AutoCAD, inclusive após salvar/fechar/reabrir |
| Idempotência OSM real | NÃO COMPROVADA | Segunda e terceira execução sem novas geometrias duplicadas |
| Persistência real/XData após reabertura | PENDENTE | Salvar, fechar, reabrir e verificar identidade/autoria OSM |
| Posicionamento real das obstruções | PENDENTE | Comparação visual/espacial controlada contra contexto conhecido |
| Runtime AutoCAD/WebView2 | PENDENTE como homologação integral | Teste manual assistido; não abrir sessão automaticamente |
| Contrato upstream Universalização | INCOMPLETO | Uma consulta autorizada manual, com evidência sanitizada de requisição e resposta |
| Integração Universalização | NÃO IMPLEMENTADA | Só decidir depois de contrato confirmado e aprovação de escopo |

## Estado local do worktree registrado

Na verificação mais recente disponível, `git status --short --branch` mostrou branch `dev` e várias mudanças existentes. A listagem incluía alterações em `CAC.md`, `RAG/MEMORY.md`, `mapa_cad_paleta/CadBridge.cs`, `MapaControl.xaml.cs`, `PaletteHost.cs`, arquivos Web OSM e testes; também arquivos novos, incluindo baselines, dossiês, `DigitalTwin.cs`, `OsmGeometryPolicy.cs`, harness e relatório Universalização. Isso não é necessariamente o estado atual: execute `git status --short --branch` antes de editar.

`git diff --check` já apontou whitespace/linhas finais em arquivos modificados (`CAC.md`, `MapaControl.xaml.cs`, `web/tracado.js`). Não corrija esses itens incidentais sem necessidade e sem separar claramente o escopo.

## Documentos e código para consultar primeiro

- `UNIVERSALIZACAO_DISCOVERY.md` — evidências e limitações da descoberta Universalização.
- `mapa_cad_paleta/DOSSIE_DIGITAL_TWIN_MAPA_CAD_PALETA.md` — histórico/decisões DT-01/DT-02; conferir os fatos contra código e execuções recentes.
- `mapa_cad_paleta/DigitalTwin.cs` — read model, builder, grafo, consultas e diagnósticos.
- `mapa_cad_paleta/CadBridge.cs` — scanner/reconciliador e contratos de entrada; preservar alterações preexistentes.
- `mapa_cad_paleta/OsmGeometryPolicy.cs`, `mapa_cad_paleta/MapaControl.xaml.cs`, `mapa_cad_paleta/PaletteHost.cs` e `mapa_cad_paleta/web/` — fluxo OSM/CAD/WebView2; verificar a superfície completa antes de mexer.
- `tests/test_digital_twin_dt02.py`, `tests/dt02_harness/` e testes Python de mapa — validação offline.
- `mapa_cad_paleta/BASELINE_OPERACIONAL.md`, `BASELINE_ESTRATEGICO.md`, `COMMANDS_BASELINE.md` e `REGRESSION_MATRIX.md` — baselines e matriz; conferir se continuam atuais.
- `RAG/MEMORY.md` — contexto persistente do projeto; não aceitar afirmações sem validar data/fonte.

## Instruções de trabalho para a próxima IA

1. Comece por `git status --short --branch`, `git branch --show-current` e `git log -n 5 --oneline`; preserve todas as mudanças.
2. Identifique qual é o pedido da sessão corrente. Não retome automaticamente uma fase apenas porque aparece neste histórico.
3. Para correções, leia os call sites e contratos existentes e siga padrões do repositório. Faça alterações cirúrgicas e relacionadas, sem refatorações incidentais.
4. Rode os testes mínimos que cobrem a mudança e, quando apropriado, suíte completa e builds de ambos os TFMs. Relate bloqueios externos como bloqueios; não os disfarce de sucesso.
5. Não use mocks para declarar homologação de AutoCAD ou Universalização. Separe claramente validação offline, build e runtime real.
6. Não iniciar DT-03 automaticamente. Não executar OSM-01R, DT-01H nem testar posicionamento real sem ambiente/sessão manual controlada.
7. Não criar integração Universalização antes de uma captura autorizada e sanitizada. Não ler `.env` real nem registrar segredos ou dados pessoais.
8. Não fazer commit, reset, clean, checkout destrutivo ou exclusão ampla sem solicitação explícita.

## Backlog sugerido (sem autorização para execução automática)

1. Corrigir/confirmar eventuais bloqueios remanescentes de testes/build DT-02 e atualizar o dossiê com resultados realmente reproduzidos.
2. Executar DT-01H e OSM-01R manualmente, com usuário presente, cópias de DWG e registro seguro das evidências.
3. Verificar em CAD controlado o posicionamento das obstruções; validar coordenadas/fuso e geometria da fonte sem assumir que contagem de entidades prova localização correta.
4. Solicitar captura manual autorizada e sanitizada de uma consulta da Universalização; atualizar descoberta e só então avaliar contrato e integração.
5. Manter OSM/Digital Twin e Universalização como domínios separados; não adicionar contexto externo ao DWG sem decisão explícita.
