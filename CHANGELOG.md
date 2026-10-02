# Changelog

Todas as alterações notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.6.0] - 2026-09-26 — OXCAD: Infraestrutura de Observabilidade, Identidade Visual e Homologação Física no AutoCAD 2026

### Added
- **Infraestrutura Central de Logs e Observabilidade Estruturada**:
  - Python: `common/logging_config.py` com `JsonLinesFormatter`, `SafeRotatingFileHandler` e `OxCadLoggerAdapter`. Rotação de 5 MB e retenção de 5 backups.
  - C# (.NET): `oxcad/OxCadLogger.cs` thread-safe gravando em `logs/application.jsonl` e `logs/errors.jsonl` sem dependências externas adicionais.
- **Rastreabilidade e Propagação de Correlation ID**:
  - Injeção e fluxo ininterrupto de `correlation_id` (C# PaletteSet $\rightarrow$ Python CLI $\rightarrow$ WorkspaceActionDispatcher $\rightarrow$ subprocessos).
- **Sanitização Ativa de Dados Sensíveis**:
  - Proteção em C# e Python contra vazamento de senhas, tokens, cookies, chaves privadas e segredos de API em logs (`sanitizar_mensagem` / `Sanitize`).
- **Identidade Visual e Catálogo Oficial de Assets OXCAD**:
  - Monograma técnico vetorial e ortogonal OX com precisão cartesiana CAD e snap points.
  - Catálogo completo em `oxcad/assets/` (`.svg`, `.png`, `.ico` multi-resolução e wordmarks).
  - Integração do monograma no cabeçalho da paleta WPF (`OxCadControl.xaml`).
- **Diagnóstico Operacional Integrado**:
  - Comando nativo do AutoCAD `OXCAD_DIAGNOSTICO` exibindo status, runtime .NET, caminhos e eventos recentes.

### Changed
- **Distribuição Multi-Targeting de Assets**: `oxcad/OxCadPaleta.csproj` configurado para copiar os assets automaticamente nos builds Release de `net8.0-windows` e `net48`.
- **Rastreamento de Subprocessos e Transições de Tempo**: Subprocessos especialistas (CQT, Orçamento, CPFC, Ambiental, AutoPrancha, Preparar SOB) registram início, PID e término correlacionados; transições de apontamento de tempo registradas em nível `INFO`.

### Technical
- **Homologação Física no AutoCAD 2026**:
  - Validação física em sessão interativa do Autodesk AutoCAD 2026 (PID 46664, v25.1.0.0, .NET 8.0.29).
  - DLL `OxCadPaleta.dll` 0.6.0.0 (`0.6.0+853dc53`) comprovada em memória no processo host.
  - `OXCAD_DIAGNOSTICO` executado com sucesso na Command Line do AutoCAD.
  - Renderização física comprovada do monograma OX e interface WPF.
  - Fluxo operacional real com SOB `A043257319` homologado (RPC C# $\rightarrow$ Python em 15.9ms).
  - 85 testes específicos do OXCAD aprovados (100% PASS).
  - Hashes SHA-256 dos modelos oficiais íntegros (`prancha.dwg` e `cqt_modelo.xlsm`).

---

## [0.9.0] - 2026-09-24

### Added
- **Institucionalização do Versionamento Oficial**: Arquivo `VERSION` estabelecido na raiz como fonte oficial única de versão (`0.9.0`), integrado ao metadata de build .NET (`net48` e `net8.0-windows`).
- **Seletor Visual de Destino no Módulo Ambiental**: Campo editável e botão "Procurar..." (`filedialog.askdirectory`) no formulário do Memorial Descritivo/Checklist Ambiental, permitindo ao projetista definir a pasta de saída dos documentos técnicos com um clique.
- **Proteção de Escrita e Rejeição de Diretórios do Sistema**: Mecanismo `is_safe_writable_dir` e `determinar_pasta_saida` que rejeita gravação em `C:\Windows\System32`, `C:\Windows`, `C:\Program Files` e raiz de disco, redirecionando automaticamente para a pasta do DWG, Desktop ou Temp.
- **Resiliência a Concorrência de Arquivo (File Lock)**: Tratamento de `PermissionError` ao exportar `.xlsx` ou `.docx` abertos no Excel/Word, gerando cópia segura com sufixo de timestamp (`CHECKLIST_{SOB}_{HHMMSS}.xlsx`) sem travamento.
- **Módulos Funcionais Consolidados**:
  - `sob/`: Orquestrador de SOBs com busca no SharePoint, integração com GOMNET e fallback manual.
  - `ambiental/`: Análise espacial de restrições via KMZ, desenho de caixas de alerta no AutoCAD, gerador de croqui de satélite, Checklist (.xlsx) e Memorial Descritivo (.docx).
  - `mapa_cad_paleta/`: Paleta cartográfica OSM nativa via C# .NET/WPF/WebView2 com sincronização bidirecional ModelSpace $\leftrightarrow$ Leaflet.
  - `cqt/`: Dimensionamento elétrico de condutores e quadros de carga com integração bidirecional Excel.
  - `unifilar/`: Extração de árvore de proteção elétrica (SGT / SQLite local) e geração de diagrama unifilar vetorial.
  - `orcamento/`: Extração quantitativa de materiais, kits de estruturas e mão de obra contratual com exportação `.xlsx` (sisORÇA).
  - `dados_tecnicos/`: Tabelas normativas de esforços mecânicos BT/MT (SQLite3/JSON/AutoLISP) e cálculo de resultantes.
  - `topografia/` e `prancha/`: Ferramentas topográficas e montagem automatizada de pranchas com carimbo.
  - `cpfc/`: Motor de cálculo analítico e formulário da REN 1.059 ANEEL.

### Changed
- **AutoLISP `KMZCHECK`**: Normalização do caminho do desenho ativo via `(getvar "DWGPREFIX")` com remoção de barra invertida terminal (`vl-string-right-trim`), invocando o subprocesso via `cd /d "<dwg_dir>"` e repassando o diretório como argumento explícito.

### Fixed
- **SharePoint Modern & Resolução de Identidade da SOB**:
  - `sob/sob_sharepoint.py`: Atualização do método `baixar_pasta_por_url` para compatibilidade com SharePoint Modern (Fluent UI), empregando seletores semânticos (`input[data-automationid='selection-checkbox']`, `input[aria-label*='Selecionar todas']`) e acionamento via JavaScript para ativar o botão 'Baixar' na barra de comandos.
  - `sob/sob_sharepoint.py`: Resolução determinística de artefatos da SOB via `_resolver_itens_sob`, evitando falso `SobConflictError` quando a busca retorna pasta e arquivos (`.pdf`, `.zip`, imagens) da mesma SOB, priorizando a pasta canônica e croquis.
  - Validação física de download comprovada em execução real com SOB `A057526153` (Base `RE`), com descompactação e nivelamento em `CROQUI/` sem falhas.
- **Reconciliação do Binding de Contexto PREPARAR SOB & Eliminação do Falso ARTIFACT_NOT_VERIFIED**:
  - `mapa_cad_paleta/ProjectScope.cs` & `mapa_cad_paleta/DwgProjectScopeStore.cs`: Adicionada ponte explícita `ReconcileCompletedManifest` e `TryReconcile` para vincular deterministamente o DWG aberto pelo `PREPARAR SOB` baseado na evidência upstream do `.sob_state.json` (status `CONCLUÍDO`, `base_dwg` canônico idêntico ao ativo, ausência de identidades concorrentes), gravando `AUXCAD_PROJECT_SCOPE` e propagando `_projectScopeResolved = true`.
  - `oxcad/OxCadControl.xaml.cs`: `AtualizarContextoAsync` tenta reconciliação determinística antes de rejeitar escopos, habilitando os botões de ação e assegurando reconstrução íntegra no clique de `🔄 Atualizar Contexto`.
  - `workspace/workspace_context_cli.py`: Adicionado `_artefato_sob_gerado`, corrigindo o contrato de verificação da ação `sob` para reconhecer processos concluídos com manifesto íntegro e eliminar falso `ARTIFACT_NOT_VERIFIED`.
- **Deduplicação de Consultas no Traçado Cartográfico**: Eliminação da chamada redundante de contexto urbano em `tracado.js`, centralizando a aquisição de vias em `app.js` (raio unificado de 140m) e preservando a cobertura do vão.
- **Crash STATUS_STACK_OVERFLOW no OXCAD (0xc00000fd)**: Eliminação definitiva de recursão infinita na paleta C# WPF através de controle de concorrência com `ContextRefreshGate.cs` e despacho assíncrono via `BeginInvoke` em `PaletteHost.cs`.
- **Permissão Negada no Checklist Ambiental**: Correção do erro `[Errno 13] Permission denied: 'C:\Windows\System32\CHECKLIST_*.xlsx'` que ocorria quando o modelo Word não estava acessível e o processo AutoCAD iniciava o subprocesso sem diretório de trabalho definido.
- **Prevenção de Falso Sucesso em Execuções Técnicas**: Subprocessos com `exit_code == 0` que não geram artefato físico não-vazio válido são marcados como falha (`ARTIFACT_NOT_VERIFIED`).
- **Resiliência de Auditoria Síncrona**: `emitir_obrigatorio` e `registrar_evento_obrigatorio` com `os.fsync` forçado em `common/logging_config.py`.
- **Persistência de Manifesto SOB**: Validação obrigatória do retorno de `gravar_manifesto_execucao` em `sob/sob_manager.py`.

### Added (Baseline P0/P1)
- **Autoridade de Identidade Host -> CLI (Gate 1)**: Transporte via stdin protegido com verificação de processo pai `acad.exe` por Win32 API e pareamento com `AUXCAD_PROJECT_SCOPE` e `Database.FingerprintGuid`.
- **Registro Imutável de Execuções (P0.3)**: `OxCadExecutionRegistry.cs` e `OxCadExecution.cs` garantindo unicidade de `ExecutionId` e separação estrita de `CorrelationId`.
- **Contratos P1 de Engenharia**:
  - `workspace_validation.py` (P1.1): Validação baseada em regras com fixação de SHA-256 e `mtime_ns` da fonte de dados.
  - `workspace_versions.py` (P1.2): Snapshots versionados imutáveis com hash e restauração atômica.
  - `workspace_pending.py` (P1.3): Gerenciamento autoritativo de pendências técnicas.
  - `workspace_delivery.py` (P1.4): Pacotes de entrega com manifesto digital e rejeição de evidências obsoletas (`VALIDATION_SOURCE_CHANGED`).
- **Política Local-First da SOB**: Desacoplamento de falhas externas do SharePoint e GOMNET com rollback seguro.
- **Módulo Integrante de Levantamento de Condutores**: Rotina AutoLISP `orcamento/levantamento_condutores.lsp` integrada à paleta OXCAD (`BtnLevantamentoCondutores`) e ao carregador `acaddoc.lsp`, com suíte de testes `tests/test_levantamento_condutores.py`.

### Technical
- **Alinhamento do Baseline de Teste DT-02**: Atualização de `tests/test_digital_twin_dt02.py` para sincronizar o contador com o harness `DT02Harness.csproj` (44 testes aprovados).
- **Validação Cruzada de Plataforma**:
  - Suíte completa de testes aprovada (100% PASS).
  - 92 testes direcionados de autoridade, isolamento e contratos P0/P1 aprovados (100% PASS).
  - Harness .NET `tests/oxcad_context_gate` aprovado com 0 erros.
  - Compilação Release .NET multi-target (`net48` e `net8.0-windows`) com 0 erros e 2 avisos conhecidos de referências Autodesk.
  - Validação real de runtime homologada no Autodesk AutoCAD 2026 (PID 34088).
