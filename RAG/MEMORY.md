# MEMORY.md - Contexto do Projeto aux cad

> **Versão Oficial Atual: v0.9.0** | Fonte de verdade: [`VERSION`](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/VERSION) | Releases: [`CHANGELOG.md`](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/CHANGELOG.md)

## Visão Geral
Este projeto contém utilitários e rotinas AutoLISP/Python para automação CAD no AutoCAD/Civil 3D, com foco em geoprocessamento, relatórios ambientais, geração de memoriais descritivos e cálculo automatizado de Queda de Tensão (CQT) em Baixa Tensão (BT).

A pasta raiz `aux cad` é organizada em pastas dedicadas por projeto/especialidade, mantendo na raiz apenas os componentes globais e comuns a todos os projetos.

## Arquitetura de Pastas e Módulos

### 1. Raiz Compartilhada (Comum a Todos os Projetos)
- `VERSION`: Fonte única oficial da versão do projeto (`0.9.0`).
- `CHANGELOG.md`: Registro oficial de mudanças seguindo o padrão Keep a Changelog.
- `acaddoc.lsp`: Carregador automático nativo do AutoCAD que registra as subpastas no SupportPath e carrega as rotinas modulares a cada desenho aberto.
- `aux_cad_toolbar.lsp` & `aux_cad_menu.mnu` (`.cuix`, `.mnr`): Barra de ferramentas visual (`AUXCADBAR`) e menu do AutoCAD com atalhos de 1 clique para todos os módulos.
- `modelos/`: Templates e modelos de planilhas e documentos (`checklist_modelo.xlsx`, `cpfc_modelo.xlsx`, etc.).
- `tests/`: Suíte completa de 300 testes unitários e de integração cobrindo todos os módulos.
- `pytest.ini`: Configuração com `pythonpath = . cqt ambiental orcamento topografia mapa_postes dados_tecnicos cpfc unifilar prancha sob`.
- `Abrir_AUXCAD.bat`: Central Executiva Hub de Engenharia e Diagnóstico do Sistema.
- `Abrir_SOB.bat`: Atalho na raiz para abrir a interface gráfica de preparação da SOB com 2 cliques.
- `Abrir_CQT.bat`: Atalho na raiz para abrir a interface CQT com 2 cliques.
- `Abrir_Orcamento.bat`: Atalho na raiz para abrir a interface de Orçamento com 2 cliques.
- `Abrir_CPFC.bat`: Atalho na raiz para abrir a interface de CPFC (REN 1.059) com 2 cliques.
- `Abrir_AutoPrancha.bat`: Atalho na raiz para abrir o módulo AutoPrancha com 2 cliques.
- `Abrir_Unifilar.bat`: Atalho na raiz para abrir o módulo Diagrama Unifilar com 2 cliques.
- `Abrir_Mapa_Postes.bat`: Atalho na raiz para abrir o Estúdio Web de Satélite com 2 cliques.
- `clean.bat`: Utilitário de limpeza de arquivos temporários, caches e downloads incompletos do Windows.
- `.env.example`: Modelo padronizado de variáveis de ambiente (GOMNET, GOM, URLs de consulta).
- `CAC.md` & `RAG/MEMORY.md`: Diretrizes arquiteturais e histórico da base de conhecimento.

### 2. `cqt/` (Projeto Queda de Tensão BT)
- `cqt_cad_extractor.lsp` (434 linhas): Rotina AutoLISP com comandos **`CQTCAD`**, **`CQT`**, **`CQTUI`**, **`CQTQUADROS`** e **`RECARREGAR_CQT`**:
  - `CQT` / `CQTUI`: Abre imediatamente a interface gráfica interativa para estudos de viabilidade.
  - `CQTCAD`: Extrai vãos e trechos do CAD graficamente ou via prompt, grava com segurança o arquivo de intercâmbio JSON via `vl-filename-mktemp`, garante compatibilidade estrita AutoLISP (`(= (type x) 'STR)` e definição global de `stringp`) e dispara a interface gráfica de forma desacoplada via `(startapp "cmd.exe" ...)`, carregando dados de projeto, trafo e vãos automaticamente.
  - `CQTQUADROS` (e `CQTEXCEL`): Desenha no CAD os Quadros de Resumo do Trafo (47.03 x 47.10 - Verde) e Quadros de CQT por Trecho (33.21 x 13.64 - Vermelho) com suporte a seleção direta de planilha Excel existente (.xlsx / .xlsm) via diálogo Windows (getfiled flag 16) com resolução de caminho absoluto ou reuso do último gerado em C:\Temp.
  - `RECARREGAR_CQT`: Recarrega a rotina imediatamente na memória da sessão do AutoCAD.
- `cqt_live_calc.py` (352 linhas): Motor de cálculo instantâneo em tempo real (Live Preview) para CQT e carregamento do trafo ($QT \le 6,00\%$), contendo o mapeamento completo de todos os 92 condutores homologados oficiais em `CONDUTORES_K` para Fatores de Potência 1.0 e 0.8 (multiplexados, subterrâneos, cabos nus AWG, cabos de cobre, com tolerância ortográfica para `nú`/`nó`/`nu` e acentuações).
- `cqt_excel_io.py` (381 linhas): Camada de persistência e I/O de planilhas Excel (`load_cables_from_database`, `get_default_template_path`, `load_scenario_from_excel`, `load_all_scenarios_from_excel`, `update_cqt_excel`). Catálogo completo com 92 condutores normativos em `DEFAULT_CABLES_BASE` e resolução em cascata do template priorizando `modelos/cqt_modelo.xlsm` (100% offline).
- `cqt_scenario_tab.py` (380 linhas): Componente visual de edição de trechos por cenário (`ScenarioTab`), combobox dinâmico com suporte a todos os 92 condutores, método `update_cables_list` para sincronização em tempo real de linhas e painel de Live Preview.
- `cqt_excel_manager.py` (409 linhas): Interface gráfica principal orquestradora (`CQTManagerGUI`) e CLI com botão integrado **"📥 Importar Planilha Existente"**, resolução de template e propagação automática de novos condutores para as abas dos cenários.
- `cqt_quadros_generator.py` (717 linhas): Ponte de alta fidelidade entre a planilha Excel e o AutoCAD para desenho dos Quadros Verdes de Resumo do Trafo (47.03 x 47.10) e Quadros Vermelhos de Queda de Tensão por Trecho (33.21 x 13.64). Extrai diretamente os dados operacionais das abas de referência de cada cenário (`ATUAL`, `ATUAL+NC`, `PROJETADO` para cargas e `CQT ATUAL`/`CQT ATUAL+NC`/`CQT PROJETADO` para rede e quedas de tensão acumuladas na Coluna L), dispensando totalmente a aba `CAPA-RESUMO` (que continha dados estáticos defasados), com suporte a cálculo automático de deltas REQ. e fallback analítico inteligente via `cqt_live_calc.py`.
- `modelos/cqt_modelo.xlsm`: Template oficial da concessionária Enel/HBT mantido localmente na pasta `modelos/` do repositório para garantir independência de caminhos externos e operação offline imediata.
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

### 6. `orcamento/` (Projeto Orçamento, Levantamento de Materiais e Mão de Obra Oficial)
- `orcamento_builder.py` (345 linhas): Extrator e construtor automatizado de banco de dados a partir dos arquivos de engenharia e orçamentação oficiais (`sisORÇA.xlsx`, `KITS E MATERIAIS REV_31.xlsx` e `Mão de Obra 31-05-2024.xlsm`).
- `orcamento_dados.sqlite3` (9,56 MB) & `orcamento_dados.json` (5,27 MB): Base de dados indexada com 13.822 materiais cadastrados com códigos almoxarifado Enel/SAP, 28.709 composições de kits e 5.158 registros contratuais de mão de obra (Contratos: ENGELMIG `JA10114811`, INDICA `JA10110552`, DÍNAMO `52L0002297`, PROGEN `JA10083389`).
- `orcamento_database.py` (168 linhas): Camada DAO de alta performance com queries parametrizadas (`obter_material`, `obter_itens_kit`, `obter_servico_mo`, `listar_contratos`, `listar_kits`).
- `orcamento_kits.py` (144 linhas): Motor de explosão de kits de engenharia (`M1`, `M2`, `B1`, `B2`, `TR-MONO`, `TR-TRI`, `ATER_EQUIP`, `ESTAI-7,9`, `CXDERDAT`) em materiais almoxarifado unitários com quantitativos de projeto e de substituição/retirada.
- `orcamento_core.py` (405 linhas): Motor analítico de regras de negócio com totalização segregada de materiais, mão de obra contratual (por empreiteira, território A/B/C e ambiente normal/salino), BDI parametrizado e consolidação de quantitativos.
- `orcamento_excel.py` (300 linhas): Exportador profissional de planilhas Excel `.xlsx` em 6 abas estruturadas (`RESUMO ORÇAMENTO`, `DETALHAMENTO MÃO DE OBRA`, `DETALHAMENTO POSTES`, `DETALHAMENTO CABOS`, `FORMATO sisORÇA` e `BANCO DE PREÇOS`).
- `orcamento_gui.py` (390 linhas): Interface gráfica moderna em Tkinter com seletores de Empreiteira (Engelmig, Indica, Dínamo, Progen), Território (A, B, C), Salinidade, KPIs em tempo real e alternância entre visualização de Materiais e Mão de Obra.
- `orcamento_manager.py` (97 linhas): Orquestrador CLI/GUI atualizado com suporte a `--empreiteira`, `--territorio` e `--ambiente`.
- `orcamento_cad_extractor.lsp`: Rotina AutoLISP com comandos **`ORCAD`** (varredura inteligente de postes, cabos e equipamentos) e **`ORCUI`** (disparo da interface gráfica).
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
- `dispositivos_kmz_finder.py` (267 linhas): Localizador geoespacial e analítico de chaves fusíveis, religadores e chaves nos 14 arquivos KMZ de apoio da concessionária (`kmz - Dispositivos 05-2020`). Indexa **134.082 dispositivos reais** com cache local em `dispositivos_kmz_cache.json` e busca instantânea (<5ms) por código (`CF636018`, `SG59356`, `AR010625`) ou dígitos. Conversão geodésica analítica Snyder de WGS84 para UTM SIRGAS 2000 (Fuso 23S/24S).
- `unifilar_diagrama_builder.py` (204 linhas): Construtor vetorial 2.5D do Diagrama Unifilar Esquemático sem escala (SE $\rightarrow$ Tronco MT $\rightarrow$ Proteção $\rightarrow$ Ramal MT $\rightarrow$ Ponto do Projeto). Determinação inteligente de blocos oficiais do AutoCAD: **`"chaves_"`** para chaves fusíveis / seccionadoras, **`"REL."`** (com compatibilidade e fallback bidirecional para `"REL"`) para religadores e **`"TRAFO1"`** (com fallback prioritário `TRAFO1` $\rightarrow$ `TRAFO` $\rightarrow$ `T` $\rightarrow$ `TRANSF` $\rightarrow$ vetorial 2.5D) para transformadores.
- `unifilar_manager.py` (161 linhas): Orquestrador de linha de comando e ponte de dados JSON com o AutoCAD (`--ponto`, `--resumo`, `--out`, `--sincronizar`, `--fuso`, `--escala`), unificando árvore, busca KMZ e geometria do diagrama.
- `unifilar_cad.lsp` (668 linhas): Rotina AutoLISP com comandos **`UNIFILAR`** e **`PROTECAO`** (aliases: **`ARVORE`**, **`BUSCAR_PROTECAO`**):
  - Permite digitar o Ponto Elétrico, selecionar no DWG (`entsel`) ou **colar diretamente o resumo copiado do SGT/GOMNET** no prompt.
  - Suporte a confirmação e ajuste rápido interativo de Clientes A/B e KVA antes da inserção gráfica.
  - Seleção interativa do bloco de Transformador via `(unifilar-obter-bloco-trafo)`: confirma `<TRAFO1>` com `[ENTER]`, lista numerada dos blocos no DWG com `[L]`, seleção direta na tela com clique `[S]`, ou digitação livre.
  - Opções integradas de geração:
    - **[1] Esquema Prancha**: Desenha o título verde sublinhado, textos técnicos alinhados à direita e o Diagrama Unifilar Esquemático 2.5D sem escala com barramento SE, tronco MT, bloco oficial (`"chaves_"` ou `"REL."`), transformador selecionado (`"TRAFO1"`) e ponto alvo com potência kVA.
    - **[2] Ramal Geográfico DWG**: Traça no ModelSpace o ramal MT a partir da coordenada real do dispositivo no KMZ até o poste/ponto selecionado no DWG, inserindo bloco da proteção, bloco do trafo e cota métrica com extensão real do ramal.
    - **[3] Ambos**: Executa o esquema na prancha e o traçado geográfico no DWG.
    - **[4] Somente Texto**: Inserção dos textos técnicos clássicos.
    - **[A]tualizar**: Seleciona textos existentes no DWG (onde há `SE.: xxx`, `ALIM.: xx`, `DISPOSITIVO DE PROTEÇÃO: ...`, `Clientes Grupo...`) e substitui os dados reais mantendo a prancha intacta.

