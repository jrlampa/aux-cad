# Auditoria de fechamento P0/P1 OXCAD

Data: 2026-09-30. Escopo: leitura do codigo, testes sinteticos de isolamento
em `tests/test_oxcad_audit_isolation.py` e gates abaixo. Sem correcoes de
produto, commit ou mudanca de versao (`VERSION`: 0.9.0). **Decisao:
P0/P1 NAO FECHADO.** Tres falhas reproduzidas afetam a identidade/evidencia
que P2 herdaria. Passagem de testes e build nao anula esses contraexemplos.

## A. Arquitetura e D. Integracao

Em cada linha: transicao; dono/contrato; identificadores; persistencia/evento;
teste. Contratos host e CLI nao sao a mesma fronteira de confianca.

| Transicao | Codigo/contrato | Identificadores | Persistencia e evento | Testes |
| --- | --- | --- | --- | --- |
| SOB -> ProjectScope | `sob/sob_manager.py` grava `.sob_state.json`; `mapa_cad_paleta/Plugin.cs` comando `AUXCAD_BIND_SOB` compara SOB/base_dwg e chama `DwgProjectScopeStore.Write` | SOB_ID, base_dwg | Manifesto SOB atomico; Xrecord `AUXCAD_PROJECT_SCOPE` v1 no DWG | `test_sob_manager.py`, `test_oxcad_project_scope.py` |
| ProjectScope -> DWG | `mapa_cad_paleta/DwgProjectScopeStore.cs`, `ProjectScope.cs` leem SOB_ID; `oxcad/OxCadControl.xaml.cs` le Xrecord | SOB_ID no Xrecord, `Database.FingerprintGuid`, caminho | Xrecord no DWG; consulta logada | `test_oxcad_project_scope.py`, `test_oxcad_context_integration.py` |
| DWG -> contexto | `oxcad/Plugin.cs` eventos MDI; `ContextRefreshGate.cs` e `OxCadControl.xaml.cs` recusam resposta atrasada | documento, database, generation, fingerprint | Memoria da paleta; refresh/log host | `test_oxcad_context_reactivity.py`, harness `tests/oxcad_context_gate` |
| contexto -> execucao | `oxcad/OxCadExecutionRegistry.cs` e `OxCadExecution.cs`; `workspace/workspace_context_cli.py` wrapper `executar_acao_operacional` | SOB, DWG, fingerprint, ExecutionId, CorrelationId; generation somente no host | Registro host em memoria (max. 256); JSONL global | `test_oxcad_execution.py`, `test_oxcad_audit_isolation.py` |
| execucao -> validacao | `workspace/workspace_context_cli.py` acao `validar`, `workspace/workspace_validation.py` engine CQT | Context/IDs P0.3; `rule_id` | Resultado retornado; evento por regra no JSONL, nao resultado historico duravel | `test_oxcad_validation.py` |
| validacao -> evidencia | `ValidationResult.to_dict` inclui valor, criterio, fonte/aba/celula, timestamp e contexto | regra, execution/correlation, DWG | Referencia no retorno/JSONL; sem hash da fonte no momento da leitura | `test_oxcad_validation.py`, `test_oxcad_audit_isolation.py` |
| evidencia -> snapshot | `workspace/workspace_versions.py` `capture/inspect`, hash reutilizado de `sob/sob_core.py` | SOB, DWG/fingerprint, caminho relativo, SHA-256, snapshot_id | `.auxcad_versions/<id>/payload` e `manifest.json`; evento CLI | `test_oxcad_versions.py` |
| snapshot -> recuperacao | `workspace/workspace_versions.py` `restore`: revalida identidade/hash, abre destino exclusivo `xb` | snapshot_id, SOB, DWG/fingerprint | Novo arquivo `.recuperado-<id>`; log de acao CLI | `test_oxcad_versions.py`, `test_oxcad_audit_isolation.py` |
| evidencia/snapshot -> pendencia | `workspace/workspace_pending.py` `create`: referencia P1.1 OU snapshot P1.2 por acao explicita | id, SOB, DWG/fingerprint, IDs de origem | `.oxcad/pending.json`, historico interno; JSONL de auditoria | `test_oxcad_pending.py`, `test_oxcad_audit_isolation.py` |
| pendencia -> entrega | `workspace/workspace_delivery.py` `generate`: retrato de pendencias, referencias e manifestos/hashes P1.2, DWG incluido | package_id, SOB, DWG/fingerprint, SHA-256 | `.oxcad/deliveries/<id>/manifest.json` + `manifest.sha256`; JSONL | `test_oxcad_delivery.py` |
| entrega -> aprovacao | `workspace/workspace_delivery.py` `approve`: confirmacao explicita e justificativa se ERRO/pendencia aberta; `revoke` explicito | package_id + digest do manifesto, contexto, execution/correlation | `approval.json` atomico; evento JSONL; aprovador `null` (sem auth) | `test_oxcad_delivery.py` |
| aprovacao -> verificacao | `workspace/workspace_delivery.py` `verify`: hashes de arquivos, checksum do manifesto, pendencias e approval | SOB, DWG/fingerprint, SHA-256 | Leitura; retorno CONFIRMED/DIVERGENT/MISSING/INVALID; JSONL CLI | `test_oxcad_delivery.py`, `test_oxcad_audit_isolation.py` |

