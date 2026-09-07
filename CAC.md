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
- `cad_to_kmz_exporter.py` & `cad2kmz.lsp` (298 linhas): Extração e exportação para Google Earth (`CAD2KMZ`) em formato WGS84 compactado:
  - Resolução segura de temporários via `vl-filename-mktemp`.
  - Suporte a extração do número real do poste via atributos do bloco (`cad2kmz-get-attr-num`).
  - Suporte completo a linhas e polilinhas (`LINE`, `LWPOLYLINE`, `POLYLINE` clássica).
  - Execução protegida via `WScript.Shell` com redirecionamento de log de diagnóstico e verificação do KMZ gerado.
- `preferencias_ambiental.json`: Smart Cache de parâmetros de formulário.

### 2. Módulo de Queda de Tensão BT (`cqt/`)
- `cqt_cad_extractor.lsp` (325 linhas):
  - **`CQT`** e **`CQTUI`**: Disparo instantâneo da Interface Gráfica para estudo prévio sem desenho.
  - **`CQTCAD`**: Extração interativa de vãos no CAD (seleção gráfica com soma automática de LINE, LWPOLYLINE, ARC) ou entrada manual de metragens; exportação segura de parâmetros e topologia em JSON via `vl-filename-mktemp`; disparo desacoplado via `(startapp "cmd.exe" ...)` idêntico ao `CQTUI`; garantia de robustez sem dependência de predicados não-nativos como `STRINGP` (uso de `(= (type x) 'STR)` e definição de compatibilidade); preenchimento automático do projeto, ponto trafo, potência, classe e trechos na UI.
  - **`CQTQUADROS`**: Desenha no CAD os Quadros de Resumo do Trafo (Verdes: 47,03 x 47,10) e Quadros de Trechos (Vermelhos: 33,21 x 13,64).
  - **`RECARREGAR_CQT`**: Comando imediato para recarregar a rotina na memória do AutoCAD sem fechar o desenho.
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

### 7. Carregamento Universal (`acaddoc.lsp`)
O arquivo `acaddoc.lsp` foi projetado para:
1. Localizar o caminho absoluto da pasta raiz `aux cad`.
2. Adicionar dinamicamente as pastas `orcamento`, `cqt`, `ambiental`, `mecanico`, `topografia` e `mapa_postes` ao `SupportPath` de arquivos de suporte do AutoCAD.
3. Carregar as rotinas modulares de forma resiliente com tratamento de erros (`vl-catch-all-apply`).

### 8. Validação e Testes
- Suíte com **52 testes unitários passando 100%** (`python -m pytest`).
- Configuração centralizada em `pytest.ini` (`pythonpath = . cqt ambiental orcamento topografia mapa_postes`).
- Cobertura nos módulos centrais de regras de negócio entre 83% e 99% (com `kmz_pontos_importer.py` em 93% e `mapa_postes` em 83%).