### 11. `softwares/` (Instaladores e Aplicações Externas)
- `sisRUA-Installer-1.1.0-Optimized.exe` & `sisRUA-Installer-1.1.0.zip`
- `ArkanceSystems_CADStudio_Job-Time.msi`
- `sisrua2/` & `Lampa/`

### 12. Validação, Debug Completo e Testes
- **Suíte de Testes**: **155 testes unitários passando com 100% de sucesso** (`python -m pytest`).

- **Cobertura de Código Crítica**:
  - `orcamento\orcamento_excel.py`: 100%
  - `unifilar\unifilar_diagrama_builder.py`: 100%
  - `cpfc\cpfc_core.py`: 98%
  - `cpfc\cpfc_notas.py`: 95%
  - `dados_tecnicos\tabelas_referencia.py`: 94%
  - `ambiental\checklist_ambiental_manager.py`: 92%
  - `unifilar\arvore_parser.py`: 92%
  - `unifilar\arvore_database.py`: 92%
  - `cqt\cqt_scenario_tab.py`: 93%
  - `cqt\cqt_live_calc.py`: 91%
  - `orcamento\orcamento_core.py`: 91%
  - `ambiental\app_buffer_generator.py`: 89%
  - `orcamento\orcamento_database.py`: 88%
  - `orcamento\orcamento_kits.py`: 84%
  - `ambiental\croqui_ambiental_generator.py`: 88%
  - `cqt\cqt_quadros_generator.py`: 85%
  - `cpfc\cpfc_excel.py`: 88%
  - `unifilar\unifilar_manager.py`: 85%
  - `unifilar\arvore_client.py`: 82%
  - `ambiental\cad_to_kmz_exporter.py`: 86%
  - `cqt\cqt_excel_io.py`: 87%
  - `cqt (módulo global)`: 80%
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
- **Renderização de Vias, Calçadas (Passeios) e Obstruções no Traçado Contínuo (`vias_obstrucoes.js`)**: Botão `🏙️ Vias: VISÍVEIS`, consulta em tempo real com prioridade absoluta para a **API Oficial do OpenStreetMap** (`https://api.openstreetmap.org/api/0.6/map.json`), eliminando completamente erros HTTP 406 Not Acceptable de servidores Overpass e bloqueios de CORS no WebView2 (`Access-Control-Allow-Origin: *` / `https://appassets.example`), com resposta rápida (<1s), parser híbrido para JSON e XML (`converterOsmXmlParaJson`), e fallbacks secundários Overpass resilientes. Buffer em torno de novos postes traçados (raio ~150m) ou de toda a extensão do projeto, com separação em camadas de Vias (`#334155`), Calçadas (`#d97706`) e Obstruções/Edificações (`#94a3b8` e `#dc2626`). **Geração Automática de Vias no AutoCAD ao Inserir Postes**: opções explícitas e visíveis no rodapé da sidebar (`chkAutoViasCad`: *"🛣️ Gerar vias no CAD ao inserir poste"*) com proteção `flex-shrink: 0` no CSS e no painel de traçado (`chkTracadoViasCad`: *"🛣️ Gerar vias no CAD a cada poste"*), com sincronização bidirecional, persistência local e deduplicação (`waysProcessados`). Ao inserir um poste ou traçar um vão, calcula analiticamente as coordenadas geodésicas Snyder a partir de UTM (X, Y, Fuso) via `window.Snyder` global (corrigido fechamento sintático em `snyder.js`), calcula larguras reais da pista e passeio via tags OSM (`width`, `lanes`, `est_width`, `highway` e `sidewalk:width`) e renderiza polilinhas 2.5D no AutoCAD (`CadBridge.DesenharElementosUrbanos`): **Eixo Guia Oculto (`VIAS_EIXO` - Cor 8)** configurado com `IsOff = true` (invisível por padrão, servindo estritamente como guia do traçado caso necessário); **Bordos da Pista / Meio-fio (`VIAS_BORDO` - Cor 8)** gerados via offsets bilaterais ($\pm \text{largura}/2$); **Limites do Passeio / Calçada (`VIAS_CALCADA` - Cor 9)** gerados via offsets ampliados ($\pm (\text{largura}/2 + \text{calcada})$); e **Obstruções / Edificações (`OBSTRUCOES_EDIF` - Cor 1)**, inserindo o nome da rua em `DBText` no centroide da via visível na camada `VIAS_BORDO`. Botão dedicado **`🛣️ Vias no CAD`** mantido para desenho sob demanda a qualquer momento. Gerador autônomo de testes DXF/DWG (`scratch/gerar_dxf_dwg_teste.py`) com offsets miter analíticos e conversão headless via `accoreconsole.exe` gerando `TESTE_POSTE_E_VIAS.dwg` e `TESTE_POSTE_E_VIAS.dxf` com 177 entidades reais validadas sem erros. Suíte completa com 156 testes passando (100%).
- **Ferramenta de Medição / Régua Métrica e Geodésica (`medicao.js`)**: Botão `📏 Régua` (atalho `M`/`ESC`), cursor crosshair, linha elástica (rubberband) com medição métrica e azimute em tempo real, suporte a múltiplos segmentos com distâncias parciais e acumuladas, painel flutuante de controle e atalhos para medir a partir do poste atual ou implantar o poste na distância exata medida.
- **P2 - Modo Traçado Contínuo com Edição Completa e Interativa (`tracado.js` & `CadBridge.InserirVaoCabos`)**: Conexão automática e sequencial de postes inseridos; desenho de `Line` nos layers `CABOS_BT` (Cor 2 - Amarelo / Yellow) e `CABOS_MT` (Cor 4 - Ciano / Cyan) e `DBText` no layer `CABOS_TEXTO` (Cor 7 - Branco) orientado ao vão sem inversão de ângulo; badges com extensão em metros no mapa. **Novo sistema de edição e correção**: nós arrastáveis (drag-and-drop) recalculando coordenadas UTM e extensões métricas dos vãos em tempo real; botão `↩️ Desfazer` e atalho global `Ctrl+Z` para desfazer o último vão/poste; exclusão pontual com clique direito no nó ou pelo popup; e gaveta expansível `📋 Postes` com visão geral, centralização rápida (`👁️`) e deleção unitária (`🗑️`) reconectando os vãos adjacentes.
- **P4 - Camada de Restrições Ambientais com Auditoria em Tempo Real (`ambiental_overlay.js` & `AmbientalParser.cs`)**: Leitura direta de `.kmz`, `.kml` e `.geojson`; sobreposição vetorial sobre satélite com cores normativas (APP, UC, Exclusão, Hídrica); auditoria instantânea por Ray-Casting analítico com banner dinâmico de conformidade/alerta no topo da sidebar.
- Persistência contínua via `localStorage` (`AUXCAD_PALETA_STATE`): restaura a última localização, zoom, camadas, número do poste, dados elétricos e posição do marcador.
- Botão "🗑️ Apagar Marcador" e atalho de clique com botão direito no marcador para removê-lo do mapa e limpar campos X/Y.
- Botão "🧹 Limpar" para resetar campos de estruturas, equipamentos e cargas com agilidade.
- Comandos do AutoCAD: **`MAPAPALETA`** (alias: **`OSMPALETA`**), **`FECHAR_MAPAPALETA`**, **`RECARREGAR_MAPAPALETA`**.

### 15. Inovações P1 a P4 (Ecossistema Integrado AUX CAD v2.5.0)
- **P1 - Conexão Direta Paleta OSM ➔ CQT (`tracado.js`, `MapaControl.xaml.cs`, `cqt_cad_extractor.lsp`, `cqt_excel_manager.py`)**:
  - Exportação e abertura instantânea da interface CQTUI via botões `⚡ CQT` (no traçado) e `⚡ CQTUI` (nas ações rápidas de consumidores BT).
  - **Abertura Não-Bloqueante**: Permite abrir a ferramenta para estudo prévio mesmo sem traçado prévio de 2 postes, exportando dados do formulário e de clientes.
  - **Launcher Resiliente com Launcher Python `py`**: Disparo via `cmd.exe /c start "" py ...` eliminando erros de permissão ("Acesso Negado" Win32Exception) causados por App Execution Aliases da Microsoft Store no Windows 11.
  - Sincronização em `%TEMP%` e `C:\Temp\auxcad_cqt_import.json`, permitindo também acionamento pelos comandos do AutoCAD **`CQTUI`**, **`CQT`** e **`CQT_OSM`**.
  - **Layout Ergonômico de Consumidores BT (CQT)**: Design em 3 células integradas com badges (1F Mono azul, 2F Bi âmbar, 3F Tri verde esmeralda destacado), controles de stepper (+ / -), totalizador dinâmico de clientes em tempo real, atalhos rápidos (`+1 Mono`, `+1 Bi`, `+1 Tri`, `Zerar`, `⚡ CQTUI`), sincronização com `localStorage` e eliminação completa de rolagem horizontal (`overflow-x: hidden`), adaptando-se com fluidez mesmo a paletas estreitas no AutoCAD.