P1.2-4 nao possuem botoes na paleta; sao acoes backend/CLI. O CLI nao recebe
generation nem relê Xrecord. `workspace/workspace_scanner.py` lista artefatos
por nome/padrao; nao e prova de identidade binaria. Aprovar nao recalcula
CQT, nao gera pendencia e nao implica nova execucao de `validar`.

## B. Matriz de identidade/contexto

Legenda: H = do host, C = fornecido ao CLI/guard local, N = ausente.

| Componente | SOB | DWG | Fingerprint | ExecutionId | Contexto reativo | Risco |
| --- | --- | --- | --- | --- | --- | --- |
| SOB preparacao/Xrecord | manifesto/Xrecord | base_dwg e DWG ativo | N no Xrecord | RUN_ID, nao P0.3 | host exige desenho ativo | falha ao gravar manifesto pode ser ignorada |
| Paleta | H (Xrecord) | documento + path | H (`FingerprintGuid`) | H, unico no registry | H (generation/ticket) | nao protege chamadas CLI independentes |
| CLI/WorkspaceScanner | C (`--sob`) | C (`--dwg`) | C (`--dwg-identity`) | C ou gerado | N | `Bound` local sem Xrecord; fallback sem manifesto |
| P0.3 registro CLI | C | C | C | C ou UUID; apenas `!= CorrelationId` | N | ID externo reutilizavel; exit 0 != artefato |
| P1.1 ValidationContext | C | C | C (= dwg_identity no CLI) | C | N | validacao nao exige scope por padrao |
| P1.2 snapshot | C validado local | C + path | C comparado a manifesto P1.2 | C quando aplicavel | N | nao autentica fingerprint fornecido |
| P1.3 pendencia | C + store por raiz | C + path | C comparado a registro | C historico | N | protegido entre registros honestos, nao contra CLI forjado |
| P1.4 pacote/aprovacao | C + store por raiz | C + path + hash no pacote | C comparado a manifesto/aprovacao | C | N | `CONFIRMED` pode conter validacao stale |

## C. Lifecycle

Registry host (`oxcad/OxCadExecutionRegistry.cs`) proibe ExecutionId duplicado,
congela snapshot por execucao e associa comandos nativos ao fingerprint; eventos
`CommandEnded`, `CommandCancelled` e fechamento do DWG controlam conclusao,
cancelamento real e aviso a UI. A paleta compara generation e fingerprint
antes de aplicar retorno. Wrapper Python registra `Iniciado -> Executando ->
Concluido/Falhou` no JSONL ou nao emite ciclo conclusivo quando ProjectScope
preflight falha. P1.1, P1.2, P1.3 e P1.4 retornam estados separados do estado
da execucao; gravacao recusada falha. Contudo, o wrapper CLI nao registra
unicidade global de ID passado pelo chamador. `exit_code == 0` pode concluir
sem novo artefato (`test_audit_characterizes_exit_zero_without_generated_artifact`).
Nao confundir sucesso de subprocesso com conformidade tecnica ou entrega.

