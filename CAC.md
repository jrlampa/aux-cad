# CAC.md - Contexto de Arquitetura e Decisões (aux cad)

> **Versão Oficial Atual: v0.9.0** | Fonte de verdade: [`VERSION`](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/VERSION) | Histórico de releases: [`CHANGELOG.md`](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/CHANGELOG.md)

## Arquitetura de Diretórios e Modularidade
A pasta raiz `aux cad` adota uma arquitetura modular por domínios de engenharia (DDD / Separação de Responsabilidades), mantendo na raiz apenas os pontos de entrada compartilhados e ferramentas universais do AutoCAD.

```text
aux cad/
├── VERSION                         # Fonte única oficial da versão do projeto (0.9.0)
├── CHANGELOG.md                    # Histórico oficial de versões (Keep a Changelog / SemVer)
├── acaddoc.lsp                     # Carregador universal do AutoCAD (inclusão dinâmica de SupportPath)
├── aux_cad_toolbar.lsp             # Barra de ferramentas global (AUXCADBAR)
├── aux_cad_menu.mnu / .cuix / .mnr # Menu nativo do AutoCAD (AUXCAD)
├── modelos/                        # Templates e modelos compartilhados (checklist, cpfc, etc.)
├── tests/                          # Full suite de testes unitários (300 testes coletados)
├── pytest.ini                      # Resolução de paths para testes (cqt, ambiental, orcamento, cpfc, sob...)
├── Abrir_AUXCAD.bat                # Central Unificada Hub de Engenharia e Diagnóstico
├── Abrir_SOB.bat                   # Atalho de 2 cliques na raiz para Preparação de SOB
├── Abrir_CQT.bat                   # Atalho de 2 cliques na raiz para CQT
├── Abrir_Orcamento.bat             # Atalho de 2 cliques na raiz para Orçamento
├── Abrir_CPFC.bat                  # Atalho de 2 cliques na raiz para CPFC (REN 1.059)
├── Abrir_AutoPrancha.bat           # Atalho de 2 cliques na raiz para AutoPrancha
├── Abrir_Unifilar.bat              # Atalho de 2 cliques na raiz para Diagrama Unifilar
├── Abrir_Mapa_Postes.bat           # Atalho de 2 cliques na raiz para Estúdio Web Satélite
├── clean.bat                       # Script utilitário de limpeza de temporários e downloads
├── .env.example                    # Modelo seguro de variáveis de ambiente (GOMNET, GOM, URLs)
├── RAG/ & CAC.md                   # Base de conhecimento e arquitetura do projeto
│
├── orcamento/                      # Módulo Orçamento e Levantamento de Materiais (AutoLISP + Python + GUI)
├── cqt/                            # Módulo Queda de Tensão BT (AutoLISP + Python + GUI)
├── cpfc/                           # Módulo Participação Financeira REN 1.059 (AutoLISP + Python + GUI)
├── unifilar/                       # Módulo Diagrama Unifilar & Árvore de Dispositivos (AutoLISP + Python + SQLite)
├── ambiental/                      # Módulo Ambiental, KMZ, Ortofoto, Memorial e Checklist
├── mecanico/                       # Módulo Cálculo Estrutural e Resultante de Postes
├── mapa_postes/                    # Módulo Estúdio Web de Satélite, Coordenadas e Clientes
├── mapa_cad_paleta/                # Módulo Paleta C# (.NET) para AutoCAD 2018+ com Mapa OSM (Menos 1 tela)
├── dados_tecnicos/                 # Módulo Dados Técnicos e Tabelas de Referência
├── prancha/                        # Módulo AutoPrancha (Enquadramento Inteligente no ModelSpace - Enel/HBT)
├── softwares/                      # Instaladores e ferramentas de terceiros
└── documentos/                     # Pranchas DWG, planilhas de referência e notas técnicas
```

---

## Detalhamento dos Módulos e Componentes

