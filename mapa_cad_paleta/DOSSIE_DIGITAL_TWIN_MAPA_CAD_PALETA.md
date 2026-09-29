# DOSSIE DE ARQUITETURA-ALVO: DIGITAL TWIN OPERACIONAL DO CROQUI DE CAMPO
## Modulo: mapa_cad_paleta -- Projeto aux cad

**Versao do Dossie:** 1.0
**Produzido em:** 2026-09-28
**Base de evidencia:** codigo-fonte auditado (CadBridge.cs x2075 linhas, app.js x873 linhas, MapaControl.xaml.cs), testes (59/59 PASS), builds Release limpos.
**Status do modulo na data:** IMPLEMENTACAO OSM IDEMPOTENTE IMPLEMENTADA . TESTES OFFLINE PASS . RUNTIME AUTOCAD PARCIALMENTE VALIDADO . RETESTE POS-CORRECAO PENDENTE.

---

## SUMARIO EXECUTIVO

## ADENDO — BASELINE OPERACIONAL (FASE DE PROTEÇÃO)

Este dossiê é uma proposta arquitetural inicial e não uma especificação definitiva. A auditoria operacional de 2026-09-27/28 reclassificou suas decisões à luz do código e dos testes existentes. O módulo deve ser evoluído sem substituir os fluxos atuais.

Os contratos protegidos estão detalhados em [BASELINE_OPERACIONAL.md](./BASELINE_OPERACIONAL.md), [COMMANDS_BASELINE.md](./COMMANDS_BASELINE.md) e [REGRESSION_MATRIX.md](./REGRESSION_MATRIX.md). Em resumo, não podem regredir: abertura da paleta, mapa/posicionamento, inserção de postes, traçado de vãos, IDs/XData v2, scan/reconstrução, COPY/reconciliação e Undo.

Nesta fase, `XData v3`, coordenadas duplicadas, timestamps/proveniência/confiança no XData, sidecar, banco e `ObjectModified` permanecem prematuros ou dependentes de validação. O runtime AutoCAD não foi executado; portanto os testes offline não são homologação operacional.

O princípio passa a ser **first, do no harm**: qualquer evolução deve declarar o que muda, o que permanece, o que pode quebrar e como a regressão será detectada e revertida.

## DT-01R — RESULTADO DA HOMOLOGAÇÃO DE INTEGRAÇÃO

**Data:** 2026-09-27/28  
**Ambiente:** Windows; branch `dev`; .NET SDK 10.0.302; AutoCAD 2026. A sessão AutoCAD foi executada manualmente para o fluxo OSM/WebView2.  
**DWGs utilizados:** o desenho ativo da sessão manual foi usado para o fluxo OSM. Os arquivos de fixture anteriormente inventariados (`documentos/PRANCHA LIGHT.dwg`, `documentos/TESTE_POSTE_E_VIAS.dwg` e `modelos/prancha.dwg`) não foram alterados nesta execução.

### Estado inicial

O worktree já continha alterações preexistentes. Elas foram preservadas. O fluxo permanece `EscanearDwgResultado -> DigitalTwinBuilder -> DigitalTwin`; o builder não contém AutoCAD, WebView2, transações, escrita XData, geração de IDs ou reparos.

### Matriz de cenários

| Cenário | Offline/estático | AutoCAD | Resultado |
|---|---|---|---|
| H01 DWG limpo | VALIDADO por modelo vazio/contrato | NÃO VALIDADO | sem evidência runtime |
| H02 postes existentes | VALIDADO por DTO/modelo e testes de identidade | NÃO VALIDADO | sem DWG aberto |
| H03 vãos e topologia | VALIDADO por modelo/relações/diagnósticos | NÃO VALIDADO | sem DWG aberto |
| H04 legado | VALIDADO pelo contrato do scanner existente | NÃO VALIDADO | sem DWG legado aberto |
| H05 XData v2 | VALIDADO por preservação de DTO/contrato | NÃO VALIDADO | schema não migrado |
| H06 XData ausente | VALIDADO por diagnóstico sem geração de ID | NÃO VALIDADO | sem entidade real |
| H07 duplicidade | VALIDADO por diagnósticos `TWIN_DUPLICATE_*` | NÃO VALIDADO | sem DWG inconsistente |
| H08 vão órfão | VALIDADO por `TWIN_ORPHAN_VAO` | NÃO VALIDADO | sem DWG inconsistente |
| H09 inserção de poste | NÃO VALIDADO offline como execução | NÃO VALIDADO | fluxo não executado |
| H10 inserção de vão | NÃO VALIDADO offline como execução | NÃO VALIDADO | fluxo não executado |
| H11 COPY | VALIDADO somente por testes/contratos anteriores | NÃO VALIDADO | sem operação CAD real |
| H12 ERASE | VALIDADO somente por testes/contratos anteriores | NÃO VALIDADO | sem operação CAD real |
| H13 Undo | VALIDADO somente por testes/contratos anteriores | NÃO VALIDADO | sem operação CAD real |
| H14 salvar/fechar/reabrir | NÃO VALIDADO | NÃO VALIDADO | sem sessão AutoCAD |
| H15 paleta/WebView2 | VALIDADO por build/assets/contrato | PARCIALMENTE VALIDADO | `MAPAPALETA` carregou e recebeu mensagens do mapa |
| H16 OSM | VALIDADO por testes existentes | PARCIALMENTE VALIDADO | consultas OSM converteram e desenharam 170, 53 e 54 elementos |
| H17 Snyder/coordenadas | VALIDADO por testes matemáticos existentes | PARCIALMENTE VALIDADO | payloads UTM no fuso 23 chegaram ao CAD com coordenadas observáveis |

### Evidência adicional de runtime OSM/Snyder

O console registrou a abertura de `OSMPALETA`/`MAPAPALETA`, payloads no fuso UTM 23 e desenho efetivo no CAD:

