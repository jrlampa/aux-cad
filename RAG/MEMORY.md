# MEMORY.md - Contexto do Projeto aux cad

## Visão Geral
Este projeto contém utilitários e rotinas AutoLISP/Python para automação CAD no AutoCAD/Civil 3D, com foco em geoprocessamento, relatórios ambientais, geração de memoriais descritivos e cálculo automatizado de Queda de Tensão (CQT) em Baixa Tensão (BT).

A pasta raiz `aux cad` é organizada em pastas dedicadas por projeto/especialidade, mantendo na raiz apenas os componentes globais e comuns a todos os projetos.

## Arquitetura de Pastas e Módulos

### 1. Raiz Compartilhada (Comum a Todos os Projetos)
- `acaddoc.lsp`: Carregador automático nativo do AutoCAD que registra as subpastas no SupportPath e carrega as rotinas modulares a cada desenho aberto.
- `aux_cad_toolbar.lsp` & `aux_cad_menu.mnu` (`.cuix`, `.mnr`): Barra de ferramentas visual (`AUXCADBAR`) e menu do AutoCAD com atalhos de 1 clique para todos os módulos.
- `modelos/`: Templates e modelos de planilhas e documentos (`checklist_modelo.xlsx`, etc.).
- `tests/`: Suíte completa de 38 testes unitários cobrindo todos os módulos.
- `pytest.ini`: Configuração com `pythonpath = . cqt ambiental orcamento` para execução imediata da suíte de testes.
- `Abrir_CQT.bat`: Atalho na raiz para abrir a interface CQT com 2 cliques.
- `Abrir_Orcamento.bat`: Atalho na raiz para abrir a interface de Orçamento com 2 cliques.
- `clean.bat`: Utilitário de limpeza de arquivos temporários do Windows.
- `CAC.md` & `RAG/MEMORY.md`: Diretrizes arquiteturais e histórico da base de conhecimento.

### 2. `cqt/` (Projeto Queda de Tensão BT)
- `cqt_cad_extractor.lsp` (325 linhas): Rotina AutoLISP com comandos **`CQTCAD`**, **`CQT`**, **`CQTUI`**, **`CQTQUADROS`** e **`RECARREGAR_CQT`**:
  - `CQT` / `CQTUI`: Abre imediatamente a interface gráfica interativa para estudos de viabilidade.
  - `CQTCAD`: Extrai vãos e trechos do CAD graficamente ou via prompt, grava com segurança o arquivo de intercâmbio JSON via `vl-filename-mktemp`, garante compatibilidade estrita AutoLISP (`(= (type x) 'STR)` e definição global de `stringp`) e dispara a interface gráfica de forma desacoplada via `(startapp "cmd.exe" ...)`, carregando dados de projeto, trafo e vãos automaticamente.
  - `CQTQUADROS`: Desenha no CAD os Quadros de Resumo do Trafo (47.03 x 47.10) e Quadros de CQT por Trecho (33.21 x 13.64).
  - `RECARREGAR_CQT`: Recarrega a rotina imediatamente na memória da sessão do AutoCAD.
- `cqt_live_calc.py` (249 linhas): Motor de cálculo instantâneo em tempo real (Live Preview) para CQT e carregamento do trafo ($QT \le 6,00\%$).
- `cqt_excel_io.py` (240 linhas): Camada de persistência e I/O de planilhas Excel (`load_cables_from_database`, `load_scenario_from_excel`, `update_cqt_excel`).
- `cqt_scenario_tab.py` (365 linhas): Componente visual de edição de trechos por cenário (`ScenarioTab`), botões de cópia inteligente e painel de Live Preview.
- `cqt_excel_manager.py` (313 linhas): Interface gráfica principal orquestradora (`CQTManagerGUI`) e CLI, respeitando rigorosamente o limite < 500 linhas.
- `cqt_quadros_generator.py` (464 linhas): Ponte entre a planilha calculada e o CAD via Excel COM e primitiva LISP.
- `Abrir_CQT.bat`: Atalho local na pasta do projeto.

