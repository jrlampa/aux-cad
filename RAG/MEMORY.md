# MEMORY.md - Contexto do Projeto aux cad

## Visão Geral
Este projeto contém utilitários e rotinas AutoLISP/Python para automação CAD no AutoCAD/Civil 3D, com foco em geoprocessamento, relatórios ambientais, geração de memoriais descritivos e cálculo automatizado de Queda de Tensão (CQT) em Baixa Tensão (BT).

A pasta raiz `aux cad` é organizada em pastas dedicadas por projeto/especialidade, mantendo na raiz apenas os componentes globais e comuns a todos os projetos.

## Arquitetura de Pastas e Módulos

### 1. Raiz Compartilhada (Comum a Todos os Projetos)
- `acaddoc.lsp`: Carregador automático nativo do AutoCAD que registra as subpastas no SupportPath e carrega as rotinas modulares a cada desenho aberto.
- `aux_cad_toolbar.lsp` & `aux_cad_menu.mnu` (`.cuix`, `.mnr`): Barra de ferramentas visual (`AUXCADBAR`) e menu do AutoCAD com atalhos de 1 clique para todos os módulos.
- `modelos/`: Templates e modelos de planilhas e documentos (`checklist_modelo.xlsx`, `cpfc_modelo.xlsx`, etc.).
- `tests/`: Suíte completa de 74 testes unitários cobrindo todos os módulos (100% passing).
- `pytest.ini`: Configuração com `pythonpath = . cqt ambiental orcamento topografia mapa_postes dados_tecnicos cpfc`.
- `Abrir_CQT.bat`: Atalho na raiz para abrir a interface CQT com 2 cliques.
- `Abrir_Orcamento.bat`: Atalho na raiz para abrir a interface de Orçamento com 2 cliques.
- `Abrir_CPFC.bat`: Atalho na raiz para abrir a interface de CPFC (REN 1.059) com 2 cliques.
- `clean.bat`: Utilitário de limpeza de arquivos temporários do Windows.
- `.env.example`: Modelo padronizado de variáveis de ambiente (GOMNET, GOM, URLs de consulta).
- `CAC.md` & `RAG/MEMORY.md`: Diretrizes arquiteturais e histórico da base de conhecimento.

### 2. `cqt/` (Projeto Queda de Tensão BT)
- `cqt_cad_extractor.lsp` (434 linhas): Rotina AutoLISP com comandos **`CQTCAD`**, **`CQT`**, **`CQTUI`**, **`CQTQUADROS`** e **`RECARREGAR_CQT`**:
  - `CQT` / `CQTUI`: Abre imediatamente a interface gráfica interativa para estudos de viabilidade.
  - `CQTCAD`: Extrai vãos e trechos do CAD graficamente ou via prompt, grava com segurança o arquivo de intercâmbio JSON via `vl-filename-mktemp`, garante compatibilidade estrita AutoLISP (`(= (type x) 'STR)` e definição global de `stringp`) e dispara a interface gráfica de forma desacoplada via `(startapp "cmd.exe" ...)`, carregando dados de projeto, trafo e vãos automaticamente.
  - `CQTQUADROS` (e `CQTEXCEL`): Desenha no CAD os Quadros de Resumo do Trafo (47.03 x 47.10 - Verde) e Quadros de CQT por Trecho (33.21 x 13.64 - Vermelho) com suporte a seleção direta de planilha Excel existente (.xlsx / .xlsm) via diálogo Windows (getfiled flag 16) com resolução de caminho absoluto ou reuso do último gerado em C:\Temp.
  - `RECARREGAR_CQT`: Recarrega a rotina imediatamente na memória da sessão do AutoCAD.
- `cqt_live_calc.py` (249 linhas): Motor de cálculo instantâneo em tempo real (Live Preview) para CQT e carregamento do trafo ($QT \le 6,00\%$).
- `cqt_excel_io.py` (276 linhas): Camada de persistência e I/O de planilhas Excel (`load_cables_from_database`, `load_scenario_from_excel`, `load_all_scenarios_from_excel`, `update_cqt_excel`).
- `cqt_scenario_tab.py` (365 linhas): Componente visual de edição de trechos por cenário (`ScenarioTab`), botões de cópia inteligente e painel de Live Preview.
- `cqt_excel_manager.py` (390 linhas): Interface gráfica principal orquestradora (`CQTManagerGUI`) e CLI com botão integrado **"📥 Importar Planilha Existente"** para carregamento dos dados cadastrais e todos os cenários (ATUAL, ATUAL+NC, PROJETADO) a partir de arquivos `.xlsx` ou `.xlsm`, respeitando rigorosamente o limite < 500 linhas.
- `cqt_quadros_generator.py` (717 linhas): Ponte de alta fidelidade entre a planilha Excel e o AutoCAD para desenho dos Quadros Verdes de Resumo do Trafo (47.03 x 47.10) e Quadros Vermelhos de Queda de Tensão por Trecho (33.21 x 13.64). Extrai diretamente os dados operacionais das abas de referência de cada cenário (`ATUAL`, `ATUAL+NC`, `PROJETADO` para cargas e `CQT ATUAL`/`CQT ATUAL+NC`/`CQT PROJETADO` para rede e quedas de tensão acumuladas na Coluna L), dispensando totalmente a aba `CAPA-RESUMO` (que continha dados estáticos defasados), com suporte a cálculo automático de deltas REQ. e fallback analítico inteligente via `cqt_live_calc.py`.
- `Abrir_CQT.bat`: Atalho local na pasta do projeto.