- `vias=18; calcadas=5; obstrucoes=75`, resultando em `polylinesCriadas=170` e `verticesCriados=1051`;
- `vias=7; calcadas=7; obstrucoes=11`, resultando em `polylinesCriadas=53` e `verticesCriados=283`;
- nova consulta com `vias=7; calcadas=8; obstrucoes=11`, resultando em `polylinesCriadas=54` e `verticesCriados=300`.

Também foi observada a mensagem `Clique em um ponto no DWG ...: *Cancel*`. Isso caracteriza cancelamento explícito da captura interativa, não erro de conversão ou falha do AutoCAD.

### Defeito observado

O mesmo payload OSM (`18/5/75`) foi enviado duas vezes e produziu duas criações de 170 polilinhas. O método `DesenharElementosUrbanos` não era idempotente: cada mensagem acrescentava novas entidades nas camadas urbanas, sem identificar ou substituir um desenho OSM anterior. Essa evidência confirmou risco de duplicação quando o usuário acionava novamente o desenho para a mesma área.

### Correção de idempotência implementada

A correção foi implementada após a evidência de runtime:

- o frontend transporta `osmId` e `osmType` em cada elemento derivado de um `way`;
- o CAD grava metadado isolado na RegApp `AUXCAD_OSM`;
- a identidade lógica é `osmType:osmId:categoria`, sem usar Handle, ordem do array ou posição aproximada;
- o fingerprint SHA-256 do item permite ignorar um reenvio com conteúdo idêntico;
- um item com a mesma identidade e conteúdo diferente atualiza somente entidades que já possuem `AUXCAD_OSM`;
- entidades sem `AUXCAD_OSM` nunca são apagadas, inclusive as geometrias OSM criadas por versões anteriores;
- itens sem `osmId` continuam sendo desenhados, mas são explicitamente registrados como não reconciliáveis.

Assim, a operação não apaga layers inteiras nem entidades arbitrárias. A limpeza de duplicatas legadas sem metadado permanece deliberadamente pendente e requer procedimento separado.

### Defeitos e correções anteriores

Além da duplicação OSM descrita acima, não foi observado outro defeito no fluxo executado. A correção implementada é limitada ao ciclo de vida dos elementos urbanos e não altera comandos elétricos, protocolo de postes/vãos, Snyder, inserção, traçado, Undo, COPY, ERASE ou XData v2.

### Testes automatizados e build

- Baseline anterior: **59/59**.
- DT-01: **7/7** testes de contrato/isolamento.
- Resultado atual: **66/66** em `py -m pytest tests\test_mapa_paleta.py tests\test_mapa_postes.py -q`.
- `dotnet build mapa_cad_paleta\MapaCadPaleta.csproj -c Release --no-restore`: **0 erros** em `net8.0-windows` e `net48`.
- Warnings: os mesmos 2 `MSB3277` de conflito de versões de `Microsoft.VisualBasic`; nenhum warning novo atribuído ao DT-01.
- Após a correção: **67/67** testes Python; `net48` compilado sem warnings/erros; `net8.0-windows` compilado com os mesmos 2 warnings `MSB3277` e 0 erros.

### Limitações e próxima ação

O fluxo OSM/WebView2 foi executado no AutoCAD antes da correção. O reteste pós-correção ainda precisa ser feito em uma cópia de DWG: primeiro desenho, repetição idêntica, contexto diferente, cancelamento e salvar/fechar/reabrir. A captura cancelada (`*Cancel`) continua comportamento normal e não gera desenho.

**STATUS DO DIGITAL TWIN**

- Modelo DT-01: **IMPLEMENTADO**
- Integração offline: **VALIDADA**
- Integração AutoCAD: **PARCIALMENTE VALIDADA; RETESTE DE IDEMPOTÊNCIA PENDENTE**
- Persistência: **NÃO VALIDADA nesta fase**
- Sincronização bidirecional: **NÃO IMPLEMENTADA**
- DWG como fonte de verdade: **SIM**

## DT-01 — PROJEÇÃO SEMÂNTICA IMPLEMENTADA

### Objetivo

DT-01 adiciona um read-model do Digital Twin construído a partir de `EscanearDwgResultado`, sem substituir o DWG, sem alterar o scanner e sem escrever no AutoCAD.

### Arquitetura implementada

`DigitalTwinBuilder.Build(...)` copia o estado já reconhecido pelo `CadBridge` para:

- `DigitalTwin`: versão do modelo, origem da construção, coleções e diagnósticos;
- `PosteTwin`: `DomainId`, `Handle`, número, coordenadas XY, atributos já existentes e `OperationId`;
- `VaoTwin`: `VaoId`, `Handle`, referências lógicas, geometria XY, metragem, tipo de rede e `OperationId`;
- `TwinTopologyRelation`: relações do scan por IDs;
- `TwinDiagnostic`: diagnósticos existentes e inconsistências observadas pelo builder.

O eixo Z do poste permanece ausente (`null`) porque não é fornecido pelo `PosteDto`. Proveniência limitada a `DWG_SCAN` é a única origem objetivamente conhecida nesta camada. Não são fabricados GPS, confiança, timestamp, autor ou observação de campo.

### Diagnósticos DT-01

O builder observa e registra `TWIN_MISSING_POSTE_ID`, `TWIN_MISSING_VAO_ID`, `TWIN_DUPLICATE_POSTE_ID`, `TWIN_DUPLICATE_VAO_ID` e `TWIN_ORPHAN_VAO`. Ele não repara, remapeia ou persiste qualquer entidade.

### Limitações

DT-01 não implementa sincronização bidirecional, `ObjectModified`, sidecar, banco, GeoJSON central, migração de XData ou comando novo. Os testes do modelo são de contrato/isolamento no conjunto Python; a homologação AutoCAD continua pendente.

O modulo mapa_cad_paleta nasceu como uma paleta de desenho CAD auxiliar: o tecnico de campo clica em um mapa OSM dentro do AutoCAD, coloca postes georreferenciados e desenha vaos de rede eletrica. O resultado e um arquivo DWG com geometria 2.5D e anotacoes tecnicas.

