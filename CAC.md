# CAC.md - Contexto de Arquitetura e Decisões (aux cad)

## Arquitetura de Diretórios e Modularidade
A pasta raiz `aux cad` adota uma arquitetura modular por domínios de engenharia (DDD / Separação de Responsabilidades), mantendo na raiz apenas os pontos de entrada compartilhados e ferramentas universais do AutoCAD.

```text
aux cad/
├── acaddoc.lsp                     # Carregador universal do AutoCAD (inclusão dinâmica de SupportPath)
├── aux_cad_toolbar.lsp             # Barra de ferramentas global (AUXCADBAR)
├── aux_cad_menu.mnu / .cuix / .mnr # Menu nativo do AutoCAD (AUXCAD)
├── modelos/                        # Templates e modelos compartilhados (checklist, cpfc, etc.)
├── tests/                          # Full suite de testes unitários (74 testes, 100% passing)
├── pytest.ini                      # Resolução de paths para testes (cqt, ambiental, orcamento, cpfc...)
├── Abrir_CQT.bat                   # Atalho de 2 cliques na raiz para CQT
├── Abrir_Orcamento.bat             # Atalho de 2 cliques na raiz para Orçamento
├── Abrir_CPFC.bat                  # Atalho de 2 cliques na raiz para CPFC (REN 1.059)
├── clean.bat                       # Script utilitário de limpeza de temporários
├── .env.example                    # Modelo seguro de variáveis de ambiente (GOMNET, GOM, URLs)
├── RAG/ & CAC.md                   # Base de conhecimento e arquitetura do projeto
│
├── orcamento/                      # Módulo Orçamento e Levantamento de Materiais (AutoLISP + Python + GUI)
├── cqt/                            # Módulo Queda de Tensão BT (AutoLISP + Python + GUI)
├── cpfc/                           # Módulo Participação Financeira REN 1.059 (AutoLISP + Python + GUI)
├── unifilar/                       # Módulo Diagrama Unifilar & Árvore de Dispositivos (AutoLISP + Python + SQLite)
├── ambiental/                      # Módulo Ambiental, KMZ, Ortofoto, Memorial e Checklist
├── mecanico/                       # Módulo Cálculo Estrutural e Resultante de Postes
├── topografia/                     # Módulo Topografia, Eixos Viários e Importação CSV
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
- `preferencias_ambiental.json`: Smart Cache de parâmetros de formulário.

### 2. Módulo de Queda de Tensão BT (`cqt/`)
- `cqt_cad_extractor.lsp` (434 linhas):
  - **`CQT`** e **`CQTUI`**: Disparo instantâneo da Interface Gráfica para estudo prévio sem desenho.
  - **`CQTCAD`**: Extração interativa de vãos no CAD (seleção gráfica com soma automática de LINE, LWPOLYLINE, ARC) ou entrada manual de metragens; exportação segura de parâmetros e topologia em JSON via `vl-filename-mktemp`; disparo desacoplado via `(startapp "cmd.exe" ...)` idêntico ao `CQTUI`; garantia de robustez sem dependência de predicados não-nativos como `STRINGP` (uso de `(= (type x) 'STR)` e definição de compatibilidade); preenchimento automático do projeto, ponto trafo, potência, classe e trechos na UI.
  - **`CQTQUADROS`** (e **`CQTEXCEL`**): Desenha no CAD os Quadros de Resumo do Trafo (Verdes: 47,03 x 47,10) e Quadros de Trechos (Vermelhos: 33,21 x 13,64) com suporte nativo a seleção de planilha Excel existente (`.xlsx` ou `.xlsm`) via diálogo do Windows (`getfiled` com flag 16 e resolução absoluta com `DWGPREFIX`) ou reuso dos últimos quadros gerados em `C:\Temp\cqt_draw_quadros.lsp`.
  - **`RECARREGAR_CQT`**: Comando imediato para recarregar a rotina na memória do AutoCAD sem fechar o desenho.
- `cqt_live_calc.py` (249 linhas): Motor de cálculo instantâneo em memória ($QT \le 6,00\%$).
- `cqt_excel_io.py` (276 linhas): Persistência atômica e leitura de planilhas Excel (`load_cables_from_database`, `load_scenario_from_excel`, `load_all_scenarios_from_excel`, `update_cqt_excel`).
- `cqt_scenario_tab.py` (365 linhas): Componente visual de edição de trechos por cenário (`ScenarioTab`) e painel de Live Preview.
- `cqt_excel_manager.py` (390 linhas): Interface principal orquestradora (`CQTManagerGUI`) e CLI com botão integrado **"📥 Importar Planilha Existente"** para carregamento integral dos cenários ATUAL, ATUAL+NC e PROJETADO a partir de arquivos `.xlsx` ou `.xlsm`, rigorosamente dentro do limite de 500 linhas.
- `cqt_quadros_generator.py` (485 linhas): Ponte analítica entre a planilha e o CAD via extração de dados brutos e recálculo topológico instantâneo (`calcular_cqt_topologia`), garantindo preenchimento total e exato de demandas, carregamento e quedas de tensão por trecho mesmo sem cache de fórmulas do Excel, CLI flexível (`--excel`, `--trafo`, `--out`) e rotina LISP de desenho vetorial (`cqt-draw-trafo-box`, `cqt-draw-cqt-box`, `cqt-exec-draw-quadros`).
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

### 7. Módulo de Dados Técnicos e Tabelas de Referência (`dados_tecnicos/`)
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
- `arvore_parser.py` (274 linhas):
  - Parser analítico de caminhos elétricos (` > ` ou `|`) com responsabilidade única de localizar a **primeira proteção a montante** a partir de um Ponto Elétrico alvo (ex: `SG40995` $\rightarrow$ `Chave Fusivel - SG59356`).
  - Reconhece os 3 tipos elegíveis de proteção: `Chave Fusivel`, `Religador` ou `Saida do Alimentador`.
  - Extração de Subestação e Alimentador a partir da saída (`RBN02` $\rightarrow$ `SE.: RBN`, `ALIM.: 02`).
  - Extração e enriquecimento de `Clientes Grupo A`, `Clientes Grupo B` e potência `KVA`.
  - Formatação padronizada das linhas do Diagrama Unifilar para o AutoCAD.
- `arvore_database.py` (227 linhas):
  - Camada de indexação e persistência local em SQLite (`unifilar/arvore_cache.sqlite3`).
  - Povoa a base a partir da planilha oficial `documentos/Árvore de Dispositivos.xlsx` com busca indexada em menos de 10ms.
- `arvore_client.py` (162 linhas):
  - Cliente com suporte a requisições web à intranet (`URL_ARVORE_DISPOSITIVOS`), autenticação NTLM com credenciais do `.env` e fallback automático e transparente para a base local.
- `unifilar_manager.py` (108 linhas):
  - Orquestrador CLI e ponte de intercâmbio JSON com o AutoCAD (`--ponto`, `--resumo`, `--out`, `--sincronizar`).
- `unifilar_cad.lsp` (376 linhas):
  - Comandos do AutoCAD **`UNIFILAR`** e **`PROTECAO`** (aliases: **`ARVORE`**, **`BUSCAR_PROTECAO`**).
  - Suporta digitação do ponto elétrico ou seleção direta de textos/blocos no DWG (`entsel`).
  - Dois modos de desenho:
    - **Inserir Novo**: Desenha o título verde `DIAGRAMA  UNIFILAR` sublinhado com linha e textos técnicos alinhados à direita.
    - **Atualizar Existente**: Seleciona textos existentes no DWG e substitui placeholders (`SE.: xxx`, `ALIM.: xx`, `DISPOSITIVO DE PROTEÇÃO...`, `Clientes Grupo...`) preservando a diagramação original.

### 10. Carregamento Universal (`acaddoc.lsp`)
O arquivo `acaddoc.lsp` foi projetado para:
1. Localizar o caminho absoluto da pasta raiz `aux cad`.
2. Adicionar dinamicamente as pastas `orcamento`, `cqt`, `cpfc`, `unifilar`, `ambiental`, `mecanico`, `topografia`, `mapa_postes` e `dados_tecnicos` ao `SupportPath` de arquivos de suporte do AutoCAD.
3. Carregar as rotinas modulares de forma resiliente com tratamento de erros (`vl-catch-all-apply`).

### 11. Validação e Testes
- Suíte com **93 testes unitários passando 100%** (`python -m pytest --cov`).
- Configuração centralizada em `pytest.ini` (`pythonpath = . cqt ambiental orcamento topografia mapa_postes dados_tecnicos cpfc unifilar`).
- Cobertura total do novo módulo `unifilar`: **88%** (`arvore_parser.py`: 92%, `arvore_database.py`: 92%, `arvore_client.py`: 82%, `unifilar_manager.py`: 80%).
- Resolução dinâmica de diretórios no `acaddoc.lsp` para independência de máquina.
- Rotinas e saídas geradas em tempo de execução organizadas com proteção no `.gitignore` (incluindo `unifilar/arvore_cache.sqlite3`).