### 3. `ambiental/` (Projeto Ambiental & Cartografia)
- `kmz_point_layer_report.lsp` & `kmz_point_layer_report.py`: Checagem de pontos contra KMZ ambiental e geração de caixas de notas, **marcação gráfica de polígonos 2.5D no AutoCAD** (`KMZCHECK`) e geração desacoplada do **Checklist Ambiental (.xlsx)** com ou sem incidência cartográfica (dispensando o Memorial quando sem restrição, mas gerando o Checklist atestando conformidade). Comandos de recarga rápida `RECARREGAR_KMZ` / `RECARREGAR_CHECKLIST`.
  - **Suporte Total a MultiGeometry & 2.504 Polígonos**: Lê todas as partes e ilhas poligonais de Placemarks complexos (como a Zona de Amortecimento do Parque Estadual dos Três Picos com 20 polígonos), eliminando descartes indevidos de polígonos.
  - **Indexação Espacial Bounding Box (`bbox`)**: Filtro preliminar ultrarrápido (<4s) para testar pontos georreferenciados contra milhares de geometrias sem degradação de desempenho.
  - **Marcação Gráfica de Polígonos**: Gera a rotina `kmz_draw_polygons.lsp` que desenha polilinhas fechadas (`LWPOLYLINE`) nas coordenadas UTM reais dos polígonos interceptados nos layers `AMBIENTAL_APP`, `AMBIENTAL_UC` ou `AMBIENTAL_EXCLUSAO`, com rótulo no centróide.