A evolucao dos ultimos sprints adicionou **identidade persistente por GUID** (DomainId / VaoId / OperationId), **topologia explicita** (PosteOrigemId / PosteDestinoId nos vaos), **scan reconciliador** (LerEstadoDwg -> ReconciliarTopologiaDwg -> ExecutarReparosDwg) e **Undo baseado em identidade** -- transformando o DWG em um grafo topologico auditavel.

Este dossie responde:
1. O que o sistema e hoje, com evidencia no codigo.
2. O que o sistema precisa ser para ser um Digital Twin operacional do croqui de campo.
3. Como chegar la de forma incremental, sem reescrita total, preservando o investimento existente.

---

## PARTE 1 -- ESTADO ATUAL (SOURCE OF TRUTH: CODIGO)

### 1.1 Entidades do Dominio Persistidas no DWG

| Entidade | RegApp XData | Campos Persistidos | Schema Ver |
|---|---|---|---|
| Poste | AUXCAD_POSTE | schemaVersion, id (DomainId GUID), domainId, numero, tipoPoste, estruturaMT, estruturaBT, equipamentos, temTrafo, potenciaTrafo, fusoUtm, operationId | v2 |
| Vao | AUXCAD_VAO | schemaVersion, vaoId (GUID), posteOrigemId, posteDestinoId, tipoRede, textoVao, operationId | v2 |

Evidencia: CadBridge.cs L1709-1780 (GravarXDataPoste, GravarXDataVao).

### 1.2 Geometria Persistida no DWG

| Camada | Tipo de Entidade | Semantica |
|---|---|---|
| POSTES | BlockReference (bloco POSTE_) | Simbolo topologico do poste (Z = 0.0) |
| POSTES_NUMERO | BlockReference (bloco PONTO) | Numero visual do poste |
| POSTES_DESCRICAO | DBText | Descricao tecnica (tipo, estrutura, trecho) |
| CABOS_BT | Polyline | Tracado do vao de Baixa Tensao |
| CABOS_MT | Polyline | Tracado do vao de Media Tensao |
| CABOS_TEXTO | DBText | Legenda do vao |

Constraint arquitetural: Z = 0.0 em todas as entidades. O sistema e estritamente 2.5D.

### 1.3 Fluxo de Execucao Real (Fim-a-Fim Verificado)

```
[Tecnico]
    |  clica no mapa OSM (Leaflet / WebView2)
    v
[app.js]
    |  gera domainId = gerarGuid()      <- RFC4122 v4 otimista
    |  postMessage -> C# host
    v
[MapaControl.xaml.cs]
    |  CoreWebView2.WebMessageReceived
    |  -> InserirPoste / InserirVao / EscanearDwg / DesfazerUltimaOperacao
    v
[CadBridge.cs]
    |  valida GUID (reemite novo se invalido)   <- autoridade C#
    |  LockDocument + Transaction
    |  GravarXDataPoste / GravarXDataVao
    |  retorna {success, domainId / vaoId, message}
    v
[MapaControl.xaml.cs]
    |  PostWebMessageAsJson -> resultado
    v
[app.js]
    |  sincroniza domainId / vaoId no TracadoState  <- ID canonico confirmado
    |  renderiza marker/polilinha no mapa
```

Scan (EscanearDwg):

```
[CadBridge.EscanearDwg]
    |  LerEstadoDwg()        <- READ-ONLY: le XData, monta PosteDto / VaoDto
    |  ReconciliarTopologiaDwg()  <- diagnostico: valida PosteOrigemId/Destino, detecta orfaos
    |  ExecutarReparosDwg()  <- WRITE: remapeia GUID colisoes de COPY, regrava XData
    v
    retorna EscanearDwgResultado { Postes, Vaos, Relacoes, Diagnostics, Statistics }
    v
[app.js] -> estado_dwg (v2, autoritativo) -> reconstruirTracadoDoDwg()
         -> postes_dwg (v1, fallback legado, so se estado_dwg nao chegar em 500ms)
```

Undo:

```
DesfazerUltimaOperacao(domainId?, operationId?)
    |  prioridade: OperationId > DomainId > fallback visual (legado)
    |  apaga entidades por Handle registrado em _historicoOperacoes
    |  retorna contagem de entidades removidas
```

### 1.4 Contratos de Interface (postMessage JSON)

| Direcao | action | Campos Chave |
|---|---|---|
| JS -> C# | inserir_poste | id, operationId, x, y, numero, tipoPoste, etc. |
| JS -> C# | inserir_vao | vaoId, operationId, posteOrigemId, posteDestinoId, tipoRede, pontos |
| JS -> C# | escanear_dwg | (sem campos extras) |
| JS -> C# | desfazer | domainId?, operationId? |
| C# -> JS | resultado_insercao | success, domainId, message |
| C# -> JS | resultado_vao | success, vaoId, message |
| C# -> JS | estado_dwg | postes[], vaos[], relacoes[], diagnostics[], statistics |
| C# -> JS | resultado_desfazer | success, message, removidos |

### 1.5 Diagnosticos Emitidos pelo Scanner

| Codigo | Severidade | Descricao |
|---|---|---|
| XDATA_NOT_FOUND | WARNING | Entidade no layer correto sem XData |
| LEGACY_POSTE | INFO | Poste sem GUID, ID prefixado com LEGACY_ |
| COPY_DETECTED | WARNING | Colisao de DomainId detectada; novo GUID emitido |
| COPY_SET_REPAIRED | INFO | COPY de conjunto com remapeamento conexo executado |
| COPY_SET_UNCERTAIN | WARNING | COPY parcial: apenas uma ponta do vao foi copiada |
| UNSUPPORTED_XDATA_VERSION | ERROR | schemaVersion > 2 encontrada no DWG |
| ORPHAN_VAO | WARNING | Vao cujo PosteOrigemId ou PosteDestinoId nao existe |
| AMBIGUOUS_GEOMETRY | WARNING | Resolucao geometrica com multiplas correspondencias possiveis |