- **P2 - Snap Magnético aos Postes e Nós da Rede (`snap_magnetico.js`)**:
  - Atração do cursor dentro de um raio de 18 pixels com suporte a postes do traçado, vértices da régua, postes importados do DWG e marcador principal.
  - Anel visual pulsante ciano (`.snap-magnetico-marker` com `@keyframes snapPulse`) e tooltip `🧲 P01`.
- **P3 - Hub Central & Launcher Unificado (`aux_cad_hub.py` & Atalhos da Raiz)**:
  - Launcher executivo moderno em Tkinter (`#0F172A`/`#1E293B`) com 10 cards interativos de 1 clique para todos os módulos (Unifilar, AutoPrancha, CQT, Orçamento, CPFC, Ambiental, Estúdio Web, Paleta OSM, Tabelas, QA).
  - Atalhos executáveis diretos de 2 cliques na raiz: `Abrir_AUXCAD.bat`, `Abrir_Unifilar.bat`, `Abrir_AutoPrancha.bat`, `Abrir_CQT.bat`, `Abrir_Orcamento.bat`, `Abrir_CPFC.bat`, `Abrir_Mapa_Postes.bat`.
  - Diagnóstico em tempo real (Python, AutoCAD `acad.exe`, compilação da DLL .NET e branch git).
  - Script de manutenção inteligente `clean.bat` limpando temporários do Windows, arquivos residuais do AutoCAD (`*.bak`, `*.dcl_tmp`, `*.tmp`) e caches Python (`__pycache__`, `.pytest_cache`, `.coverage`), preservando 100% dos dados.
- **P4 - Docker First & CI/CD (`Dockerfile`, `docker-compose.yml`, `.dockerignore`, `ci.yml`, `requirements.txt`)**:
  - Imagem Docker padronizada Python 3.12-slim para testes e execução local do servidor web.
  - Pipeline GitHub Actions com matriz Python 3.11 e 3.12 garantindo barreira de qualidade mínima de 80% de cobertura.
- **Validação & QA**: **149 testes unitários passando com 100% de sucesso** (`python -m pytest tests/`).

### 16. `documentos/` (Pranchas, Referências e Notas)
- `PRANCHA LIGHT.dwg` e `PRANCHA LIGHT.bak`: Templates de prancha oficial.
- `PLAN_MEDIÇÃO_ELETTRICA_PROJETOS_BASE(1).xlsx` & `Árvore de Dispositivos.xlsx`: Planilhas de medição e dispositivos.
- `anotações-2.one`: Caderno técnico de anotações.
- `Captura de tela 2026-01-29 174711.png`
- `Application does not support just-i.txt` & `Autodesk mudou o motor do AutoCAD r.txt`: Notas técnicas de suporte.

### 17. `prancha/` (AutoPrancha - Enquadramento Inteligente no ModelSpace - Padrão Enel / HBT)
- **Conceito & Contexto**: Atende ao fluxo de trabalho oficial da Enel e HBT Engenharia, onde pranchas com margens, bordas, marcas de dobra e carimbo oficial são posicionadas **diretamente no ModelSpace** em escala 1:1 métrica real ($1\text{ unidade} = 1\text{ metro}$).
- `autoprancha_core.py` (160 linhas): Motor analítico de enquadramento geométrico:
  - Mapeia formatos ABNT NBR 10068: A0 ($1189 \times 841$ mm), A1 ($841 \times 594$ mm), A2 ($594 \times 420$ mm), A3 ($420 \times 297$ mm), A4 ($297 \times 210$ mm).
  - Margens normativas: 25mm na margem esquerda e 10mm nas demais.
  - Reserva técnica do Carimbo Enel/HBT no canto inferior direito ($185 \times 60$ mm na folha).
  - Escalas normativas de distribuição: 1:500, 1:750, 1:1000, 1:1250, 1:1500 e 1:2000 (Fator: $\text{Escala}/1000.0$).
  - Algoritmo `calcular_enquadramento` com margem de respiro (10%) e prioridade para escala 1:1000 e formato A1 da concessionária.
- `autoprancha.lsp` (230 linhas): Rotina AutoLISP no AutoCAD:
  - Comandos: **`AUTOPRANCHA`** (atalhos: **`PRANCHA`**, **`ENQUADRAR`**, **`FOLHA`**) e **`RECARREGAR_PRANCHA`**.
  - Seleção por diagonal em 2 cliques com retângulo elástico dinâmico (`getcorner`).
  - Modos: **Auto**, **Escala** (fixa escala) ou **Formato** (fixa folha).
  - Desenho automático em camadas dedicadas: `A-PRANCHA` (corte externo), `A-PRANCHA-MARGEM` (margem interna ciano 0.50mm), `A-PRANCHA-DOBRA` (marcas de dobra 185/210mm) e `A-PRANCHA-CARIMBO`.
  - Inserção do Carimbo Técnico Enel/HBT preenchido no canto inferior direito.
  - Centralização geométrica sobre o centro da rede e zoom automático na folha inserida.
- **Cobertura & Testes**: `tests/test_autoprancha.py` com **10 testes unitários específicos (94% de cobertura)** e suíte global com **147 testes unitários passando com 100% de sucesso**.

### 18. `sob/` (Projeto Automação de Preparação de Projeto SOB - SharePoint & CAD)
- **Conceito & Contexto**: Automatiza o ciclo de preparação inicial de um projeto de distribuição a partir de uma SOB informada pelo usuário no AutoCAD, integrando o download de croquis do SharePoint da HBT/Enel com a geração do arquivo-base de desenho `BASE_SOB_DESENHO.dwg`.
- **Arquitetura Oficial: Divisão Estrita em FASE A (Pré-Validação) e FASE B (Criação e Execução) — Seção 17**:
  - **Princípio Fundamental de Atomicidade Não-Destrutiva**: Nenhuma criação de pasta (`SOB_ROOT`, `CROQUI_DIR`), cópia de DWG (`BASE_DWG`), download ou alteração de arquivos ocorre antes de a Fase A atingir `PRE_VALIDACAO = OK`. Se qualquer pré-condição falhar, nada é criado no disco.
  - **FASE A — PRÉ-VALIDAÇÃO (Etapas A01 a A15)**:
    - `A01`: Iniciar comando no AutoCAD (`SOB`, `NOVASOB`, `PREPARAR_SOB`), validar solução e ambiente.
    - `A02 & A03`: Solicitar SOB e normalizar para `SOB_ID` e `SOB_NAME`. Falha: `[FALHA] Número da SOB inválido.`.
    - `A04 & A05`: Selecionar e validar `DESTINATION_ROOT` via diálogo nativo Windows. Cancelamento: `[INFO] Operação cancelada pelo usuário.`.
    - `A06`: Derivação canônica dos caminhos (`SOB_ROOT`, `CROQUI_DIR`, `BASE_DWG`, `BASE_TEMPLATE`).
    - `A07`: Verificar conflito de `SOB_ROOT` pré-existente (`[FALHA] A pasta da SOB já existe.`). Não apaga/sobrescreve/mescla.
    - `A08`: Validar possibilidade e permissão de criação em `DESTINATION_ROOT` (`[FALHA] O diretório selecionado não permite a criação da estrutura da SOB.`).
    - `A09`: Validar existência, legibilidade e formato do `BASE_TEMPLATE` (`modelos/prancha.dwg`). Falha: `[FALHA] Arquivo-modelo prancha.dwg não encontrado ou inacessível.`.
    - `A10`: Validar disponibilidade de `BASE_DWG` (`[FALHA] O arquivo BASE_SOB_DESENHO.dwg já existe no destino.`).
    - `A11`: Validar credenciais no `.env` (`[FALHA] Credenciais do SharePoint não configuradas.`).
    - `A12`: Autenticar no SharePoint (`[FALHA] Não foi possível autenticar no SharePoint.`).
    - `A13`: Localizar SOB unívoca pelo `SOB_ID` puro (falhas: `[FALHA] SOB não encontrada.` ou `[FALHA] Foram encontradas múltiplas correspondências ambíguas.`).
    - `A14`: Validar conteúdo disponível para download no SharePoint (`[FALHA] O conteúdo da SOB não está disponível para download.`).
    - `A15`: Encerrar pré-validação (`PRE_VALIDACAO = OK`).
  - **FASE B — CRIAÇÃO E EXECUÇÃO (Etapas B01 a B11 - Somente após PRE_VALIDACAO = OK)**:
    - `B01 & B02`: Criar e validar fisicamente `SOB_ROOT` e `CROQUI_DIR` (falhas: `[FALHA] Não foi possível criar SOB_ROOT/CROQUI_DIR.`).
    - `B03 & B04`: Baixar conteúdo para `CROQUI_DIR` e validar fisicamente (sem temporários `.tmp`/`.crdownload` e sem arquivos vazios).
    - `B05, B06 & B07`: Copiar `BASE_TEMPLATE -> BASE_DWG`, validar integridade binária (tamanho > 0, cabeçalho `AC10`, hash SHA-256) e comprovar preservação do template original (`hash_antes == hash_depois`).
    - `B08`: Validar estrutura física final completa (`SOB_ROOT`, `CROQUI_DIR`, conteúdo, `BASE_DWG`, template preservado).
    - `B09 & B10`: Abrir exclusivamente `BASE_DWG` no AutoCAD e validar o caminho absoluto ativo `CURRENT_AUTOCAD_DWG == BASE_DWG` (`[OK] BASE_DWG correto aberto no AutoCAD.`).
    - `B11`: Validação final do checklist de 21 critérios para emitir `STATUS = CONCLUÍDO`.
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
  - **Princípio de Idempotência (19.1)**: Mesma combinação `SOB_ID + DESTINATION_ROOT` sempre produz estritamente os mesmos `SOB_NAME`, `SOB_ROOT`, `CROQUI_DIR` e `BASE_DWG`. Proibição absoluta de sufixos numéricos (`_1`, `_2`) ou timestamps (`_20260919`) para contornar conflitos.
  - **Classificação Rigorosa de Estados (19.2 e 19.5)**: Estados possíveis ao examinar `SOB_ROOT`:
    - `NÃO_EXISTE`: Pré-validação aprovada -> Iniciar nova execução limpa.
    - `EXISTE_E_NÃO_É_DA_EXECUÇÃO`: Pasta preexistente sem manifesto ou criada por terceiros -> Bloquear (`STATUS = BLOQUEADO`).
    - `EXISTE_E_ESTÁ_INCOMPLETA`: Execução anterior interrompida ou com rollback parcial -> Bloquear (`STATUS = BLOQUEADO`).
    - `EXISTE_E_ESTÁ_CONCLUÍDA`: Execução anterior `CONCLUÍDO` com arquivos íntegros -> Bloquear criação duplicada e informar `[INFO] A SOB já possui uma execução concluída neste destino.`.
    - `EXISTE_EM_ESTADO_INCONSISTENTE`: Divergência entre manifesto e arquivos em disco -> Bloquear (`STATUS = BLOQUEADO`).
  - **Não Confundir Existência com Conclusão (19.6)**: Presença de arquivos físicos isolada não atesta conclusão; exige validação do manifesto `.sob_state.json` e integridade física.
  - **Downloads e Cópia de Base Idempotentes (19.11 e 19.12)**: Comparação de hash/tamanho; arquivos idênticos são reutilizados/validados, divergências geram bloqueio imediato; templates originais permanecem intocados.
  - **Rastreabilidade por RUN_ID (19.14)**: Identificador técnico único por execução (`RUN_YYYYMMDD_HHMMSS_<hex>`) para rastrear etapas sem alterar caminhos canônicos em disco.