### 3. `ambiental/` (Projeto Ambiental & Cartografia)
- `kmz_point_layer_report.lsp` & `kmz_point_layer_report.py`: Checagem de pontos contra KMZ ambiental e geração de caixas de notas e **marcação gráfica de polígonos 2.5D no AutoCAD** (`KMZCHECK`):
  - **Suporte Total a MultiGeometry & 2.504 Polígonos**: Lê todas as partes e ilhas poligonais de Placemarks complexos (como a Zona de Amortecimento do Parque Estadual dos Três Picos com 20 polígonos), eliminando descartes indevidos de polígonos.
  - **Indexação Espacial Bounding Box (`bbox`)**: Filtro preliminar ultrarrápido (<4s) para testar pontos georreferenciados contra milhares de geometrias sem degradação de desempenho.
  - **Marcação Gráfica de Polígonos**: Gera a rotina `kmz_draw_polygons.lsp` que desenha polilinhas fechadas (`LWPOLYLINE`) nas coordenadas UTM reais dos polígonos interceptados nos layers `AMBIENTAL_APP`, `AMBIENTAL_UC` ou `AMBIENTAL_EXCLUSAO`, com rótulo no centróide.
- `memorial_ambiental_generator.py`: Interface gráfica moderna em Tkinter (100% pt-BR) com layout responsivo em 2 colunas (Cards), cabeçalho executivo (#1B365D), banner de status de restrições em tempo real, suporte a mousewheel e auto-ajuste de largura:
  - **COM Restrição Ambiental**: O **Memorial Descritivo (`.docx`) É OBRIGATORIAMENTE GERADO** juntamente com o **Checklist Ambiental (`.xlsx`)** (`SIM`).
  - **SEM Restrição Ambiental**: O **Memorial Descritivo (`.docx`) É DISPENSADO**. Gera-se apenas o **Checklist Ambiental (`.xlsx`)** (`NÃO`).
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

### 8. `softwares/` (Instaladores e Aplicações Externas)
- `sisRUA-Installer-1.1.0-Optimized.exe` & `sisRUA-Installer-1.1.0.zip`
- `ArkanceSystems_CADStudio_Job-Time.msi`
- `sisrua2/` & `Lampa/`

### 9. `documentos/` (Pranchas, Referências e Notas)
- `PRANCHA LIGHT.dwg` e `PRANCHA LIGHT.bak`: Templates de prancha oficial.
- `PLAN_MEDIÇÃO_ELETTRICA_PROJETOS_BASE(1).xlsx` & `Árvore de Dispositivos.xlsx`: Planilhas de medição e dispositivos.
- `anotações-2.one`: Caderno técnico de anotações.
- `Captura de tela 2026-01-29 174711.png`
- `Application does not support just-i.txt` & `Autodesk mudou o motor do AutoCAD r.txt`: Notas técnicas de suporte.

## Validação e Qualidade
- Suíte completa com **56 testes unitários passando 100%** (`python -m pytest --cov`):
  - `orcamento\orcamento_excel.py`: 99%
  - `ambiental\postes_detalhador.py`: 98%
  - `topografia\kmz_pontos_importer.py`: 93%
  - `ambiental\checklist_ambiental_manager.py`: 92%
  - `cqt\cqt_live_calc.py`: 91%
  - `cqt\cqt_quadros_generator.py`: 90%
  - `orcamento\orcamento_core.py`: 89%
  - `ambiental\croqui_ambiental_generator.py`: 88%
  - `ambiental\cad_to_kmz_exporter.py`: 86%
  - `cqt\cqt_excel_io.py`: 85%
  - `mapa_postes\mapa_servidor.py`: 83%
  - `orcamento\orcamento_manager.py`: 81%
- Cobertura global do projeto: **84%** (todos os módulos de lógica de negócio acima de 80%).
- Sintaxe AutoLISP (.lsp): 23 arquivos verificados com 100% de parênteses balanceados.
- Scripts Batch (.bat): Limpeza modernizada e atalhos testados.
- Detecção dinâmica de caminho raiz em `acaddoc.lsp` com fallback resiliente.