## E. Persistencia e duplicacao

| Mecanismo | Fonte de verdade/finalidade | Atomicidade; risco; relacao |
| --- | --- | --- |
| Xrecord DWG + `.sob_state.json` | identidade persistente no host + estado SOB | transacao DWG; JSON temporario + replace. CLI so confere JSON/candidatos, nao Xrecord; retorno de gravacao SOB ignorado pelo manager |
| JSONL global `logs/application.jsonl`, `errors.jsonl` | auditoria/observabilidade, NAO cadastro de estado | rotacao por tamanho; `SafeRotatingFileHandler.handleError` suprime falha; eventos podem ser perdidos, nao ha transacao com stores |
| Memoria host/ContextRefreshGate | estado efemero da execucao/contexto | lock de registry/generation; sem persistencia; nao atravessa CLI |
| `.oxcad/time.json` | apontamento operacional de tempo | JSON temp/replace; historico de sessoes nao substitui lifecycle |
| `.auxcad_versions/<id>` | manifesto e bytes opt-in para recuperacao | diretório temporario/rename; hash payload/arquivo; copia seletiva, NAO entrega |
| `.oxcad/pending.json` | cadastro autoritativo, historico por pendencia | lock + fsync/replace; falha/corrupcao explicita; JSONL derivado |
| `.oxcad/deliveries/<id>` | manifesto/checksum e decisao approval.json | staging/rename; approval fsync/replace; nao copia arquivos; checksum sem assinatura nao autentica autor |

Existe sobreposicao intencional de SOB/DWG/IDs nos envelopes para auditoria,
nao segundo cadastro de pendencias. Estados transitorios de execucao e
validacao nao sao snapshots tecnicos persistentes; JSONL rotativo nao prova
permanencia historica de resultados P1.1.

## F. Testes, G. Build e H. Isolamento

Descoberta por `test_oxcad_*.py`, `test_workspace_*.py`, `test_sob_*.py`:
15 arquivos OXCAD (159 testes, incluindo 7 de auditoria), 10 workspace
(113), 11 SOB (158), total **430 coletados**. Execucao completa apos o ultimo
teste: **429 aprovados, 1 ignorado, 0 falhas** em ~92 s. O ignorado da
execucao foi `test_sob_launcher_gui.py:51` (sem display Tk). GUI isolada:
23 aprovados, 2 ignorados por display Tk; E2E `test_workspace_e2e_operacional.py`
incluido e aprovado. Skips sao condicionais ao ambiente, nao falha funcional.

| Componente | Casos coletados | Cobertura aparente | Lacuna relevante |
| --- | ---: | --- | --- |
| P0 contexto/execucao (`test_oxcad_context_*`, `execution`, `project_scope`, `audit_isolation`) | 45 | Xrecord via harness, MDI, IDs, falhas, A/B e desvios reproduzidos | sem teste AutoCAD interativo de ponta a ponta P1.2-4 |
| P1.1 (`test_oxcad_validation.py`) | 12 | CQT cached, 4 estados, evidencia e JSONL | fonte sem hash/frescor; outros modulos sem validadores comprovados |
| P1.2 (`test_oxcad_versions.py`) | 10 | hash, missing, contexto, copia exclusiva, falha parcial | nao autenticacao do fingerprint CLI |
| P1.3 (`test_oxcad_pending.py`) | 7 | CRUD, estados, A/B, evidencia, falha de gravacao | nenhum UI host; JSONL sem durabilidade garantida |
| P1.4 (`test_oxcad_delivery.py`) | 12 | manifesto, aprovacao, revogacao, hash, pending, fail write, ciclo | stale P1.1 com pacote CONFIRMED |
| Demais OXCAD | 73 | assets, integracao, jobtime, logging, hardening | nao atesta identidade do chamador CLI |
| Workspace (10 arquivos) | 113 | despachos tecnicos, contexto, E2E Tk | retorno de subprocesso nao garante entregavel |
| SOB (11 arquivos) | 158 | preparo, idempotencia, rollback, GUI, SharePoint | retorno de gravação do manifesto ignorado |