- `sob_core.py` (477 linhas):
  - Normalização e validação robusta da SOB (`obter_sob_id`, `obter_sob_name`, `validar_sob_name`, `derivar_caminhos_sob`).
  - Checagem não-destrutiva de permissão de escrita em diretórios (`validar_permissao_criacao` e `SobPermissionError`).
  - Hierarquia canônica unificada de exceções do domínio SOB (`SobConflictError`, `SobCancellationRequestedError`, `SobIntegrityError`, etc.).
  - Criação da estrutura canônica de diretórios (`SOB_ROOT` e subpasta `CROQUI`).
  - Cópia segura com conferência de hash SHA-256 e validação de cabeçalho DWG `AC10`.
  - Limpeza não-destrutiva em ordem inversa em `remover_estrutura_incompleta` sem uso de `rmtree` genérico.
- `sob_fallback_manual.py` (303 linhas):
  - Geração de URLs de busca contextualizada no SharePoint (`gerar_url_busca_sharepoint`).
  - Abertura no navegador e cópia atômica para área de transferência via `clip` (`abrir_busca_sharepoint_navegador`).
  - Validação estrita de downloads manuais (`validar_arquivos_manuais`), rejeitando 0 bytes, erros HTML e temporários.
  - Orquestração de intervenção manual (`executar_fallback_intervencao_manual`) com suporte a continuidade com arquivos manuais, continuidade sem croqui (`CROQUI = SEM_ARQUIVOS`) e cancelamento seguro.
- `sob_progress_gui.py` (637 linhas):
  - Interface gráfica Tkinter TTK com feedback em tempo real e barra de progresso (determinada/indeterminada).
  - Comunicação multithread desacoplada via `ProgressoObserver` impedindo congelamentos da UI.
  - Painel interativo de intervenção com botões `[ 🌐 Abrir SharePoint ]`, `[ 📁 Selecionar Pasta... ]`, `[ Continuar ]`, `[ Continuar sem Croqui ]` e `[ Cancelar ]`.
  - Exibição em tempo real da SOB e da Base no cabeçalho executivo (`SOB: {sob_id} | Base: {base}`).
  - Elevação e foco garantidos sobre o AutoCAD (`deiconify`, `lift`, `-topmost`), evitando congelamento da interface.
  - Botão de cancelamento responsivo disparando rollback seguro na Fase B.
- `sob_bases.py` (147 linhas):
  - Mapeamento, leitura dinâmica do FABAO (`C:\Users\jonat\OneDrive\Área de Trabalho\FABAO\Controle\gomnet_18-08-2022.xlsm`) e tabela de fallback com CECOs e polos Enel Rio (`PE`, `CF`, `AN`, `RE`, `NI`, `MA`, `SG`, `TE`).
  - Normalização de siglas e geração de nome canônico `{BASE}_{SOB}_DESENHO.dwg` (ex.: `PE_A057350816_DESENHO.dwg`).
- `sob_logger.py` (58 linhas):
  - Utilitários isolados de logging seguro (`LoggerSeguro`) com sanitização de segredos e formatação padrão de erros (`formatar_mensagem_erro`).
- `sob_cli.py` (88 linhas):
  - Ponto de entrada CLI desacoplado com parâmetro `--base` (default `"PE"`), suporte a flags `--no-ui` / `--headless` e emissão de arquivo JSON para intercâmbio com o AutoCAD.
- `sob_gomnet.py` (374 linhas):
  - Conector HTTP dedicado para o sistema corporativo GOMNET com sessão mantida (`ASP.NET_SessionId`).
  - Consulta ao modal de anexos via `Upload.aspx?numsob={SOB_ID}` e extração de metadados em `gridviewUploads`.
  - Descarte seguro do ícone de interface `/imagens/anexarArquivo.gif`.
  - Download em lote atômico e idempotente para `CROQUI\ANEXOS` (`baixar_anexos_gomnet_fase_b`).
- `sob_idempotencia.py` (173 linhas):
  - Gestão de estado e integridade para repetição segura.
  - Funções: `gerar_run_id`, `gravar_manifesto_execucao`, `ler_manifesto_execucao`, `classificar_sob_root`, `verificar_arquivo_download_idempotente`.
- `sob_rollback.py` (425 linhas):
  - Classes `RecursoRastreado`, `RecursoRemanescente` e `RollbackContext`.
  - Rastreamento fino de recursos SharePoint, GOMNET (`gomnet_created_files`), pasta `ANEXOS_DIR` e DWG aberto no CAD.
  - Execução sequencial reversa, validação pós-rollback e relatório de integridade.
- `sob_sharepoint.py` (637 linhas):
  - Carregamento seguro e isolado de credenciais do `.env` (`SHAREPOINT_ID`, `SHAREPOINT_SENHA` e opcional `SHAREPOINT_URL`) com `dotenv_values` e parser resiliente sem vazamento para `os.environ`.
  - URL Canônica Padrão configurada para a pasta compartilhada de **Levantamentos de campo**: `https://hbtengenharia1.sharepoint.com/:f:/s/HBT-EnelRJ-Sul/IgALh51uFX0fRovCUeVsprYWAWYGyn7GwehC6BrYpg9KcFc?e=ltJeMr`.
  - Navegação e autenticação Microsoft Online com Edge/Chrome headless via Selenium (`SharePointClient`).
  - Localização precisa da pasta da SOB na pasta de levantamentos de campo, com busca filtrada e detecção de ambiguidade (`SobConflictError`).
  - Download da **pasta inteira** da SOB via seleção de checkbox/menu de ações no SharePoint (baixada em formato `.zip`), com descompactação atômica, nivelamento de subpasta raiz para `CROQUI_DIR` e validação recursiva de integridade física.
