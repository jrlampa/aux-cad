# CAC.md - Contexto de Arquitetura e Decisões (aux cad)

## Arquitetura de Diretórios e Modularidade
A pasta raiz `aux cad` adota uma arquitetura modular por domínios de engenharia (DDD / Separação de Responsabilidades), mantendo na raiz apenas os pontos de entrada compartilhados e ferramentas universais do AutoCAD.

```text
aux cad/
├── acaddoc.lsp                     # Carregador universal do AutoCAD (inclusão dinâmica de SupportPath)
├── aux_cad_toolbar.lsp             # Barra de ferramentas global (AUXCADBAR)
├── aux_cad_menu.mnu / .cuix / .mnr # Menu nativo do AutoCAD (AUXCAD)
├── modelos/                        # Templates e modelos compartilhados (checklist, etc.)
├── tests/                          # Full suite de testes unitários (38 testes, 100% passing)
├── pytest.ini                      # Resolução de paths para testes (cqt, ambiental, orcamento)
├── Abrir_CQT.bat                   # Atalho de 2 cliques na raiz para CQT
├── Abrir_Orcamento.bat             # Atalho de 2 cliques na raiz para Orçamento
├── clean.bat                       # Script utilitário de limpeza de temporários
├── RAG/ & CAC.md                   # Base de conhecimento e arquitetura do projeto
│
├── orcamento/                      # Módulo Orçamento e Levantamento de Materiais (AutoLISP + Python + GUI)
├── cqt/                            # Módulo Queda de Tensão BT (AutoLISP + Python + GUI)
├── ambiental/                      # Módulo Ambiental, KMZ, Ortofoto, Memorial e Checklist
├── mecanico/                       # Módulo Cálculo Estrutural e Resultante de Postes
├── topografia/                     # Módulo Topografia, Eixos Viários e Importação CSV
├── softwares/                      # Instaladores e ferramentas de terceiros
└── documentos/                     # Pranchas DWG, planilhas de referência e notas técnicas
```

---

## Detalhamento dos Módulos e Componentes

### 1. Módulo Ambiental (`ambiental/`)
- `kmz_point_layer_report.lsp`: Seleção de pontos, caixas no CAD, disparo do memorial (`KMZCHECK`) e opção de traçado gráfico 2.5D dos polígonos de restrição ambiental no CAD com layer `AMB_POLIGONO_RESTRICAO`.
- `kmz_point_layer_report.py`: Parse completo de KMZ com suporte total a `MultiGeometry` (2.504 polígonos lidos), Snyder UTM $\rightarrow$ WGS84, indexação espacial por Bounding Box (`bbox`), Ray-Casting analítico, extração de polígonos para `kmz_polygons.json` e compilação automática da rotina AutoLISP `kmz_draw_polygons.lsp`.
- `memorial_ambiental_generator.py` (687 linhas): Interface visual moderna e responsiva (100% pt-BR) organizada em 2 colunas com cards brancos, header executivo (#1B365D), banner de status ambiental de alto contraste, suporte a BT divergente, preenchimento de campos de obra/município/projetista e disparo conjunto do Word e Excel:
  - **Regra de Negócio Condicional**:
    - **Com Restrição Ambiental (APP, UC, Amortecimento, Exclusão)**: Gera **ambos os documentos** na mesma pasta: o **Memorial Descritivo (`.docx`)** e o **Checklist Ambiental (`.xlsx`)** (`SIM`).
    - **Sem Restrição Ambiental (Livre de Restrições)**: O **Memorial Descritivo (`.docx`) É DISPENSADO**. Gera-se **apenas o Checklist Ambiental (`.xlsx`)** (`NÃO`).
- `checklist_ambiental_manager.py`: Preenchimento automatizado da planilha `checklist.xlsx` da HBT/concessionária com marcas `✓` em APPs.
- `postes_detalhador.py`: Parser inteligente de blocos e atributos do CAD (`12/300`, `12/600`, `10/300` etc.).
- `croqui_ambiental_generator.py`: Gerador de Ortofoto / Croqui de Satélite georreferenciado (`CROQUI_AMBIENTAL_{SOB}.png`) com conversão Snyder analítica bidirecional (`latlon_to_utm`) e **Cache de Tiles em Disco** (`ambiental/.tile_cache/`) com chave MD5 para acelerar downloads e garantir custo zero de requisições.
- `croqui_cad_inserter.lsp`: Inserção automática de raster georreferenciado via ActiveX (`INSCROQUI`) em Model ou PaperSpace.
- `cad_to_kmz_exporter.py` & `cad2kmz.lsp`: Extração e exportação para Google Earth (`CAD2KMZ`) em formato WGS84 compactado.
- `preferencias_ambiental.json`: Smart Cache de parâmetros de formulário.

### 2. Módulo de Queda de Tensão BT (`cqt/`)
- `cqt_cad_extractor.lsp`:
  - **`CQT`** e **`CQTUI`**: Disparo instantâneo da Interface Gráfica para estudo prévio sem desenho.
  - **`CQTCAD`**: Extração de vãos no CAD ou entrada manual e disparo da UI.
  - **`CQTQUADROS`**: Desenha no CAD os Quadros de Resumo do Trafo (Verdes: 47,03 x 47,10) e Quadros de Trechos (Vermelhos: 33,21 x 13,64).
- `cqt_live_calc.py` (249 linhas): Motor de cálculo instantâneo em memória ($QT \le 6,00\%$).
- `cqt_excel_io.py` (240 linhas): Persistência atômica e leitura de planilhas Excel (`load_cables_from_database`, `load_scenario_from_excel`, `update_cqt_excel`).
- `cqt_scenario_tab.py` (365 linhas): Componente visual de edição de trechos por cenário (`ScenarioTab`) e painel de Live Preview.
- `cqt_excel_manager.py` (313 linhas): Interface principal orquestradora (`CQTManagerGUI`) e CLI, rigorosamente dentro do limite de 500 linhas.
- `cqt_quadros_generator.py` (464 linhas): Ponte entre planilha calculada e o CAD via Excel COM e rotina LISP primitivas (`entmake`).
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

### 6. Carregamento Universal (`acaddoc.lsp`)
O arquivo `acaddoc.lsp` foi projetado para:
1. Localizar o caminho absoluto da pasta raiz `aux cad`.
2. Adicionar dinamicamente as pastas `orcamento`, `cqt`, `ambiental`, `mecanico` e `topografia` ao `SupportPath` de arquivos de suporte do AutoCAD.
3. Carregar as rotinas modulares de forma resiliente com tratamento de erros (`vl-catch-all-apply`).

### 7. Validação e Testes
- Suíte com 46 testes unitários passando 100% (`python -m pytest`).
- Configuração centralizada em `pytest.ini` (`pythonpath = . cqt ambiental orcamento topografia`).
- Cobertura nos módulos centrais de regras de negócio entre 88% e 99% (com `kmz_pontos_importer.py` em 93%).