### 1. Módulo Ambiental (`ambiental/`)
- `kmz_point_layer_report.lsp`: Seleção de pontos, caixas no CAD, disparo do memorial/checklist (`KMZCHECK`) e opção de traçado gráfico 2.5D dos polígonos de restrição ambiental no CAD com layer `AMB_POLIGONO_RESTRICAO`. Fluxo desacoplado: gera o **Checklist Ambiental (.xlsx)** com ou sem incidência ambiental cartográfica (atestando conformidade/isenção de restrições conforme exigência da concessionária), com comando de recarga rápida `RECARREGAR_KMZ` / `RECARREGAR_CHECKLIST`.
- `kmz_point_layer_report.py`: Parse completo de KMZ com suporte total a `MultiGeometry` (2.504 polígonos lidos), Snyder UTM $\rightarrow$ WGS84, indexação espacial por Bounding Box (`bbox`), Ray-Casting analítico, extração de polígonos para `kmz_polygons.json` e compilação automática da rotina AutoLISP `kmz_draw_polygons.lsp`.
- `memorial_ambiental_generator.py` (701 linhas): Interface visual moderna e responsiva (100% pt-BR) organizada em 2 colunas com cards brancos, header executivo (#1B365D), banner de status ambiental de alto contraste, suporte a BT divergente, preenchimento de campos de obra/município/projetista e disparo conjunto do Word e Excel:
  - **Regra de Negócio Condicional**:
    - **Com Restrição Ambiental (APP, UC, Amortecimento, Exclusão)**: Gera **ambos os documentos** na mesma pasta: o **Memorial Descritivo (`.docx`)** e o **Checklist Ambiental (`.xlsx`)** (`SIM`).
    - **Sem Restrição Ambiental (Livre de Restrições)**: O **Memorial Descritivo (`.docx`) É DISPENSADO**. Gera-se **obrigatoriamente o Checklist Ambiental (`.xlsx`)** (`NÃO`) atestando conformidade.
- `checklist_ambiental_manager.py`: Preenchimento automatizado da planilha `checklist.xlsx` da HBT/concessionária com marcas `✓` em APPs.
- `postes_detalhador.py`: Parser inteligente de blocos e atributos do CAD (`12/300`, `12/600`, `10/300` etc.).
- `croqui_ambiental_generator.py`: Gerador de Ortofoto / Croqui de Satélite georreferenciado (`CROQUI_AMBIENTAL_{SOB}.png`) com conversão Snyder analítica bidirecional (`latlon_to_utm`) e **Cache de Tiles em Disco** (`ambiental/.tile_cache/`) com chave MD5 para acelerar downloads e garantir custo zero de requisições.
- `croqui_cad_inserter.lsp`: Inserção automática de raster georreferenciado via ActiveX (`INSCROQUI`) em Model ou PaperSpace.
- `cad_to_kmz_exporter.py` & `cad2kmz.lsp` (298 linhas): Extração e exportação para Google Earth (`CAD2KMZ`) em formato WGS84 compactado:
  - Resolução segura de temporários via `vl-filename-mktemp`.
  - Suporte a extração do número real do poste via atributos do bloco (`cad2kmz-get-attr-num`).
  - Suporte completo a linhas e polilinhas (`LINE`, `LWPOLYLINE`, `POLYLINE` clássica).
  - Execução protegida via `WScript.Shell` com redirecionamento de log de diagnóstico e verificação do KMZ gerado.
- `app_buffer_generator.py` (633 linhas): Motor geodésico analítico de buffers de Áreas de Preservação Permanente (APP) para corpos hídricos conforme Código Florestal (Lei 12.651/2012):
  - **Cursos d'água / Rios / Córregos (<10m)**: Buffer bilateral contínuo de 30m ao longo do traçado geodésico com tampas semicirculares e junções angulares analíticas (`utm_buffer_linestring`).
  - **Nascentes e Olhos d'água**: Buffer circular geodésico de raio 50m (`utm_buffer_point`).
  - **Classificação Semântica Inteligente**: Reconhecimento de nomes e diretórios no KMZ/KML (`parse_kml_hydrography`).
  - **Auditoria Geodésica de Postes**: Ray-Casting analítico de postes contra polígonos de APP (`check_postes_in_hydro_app`), destacando em vermelho (`AMBIENTAL_APP_ALERTA`) postes que incidem em faixa marginal ou nascente.
  - **Geração de LISP Gráfico 2.5D**: Compilação de rotina ActiveX (`app_draw_buffers.lsp`) desenhando polilinhas fechadas e hachuras no layer `AMBIENTAL_APP_HIDRICA` (Ciano).
  - **Integração com Memorial e Checklist**: Alimenta automaticamente o arquivo `kmz_boxes.txt`, acionando as linhas 24 (Rio <10m) e 33 (Nascente) do `checklist.xlsx`.
- `app_buffer.lsp` (276 linhas): Comandos do AutoCAD **`APP_BUFFER`**, **`BUFFER_RIO`**, **`BUFFER_APP`**, **`APP_HIDRICA`** e **`RECARREGAR_BUFFER`**:
  - Modos de entrada flexíveis: **[K]MZ** (arquivo cartográfico externo), **[D]WG** (linhas/polilinhas/pontos selecionados na tela) ou **[A]uditoria** (seleção de postes para auditoria imediata).
  - Parâmetros normativos customizáveis no prompt com padrões da Lei 12.651 (30m rios / 50m nascentes).
- `preferencias_ambiental.json`: Smart Cache de parâmetros de formulário.

### 2. Módulo de Queda de Tensão BT (`cqt/`)
- `cqt_cad_extractor.lsp` (434 linhas):
  - **`CQT`** e **`CQTUI`**: Disparo instantâneo da Interface Gráfica para estudo prévio sem desenho.
  - **`CQTCAD`**: Extração interativa de vãos no CAD (seleção gráfica com soma automática de LINE, LWPOLYLINE, ARC) ou entrada manual de metragens; exportação segura de parâmetros e topologia em JSON via `vl-filename-mktemp`; disparo desacoplado via `(startapp "cmd.exe" ...)` idêntico ao `CQTUI`; garantia de robustez sem dependência de predicados não-nativos como `STRINGP` (uso de `(= (type x) 'STR)` e definição de compatibilidade); preenchimento automático do projeto, ponto trafo, potência, classe e trechos na UI.
  - **`CQTQUADROS`** (e **`CQTEXCEL`**): Desenha no CAD os Quadros de Resumo do Trafo (Verdes: 47,03 x 47,10) e Quadros de Trechos (Vermelhos: 33,21 x 13,64) com suporte nativo a seleção de planilha Excel existente (`.xlsx` ou `.xlsm`) via diálogo do Windows (`getfiled` com flag 16 e resolução absoluta com `DWGPREFIX`) ou reuso dos últimos quadros gerados em `C:\Temp\cqt_draw_quadros.lsp`.
  - **`RECARREGAR_CQT`**: Comando imediato para recarregar a rotina na memória do AutoCAD sem fechar o desenho.
- `cqt_live_calc.py` (352 linhas): Motor de cálculo instantâneo em memória ($QT \le 6,00\%$) com dicionário `CONDUTORES_K` cobrindo integralmente todos os 92 condutores homologados da distribuidora (FP 1 e FP 0,8).
- `cqt_excel_io.py` (381 linhas): Persistência atômica e leitura de planilhas Excel (`load_cables_from_database`, `get_default_template_path`, `load_scenario_from_excel`, `load_all_scenarios_from_excel`, `update_cqt_excel`). Resolução automática do template oficial em `modelos/cqt_modelo.xlsm` e catálogo completo de condutores com 92 itens em `DEFAULT_CABLES_BASE`.
- `cqt_scenario_tab.py` (380 linhas): Componente visual de edição de trechos por cenário (`ScenarioTab`), combobox com os 92 condutores oficiais, método `update_cables_list` para sincronização em lote e painel de Live Preview.
- `cqt_excel_manager.py` (409 linhas): Interface principal orquestradora (`CQTManagerGUI`) e CLI com botão integrado **"📥 Importar Planilha Existente"** para carregamento integral dos cenários ATUAL, ATUAL+NC e PROJETADO a partir de arquivos `.xlsx` ou `.xlsm`, resolução de template e propagação de novos condutores para as abas dos cenários.
- `modelos/cqt_modelo.xlsm`: Template oficial da concessionária Enel/HBT mantido localmente na pasta `modelos/` do repositório para garantir operação 100% offline.
- `cqt_quadros_generator.py` (717 linhas):
  - Ponte de alta fidelidade entre a planilha e o CAD para desenho dos Quadros Verdes de Resumo do Trafo (47.03 x 47.10) e Quadros Vermelhos de Queda de Tensão por Trecho (33.21 x 13.64).
  - **Extração Direta das Abas de Referência**: Lê diretamente das abas operacionais do projeto (`ATUAL`, `ATUAL+NC`, `PROJETADO` para cargas e `CQT ATUAL` / `CQT ATUAL+NC` / `CQT PROJETADO` para rede e quedas de tensão acumuladas na Coluna L), dispensando a aba `CAPA-RESUMO` (que continha dados legados estáticos). Calcula automaticamente os deltas de REQ. residencial e especial/não-residencial.
  - **Fallback Analítico Inteligente**: Caso a planilha seja gerada sem cache de fórmulas em células, aciona automaticamente o motor `calcular_cqt_topologia` de `cqt_live_calc.py`.
  - CLI flexível (`--excel`, `--trafo`, `--out`) e rotina LISP de desenho vetorial (`cqt-draw-trafo-box`, `cqt-draw-cqt-box`, `cqt-exec-draw-quadros`).
- `Abrir_CQT.bat`: Atalho executável direto com 2 cliques.

### 3. Módulo Mecânico (`mecanico/`)
- `CALC_RESULTANTE_v1.0.lsp` (v3.0): Inspeção de blocos `INSERT` em raio de 1.5m, cálculo de taxa de sobrecarga mecânica em daN e recomendação de estaiamento ou upgrade de poste.
- `CALC_ESF_AUTOCAD.mp4`: Demonstração operacional.
- `Poste Duplo T (11m 600 daN).SLDPRT`: Modelo 3D de poste duplo T.

### 4. Módulo de Topografia (`topografia/`)
- `kmz_pontos_importer.py` (228 linhas) & `kmz_pontos_importer.lsp` (79 linhas): Importador direto de marcadores do Google Earth (`.kmz`/`.kml`) para o AutoCAD via comando **`IMPORTAR_KMZ_POSTES`** (ou **`KMZPOSTES`**):
  - **Conversão Geodésica Snyder**: Converte `(lon, lat)` WGS84 para UTM SIRGAS 2000 (Fuso 23S/24S/automático) com precisão milimétrica sem custos de APIs.
  - **Inserção de Simbologia**: Insere o bloco **`POSTE_`** na coordenada UTM exata (vértice da rede/cabo).
  - **Bloco Numerador**: Insere o bloco **`PONTO`** com offset lateral e popula o atributo com o número do poste (`<name>`, ex: `05`).
  - **Descrição Técnica Lateral**: Extrai do campo `<description>` do Google Earth as linhas técnicas sanitizadas (`11/M`, `N1`, `S1`, `ESF. RESULTANTE...`) e desenha o bloco de texto MText empilhado no layer `POSTES_DESCRICAO`.
  - **Fallback Seguro**: Caso o DWG não tenha os blocos `POSTE_` ou `PONTO` pré-definidos, gera a geometria vetorial limpa (círculos e textos centralizados) sem falhas.
- `IMPORTADOR_CSV_CONTORNOS_v2.2.lsp`, `IMPORTADOR_CSV_PRO_v2.1.lsp`, `IMPORTADOR_CSV_PRO.lsp`, `importar-pontos_BASE.lsp`: Importadores CSV UTM clássicos.
- `IBCOORD.lsp`: Extração e anotação de coordenadas.
- `addbloco.lsp`: Inserção orientada ao UCS da tela.
- `pt2blk.lsp`: Conversão de pontos para blocos.
- `TLENTAB.lsp`: Tabelas e medições lineares.
- `mlrua.lsp` & `STYLE RODOVIA.mln`: Multilinhas para arruamento.
- `backup/`: Cópias históricas mantidas para segurança.

### 5. Módulo de Orçamento e Levantamento de Materiais (`orcamento/`)
- `orcamento_cad_extractor.lsp`: Extração gráfica ou varredura de todo o desenho (`ORCAD`) de postes (`INSERT`), condutores (`LINE`, `LWPOLYLINE`) com comprimentos analíticos e equipamentos/estruturas, gerando `orcamento_dados.json`. Comando `ORCUI` para abertura direta.
- `orcamento_core.py` (276 linhas): Motor analítico de classificação de postes, cálculo de condutores com margem técnica de flecha/amarras, explosão de estruturas e consolidação quantitativa.
- `orcamento_excel.py` (218 linhas): Exportador profissional de pastas de trabalho `.xlsx` estruturadas em 4 abas (`RESUMO ORÇAMENTO`, `DETALHAMENTO POSTES`, `DETALHAMENTO CABOS` e `BANCO DE PREÇOS`).
- `orcamento_gui.py` (271 linhas): Interface visual interativa em Tkinter 100% em pt-BR com KPIs em tempo real, tabela com filtros por categoria, slider de flecha (0-15%) e inserção manual.
- `orcamento_manager.py` (79 linhas): Orquestrador principal CLI/GUI e ponto de entrada do sistema.
- `orcamento_catalogo.json`: Base padronizada de códigos, unidades e preços de referência para redes de distribuição.
- `Abrir_Orcamento.bat`: Atalho executável direto com 2 cliques na raiz e na pasta do módulo.

### 6. Módulo Estúdio Web de Satélite (`mapa_postes/`)
- `mapa_servidor.py` (305 linhas): Servidor HTTP local leve e resiliente com endpoints REST:
  - `/api/postes` (GET/POST): Persistência em arquivo JSON local (`dados_postes.json`).
  - `/api/enviar-cad` (POST): Compilação instantânea da rotina AutoLISP `desenhar_postes_gerados.lsp` para desenho automático no AutoCAD.
  - `/api/exportar-kmz` (POST): Geração de arquivo `.kml`/`.kmz` compatível com o Google Earth Pro.
  - `/api/converter-coordenadas` (POST): Conversão bidirecional Snyder analítica UTM (Fuso 23S/24S) $\leftrightarrow$ Lat/Lon WGS84 para lançamento direto a partir do croqui de campo.
- `web/index.html` & `web/style.css` (451 linhas): Interface gráfica moderna em tema executivo `#1B365D` (Inter font, cards táteis, responsiva):
  - **Modal de Lançamento por Coordenadas**: Permite digitar coordenadas exatas do croqui de campo em **UTM Métrico** (E/X, N/Y, Fuso 23S/24S) ou **Graus Decimais (Lat/Lon)**, realizando cálculo em tempo real e animação `flyTo` no mapa.
  - **Card de Configuração do Poste**:
    - Tipos de Poste: 11/M, 11/400, 11/600, 11/1000, 12/300, 12/600, etc.
    - Estruturas MT: N1, N2, N3b, N4, CE1, CE2, etc.
    - Estruturas BT: S1, S2, F1, F2-D2, etc.
    - Equipamentos de 1 clique: IP, ATERR, DAE, Trafo, Chave Fusível, Para-raios.
    - **Quantificação de Clientes & Cargas Especiais Trifásicas**:
      - Lançamento rápido de clientes **Monofásicos (Mono)**, **Bifásicos (Bi)** e **Trifásicos (Tri)**.
      - **Cargas Especiais Trifásicas Interligadas**: Permite informar a potência em **kVA** ou em **kW** com conversão bidirecional automática em tempo real através do Fator de Potência **FP = 0.92** ($kVA = kW / 0.92$ e $kW = kVA \times 0.92$), com chips de sugestão rápida (Bomba, Trafo, Motor, Comércio, Serralheria) e geração de linha técnica formatada no CAD (`CARGA TRI: BOMBA 16.3kVA (15kW)`).
- `web/app.js` (368 linhas): Orquestração do mapa Leaflet com tiles de satélite ESRI World Imagery, Google Híbrido e OSM, marcadores arrastáveis, cálculo de vão linear, conversão instantânea de potência e conexão das redes.
- `mapa_cad_launcher.lsp` (85 linhas): Comandos do AutoCAD:
  - **`MAPAPOSTES`** (ou **`MAPA`**): Abre o estúdio no navegador e inicia o servidor caso esteja desligado.
  - **`ATUALIZAR_MAPAPOSTES`**: Lê os postes enviados pelo mapa web e gera os blocos `POSTE_`, `PONTO` e os textos técnicos empilhados no AutoCAD.
- `Abrir_Mapa_Postes.bat`: Atalho executável de 2 cliques para abertura direta do estúdio.

### 7. Módulo Paleta Cartográfica OSM C# (.NET) - Menos 1 Tela (`mapa_cad_paleta/`)
- `MapaCadPaleta.csproj`: Projeto C# com arquitetura **Multi-Targeting** moderna compilando simultaneamente para:
  - **`net8.0-windows`**: Para AutoCAD 2025 e AutoCAD 2026.
  - **`net48`**: Para AutoCAD 2018 a 2024 (executando sobre o runtime clássico .NET Framework 4.7/4.8).
  - Integração com `Microsoft.Web.WebView2` e referências nativas à API do AutoCAD (`accoremgd`, `acdbmgd`, `acmgd`).
- `Plugin.cs`: Ponto de entrada (`IExtensionApplication`) com comandos do AutoCAD:
  - **`MAPAPALETA`** (ou **`OSMPALETA`**, **`MAPACAD`**): Abre a paleta cartográfica acoplável.
  - **`FECHAR_MAPAPALETA`**: Oculta a paleta.
  - **`RECARREGAR_MAPAPALETA`**: Recarrega os componentes da paleta.
- `PaletteHost.cs`: Gerenciador da paleta nativa `PaletteSet` (GUID único), com ancoragem à direita, auto-hide e hospedagem visual direta de controle WPF.
- `MapaControl.xaml` & `MapaControl.xaml.cs`: Controle WPF hospedeiro do controle Chromium `WebView2` com **Mapeamento de Host Virtual Seguro (`https://appassets.example/index.html`)** com validação rigorosa de origem (`IsAuthorizedOrigin`), operando 100% isolado dentro do AutoCAD.
- `CadBridge.cs`: Ponte de automação transacional do AutoCAD (`DocumentLock`, `Transaction`):
  - **Separação Canônica de Identidades de Domínio**:
    - `DomainId`: Identificador único persistente da entidade elétrica (GUID RFC4122 v4), autoridade final mantida no C# .NET, independente do número visual.
    - `Numero`: Rótulo de apresentação visual do poste (ex: "01", "P01"), não utilizado como chave primária de persistência (`Numero != DomainId`).
    - `VaoId`: Identificador único persistente do vão de rede (GUID RFC4122 v4), independente do `OperationId`.
    - `PosteOrigemId` & `PosteDestinoId`: Vínculos relacionais topológicos por `DomainId` persistente (não por número nem proximidade geométrica).
    - `OperationId`: Agrupamento transacional da operação executada.
    - `Handle`: Identificador físico atual da entidade no banco de dados do DWG.
  - **Identidade Persistente BIM via XData Versionado (`schemaVersion = 2`)**: Aplicações DXF registradas oficiais `AUXCAD_POSTE` e `AUXCAD_VAO` gravando cabeçalho de versão `ExtendedDataInteger16 = 2`, `DomainId`, `Numero`, `TipoPoste`, `VaoId`, `PosteOrigemId`, `PosteDestinoId`, `OperationId` e metadados JSON com parsing defensivo (`IsValid`/`InvalidReason`).
  - **Pipeline Modular de Escaneamento e Reconciliação (`EscanearDwg`)**:
    - `LerEstadoDwg`: Varredura estritamente somente-leitura e defensiva sem efeitos colaterais no DWG.
    - `ReconciliarTopologiaDwg`: Resolução canônica por identidade (`Exact`), resolução geométrica para legados `< 1.0m` (`Inferred`), detecção de ambiguidades (`Ambiguous`) e detecção de vãos órfãos (`ORPHAN_VAO`).
    - `ExecutarReparosDwg`: Transação explícita de mutação para reatribuição de GUIDs de clones gerados por `COPY`/`ARRAY` e remapeamento de conjunto (`COPY_SET_REPAIRED`).
    - Objeto de saída `DwgState` contendo `Postes`, `Vaos`, `Relacoes`, `Diagnostics` e `Statistics`.
  - **Undo / Rollback Seguro e Independente do Número Visual**: Rollback atômico cirúrgico rastreado em sessão via lista de Handles em `_historicoOperacoes` e busca persistente no DWG por `OperationId` e `DomainId`, eliminando dependência do número visual (`Contains(numero)`) e prevenindo deleções indevidas.
  - Inserção do bloco `POSTE_` (com fallback para círculo/cruz vetorial) na coordenada UTM exata (2.5D, $Z=0.0$).
  - Inserção do bloco `PONTO` com número do poste no atributo.
  - Inserção de texto técnico empilhado MText com tipo de poste, estruturas MT/BT, equipamentos e cargas trifásicas.
  - Inserção de vãos de condutores (`VIAS_CABOS_BT` / `VIAS_CABOS_MT`) com texto de distância alinhado ao vão e gravação de `VaoId`.
  - Captura interativa de coordenadas no DWG via `Editor.GetPoint` e envio ao mapa via WebMessage.
- `SnyderConverter.cs`: Conversor analítico Snyder geodésico C# bidirecional entre Lat/Lon WGS84 e UTM SIRGAS 2000 (Fuso 22S, 23S e 24S) com precisão milimétrica.
- `web/index.html`, `web/style.css`, `web/app.js` e `web/tracado.js`: Interface moderna em tema corporativo `#1B365D`, alternância entre OSM, Satélite ESRI e Google Híbrido, marcador arrastável, conversão kVA $\leftrightarrow$ kW com FP = 0.92, chips rápidos de equipamentos/cargas, traçado contínuo com geração de vãos automáticos, arrasto dinâmico de postes, undo bidirecional (UI + DWG) e reconstrução topológica do traçado (`reconstruirTracadoDoDwg`).
- **Geração Automática de Vias no AutoCAD ao Inserir Postes**:
  - Opção explícita no rodapé da sidebar (`chkAutoViasCad`) e no traçado contínuo (`chkTracadoViasCad`).
  - Sincronização bidirecional e deduplicação inteligente por `waysProcessados`.
  - Cobertura geodésica contínua: cálculo analítico imediato de coordenadas via `window.Snyder`, consulta resiliente na Overpass API via POST form-urlencoded e desenho direto de polilinhas 2.5D no DWG nos layers `VIAS_EIXO`, `VIAS_CALCADA` e `OBSTRUCOES_EDIF`.
- `mapa_paleta_loader.lsp`: Carregador AutoLISP com detecção dinâmica da versão do AutoCAD (`ACADVER`) e disparo via `NETLOAD`.

### 8. Módulo de Dados Técnicos e Tabelas de Referência (`dados_tecnicos/`)
- `tabelas_referencia.py` (520 linhas): Motor analítico e gerador dos bancos de dados técnicos oficiais das redes BT e MT (Fontes: OneNote `BASE.one` e diretório `CALC_ESF` da IM3 Brasil):
  - **Tabela 9 - Condutores de Baixa Tensão**: Relação de cabos (`3x150+1x80`, `3x95+1x54,6`, `3x50+1x54,6`, `3x35+1x54,6`) com correntes nominais, trações em daN (554, 393, 260, 235 daN), diâmetros, massas e impedâncias nominais ($R$ e $X$).
  - **Tabela 7 - Estruturas de Baixa Tensão**: Matriz completa de estruturas BT (`SI1`, `SI1.AF`, `SI1.2AF`, `SI1B.SI3`, `SI1A.SI3`, `SI1.SI4`, `SI3.S3`, `SI4.SI3`, `SI4`, `SI3`, `SI3.SI3`, `DERIV_VAO`, `FLYTAP`), limites angulares e resistências mecânicas de poste (300/600 daN).
  - **Tabelas de Média Tensão (MT)**: Esforços nominais por vão para condutores de MT: `1/0 CAA`, `4/0 CAA`, `336,4 CAA`, `4 CAA`, `1/0 CA`, `4/0 CA`, `336,4 CA`, `2 CA`, `35/50 XLPE` e `185 XLPE`.
  - **Interpolação Contínua & Regra de 3**:
    - *Vãos intermediários*: Interpolação linear precisa entre os dois pontos tabelados adjacentes (ex: 35m no 1/0 CAA = 450 daN).
    - *Vãos curtos (<20m)*: Regra de três proporcional ao menor vão tabelado (ex: 10m no 1/0 CAA = 187,5 daN).
    - *Vãos longos (>200m)*: Extrapolação linear pela inclinação final (ex: 220m no 1/0 CAA = 1.473 daN).
  - **Combinações Paralelas Colineares MT + BT**:
    - Suporte nativo à expressão com `+` (ex: `1/0 + 150`, `4/0 CAA + PR95`). Os vetores colineares compartilham ângulo e direção geométrica no DWG, somando algebricamente seus módulos vetoriais: $\vec{F}_{total} = \vec{F}_{MT} + \vec{F}_{BT}$ (ex: 450 daN MT + 554 daN BT = 1.004 daN total).
  - **Interoperabilidade SQLite3 & JSON**: Banco relacional `tabelas_referencia.sqlite3` com tabelas `condutores_bt`, `estruturas_bt` e `cabos_mt_esforcos` indexadas, além do arquivo padronizado `tabelas_referencia.json` (v2.0.0).
- `tabelas_referencia.lsp` (515 linhas): Biblioteca AutoLISP de altíssima velocidade para consulta direta de LISPs:
  - Comandos: **`TABELAS`**, **`CONDUTORES_BT`** (ou **`BT`**), **`ESTRUTURAS_BT`**, **`CABOS_MT`** (ou **`MT`**) e **`CONSULTAR_TABELA`**.
  - Prompt interativo tolerante e ágil em `TABELAS`: aceita letras e números `[C]ondutores BT`, `[E]struturas BT`, `[M]T Cabos`, `1`, `2`, `3`, `BT`, `MT` ou Enter para o padrão.
  - Funções reutilizáveis: `(tb-get-condutor chave)`, `(tb-get-tracao chave)`, `(tb-get-tracao-mt chave n_fases)`, `(tb-interpolar-mt chave vao_m)`, `(tb-calcular-linha-esforco input vao_m)`, `(tb-get-estrutura cod fase)`, `(tb-list-condutores)`, `(tb-list-estruturas)`.
  - Integração no `CALC_RESULTANTE_v1.0.lsp`:
    - Medição geométrica automática do vão no CAD (`vlax-curve-getDistAtParam`).
    - Exibição da extensão medida no prompt: `[Vão medido no CAD: X.X m]`.
    - Suporte a valor manual puro em daN (`350`, `150d`, `=400`), código de cabo MT/BT ou expressão colinear MT+BT (`1/0 + 150`), com tecla `?` com loop de consulta interativa sem travar o cálculo.
    - Comandos de recarga rápida: **`RECARREGAR_RESULTANTE`** e **`RECARREGAR_MECANICO`**.

### 8. Módulo de Participação Financeira do Consumidor (`cpfc/`)
- `cpfc_core.py` (102 linhas):
  - Implementação das fórmulas oficiais da Resolução Normativa ANEEL Nº 1.059 (Válido até 10/03/2027 - Versão 03).
  - Tabela de Fatores K da concessionária ($K_{carga}$ e $K_{geração}$) com resolução exata para os 13 subgrupos (`B1`, `B2rur`, `B2irrig`, `B3`, `B4a`, `B4b`, `A4`, `A3a`, `A3`, `A2`, `AS`, `BT1 Geração`, `BT2 Geração`).
  - Cálculo de $\text{ERD} = \text{Demanda Carga} \times K_c + \max(0, \text{Geração} - \text{Carga}) \times K_g$.
  - Proporcionalização de custos $\text{COP} = \text{Custo Total da Obra} \times \left(\frac{\max(\text{Carga}, \text{Geração})}{\text{Demanda Disponibilizada}}\right)$.
  - Cálculo da Participação Financeira $\text{PF} = \max(0, \text{COP} - \text{ERD})$ e alertas de suficiência de demanda.
- `cpfc_excel.py` (43 linhas):
  - Camada de manipulação de planilhas via `openpyxl`.
  - Injeção precisa nos campos cadastrais (`C11:G11`, `C13:G13`, `C15:G15`, `C17:G17`, `C19:G19`), custos (`C24`, `F30`, `F31`) e demandas elétricas (`C41`, `C43`, `G66`, `G80`).
  - Preservação estrita de fórmulas nativas (`F32`, `G70`, `G72`, `G74`, `G76`, `G82`, `G84`, `G86`, `G88`, `G93`), estilos de formatação e imagens do cabeçalho.
- `cpfc_gui.py` (494 linhas):
  - Interface moderna em Tkinter 100% em pt-BR com tema corporativo `#1B365D`.
  - Layout dividido em 4 cards: Dados Cadastrais, Custos da Obra, Demandas Elétricas e Live Preview de Indicadores.
  - Indicadores em tempo real para ERD, Fator de Proporcionalização e COP.
  - Banner dinâmico de status: Destaque verde para Isenção de PF ou âmbar para Valor Devido.
  - Botão integrado no cabeçalho: **"📘 Regras REN 1.059 (Casos de PF)"** abrindo modal explicativo.
  - Diálogo nativo `filedialog.asksaveasfilename` com sugestão inteligente de nome (`PE_{PROJETO}_CPFC_REN1.059.xlsx`).
  - Atalhos de pós-geração: Abrir no Excel ou Abrir Pasta de Destino.
- `cpfc_guia_ren1059.py` (28 linhas):
  - Guia didático das regras da REN 1.059/2023 e REN 1.000/2021 detalhando quando há incidência de PF (COP > ERD, MMGD, tensão diferenciada, trafo exclusivo) e quando há gratuidade.
- `cpfc_manager.py` (36 linhas): Orquestrador com suporte a CLI, pasta padrão do DWG e intercâmbio JSON.
- `cpfc_cad_launcher.lsp` (98 linhas):
  - Comandos do AutoCAD **`CPFC`** / **`CPFCUI`** (abertura direta com aviso regulatório).
  - Comando **`CPFCCAD`** (com leitura do projeto e pasta do DWG aberto).
  - Comando **`CPFCALERTA`** / **`CPFCREGRA`** (caixa de diálogo visual detalhando os casos que geram PF).
- `modelos/cpfc_modelo.xlsx`: Planilha modelo de referência padronizada.
- `Abrir_CPFC.bat`: Atalho executável na raiz e em `cpfc/`.

### 9. Módulo Diagrama Unifilar & Árvore de Dispositivos (`unifilar/`)
- `arvore_parser.py` (331 linhas):
  - Parser analítico de caminhos elétricos (` > ` ou `|`) com responsabilidade única de localizar a **primeira proteção a montante** a partir de um Ponto Elétrico alvo (ex: `SG40995` $\rightarrow$ `Chave Fusivel - SG59356`, `N760355` $\rightarrow$ `ZSL10 - Saida do Alimentador - ZSL10`).
  - Suporte completo a strings de nós de 3 partes no padrão oficial da concessionária (`[COD_ALIM] - Saida do Alimentador - [COD_ALIM] Clientes Grupo A: X Clientes Grupo B: Y - KVA: Z`).
  - Reconhece os tipos elegíveis de proteção: `Chave Fusivel`, `Religador`, `Disjuntor` ou a própria `Saida do Alimentador` quando não há proteção intermediária (excluindo expressamente chaves faca, chaves NA, CTLs e transformadores/CDs).
  - Extração de Subestação e Alimentador a partir da saída (`ZSL10` $\rightarrow$ `SE.: ZSL`, `ALIM.: 10`).
  - Extração e enriquecimento em tempo real de `Clientes Grupo A`, `Clientes Grupo B` e potência `KVA`.
  - Formatação padronizada das linhas do Diagrama Unifilar para o AutoCAD com espaçamento estrito `DISPOSITIVO DE PROTEÇÃO: <rotulo>`.
- `arvore_database.py` (227 linhas):
  - Camada de indexação e persistência local em SQLite (`unifilar/arvore_cache.sqlite3`).
  - Povoa a base a partir da planilha oficial `documentos/Árvore de Dispositivos.xlsx` com busca indexada em menos de 10ms.
- `arvore_client.py` (162 linhas):
  - Cliente com suporte a requisições web à intranet (`URL_ARVORE_DISPOSITIVOS`), autenticação NTLM com credenciais do `.env` e fallback automático e transparente para a base local ou modo resumo manual (`consultar_resumo_manual`).
- `dispositivos_kmz_finder.py` (267 linhas):
  - Localizador geoespacial e analítico de chaves fusíveis, religadores e chaves nos arquivos KMZ de apoio da concessionária (`kmz - Dispositivos 05-2020`).
  - Indexa **134.082 dispositivos reais** com cache local em `dispositivos_kmz_cache.json` e busca instantânea (<5ms) por código (`CF636018`, `SG59356`, `AR010625`) ou dígitos.
  - Conversão analítica Snyder de WGS84 para UTM SIRGAS 2000 (Fuso 23S/24S).
- `unifilar_diagrama_builder.py` (204 linhas):
  - Construtor vetorial 2.5D do Diagrama Unifilar Esquemático sem escala (SE $\rightarrow$ Tronco MT $\rightarrow$ Proteção $\rightarrow$ Ramal MT $\rightarrow$ Ponto do Projeto).
  - Determinação inteligente de blocos oficiais do AutoCAD: **`"chaves_"`** para chaves fusíveis / seccionadoras e **`"REL"`** para religadores.
- `unifilar_manager.py` (161 linhas):
  - Orquestrador CLI e ponte de intercâmbio JSON com o AutoCAD (`--ponto`, `--resumo`, `--out`, `--sincronizar`, `--fuso`, `--escala`), unificando árvore, busca KMZ e geometria do diagrama.
- `unifilar_cad.lsp` (640 linhas):
  - Comandos do AutoCAD **`UNIFILAR`** e **`PROTECAO`** (aliases: **`ARVORE`**, **`BUSCAR_PROTECAO`**).
  - Suporta digitação do ponto elétrico, seleção direta no DWG (`entsel`) ou **colagem direta da linha de resumo copiada do SGT/GOMNET** no prompt.
  - **Gerenciamento do Bloco do Transformador (`TRAFO1`)**:
    - Substituição do bloco genérico `"T"` pelo bloco oficial **`"TRAFO1"`** (com fallback sequencial para `"TRAFO"` e `"T"`).
    - Suporte interativo completo: tecla Enter para aceitar `<TRAFO1>` (ou o último memorizado na sessão), opção `[L]` ou `[?]` para listar blocos disponíveis no DWG e selecionar por número, ou opção `[S]` para selecionar diretamente um bloco na tela com 1 clique.
  - Opções integradas de geração:
    - **[1] Esquema Prancha**: Gera o título verde sublinhado, textos técnicos alinhados à direita e o Diagrama Unifilar Esquemático 2.5D sem escala com barramento SE, tronco MT, bloco oficial da proteção (`"chaves_"` ou `"REL"`), ramal MT e bloco oficial do Transformador (`"TRAFO1"` / `"TRAFO"` ou fallback vetorial normativo de 2 círculos tangentes) com indicação de kVA.
    - **[2] Ramal Geográfico DWG**: Traça no ModelSpace o ramal MT a partir da coordenada real do dispositivo no KMZ até o poste/ponto selecionado no DWG, inserindo bloco da proteção, bloco do transformador (`TRAFO1`) e cota métrica com extensão real do ramal.
    - **[3] Ambos**: Executa o esquema na prancha e o traçado geográfico no DWG.
    - **[4] Somente Texto**: Inserção dos textos técnicos clássicos.
    - **[A]tualizar**: Seleciona textos existentes no DWG e substitui placeholders preservando a diagramação existente.

### 10. Módulo de Orçamento e Levantamento de Materiais e Mão de Obra (`orcamento/`)
- `orcamento_builder.py` (345 linhas): Motor de compilação e extração das bases oficiais da concessionária e empreiteiras (`sisORÇA.xlsx`, `KITS E MATERIAIS REV_31`, `Mão de Obra 31-05-2024.xlsm`), gerando a base SQLite local indexada `orcamento_dados.sqlite3` (13.822 materiais cadastrados, 28.709 kits de estruturas e 5.158 itens contratuais de mão de obra) e o cache JSON `orcamento_dados.json`.
- `orcamento_database.py` (168 linhas): Repositório DAO de alto desempenho (<15ms) com queries parametrizadas para consulta de materiais por código SAP/E4E ou SIE, busca de componentes de kits e recuperação de tabelas de mão de obra por contrato/empreiteira e classe territorial.
- `orcamento_kits.py` (144 linhas): Motor de normalização e explosão de kits oficiais:
  - Mapeia estruturas MT/BT (`M1`, `M2`, `B1`, `B2`, `N1`, `N2`...), taqueamento de transformadores (`TR-MONO`, `TR-BI`, `TR-TRI`), aterramentos (`ATER_EQUIP`) e estais (`ESTAI-7,9`).
  - Desdobra cada estrutura nos materiais reais de almoxarifado da distribuidora com quantidades normativas e ambientes Normal (`NA`) e Agressivo (`AA` / Salinidade).
- `orcamento_core.py` (405 linhas): Motor analítico central de regras de negócio:
  - Classificação inteligente de postes e cabos extraídos do CAD ou da Paleta OSM.
  - Orquestração da explosão de kits e precificação real em R$.
  - Cálculo segregado da Mão de Obra Contratual para as 4 empreiteiras:
    - **INDICA** (Cantagalo/Pádua - Contrato `JA10110552` - Unidade Base `0010552`)
    - **ENGELMIG** (Itaperuna/Campos - Contrato `JA10114811` - Unidade Base `0002042`)
    - **DÍNAMO** (Lagos - Contrato `52L0002297` - Unidade Base `0002297`)
    - **PROGEN** (Macaé - Contrato `JA10083389` - Unidade Base `0002043`)
  - Classificação de Território em Classes **A**, **B** e **C**.
  - Totalizadores segregados: `total_materiais`, `total_mao_de_obra`, `total_bdi` e `total_geral`.
- `orcamento_excel.py` (300 linhas): Exportador profissional de planilhas Excel `.xlsx` em 5 abas integradas:
  - `RESUMO ORÇAMENTO`: Metadados da obra, cards de KPI e consolidação geral.
  - `DETALHAMENTO MÃO DE OBRA`: Relação contratual com vozes, baremos SAP e custos unitários.
  - `DETALHAMENTO POSTES` & `DETALHAMENTO CABOS`: Dados de engenharia e geometria extraídos do DWG.
  - `FORMATO sisORÇA`: Colunas compatíveis para colagem direta na aba `ORÇA` da planilha oficial.
- `orcamento_gui.py` (390 linhas): Interface gráfica moderna em Tkinter (100% pt-BR) com layout executivo `#1B365D`:
  - Seleção de Empreiteira, Classe de Território e Ambiente Salino.
  - Painel de KPIs em tempo real (Materiais, Mão de Obra e Total Geral).
  - Alternância de visualização entre Materiais Orçados e Mão de Obra Contratual.
- `orcamento_manager.py` (97 linhas): Orquestrador de linha de comando (CLI) e ponte com a rotina AutoLISP `orcamento_cad_extractor.lsp` (`ORCAD` / `ORCUI`).
- `Abrir_Orcamento.bat`: Atalho executável de 2 cliques na raiz e em `orcamento/`.

### 11. Carregamento Universal & Auditoria de Integridade (`acaddoc.lsp`)
O arquivo `acaddoc.lsp` atua como o ponto central de inicialização e orquestração do AUX CAD:
1. **Compatibilidade Global**: Funções de segurança e reflexão pré-carregadas (`stringp`, `fboundp`, `vl-symbol-p`, `vl-sleep`, `vl-filename-nxname`), prevenindo erros de ambiente em qualquer versão de AutoCAD.
2. **Resolução Dinâmica**: Localiza o caminho absoluto da pasta raiz e adiciona dinamicamente as 9 pastas dos módulos ao `SupportPath` de suporte do AutoCAD (`cqt`, `ambiental`, `mecanico`, `topografia`, `orcamento`, `mapa_postes`, `dados_tecnicos`, `cpfc`, `unifilar`).
3. **Carregamento Seguro**: Utiliza `load-aux-safe` com `vl-catch-all-apply` e fallbacks automáticos.
4. **Comando Mestre de Recarga**: Comando **`RECARREGAR_TUDO`** (ou **`RELOAD_AUXCAD`**) para recarregar todos os 10 módulos e menus de uma só vez na memória do AutoCAD.
5. **Barra de Ferramentas e Menus Nativos**: `aux_cad_toolbar.lsp` e `aux_cad_menu.mnu` atualizados com 20 ferramentas integradas em 1 clique.

### 11. Validação, Debug Completo e Testes
- **Auditoria de Sintaxe AutoLISP**: 100% dos 28 arquivos `.lsp` do projeto validados e com balanceamento de parênteses e strings verificado (0 erros).
- **Auditoria de Módulos Python**: 100% dos arquivos `.py` compilados e validados contra regras de Clean Code e limites de linhas (<750 linhas).
- **Suíte de Testes**: **155 testes unitários passando com 100% de sucesso** (`python -m pytest`).

- **Cobertura de Código**: Cobertura crítica de 88% no módulo `unifilar` (com 100% no `unifilar_diagrama_builder`), 85% no `cqt_quadros_generator`, 83% no `mapa_servidor` e acima de 80% a 100% em todos os módulos de domínio.

### 12. `mapa_cad_paleta/` (Paleta Cartográfica OSM C# .NET para AutoCAD 2018+)
- **Objetivo**: Alternativa direta integrada ao AutoCAD ("menos 1 tela"), permitindo visualizar mapas Leaflet (OSM, Satélite ESRI e Google Híbrido), buscar posições e inserir postes com blocos e textos MText diretamente no ModelSpace do desenho ativo sem necessidade de navegador externo ou KMZ intermediário.
- **Arquitetura Multi-Targeting C#**:
  - `net8.0-windows` para AutoCAD 2025/2026.
  - `net48` para AutoCAD 2018-2024.
  - `Microsoft.Web.WebView2` com carregamento isolado e injeção dinâmica de caminhos nativos no `PATH` do processo `acad.exe`.
- **Layout Moderno Sidebar & Suporte a Multi-Estruturas**:
  - Mapa em tela cheia com barra flutuante de camadas (OSM, Satélite ESRI, Google Híbrido), ferramentas de captura (`🎯 Ler DWG`), sincronização de postes existentes (`🔄 Sincronizar`) e alternador retrátil do painel lateral (`📑 Painel ◀/▶`).
  - **Múltiplas Estruturas MT e BT**: Combobox expansível + botão `➕` + chips de atalho rápido (`+ N1`, `+ N2`, `+ N3b`, `+ CE1`, `+ S1`, `+ S2`, `+ F1`, `+ F2-D2`). Permite empilhar N estruturas simultâneas exibidas como badges interativos com remoção em 1 clique (`✕`).
  - **Seleção Dinâmica de Potência do Transformador**: Chip de trafo reativo (`🔋 Trafo <potência>`) com painel expansivo contendo as potências padronizadas de distribuição (15kVA, 30kVA, 45kVA, 75kVA, 112.5kVA, 150kVA, 225kVA, 300kVA e campo customizável).
- **P2 - Modo Traçado Contínuo de Linhas/Vãos no CAD (`tracado.js`)**:
  - Permite ligar o botão `📐 Modo Traçado` na barra superior para conectar automaticamente postes consecutivos.
  - Painel flutuante com alternador de tipo de rede (`BT` em Amarelo / `MT` em Ciano), contador de postes conectados, botão `↩️ Desfazer` (atalho `Ctrl+Z`), botão `📋 Postes` (gaveta com lista e foco 👁️) e botões `🏁 Finalizar Trecho` / `Limpar`.
  - **Edição e Movimentação Interativa**: Todos os postes do traçado contínuo geram marcadores numerados arrastáveis (`draggable: true`). Ao mover qualquer poste no mapa, suas coordenadas UTM são recalculadas analiticamente via Snyder e todos os vãos e rótulos adjacentes são reajustados em tempo real.
  - **Exclusão Rápida e Desfazer**: Suporte a remoção individual por clique com botão direito no marcador, popup de gestão rápida e atalho `Ctrl+Z` para reverter o último poste mantendo o restante do traçado íntegro.
  - **Cálculo Analítico de Vão**: Medição métrica exata em UTM via `Math.hypot(dx, dy)` exibida em etiquetas intermediárias no Leaflet (`38.5m`).
  - **Desenho Automático no DWG (`CadBridge.InserirVaoCabos`)**: Traça a entidade `Line` entre centros de postes no layer `CABOS_BT` (Cor 2 - Amarelo / Yellow) ou `CABOS_MT` (Cor 4 - Ciano / Cyan) e insere `DBText` no layer `CABOS_TEXTO` (Cor 7 - Branco / White) alinhado ao vão com correção de ângulo para legibilidade técnica sem inversão de cabeça para baixo. Suporte a rollback e aviso via ação `desfazer_vao`.
- **P4 - Camada de Restrições Ambientais com Auditoria em Tempo Real (`ambiental_overlay.js` & `AmbientalParser.cs`)**:
  - Botão `🌿 Restrições` na barra superior para carregar e alternar a visualização de polígonos geoespaciais ambientais diretamente sobre as ortofotos de satélite.
  - **Parser C# Multi-Formato (`AmbientalParser.cs`)**: Leitura e extração direta de arquivos `.kmz` (descompactação zip e parse de KML), `.kml` (XML Linq com suporte a namespaces) e `.geojson`/`.json` com conversão para formato Leaflet `[lat, lon]`.
  - **Estilização Inteligente por Categoria**: Cores normativas para APP (Laranja `#f77f00`), Exclusão/Faixa de Servidão (Vermelho `#d90429`), Unidade de Conservação (Verde petróleo `#2a9d8f`) e Área Hídrica (Azul `#0077b6`).
  - **Auditoria Instantânea via Ray-Casting Analítico**: Conforme o marcador do poste é movido ou inserido, o algoritmo de Jordan Ray-Casting verifica se as coordenadas incidem dentro de qualquer polígono cadastrado.
  - **Banner Dinâmico de Auditoria (`#bannerAmbiental`)**: Exibe em tempo real no topo da sidebar:
    - *Verde*: `🌿 Ponto Seguro: Fora de restrições ambientais`.
    - *Vermelho Pulsante*: `⚠️ ATENÇÃO: Ponto dentro de [Nome da Área] ([Categoria])`.
- **Ferramenta de Medição / Régua Métrica e Geodésica (`medicao.js`)**:
  - Botão `📏 Régua` na barra de ferramentas superior (e atalho de teclado `M` / `ESC` para fechar) com cursor em `crosshair`.
  - **Linha Elástica (Rubberband) em Tempo Real**: Conforme o usuário move o cursor após o 1º clique, exibe a distância instantânea em metros e o azimute em graus (°).
  - **Medição Multi-Segmentos**: Adiciona vértices consecutivos com tooltip permanente contendo a distância do trecho e acumulada (`P1`, `+32.4m (32.4m)`, etc.).
  - **Painel Flutuante Interativo (`#painelMedicao`)**: Exibe Total Medido, Último Trecho, Azimute e botões ágeis:
    - `📍 Do Poste`: Inicia a medição exatamente a partir da coordenada do poste ativo no mapa.
    - `📍 Poste Aqui`: Move o marcador de implantação de poste exatamente para a coordenada do último ponto medido na régua.
    - `🗑️ Limpar`: Reseta a geometria da régua sem desativar a ferramenta.
- **Renderização de Vias, Calçadas (Passeios) e Obstruções no Traçado Contínuo (`vias_obstrucoes.js`)**:
  - Botão `🏙️ Vias: VISÍVEIS` na barra superior para alternar a exibição vetorial urbana com dados reais do OpenStreetMap (Overpass API com custo zero).
  - **Carregamento Automático ao Lançar Postes**: Ao adicionar postes sequenciais no modo traçado contínuo, consulta automaticamente a Bounding Box em torno do novo poste (buffer métrico de 100m) com cache de quadrículas (`cacheGrid`) para nunca duplicar tráfego.
  - **Separação Semântica das Camadas Urbanas**:
    - **Vias e Ruas (`highway`)**: Pistas e eixos de rolamento em asfalto escuro (`#334155`) com espessura destacada e tooltip com o nome do logradouro.
    - **Calçadas e Passeios Públicos (`footway=sidewalk`, `sidewalk`)**: Faixas em âmbar/bege (`#d97706`) delimitando o passeio público para locação correta do poste fora da pista.
    - **Obstruções Físicas e Edificações (`building`, `barrier`)**: Polígonos de edificações em ardósia semitransparente (`#94a3b8`) e muros/barreiras em vermelho pontilhado (`#dc2626`) alertando contra colisão visual de vãos.
  - **Desenho 2.5D Automático e Sob Demanda no AutoCAD (`CadBridge.DesenharElementosUrbanos`)**: Lançamento das geometrias no DWG nos layers `VIAS_EIXO` (Cor 8 - Cinza escuro), `VIAS_CALCADA` (Cor 9 - Cinza claro) e `OBSTRUCOES_EDIF` (Cor 1 - Vermelho), com anotação automática do nome das ruas em `DBText` no centróide da polilinha. Consulta com prioridade para a **API Oficial do OpenStreetMap** (`https://api.openstreetmap.org/api/0.6/map.json`), eliminando bloqueios HTTP 406 e CORS em WebView2, suportando parsing híbrido JSON/XML com zero custo e tempo de resposta <1s. Ativo por padrão (`desenharNoCad: true`) com botão dedicado **`🛣️ Vias no CAD`** na barra superior e no painel de traçado para desenho instantâneo de toda a extensão do projeto.
- **Anti-Sobreposição Gráfica 2.5D no AutoCAD**:
  - `ptPoste`: inserção central na coordenada UTM exata $(X, Y)$ do bloco `POSTE_` (ou círculo `R=0.6m`).
  - `ptNum` (Bloco `PONTO`): deslocado analiticamente para $(X - 2.8, Y + 1.8)$, desobstruindo totalmente a simbologia física do poste e os textos descritivos.
  - `ptDesc` (`MText` técnico): deslocado para $(X + 1.8, Y + 1.2)$ com alinhamento `TopLeft`, empilhando tipo de poste, estruturas MT/BT individuais e identificação de trafo sem colisão visual.
- **Inserção do Bloco `"T"` de Transformador**:
  - Quando o equipamento `Trafo` está ativo, o CadBridge verifica se o bloco `"T"` existe na `BlockTable` do desenho ativo (`bt.Has("T")`). Se existir, insere uma `BlockReference` no ponto exato do poste (`ptPoste`).
- **Modularização de Código & Clean Architecture**:
  - `vias_obstrucoes.js` (218 linhas), `medicao.js` (276 linhas), `tracado.js` (193 linhas) e `ambiental_overlay.js` (179 linhas) rigorosamente desacoplados.
  - `app.js` mantido em 777 linhas.
  - `CadBridge.cs` (595 linhas) e `AmbientalParser.cs` (196 linhas) mantendo alta coesão e responsabilidade única.
- **Persistência Contínua de Estado (`localStorage`)**:
  - Chave `AUXCAD_PALETA_STATE`: salva automaticamente coordenadas, centro e zoom do mapa, camada ativa, número do poste, listas de estruturas MT/BT, equipamentos e potências.
- **Comandos do AutoCAD**:
  - **`MAPAPALETA`** (alias: **`OSMPALETA`**): Exibe a paleta acoplável à direita com auto-hide.
  - **`FECHAR_MAPAPALETA`**: Fecha a paleta.
  - **`RECARREGAR_MAPAPALETA`**: Recarrega a interface web instantaneamente na sessão.

### 13. `cpfc/` (Participação Financeira do Consumidor - REN 1.000 / REN 1.059 ANEEL)
- **Motor de Regras Regulatórias (`cpfc_core.py`, `cpfc_gui.py`, `cpfc_excel.py`)**:
  - Cálculo oficial da fórmula ANEEL: $PF = \max(0, COP - ERD)$, com rateio proporcional da obra e cobertura pelo Fator K ($K_c$ e $K_g$).
  - Geração automática e preenchimento da planilha oficial de distribuição da concessionária.
- **Gerador de Notas Regulatórias para o Desenho (`cpfc_notas.py`)**:
  - Catálogo com as 4 Notas Técnicas Oficiais para carimbo/prancha no CAD:
    1. *Carga x Disjuntor (Arts. 98 e 99 - Custeio de medição e adaptações de rede)*
    2. *Ligação Nova > 50 kW (Arts. 104 e 106 - Sem gratuidade)*
    3. *Acréscimo de Carga > 50 kW / Complementação de Fase MT (Arts. 105 e 106)*
    4. *Relocação de Poste / Afastamento de Rede / Interesse de Terceiros (Art. 110)*
  - Modal na interface com seleção múltipla, cópia com 1 clique e exportação para arquivo `.txt`.
- **Inserção Direta no AutoCAD via AutoLISP (`cpfc_cad_launcher.lsp`)**:
  - Comandos **`CPFC_NOTAS`** (ou **`NOTAS_CPFC`**): insere caixa MText formatada com fonte técnica no layer `NOTAS_CPFC` na prancha do DWG.
### 14. Inovações Estratégicas P1 a P4 (Ecossistema Integrado AUX CAD)

#### P1. Conexão Direta Paleta OSM ➔ CQT (Queda de Tensão BT)
- **Exportador e Launcher Instantâneo (`tracado.js`, `MapaControl.xaml.cs` & `cqt_cad_extractor.lsp`)**:
  - Botão `⚡ CQT` integrado no painel de traçado contínuo e botão de atalho direto `⚡ CQTUI` na barra de ações rápidas de consumidores BT.
  - **Execução Não-Bloqueante**: Ao clicar no botão, a interface do CQTUI abre imediatamente. Se houver 2 ou mais postes traçados, transfere todos os vãos, condutores e cargas; se não houver traçado, abre para estudo prévio com os dados de identificação e clientes do formulário.
  - **Resiliência Multi-Ambiente no Windows 11**: Disparo do Python executado via `cmd.exe /c start "" py ...` contornando restrições de permissão ("Acesso Negado") associadas a App Execution Aliases da Microsoft Store.
  - **Sincronização Bidirecional com AutoCAD**: Gravação atômica do arquivo de intercâmbio `auxcad_cqt_import.json` tanto em `%TEMP%` quanto em `C:\Temp`. Comandos do AutoCAD **`CQTUI`** (ou **`CQT`** e **`CQT_OSM`**) detectam o arquivo exportado pela Paleta automaticamente.
  - **Layout Ergonômico de Consumidores BT (CQT)**: Design em 3 células integradas com badges coloridos (1F Mono azul, 2F Bi âmbar, 3F Tri verde esmeralda destacado), controles de stepper (+ / -), totalizador dinâmico de clientes em tempo real, atalhos rápidos (`+1 Mono`, `+1 Bi`, `+1 Tri`, `Zerar`, `⚡ CQTUI`), sincronização com `localStorage` e eliminação completa de rolagem horizontal (`overflow-x: hidden`).

#### P2. Snap Magnético aos Postes e Nós da Rede (`snap_magnetico.js`)
- **Atração Magnética em Tela (18 pixels de raio)**:
  - Botão `🧲 Snap: ON` na barra de ferramentas superior com alternância em tempo real.
  - Varredura de múltiplos candidatos com cálculo de distância euclidiana em pixels de tela:
    1. Vértices do traçado contínuo ativo (`TracadoState.pontos`).
    2. Vértices da régua métrica (`MedicaoState.pontos`).
    3. Postes importados ou sincronizados do desenho DWG (`AppState.dwgMarkersLayer`).
    4. Marcador principal do poste.
  - Indicador visual com anel pulsante ciano (`.snap-magnetico-marker` com animação `@keyframes snapPulse`) e tooltip identificando o ponto de snap (`🧲 P01`).
  - Conexão e fixação automática nos eventos de clique e arrasto no mapa e medição.

#### P3. Hub Central & Launcher Unificado (`aux_cad_hub.py` & Atalhos da Raiz)
- **Painel Executivo Unificado (Tema Navy/Slate `#0F172A` / `#1E293B`)**:
  - Ponto de entrada único na raiz do projeto executável via 2 cliques no `Abrir_AUXCAD.bat`.
  - Atalhos diretos de 2 cliques na raiz: `Abrir_AUXCAD.bat`, `Abrir_Unifilar.bat`, `Abrir_AutoPrancha.bat`, `Abrir_CQT.bat`, `Abrir_Orcamento.bat`, `Abrir_CPFC.bat`, `Abrir_Mapa_Postes.bat`.
  - Diagnóstico em tempo real: versão do Python, detecção de processo do AutoCAD (`acad.exe`), status de compilação da DLL .NET e branch git ativa.
  - Cards de 1 clique para todos os 10 módulos da suíte:
    1. ⚡ Diagrama Unifilar & Proteção a Montante (KMZ / SGT)
    2. 📐 AutoPrancha Enel / HBT (ModelSpace 1:1)
    3. ⚡ Queda de Tensão BT (CQT)
    4. 💰 Orçamento & Materiais
    5. 📑 Participação Financeira (CPFC REN 1.059)
    6. 🌳 Estudo & Memorial Ambiental
    7. 🗺️ Estúdio Web de Satélite & Postes
    8. 📐 Paleta Cartográfica OSM no AutoCAD (.NET)
    9. 📊 Tabelas de Referência Normativas
    10. 🧪 Central de Testes & QA (execução em background com relatório de 149 testes)
  - Manutenção inteligente de raiz: `clean.bat` aprimorado com limpeza profunda de `%temp%`, `Temp` do Windows, arquivos residuais do AutoCAD (`*.bak`, `*.dcl_tmp`, `*.tmp`) e caches Python (`__pycache__`, `.pytest_cache`, `.coverage`), preservando 100% dos modelos e desenhos.

#### P4. Docker First & Pipeline de Integração Contínua (CI/CD)
- **Containerização Total e Reprodutibilidade**:
  - `Dockerfile` padronizado com `python:3.12-slim`, ambiente UTF-8, PYTHONPATH completo e execução padrão da suíte de testes com cobertura.
  - `docker-compose.yml` orquestrando o serviço de testes (`auxcad-tests`) e o estúdio web de satélite (`auxcad-mapa` na porta 8000).
  - `.dockerignore` otimizado descartando caches, arquivos DWG pesados e binários intermediários.
  - `requirements.txt` com versionamento explícito das dependências essenciais (`openpyxl`, `pytest`, `pytest-cov`, `requests`, `python-docx`, `Pillow`).
  - `.github/workflows/ci.yml` configurado com matriz Python 3.11 e 3.12, disparando testes em push/PR na branch `dev` e `main` com barreira de qualidade mínima de 80% de cobertura.
- **Métricas de Qualidade**: 149 testes unitários passando com 100% de sucesso.

### 15. Módulo AutoPrancha Enel / HBT (`prancha/`)
- **Conceito & Método Concessionária**: No fluxo de trabalho da Enel e HBT Engenharia, as pranchas completas de projeto (folha com bordas, margens ABNT, linhas de dobra e carimbo oficial) são inseridas **diretamente no ModelSpace** (sem uso de PaperSpace/Layouts para carimbo), em escala métrica 1:1 real ($1\text{ unidade} = 1\text{ metro}$).
- **Motor Analítico de Enquadramento (`autoprancha_core.py`)**:
  - Mapeamento normativo dos formatos de papel ABNT NBR 10068: A0 ($1189 \times 841$ mm), A1 ($841 \times 594$ mm), A2 ($594 \times 420$ mm), A3 ($420 \times 297$ mm) e A4 ($297 \times 210$ mm).
  - Desconto automático de margens: 25mm na margem esquerda (encadernação/pasta) e 10mm nas demais (topo, base e direita).
  - Reserva técnica do Carimbo + Legenda Enel/HBT no canto inferior direito ($185 \times 60$ mm no papel).
  - Escalas normativas de rede de distribuição: 1:500, 1:750, 1:1000, 1:1250, 1:1500 e 1:2000. Fator métrico no Model: $\text{Escala}/1000.0$.
  - Função `calcular_enquadramento`: recebe a diagonal da rede ($x_1, y_1, x_2, y_2$), adiciona folga de respiro de 10% a 15% e seleciona a menor folha e escala adequadas, priorizando a escala mãe 1:1000 e o formato A1 da Enel.
- **Rotina AutoLISP no AutoCAD (`autoprancha.lsp`)**:
  - Comandos: **`AUTOPRANCHA`** (atalhos: **`PRANCHA`**, **`ENQUADRAR`**, **`FOLHA`**) e **`RECARREGAR_PRANCHA`**.
  - Captura interativa em 2 cliques com retângulo elástico dinâmico (`getcorner`).
  - Modos flexíveis: **Auto** (cálculo total ótimo), **Escala** (forçar escala específica) e **Formato** (forçar formato de folha).
  - Criação automática de camadas técnicas: `A-PRANCHA` (corte externo), `A-PRANCHA-MARGEM` (margem interna em ciano 0.50mm), `A-PRANCHA-DOBRA` (marcas discretas de dobra a cada 185/210mm) e `A-PRANCHA-CARIMBO`.
  - Inserção do Carimbo Técnico Enel/HBT com escala calculada, data atual e dados da obra no canto inferior direito.
  - Centralização geométrica perfeita da área útil da folha sobre a área delimitada pelo projetista.

### 16. Módulo Diagrama Unifilar & Proteção KMZ (`unifilar/`)
- **Automação de Proteção & Árvore Elétrica**:
  - `arvore_parser.py`: Leitura de caminho elétrico e determinação da primeira proteção a montante, quantificação de Clientes A/B e potência instalada em kVA.
  - `dispositivos_kmz_finder.py`: Consulta georreferenciada nos 14 arquivos KMZ de apoio da concessionária com 134.082 dispositivos indexados, convertendo WGS84 para coordenadas de projeto UTM SIRGAS 2000 (Fuso 23S/24S).
  - `unifilar_diagrama_builder.py`: Construtor 2.5D do esquema unifilar sem escala no ModelSpace com resolução inteligente de blocos oficiais:
    - **Chaves Fusíveis / Seccionadoras**: bloco **`chaves_`** (fallback geométrico 2.5D).
    - **Religadores**: bloco **`REL.`** (com compatibilidade bidirecional e fallback para `REL` e símbolo vetorial 2.5D).
    - **Transformadores**: bloco **`TRAFO1`** (com prioridade configurável e seleção interativa no DWG via `[L]` lista, `[S]` clique na tela ou `[ENTER]`).
  - `unifilar_cad.lsp`: Comandos **`UNIFILAR`** e **`PROTECAO`** gerando esquema em prancha, ramal geográfico interativo no ModelSpace a partir da coordenada real do KMZ ou atualização in-place dos textos técnicos da prancha.

### 17. Módulo Preparação de Projeto SOB (`sob/`)
- **Ordem Oficial das Etapas — Pré-Validação e Criação (Seção 17 - Fase A e Fase B)**:
  - **Princípio Fundamental**: *Nenhuma criação, cópia, download ou alteração de arquivos deverá ocorrer enquanto a pré-validação não estiver concluída com sucesso.*
  - **FASE A — PRÉ-VALIDAÇÃO (Etapas A01 a A15 - Não Destrutiva / Atômica)**:
    - `A01 - Iniciar comando no AutoCAD`: Comando reconhecido (`SOB`, `NOVASOB`, `PREPARAR_SOB`) e ambiente inicializado. Se erro: `STATUS = BLOQUEADO`.
    - `A02 - Solicitar SOB`: Entrada da SOB (`A057349839` ou `SOB_A057349839`).
    - `A03 - Normalizar e validar SOB`: Geração de `SOB_ID` e `SOB_NAME`. Se inválido: `[FALHA] Número da SOB inválido.`.
    - `A04 - Selecionar DESTINATION_ROOT`: Seletor nativo do Windows. Cancelamento: `[INFO] Operação cancelada pelo usuário.`.
    - `A05 - Validar DESTINATION_ROOT`: Caminho absoluto, diretório válido e acessível.
    - `A06 - Derivar caminhos canônicos`: Cadeia oficial única `SOB_ID -> SOB_NAME -> DESTINATION_ROOT + SOB_NAME -> SOB_ROOT -> CROQUI_DIR -> BASE_DWG`.
    - `A07 - Verificar conflito de SOB_ROOT`: Verificação se pasta já existe. Se existir: `[FALHA] A pasta da SOB já existe.` (sem sobrescrever/mesclar).
    - `A08 - Validar possibilidade de criação`: Validação de permissões de escrita em `DESTINATION_ROOT` sem criar pastas definitivas. Se falhar: `[FALHA] O diretório selecionado não permite a criação da estrutura da SOB.`.
    - `A09 - Validar BASE_TEMPLATE`: Verificação prévia de existência e legibilidade de `modelos/prancha.dwg`. Se falhar: `[FALHA] Arquivo-modelo prancha.dwg não encontrado ou inacessível.`.
    - `A10 - Validar disponibilidade de BASE_DWG`: Confirmação de que `BASE_SOB_DESENHO.dwg` não existe previamente no destino.
    - `A11 - Validar credenciais do SharePoint`: Checagem segura de `SHAREPOINT_ID` e `SHAREPOINT_SENHA` no `.env` sem expor valores.
    - `A12 - Autenticar no SharePoint`: Autenticação e validação efetiva. Se falhar: `[FALHA] Não foi possível autenticar no SharePoint.`.
    - `A13 - Localizar SOB no SharePoint`: Busca unívoca por `SOB_ID`. Falhas: `[FALHA] SOB não encontrada.` ou `[FALHA] Foram encontradas múltiplas correspondências ambíguas.`.
    - `A14 - Validar conteúdo disponível para download`: Verificação de disponibilidade do conteúdo no SharePoint antes de criar arquivos locais.
    - `A15 - Encerrar pré-validação`: Emissão de `PRE_VALIDACAO = OK` (ou `PRE_VALIDACAO = BLOQUEADA` se houver pendência/falha).
  - **FASE B — CRIAÇÃO E EXECUÇÃO (Etapas B01 a B11)**:
    - `B01 - Criar SOB_ROOT`: Criação física e validação imediata.
    - `B02 - Criar CROQUI_DIR`: Criação física e validação imediata.
    - `B03 - Baixar conteúdo da SOB`: Download do SharePoint para `CROQUI_DIR` preservando estrutura interna.
    - `B04 - Validar download`: Verificação física de integridade (sem temporários, corrupção ou 0 bytes).
    - `B05 - Copiar BASE_TEMPLATE`: Cópia preservando o arquivo original (`BASE_TEMPLATE -> BASE_DWG`).
    - `B06 - Validar BASE_DWG`: Confirmação de existência, tamanho > 0 e integridade binária.
    - `B07 - Validar preservação do BASE_TEMPLATE`: Confirmação de que o modelo original permaneceu intacto no caminho original.
    - `B08 - Validar estrutura final`: Validação de toda a árvore de diretórios e arquivos da SOB.
    - `B09 - Abrir BASE_DWG no AutoCAD`: Abertura exclusiva de `BASE_DWG` (nunca o template).
    - `B10 - Validar DWG efetivamente aberto`: Verificação estrita do desenho ativo (`CURRENT_AUTOCAD_DWG == BASE_DWG`).
    - `B11 - Validação final`: Checagem integral do checklist operacional e emissão de `STATUS = CONCLUÍDO`.
  - **Mecanismo de Rollback Seguro da Fase B (Seção 18 - `sob_rollback.py`)**:
    - `RollbackContext`: Gerenciador de contexto atômico e seguro disparado em qualquer falha da Fase B.
    - **Princípio Fundamental (18.1)**: Remoção estrita e exclusiva daquilo que foi comprovadamente criado pela execução atual (`CRIADO_NESTA_EXECUÇÃO = SIM`), com proibição expressa de `shutil.rmtree` indiscriminado.
    - **Proteção Absoluta do BASE_TEMPLATE (18.8)**: Imutabilidade absoluta do arquivo-modelo (nunca apagado, movido ou renomeado).
    - **Proteção de Conteúdo Preexistente (18.6)**: Arquivos e pastas preexistentes nunca são apagados; em caso de resíduo, declara-se `ROLLBACK_PARCIAL`.
    - **Ordem Inversa Estrita de Desfazimento (18.10)**:
      1. Fechar / desassociar `BASE_DWG` do AutoCAD;
      2. Remover `BASE_DWG` criado pela execução;
      3. Remover arquivos baixados pela execução;
      4. Remover `CROQUI_DIR` se vazio e criado nesta execução;
      5. Remover `SOB_ROOT` se vazio e criado nesta execução.
    - **Estados Formais**: `ROLLBACK_NÃO_NECESSÁRIO`, `ROLLBACK_INICIADO`, `ROLLBACK_CONCLUÍDO`, `ROLLBACK_PARCIAL`.
    - **Registro Estruturado**: Rastreabilidade completa com `recursos_criados_pela_execucao`, `recursos_removidos`, `recursos_preservados`, `recursos_remanescentes` e orientações de ação.
    - **Mecanismo de Idempotência e Repetição Segura (Seção 19 - `sob_idempotencia.py`)**:
      - **Princípio de Idempotência (19.1)**: Mesma combinação `SOB_ID + DESTINATION_ROOT` sempre produz estritamente os mesmos `SOB_NAME`, `SOB_ROOT`, `CROQUI_DIR` e `BASE_DWG`. Proibição absoluta de sufixos numéricos (`_1`, `_2`) ou timestamps (`_20260919`) para ocultar conflitos.
      - **Classificação Rigorosa de Estados (19.2 e 19.5)**: Estados possíveis ao examinar `SOB_ROOT`:
        - `NÃO_EXISTE`: Pré-validação aprovada -> Iniciar nova execução limpa.
        - `EXISTE_E_NÃO_É_DA_EXECUÇÃO`: Pasta preexistente sem manifesto ou criada por terceiros -> Bloquear (`STATUS = BLOQUEADO`).
        - `EXISTE_E_ESTÁ_INCOMPLETA`: Execução anterior interrompida ou com rollback parcial -> Bloquear (`STATUS = BLOQUEADO`).
        - `EXISTE_E_ESTÁ_CONCLUÍDA`: Execução anterior `CONCLUÍDO` com arquivos íntegros -> Bloquear criação duplicada e informar `[INFO] A SOB já possui uma execução concluída neste destino.`.
        - `EXISTE_EM_ESTADO_INCONSISTENTE`: Divergência entre manifesto e arquivos em disco -> Bloquear (`STATUS = BLOQUEADO`).
      - **Não Confundir Existência com Conclusão (19.6)**: Presença de arquivos físicos isolada não atesta conclusão; exige validação do manifesto `.sob_state.json` e integridade física.
      - **Downloads e Cópia de Base Idempotentes (19.11 e 19.12)**: Comparação de hash/tam    - **Interface de Progresso com Feedback Visual Obrigatório (`sob_progress_gui.py`)**:
      - **Comunicação Multithread Segura**: Observer thread-safe (`ProgressoObserver`) desacoplando o motor de regras da interface Tkinter TTK, impedindo congelamento de tela durante downloads ou I/O pesado.
      - **Design Corporativo e Clareza Operacional**: Paleta executiva (#1B365D, #F8FAFC, #2563EB, #10B981, #EF4444), progresso determinado/indeterminado dinâmico, badges de etapa sem mensagens genéricas.
      - **Cancelamento Seguro com Rollback**: Botão `[ Cancelar ]` interativo que dispara o desfazimento atômico e seguro na Fase B caso o usuário interrompa o processo.
    - **Fallback para Múltiplas Ocorrências no SharePoint (`sob_fallback_manual.py`)**:
      - **Ambiguidade Não-Automatizada**: Quando o SharePoint retorna mais de uma ocorrência correspondente, o sistema **NUNCA** escolhe arbitrariamente. A ocorrência é determinada exclusivamente pelo usuário.
      - **Prevenção de Criação Prematura**: O fluxo automático é paralisado antes da criação de `SOB_ROOT` e `CROQUI_DIR`.
      - **Busca Contextualizada no Navegador**: Abertura automática da busca no SharePoint já filtrada por `SOB_ID` e cópia atômica do identificador para a área de transferência do Windows (`clip`).
      - **Validação Rigorosa de Arquivos Manuais (`validar_arquivos_manuais`)**: Rejeição de arquivos com 0 bytes, temporários (`~$`, `.download`, `.tmp`), e páginas HTML de erro com extensão trocada.
    - **Regra Fundamental — Estrutura do Projeto Independente do Croqui**:
      - A criação da estrutura local do projeto e a obtenção do conteúdo do croqui são operações distintas.
      - O fato de o download automático do croqui pelo SharePoint ser interrompido, substituído por intervenção manual ou eventualmente dispensado **NÃO elimina** a necessidade de criação da estrutura local do projeto.
      - `IF pre_validacao == OK THEN criar estrutura do projeto + copiar modelo + validar BASE_DWG + continuar fluxo`.
    - **Regra Fundamental — Nomenclatura Canônica Dinâmica {BASE}_{SOB}_DESENHO.dwg**:
       - O modelo canônico de nome do desenho DWG segue a máscara `{BASE}_{SOB}_DESENHO.dwg`, substituindo:
         - **BASE**: Sigla técnica oficial de 2 letras mapeada da base da concessionária/FABAO (`C:\Users\jonat\OneDrive\Área de Trabalho\FABAO\Controle\gomnet_18-08-2022.xlsm`), ex.: `PE` (Petrópolis), `CF` (Cabo Frio), `AN` (Angra dos Reis), `RE` (Resende), `NI` (Niterói), `MA` (Magé), `SG` (São Gonçalo), `TE` (Teresópolis).
         - **SOB**: Número puro da SOB informado pelo usuário (`A057350816`).
         - **_DESENHO**: Sufixo obrigatório canônico (`_DESENHO.dwg`).
       - Exemplo canônico gerado: `PE_A057350816_DESENHO.dwg`.
       - O arquivo-modelo original `modelos/prancha.dwg` permanece absolutamente intacto (imutabilidade de template) e é copiado para `SOB_ROOT` com este nome exato.
- **Arquitetura & Componentes**:
  - `sob_bases.py` (147 linhas): Mapeamento, normalização e resolução de siglas técnicas Enel Rio / FABAO (`normalizar_sigla_base`, `gerar_nome_dwg_sob`, `carregar_bases_fabao`).
  - `sob_core.py` (487 linhas): Lógica de domínio, normalização, checagem não-destrutiva de permissões (`validar_permissao_criacao`), geração de caminhos centralizados com `BASE_SIGLA` e `NOME_BASE_DWG`, validações de integridade SHA-256 e hierarquia unificada de exceções com `SobConflictError`.
  - `sob_fallback_manual.py` (303 linhas): Geração de URLs de busca, cópia para clipboard, validação física de downloads manuais e orquestração de intervenção (`executar_fallback_intervencao_manual`).
  - `sob_progress_gui.py` (633 linhas): Interface Tkinter TTK com feedback em tempo real, exibição de SOB e Base no cabeçalho executivo, elevação e foco garantidos sobre o AutoCAD (`deiconify`, `lift`, `-topmost`), painel de intervenção manual (`[ Abrir SharePoint ]`, `[ Selecionar Pasta ]`, `[ Continuar ]`, `[ Continuar sem Croqui ]`, `[ Cancelar ]`).
  - `sob_logger.py` (58 linhas): Utilitários isolados de logging seguro (`LoggerSeguro`) com sanitização de segredos e formatação padrão de erros (`formatar_mensagem_erro`).
  - `sob_cli.py` (88 linhas): Ponto de entrada CLI desacoplado com parâmetro `--base`, geração de arquivo JSON de intercâmbio e flags `--no-ui` / `--headless`.
  - `sob_gomnet.py` (374 linhas): Cliente HTTP para autenticação e consumo do modal de anexos do GOMNET e download em lote na Fase B (`baixar_anexos_gomnet_fase_b`).
  - `sob_idempotencia.py` (173 linhas): Gestão de estado idempotente, `gerar_run_id`, `classificar_sob_root`, manifesto atômico `.sob_state.json` e verificação de arquivos de download (`verificar_arquivo_download_idempotente`).
  - `sob_rollback.py` (425 linhas): Classes `RecursoRastreado`, `RecursoRemanescente` e `RollbackContext` para desfazimento sequencial reverso, rollback de anexos GOMNET, validação pós-rollback e proteção de dados.
  - `sob_sharepoint.py` (637 linhas): Driver Selenium headless, autenticação Microsoft Online, busca unívoca diretamente na pasta compartilhada de **Levantamentos de campo**, download da pasta inteira em ZIP com nivelamento para `CROQUI/`, verificação prévia de conteúdo (`validar_conteudo_disponivel`) e detecção de ambiguidade (`SobConflictError`).
  - `sob_manager.py` (747 linhas - mantido estritamente abaixo do soft limit de 750 linhas): Orquestrador de máquina de estados segregada em Fase A e Fase B, suporte ao parâmetro de base, integração com fallback manual, criação obrigatória de estrutura e modelo independente do croqui, rastreamento por `RUN_ID` e checklist operacional completo.
  - `sob_cad_launcher.lsp` (409 linhas): Ponto de entrada nativo no AutoCAD com comandos **`SOB`**, **`NOVASOB`**, **`PREPARAR_SOB`**, **`RECARREGAR_SOB`**, solicitação de Base com default `PE`, derivação dinâmica de `{baseSigla}_{sobId}_DESENHO.dwg`, fallback com busca de arquivo `*_DESENHO.dwg`, tratamento de status idempotente, inicialização estrita de `croquiDir`, blindagem de `strcat` contra `nil`, localização robusta e comando de recarga dinâmico sem reiniciar o CAD.
  - **Cobertura de Testes**: **288 testes unitários e de integração com 100% de sucesso (PASS)** em todo o projeto, **81% de cobertura global no módulo SOB** e **80% de cobertura global no módulo CQT** (`cqt_scenario_tab.py`: 93%, `cqt_live_calc.py`: 91%, `cqt_excel_io.py`: 87%, `cqt_quadros_generator.py`: 85%). Bateria de testes operacionais no AutoCAD 2026 Core Console: **PASS** em todos os cenários.

---

## Registro de Investigação OSMPALETA - 2026-09-23

### Escopo e decisões
- Investigação iniciada por falha de desenho automático de ruas no AutoCAD ao inserir postes.
- Escopo cobriu aquisição OSM, coordenadas/UTM, WebView2, AutoCAD .NET, `CadBridge` e múltiplas instâncias do AutoCAD.
- Regra adotada: evidência operacional antes de qualquer correção funcional.
- Não introduzir COM, ActiveX, IPC, Named Pipes, `accoreconsole`, proxy ou backend no fluxo OSMPALETA.

### Aquisição OSM
- API oficial OSM retornou HTTP 429 em execuções reais; fallbacks Overpass retornaram 429, timeout ou erro de rede.
- Requisições originais não tinham User-Agent identificável, deduplicação in-flight ou política específica de 429.
- A BBOX testada era pequena; não houve evidência de erro de fuso, UTM, Snyder ou inversão X/Y.
- Correção mantida: User-Agent `OSMPALETA (CAD interno)`, deduplicação por BBOX, classificação de status, retry limitado, `Retry-After`, fallback somente para falhas transitórias e mensagens/logs de diagnóstico.

### Evidência OSM/payload
- Consulta real HTTP 200: 872 elementos, 91 ways, 595 nodes, 57 ways com highway, 35 vias, 22 calçadas, 13 obstruções e 417 vértices.
- Payload WebView2 real: `vias=35`, `calcadas=22`, `obstrucoes=13`, `vertices=417`.
- Outro payload real observado no CAD: `vias=6`, `calcadas=1`, `obstrucoes=0`, `verticesTotal=65`, `polylinesCriadas=31`.
- O payload de 6 vias foi atribuído ao fluxo real `converterEEnviarParaCad` -> `window.chrome.webview.postMessage` -> `WebMessageReceived` -> `CadBridge`, não ao self-test artificial.

### Evidência AutoCAD .NET
- Self-test interno: `DocumentCount=1`, `MdiActiveDocument=TESTE_POSTE_E_VIAS.dwg`, Database/BlockTable/ModelSpace OK.
- Transaction iniciou e commitou; Polyline persistida com `EntitiesBefore=177`, `EntitiesAfter=178`, `Delta=1`, `EntityExists=TRUE`.
- A API CAD básica e a criação de entidades foram comprovadas dentro da instância real.

### Diagnóstico WebView2
- Lifecycle real: `MapaControl.Loaded` -> `CreateAsync` -> `EnsureCoreWebView2Async` -> configuração/registro de `WebMessageReceived` -> `Navigate`.
- `PaletteHost.MostrarPaleta()` retorna antes da conclusão do lifecycle assíncrono.
- `CoreWebView2=NULL` no self-test ocorreu porque o comando foi executado cedo demais.
- Payload real posterior e logs CAD comprovam inicialização posterior do WebView2 e processamento pelo handler.
- Classificação: **W2 - self-test antecipado em relação à inicialização assíncrona do WebView2**.

### Limitação do teste artificial
- Para uma entrada em `vias`, o `CadBridge` cria o eixo e quatro offsets; portanto uma via pode gerar 5 polylines, não 1.
- O `CadBridge` não foi alterado para adaptar essa expectativa.
- Comandos e instrumentações temporárias (`OSMPALETA_SELFTEST` e `OSMPALETA_WEBTEST`) foram removidos.

### Validação final
- Build Release `net8.0-windows` e `net48`: aprovados.
- `node --check` de `vias_obstrucoes.js` e `app.js`: aprovados.
- `pytest tests/test_mapa_paleta.py -q`: `16 passed`.
- Nenhum diagnóstico temporário permaneceu no projeto.

### Homologação da correção de prontidão WebView2 - 2026-09-23
- `MapaControl.xaml.cs` passou a usar uma única task idempotente de inicialização (`_initializationTask`) como condição de prontidão.
- A prontidão somente termina após `EnsureCoreWebView2Async`, configuração, registro de `WebMessageReceived` e `NavigationCompleted` bem-sucedido.
- `BtnRecarregar_Click` e `EnviarMensagemWeb` aguardam a mesma task com `async/await`; não há `Sleep`, `.Wait()`, `.Result`, retry ou nova infraestrutura.
- Falhas de inicialização são propagadas aos chamadores e exibidas no status; não há acesso prematuro silencioso a `CoreWebView2`.
- Build/testes finais aprovados: `net48`, `net8.0-windows`, syntax checks JS e `16 passed`.

### Auditoria Técnica Integral — Todos os Módulos e Comandos da Raiz (2026-09-23)
- **Inventário Completo**: Mapeados 445 arquivos, 13 módulos funcionais, 102 comandos AutoLISP (`c:...`), 5 comandos C# .NET (`[CommandMethod]`), scripts de automação, executáveis e arquivos de modelo.
- **Auditoria AutoLISP**: 30 arquivos `.lsp` inspecionados estaticamente; 100% com parênteses balanceados e sem erros de sintaxe.
- **Auditoria JavaScript**: Todos os scripts inspecionados via `node --check` com 100% de aprovação.
- **Auditoria C# / .NET**: `dotnet build mapa_cad_paleta/MapaCadPaleta.csproj -c Release` aprovado com 0 erros para ambos os targets (`net48` e `net8.0-windows`).
- **Problema P1 Comprovado e Corrigido**:
  - `sob/sob_fallback_manual.py:245`: Importava `SobNotFoundError` de `sob_core` (que não o define), provocando falha em 10 testes de fallback manual e orquestração.
  - Correção cirúrgica: importação redirecionada para `sob_sharepoint` e prefixo de mensagem de falha padronizado para `[FALHA]`.
- **Validação de Testes**: Suíte completa executada com **296 passed, 2 skipped** (100% dos testes executáveis aprovados).
- **Classificação**: **HOMOLOGÁVEL**.

### Validação Operacional Final — Fechamento da Homologação (2026-09-24)
- **GOMNET (Fases A e B)**: **100% PASS OPERACIONAL** com conexão real ao host corporativo (`gomnet-rj.enelint.global`). Autenticação real com sessão ASP.NET, consulta real de SOBs com anexos identificados (`A057349839` e `A057219996`), download atômico real validado fisicamente (`CHECKLIST_A057349839.xlsx` com 18.777 bytes e cabeçalho OpenXML), idempotência confirmada e falhas controladas sem vazamento de credenciais.
- **SGT Caminho Elétrico**: Host corporativo alcançado; resposta HTTP 401 aciona o fallback resiliente transparente para a base local SQLite (`arvore_cache.sqlite3`), retornando a proteção a montante com sucesso em 0.26s.
- **AutoCAD 2026 Core Console**: `acaddoc.lsp` carregado em ambiente headless sem erros; 100% dos comandos testados disponíveis (`CQTCAD`, `SOB`, `AUTOPRANCHA`, `UNIFILAR`, `KMZCHECK`, `ORCAMENTO`, `CPFC`); criação física de entidades no ModelSpace validada.
- **Suíte Automatizada**: 296 PASS, 2 SKIP (dependência de drive G: externo não montado), 0 FAIL, 0 ERROR.
- **Classificação Final**: **HOMOLOGADO**.

### Correção Operacional — Módulo Ambiental / Permissão de Escrita (2026-09-24)
- **Incidente**: Popup de erro fatal `[Errno 13] Permission denied: 'C:\Windows\System32\CHECKLIST_A057383730.xlsx'` ao gerar Checklist Ambiental.
- **Diagnóstico**: Quando o modelo `.docx` não estava no drive `G:`, `docx_template` recebia string vazia `""`. `os.path.dirname("")` resultava em `""`, e o script caía no fallback `os.getcwd()`. O AutoCAD invocou o `cmd.exe` sem working directory, herdando `C:\Windows\System32`, onde a escrita é bloqueada pelo UAC do Windows.
- **Ações Implementadas**:
  1. `kmz_point_layer_report.lsp`: captura `(getvar "DWGPREFIX")`, limpa trailing backslash com `vl-string-right-trim`, define o working directory com `cd /d "<dwg_dir>"` e passa `dwg_dir` como 5º argumento CLI.
  2. `memorial_ambiental_generator.py`:
     - Implementadas funções `is_safe_writable_dir(path)` e `determinar_pasta_saida(candidate, template_path)`.
     - Blindagem com rejeição estrita de pastas de sistema (`Windows`, `System32`, `Program Files`, raiz do disco).
     - Adicionado campo visual editável na GUI: "📁 Pasta de Destino (Salvar):" com botão "Procurar..." (`filedialog.askdirectory`), dando visibilidade e escolha ao projetista.
     - Resiliência contra concorrência/lock de arquivos: se o arquivo já estiver aberto no Microsoft Excel, salva automaticamente com sufixo de timestamp (`CHECKLIST_{SOB}_{HHMMSS}.xlsx`), alertando o usuário sem travar o processo.
  3. `tests/test_checklist_ambiental.py`: novos testes `test_is_safe_writable_dir` e `test_determinar_pasta_saida` (6/6 PASS).
- **Validação Global**: Suíte global com 300 testes (296 PASS, 0 FAIL, 4 SKIP).

---

## Política Oficial de Versionamento e Ciclo de Releases

### 1. Fonte Única da Versão
O arquivo [`VERSION`](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/VERSION) na raiz do projeto é a **fonte oficial única de verdade** da versão do AUX CAD, adotando Semantic Versioning (`MAJOR.MINOR.PATCH`):
- **MAJOR**: Mudanças estruturais incompatíveis ou quebra do modelo operacional.
- **MINOR**: Novas funcionalidades, novos módulos ou comandos compatíveis.
- **PATCH**: Correções de bugs, pequenas melhorias ou ajustes internos sem quebra de contrato.

### 2. Convenção de Commits (Conventional Commits)
Commits a partir da v0.9.0 devem seguir o padrão:
- `feat(<escopo>)`: Nova funcionalidade ou comando.
- `fix(<escopo>)`: Correção de bug.
- `refactor(<escopo>)`: Refatoração sem alteração funcional.
- `docs(<escopo>)`: Alterações exclusivamente em documentação.
- `test(<escopo>)`: Adição ou ajuste de testes automatizados.
- `build(<escopo>)`: Alterações em dependências, `.csproj`, scripts de build ou versão.
- `chore(<escopo>)`: Tarefas de manutenção rotineira.
- `perf(<escopo>)`: Otimizações de desempenho comprovadas.

### 3. Fluxo de Release
```text
branch dev
    ↓
desenvolvimento
    ↓
testes automatizados (pytest, .NET Release, node --check)
    ↓
validação operacional (AutoCAD Core Console / GUI)
    ↓
atualização do arquivo VERSION
    ↓
atualização do CHANGELOG.md
    ↓
commit de release (ex: "chore(release): v0.9.0")
    ↓
tag Git anotada (ex: git tag -a v0.9.0 -m "Release v0.9.0")
### 18. Módulo Workspace da SOB / Projeto (`workspace/`)
- **Finalidade**: Camada central de coordenação e detecção de contexto para uma SOB/projeto, reunindo e identificando os artefatos de engenharia produzidos pelos módulos existentes sem duplicar lógica ou estruturas de persistência.
- **Estrutura**:
  - `workspace_core.py` (145 linhas): Modelo de domínio com `ProjectWorkspace`, `ProjectArtifact` e enum `ArtifactStatus` (`EXISTE`, `NAO_EXISTE`, `NAO_APLICAVEL`).
  - `workspace_scanner.py` (275 linhas): Motor analítico 100% somente leitura para varredura e detecção de DWG, pasta de croqui, anexos de documentos, checklist/memorial/croqui ambiental, planilha CQT, orçamento, CPFC e diagrama unifilar.
  - `workspace_cli.py` (285 linhas): Interface desktop visual em Tkinter e ponto de entrada CLI (com suporte a `--json` e formatação de texto pt-BR), integrada ao `WorkspaceActionDispatcher` com botões "Abrir", "Localizar", atalho de duplo clique e lançadores para CQT, Orçamento e CPFC.
  - `workspace_actions.py` (210 linhas): Despachante único e centralizado de ações (`WorkspaceActionDispatcher`), implementando abertura nativa (`abrir_artefato`), localização com seleção no Explorer (`localizar_artefato`) e acionamento desacoplado contextual dos módulos CQT, Orçamento e CPFC.
  - `workspace_cad.lsp`: Comandos nativos do AutoCAD **`WORKSPACE`** e **`SOBWORKSPACE`** para inspeção instantânea do desenho ativo a partir do `DWGPREFIX`.
  - `Abrir_Workspace.bat`: Atalho executável de 2 cliques na raiz.
- **Entrada**: Identificador puro da SOB (`A057349839`), caminho da pasta de destino ou arquivo DWG aberto no CAD.
- **Saída**: Contexto unificado e determinístico contendo o status físico de cada artefato e metadados de engenharia, com capacidade de despacho de ações para o SO ou módulos existentes.
- **Relação com SOB**: Reutiliza integralmente a raiz canônica `SOB_{SOB_ID}` e o desenho `{BASE}_{SOB}_DESENHO.dwg` definidos pelo módulo `sob/`.
- **Módulos Integrados**: `sob`, `ambiental`, `cqt`, `orcamento`, `cpfc` e `unifilar`.
- **Ações Habilitadas na Interface (v1)**:
  - `ABRIR`: Execução direta no aplicativo associado do Windows via `os.startfile` para o artefato selecionado ou via duplo clique na tabela.
  - `LOCALIZAR`: Foco no Windows Explorer com `/select,"<arquivo>"` ou abertura de pasta.
  - `EXECUTAR CQT`: Inicialização de `cqt/cqt_excel_manager.py` com preenchimento contextual de template, cad_json e destino `CQT_{SOB}.xlsm`.
  - `EXECUTAR ORÇAMENTO`: Inicialização de `orcamento/orcamento_manager.py` com preenchimento contextual de `--projeto <SOB>` e `--json`.
  - `EXECUTAR CPFC`: Inicialização de `cpfc/cpfc_manager.py` com preenchimento contextual de `root_dir` e `sob_id`.

### 19. Módulo SOB: Resiliência e Decisão do Usuário em Falha do GOMNET (`sob/`)
- **Diretriz Arquitetural**: Falha de acesso ou download de anexos do GOMNET **não é motivo para rollback automático**. O GOMNET é um serviço externo cujas indisponibilidades momentâneas não devem descartar a pasta da obra e o arquivo base DWG já preparados.
- **Mecanismo de Intervenção**:
  - Quando ocorre erro de autenticação, timeout ou download no GOMNET, o orquestrador (`SobOrchestrator`) consulta o usuário via `callback_progresso.perguntar_continuar_sem_gomnet(...)` ou diálogo modal Tkinter (`messagebox.askyesno`).
  - **Opção 1 - Continuar sem GOMNET**: A preparação prossegue, gerando o DWG base e a estrutura da SOB, concluindo com status `CONCLUÍDO` e registrando `GOMNET_IGNORADO = True`.
  - **Opção 2 - Fazer Rollback**: O usuário cancela explicitamente a operação, acionando o `RollbackContext` para reverter as pastas e arquivos criados.

### 20. Módulo SOB: Busca Prioritária de Croqui no SharePoint ("Levantamentos de campo") (`sob/`)
- **Diretriz Arquitetural**: A pasta `Levantamentos de campo` (`HBT-EnelRJ-Sul`) é a primeira fonte prioritária a ser pesquisada para localização do croqui de campo da SOB, preservando integralmente o mecanismo existente de pesquisa como fallback seguro.
- **Fluxo Operacional**:
  ```text
  SOB informada
        ↓
  Autenticação SharePoint (Sessão existente reutilizada)
        ↓
  BUSCA PRIORITÁRIA ("Levantamentos de campo")
        ↓
  Encontrou croqui válido?
        ├── SIM → Baixar / Validar → Continuar fluxo normal
        └── NÃO / Erro não-fatal
              ↓
        FALLBACK EXISTENTE
              ↓
        Pesquisa existente no SharePoint
              ↓
        Localizar / Baixar / Validar → Continuar fluxo normal
  ```
- **Critérios de Validação e Integridade**:
  - Reutilização estrita de `_item_eh_croqui_valido` e `validar_download(croqui_dir)`, descartando arquivos temporários (`~$`), backups e extensões inválidas (`.tmp`, `.exe`, scripts).
  - Preservação de tratamento de múltiplos candidatos ambíguos via `SobConflictError`.
  - Isolamento de erros: falhas de autenticação (`SobAuthenticationError`) não são mascaradas como falso "não encontrado".

---

## 15. Módulo OXCAD — Interface Nativa Integrada ao AutoCAD (.NET / WPF)

### Visão Geral e Princípio Arquitetural (Thin Client)
O **OXCAD** é a fundação da interface integrada nativa ao AutoCAD (PaletteSet lateral), projetada para substituir progressivamente a interface externa Tkinter sem duplicar lógicas de negócio ou regras de engenharia em C#.

```text
┌──────────────────────────────────────────────┐
│ AutoCAD (Sessão CAD)                         │
│                                              │
│ Comando: OXCAD                               │
│      ↓                                       │
│ oxcad_loader.lsp (AutoLISP)                  │
│      ↓                                       │
│ OxCadPaleta.dll (.NET 8.0 / net48)           │
│      ↓                                       │
│ PaletteHost (Singleton PaletteSet)           │
│      ↓                                       │
│ OxCadControl (WPF UserControl)               │
│      ↓                                       │
│ DwgContextExtractor (Contexto do DWG Ativo)  │
└──────────────────────────────────────────────┘
```

### Componentes e Decisões Técnicas
- **Isolamento de Domínio (Thin Client)**: O C# não implementa regras de negócio, cálculos ou scanners complexos. Obtém `MdiActiveDocument.Database.Filename` e extrai de forma segura o nome do DWG, diretório e número da SOB via regex homologada (`SOB_...`, `{BASE}_{SOB}_DESENHO` ou padrão da concessionária).
- **Tratamento de Desenho Não Salvo**: Caso o documento ativo não esteja gravado em disco ou seja nulo, o sistema exibe claramente `"Desenho ainda não salvo."` sem lançar exceções.
- **PaletteSet Singleton**: Gerenciado por `PaletteHost` com GUID estável e exclusivo (`8A4F1D9C-2B7E-4E6A-B35D-9F0A1C8E7B2D`), estilo com auto-hide, close button, dock lateral à direita (`DockSides.Right`) e prevenção de abas duplicadas.
- **Multi-targeting .NET**: Projeto `OxCadPaleta.csproj` compilável tanto para `net8.0-windows` (AutoCAD 2025/2026+) quanto para `net48` (AutoCAD 2018-2024 via pacote NuGet `AutoCAD.NET 24.3.0`).
- **Resolução Relativa de Paths**: AutoLISP loader (`oxcad_loader.lsp`) com detecção automática do runtime via `ACADVER`, sem dependências absolutas de máquina local ou OneDrive.
- **Preservação de Comandos Nativos**: O comando nativo conflitante `WORKSPACE` e os comandos existentes de especialistas permanecem intactos.

### Evolução OXCAD 0.2.0 — Integração do Contexto Operacional
A versão 0.2.0 conecta a interface WPF diretamente ao ecossistema operacional do projeto via interface headless dedicada:

```text
AutoCAD (DWG Ativo)
       ↓
OXCAD (PaletteSet + WPF)
       ↓
WorkspaceService (C#)
       ↓ (Ciclo estrito: Iniciar → Consultar → JSON → Encerrar)
workspace/workspace_context_cli.py (Python Headless — Zero Tkinter)
       ↓
ProjectWorkspace + WorkspaceScanner
       ↓
Contrato OxCadWorkspaceContext (JSON)
       ↓
OXCAD UI (SOB, Metadados, Inconsistência, Matriz de Artefatos)
```

- **Contrato Estável (`OxCadWorkspaceContext`)**:
  - `sob_id`: identificador oficial da SOB;
  - `root_dir`: diretório raiz da SOB no disco;
  - `dwg_principal`: arquivo DWG canônico;
  - `municipio`, `bairro`, `endereco`: metadados de localização recuperados do manifesto local (`-` quando ausentes);
  - `artefatos`: matriz dos 10 principais artefatos monitorados com rótulo, status e ícones (`✓` / `○`);
  - `inconsistencia` & `mensagem_inconsistencia`: detecção automática e alerta explícito caso o DWG ativo aponte para uma SOB divergente da pasta do Workspace.
- **Prevenção de Concorrência**: Controle atômico com flag `_isUpdating` e desativação temporária do botão `[🔄 Atualizar Contexto]` durante a consulta assíncrona.

### Evolução OXCAD 0.3.0 — Integração de Execução via WorkspaceActionDispatcher
A versão 0.3.0 transforma a OXCAD de interface passiva em ambiente ativo de execução de engenharia, disparando os módulos especialistas através do `WorkspaceActionDispatcher` homologado:

```text
AutoCAD (Sessão CAD)
       ↓
Botão de Ação / Abrir Artefato (OxCadControl)
       ↓
WorkspaceService.ExecutarAcaoAsync(acao, dwg, alvo)
       ↓ (Subprocesso desacoplado com timeout e retorno JSON)
workspace/workspace_context_cli.py (--acao / --alvo)
       ↓
WorkspaceActionDispatcher (Motor Oficial de Execução)
       ├── CQT           → cqt_excel_manager.py
       ├── Orçamento     → orcamento_manager.py
       ├── CPFC          → cpfc_manager.py
       ├── Ambiental     → memorial_ambiental_generator.py
       ├── AutoPrancha   → autoprancha_core.py
       ├── Preparar SOB  → sob_launcher_gui.py
       ├── Abrir/Localiz → os.startfile / explorer.exe
       └── Unifilar      → Orientação: comandos UNIFILAR/PROTECAO no AutoCAD
       ↓
Auto-refresh da Matriz de Artefatos pós-execução
```

- **Diretrizes de Segurança**:
  - Zero duplicação de regras em C#;
  - Chamadas estritamente não-bloqueantes para preservar a responsividade do AutoCAD;
  - Controle de concorrência com flag `_isActionRunning` e bloqueio de cliques múltiplos;
  - Barra de status simples: `Pronto`, `Executando...`, `Concluído`, `Falhou`, `Requer especificação`.

### Evolução OXCAD 0.4.0 — Homologação Operacional e Endurecimento da Infraestrutura
A versão 0.4.0 estabiliza e endurece a integração entre o AutoCAD, .NET C# e o backend Python, eliminando fragilidades operacionais sob condições adversas de sistema:

1. **Extração Resiliente de JSON (`ExtrairJsonValido`)**:
   - Isolamento robusto do bloco JSON delimitado pelo primeiro `{` e último `}` na saída padrão.
   - Protege a desserialização contra poluição de warnings de pacotes terceiros (ex: `urllib3`, `requests`, `openpyxl`) ou logs de stdout.
2. **Supressão Preventiva de Warnings**:
   - `workspace/workspace_context_cli.py` com `warnings.filterwarnings("ignore")` garantindo canal stdout 100% puro para contratos de intercâmbio.
3. **Gestão Atômica de Processos e Prevenção de Zumbis (`EncerrarProcessoETodosOsFilhos`)**:
   - Em caso de timeout em subprocessos de consulta ou ação, execução determinística de `taskkill /F /T /PID` no Windows para eliminação de toda a árvore de subprocessos, prevenindo processos órfãos em background.
4. **Resolução de Diretório Raiz Multi-Fallback (`ObterDiretorioRaizProjeto`)**:
   - Cadeia determinística: (1) `AUXCAD_ROOT`, (2) Assembly location, (3) Diretório do DWG ativo, (4) Diretório corrente, garantindo localização de `acaddoc.lsp` e pasta `workspace` mesmo com `NETLOAD` de pastas remotas.
5. **Diagnóstico Gracioso de Falha de Executável**:
   - Captura específica de `System.ComponentModel.Win32Exception` com emissão de mensagem operacional amigável informando a necessidade de configurar `PYTHON_EXECUTABLE` sem propagar exceções não tratadas para a interface WPF.
6. **Timeout Configurável**:
   - Suporte a personalização via variável de ambiente `OXCAD_TIMEOUT_MS` (com fallback seguro para 8000ms).
7. **Preservação de Comandos e Regras de Negócio**:
   - Unifilar mantido com classificação estrita `Requer especificação` e orientação de comandos nativos do CAD (`UNIFILAR` / `PROTECAO`).
   - Zero regras de negócio em C# (Thin Frontend / Smart Backend).

### Evolução OXCAD 0.5.0 — Controle Operacional de Tempo por SOB e JobTime
A versão 0.5.0 introduz o controle rigoroso, auditável e persistente do tempo produtivo gasto em cada projeto/SOB:

1. **Investigação do JobTime do AutoCAD**:
   - Constatado que o comando `JOBTIME` não é nativo do AutoCAD (trata-se de um VLX/add-on de terceiros da Arkance/CAD Studio).
   - O mecanismo embutido do AutoCAD (`TIME`, `TDINDWG`, `TDUSRTIMER`) é read-only no DWG para edição acumulada, herda tempos prévios do template `BASE_DESENHO.dwg`, não permite pausa determinística nem rastreabilidade de início/fim gerencial.
   - **Decisão**: Implementação de motor próprio de domínio `OxCadJobTimer` (`workspace/workspace_time.py`) com persistência em `.oxcad/time.json`.
2. **Semântica e Fonte da Verdade Sem Deriva**:
   - Não utiliza loops, `Thread.Sleep` ou timers como fonte de dados.
   - Baseado exclusivamente em timestamps ISO 8601 UTC (`DateTimeOffset`).
   - Cálculo determinístico de tempo trabalhado: `tempo = acumulado + (agora - sessao_atual_inicio)`.
3. **Persistência Fora do DWG**:
   - Arquivo `.oxcad/time.json` armazenado na raiz da SOB com gravação atômica via arquivo temporário `.tmp` e substituição transacional.
   - Preservado com segurança em caso de queda, encerramento ou reinicialização do AutoCAD.
4. **Integração no Ciclo de Vida da SOB**:
   - Integrado diretamente ao orquestrador do comando `SOB` (`sob/sob_manager.py`), inicializando o apontamento com a criação do DWG.
5. **Interface WPF da Paleta OXCAD**:
   - Card visual discreto `TEMPO DO PROJETO` apresentando Início, Tempo trabalhado, Estado e Conclusão.
   - Ações contextuais de Iniciar, Pausar, Retomar, Concluir (com confirmação) e Reabrir.
   - `DispatcherTimer` a cada 1s executando apenas cálculo visual sem impacto de I/O em disco.

### Evolução OXCAD 0.5.2 — Auditoria Final do PID, Heartbeat e Ciclo Real do AutoCAD
A versão 0.5.2 consolida a auditoria profunda da integração de processos Windows com o AutoCAD, eliminando a vulnerabilidade de reciclagem de PID pelo sistema operacional e blindando o ciclo de vida do apontamento operacional de tempo:

1. **Auditoria e Eliminação de Vulnerabilidade de Reciclagem de PID**:
   - **Vulnerabilidade Identificada**: No Windows, um PID pode ser reciclado pelo kernel e atribuído a outro processo qualquer do sistema operacional após o encerramento do `acad.exe`. Se um novo AutoCAD ou processo do sistema recebesse o mesmo PID, uma verificação baseada unicamente em `PID` falharia em distinguir a troca de processo.
   - **Solução Arquitetural Implementada**: Criação do `InstanciaSessionToken` no C# (`WorkspaceService.cs`), que combina `Process.GetCurrentProcess().Id`, `Process.GetCurrentProcess().StartTime.ToUniversalTime().Ticks` e um `Guid` aleatório imutável instanciado na inicialização da aplicação host.
   - **Propagação**: Passagem de `--acad-pid <PID>` e `--acad-token <TOKEN>` via CLI (`workspace_context_cli.py`).
   - **Detecção Determinística**: Em `workspace/workspace_time.py`, a função `tratar_interrupcao_se_necessario` valida a congruência de `token_sessao`. Se o token gravado no `time.json` for divergente do token da sessão corrente do AutoCAD, a interrupção é detectada com 100% de determinismo, eliminando qualquer risco de falso-positivo ou falso-negativo por reaproveitamento de PID.

2. **Auditoria do Heartbeat e Preservação da Fonte de Verdade**:
   - **Mecanismo Não-Bloqueante**: Disparado a cada 60s em background através de `Task.Run` e protegido pela flag atômica `_isHeartbeatRunning` contra sobreposição de chamadas sob alto estresse de CPU.
   - **Fonte Canônica de Dados**: O heartbeat atua estritamente como *touch* defensivo de metadados (`ultima_atividade` e `ultima_atualizacao`). Não soma tempo (+60s) nem incrementa acumulados.
   - **Estabilidade Assintótica do JSON**: O arquivo `time.json` mantém tamanho fixo e zero criação de sessões espúrias durante horas contínuas de trabalho (comprovado em teste de 120 pulsos de heartbeat).
   - **Tratamento de Exceções**: Qualquer falha transitória de I/O é absorvida silenciosamente sem propagar erro para o loop de despacho do WPF.

3. **Margem Máxima de Incerteza em Crash**:
   - Em caso de crash súbito (kill de processo, tela azul, corte de energia), a sessão é consolidada até a `ultima_atividade` gravada pelo último heartbeat. A margem máxima de incerteza operacional pós-queda é rigorosamente limitada ao intervalo do heartbeat (**60 segundos**).

4. **Matriz de Auditoria e Validação Metodológica**:
   - **TESTE AUTOMATIZADO**:
     - Detecção de colisão de PID reciclado com `token_sessao` divergente;
     - Heartbeat idempotente ignorado em `Pausado` e `Concluido`;
     - Longo período sem inchaço de JSON (120 pulsos sucessivos);
     - Pausa seguida de fechamento mantendo estado `Pausado` na reabertura;
     - Conclusão mantendo estado `Concluido` e tempo congelado;
     - Timezone ISO 8601 UTC explícito em todos os campos;
     - Robustez contra PIDs inválidos, nulos e negativos em `processo_esta_ativo`.
   - **VALIDAÇÃO POR INSPEÇÃO**:
     - Confirmação de que `Process.GetCurrentProcess()` no contexto do plugin .NET via `NETLOAD` roda in-process e representa o processo host `acad.exe`;
     - Confirmação de que campos `tempo_total_segundos` e `tempo_formatado` são valores derivados de runtime, não fontes de verdade;
     - Verificação de encoding UTF-8 puro no canal stdout sem poluição de warnings de dependências.
   - **VALIDAÇÃO MANUAL (AUTOCAD REAL)**:
     - Classificada como PENDENTE de execução física pelo operador em workstation com viewport ativa do AutoCAD, conforme protocolo da Seção 25 do roteiro de release.

### Evolução OXCAD 0.5.3 — Validação Operacional no AutoCAD
A versão 0.5.3 consolida o fechamento do ciclo de controle operacional de tempo por SOB, preparando a infraestrutura para a validação real dentro do AutoCAD:

1. **Unificação e Propagação de Versão 0.5.3**:
   - `oxcad/OxCadPaleta.csproj`: Atualizado para versão `0.5.3`, `AssemblyVersion 0.5.3.0` e `FileVersion 0.5.3.0`.
   - `oxcad/OxCadControl.xaml`: Rodapé atualizado para `OXCAD 0.5.3 • AUX CAD`.
   - `tests/test_oxcad_hardening.py`: Teste `test_versao_oxcad_0_5_3_propagada` validado com 100% de cobertura.
   - Build Release compilado sem erros para ambos os targets (`net8.0-windows` e `net48`).

2. **Carregador Oficial e Integração Universal**:
   - `acaddoc.lsp`: Registra suporte e invoca `oxcad/oxcad_loader.lsp`.
   - `oxcad/oxcad_loader.lsp`: Detecta versão do AutoCAD (`ACADVER >= 25.0` -> `net8.0-windows`, `< 25.0` -> `net48`), provendo os comandos `OXCAD`, `FECHAR_OXCAD` e `RECARREGAR_OXCAD`.

3. **Status da Homologação**:
   - **Regressão Global**: 536 testes aprovados, 3 skipped, 0 falhas em 92s.
   - **Testes OXCAD**: 64 testes aprovados (100%).
   - **Modelos Oficiais**: Hashes SHA-256 intactos (`cqt_modelo.xlsm` e `prancha.dwg`).
   - **Veredito**: HOMOLOGADO COM RESSALVAS (pendente de validação manual do operador na viewport ativa do AutoCAD aberto).
4. **Correção de Homologação Real no AutoCAD (`oxcad_loader.lsp`)**:
   - **Diagnóstico do Erro Real**: Durante o primeiro carregamento manual no AutoCAD 2026, o comando `OXCAD` emitiu `; error: bad argument type: stringp nil`.
   - **Causa Raiz**: A função `oxcad-get-dll-path` dependia de `load-aux-find-root` (não declarada) e realizava `(findfile "oxcad_loader.lsp")`. Ao carregar via `(load "oxcad/oxcad_loader.lsp")`, `findfile` retornava `nil` e `(vl-filename-directory nil)` disparava a exceção de tipo de argumento. Além disso, `(vl-filename-nxname)` e `(command "OXCAD")` sofriam risco de avaliação nula / recursão.
   - **Correção Aplicada**: Cadeia de resolução dinâmica e agnóstica de `base-dir` com checagem de tipos estrita (`stringp`), implementação inline autossuficiente de `vl-filename-nxname`, sanitização contra variáveis `nil` e invocação global via `(vl-cmdf "_.OXCAD")`. 100% de adesão à regra de zero dependência a caminhos hardcoded.
5. **Homologação Física Concluída no AutoCAD 2026**:
   - **Ambiente Real**: Autodesk AutoCAD 2026 (PID 64656) executando em Windows 11 x64 com target .NET 8 (`net8.0-windows`).
   - **Projeto/SOB Real Testado**: SOB `A043257319` (`EXEMPLO GRUPO A COM AVT - MC_A043257319_DESENHO_REV01.dwg`).
   - **Ciclo Completo Comprovado em Produção**:
     1. Abertura da PaletteSet via comando `OXCAD` com docking lateral nativo;
     2. Reconhecimento automático da SOB e detecção de artefatos existentes (DWG, Checklist, Memorial, CQT);
     3. Início da contagem de tempo (Sessão 1: 3.3s);
     4. Pausa operacional (19s em pausa descartados do tempo trabalhado);
     5. Retomada da contagem (Sessão 2: 8.9s);
     6. Conclusão formal com gravação de data/hora início (`26/09/2026 15:32`), conclusão (`26/09/2026 15:33`) e tempo congelado (`00:00:12`);
     7. Persistência atômica validada no disco em `.oxcad/time.json` (1.012 bytes);
     8. Interface gráfica WPF responsiva, sem flicker e 100% sincronizada com a fonte de verdade em disco.
   - **Veredito Oficial**: **HOMOLOGADO**.
6. **Ajustes de Ações da Paleta (Feedback Operacional)**:
   - **CPFC**: Adicionado bootstrap resiliente de `sys.path` em `cpfc/cpfc_manager.py`, eliminando `ModuleNotFoundError: No module named 'cpfc'` ao disparar via paleta/CLI.
   - **Ambiental**: Adicionado mecanismo de elevação e foco (`deiconify`, `lift`, `-topmost`, `focus_force`) em `ambiental/memorial_ambiental_generator.py`, garantindo que a janela Tkinter venha para o primeiro plano sobre o AutoCAD.
   - **AutoPrancha**: Esclarecido o fluxo: o AutoPrancha é uma ferramenta gráfica interativa que roda nativamente no ModelSpace do AutoCAD (`AUTOPRANCHA` / `autoprancha.lsp`). O botão na paleta exporta o contexto do projeto para `prancha_contexto.json` e notifica o usuário na barra de status: `AutoCAD | Módulo AutoPranche: Contexto exportado. Digite AUTOPRANCHA no AutoCAD.`
7. **Evolução OXCAD 0.6.0 — Infraestrutura Central de Logs, Auditoria e Observabilidade**:
   - **Auditoria de Diagnóstico**: Realizado levantamento completo prévio de mecanismos de diagnóstico (`print`, `logging`, `catch`, subprocessos).
   - **Arquitetura de Logging Unificada**:
     - Python: Criado `common/logging_config.py` com `JsonLinesFormatter`, `SafeRotatingFileHandler` e `OxCadLoggerAdapter`. Rotação de 5 MB e retenção de 5 arquivos.
     - C# .NET: Criado `oxcad/OxCadLogger.cs` com formatação JSONL thread-safe sem dependências externas adicionais, gravando simultaneamente em `logs/application.jsonl` e `logs/errors.jsonl`.
   - **Propagação de Correlação Fim-a-Fim**:
     - Injeção de `correlation_id` a partir da UI/WorkspaceService em C#, propagada via `--correlation-id` para a CLI `workspace_context_cli.py`, chegando a `workspace_actions.py` e subprocessos gerados.
   - **Rastreabilidade de Subprocessos e Transições**:
     - Subprocessos operacionais (CQT, Orçamento, CPFC, Ambiental, AutoPrancha, Preparar SOB) registram início, PID (`subproc_pid`), comando sanitizado e conclusão.
     - Transições de tempo (`tempo.iniciado`, `tempo.pausado`, `tempo.concluido`, `tempo.reaberto`, `tempo.interrompido`) registradas em nível `INFO`. Heartbeat isolado em nível `DEBUG`.
   - **Segurança e Sanitização**:
     - Sanitização ativa em C# e Python contra vazamento de senhas, tokens, cookies e credenciais sensíveis (`sanitizar_mensagem` / `Sanitize`).
     - Proteção no `.gitignore` impedindo versionamento de `logs/`, `*.log` e `*.jsonl`.
   - **Diagnóstico Operacional**:
     - Novo comando AutoCAD `OXCAD_DIAGNOSTICO` expondo versão, processo, PID, diretório, arquivos de log ativos e contagem de eventos recentes.
   - **Testes & Qualidade**:
     - 14 testes unitários e de integração dedicados de logging (`tests/test_oxcad_logging.py`) aprovados (100% PASS).
     - Suíte específica OXCAD: 78 testes aprovados (100% PASS).
     - Suíte global de regressão: 549 testes aprovados, 4 skipped, 0 falhas, 0 erros.
     - Compilação .NET Release (`net8.0-windows` e `net48`) com 0 erros.
     - Modelos oficiais íntegros por SHA-256 (`cqt_modelo.xlsm`: `09224E...`, `prancha.dwg`: `13562C...`).
   - **Veredito Oficial**: **HOMOLOGADO**.
8. **Identidade Visual e Assets Oficiais OXCAD**:
   - **Conceito Geométrico Monograma OX**:
     - Fusão geométrica de precisão CAD: anel "O" (ciclo, projeto, integração sistêmica) e eixos diagonais ortogonais "X" a 45° (automação, transformação, conexões nodais).
     - Cortes técnicos de folga (kerf CAD) nos pontos de sobreposição, retículo central de precisão cartesiana e terminais com snap points/nós de controle vetoriais.
   - **Paleta de Cores Oficial**:
     - Destaque Primário: Azul Elétrico CAD (`#4EA8DE`).
     - Acentos Técnicos: Ciano Técnico Snap (`#72EFDD`) e Azul Profundo Engenharia (`#0077B6`).
     - Estrutura: Grafite Técnico (`#1E222D`) e Slate Técnico (`#2B3245`).
     - Nós e Mira: Branco Puro (`#FFFFFF`).
     - Validação Monocromática: Alto contraste límpido preservado em escala de cinza/preto e branco.
   - **Catálogo de Assets em `oxcad/assets/`**:
     - `oxcad.svg`: Fonte vetorial mestre (512x512).
     - `oxcad_wordmark.svg`: Logotipo completo horizontal (1024x320) com tipografia técnica.
     - `oxcad.png`: Master raster em alta resolução (1024x1024) com canal alpha transparente.
     - `oxcad_mono.png`: Versão monocromática (1024x1024) para alto contraste.
     - `oxcad_wordmark.png`: Logotipo rasterizado (1024x320).
     - `oxcad.ico`: Ícone nativo do Windows multi-resolução legítimo (16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256).
     - Pacote raster individual: `oxcad_16.png`, `oxcad_24.png`, `oxcad_32.png`, `oxcad_48.png`, `oxcad_64.png`, `oxcad_128.png`, `oxcad_256.png`.
   - **Geração Reprodutível**:
     - Script determinístico `oxcad/scripts/generate_assets.py` com supersampling 4x e anti-aliasing Lanczos.
   - **Integração no Aplicativo**:
     - Incorporado no cabeçalho WPF da paleta `oxcad/OxCadControl.xaml` com carregamento desacoplado em `OxCadControl.xaml.cs`.
     - `oxcad/OxCadPaleta.csproj` configurado para distribuir `assets/` para os builds `net8.0-windows` e `net48`.
   - **Testes Automatizados**:
     - Suíte `tests/test_oxcad_assets.py` com 7 testes dedicados (100% PASS).
     - Suíte global de testes: 558 passed, 2 skipped (0 falhas, 0 erros).
   - **Veredito Oficial**: **HOMOLOGADO**.
9. **Fechamento Formal e Release OXCAD 0.6.0**:
   - **Homologação Física no AutoCAD 2026**:
     - Sessão Interativa: Autodesk AutoCAD 2026 (PID `46664`, `acad.exe`, v25.1.0.0, .NET 8.0.29).
     - Assembly .NET 8: `OxCadPaleta.dll` versão `0.6.0.0` (commit `853dc5356f02b5aa1dfa957dbe0ef203f8f156cc`) confirmada em memória física.
     - Diagnóstico: Comando `OXCAD_DIAGNOSTICO` executado com resposta limpa e status de observabilidade.
     - Interface Gráfica WPF: Cabeçalho com monograma técnico OX renderizado e controles ativos.
     - Fluxo Real de Engenharia: Resolução de contexto com SOB `A043257319` em 15.9ms.
     - Rastreabilidade End-to-End: `correlation_id` compartilhado entre o host AutoCAD e subprocessos Python gravado em `logs/application.jsonl`.
     - Veredito da Versão: **HOMOLOGADO**.

10. **Auditoria de Coerência e Caminho de Execução Real — `mapa_cad_paleta`**:
   - **Mapeamento de Chamadas Reais**: Verificados todos os pontos de comunicação entre Web (JS), WPF/WebView2, CadBridge e DWG.
   - **Sincronização de Identidade**: `resultado_insercao` e `resultado_vao` no frontend (`app.js`) agora sincronizam e confirmam os IDs canônicos emitidos pelo backend C# no `TracadoState`.
   - **Hierarquia de Sincronização DWG**: Estabelecida precedência rígida: `estado_dwg` (v2) é o canal canônico de reconstrução topológica autoritativa; `postes_dwg` (v1) rebaixado a fallback legado.
   - **Rigidez em COPY SET**: Identificação de conjunto copiado agora exige que AMBAS as extremidades do vão pertençam ao conjunto remapeado para emitir `COPY_SET_REPAIRED`. Se apenas uma ponta foi copiada, o sistema emite `COPY_SET_UNCERTAIN` e não redireciona referências arbitrariamente.
   - **Defesa Contra Versão Futura de XData**: Se uma entidade no DWG contiver `schemaVersion > XDATA_SCHEMA_VERSION` (v2), o scanner emite `UNSUPPORTED_XDATA_VERSION` e não sobrescreve os dados.
   - **Eliminação de Warnings de Compilação**: Eliminados todos os avisos CS8600, CS8601, CS8602, CS8604 em `CadBridge.cs` e `MapaControl.xaml.cs`. Compilação `net48` e `net8.0-windows` limpa com 0 avisos de código.
   - **Status Geral**: IMPLEMENTAÇÃO: COMPLETA | INTEGRAÇÃO INTERNA: COMPLETA | TESTES OFFLINE: PASS (59/59) | BUILD: PASS (0 erros) | RUNTIME AUTOCAD: NÃO VALIDADO (acad.exe ausente) | HOMOLOGAÇÃO ASSISTIDA: PENDENTE.

11. **Arquitetura OXCAD Baseline P0/P1 — Identidade, MDI e Contratos de Integridade (2026-10-01)**:
   - **Fronteira de Confiança Host -> CLI**:
     - Princípio: O AutoCAD (.NET C# em `acad.exe`) é o único ponto de autoridade sobre o desenho ativo e sua identidade.
     - Comunicação: O Host dispara o CLI (`workspace_context_cli.py`) através de canal protegido por `stdin` transmitindo o envelope JSON autenticado.
     - Verificação de Integridade: O CLI valida via Win32 API (`QueryFullProcessImageNameW`) que o processo pai chamador é genuinamente `acad.exe` com o PID correspondente, recusando parâmetros forjados por linha de comando (`DWG_CONTEXT_NOT_VERIFIED`).
   - **Resiliência MDI (.NET C#)**:
     - Desacoplamento de concorrência com `ContextRefreshGate.cs` utilizando números de geração monotônicos (`context_generation`) e tickets de sessão.
     - Despacho assíncrono na thread de interface via `Dispatcher.BeginInvoke` em `PaletteHost.cs`, evitando reentrância e eliminando a condição de corrida causadora do `STATUS_STACK_OVERFLOW` (`0xc00000fd`).
     - Identidade de desenho ancorada em `Database.FingerprintGuid` e caminho normalizado do arquivo DWG.
   - **Registro de Execuções e Ciclo de Vida (P0.3)**:
     - `OxCadExecutionRegistry.cs` gerencia o ciclo formal de ações com lock seguro, garantindo `ExecutionId != CorrelationId` e proibindo reutilização de identificadores.
     - Sincronização de encerramento atrelada a eventos nativos do documento no AutoCAD.
   - **Contratos P1 de Validação e Entrega**:
     - **P1.1 Validação (`workspace_validation.py`)**: `ValidationSource` captura o hash SHA-256 e `mtime_ns` da fonte de dados no momento da leitura, impedindo o reuso de resultados obsoletos.
     - **P1.2 Versionamento (`workspace_versions.py`)**: Snapshots imutáveis em `.auxcad_versions/` com restauração exclusiva (`xb`) e conferência de checksum.
     - **P1.3 Pendências (`workspace_pending.py`)**: Cadastro autoritativo de pendências em `.oxcad/pending.json` com atomicidade via rename e locking exclusivo.
     - **P1.4 Entrega (`workspace_delivery.py`)**: Geração de pacotes em `.oxcad/deliveries/` com manifesto digital assinado por SHA-256. Recusa pacotes onde a fonte sofreu alterações pós-validação (`VALIDATION_SOURCE_CHANGED`).
   - **Garantia de Não-Falso Sucesso e Auditoria**:
     - `_artefato_tecnico_gerado`: Subprocesso que encerra com código 0 mas não gera arquivo modificado com dados válidos é marcado como `Falhou` (`ARTIFACT_NOT_VERIFIED`).
     - `common/logging_config.py`: `emitir_obrigatorio` e `registrar_evento_obrigatorio` forçam `os.fsync`, assegurando que eventos de ciclo de vida sejam persistidos ou abortem com exceção explícita.
   - **Módulo Integrante de Orçamento no OXCAD (`levantamento_condutores.lsp`)**:
     - Rotina AutoLISP (`c:LEVANTAR_CONDUTORES`) para levantamento expedito de condutores no DWG ativo através da seleção de cotas e textos (`DIMENSION`, `TEXT`, `MTEXT`).
     - Integração na UI do OXCAD: disparado via `BtnLevantarCondutores_Click` no `OxCadControl.xaml.cs`.
     - Carregamento transparente via `acaddoc.lsp` com tratamento seguro de erros (`load-aux-safe`).
     - Contrato verificado por testes de balanço de parênteses, sobreposição de cotas, arredondamento para metros inteiros e despacho no documento (`test_levantamento_condutores.py`).
   - **Status da Baseline**: **P0 E P1 AUDITADOS, VALIDADOS E FECHADOS**.

12. **Hotfix Operacional Pós-Baseline — SharePoint Modern e Resolução de Identidade SOB (2026-10-01)**:
   - **Compatibilidade SharePoint Modern (`sob/sob_sharepoint.py`)**:
     - Seleção de múltiplos itens migrada para atributos semânticos (`input[data-automationid='selection-checkbox']`, `input[aria-label*='Selecionar todas']`, etc.) disparados via script JavaScript para contornar estilização de opacidade zero do Fluent UI.
     - Detecção dinâmica do botão de download na barra de comandos (`Baixar` / `Download`) garantindo ativação resiliente.
   - **Resolução de Identidade SOB vs Artefatos (`_resolver_itens_sob`)**:
     - Busca no SharePoint distingue a entidade SOB de seus múltiplos artefatos (`A057526153`, `A057526153_CROQUI.pdf`, `A057526153_FOTOS.zip`). Múltiplos artefatos pertencentes à mesma SOB não geram mais `SobConflictError`.
     - Precedência determinística: (1) Pasta com nome canônico da SOB; (2) Arquivo de croqui da SOB; (3) Demais artefatos da mesma SOB. Conflito reservado estritamente para SOBs distintas ou pastas de trabalho concorrentes.
   - **Validação Física do Download e Rollback Preservado**:
     - Confirmação física de arquivos descompactados e integridade de tamanho em disco antes de atestar sucesso da etapa. Falhas preservam reversão atômica (`rollback`) sem afetar arquivos de execuções anteriores.

13. **Correção Controlada — Fechamento da Cadeia PREPARAR SOB -> DWG -> Contexto OXCAD (2026-10-01)**:
    - **Reconciliação Segura e Determinística no AutoCAD Host**:
      - `ProjectScopeContract.ReconcileCompletedManifest`: Valida `.sob_state.json` com status `CONCLUÍDO`, compara canonicamente `base_dwg` com o caminho ativo do DWG e recusa identidades conflitantes na pasta.
      - `DwgProjectScopeStore.TryReconcile`: Aplica o binding com `document.LockDocument()`, persiste no `NamedObjectsDictionary` e executa salvamento controlado.
      - `OxCadControl.xaml.cs`: `AtualizarContextoAsync` tenta reconciliação determinística antes de rejeitar escopos não vinculados, tanto no carregamento/ativação quanto no clique manual de `🔄 Atualizar Contexto`, garantindo a habilitação de todos os botões de engenharia (`_projectScopeResolved == true`).
    - **Eliminação de Falso `ARTIFACT_NOT_VERIFIED` para a Ação `sob`**:
      - `workspace_context_cli.py`: Implementado `_artefato_sob_gerado`, garantindo que processos concluídos com sucesso (código 0) e evidências físicas válidas (manifesto `CONCLUÍDO`, `base_dwg` íntegro) sejam reconhecidos como sucesso sem erros espúrios de auditoria.
    - **Status**: **CORREÇÃO CONSOLIDADA E VALIDADA; P2 PERMANECE SUSPENSA**.

17. **Decisão Arquitetural — Resolução Determinística e Atestação de Artefato da Ação SOB (`workspace_context_cli.py` & `sob/`) (2026-10-01)**:
    - **Problema Operacional Identificado**:
      - Na ação `PREPARAR SOB`, mesmo com `exit_code=0` e o DWG sendo criado e aberto corretamente, o monitoramento de auditoria da ação registrava `ARTIFACT_NOT_VERIFIED`.
      - A função `_artefato_sob_gerado` tentava importar `sob.sob_config` (módulo inexistente) e, após engolir o `ImportError`, buscava o manifesto `.sob_state.json` com fallback para `p_root` (apontando para o DWG aberto antes da ação, tipicamente `models/prancha.dwg`).
    - **Regra Arquitetural Obrigatória (Zero Varredura Aleatória)**:
      - Proibida categoricamente qualquer busca aleatória ou varredura de diretórios históricos em `G:\Meu Drive` ou árvore de arquivos para localizar manifestos `.sob_state.json`. Uma varredura arbitrária arrisca atestar falsamente um manifesto antigo ou de outra obra.
    - **Solução Determinística Baseada em Fluxo de Dados**:
      - `SobOrchestrator.executar`: Aceita o parâmetro opcional `resultado_json`. Ao finalizar com sucesso, registra `manifesto_path`, `SOB_ROOT`, `BASE_DWG`, `SOB_ID` e `sucesso`, gravando o resultado estruturado em disco de forma atômica.
      - `SobLauncherDialog` e CLI (`sob_launcher_gui.py`): Aceitam `--resultado-json` / `--result-file` e propagam ao orquestrador.
      - `workspace_actions.py` (`montar_comando_sob`, `executar_sob`): Envia a flag de resultado estruturado para o lançador da GUI.
      - `workspace_context_cli.py`: Cria arquivo de resultado temporário por execução, despacha no comando da SOB e repassa o resultado estruturado para `_artefato_sob_gerado()`.
      - `_artefato_sob_gerado`: Valida fisicamente o caminho explícito retornado:
        1. Pasta existe e manifesto `.sob_state.json` existe com tamanho > 0;
        2. JSON íntegro e parseável;
        3. `status == CONCLUÍDO`;
        4. `sob_id` válido e coerente;
        5. `base_dwg` existe fisicamente, possui tamanho > 0 bytes e localiza-se dentro da pasta da SOB criada;
        6. Ausência de caminho explícito ou falha em qualquer critério físico resulta em recusa imediata e diagnosticável.
    - **Qualidade e Cobertura**:
      - Suíte dedicada `tests/test_sob_artifact_verification.py` com 7 cenários obrigatórios (A até G) passando 100%.
      - Suíte completa de 739 testes do repositório executada com 100% de aprovação (737 pass, 2 skip).
      - Build .NET do OXCAD sem erros (0 Erros).
      - Harness C# `OxCadContextGateHarness` 100% aprovado.
    - **Status**: **RESOLVIDO DETERMINISTICAMENTE; P2 PERMANECE SUSPENSA**.

18. **Decisão Arquitetural — P2.1: Motor Analítico de Indicadores de Gestão (`workspace/workspace_indicators.py`) (2026-10-02)**:
    - **Princípio e Escopo**:
      - Motor puramente read-only, funcional e determinístico. Nenhuma escrita em disco, nenhuma alteração de estado de projeto e zero infraestrutura externa (sem banco de dados relacional/NoSQL, sem serviços residentes).
      - Não se integra como ação operacional de execução do `workspace_context_cli.py`, operando como módulo de consulta analítica independente para não interferir no ciclo de vida de `OxCadExecution`.
    - **Hierarquia de Autoridade das Fontes**:
      1. *Fontes Duráveis de Projeto*: `.oxcad/pending.json` (cadastro autoritativo de pendências), `.oxcad/deliveries/` (pacotes e aprovações), `.oxcad/time.json` (sessões e tempo de apontamento) e `.sob_state.json` (manifesto de preparação da SOB) representam a verdade persistente.
      2. *Fontes Observacionais Rotativas*: `logs/application.jsonl` e `logs/errors.jsonl` representam uma janela temporal limitada (~5 MB por arquivo com rotação).
    - **Regras Analíticas Contratuais**:
      - *Reconstrução por `execution_id`*: Agrupa todos os eventos pertencentes à mesma execução para determinar o estado final (`Concluido`, `Falhou`, `Cancelado`), calculando duração e atribuindo falhas uma única vez por ciclo.
      - *Identidade Estrita*: Consultas por SOB filtram rigorosamente por `sob_id`. Se houver divergência entre o manifesto do diretório e a SOB informada, a agregação é recusada deterministamente com `IDENTITY_UNVERIFIABLE`.
      - *Integridade da Ausência*: Ausência de dados não é convertida em zero quando produzir distorção de interpretação (ex.: taxas de pendências e duração são reportadas como `None` sob status `NÃO DISPONÍVEL`).
      - *Tolerância a Falhas e Auditoria*: Leitura resiliente de logs linha a linha; linhas corrompidas ou truncadas são ignoradas sem interromper o processamento e registradas em `qualidade_dados.linhas_invalidas_log`.
    - **Qualidade e Cobertura**:
      - Suíte dedicada `tests/test_oxcad_indicators.py` com 18 testes obrigatórios (100% PASS).
    - **Status**: **IMPLEMENTADO E TESTADO (P2.1 CONCLUÍDO)**.