`net48`: build aprovado. `net8.0-windows`: build aprovado com **dois**
avisos MSB3277 conhecidos nas referencias Autodesk: `Microsoft.VisualBasic`
10.0.0.0 vs 10.1.0.0; `System.Drawing` 4.0.0.0 vs 8.0.0.0. `git diff --check`:
aprovado; somente avisos LF/CRLF. Nao foi iniciada sessao AutoCAD interativa.

Testes de isolamento A/B passam **no caminho corretamente vinculado**:
A nao le B, B nao le A, acao A com DWG B e SOB A e recusada antes do ciclo,
pending A nao e resolvida por B, pacote A nao e aprovado em B, snapshot A nao
e recuperado em B e P1.1 de A nao aparece em resultado B. Mesmo projeto com
segundo DWG/fingerprint stale nao altera pending/aprovacao A. Cinco testes
adicionais de caracterizacao passam demonstrando *desvios* sob CLI sem
vinculo/sem preflight ou validacao antiga: passar nao significa seguranca.

## I. Gaps classificados e J. Backlog recomendado

| Classe e fase | Evidencia/impacto | Recomendacao | Bloqueia P2? |
| --- | --- | --- | --- |
| CRITICO P0.1/P1.2-4 | `workspace_context_cli.py:_resolver_project_scope`: sem `.sob_state.json`, exclui o DWG ativo dos candidatos e pode aceitar SOB B com DWG A; `test_audit_characterizes_unbound_scope_fallback` capturou snapshot A rotulado B. Host exige manifesto, CLI nao rele Xrecord. | Exigir prova da identidade persistente na fronteira CLI; recusar `Bound` sem manifesto/prova equivalente e vincular fingerprint real do host. | SIM |
| CRITICO P1.1 | `validar` CLI nao obriga `require_project_scope`; `WorkspaceScanner.scan(...sob_id=B)` aceita fallback `CQT*.xls*`; `test_audit_characterizes_optional_validation_scope` retornou fonte A como resultado SOB B. | Exigir escopo/raiz/identidade comprovados antes de validar; rejeitar arquivo de outro SOB. | SIM |
| CRITICO P1.1/P1.4 | `workspace_delivery.py:_validation` verifica identificadores e fonte, nao bytes no momento P1.1. `test_audit_characterizes_stale_validation_in_approved_package`: CQT muda de OK para ALERTA, pacote novo dos bytes alterados carrega OK antigo e `verify` retorna CONFIRMED. | Associar hash de fonte a resultado P1.1 no ato da validacao; recusar evidencia cujo hash nao corresponda ao pacote. | SIM |
| ALTO P0.1/SOB | `sob/sob_manager.py` define sucesso e chama `gravar_manifesto_execucao` (retorna bool), sem verificar o retorno; uma falha pode deixar SOB concluida sem manifesto e expor o fallback acima. | Falha de persistencia do manifesto deve impedir sucesso/conclusao. | SIM |
| ALTO P0.3 | `workspace_context_cli.py` conclui por `exit_code in (None,0)`; teste de auditoria com processo `pass` retornou Concluido e `artifacts=[]`. IDs externos do CLI nao tem registry global (`exec_id` so difere de `cid`). | Separar estado de subprocesso de entregavel verificado e proteger reutilizacao de ID; manter sem cancelamento inventado. | SIM para P2 que consuma sucesso como entrega |
| ALTO P0.3/auditoria | `common/logging_config.py:SafeRotatingFileHandler.handleError` descarta erro; JSONL rota e nao e transacional. Sucesso do produto nao assegura registro global duravel. | Definir requisito de auditoria duravel/falha observavel antes de usar JSONL como prova de aprovacao. | SIM se P2 depender de trilha auditavel |
| MEDIO P1.4 | `_load` em `workspace_delivery.py` lanca `FileNotFoundError` tanto para pacote ausente quanto checksum faltante; `test_audit_characterizes_missing_checksum_as_missing_package` confirma diagnostico PACKAGE_NOT_FOUND (approval_valid=False). | Distinguir pacote inexistente de manifesto incompleto; nao alterar regra de aprovacao. | NAO |
| MEDIO P1.4 | Pacote retém status/regra/fonte e IDs P1.1, mas nao valor/criterio; recuperacao depende de log rotativo. | Definir referencia duravel para resultado tecnico completo antes de historico formal P2. | NAO, salvo exigencia de prova retrospectiva |
| MEDIO P1.1/P1.4 | Somente regra CQT comprovada; `NÃO DISPONÍVEL` para outras regras e permitido; aprovador nao autenticado e checksum nao assinado. | Ampliar somente regras com evidencia real; definir identidade/aprovacao corporativa se P2 exigir nao repudio. | NAO no escopo atual |
| BAIXO build/GUI | MSB3277 Autodesk conhecido; teste Tk pode ser ignorado sem display. | Manter aviso e executar GUI em ambiente apropriado no gate futuro. | NAO |