- `sob_manager.py` (747 linhas - estritamente abaixo do soft limit de 750 linhas):
  - Orquestrador com execução dividida em Fase A (Pré-Validação Não-Destrutiva) e Fase B (Criação e Execução).
  - Suporte a parâmetro de base, propagando para `derivar_caminhos_sob`.
  - Integração do fallback manual de múltiplas ocorrências: paralisação antes da criação de `SOB_ROOT` e condução da intervenção.
  - **Regra Fundamental de Estrutura Independente do Croqui e Nomenclatura Dinâmica**:
    A criação da estrutura local e a obtenção do croqui são operações distintas. Seja por download automático, manual ou dispensa (`CROQUI = SEM_ARQUIVOS`), a Fase B obrigatoriamente cria `SOB_ROOT\CROQUI\`, copia `BASE_TEMPLATE` para `{BASE}_{SOB}_DESENHO.dwg` (ex.: `PE_A057350816_DESENHO.dwg`), valida o DWG e abre no AutoCAD.
  - Checklist operacional completo para determinar `CONCLUÍDO` vs `BLOQUEADO`.
- `sob_cad_launcher.lsp` (409 linhas):
  - Rotina AutoLISP com comandos **`SOB`**, **`NOVASOB`**, **`PREPARAR_SOB`** e **`RECARREGAR_SOB`**.
  - Prompt da Base (`(getstring "\nInforme a Base (PE/CF/AN/RE/NI/MA/SG/TE) <PE>: ")`).
  - Derivação dinâmica de `{baseSigla}_{sobId}_DESENHO.dwg` e fallback com `(vl-directory-files sobRoot "*_DESENHO.dwg" 1)`.
  - Inicialização estrita de `croquiDir` e blindagem completa contra valores `nil` em chamadas `strcat`.
  - Resolução robusta de caminho em `sob-localizar-lsp` e comando `RECARREGAR_SOB` para recarregar sem reiniciar o CAD.
  - Função operacional `(sob-executar-fluxo sobInput destPath abrirCad baseInput)` com verificação estrita de abertura de DWG (`CURRENT_AUTOCAD_DWG == BASE_DWG`).
  - Apresentação no console e em diálogo do status de rollback e idempotência.
- `sob_launcher_gui.py` (282 linhas):
  - Interface gráfica interativa para preparação autônoma de projetos SOB via Windows Explorer (`Abrir_SOB.bat`) ou através do Hub Central (`aux_cad_hub.py`).
  - Seleção visual de SOB, Base técnica (combobox Enel Rio/FABAO) e pasta de destino.
- **Cobertura & Testes**:
  - **288 testes unitários e de integração com 100% de aprovação (PASS)** em todo o projeto.
  - **81% de cobertura global no módulo SOB** e **80% no módulo CQT**.
  - **Suíte global de não-regressão**: 100% dos testes passando sem falhas.
  - **Bateria de testes operacionais no AutoCAD 2026 Core Console**: **PASS** em todos os cenários (AUTOCAD-01 a AUTOCAD-06).

---

## Memória de Sessão Consolidada - OSMPALETA (2026-09-23)

- Problema inicial: vias OSM não apareciam no AutoCAD ao inserir postes.
- Hipótese de fuso/UTM/Snyder foi descartada; conversões e zona 23S permaneceram coerentes.
- Falha inicial de aquisição: OSM/Overpass retornaram 429/timeout; faltavam User-Agent, deduplicação in-flight e política específica de 429.
- Correção mantida em `vias_obstrucoes.js`: request key por BBOX, compartilhamento de promises, classificação, retry limitado, `Retry-After` e fallback controlado.
- Correção mantida em `MapaControl.xaml.cs`: User-Agent `OSMPALETA (CAD interno)` no WebView2.
- Consulta real comprovada: HTTP 200, 872 elementos, 91 ways, 595 nodes, 35 vias, 22 calçadas, 13 obstruções e 417 vértices.
- Payload real comprovado: 35 vias, 22 calçadas, 13 obstruções e 417 vértices.
- Payload CAD real observado: 6 vias, 1 calçada, 0 obstruções, 65 vértices e 31 polylines; não confundir com o self-test artificial.
- AutoCAD .NET comprovado internamente: `MdiActiveDocument=TESTE_POSTE_E_VIAS.dwg`, Database/ModelSpace/Transaction OK e delta de entidades 1.
- Fluxo interno do OSMPALETA: AutoCAD .NET + `PaletteSet` + WPF + WebView2 + `WebMessageReceived`; COM/ActiveX não fazem parte dele.
- Lifecycle WebView2: `Loaded` -> `CreateAsync` -> `EnsureCoreWebView2Async` -> registro do evento -> `Navigate`. O comando de self-test podia executar antes do lifecycle assíncrono terminar.
- `CoreWebView2=NULL` no self-test não provou quebra; classificação final: W2, self-test antecipado.
- O payload CAD real veio de `converterEEnviarParaCad` -> `window.chrome.webview.postMessage` -> `MapaControl` -> `CadBridge`.
- Instrumentações/comandos temporários foram removidos; não permaneceram `OSMPALETA_SELFTEST` ou `OSMPALETA_WEBTEST`.
- Validação final: builds Release `net8.0-windows`/`net48`, syntax checks JS e `16 passed` em `tests/test_mapa_paleta.py`.
- Regra futura: aguardar lifecycle normal do WebView2 antes de testar `CoreWebView2`; não usar delays arbitrários, COM ou workarounds.
- Homologação final: `MapaControl` agora compartilha uma única `_initializationTask`; readiness só conclui após `EnsureCoreWebView2Async`, registro do handler e `NavigationCompleted` bem-sucedido.
- `BtnRecarregar_Click` e `EnviarMensagemWeb` aguardam a task com `async/await`; erros são propagados/tratados, sem `Sleep`, `.Wait()`, `.Result` ou retry artificial.
- Validação após a correção: builds `net48`/`net8.0-windows` aprovados, `node --check` aprovado e `16 passed`.
- Correção P2 (2026-09-23): eliminada chamada redundante de `carregarContextoUrbano` para o novo poste em `tracado.js` (raio 120m), mantendo `app.js` como único responsável pelo poste (140m) e preservando a consulta do vão (`midLat, midLon`, `raioVao`) em `tracado.js`. Testes atualizados para 17 passed (100%).

---

## Memória de Sessão Consolidada - Auditoria Técnica Integral da Raiz (2026-09-23)

- **Escopo**: 100% da pasta raiz `aux cad` (445 arquivos, 13 módulos funcionais, 102 comandos AutoLISP, 5 comandos C# .NET).
- **Inventário**: Todos os diretórios, comandos `c:...`, métodos `[CommandMethod]`, entry points de Python e interfaces gráficas catalogados.
- **AutoLISP**: 30 arquivos `.lsp` auditados; 100% com parênteses e sintaxe balanceados (0 erros sintáticos).
- **JavaScript**: Todos os scripts auditados com `node --check` (100% PASS).
- **.NET / C#**: `dotnet build mapa_cad_paleta/MapaCadPaleta.csproj -c Release` aprovado para ambos os targets (`net48` e `net8.0-windows`).
- **Problema P1 Comprovado e Corrigido**:
  - `sob/sob_fallback_manual.py:245`: `SobNotFoundError` importado indevidamente de `sob_core` (que não o define) em vez de `sob_sharepoint`. Corrigido cirurgicamente. Prefixo padronizado para `[FALHA]`.
- **Testes**: Suíte global com **296 passed, 2 skipped** (100% dos testes executáveis aprovados com sucesso).
- **Status Geral**: **HOMOLOGÁVEL**.

---

## Memória de Sessão Consolidada - Validação Operacional Final (2026-09-24)

- **GOMNET (Fases A e B)**: **100% PASS OPERACIONAL**:
  - Conectividade comprovada ao host `gomnet-rj.enelint.global:80` (IP `10.152.152.109`).
  - Autenticação real via POST em `login.aspx` com sucesso em 1.15s; cookie `ASP.NET_SessionId` capturado e mantido.
  - Consulta real de SOB no `Upload.aspx`: SOB `A057349839` retornou 4 anexos em 0.97s; SOB `A057219996` retornou 9 anexos em 0.75s.
  - Download atômico real validado: arquivo `CHECKLIST_A057349839.xlsx` (18.777 bytes baixados em 0.24s, magic bytes `504B0304` `PK\x03\x04` confirmados).
  - Idempotência real comprovada: segunda execução para o mesmo diretório detectou arquivo idêntico e realizou 0 downloads adicionais.
  - Falhas controladas: credencial inválida gerou `GomnetAuthError` seguro sem expor senhas; SOB inexistente retornou lista vazia de anexos.
- **SGT Caminho Elétrico (`unifilar/arvore_client.py`)**: Host `sgt.rio.e-corpnet.org:80` (IP `10.152.152.162`) acessado; resposta HTTP 401 tratada graciosa e resilientemente, acionando o fallback automático para a base SQLite local (`arvore_cache.sqlite3`), retornando a proteção a montante de `SG40995` (`Chave Fusivel - SG59356`, 80 clientes, 150 kVA) em 0.26s (**VALIDADO COM FALLBACK OPERACIONAL**).
- **AutoCAD Físico (`accoreconsole.exe` 2026 Core Console)**: `acaddoc.lsp` executado com sucesso; comandos `CQTCAD`, `SOB`, `AUTOPRANCHA`, `UNIFILAR`, `KMZCHECK`, `ORCAMENTO`, `CPFC` confirmados carregados (`SIM`); inserção real de polyline fechada no ModelSpace validada (`1 entidade`) com saída limpa (**PASS OPERACIONAL**).
- **Suíte de Testes Automatizados**: **296 passed, 2 skipped** (100% dos testes executáveis aprovados com sucesso).
- **Status Geral Final**: **HOMOLOGADO**.

---

## Memória de Sessão - Correção de Permissão e Destino de Arquivos no Módulo Ambiental (2026-09-24)

- **Incidente**: `[Errno 13] Permission denied: 'C:\\Windows\\System32\\CHECKLIST_A057383730.xlsx'` ao gerar Checklist Ambiental no comando `KMZCHECK`.
- **Causa Raiz**:
  - `kmz_point_layer_report.lsp`: quando `docx_template` não existia no drive `G:`, atribuía `""`. O AutoCAD disparava `(startapp "cmd.exe" ...)` sem definir diretório de trabalho, herdando `C:\Windows\System32`.
  - `memorial_ambiental_generator.py`: `os.path.dirname("")` retornava `""`, que caía em `out_dir = os.getcwd()` (`C:\Windows\System32`). A tentativa de criar o arquivo Excel disparava `PermissionError` devido ao UAC do Windows.
- **Solução Implementada**:
  1. `kmz_point_layer_report.lsp`: obtém `(getvar "DWGPREFIX")`, normaliza via `vl-string-right-trim`, define `cd /d "<dwg_dir>"` e repassa como 5º argumento CLI.
  2. `memorial_ambiental_generator.py`:
     - Implementadas funções `is_safe_writable_dir(path)` e `determinar_pasta_saida(candidate, template_path)`.
     - Rejeição estrita a diretórios do sistema (`Windows`, `System32`, `Program Files`, etc.).
     - Campo visual na GUI "📁 Pasta de Destino (Salvar):" com botão `Procurar...` (`filedialog.askdirectory`).
     - Tratamento de concorrência/lock de arquivos: se o arquivo já estiver aberto no Microsoft Excel, salva automaticamente com sufixo de timestamp (`CHECKLIST_{SOB}_{HHMMSS}.xlsx`), alertando o usuário sem travar o processo.
  3. `tests/test_checklist_ambiental.py`: novos testes `test_is_safe_writable_dir` e `test_determinar_pasta_saida`.
- **Validação**: 6/6 testes em `test_checklist_ambiental.py` e 300 testes na suíte global (296 PASS, 0 FAIL, 4 SKIP).

---

## Memória de Sessão - Institucionalização do Versionamento Oficial (v0.9.0) (2026-09-24)

- **Versão Oficial**: `0.9.0` (SemVer: `MAJOR.MINOR.PATCH`).
- **Artefatos Oficiais de Versionamento Criados**:
  - `VERSION`: Arquivo na raiz do projeto com o conteúdo estrito `0.9.0`, estabelecido como **fonte oficial única de verdade**.
  - `CHANGELOG.md`: Registro histórico oficial baseado em Keep a Changelog.
  - `mapa_cad_paleta/MapaCadPaleta.csproj`: Integradas as propriedades MSBuild `<Version>0.9.0</Version>`, `<AssemblyVersion>0.9.0.0</AssemblyVersion>`, `<FileVersion>0.9.0.0</FileVersion>` e `<InformationalVersion>0.9.0</InformationalVersion>`, propagando o versionamento para ambos os targets `.NET` (`net48` e `net8.0-windows`).
- **Política de Versionamento e Releases Documentada**:
  - Semantic Versioning: `PATCH` para correções/ajustes; `MINOR` para novos recursos/comandos compatíveis; `MAJOR` para quebras de compatibilidade ou alterações estruturais.
  - Padrão de Commits: Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `build:`, `chore:`, `perf:`).
  - Ciclo de Releases: branch `dev` $\rightarrow$ validação $\rightarrow$ atualização de `VERSION` e `CHANGELOG.md` $\rightarrow$ commit de release $\rightarrow$ tag `vX.Y.Z`.
- **Validações Executadas**:
  - `pytest`: 300 testes coletados (297 PASS, 3 SKIP, 0 FAIL).
  - .NET Build: Release `net48` e `net8.0-windows` aprovados com 0 erros.
  - JavaScript: 43 arquivos com `node --check` (0 erros).
  ## Memória de Sessão - Núcleo Funcional do Workspace da SOB/Projeto (2026-09-24)

- **Objetivo**: Desenvolver o primeiro núcleo funcional do Workspace da SOB/Projeto como camada de coordenação e detecção central de contexto.
- **Componentes Implementados**:
  - `workspace/workspace_core.py`: Domínio com `ProjectWorkspace`, `ProjectArtifact` e enum `ArtifactStatus` (`EXISTE`, `NAO_EXISTE`, `NAO_APLICAVEL`).
  - `workspace/workspace_scanner.py`: Scanner analítico não-destrutivo para detecção de DWG (`{BASE}_{SOB}_DESENHO.dwg`), pasta de croqui de campo (`CROQUI/`), documentos/anexos (`CROQUI/ANEXOS/`, `DOCUMENTOS/`), ambiental (`CHECKLIST_{SOB}.xlsx`, `MEMORIAL_DESCRITIVO_{SOB}.docx`, `CROQUI_AMBIENTAL_{SOB}.png`), `CQT_{SOB}.xlsm`, `ORCAMENTO_{SOB}.xlsx`, `CPFC_{SOB}.xlsx` e `UNIFILAR_{SOB}.json`.
  - `workspace/workspace_cli.py`: CLI formatada em pt-BR e interface visual desktop Tkinter (`WorkspaceGUI`) com botão de navegação, atualização e abertura direta no Explorer.
  - `workspace/workspace_cad.lsp`: Comandos do AutoCAD **`WORKSPACE`** e **`SOBWORKSPACE`** acionando o contexto do DWG ativo (`DWGPREFIX`).
  - `Abrir_Workspace.bat`: Atalho executável de 2 cliques na raiz.
  - `tests/test_workspace.py`: 16 testes unitários cobrindo inicialização, identificação de SOB, detecção física, múltiplos candidatos, ausência de artefatos, diretório inexistente, determinismo e CLI.
  ## Memória de Sessão - Camada de Ações do Workspace da SOB (2026-09-24)

- **Objetivo**: Implementar a primeira camada de ações (v1) do Workspace da SOB/Projeto sem duplicar lógicas de negócio dos módulos especializados.
- **Componentes Implementados**:
  - `workspace/workspace_actions.py`: Implementação do `WorkspaceActionDispatcher` com métodos estáticos para:
    - `abrir_artefato`: Abertura não-bloqueante no aplicativo padrão via `os.startfile` (arquivo/diretório).
    - `localizar_artefato`: Abertura no Windows Explorer com seleção (`explorer.exe /select,"<caminho>"`) ou abertura de pasta.
    - `montar_comando_cqt` / `executar_cqt`: Derivação contextual de destino (`CQT_{SOB}.xlsm` ou planilha existente) e disparo desacoplado de `cqt/cqt_excel_manager.py`.
    - `montar_comando_orcamento` / `executar_orcamento`: Passagem de `--projeto <SOB>` e `--json` (quando detectado) para `orcamento/orcamento_manager.py`.
    - `montar_comando_cpfc` / `executar_cpfc`: Passagem de `root_dir` e `sob_id` para `cpfc/cpfc_manager.py`.
  - `workspace/__init__.py`: Exportação oficial de `WorkspaceActionDispatcher`.
  - `tests/test_workspace_actions.py`: 25 testes unitários dedicados cobrindo 99% do código de ações, incluindo mocks de `os.startfile`, `subprocess.Popen`, fallbacks e tratamento de exceções.
  ## Memória de Sessão - Integração Visual Workspace Actions v1 (2026-09-24)

- **Objetivo**: Integrar visualmente a `WorkspaceGUI` em `workspace/workspace_cli.py` ao `WorkspaceActionDispatcher`, eliminando a lacuna entre apresentação e despacho de ações.
- **Componentes Conectados**:
  - `workspace/workspace_cli.py`:
    - Adicionado seletor de artefato via `_get_selected_artifact()` utilizando o `iid` da Treeview sincronizado ao `ProjectArtifact`.
    - Botão **"📂 Abrir"** e atalho de duplo clique (`<Double-1>`) disparando `_on_abrir_artefato()`.
    - Botão **"🔍 Localizar"** disparando `_on_localizar_artefato()` via Explorer.
    - Botões lançadores de módulos especialistas: **"⚡ CQT"**, **"📊 Orçamento"** e **"📐 CPFC"** disparando `WorkspaceActionDispatcher.executar_*`.
    - Botão **"📁 Pasta SOB"** redirecionado para `WorkspaceActionDispatcher.localizar_artefato()`.
  - `tests/test_workspace_cli_actions.py`: 17 novos testes unitários cobrindo seleção, avisos de não-seleção, artefatos inexistentes, despacho de ações e tratamento de exceções.
- **Validações Consolidadas**:
  - `pytest`: 358 testes coletados (**356 PASS**, 2 SKIP, 0 FAIL) em toda a suíte.
  - Cobertura do pacote `workspace`: 88% no total (99% em `workspace_actions.py`, 89% em `workspace_cli.py`, 95% em `workspace_core.py`, 80% em `workspace_scanner.py`).
  - Preservação estrita: Zero alterações em módulos especialistas e sem commits/tags.

## Memória de Sessão - SOB: Tratamento Resiliente de Erro no GOMNET (2026-09-26)

- **Regra de Negócio Implementada**: Erro ao acessar o GOMNET (seja na autenticação/consulta da Fase A ou no download de anexos na Fase B) **não pode ser motivo de rollback automático**.
- **Comportamento Interativo**:
  - O sistema pergunta expressamente ao usuário se deseja **continuar sem o fluxo do GOMNET** ou **fazer rollback**.
  - **Continuar sem GOMNET**: O fluxo prossegue normalmente, copiando o arquivo base DWG, validando a estrutura do projeto e concluindo a preparação da SOB com status `CONCLUÍDO` / `SUCESSO`, sem reversão de pastas/arquivos criados.
  - **Fazer Rollback**: O processo é interrompido e a reversão atômica dos recursos (`RollbackContext`) é executada, marcando o resultado como `BLOQUEADO`.
- **Componentes Atualizados**:
  - `sob/sob_manager.py`:
    - Adicionado método `_perguntar_decisao_gomnet(erro, callback_progresso, etapa, continuar_em_falha)`.
    - Adicionado parâmetro opcional `continuar_sem_gomnet_em_falha` em `SobOrchestrator.executar`.
    - Envolvimento seguro em blocos `try/except` nas etapas `A14-G` (pré-validação) e `B04-G` (download).
  - `sob/sob_progress_gui.py`:
    - `ProgressoObserver`: Adicionado método `perguntar_continuar_sem_gomnet(dados)` com notificação de evento `INTERVENCAO_GOMNET`.
    - `SobProgressGUI`: Implementado tratamento para `INTERVENCAO_GOMNET` disparando diálogo modal `messagebox.askyesno(..., title="GOMNET - Continuar ou Rollback?")` no thread da interface Tkinter.
  - `tests/test_sob_gomnet.py` e `tests/test_sob_progress_gui.py`:
    - Testes unitários para continuidade sem GOMNET na Fase A e Fase B, escolha de rollback e integração com Observer/GUI.
- **Validação**: Suíte completa executada com 438 testes coletados (434 PASS, 4 SKIP, 0 FAIL).

## Memória de Sessão - SOB: Busca Prioritária de Croqui no SharePoint ("Levantamentos de campo") (2026-09-26)

- **Objetivo**: Aprimorar o mecanismo de localização de croqui do módulo `sob/` adicionando uma busca prioritária na pasta `Levantamentos de campo` do SharePoint (`https://hbtengenharia1.sharepoint.com/:f:/s/HBT-EnelRJ-Sul/IgALh51uFX0fRovCUeVsprYWAWYGyn7GwehC6BrYpg9KcFc?e=lqKnT7`), mantendo o mecanismo existente como fallback integral.
- **Regra de Execução**:
  1. `SOB informada` $\rightarrow$ `Autenticação SharePoint` (reutilizada sem duplicar sessão ou credenciais).
  2. `BUSCA PRIORITÁRIA`: Acessa a pasta `Levantamentos de campo`, normaliza a SOB e varre o DOM procurando linhas/links correspondentes com validação rigorosa (`_item_eh_croqui_valido`, descartando arquivos temporários `~$`, `.tmp`, scripts, executáveis e requerendo extensão permitida).
  3. `Avaliação de Resultado`:
     - Se encontrar um único croqui válido: retorna imediatamente e continua o fluxo normal (download/validação existente).
     - Se encontrar múltiplos candidatos ambíguos: levanta `SobConflictError` com as ocorrências e URL de busca, preservando a intervenção de conflito existente.
     - Se não encontrar nenhum croqui válido ou ocorrer erro não-fatal na pasta prioritária: aciona o `FALLBACK ATUAL` (busca geral existente no SharePoint via input de busca).
     - Se ocorrer erro de autenticação (`SobAuthenticationError`): não mascara como falso "não encontrado" e propaga imediatamente.