### 1.6 Lacunas Atuais (Evidencia no Codigo)

| # | Lacuna | Evidencia |
|---|---|---|
| L-01 | Sem persistencia de coordenadas reais no XData -- o DomainId aponta a entidade mas as coordenadas ficam apenas na geometria CAD. | GravarXDataPoste nao grava x, y. |
| L-02 | Sem campo dataHora no XData -- nao ha registro de quando o poste foi inserido ou modificado. | Schema v2 nao inclui timestamp. |
| L-03 | Sem campo fonte/proveniencia -- nao ha distincao entre dado inserido manualmente ou importado de GPS. | Schema v2 nao inclui source. |
| L-04 | Sem campo confianca/qualidade -- o sistema nao distingue GPS sub-metro de estimativa visual. | Nenhum campo de qualidade. |
| L-05 | Sem versionamento de estado -- edicao nativa no AutoCAD e invisivel para o sistema. | Sem listener ObjectModified. |
| L-06 | _historicoOperacoes e in-memory -- ao fechar o AutoCAD o historico de Undo e perdido. | private static readonly List em memoria. |
| L-07 | Sem exportacao canonica -- nao ha comando para exportar o estado como GeoJSON. | Nenhum metodo de serializacao para formato aberto. |
| L-08 | Geometria dos vaos nao esta persistida no XData -- apenas referencias por GUID. | GravarXDataVao nao grava os vertices. |

---

## PARTE 2 -- VISAO DE PRODUTO: DIGITAL TWIN OPERACIONAL

### 2.1 O Que Significa "Digital Twin" Neste Contexto

Um Digital Twin de rede eletrica de distribuicao, neste escopo, e um **modelo computacional persistente, autoritativo e sincronizavel** da rede fisica, que:

1. Representa cada ativo fisico com identidade unica e estavel.
2. Preserva proveniencia: de onde veio cada dado.
3. Mantem topologia explicita: grafo computacionalmente consultavel.
4. Rastreia estado temporal: historico de criacao, modificacao e desativacao.
5. Sincroniza com a realidade de forma controlada.
6. Exporta para padroes abertos: GeoJSON, GeoPackage, GraphML.
7. Distingue camadas de conhecimento: croqui != GPS != sistema de gestao.

### 2.2 O Que o Modulo NAO Precisa Ser

- NAO e um sistema de gestao de rede (SIGEL, SGRD, SAP PM).
- NAO e um sistema GIS completo (QGIS, ArcGIS).
- NAO precisa ter banco de dados externo -- o DWG e o banco primario.
- NAO e 3D. A restricao Z = 0.0 (2.5D) e correta e deve ser mantida.

### 2.3 Separacao Conceitual: Realidade x Twin x CAD

```
REALIDADE FISICA
    Poste 7m/600 daN na Rua Boa Vista n. 312
    Vao MT 34,5kV em cabo CA 70mm2 entre poste A e poste B
         |
         | levantamento de campo (GPS/croqui)
         v
DIGITAL TWIN (Modelo de Dominio)
    PosteId: GUID . Coordenada WGS84 . Tipo . Estrutura
    VaoId: GUID . PosteOrigemId . PosteDestinoId . TipoRede . Cabo
    Proveniencia: fonte, confianca, autor, timestamp
    Topologia: grafo adjacencia Postes <-> Vaos
         |                         |
         | render/edicao            | exportacao
         v                         v
REPRESENTACAO CAD          FORMATOS ABERTOS
DWG: BlockRef, Polyline,   GeoJSON, GeoPackage,
DBText, XData              GraphML, CSV, CIM
```

Regra fundamental: o Twin e autoritativo. O CAD e uma representacao renderizada do Twin.
O XData no DWG e o mecanismo de persistencia do Twin dentro do ambiente CAD -- nao e o Twin em si.

---

## PARTE 3 -- MODELO CONCEITUAL DO TWIN

### 3.1 Entidades de Dominio Alvo

#### PosteTwin

```
PosteTwin {
  domainId:        GUID (RFC4122 v4, imutavel apos criacao)
  versao:          int (incrementa a cada modificacao)

  longitude:       float64 (WGS84, graus decimais)
  latitude:        float64 (WGS84, graus decimais)
  precisao_m:      float32 (erro estimado em metros; 0.0 = desconhecido)
  fusoUtm:         int

  numero:          string
  tipoPoste:       string
  estruturasMt:    string[]
  estruturasBt:    string[]
  equipamentos:    string[]
  temTrafo:        bool
  potenciaTrafo:   string
  cargaTri:        string

  fonte:           enum { CROQUI_CAMPO, GPS_LEVANTAMENTO, IMPORTACAO_SIGEL, MANUAL_CAD }
  confianca:       enum { ALTA, MEDIA, BAIXA, NAO_VERIFICADO }
  autor:           string
  criadoEm:        DateTime (UTC)
  modificadoEm:    DateTime (UTC)
  operationId:     GUID

  status:          enum { ATIVO, REMOVIDO, SUBSTITUIDO }
  substituido_por: GUID?
}
```

#### VaoTwin

```
VaoTwin {
  vaoId:           GUID (RFC4122 v4, imutavel)
  versao:          int

  posteOrigemId:   GUID
  posteDestinoId:  GUID

  vertices:        Point2D[] (WGS84; Z = 0.0)
  comprimento_m:   float64

  tipoRede:        enum { MT, BT, MT_BT }
  tensao_kV:       float32?
  cabo:            string?
  textoVao:        string

  fonte:           enum { ... }
  confianca:       enum { ... }
  autor:           string
  criadoEm:        DateTime (UTC)
  modificadoEm:    DateTime (UTC)
  operationId:     GUID

  status:          enum { ATIVO, REMOVIDO }
}
```