- `memorial_ambiental_generator.py`: Interface gráfica moderna em Tkinter (100% pt-BR) com layout responsivo em 2 colunas (Cards), cabeçalho executivo (#1B365D), banner de status de restrições em tempo real, suporte a mousewheel e auto-ajuste de largura:
  - **COM Restrição Ambiental**: O **Memorial Descritivo (`.docx`) É OBRIGATORIAMENTE GERADO** juntamente com o **Checklist Ambiental (`.xlsx`)** (`SIM`).
  - **SEM Restrição Ambiental**: O **Memorial Descritivo (`.docx`) É DISPENSADO**. Gera-se obrigatoriamente apenas o **Checklist Ambiental (`.xlsx`)** (`NÃO`).
- `checklist_ambiental_manager.py`: Preenchimento automático do modelo `checklist.xlsx` da concessionária/HBT com marcas `✓` em APPs e identificação de UCs.
- `croqui_ambiental_generator.py`: Geração automática de Ortofoto / Croqui de Satélite georreferenciado (`CROQUI_AMBIENTAL_{SOB}.png`):
  - **Cache de Tiles em Disco (`.tile_cache/`)**: Evita downloads redundantes de satélite ESRI/OSM, permitindo geração offline e instantânea (<50ms) para regiões já acessadas.
  - **Projeção Geodésica Analítica Snyder**: Conversão bidirecional milimétrica `utm_to_latlon` e `latlon_to_utm`.
- `croqui_cad_inserter.lsp`: Inserção automática de Ortofoto/Croqui no AutoCAD via comando **`INSCROQUI`** no ModelSpace ou PaperSpace sem diálogos manuais.
- `postes_detalhador.py`: Parser inteligente de blocos e atributos do CAD (`12/300`, `12/600`, `10/300` etc.).
- `cad_to_kmz_exporter.py` & `cad2kmz.lsp` (298 linhas): Exportador direto do AutoCAD para Google Earth via comando **`CAD2KMZ`** (WGS84 `.kmz`):
  - Resolução de temporários via `vl-filename-mktemp`.
  - Extração de número do poste via atributos do bloco (`cad2kmz-get-attr-num`).
  - Suporte completo a linhas e polilinhas (`LINE`, `LWPOLYLINE`, `POLYLINE`).
  - Execução protegida via `WScript.Shell` com log de diagnóstico e verificação de saída.
- `app_buffer_generator.py` (633 linhas): Motor geodésico analítico de buffers de APP hídrica conforme Código Florestal (Lei 12.651/2012):
  - **Buffer Bilateral Contínuo de 30m**: Cursos d'água / rios / córregos (<10m) com tampas semicirculares e junções angulares (`utm_buffer_linestring`).
  - **Buffer Circular de Raio 50m**: Nascentes e olhos d'água (`utm_buffer_point`).
  - **Classificação Semântica Inteligente**: Mapeia feições de rios e nascentes de arquivos KMZ/KML ou exportadas do DWG.
  - **Auditoria de Postes em APP**: Ray-Casting analítico de postes contra polígonos de APP (`check_postes_in_hydro_app`), alertando postes em infração em vermelho (`AMBIENTAL_APP_ALERTA`).
  - **Geração Gráfica 2.5D no CAD**: Compila rotina ActiveX (`app_draw_buffers.lsp`) desenhando os polígonos na camada `AMBIENTAL_APP_HIDRICA` (Ciano).
  - **Integração com Memorial e Checklist**: Alimenta `kmz_boxes.txt` ativando as linhas 24 e 33 do `checklist.xlsx`.
- `app_buffer.lsp` (276 linhas): Comandos do AutoCAD **`APP_BUFFER`**, **`BUFFER_RIO`**, **`BUFFER_APP`**, **`APP_HIDRICA`** e **`RECARREGAR_BUFFER`** com suporte a seleção no DWG ou arquivo KMZ.
- `preferencias_ambiental.json`: Smart Cache de preferências locais.

### 4. `mecanico/` (Projeto Cálculo Mecânico / Esforço em Postes)
- `CALC_RESULTANTE_v1.0.lsp` (v3.0): Cruzamento inteligente de tração resultante com capacidade do bloco do poste (`12/300`, `12/600` etc.), cálculo da taxa de utilização (%) e alerta de sobrecarga (`CALC_RESULTANTE`).
- `CALC_ESF_AUTOCAD.mp4`: Vídeo demonstrativo da rotina no AutoCAD.
- `Poste Duplo T (11m 600 daN).SLDPRT`: Modelo 3D paramétrico de poste.

### 5. `topografia/` (Projeto Topografia, Ruas, KMZ & Importação CSV)
- `kmz_pontos_importer.py` & `kmz_pontos_importer.lsp`: Importador direto de marcadores do Google Earth (`.kmz`/`.kml`) para o AutoCAD via comando **`IMPORTAR_KMZ_POSTES`** (ou **`KMZPOSTES`**):
  - Converte `(lon, lat)` para UTM SIRGAS 2000 (Snyder) analítico.
  - Insere o bloco **`POSTE_`** no ponto UTM exato do cabo.
  - Insere o bloco numerador **`PONTO`** com offset lateral e número `<name>` (ex: `05`) no atributo.
  - Insere anotação técnica MText lateral formatada com as linhas da `<description>` (`11/M`, `N1`, `S1`, `ESF. RESULTANTE...`).
  - Fallback automático caso os blocos não existam no arquivo DWG.
- `IBCOORD.lsp`: Utilitário de coordenadas.
- `IMPORTADOR_CSV_CONTORNOS_v2.2.lsp`: Importação de pontos com contornos.
- `IMPORTADOR_CSV_PRO_v2.1.lsp` & `IMPORTADOR_CSV_PRO.lsp`: Importadores clássicos de CSV UTM.
- `importar-pontos_BASE.lsp`: Importador básico de pontos.
- `pt2blk.lsp`: Conversor de pontos para blocos.
- `addbloco.lsp`: Inserção de blocos orientados ao UCS da tela.
- `TLENTAB.lsp`: Tabelas e medições no CAD.
- `mlrua.lsp` & `STYLE RODOVIA.mln`: Rotinas de multilinhas e eixos viários.
- `backup/`: Cópias históricas e rotinas complementares de backup.

### 6. `orcamento/` (Projeto Orçamento & Levantamento de Materiais)
- `orcamento_cad_extractor.lsp`: Rotina AutoLISP com comandos **`ORCAD`** (varredura inteligente de postes, cabos e equipamentos) e **`ORCUI`** (disparo da interface gráfica).
- `orcamento_core.py` (276 linhas): Motor analítico de regras de negócio, classificação de postes, cálculo de comprimentos com margem técnica de flecha/amarras e consolidação de quantitativos.
- `orcamento_excel.py` (218 linhas): Exportador profissional de planilhas Excel `.xlsx` em 4 abas estruturadas (`RESUMO ORÇAMENTO`, `DETALHAMENTO POSTES`, `DETALHAMENTO CABOS` e `BANCO DE PREÇOS`).
- `orcamento_gui.py` (271 linhas): Interface gráfica moderna em Tkinter com KPIs em tempo real, tabela por categorias, slider de margem de cabos e inserção manual.
- `orcamento_manager.py` (79 linhas): Orquestrador principal CLI/GUI e ponte com o AutoCAD.
- `orcamento_catalogo.json`: Catálogo base de materiais padronizados para redes aéreas.
- `Abrir_Orcamento.bat`: Atalho local na pasta do projeto e na raiz.

### 7. `mapa_postes/` (Estúdio Web de Satélite, Coordenadas e Clientes)
- `mapa_servidor.py` (305 linhas): Servidor HTTP local nativo com API REST:
  - `/api/postes`: Persistência atômica de postes e redes (`dados_postes.json`).
  - `/api/enviar-cad`: Gera dinamicamente `desenhar_postes_gerados.lsp` com blocos `POSTE_`, `PONTO` e descrição empilhada para injeção direta no AutoCAD.
  - `/api/exportar-kmz`: Geração de KML/KMZ para interoperabilidade com o Google Earth Pro.
  - `/api/converter-coordenadas`: Conversor bidirecional analítico Snyder (UTM 23S/24S $\leftrightarrow$ Lat/Lon WGS84).
- `web/index.html` & `web/style.css` (451 linhas): Interface gráfica executiva moderna (Inter, paleta `#1B365D`):
  - **Lançamento Direto de Coordenadas de Campo**: Modal dedicado com suporte a **UTM Métrico** (E/X, N/Y) e **Lat/Lon GPS**, calculando em tempo real e voando suavemente com animação `flyTo` até a posição exata.
  - **Configuração de Postes & Equipamentos de 1 Clique**: Tipo de poste (`11/M`, `11/400`...), estruturas MT/BT, equipamentos (IP, ATERR, DAE, Trafo, etc.).
  - **Quantificação de Clientes & Cargas Especiais Trifásicas**:
    - Contagem de clientes **Monofásicos**, **Bifásicos**, **Trifásicos**.
    - **Cargas Especiais Trifásicas Interligadas**: Lançamento com conversão instantânea bidirecional entre **kVA** e **kW** com Fator de Potência **FP = 0.92** ($kVA = kW / 0.92$ e $kW = kVA \times 0.92$), com sugestões de 1 clique (Bomba, Trafo, Motor, Comércio) e anotação técnica padronizada no CAD (`CARGA TRI: BOMBA 16.3kVA (15kW)`).
- `web/app.js` (368 linhas): Lógica do mapa Leaflet, camadas de satélite (ESRI / Google Híbrido / OSM), marcadores com drag & drop, conversão em tempo real de kVA/kW e conectores de linha de transmissão/distribuição.
- `mapa_cad_launcher.lsp` (85 linhas): Comandos do AutoCAD **`MAPAPOSTES`** (ou **`MAPA`**) e **`ATUALIZAR_MAPAPOSTES`**.
- `Abrir_Mapa_Postes.bat`: Atalho executável de 2 cliques na raiz para inicialização instantânea.

### 8. `mapa_cad_paleta/` (Paleta Cartográfica OSM C# .NET no AutoCAD - Menos 1 Tela)
- `MapaCadPaleta.csproj`: Multi-Targeting SDK para AutoCAD 2025/2026 (`net8.0-windows`) e AutoCAD 2018-2024 (`net48`), empacotando WebView2 e referências nativas `accoremgd`, `acdbmgd` e `acmgd`.
- `Plugin.cs`: Implementação `IExtensionApplication` com comandos AutoCAD **`MAPAPALETA`**, **`OSMPALETA`**, **`FECHAR_MAPAPALETA`** e **`RECARREGAR_MAPAPALETA`**.
- `PaletteHost.cs`: Contêiner nativo `PaletteSet` com acoplamento lateral (docked à direita), auto-hide e hospedagem direta de controle visual WPF.
- `MapaControl.xaml` / `.cs`: Controle WPF com `Microsoft.Web.WebView2` utilizando **Mapeamento de Host Virtual Local (`https://auxcad.local/index.html`)**, eliminando qualquer dependência de servidores web ou portas abertas no sistema.
- `CadBridge.cs`: Ponte de automação do AutoCAD (`DocumentLock`, `TransactionManager`):
  - Criação automática de layers `POSTES`, `POSTES_NUMERO` e `POSTES_DESCRICAO`.
  - Inserção de bloco `POSTE_` (ou fallback vetorial círculo/cruz) na coordenada UTM milimétrica.
  - **Inserção do Bloco Específico "T"**: Quando o poste possui transformador, insere o bloco `"T"` oficial na coordenada exata do poste com preenchimento de potência nos atributos e fallback vetorial 2.5D.
  - **Geometria Anti-Sobreposição**: Afastamento geométrico limpo do bloco numerador `PONTO` $(-2.8, +1.8)$ e do bloco de anotações técnicas `MText` $(+1.8, +1.2)$ garantindo separação visual total sem colisão com o círculo do poste `POSTE_`.
  - **Suporte a Multi-Estruturas MT e BT**: Renderização empilhada e ordenada de múltiplas estruturas de média e baixa tensão no MText.
  - Captura interativa de coordenadas no desenho via `Editor.GetPoint` com sincronização no mapa.
  - Varredura e plotagem de postes do DWG direto no Leaflet.
- `SnyderConverter.cs` & `web/snyder.js`: Algoritmo geodésico Snyder analítico de altíssima precisão para conversão bidirecional entre Lat/Lon WGS84 e UTM SIRGAS 2000 (Fusos 22S, 23S e 24S) com responsabilidade única modularizada.
- `web/index.html`, `web/style.css` e `web/app.js`: Interface moderna em tema executivo `#1B365D` otimizada para paleta estreita com OSM, Satélite ESRI, Google Híbrido, marcador arrastável, multi-estruturas MT e BT com tags dinâmicas e quick chips, seleção de potência do transformador (15 a 300 kVA), conversão kVA $\leftrightarrow$ kW com FP = 0.92, chips rápidos e botões de 1 clique ("📍 Inserir no CAD", "🎯 Ler DWG", "🔄 Sincronizar").
- `mapa_paleta_loader.lsp`: Carregador AutoLISP dinâmico baseado na variável de versão do AutoCAD (`ACADVER`) disparando `NETLOAD`.

### 9. `dados_tecnicos/` (Tabelas de Referência Técnicas BT & MT: SQLite3, JSON e AutoLISP)
- `tabelas_referencia.py` (520 linhas): Criação, exportação e consultas rápidas das tabelas normativas oficiais de Baixa Tensão (BT) e Média Tensão (MT) da concessionária (Fonte: OneNote `BASE.one` e diretório `CALC_ESF`):
  - **Tabela 9 - Condutores de Baixa Tensão**: Dados elétricos e mecânicos reais (`3x150+1x80`, `3x95+1x54,6`, `3x50+1x54,6`, `3x35+1x54,6`), incluindo corrente admissível ($I_n$), tração nominal em daN, diâmetro total (mm), massa linear (kg/km), resistência ($R$ em $\Omega/km$) e reatância ($X$ em $\Omega/km$).
  - **Tabela 7 - Estruturas de Baixa Tensão**: Matriz completa de estruturas (`SI1`, `SI1.AF`, `SI1.2AF`, `SI1B.SI3`, `SI1A.SI3`, `SI1.SI4`, `SI3.S3`, `SI4.SI3`, `SI4`, `SI3`, `SI3.SI3`, `DERIV_VAO`, `FLYTAP`), com seções de neutro/fase, esforço mínimo do poste (300/600 daN), ângulo de aplicação e tipo de fixação mecânica.
  - **Tabelas de Média Tensão (MT)**: Esforços mecânicos por vão (daN) para cabos de alumínio com alma de aço (`CAA`), alumínio puro (`CA`) e protegidos (`XLPE`): `1/0 CAA`, `4/0 CAA`, `336,4 CAA`, `4 CAA`, `1/0 CA`, `4/0 CA`, `336,4 CA`, `2 CA`, `35/50 XLPE` e `185 XLPE`.
  - **Motor de Interpolação & Regra de 3**: Função `buscar_tracao_mt(tipo_cabo, vao_m, condutores)` calcula trações exatas para qualquer vão em metros:
    - *Vão intermediário*: Interpolação linear contínua (ex: vão 35m no 1/0 CAA = 450 daN).
    - *Vão curto (<20m)*: Regra de 3 proporcional ao menor vão tabelado (ex: 10m no 1/0 CAA = 187,5 daN).
    - *Vão longo (>200m)*: Extrapolação linear contínua baseada na inclinação do último intervalo (ex: 220m no 1/0 CAA = 1.473 daN).
  - **Combinação Colinear MT + BT em Paralelo**: Função `calcular_esforco_linha(expressao, vao_m)` aceita expressões combinadas com `+` (ex: `1/0 + 150`, `4/0 CAA + PR95`), somando os módulos na mesma direção e ângulo de ancoragem, além de manter entrada manual pura em daN (`350`, `150d`, `=400`).
  - **Interoperabilidade SQLite3 & JSON**: Gera automaticamente `tabelas_referencia.sqlite3` com tabelas `condutores_bt`, `estruturas_bt` e `cabos_mt_esforcos` indexadas, além do arquivo padronizado `tabelas_referencia.json` (v2.0.0).
- `tabelas_referencia.lsp` (515 linhas): Biblioteca AutoLISP de alto desempenho com dados em memória nativa (zero latência):
  - Funções de API LISP: `(tb-get-condutor chave)`, `(tb-get-tracao chave)`, `(tb-get-tracao-mt chave n_fases)`, `(tb-interpolar-mt chave vao_m)`, `(tb-calcular-linha-esforco input vao_m)`, `(tb-get-estrutura cod fase)`, `(tb-list-condutores)`, `(tb-list-estruturas)`.
  - Comandos interativos no console do AutoCAD: **`TABELAS`**, **`CONDUTORES_BT`** (ou **`BT`**), **`ESTRUTURAS_BT`**, **`CABOS_MT`** (ou **`MT`**) e **`CONSULTAR_TABELA`**.
  - Reconhecimento flexível de keywords no `TABELAS`: aceita `C`, `E`, `M`, `1`, `2`, `3`, `BT`, `MT` ou Enter sem erro de `Invalid option keyword`.
  - Integração no `mecanico/CALC_RESULTANTE_v1.0.lsp`:
    - Mede o vão real da linha no CAD automaticamente (`vlax-curve-getDistAtParam`).
    - Exibe o comprimento no prompt `[Vão medido no CAD: X.X m]`.
    - Aceita entrada manual pura em daN (ex: `350`, `150d`), código de cabo MT/BT ou expressão colinear MT+BT (`1/0 + 150`).
    - Menu de ajuda interativo com `?` em loop contínuo e comandos de recarga rápida `RECARREGAR_RESULTANTE` / `RECARREGAR_MECANICO`.

### 9. `cpfc/` (Projeto Participação Financeira do Consumidor - REN 1.059 ANEEL)
- `cpfc_core.py` (102 linhas): Motor de regras de negócio e cálculo analítico da REN 1.059 ANEEL (Válido até 10/03/2027 - Versão 03):
  - Mapeamento oficial dos 13 subgrupos tarifários (`B1`, `B2rur`, `B2irrig`, `B3`, `B4a`, `B4b`, `A4`, `A3a`, `A3`, `A2`, `AS`, `BT1 Geração`, `BT2 Geração`).
  - Fatores $K_{carga}$ e $K_{geração}$ oficiais tabelados.
  - Cálculo do Encargo de Responsabilidade da Distribuidora ($\text{ERD}$).
  - Proporcionalização do Custo da Obra ($\text{COP} = \text{Custo Total} \times \text{Fator Proporcionalização}$).
  - Cálculo da Participação Financeira ($\text{PF} = \max(0, \text{COP} - \text{ERD})$) e detecção de isenção.
- `cpfc_excel.py` (43 linhas): Camada de persistência em planilha oficial via `openpyxl`:
  - Preenchimento atômico dos dados cadastrais (`C11` a `C19`), orçamento (`C24`, `F30`, `F31`), demandas (`C41`, `C43`, `G66`, `G80`).
  - Preservação integral de fórmulas nativas (`F32`, `G70`, `G72`, `G74`, `G76`, `G82`, `G84`, `G86`, `G88`, `G93`), formatações e imagens de cabeçalho.
- `cpfc_gui.py` (494 linhas): Interface gráfica moderna em Tkinter 100% em pt-BR (#1B365D):
  - Cards visuais organizados para Dados Cadastrais, Orçamento da Obra e Demandas Elétricas.
  - Painel de **Live Preview** em tempo real com KPIs (ERD, Fator Proporc., COP e Banner com destaque de PF ou Isenção).
  - Botão de acesso direto ao **Guia Regulatório da REN 1.059** com modal explicativo dos casos que geram PF.
  - Diálogo de salvamento nativo do Windows (`Salvar Como`) sugerindo `PE_{PROJETO}_CPFC_REN1.059.xlsx`.
  - Diálogo de conclusão com ações de 1 clique para "Abrir no Excel" ou "Abrir Pasta".
- `cpfc_guia_ren1059.py` (28 linhas): Componente didático e regulatório com a síntese dos casos objetivos que geram Participação Financeira (COP > ERD, MMGD Geração > Carga, Obras de Interesse Restrito, Fator Prop = 100%) e hipóteses de gratuidade.
- `cpfc_manager.py` (36 linhas): Orquestrador CLI/GUI com suporte a argumentos de pasta/projeto e JSON de intercâmbio.
- `cpfc_cad_launcher.lsp` (98 linhas): Comandos do AutoCAD:
  - **`CPFC`** / **`CPFCUI`**: Disparo direto com exibição de alerta regulatório no prompt.
  - **`CPFCCAD`**: Disparo com extração de DWG e alerta no prompt.
  - **`CPFCALERTA`** / **`CPFCREGRA`**: Exibe caixa de diálogo visual (`alert`) com o resumo dos casos que geram PF.
- `modelos/cpfc_modelo.xlsx`: Template base oficial mantido na pasta de modelos.
- `Abrir_CPFC.bat`: Atalho executável de 2 cliques na raiz e em `cpfc/`.

### 10. `unifilar/` (Projeto Diagrama Unifilar & Árvore de Dispositivos)
- `arvore_parser.py` (331 linhas): Motor de interpretação de caminhos elétricos (` > ` e `|`), localização da **primeira proteção a montante** (Chave Fusível, Religador, Disjuntor ou a própria Saída do Alimentador no padrão `{cod} - Saida do Alimentador - {cod}`), suporte oficial a strings de nós de 3 partes, separação de Subestação e Alimentador (`ZSL10` $\rightarrow$ `SE.: ZSL`, `ALIM.: 10`), quantificação de Clientes A/B e potência kVA, e geração das linhas formatadas para o CAD com espaçamento rigoroso `DISPOSITIVO DE PROTEÇÃO: <rotulo>`.
- `arvore_database.py` (227 linhas): Motor de persistência e indexação local em SQLite (`unifilar/arvore_cache.sqlite3`) a partir da planilha `documentos/Árvore de Dispositivos.xlsx`, com busca indexada ultrarrápida (<10ms).
- `arvore_client.py` (162 linhas): Cliente com suporte a consultas online à intranet (`URL_ARVORE_DISPOSITIVOS`), autenticação corporativa NTLM com credenciais do `.env` e fallback automático e resiliente para o banco local ou modo resumo manual (`consultar_resumo_manual`).
- `unifilar_manager.py` (108 linhas): Orquestrador de linha de comando e ponte de dados JSON com o AutoCAD (`--ponto`, `--resumo`, `--out`, `--sincronizar`).
- `unifilar_cad.lsp` (411 linhas): Rotina AutoLISP com comandos **`UNIFILAR`** e **`PROTECAO`** (aliases: **`ARVORE`**, **`BUSCAR_PROTECAO`**):
  - Permite digitar o Ponto Elétrico, selecionar no DWG (`entsel`) ou **colar diretamente o resumo copiado do SGT/GOMNET** no prompt (`(getstring T ...)` com reconhecimento automático de `--resumo`).
  - Suporte a confirmação e ajuste rápido interativo de Clientes A/B e KVA antes da inserção gráfica.
  - **Modo Inserir**: Desenha o título verde `DIAGRAMA  UNIFILAR` sublinhado com linha e textos técnicos alinhados à direita.
  - **Modo Atualizar**: Seleciona textos existentes no DWG (onde há `SE.: xxx`, `ALIM.: xx`, `DISPOSITIVO DE PROTEÇÃO: ...`, `Clientes Grupo...`) e substitui os dados reais mantendo a prancha intacta.

### 11. `softwares/` (Instaladores e Aplicações Externas)
- `sisRUA-Installer-1.1.0-Optimized.exe` & `sisRUA-Installer-1.1.0.zip`
- `ArkanceSystems_CADStudio_Job-Time.msi`
- `sisrua2/` & `Lampa/`

### 12. Validação, Debug Completo e Testes
- **Suíte de Testes**: **116 testes unitários passando com 100% de sucesso** (`python -m pytest tests/`).
- **Cobertura de Código Crítica**:
  - `cpfc\cpfc_core.py`: 98%
  - `cpfc\cpfc_notas.py`: 95%
  - `dados_tecnicos\tabelas_referencia.py`: 94%
  - `ambiental\checklist_ambiental_manager.py`: 92%
  - `unifilar\arvore_parser.py`: 92%
  - `unifilar\arvore_database.py`: 92%
  - `cqt\cqt_live_calc.py`: 91%
  - `ambiental\app_buffer_generator.py`: 89%
  - `cqt\cqt_quadros_generator.py`: 88%
  - `orcamento\orcamento_core.py`: 89%
  - `ambiental\croqui_ambiental_generator.py`: 88%
  - `cpfc\cpfc_excel.py`: 88%
  - `ambiental\cad_to_kmz_exporter.py`: 86%
  - `cqt\cqt_excel_io.py`: 88%
  - `cpfc\cpfc_gui.py`: 85%
  - `cpfc\cpfc_manager.py`: 83%
  - `unifilar\arvore_client.py`: 82%
  - `unifilar\unifilar_manager.py`: 80%
  - `mapa_postes\mapa_servidor.py`: 83%
  - `orcamento\orcamento_manager.py`: 81%
- **Auditoria de Sintaxe AutoLISP (.lsp)**: Todos os 28 arquivos `.lsp` do projeto verificados por parser estrito com 100% de parênteses e strings balanceadas (0 erros).
- **Auditoria de Módulos Python (.py)**: Todos os 52 arquivos compilados e em conformidade com as regras de Clean Code e limites de linhas (<750 linhas).
- **Carregador Central `acaddoc.lsp`**:
  - Funções de compatibilidade globais: `stringp`, `fboundp`, `vl-symbol-p`, `vl-sleep`, `vl-filename-nxname`.
  - Suporte dinâmico a 9 pastas no `SupportPath`.
  - Novos módulos integrados: Topografia (`TLENTAB`, `IBCOORD`, `pt2blk`, `mlrua`), CQT (`CQTEXCEL`), Tabelas (`BT`, `MT`), Ambiental (`APP_BUFFER`), Paleta OSM (`mapa_paleta_loader.lsp`), CPFC Notas (`CPFC_NOTAS`).
  - Comando mestre de recarga: **`RECARREGAR_TUDO`** (ou **`RELOAD_AUXCAD`**).
- **Interface Gráfica & Menus**: `aux_cad_toolbar.lsp` e `aux_cad_menu.mnu` sincronizados com 22 botões e itens de menu organizados.

### 14. `mapa_cad_paleta/` (Paleta Cartográfica OSM C# .NET para AutoCAD 2018+)
- Multi-targeting .NET SDK (`net8.0-windows` para ACAD 2025/2026 e `net48` para ACAD 2018-2024) com `Microsoft.Web.WebView2`.
- Layout Sidebar moderno com mapa em tela cheia à esquerda e barra flutuante de ferramentas (OSM, Satélite ESRI, Google Híbrido, Ler DWG, Sincronizar) e painel lateral à direita.
- **P2 - Modo Traçado Contínuo de Linhas/Vãos no CAD (`tracado.js` & `CadBridge.InserirVaoCabos`)**: Conexão automática e sequencial de postes inseridos; desenho de `Line` nos layers `CABOS_BT` (Ciano) e `CABOS_MT` (Magenta) e `DBText` no layer `CABOS_TEXTO` (Amarelo) orientado ao vão sem inversão de ângulo; badges com extensão em metros no mapa.
- **P4 - Camada de Restrições Ambientais com Auditoria em Tempo Real (`ambiental_overlay.js` & `AmbientalParser.cs`)**: Leitura direta de `.kmz`, `.kml` e `.geojson`; sobreposição vetorial sobre satélite com cores normativas (APP, UC, Exclusão, Hídrica); auditoria instantânea por Ray-Casting analítico com banner dinâmico de conformidade/alerta no topo da sidebar.
- Persistência contínua via `localStorage` (`AUXCAD_PALETA_STATE`): restaura a última localização, zoom, camadas, número do poste, dados elétricos e posição do marcador.
- Botão "🗑️ Apagar Marcador" e atalho de clique com botão direito no marcador para removê-lo do mapa e limpar campos X/Y.
- Botão "🧹 Limpar" para resetar campos de estruturas, equipamentos e cargas com agilidade.
- Comandos do AutoCAD: **`MAPAPALETA`** (alias: **`OSMPALETA`**), **`FECHAR_MAPAPALETA`**, **`RECARREGAR_MAPAPALETA`**.

### 13. `documentos/` (Pranchas, Referências e Notas)
- `PRANCHA LIGHT.dwg` e `PRANCHA LIGHT.bak`: Templates de prancha oficial.
- `PLAN_MEDIÇÃO_ELETTRICA_PROJETOS_BASE(1).xlsx` & `Árvore de Dispositivos.xlsx`: Planilhas de medição e dispositivos.
- `anotações-2.one`: Caderno técnico de anotações.
- `Captura de tela 2026-01-29 174711.png`
- `Application does not support just-i.txt` & `Autodesk mudou o motor do AutoCAD r.txt`: Notas técnicas de suporte.