- **Componentes Alterados**:
  - `sob/sob_sharepoint.py`:
    - Adicionada constante `URL_LEVANTAMENTOS_CAMPO` e configurada como `SHAREPOINT_URL_PADRAO`.
    - Adicionado suporte a `logger` opcional no cliente SharePoint e método `_log`.
    - Implementado `_item_eh_croqui_valido(nome_item, codigo_busca)`.
    - Implementado `buscar_em_levantamentos_campo(sob_codigo)`.
    - Extraído `localizar_pasta_sob_existente(sob_codigo)` para encapsular o fallback.
    - Orquestrado `localizar_pasta_sob(sob_codigo)` encadeando Busca Prioritária $\rightarrow$ Fallback Existente.
  - `sob/sob_manager.py`: Propagação do `logger` da SOB para `SharePointClient`.
  - `tests/test_sob_sharepoint.py`: 7 novos testes dedicados cobrindo os casos de sucesso na pasta prioritária, zero resultados com fallback, resultados inválidos com fallback, múltiplos resultados em conflito, erro não-fatal com fallback, propagação estrita de erro de autenticação e normalização da SOB.
- **Validações Consolidadas**:
  - 35 testes em `test_sob_sharepoint.py` (100% PASS).
  - 150 testes no módulo SOB (100% PASS).
  - Suíte completa: 449 testes coletados (445 PASS, 4 SKIP, 0 FAIL, 0 ERROR).

## Memória de Sessão - Implementação da Casca do OXCAD V1 (AutoCAD .NET / WPF) (2026-09-26)

- **Objetivo**: Implementar a fundação da interface integrada ao AutoCAD denominada **OXCAD** (Paleta nativa .NET `PaletteSet` + WPF `UserControl`), provendo identificação e apresentação do contexto básico do DWG ativo (DWG, pasta, SOB, status) e botão manual `[Atualizar]`, sem afetar o motor existente e sem duplicar lógicas de negócio.
- **Componentes Implementados em `oxcad/`**:
  - `oxcad/OxCadPaleta.csproj`: Multi-targeting para `.NET 8.0` (`net8.0-windows` para AutoCAD 2025/2026) e `.NET Framework 4.8` (`net48` para AutoCAD 2018-2024 via NuGet `AutoCAD.NET 24.3.0`).
  - `oxcad/DwgContext.cs`: Modelo de dados `DwgContextInfo` e serviço `DwgContextExtractor` com regex de extração de SOB (`SOB_...`, `{BASE}_{SOB}_DESENHO` e alfanumérico padrão), tratando DWG não salvo de forma segura sem lançar exceções.
  - `oxcad/OxCadControl.xaml` & `oxcad/OxCadControl.xaml.cs`: Interface WPF técnica e limpa (100% pt-BR) com cartões para Status, SOB, DWG e Pasta, e botão `[🔄 Atualizar Contexto]`.
  - `oxcad/PaletteHost.cs`: Singleton gerenciador da `PaletteSet` com GUID estável e exclusivo (`8A4F1D9C-2B7E-4E6A-B35D-9F0A1C8E7B2D`), estilo com auto-hide, close button, dock lateral à direita e sem duplicação de instâncias.
  - `oxcad/Plugin.cs`: Ponto de entrada `IExtensionApplication` registrando os comandos nativos `OXCAD`, `FECHAR_OXCAD` e `RECARREGAR_OXCAD`. O comando nativo conflitante `WORKSPACE` foi preservado intacto.
  - `oxcad/oxcad_loader.lsp`: Loader AutoLISP dinâmico com detecção da versão do AutoCAD (`ACADVER`), resolução relativa de caminhos sem hardcode de máquina/OneDrive e injeção via `_.NETLOAD`.