#### Grafo Topologico

```
RedeTopologica {
  postes:      Map<DomainId, PosteTwin>
  vaos:        Map<VaoId, VaoTwin>
  adjacencia:  Map<DomainId, VaoId[]>

  vizinhos(posteId):       PosteTwin[]
  vaosDePoste(posteId):    VaoTwin[]
  caminhoEntre(a, b):      VaoTwin[]
  componentesConexas():    Set<DomainId>[]
  postes_orfaos():         PosteTwin[]
  vaos_invalidos():        VaoTwin[]
}
```

### 3.2 Proveniencia e Confianca

| fonte | confianca | Significado |
|---|---|---|
| CROQUI_CAMPO | MEDIA | Tecnico desenhou de memoria/estimativa visual |
| GPS_LEVANTAMENTO | ALTA | Coordenada medida com GPS sub-metro em campo |
| IMPORTACAO_SIGEL | ALTA | Dado importado do sistema oficial de gestao |
| MANUAL_CAD | BAIXA | Inserido manualmente no AutoCAD sem referencia geografica |

Regra de fusao: quando dois dados descrevem o mesmo ativo, prevalece o de maior confianca. Empate: prevalece o mais recente.

### 3.3 Identidade e Estabilidade

| Campo | Mutabilidade | Regra |
|---|---|---|
| domainId / vaoId | Imutavel | Nunca reatribuir apos criacao; sobrevive a COPY, Move, Edit |
| operationId | Por operacao | Um por acao de insercao/edicao; usado para Undo atomico |
| versao | Monotonica | Incrementa a cada modificacao; permite deteccao de conflito |
| numero (visual) | Mutavel | Pode ser editado pelo tecnico; nao e identidade |

---

## PARTE 4 -- LACUNAS x ACOES DE EVOLUCAO (PLANO INCREMENTAL)

### 4.1 Mapeamento de Lacunas para Implementacoes

| Lacuna | Impacto no Twin | Acao Necessaria | Prioridade |
|---|---|---|---|
| L-01: sem coordenadas no XData | Twin nao e exportavel sem ler geometria | Gravar longitude, latitude, precisao_m no XData v3 | ALTA |
| L-02: sem timestamp | Twin nao tem linha do tempo | Gravar criadoEm ISO-8601 no XData v3 | ALTA |
| L-03: sem proveniencia | Twin nao distingue croqui de GPS | Gravar fonte e confianca no XData v3 | ALTA |
| L-04: sem qualidade | Twin nao distingue precisao de localizacao | Gravar precisao_m (float, metros) no XData v3 | MEDIA |
| L-05: sem deteccao de edicao nativa | Twin pode ficar desatualizado | Listener ObjectModified + scan periodico | MEDIA |
| L-06: historico de Undo in-memory | Undo perdido ao reiniciar AutoCAD | Serializar _historicoOperacoes em sidecar .oxcad.json | MEDIA |
| L-07: sem exportacao canonica | Twin nao interopera com outros sistemas | Implementar comando EXPORTAR_REDE -> GeoJSON | MEDIA |
| L-08: vertices do vao nao no XData | Topologia nao e auto-contida | Gravar vertices (JSON array) no XData do vao v3 | BAIXA |

### 4.2 Estrategia de Schema XData v3

A migracao para XData v3 deve ser retrocompativel:

- XDATA_SCHEMA_VERSION = 3 (constante incrementada).
- O scanner ja detecta schemaVer > XDATA_SCHEMA_VERSION e emite UNSUPPORTED_XDATA_VERSION. Ao atualizar a constante para 3, o v2 passa a ser legado compativel.
- Novos campos sao opcionais na leitura (logica TryGetProperty ja em uso).
- Postes legados (v1/v2) continuam funcionando; so postes v3 terao coordenadas auto-contidas no XData.

Schema v3 Poste (adicoes sobre v2):

```json
{
  "schemaVersion": 3,
  "id": "<GUID>",
  "domainId": "<GUID>",
  "versao": 1,
  "longitude": -48.5432,
  "latitude": -23.1234,
  "precisao_m": 5.0,
  "fonte": "CROQUI_CAMPO",
  "confianca": "MEDIA",
  "autor": "",
  "criadoEm": "2026-09-28T15:00:00Z",
  "modificadoEm": "2026-09-28T15:00:00Z"
}
```

Schema v3 Vao (adicoes sobre v2):

```json
{
  "schemaVersion": 3,
  "vaoId": "<GUID>",
  "versao": 1,
  "comprimento_m": 42.5,
  "cabo": "CA 70mm2",
  "fonte": "CROQUI_CAMPO",
  "confianca": "MEDIA",
  "criadoEm": "2026-09-28T15:00:00Z",
  "modificadoEm": "2026-09-28T15:00:00Z"
}
```

### 4.3 Roadmap Incremental (Sprints)

Cada sprint e independente e nao requer o anterior para manter o sistema funcional.

#### Sprint DT-01 -- XData v3 com Proveniencia e Timestamp (Prioridade ALTA)

Escopo:
- Incrementar XDATA_SCHEMA_VERSION para 3.
- Adicionar campos longitude, latitude, criadoEm, modificadoEm, fonte, confianca, versao ao XData de Poste.
- Adicionar criadoEm, modificadoEm, fonte, confianca, comprimento_m, versao ao XData de Vao.
- Atualizar GravarXDataPoste e GravarXDataVao para incluir novos campos.
- Atualizar LerEstadoDwg para ler novos campos (opcionais, TryGetProperty).
- Atualizar PosteDto e VaoDto com novos campos.
- Atualizar app.js para exibir fonte e confianca no tooltip/popup do mapa.
- Atualizar testes.

Entregavel de aceitacao: scan de DWG existente (v2) nao quebra; insercao de novo poste grava v3 com coordenadas e timestamp; EscanearDwgResultado.Postes[i].Longitude != 0 para postes novos.

