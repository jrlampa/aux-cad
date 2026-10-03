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
- **Ponte Operacional de Revisão Técnica WPF → CLI (P2.7A)**:
  - Transformação da seção `REVISÃO TÉCNICA` da paleta WPF em interface operacional real, substituindo mock visual pelo domínio real em `workspace_review.py`.
  - Criação do CLI dedicado `workspace/workspace_review_cli.py` (461 linhas) expondo status, iniciar, gate, achado, solicitar-alterações, aprovar, rejeitar, cancelar e rastreabilidade, sem inflar `workspace_context_cli.py`.
  - Método assíncrono `WorkspaceService.ExecutarComandoRevisaoAsync` em C# para comunicação com subprocesso Python via stdout JSON (`ExtrairJsonValido`).
  - Execução assíncrona não-bloqueante na paleta WPF (`OxCadControl.RevisaoTecnica.cs`), refletindo estados de `.oxcad/reviews.json` e bloqueio determinístico no Gate de Aprovação (`APPROVAL_GATE_BLOCKED`).
  - Suíte dedicada de testes `tests/test_oxcad_review_cli.py` (12 testes, 100% PASS) e validação no harness C# (`tests/oxcad_context_gate/Program.cs`).
- **Revisão Técnica, Governança de Entrega e Rastreabilidade Operacional (P2.6)**:
  - Separação explícita de cinco conceitos fundamentais: REVISION (versão técnica analisada), REVIEW (processo de análise técnica), APPROVAL (decisão formal), DELIVERY (pacote preparado) e REVOCATION (invalidação posterior auditável), respeitando a regra REVIEW != APPROVAL != DELIVERY != SYNC.
  - Contrato formal de revisão técnica (TechnicalReview, ReviewContracts.cs, workspace/workspace_review.py) atrelado à autoridade estrita do AutoCAD (FingerprintGuid + AUXCAD_PROJECT_SCOPE + SOB_ID), com persistência atômica e lock em .oxcad/reviews.json.
  - Matriz determinística de transições de estado (DRAFT, IN_REVIEW, CHANGES_REQUIRED, APPROVED, REJECTED, SUPERSEDED, CANCELLED) com bloqueio de transições arbitrárias.
  - Gestão de achados técnicos (ReviewFinding) com severidades (INFO, MINOR, MAJOR, CRITICAL) e integração ao store autoritativo de pendências (.oxcad/pending.json) sem duplicação de dados.
  - Gate determinístico de aprovação (valuate_approval_gate / ApprovalGateResult) validando integridade de identidade, snapshot, evidências com hash SHA-256, findings impeditivos e pendências ativas.
  - Conexão do fluxo Review → Approval → Delivery reutilizando contratos de entrega P1.4 (workspace_delivery.generate), garantindo rastreabilidade ponta a ponta e auditabilidade de revogação.
  - Painel visual 'REVISÃO TÉCNICA' na paleta WPF do AutoCAD (OxCadControl.xaml, OxCadControl.RevisaoTecnica.cs) com exibição de metadados, contadores, resultado do Gate e ações de governança.
  - Suíte dedicada com 35 testes em 	ests/test_oxcad_review_governance.py (100% PASS) e validação no harness C#.
- **Validação de Campo e Operação Resiliente/Offline (P2.5)**:
  - Arquitetura de resiliência e operação contínua com 4 dimensões explícitas de estado (`CoreStatus`, `ConnectivityMode`, `IntegrationAvailability`, `OperationalMode`).
  - Distinção rigorosa entre `OFFLINE` (núcleo local ativo, sincronização remota pendente) e `BLOCKED` (dependência estrita de integração externa indisponível ou núcleo inoperante).
  - Contrato persistível de validação de campo (`FieldValidationItem`) e evidências técnicas (`FieldEvidenceReference`) com integridade binária SHA-256 e proteção absoluta contra `IDENTITY_MISMATCH`.
  - Integração com o cadastro autoritativo existente de pendências (`.oxcad/pending.json`) para divergências em `ERRO` ou `ALERTA` sem duplicação.
  - Fila declarativa de intenção futura de sincronização (`SyncQueue`) persistida em `.oxcad/sync_queue.json` com deduplicação por `IdempotencyKey` e zero workers ou chamadas de rede em background.
  - Painel visual "VALIDAÇÃO DE CAMPO" na paleta WPF do AutoCAD exibindo modo operacional, status das 4 dimensões, soberania SOB/DWG/Fingerprint, checklist e métricas locais.
  - Suíte dedicada com 30 testes em `tests/test_oxcad_field_offline.py` (100% PASS).