- **Validações Consolidadas**:
  - Compilação: Build aprovado com código 0 em Release para `net8.0-windows` e `net48`.
  - Testes: 13 novos testes em `tests/test_oxcad_casca.py` (100% PASS).
  - Suíte de regressão global: 488 testes coletados (**484 PASS**, 4 SKIP, 0 FAIL, 0 ERROR).
  - Integridade: `modelos/prancha.dwg` e `modelos/cqt_modelo.xlsm` com hashes SHA-256 inalterados.

## Memória de Sessão - OXCAD 0.2.0: Integração do Contexto Operacional (2026-09-26)

- **Objetivo**: Conectar a paleta nativa OXCAD ao contexto operacional real do projeto (`ProjectWorkspace` e `WorkspaceScanner`), apresentando metadados de localização (Município, Bairro, Endereço), detecção de divergência (DWG × Workspace) e matriz em tempo real dos 10 principais artefatos de engenharia, sem duplicar regras de negócio em C# e sem dependência do Tkinter.
- **Componentes Implementados**:
  - `workspace/workspace_context_cli.py`: Interface headless pura (zero Tkinter), recebendo `--dwg` ou `--dir`, invocando `WorkspaceScanner.scan()`, avaliando divergências entre o DWG ativo e a pasta da SOB, recuperando metadados locais de manifesto e emitindo estritamente o contrato JSON padronizado (`OxCadWorkspaceContext`).
  - `oxcad/WorkspaceService.cs`: Camada C# de integração subprocessada com ciclo estrito (iniciar -> consultar -> retornar JSON -> encerrar), localização determinística do Python, timeout defensivo e desserialização via `System.Text.Json`.
  - `oxcad/OxCadControl.xaml` & `oxcad/OxCadControl.xaml.cs`: Interface WPF atualizada com cartões para Município, Bairro e Endereço, banner condicional para `⚠ Inconsistência de contexto`, matriz visual dos artefatos monitorados com ícones (`✓` / `○`) e controle atômico de concorrência (`_isUpdating`) no botão `[🔄 Atualizar Contexto]`.
  - `oxcad/OxCadPaleta.csproj`: Versionamento atualizado para `0.2.0` com dependência estável do `System.Text.Json` para `net48`.
  - `tests/test_oxcad_context_integration.py`: 13 novos testes unitários cobrindo contexto válido, SOB inexistente, diretório inexistente, conformidade JSON, timeout, concorrência, detecção de divergência e ausência de Tkinter/OneDrive.
- **Validações Consolidadas**:
  - .NET Build: Compilação Release com 0 erros para ambos os targets (`net8.0-windows` e `net48`).
  - Testes específicos do OXCAD: 26 testes coletados (**26 PASS**, 100% de aprovação).
  - Suíte de regressão global: 501 testes coletados (**499 PASS**, 2 SKIP, 0 FAIL, 0 ERROR).
  - Modelos Oficiais: Hashes SHA-256 de `modelos/prancha.dwg` e `modelos/cqt_modelo.xlsm` rigorosamente inalterados.

## Memória de Sessão - OXCAD 0.3.0: Integração de Execução via WorkspaceActionDispatcher (2026-09-26)

- **Objetivo**: Conectar a paleta nativa OXCAD ao motor de execução oficial do projeto (`WorkspaceActionDispatcher`), transformando-a de interface passiva em centro operacional capaz de despachar ações para os módulos especialistas sem duplicar lógicas em C# e sem bloquear a thread do AutoCAD.
- **Componentes Implementados**:
  - `workspace/workspace_context_cli.py`: Adicionado suporte aos parâmetros `--acao` e `--alvo`. Função `executar_acao_operacional` mapeando o despacho de CQT, Orçamento, CPFC, Ambiental, AutoPrancha, Preparar SOB, Abertura de artefatos e Localização no Explorer diretamente para o `WorkspaceActionDispatcher`. Tratamento seguro para Unifilar sinalizando `Requer especificação` com orientação de comandos nativos do CAD (`UNIFILAR` / `PROTECAO`).
  - `oxcad/WorkspaceService.cs`: Adicionado método `ExecutarAcaoAsync(acao, dwgFullPath, alvo)` executando chamadas assíncronas em processos externos não-bloqueantes com controle de tempo limite e serialização JSON via `OxCadActionResult`.
  - `oxcad/OxCadControl.xaml` & `oxcad/OxCadControl.xaml.cs`: Interface WPF atualizada com painel de Ações de Engenharia (`⚡ CQT`, `📊 Orçamento`, `📐 CPFC`, `🌿 Ambiental`, `📐 AutoPrancha`, `📁 Preparar SOB`), botões contextuais `📂 Abrir` na matriz de artefatos, badge de interação no CAD para Unifilar, barra de estado de execução (`Pronto`, `Executando...`, `Concluído`, `Falhou`, `Requer especificação`), controle estrito de concorrência (`_isActionRunning`) e auto-refresh pós-execução.
  - `oxcad/OxCadPaleta.csproj`: Versionamento oficial atualizado para `0.3.0`.
  - `tests/test_oxcad_actions_integration.py`: 13 novos testes unitários cobrindo o despacho de todas as ações, mock de subprocessos, validação de Unifilar, abertura de artefatos existentes/inexistentes e execução via CLI.
- **Validações Consolidadas**:
  - .NET Build: Compilação Release com 0 erros para ambos os targets (`net8.0-windows` e `net48`).
  - Testes específicos do OXCAD: 39 testes coletados (**39 PASS**, 100% de aprovação).
  - Suíte de regressão global: 514 testes coletados (**512 PASS**, 2 SKIP, 0 FAIL, 0 ERROR).
  - Modelos Oficiais: Hashes SHA-256 de `modelos/prancha.dwg` e `modelos/cqt_modelo.xlsm` rigorosamente inalterados.

## Memória de Sessão - OXCAD 0.4.0: Homologação Operacional, Endurecimento e Resiliência (2026-09-26)

- **Objetivo**: Elevar a robustez e resiliência da integração AutoCAD (`.NET/WPF`) com o backend Python do Workspace, eliminando vulnerabilidades de processos zumbis, ruídos em stdout (warnings externos), caminhos com caracteres especiais, ausência de executável Python no PATH e variabilidade de caminhos de assembly.
- **Componentes Endurecidos**:
  - `oxcad/WorkspaceService.cs`:
    - `ExtrairJsonValido(saida)`: Extração resiliente entre o primeiro `{` e último `}`, descartando quaisquer logs/warnings externos antes da desserialização.
    - `EncerrarProcessoETodosOsFilhos(proc)`: Gestão atômica de processos via `taskkill /F /T /PID` no Windows e `proc.Kill()`, impedindo subprocessos zumbis após timeout.
    - `ObterDiretorioRaizProjeto(dwgFullPath)`: Resolução em cascata (`AUXCAD_ROOT` $\rightarrow$ assembly location $\rightarrow$ dwg parent $\rightarrow$ current dir).
    - `ObterExecutavelPython()`: Detecção determinística expandida para `PYTHON_EXECUTABLE`, AppData WindowsApps/Python e pastas padrão `C:\Python3*`.
    - Captura específica de `System.ComponentModel.Win32Exception` com diagnóstico amigável para o usuário.
    - `ObterTimeoutMilissegundos()`: Suporte a `OXCAD_TIMEOUT_MS`.
  - `workspace/workspace_context_cli.py`:
    - Adicionada supressão global de warnings de pacotes terceiros (`warnings.filterwarnings("ignore")`).
  - `oxcad/OxCadPaleta.csproj` & `oxcad/OxCadControl.xaml`:
    - Versionamento oficial elevado para `0.4.0` de forma consistente em ambos os arquivos.
  - `tests/test_oxcad_hardening.py`:
    - 6 novos testes unitários e de integração cobrindo versão 0.4.0, extração resiliente de JSON com warnings, stdout estritamente limpa, ação inválida com contrato estruturado, preservação de Unifilar no CAD e presença de métodos defensivos no C#.
- **Validações Consolidadas**:
  - .NET Build: Release compilado com 0 erros para `net8.0-windows` e `net48`.
  - Testes do OXCAD: 45 testes coletados (**45 PASS**, 100% de aprovação).
  - Suíte de regressão global: 520 testes coletados (**516 PASS**, 4 SKIP legítimos, 0 FAIL, 0 ERROR).
  - Skips analisados e classificados: 2 em `test_cqt_quadros.py` (ausência de planilha física local no drive externo da concessionária) e 2 em `test_cqt_gui.py` (ausência de display gráfico em ambiente headless).
  - Modelos Oficiais: Hashes SHA-256 de `modelos/prancha.dwg` e `modelos/cqt_modelo.xlsm` rigorosamente inalterados.

## Memória de Sessão - OXCAD 0.5.0: Controle de Tempo por SOB e JobTime (2026-09-26)

- **Objetivo**: Implementar controle operacional de tempo auditável e confiável associado à SOB/DWG, investigando a viabilidade técnica do JobTime nativo do AutoCAD e construindo motor de apontamento persistente sem deriva de relógio.
- **Investigação JobTime**:
  - `JOBTIME` não é comando nativo do AutoCAD (é um add-on de terceiros da Arkance/CAD Studio).
  - O mecanismo nativo (`TIME`, `TDINDWG`, `TDUSRTIMER`) mede o tempo acumulado no DWG de forma read-only, herdando horas de edição do template base (`modelos/prancha.dwg`), sem suporte a pausa determinística nem rastreabilidade de início/fim gerencial.
  - **Decisão**: Desenvolvido `OxCadJobTimer` próprio em Python + C# com persistência atômica em `.oxcad/time.json`.
- **Componentes Implementados**:
  - `workspace/workspace_time.py`: Módulo de domínio com `TimeState` (`NaoIniciado`, `EmExecucao`, `Pausado`, `Concluido`), cálculo sem deriva `tempo = acumulado + (agora - sessao_atual_inicio)`, gravação atômica via `.tmp` e substituição transacional.
  - `sob/sob_manager.py`: Integração no fluxo do comando `SOB` chamando `inicializar_tempo_projeto` imediatamente após a criação bem-sucedida do DWG e manifesto de conclusão.
  - `workspace/workspace_context_cli.py`: Inclusão do nó `tempo` no payload de contexto e despacho das ações `tempo_iniciar`, `tempo_pausar`, `tempo_retomar`, `tempo_concluir`, `tempo_reabrir`.
  - `oxcad/WorkspaceService.cs`: Adicionado DTO `OxCadTimeEntryDto`, propriedade `Tempo` e método assíncrono `ControlarTempoAsync(acao, dwgFullPath)`.
  - `oxcad/OxCadControl.xaml` & `oxcad/OxCadControl.xaml.cs`: Card visual `TEMPO DO PROJETO`, botões contextuais `BtnTempoAcaoPrincipal` e `BtnTempoConcluir`, confirmação de conclusão, rodapé `OXCAD 0.5.0 • AUX CAD` e `DispatcherTimer` a cada 1s apenas para atualização visual (zero I/O).
  - `oxcad/OxCadPaleta.csproj`: Versionamento oficial atualizado para `0.5.0`.
  - `tests/test_oxcad_jobtime.py`: 10 testes dedicados cobrindo ciclo de vida, persistência atômica, recuperação pós-fechamento, robustez a arquivos corrompidos/inexistentes, relógio retrocedido e integração com CLI e `SobOrchestrator`.