#### Planejamento historico -- Sprint DT-02 (exportacao GeoJSON proposta; escopo substituido)

Esta proposta antecede a DT-02 implementada abaixo e nao representa funcionalidade entregue. O escopo vigente de DT-02 e o grafo semantico somente em memoria; exportacao GeoJSON e persistencia continuam fora desta fase.

Escopo:
- Novo comando AutoCAD EXPORTAR_REDE_GEOJSON.
- Serializa EscanearDwgResultado como FeatureCollection GeoJSON.
  - Postes -> Feature Point com todas as propriedades do PosteDto.
  - Vaos -> Feature LineString (vertices da Polyline lidos do DWG).
- Salva em arquivo .geojson ao lado do .dwg ativo.
- Exposicao via botao na paleta "Exportar Rede".

Entregavel de aceitacao: GeoJSON valido por geojsonlint.com; postes com coordenadas corretas; vaos com geometria da Polyline; propriedades incluem domainId, fonte, confianca.

#### Sprint DT-03 -- Persistencia do Historico de Undo

Escopo:
- Serializar _historicoOperacoes em arquivo sidecar <dwgname>.oxcad.json ao lado do DWG.
- Carregar o sidecar ao inicializar o modulo se o DWG ja tiver um historico.
- Limitar o historico a 500 operacoes (FIFO).

Entregavel de aceitacao: inserir poste, salvar DWG, fechar/reabrir AutoCAD, executar Undo -> poste removido.

#### Sprint DT-04 -- Deteccao de Modificacao Nativa

Escopo:
- Subscrever Database.ObjectModified para entidades nas layers POSTES, CABOS_BT, CABOS_MT.
- Quando detectado, marcar o poste/vao como modificadoEm = UtcNow e incrementar versao.
- Emitir diagnostico NATIVE_EDIT_DETECTED no proximo scan.
- Nao fazer escrita automatica no XData durante o evento (risco de transacao aninhada).

Entregavel de aceitacao: mover um poste nativamente no AutoCAD -> proximo EscanearDwg retorna diagnostics com NATIVE_EDIT_DETECTED para aquele poste.

#### Sprint DT-05 -- Consulta Topologica no Frontend

Escopo:
- Implementar RedeTopologica em JavaScript no app.js usando o TracadoState.
- Expor no mapa: clique em poste -> lista vaos incidentes -> lista postes vizinhos.
- Destacar componente conexa (BFS) ao clicar em "Mostrar Trecho".
- Nao requer mudanca no backend C#.

Entregavel de aceitacao: clique em poste -> painel lateral exibe vizinhos e vaos; "Mostrar Trecho" destaca graficamente todos os elementos do subgrafo conexo.

---

## PARTE 5 -- RESTRICOES E DECISOES DE NAO-FAZER

### 5.1 Restricoes Preservadas

| Restricao | Justificativa |
|---|---|
| Z = 0.0 (2.5D) | O croqui de campo e planimétrico. Altimetria nao e levantada no fluxo atual. |
| DWG como persistencia primaria | O AutoCAD e o ambiente de trabalho do tecnico. Banco externo obrigatorio quebraria o fluxo offline. |
| Sem CIM/IEC 61968 nesta fase | Relevante para SCADA/SGRD, fora do escopo do croqui de campo. |
| Sem telemetria em tempo real | Digital Twin != SCADA. Este Twin e do croqui, nao do estado operacional. |
| Sem banco externo nos sprints DT-01 a DT-05 | A proposta original de exportacao GeoJSON nao faz parte da DT-02 vigente; o grafo atual e somente em memoria. |

### 5.2 Decisoes de Nao-Fazer Agora

- NAO usar GUID v5: GUID v4 ja esta implementado; GUID v5 exigiria chave natural estavel.
- NAO adicionar servidor REST/API no AutoCAD: paleta WPF com WebView2 ja e o canal de comunicacao.
- NAO implementar merge/conflito de DWGs: problema CRDT fora do escopo.
- NAO fazer migracao automatica de v2 para v3 em lote: migracao deve ser lazy; forcada em massa e risco alto.

---

## PARTE 6 -- CRITERIOS DE HOMOLOGACAO DO TWIN

### 6.1 Homologacao Offline

- [ ] Schema XData v3 definido e documentado.
- [ ] GravarXDataPoste / GravarXDataVao gravam todos os campos v3.
- [ ] LerEstadoDwg le campos v3 sem quebrar ao encontrar v2 ou v1.
- [ ] PosteDto / VaoDto tem campos de proveniencia.
- [ ] 100% dos testes relevantes passam (cobertura >= 80%).
- [ ] Build Release net8.0-windows e net48 com 0 erros.

### 6.2 Homologacao Assistida (Com AutoCAD Runtime)

- [ ] Inserir poste via paleta -> inspecionar XData com XLIST no AutoCAD -> verificar GUID, longitude, latitude, fonte, criadoEm.
- [ ] EscanearDwg em DWG com postes v2 e v3 -> sem erros, diagnosticos corretos.
- [ ] Exportar GeoJSON -> abrir no QGIS ou geojsonlint.com -> feicoes corretas.
- [ ] Desfazer apos reiniciar AutoCAD (Sprint DT-03) -> poste removido.
- [ ] Mover poste nativamente -> proximo scan -> NATIVE_EDIT_DETECTED no diagnostico.

### 6.3 Criterio de Rejeicao

- domainId diferente do id lido pelo XLIST para o mesmo poste.
- GeoJSON com coordinates: [0, 0] para postes inseridos via paleta.
- Scan de DWG v2 emite erro (nao diagnostico) -- deve ser retrocompativel.
- Compilacao com avisos CS860x.
- Qualquer teste previamente passando quebrando apos as mudancas.

---

## PARTE 7 -- APENDICES

### 7.1 Inventario de Arquivos do Modulo