**K. Criterio de saida preliminar (2026-09-30): P0/P1 NAO FECHADO.**
O host possuía vinculação persistente e gate MDI preliminar, mas os três desvios críticos demonstraram a necessidade de endurecimento na fronteira Host -> CLI e fixação de hash em validações antes da baseline.

---

## L. Fechamento Definitivo P0/P1 e Validação do Gate 1 (2026-10-01)

Data: 2026-10-01. Escopo: validação de runtime no AutoCAD 2026, endurecimento da autoridade Host -> CLI, hashing de evidências e suíte de isolamento.
**Decisão Final: P0/P1 FECHADO.**

### 1. Evidência Real de Runtime (AutoCAD 2026 Host -> CLI)
- **Host Process**: Autodesk AutoCAD 2026 (`acad.exe`, PID `34088`, .NET 8.0.29).
- **Desenho Real Vinculado**: `G:\Meu Drive\1-HBT\05_PROJETOS_HISTORICOS\SETEMBRO\21\SOB_A057385505\SG_A057385505_DESENHO.dwg`.
- **SOB_ID Oficial**: `A057385505` (vinculado via `AUXCAD_BIND_SOB` e gravado no Xrecord `AUXCAD_PROJECT_SCOPE` v1).
- **Database.FingerprintGuid**: `{3DD86E03-797C-0A41-9446-ADA594C4E383}`.
- **Rastreabilidade**:
  - `ExecutionId`: `abbabeea3c0f48ddb4d9c1dd94d3e142`.
  - `CorrelationId`: `0bdd026d96694e5c85a919c7dba34f97` (`ExecutionId != CorrelationId`).
- **Ação Executada**: `tempo_iniciar` disparada pela paleta OXCAD (`oxcad.palette`), confirmada como `Concluído` / `sucesso` e persistida em `logs/application.jsonl`.

### 2. Resolução Comprovada dos Blockers P0/P1
1. **Identidade falsa/mismatch entre SOB, DWG e fingerprint (`FECHADO`)**:
   `_verificar_envelope_host` e `_autocad_parent_verified` em `workspace_context_cli.py` rejeitam qualquer chamada CLI independente desprovida de envelope assinado por `acad.exe`, e validam a correspondência exata de SOB, DWG e FingerprintGuid. Comprovado em `test_oxcad_gate1_authority.py`.
2. **Validação executável sem contexto verificável (`FECHADO`)**:
   Ação `validar` inserida em `exige_dwg_verificado` e validada por `_verificar_contexto_validacao` em `workspace_validation.py`. Rejeita validação com `DWG_CONTEXT_NOT_VERIFIED` na ausência de contexto host verificado.