- **Validações Consolidadas**:
  - .NET Build: Release compilado com 0 erros para `net8.0-windows` e `net48`.
  - Modelos Oficiais: Hashes SHA-256 de `modelos/prancha.dwg` e `modelos/cqt_modelo.xlsm` rigorosamente inalterados.

## Memória de Sessão - OXCAD 0.5.1: Validação Operacional e Hardening do Controle de Tempo (2026-09-26)

- **Objetivo**: Auditar, endurecer e validar operacionalmente o controle de tempo do OXCAD, eliminando risco de contagem de tempo com o AutoCAD fechado e assegurando idempotência em operações concorrentes/repetidas (Casos A a F).
- **Problema Crítico Solucionado**:
  - Sessões não encerradas formalmente antes da queda ou encerramento do AutoCAD acumulavam todo o tempo transcorrido até a reabertura subsequente.
  - Implementada associação ao PID do processo chamador (`pid_processo`), registro de batimento contínuo (`ultima_atividade`) e detecção automática de `TimeState.INTERROMPIDO`.
  - Ao reabrir o DWG em novo processo, o período em que o AutoCAD esteve indisponível/fechado é descartado e o tempo trabalhado prévio é preservado intacto.
- **Componentes Refinados**:
  - `workspace/workspace_time.py`: Adicionados `TimeState.INTERROMPIDO`, função `tratar_interrupcao_se_necessario()`, `atualizar_heartbeat_tempo()`, verificação nativa de integridade de processo (`processo_esta_ativo()`) e idempotência estrita em todas as transições de estado.
  - `workspace/workspace_context_cli.py`: Parâmetro `--acad-pid` propagado para extração e despacho operacional, garantindo detecção imediata de reinicialização do CAD.
  - `oxcad/WorkspaceService.cs`: Passagem transparente do PID do AutoCAD atual (`Process.GetCurrentProcess().Id`).
  - `oxcad/OxCadControl.xaml` & `oxcad/OxCadControl.xaml.cs`: Exibição visual de `⚠ Sessão interrompida` em cor âmbar, congelamento do contador no tempo prévio real, ações contextuais e heartbeat a cada 60s em background.
  - `oxcad/OxCadPaleta.csproj`: Versionamento atualizado para `0.5.1`.
  - `tests/test_oxcad_jobtime.py`: Bateria completa com os Casos A (Pausa normal), B (Retomada), C (Conclusão congelada), D (Encerramento do AutoCAD e recuperação sem tempo fantasma), E (Resiliência a corrupção) e F (Duplo clique e idempotência).
### 17. OXCAD 0.5.2 — Auditoria Final do PID, Heartbeat e Ciclo Real do AutoCAD
- **Auditoria de Processos e Imunidade a Reciclagem de PID**:
  - Identificada e eliminada a vulnerabilidade intrínseca do Windows de reutilização de PID pelo kernel após o encerramento do `acad.exe`.
  - Introduzido o `InstanciaSessionToken` no C# (`WorkspaceService.cs`), combinando PID, start ticks UTC do host e um GUID aleatório imutável de instância.
  - Propagado via CLI `--acad-pid <PID> --acad-token <TOKEN>` para `workspace_context_cli.py`.
  - Em `workspace/workspace_time.py`, a função `tratar_interrupcao_se_necessario` valida `token_sessao`, garantindo detecção 100% determinística de interrupção mesmo se o Windows alocar o mesmo PID para um novo processo.
- **Auditoria do Heartbeat e Integridade**:
  - Disparado assincronamente a cada 60s em thread secundária (`Task.Run`) com trava de concorrência (`_isHeartbeatRunning`).
  - O heartbeat é estritamente um mecanismo de atualização de metadados (`ultima_atividade`), mantendo o cálculo ancorado em timestamps (`tempo = acumulado + (agora - sessao_inicio)`).
  - Comprovada a ausência de inchaço do `time.json` em longos períodos de trabalho contínuo.
  - Margem máxima de incerteza pós-queda limitada a 60 segundos.
- **Validações Consolidadas**:
  - **TESTE AUTOMATIZADO**: 64 testes do OXCAD aprovados (**64 PASS**, 100%); 537 testes globais de regressão aprovados (**537 PASS**, 2 SKIP, 0 FAIL, 0 ERROR).
  - **VALIDAÇÃO POR INSPEÇÃO**: Confirmado que `Process.GetCurrentProcess()` no plugin .NET via `NETLOAD` representa fielmente o `acad.exe` in-process; campos derivados desacoplados da persistência canônica.
  - **VALIDAÇÃO MANUAL (AUTOCAD REAL)**: Protocolo da Seção 25 classificado como PENDENTE de execução física pelo operador em viewport ativa.
  - Hashes SHA-256 de `modelos/prancha.dwg` e `modelos/cqt_modelo.xlsm` rigorosamente íntegros.
  - .NET Build: Release compilado com 0 erros para `net8.0-windows` e `net48`.
### 18. OXCAD 0.5.3 — Validação Operacional Real no AutoCAD
- **Alinhamento e Propagação de Versão 0.5.3**:
  - `oxcad/OxCadPaleta.csproj`: Versão 0.5.3 com compilação Release para `net8.0-windows` e `net48` (0 erros).
  - `oxcad/OxCadControl.xaml`: Rodapé `OXCAD 0.5.3 • AUX CAD`.
  - `tests/test_oxcad_hardening.py`: Asserção de integridade da versão 0.5.3.
- **Carregamento Oficial no AutoCAD**:
  - `acaddoc.lsp`: Adicionado registro e carregamento automático de `oxcad/oxcad_loader.lsp`.
  - `oxcad/oxcad_loader.lsp`: Resolução dinâmica de versão do AutoCAD (`net8.0-windows` para AutoCAD 2025/2026 e `net48` para versões anteriores), com comandos `OXCAD`, `FECHAR_OXCAD` e `RECARREGAR_OXCAD`.
- **Validação de Regressão e Modelos Oficiais**:
  - 64 testes específicos OXCAD aprovados (100% PASS).
  - 536 testes globais de regressão aprovados (0 falhas, 0 erros).
  - Modelos oficiais íntegros (`cqt_modelo.xlsm`: `09224E...`, `prancha.dwg`: `13562C...`).
- **Status Operacional Real no AutoCAD**:
  - Processo host ativo identificado: AutoCAD 2026 (PID `64656`, executável `acad.exe`).
  - Carregador e DLL prontos para execução em viewport com o comando `OXCAD`.
  - Veredito da fase: **HOMOLOGADO COM RESSALVAS** (aguardando execução manual na GUI do AutoCAD pelo operador conforme regra de não inventar resultados).
- **Correção Crítica no Carregador Real (`oxcad_loader.lsp`)**:
  - Eliminado o erro `; error: bad argument type: stringp nil` reproduzido no AutoCAD 2026.
  - Resolução robusta e agnóstica de caminhos sem dependência de funções externas ou caminhos hardcoded.
  - Invocação segura do comando .NET nativo via `(vl-cmdf "_.OXCAD")`.
- **Homologação Física Real no AutoCAD 2026 Concluída**:
  - Evidências visuais e em disco capturadas no AutoCAD 2026 com o projeto SOB `A043257319`.
  - Ciclo Iniciar -> Pausar -> Retomar -> Concluir testado com sucesso.
  - Intervalo em pausa descartado; tempo líquido trabalhado (12 segundos) congelado com precisão milimétrica.
  - Persistência em disco confirmada em `models/.oxcad/time.json`.
  - Veredito da versão OXCAD 0.5.3: **HOMOLOGADO**.
- **Refinamento de Disparo dos Módulos Especialistas**:
  - `cpfc_manager.py`: Injeção de `sys.path` antes do import de `cpfc_gui`, permitindo abertura desacoplada imediata.
  - `memorial_ambiental_generator.py`: Elevação de foco Tkinter garantida sobre a janela principal do AutoCAD.
  - `AutoPrancha`: Notificação explícita na barra de ação orientando a execução gráfica via comando nativo `AUTOPRANCHA` no AutoCAD.
---

## Memória de Sessão Consolidada - OXCAD 0.6.0: Infraestrutura Central de Logs, Auditoria e Observabilidade (2026-09-26)

- **Escopo e Motivação**:
  - Implementação da infraestrutura central de logging estruturado (JSON Lines) para todo o ecossistema OXCAD/AUX CAD após a homologação física da 0.5.3.
  - Eliminação de `print` desestruturado e garantia de rastreabilidade completa (quem, quando, onde, qual SOB, qual módulo, quanto tempo, qual resultado e qual exceção).
- **Auditoria Prévia**:
  - Diagnóstico em C# (.NET) e Python mapeando todos os pontos de log, `print`, captura de exceções, subprocessos e timers.
- **Implementação Centralizada**:
  - **Python**: Criado `common/logging_config.py` com `JsonLinesFormatter`, `SafeRotatingFileHandler`, `OxCadLoggerAdapter`, e utilitários de medição de duração (`cronometrar`, `medir_duracao`) e sanitização rigorosa de credenciais. Rotação em 5 MB com retenção de 5 arquivos.
  - **C# .NET**: Criado `oxcad/OxCadLogger.cs` (sem novas dependências externas pesadas), gravando de forma thread-safe em `logs/application.jsonl` e `logs/errors.jsonl`.
  - **Propagação de Correlation ID**: Integrado em `WorkspaceService.cs`, repassado via `--correlation-id` para `workspace_context_cli.py`, `workspace_actions.py` e subprocessos gerados.
  - **Rastreamento de Subprocessos**: PIDs de processos filhos (`subproc_pid`), comandos e status registrados detalhadamente.
  - **Transições de Tempo**: Estados do timer de projeto (`tempo.iniciado`, `tempo.pausado`, `tempo.concluido`, etc.) logados em `INFO`; batimentos cardíacos defensivos mantidos em `DEBUG`.
  - **Diagnóstico no AutoCAD**: Novo comando nativo `OXCAD_DIAGNOSTICO` expondo saúde, status, caminhos e logs recentes.
- **Segurança e Sanitização**:
  - Sanitização de argumentos e mensagens mascarando senhas, tokens, cookies e chaves de API.
  - `logs/`, `*.log`, `*.jsonl` estritamente ignorados pelo `.gitignore`.
- **Validação de Testes e Compilação**:
  - 14 testes unitários e de integração de logging (`tests/test_oxcad_logging.py`) aprovados (100% PASS).
  - 78 testes específicos OXCAD aprovados (100% PASS).
  - 549 testes globais de regressão aprovados, 4 skipped, 0 falhas, 0 erros.
  - Compilação .NET Release para `net8.0-windows` e `net48` aprovada com 0 erros.
  - Modelos oficiais íntegros por SHA-256 (`cqt_modelo.xlsm` e `prancha.dwg`).
- **Status Geral**: **HOMOLOGADO** na versão **0.6.0**.