- **Plataforma de Integração e Extensibilidade (P2.4)**:
  - Arquitetura de Gateway e desacoplamento do Core: o núcleo conhece apenas contratos de domínio sem conhecer URLs, endpoints, SDKs externos, tokens ou credenciais.
  - Soberania garantida da autoridade DWG e AutoCAD através de `IntegrationContext`: rejeição imediata (`IDENTITY_MISMATCH`) de qualquer tentativa de alteração de SOB, desvio de caminho DWG ou substituição de FingerprintGuid.
  - Contratos de domínio independentes de fornecedor: `IIntegrationProvider`, `IIdentityProvider`, `IDocumentRepository`, `IArtifactRepository`, `IWorkOrderProvider`, `IBusinessSystemProvider`, `ICustomerProvider`, `INotificationProvider`, `IEventProvider`, `IRestProvider`, `ISoapProvider`.
  - Catálogo declarativo padronizado (`IntegrationRegistry`): adaptadores preparados para Microsoft Graph, Microsoft Entra ID, SharePoint, OneDrive, SAP, SAP S/4HANA, SAP BTP, Salesforce CRM, REST e SOAP (todos com status inicial `NotConfigured` e zero chamadas externas de rede).
  - Autenticação declarativa segura (`AuthenticationDescriptor`) sem armazenamento de segredos, senhas ou tokens.
  - Seção visual compacta "INTEGRAÇÕES" na paleta WPF do AutoCAD (`OxCadControl.xaml`, `OxCadControl.Integracoes.cs`) atualizada dinamicamente a partir do registry.
  - Suíte com 40 testes contratuais em `tests/test_oxcad_integrations.py` e asserções integradas no Harness C#.
- **Qualidade, Histórico e Interpretação Operacional dos Indicadores (P2.3)**:
  - Classificação canônica de cobertura histórica (`COMPLETA`, `PARCIAL`, `LIMITADA_POR_ROTACAO`, `SEM_DADOS`, `IDENTIDADE_NAO_VERIFICAVEL`, `FONTE_INDISPONIVEL`).
  - Mapeamento explícito de proveniência por bloco de dados e auditoria detalhada de registros descartados por filtros e integridade.
  - Mecanismo descritivo de comparabilidade metodológica entre períodos sem banco de dados, reportando deltas observados ou `status: NAO_DETERMINADA` com motivo auditável em caso de restrições de cobertura ou identidade.
  - Evolução do CLI com flags `--compare-start` e `--compare-end` e cards visuais compactos de cobertura na paleta WPF.
  - Suíte de 20 testes dedicados em `tests/test_oxcad_indicators_quality.py`.
- **Indicadores Operacionais e Visão Consolidada de Processo (P2.2)**:
  - Camada de consulta e apresentação de indicadores de processo (`workspace/workspace_indicators_cli.py`) suportando saídas em JSON estruturado e resumos amigáveis em console.
  - Integração assíncrona com a paleta WPF do AutoCAD (`OxCadControl.xaml`, `WorkspaceService.cs`) com cards de métricas de execução, duração P95, pendências, entregas e limitações de log rotativo, totalmente isolada de `OxCadExecution` e `OxCadExecutionRegistry`.
  - Suporte a filtros analíticos refinados: por SOB, por período temporal (datas ISO), por tipo de ação (`cqt`, `orcamento`, `sob`, etc.) e por estado final (`Concluido`, `Falhou`, `Cancelado`).
  - Consolidação defensiva de múltiplos projetos sob uma raiz de workspace com suporte explícito a workspace vazio (`SEM_DADOS`).
  - Governança estrita sem métricas de produtividade individual ou rankings de pessoas.
  - Suíte de 20 testes contratuais em `tests/test_oxcad_indicators_operational.py` (100% PASS).
- **Módulo Analítico de Indicadores de Gestão (P2.1 — workspace/workspace_indicators.py)**:
  - Implementação do motor analítico determinístico, read-only e auditável sob o contrato IndicadoresGestao (Schema 1).
  - Reconstrução obrigatória de ciclo de vida por xecution_id, prevenindo a inflação de volume e taxas decorrente de múltiplas transições intermediárias.
  - Distinção estrita de autoridade: fontes duráveis de projeto (.oxcad/pending.json, .oxcad/deliveries/, .oxcad/time.json, .sob_state.json) vs. observabilidade rotativa de janela limitada (logs/application.jsonl).
  - Tratamento defensivo de dados: valores ausentes reportados como NÃO DISPONÍVEL sem mascaramento indevido como zero; isolamento estrito por sob_id com recusa IDENTITY_UNVERIFIABLE em caso de divergência.
  - Leitura resiliente linha a linha de JSON Lines com tolerância a linhas corrompidas e contabilização em qualidade_dados.
  - Suíte de 18 testes automatizados cobrindo todos os cenários contratuais (	ests/test_oxcad_indicators.py).
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