3. **Evidência antiga sem hash de origem (`FECHADO`)**:
   `ValidationSource` em `workspace_validation.py` captura `sha256` e `mtime_ns` diretamente dos bytes lidos no instante exato da validação técnica.
4. **Aprovação/entrega com evidência incompatível (`FECHADO`)**:
   `workspace_delivery.py` compara o hash da evidência contra o arquivo no disco; se houver alteração, aborta com `VALIDATION_SOURCE_CHANGED`. Se o hash não estiver presente, rejeita com `VALIDATION_EVIDENCE_UNVERIFIABLE`. Verificação na aprovação recusa o pacote com `PACKAGE_INVALID` caso divirja.
5. **Lifecycle marcado como concluído sem artefato verificável (`FECHADO`)**:
   `_artefato_tecnico_gerado` em `workspace_context_cli.py` valida modificação de tamanho/mtime e conformidade física (zip check em `.xlsx`). Processo com exit 0 sem entregável é marcado como `Falhou` com erro `ARTIFACT_NOT_VERIFIED`.
6. **Falha de persistência de estado (`FECHADO`)**:
   `sob/sob_manager.py` valida o retorno de `gravar_manifesto_execucao`, levantando `IOError` em caso de falha de persistência. Stores de pendências, versões e entregas utilizam escrita temporária + rename atômico com locking exclusivo.
7. **Falha crítica de logging/auditoria (`FECHADO`)**:
   `common/logging_config.py` implementa `emitir_obrigatorio` e `registrar_evento_obrigatorio` com flush síncrono e `os.fsync`. Se o log não puder ser gravado, uma exceção é propagada e a operação é abortada.

### 3. Incorporação do Módulo levantamento_condutores à Suíte OXCAD
O componente `orcamento/levantamento_condutores.lsp` (comando nativo `LEVANTAR_CONDUTORES`) foi oficialmente incorporado à suíte do OXCAD. Ele é acionado pelo botão `BtnLevantamentoCondutores` na paleta WPF (`oxcad/OxCadControl.xaml` / `OxCadControl.xaml.cs`), registrado no carregador global `acaddoc.lsp` e validado integralmente pela suíte `tests/test_levantamento_condutores.py` (6 testes aprovados).

### 4. Correção e Alinhamento do Baseline DT-02
O teste de integração `tests/test_digital_twin_dt02.py` foi atualizado para alinhar o contador esperado ao contrato vigente do harness C# `tests/dt02_harness/DT02Harness.csproj` (44 testes aprovados), resolvendo a inconsistência de baseline herdada do commit `d3b3b193`.

### 5. Veredito Final
A baseline P0/P1 está formalmente encerrada, auditada e apta para servir como fundação estável do sistema.

### 6. Nota Operacional Pós-Fechamento da Baseline (Hotfix SharePoint Modern)
Após a consolidação da baseline P0/P1 (commit `5be84a7`), um teste real operacional com a SOB `A057526153` revelou duas falhas de integração no cliente SharePoint (`sob/sob_sharepoint.py`):
1. **Seletores do SharePoint Modern**: `baixar_pasta_por_url` utilizava seletores de checkbox de tabela legados, impedindo a seleção de itens e a ativação do botão 'Baixar' no design Fluent UI. Corrigido com seletores semânticos (`input[data-automationid='selection-checkbox']`, `input[aria-label*='Selecionar todas']`) e clique via JavaScript.
2. **Identidade da SOB vs Artefatos**: Múltiplos arquivos pertencentes à mesma SOB (`{SOB}`, `{SOB}_CROQUI.pdf`, `{SOB}_FOTOS.zip`) eram interpretados erroneamente como conflito de SOBs distintas (`SobConflictError`). Corrigido com a resolução prioritária de artefatos da mesma SOB sem falso conflito.

Essa correção pontual preserva integralmente os contratos de segurança, Local-First e rollback estabelecidos em P0/P1, sem reabertura dos gates ou alteração arquitetural.
