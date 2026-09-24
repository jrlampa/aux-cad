# Changelog

Todas as alterações notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

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
- **Deduplicação de Consultas no Traçado Cartográfico**: Eliminação da chamada redundante de contexto urbano em `tracado.js`, centralizando a aquisição de vias em `app.js` (raio unificado de 140m) e preservando a cobertura do vão.

### Fixed
- **Permissão Negada no Checklist Ambiental**: Correção do erro `[Errno 13] Permission denied: 'C:\Windows\System32\CHECKLIST_*.xlsx'` que ocorria quando o modelo Word não estava acessível e o processo AutoCAD iniciava o subprocesso sem diretório de trabalho definido.

### Technical
- **Validação Cruzada de Plataforma**:
  - 300 testes automatizados via `pytest` (297 PASS, 3 SKIP por unidade externa `G:`).
  - 43 arquivos JavaScript validados com `node --check` (0 erros).
  - Compilação Release .NET multi-target (`net48` e `net8.0-windows`) com 0 erros.
  - Verificação de 10 comandos críticos via AutoCAD 2026 Core Console (`accoreconsole.exe`).