| Arquivo | Linhas | Responsabilidade |
|---|---|---|
| CadBridge.cs | 2075 | Toda a logica de dominio CAD (DTOs, insercao, scan, undo, XData) |
| MapaControl.xaml.cs | ~550 | Host WPF, WebView2, dispatcher de mensagens |
| MapaControl.xaml | ~120 | Layout da paleta (WebView2 + barra de status) |
| web/app.js | 873 | Frontend Leaflet/OSM, TracadoState, postMessage |
| Plugin.cs | ~50 | Registro do comando AutoCAD e da paleta |
| PaletteHost.cs | ~60 | Container WPF da paleta no AutoCAD |
| SnyderConverter.cs | ~170 | Conversao UTM <-> WGS84 |
| AmbientalParser.cs | ~330 | Parser de relatorio ambiental |
| mapa_paleta_loader.lsp | ~100 | AutoLISP de inicializacao |

### 7.2 Dependencias de Infraestrutura

| Dependencia | Uso |
|---|---|
| AutoCAD .NET API (net48 / net8.0-windows) | Database, Transaction, XData, Layer, Block |
| System.Text.Json | Serializacao/desserializacao JSON |
| Microsoft.Web.WebView2 | Host do frontend Leaflet |
| Leaflet.js | Renderizacao do mapa OSM |
| OpenStreetMap tiles | Mapa de fundo (requer internet) |

### 7.3 Glossario

| Termo | Definicao |
|---|---|
| DomainId | GUID RFC4122 v4 que identifica unicamente um Poste no Twin. Imutavel. |
| VaoId | GUID RFC4122 v4 que identifica unicamente um Vao no Twin. Imutavel. |
| OperationId | GUID gerado por cada operacao de insercao/edicao. Escopo de Undo. |
| XData | Extended Data do AutoCAD. Mecanismo de persistencia de metadados por entidade no DWG. |
| RegApp | Application Registry Name no DWG. AUXCAD_POSTE e AUXCAD_VAO. |
| Scan | Execucao de LerEstadoDwg -> ReconciliarTopologiaDwg -> ExecutarReparosDwg. |
| TracadoState | Objeto JavaScript in-memory que mantem o estado do tracado na sessao da paleta. |
| Twin | O modelo computacional persistente da rede (este dossie). |
| Croqui de Campo | Desenho feito pelo tecnico durante o levantamento fisico da rede. Fonte primaria. |
| 2.5D | Geometria plana (X, Y) com Z = 0.0 constante. |

---

Dossie produzido com base em auditoria direta do codigo-fonte. Fonte de verdade: codigo, nao documentacao anterior.

## DT-02 — GRAFO SEMANTICO EM MEMORIA

**Estado:** implementado offline. Esta fase evolui a projeção DT-01 sem alterar o DWG, criar IDs ou iniciar sincronização por eventos.

### Arquitetura implementada

```text
DWG
 -> LerEstadoDwg()
 -> ReconciliarTopologiaDwg()
 -> EscanearDwgResultado
 -> DigitalTwinBuilder
 -> DigitalTwin
 -> TwinTopologyGraph e consultas semanticas
```

`DWG` continua sendo a fonte de verdade operacional. O `DigitalTwin` é um read model somente leitura derivado de `EscanearDwgResultado`; `DigitalTwinBuilder` não altera a entrada, repara topologia, escreve no desenho nem gera IDs. O grafo usa as relações explícitas do scanner e não infere conectividade por coordenadas ou proximidade.

### Modelo e consultas

O grafo preserva `PosteTwin.DomainId` como identidade lógica, mantendo `Numero` como atributo visual/editável e `Handle` como referência física CAD. Os vãos conservam `VaoId`, `PosteOrigemId` e `PosteDestinoId`. Consultas disponíveis em `DigitalTwin`:

- `GetPoste` e `GetVao`;
- `GetVaoIdsIncidentToPoste` e `GetConnectedPosteIds`;
- `GetIsolatedPostes` e `GetOrphanVaos`;
- `GetConnectedComponents`.

Componentes são formados somente por relações topológicas aceitas, ordenados deterministicamente por identidade; poste isolado constitui componente próprio. Relações inválidas não conectam componentes.

### Diagnósticos

O grafo emite `TWIN_ORPHAN_POSTE_REFERENCE`, `TWIN_SELF_LOOP`, `TWIN_ISOLATED_POSTE`, `TWIN_DUPLICATE_RELATION` e `TWIN_INVALID_TOPOLOGY`. Diagnósticos originais do scanner são transportados ao Twin. Os diagnósticos gerados pelo grafo são informativos; sua severidade não converte automaticamente todo caso em erro. A fonte continua identificada como `DWG_SCAN`; atributos não fornecidos pelo scanner permanecem ausentes.

### Validação offline DT-02

- Harness isolado DT-02: **24 cenários aprovados**, cobrindo Twin vazio, isolamento, relações válidas/inválidas, cadeia, ramificação, órfãos, referências ausentes, self-loop, duplicidade, componentes, identidade, entrada reordenada, diagnóstico do scanner e builder sem mutação/geração de IDs.
- Suíte Python completa na revalidação mais recente: **604 passed, 2 skipped** (`py -m pytest -q -rs`); os skips e o escopo offline estão detalhados na seção DT-02I abaixo.
- Build Release multialvo de `MapaCadPaleta.csproj`: **0 erros** para `net8.0-windows` e `net48`; `net48` sem warnings e `net8.0-windows` com 2 warnings `MSB3277` de conflito de referências.
- Os resultados acima são validação offline/compilação, não homologação AutoCAD.

## DT-02I — FRONTEIRA OFFLINE DE INTEGRAÇÃO

**Decisão:** concluída sem alteração de código — a fronteira existente é suficiente para preparar um consumidor futuro, sem ativá-lo no fluxo operacional.

`DigitalTwinBuilder.Build(EscanearDwgResultado)` é a fronteira de transformação já disponível e coberta pelo harness quanto à preservação de identidade/topologia e não mutação. Ela não depende de API do AutoCAD, não chama scanner, reconciliação ou reparo e não é chamada pelo fluxo operacional da paleta. Não foi criado serviço, interface ou integração adicional nesta fase.

O ponto de consumo futuro é o `EscanearDwgResultado` produzido pela única chamada existente de `CadBridge.EscanearDwg`, seguido de `DigitalTwinBuilder.Build(resultado)`, sem uma segunda varredura. Atenção: a implementação atual de `CadBridge.EscanearDwg` chama `LerEstadoDwg`, `ReconciliarTopologiaDwg` e `ExecutarReparosDwg` antes de retornar. Portanto, o Builder é somente leitura, mas a chamada atual do scanner pode executar reparos no DWG; este registro não declara o fluxo completo como leitura pura nem autoriza nova chamada operacional.

### Revalidação offline DT-02I

- `py -m pytest -q -rs`: **604 passed, 2 skipped**. Ambos os skips são casos de planilha real ausente em `tests\test_cqt_quadros.py`; a suíte inclui um novo teste de contrato offline para geometria das obstruções OSM.
- `py -m pytest tests\test_digital_twin_dt02.py -q`: **1 passed**.
- Testes direcionados OSM: **2 passed**; harness `dotnet run --project tests\dt02_harness\DT02Harness.csproj -c Release`: **30 cenários aprovados** (24 de grafo e seis de geometria OSM).
- Build isolado Release `net8.0-windows`: **0 erros, 2 warnings MSB3277** já conhecidos; build `net48`: **0 erros, 0 warnings**. Ambos foram direcionados a diretórios temporários para não substituir a DLL potencialmente carregada no AutoCAD ativo.
- O build Release padrão falhou ao copiar a DLL para `bin` porque ela estava em uso pelo processo AutoCAD PID 53244. O processo não foi encerrado.
- `git diff --check` não está limpo no worktree inicial: reporta whitespace preexistente em `CAC.md`, `MapaControl.xaml.cs` e `web/tracado.js`; esses arquivos não foram alterados nesta fase.
- Nenhum processo AutoCAD foi encerrado, aberto ou manipulado; nenhum DWG foi aberto ou alterado. A mudança operacional ficou restrita à semântica geométrica OSM documentada nesta seção; a identidade e a reconciliação OSM-01 foram preservadas.

### Verificação offline do posicionamento OSM de obstruções

O frontend converte as coordenadas OSM de latitude/longitude para UTM usando Snyder e o fuso selecionado/configurado (fallback 23), envia os pares X/Y em `pontosUtm` e o CAD os usa diretamente como coordenadas de vértice. Isso demonstra o caminho de transformação, mas não prova que os objetos apareçam no local correto: é necessário que o fuso, hemisfério, datum/projeção e unidades do DWG coincidam com os do payload e conferir o resultado em uma cópia controlada do desenho. Os logs fornecidos mostram amostra de via, não amostra de obstrução nem CRS do DWG; não há base para declarar posicionamento visualmente validado.

Foi confirmada uma inconsistência geométrica no código: o frontend classifica edificações como polígonos e barreiras como linhas, enquanto a chamada CAD fechava indiscriminadamente todas as obstruções. A correção offline agora fecha `EDIFICACAO`, mantém `BARREIRA` aberta e preserva o fechamento anterior como fallback para tipos desconhecidos. As coordenadas são validadas antes da reconciliação OSM: exigem pelo menos dois pares `[x,y]` numéricos e finitos; payload inválido é ignorado antes de poder atualizar/remover entidade existente. O harness offline cobre os dois tipos, geometrias com dois/três pontos, payload vazio/inválido e fallback legado.

Essa alteração corrige a semântica de fechamento da polilinha, mas não comprova que as coordenadas estejam posicionadas corretamente no espaço do DWG. Fuso, hemisfério, datum/projeção e unidades do desenho ainda precisam ser conferidos em uma cópia controlada no AutoCAD; nenhum desenho ou processo AutoCAD foi manipulado nesta fase.

### Validação offline da política geométrica OSM

- Harness: **30 cenários aprovados**, incluindo os 24 cenários DT-02 e seis casos da política geométrica OSM.
- Testes direcionados OSM: **2 aprovados**, cobrindo identidade/reconciliação existente e o contrato semântico/validação do desenho de obstruções.
- Suíte completa: **604 passed, 2 skipped**; testes OSM direcionados: **2 passed**; harness: **30 cenários aprovados**.
- Builds Release em saída temporária: `net8.0-windows` **0 erros / 2 avisos MSB3277** e `net48` **0 erros / 0 avisos**.
- Essas verificações são offline/compilação e não equivalem a runtime AutoCAD nem confirmam o posicionamento espacial real.

### Pendências de runtime preservadas

Os registros de OSM/Snyder e da paleta acima descrevem evidência de execução anterior à correção OSM-01 e não comprovam a idempotência pós-correção. Nesta fase nenhum processo AutoCAD ou DWG foi aberto ou alterado.

| Item | Estado |
|---|---|
| DT-02 — grafo e consultas em memória | IMPLEMENTADO OFFLINE |
| DT-02I — fronteira offline de integração | CONCLUÍDA SEM ALTERAÇÃO; Builder existente não ativado operacionalmente |
| DT-01H — homologação assistida no AutoCAD | PENDENTE |
| OSM-01 — correção | IMPLEMENTADA; validação offline registrada |
| OSM-01R — reteste manual pós-correção | PENDENTE |
| Idempotência real OSM no AutoCAD | NÃO COMPROVADA |
| Persistência real após salvar/fechar/reabrir | PENDENTE |
| Runtime AutoCAD da DT-02 | PENDENTE |
| DWG como fonte de verdade | SIM |

Não se inicia DT-03 nesta etapa. As limitações de runtime permanecem até a execução manual controlada em AutoCAD, usando cópias de teste.
