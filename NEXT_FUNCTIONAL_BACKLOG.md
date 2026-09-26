# NEXT_FUNCTIONAL_BACKLOG.md — GATE DE PRIORIZAÇÃO E ESPECIFICAÇÃO TÉCNICA

---

## 1. BASELINE HOMOLOGADO

O AUX CAD V1 encontra-se formalmente fechado, validado e congelado:

```text
AUX CAD — BASELINE HOMOLOGADO OXCAD 0.4.0

Testes automatizados: 520 testes coletados (516 passed, 4 skipped legítimos, 0 failed, 0 errors)
Testes OXCAD:          45 passed (100%)
Build .NET:           net8.0-windows (0 erros) | net48 (0 erros)
Cobertura estrutural: Full suite de testes de unidade, integração e E2E operacional
Workspace Core:       CONGELADO (Thin Frontend + Smart Modules)
Módulos Especialistas: CONGELADOS (CPFC, Orçamento, Ambiental, CQT, SOB, AutoPrancha, Unifilar)
Contratos:            ESTÁVEIS (CLI, JSON, Metadados BIM, Matriz de Artefatos, OXCAD Context/Actions)
Modelos Oficiais:     ÍNTEGROS (prancha.dwg SHA256: 13562C..., cqt_modelo.xlsm SHA256: 09224E...)
Integração E2E:       HOMOLOGADA
Branch oficial:       dev
```

Nenhuma implementação ou refatoração preventiva é permitida nesta etapa. O objetivo exclusivo deste documento é a especificação e classificação factual das oportunidades de evolução funcional mapeadas.

---

## 2. ANÁLISE DOS CANDIDATOS

---

### CANDIDATO 1: CPFC — Suporte a Novos Tipos de Consumidores e Faixas Tarifárias (REN 1.059)

#### A. Objetivo Funcional
Permitir que o usuário dimensione o Custo Padrão de Fornecimento e Conexão (CPFC) para novas modalidades e classes tarifárias introduzidas ou alteradas no marco da REN 1.059/ANEEL (ex.: autoprodução, geração compartilhada em consórcio/cooperativa, novas faixas horossazonais B/A), obtendo os fatores Kc e Kg oficiais sem necessidade de intervenção manual no Excel.

#### B. Fluxo Atual
```text
Entrada:
  GUI CPFC / CLI (cpfc/cpfc_gui.py, cpfc/cpfc_manager.py)
  Parâmetros: subgrupo (ex: "B1", "B3", "A4"), potência (kW), demanda (kW).
↓
Processamento Atual:
  cpfc/cpfc_core.py:
    - Busca em SUBGRUPOS_LOOKUP (atualmente 13 subgrupos mapeados).
    - Busca em FATORES_K (tabela de vigência até 10/03/2027 da Enel RJ / ANEEL para B1..B4, A4..A2, BT1/BT2 Geração).
    - Executa calcular_cpfc(...) e classificar_consumidor(...).
↓
Saída Atual:
  Planilha preenchida (cpfc_modelo.xlsx) e JSON de resultado com Kc, Kg, encargos e memória de cálculo.
```

#### C. Fluxo Desejado
```text
Entrada:
  Novos subgrupos/modalidades selecionáveis no CPFCManagerGUI ou payload JSON.
↓
Novo Comportamento:
  Lookup do subgrupo estendido com aplicação das regras específicas de Kc/Kg da REN 1.059.
↓
Saída Esperada:
  Cálculo preciso com memorial discriminando a base regulatória e fatores específicos da nova modalidade.
```

#### D. Regras de Negócio
- Tabela oficial de fatores Kc e Kg homologada pela ANEEL para cada nova classe tarifária e modalidade de compensação.
- Critério de enquadramento de potência instalada vs. demanda contratada.
- **REGRA EXTERNA NECESSÁRIA**: As tabelas de fatores de cálculo e alíquotas regulatórias específicas para novos modelos de negócio da REN 1.059 (além das 13 já mapeadas em `cpfc/cpfc_core.py`) não constam no repositório.

#### E. Arquivos e Funções Reais Envolvidos
- [cpfc/cpfc_core.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/cpfc/cpfc_core.py): `SUBGRUPOS_LOOKUP`, `FATORES_K`, `classificar_consumidor()`, `calcular_cpfc()`.
- [cpfc/cpfc_gui.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/cpfc/cpfc_gui.py): combobox `cbo_subgrupo`, validação de campos.
- [modelos/cpfc_modelo.xlsx](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/modelos/cpfc_modelo.xlsx): abas e células de preenchimento.

#### F. Dependências
- *Interna*: `cpfc/cpfc_core.py`.
- *Normativa*: Resolução Normativa ANEEL nº 1.059/2023 e tabelas tarifárias homologadas vigentes da concessionária local (Enel RJ).
- *Excel*: Compatibilidade com as fórmulas existentes no `cpfc_modelo.xlsx`.

#### G. Contrato
- **SEM ALTERAÇÃO DE CONTRATO CLI/WORKSPACE**: O contrato aceita JSON de entrada e gera planilha/JSON de saída.
- **ALTERAÇÃO DE CONTRATO INTERNO DE DADOS**: Adição de novos valores válidos no enum/lista de subgrupos e novas chaves em `FATORES_K`.

#### H. Testabilidade
- *Unitário*: Testar lookup de fatores e cálculo de CPFC com novos subgrupos contra tabela padrão.
- *Integração*: Validação da injeção no template Excel sem corromper células vinculadas.
- *E2E*: Validação completa via GUI e WorkspaceActionDispatcher.

#### I. Critérios de Aceite
```text
DADO um consumidor com a nova modalidade tarifária especificada pela REN 1.059
QUANDO os parâmetros de potência e demanda forem processados pelo CPFC
ENTÃO o sistema deve aplicar os fatores Kc e Kg oficiais da tabela regulatória correspondente
E gerar a planilha cpfc_modelo.xlsx preenchida com a memória de cálculo exata.
```

#### J. Pendências e Status
- **Pendência**: Ausência da tabela oficial de valores de Kc/Kg e regras de cálculo específicas para as novas classes pretendidas.
- **Status**: **REQUER ESPECIFICAÇÃO** (Motivo: `REGRA EXTERNA NECESSÁRIA / DADO NORMATIVO AUSENTE`).

---

### CANDIDATO 2: CQT — Ramais Subterrâneos com Impedâncias Específicas (EPR/XLPE 1 kV)

#### A. Objetivo Funcional
Permitir que o cálculo de Queda de Tensão (CQT) dimensione trechos de baixa tensão com ramais subterrâneos compostos por condutores unipolares ou tripolares isolados em EPR ou XLPE 1 kV instalados em eletrodutos, aplicando a constante de queda de tensão $K$ exata em função de sua resistência $R$ ($\Omega/km$) e reatância $X$ ($\Omega/km$).

#### B. Fluxo Atual
```text
Entrada:
  Tabela de trechos no CQT (cqt/cqt_gui.py, cqt/cqt_excel_io.py)
  Campo cabo: ex: "Subterrâneo 50 - Al - F.P 1", "3x50+1x50 - Al - F.P 1".
↓
Processamento Atual:
  cqt/cqt_live_calc.py:
    - CONDUTORES_K (linhas 10-135): contém condutores aéreos multiplexados e 7 bitolas subterrâneas de alumínio genéricas (16, 25, 50, 95, 150, 240, 400 mm²).
    - get_fator_condutor(cabo_str): busca exata ou fallback por bitola (ex: "50" -> 0.1784).
    - Cálculo de momento: Momento = ((Carga_Propria / 2) + Carga_Jusante) * Comprimento(hm).
    - Cálculo de QT parcial: qt_parcial = Momento * fator_k.
↓
Saída Atual:
  Queda de tensão acumulada e preenchimento de cqt_modelo.xlsm.
```

#### C. Fluxo Desejado
```text
Entrada:
  Seleção explícita do condutor subterrâneo: bitola, isolação (EPR/XLPE), material (Cu/Al), arranjo (eletroduto/canaleta) e FP (0.8 ou 1.0).
↓
Novo Comportamento:
  Lookup em CONDUTORES_K com o fator K normatizado correspondente para cabos isolados 1 kV.
↓
Saída Esperada:
  Cálculo de queda de tensão em tempo real e injeção fidedigna na planilha CQT oficial.
```

#### D. Regras de Negócio e Verificação Obrigatória
1. **Onde está o catálogo `CONDUTORES_K`:** Está em [cqt/cqt_live_calc.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/cqt/cqt_live_calc.py#L10-L135) e sincronizado com a aba `BASE DE DADOS` do modelo [modelos/cqt_modelo.xlsm](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/modelos/cqt_modelo.xlsm).
2. **Grandezas utilizadas:** Constante $K$ ($\%/kVA \cdot hm$ ou $\%/(kVA \cdot m) \times 100$). A constante $K$ é dada pela fórmula de Linha Curta:
   $$K = \frac{R \cos\phi + X \sin\phi}{10 \cdot V_{ff}^2}$$
3. **Como a impedância é aplicada:** Multiplicação direta do momento elétrico do trecho ($kVA \cdot hm$) pela constante $K$:
   $$\Delta U_{\%} = M \cdot K$$
4. **Distinção entre circuito aéreo e subterrâneo:** Atualmente existe apenas por convenção de nomenclatura na string do cabo (prefixo `"Subterrâneo"`). A topologia e a fórmula de momento são idênticas.
5. **Campos no modelo Excel:** O modelo oficial `cqt_modelo.xlsm` possui validação de dados por lista vinculada à coluna de cabos da aba `BASE DE DADOS`. Se um novo cabo for inserido no Python mas não constar na lista de validação do Excel, o Excel acusa erro de validação ou exibe `#N/D`.
6. **Existência da tabela normativa no repositório:**
   - **NÃO EXISTE**. O repositório possui apenas os valores legados da planilha Enel/HBT. Não constam as tabelas de $R$ e $X$ para cabos EPR/XLPE 1 kV com espaçamento em eletroduto subterrâneo para cobre e alumínio segundo as normas vigentes (NBR 5410 / NBR 7286 / NBR 7287 / Padrão Técnico Enel).
7. **Dados que precisam ser fornecidos pelo responsável técnico:**
   - Tabela oficial de cabos homologados com: Bitola ($mm^2$), Material (Cobre/Alumínio), Espessura e Tipo de Isolação (EPR ou XLPE 90°C), Disposição dos cabos (trifólio ou plano em eletroduto PEAD/PVC), Resistência elétrica efetiva a 90°C ($R$ em $\Omega/km$), Reatância indutiva a 60 Hz ($X$ em $\Omega/km$) e o Fator $K$ oficial calculado para $FP=1.0$ e $FP=0.8$ na tensão base da rede secundária (220/127 V ou 380/220 V).

#### E. Contrato
- **SEM ALTERAÇÃO DE CONTRATO CLI/WORKSPACE**.
- **ALTERAÇÃO DE CONTRATO DE DADOS**: Adição de chaves ao dicionário `CONDUTORES_K` e inclusão das mesmas linhas na aba `BASE DE DADOS` do modelo congelado `cqt_modelo.xlsm`.

#### F. Dependências
- *Interna*: `cqt/cqt_live_calc.py`, `cqt/cqt_excel_io.py`.
- *Normativa/Externa*: Tabela oficial de cabos de concessionária com valores nominais de impedância.
- *Modelo*: `modelos/cqt_modelo.xlsm` (não pode ser alterado sem descongelar modelos oficiais).

#### G. Testabilidade
- *Unitário*: Testes de cálculo de $\Delta U$ comparando o fator manual com o cálculo de `cqt_live_calc.py`.
- *Integração*: Verificação de leitura e escrita no Excel sem violar validação de dados.

#### H. Critérios de Aceite
```text
DADO um trecho de BT configurado com cabo isolado EPR/XLPE 1 kV especificado
QUANDO for executado o cálculo de CQT em tempo real
ENTÃO o fator K utilizado deve ser exatamente o constante da tabela normativa oficial homologada
E a queda de tensão parcial calculada deve corresponder a M * K_normativo.
```

#### I. Pendências e Status
- **Pendência**: Faltam os dados normativos de $R$, $X$, $K$ e a aprovação de atualização da lista de validação do modelo congelado `cqt_modelo.xlsm`.
- **Status**: **REQUER ESPECIFICAÇÃO** (Motivo: `DADO NORMATIVO AUSENTE`).

---

### CANDIDATO 3: Workspace — Auto-Refresh Opcional via `<FocusIn>`

#### A. Objetivo Funcional
Atualizar automaticamente o status dos artefatos do projeto exibidos na árvore da `WorkspaceGUI` sempre que a janela da aplicação receber foco do sistema operacional (evento `<FocusIn>`), dispensando o usuário de clicar manualmente no botão "Atualizar Status" após editar ou salvar arquivos em outras ferramentas (AutoCAD, Excel, pasta do Windows).

#### B. Fluxo Atual
```text
Entrada:
  Usuário clica no botão "Atualizar Status" (workspace/workspace_cli.py linha 105).
↓
Processamento Atual:
  self._executar_varredura():
    - Executa WorkspaceScanner.scan(p, sob_id=...)
    - Lê sistema de arquivos em busca dos artefatos conhecidos
    - Limpa e repopula o Treeview do Tkinter.
↓
Saída Atual:
  Status e rótulos dos artefatos atualizados na tela.
```

#### C. Fluxo Desejado
```text
Entrada:
  Evento de janela <FocusIn> disparado pelo sistema operacional.
↓
Novo Comportamento:
  Avaliação de debounce / cooldown (ex.: mínimo 3-5 segundos desde a última varredura).
  Verificação se não há subprocesso especialista em execução ativa pelo dispatcher.
  Disparo não-bloqueante de _executar_varredura().
↓
Saída Esperada:
  Treeview atualizado silenciosamente sem travar a interface nem competir com I/O de rede/OneDrive.
```

#### D. Regras de Negócio e Avaliação de Riscos Técnicos
1. **Frequência potencial:** Muito alta. Alternar entre AutoCAD, Excel, Explorer e Workspace geraria dezenas de eventos `<FocusIn>` por minuto.
2. **Custo de `WorkspaceScanner`:** O scanner realiza varreduras síncronas de diretório (`Path.glob`, checagem de existência, resolução de links e leitura de cabeçalhos).
3. **Impacto em OneDrive:** Varreduras repetidas em pastas sincronizadas pelo OneDrive for Business (onde o projeto opera) podem forçar downloads parciais de ponteiros em nuvem (hydration), causar contenção de lock de arquivo e gerar latência perceptível no Tkinter.
4. **Risco de corrida e estado intermediário:** Se um especialista (ex.: CQT ou AutoPranche) estiver gravando um arquivo `.xlsm` ou `.dwg`, o scanner pode ler o arquivo temporário ou incompleto durante o `<FocusIn>`, marcando incorretamente o artefato ou gerando exceção de permissão (`PermissionError: [Errno 13]`).
5. **Necessidade de debounce:** Imprescindível. Sem debounce mínimo de 3 a 5 segundos e sem trava de execução concorrente, o evento tornará a GUI instável.

#### E. Arquivos e Funções Reais Envolvidos
- [workspace/workspace_cli.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/workspace/workspace_cli.py): `WorkspaceGUI.__init__()`, `_executar_varredura()`.

#### F. Dependências
- *Interna*: `workspace/workspace_cli.py`, `workspace/workspace_scanner.py`.
- *Externa*: Gerenciador de janelas do SO e sincronizador do OneDrive.

#### G. Contrato
- **SEM ALTERAÇÃO DE CONTRATO CLI/WORKSPACE/DISPATCHER**.
- Alteração restrita à camada de apresentação interna da GUI.

#### H. Testabilidade
- *Unitário*: Teste da lógica de debounce e trava de concorrência.
- *Manual*: Teste de usabilidade alternando janelas com arquivos abertos.

#### I. Critérios de Aceite
```text
DADO que a WorkspaceGUI está aberta e o usuário retorna de outro aplicativo
QUANDO a janela receber o evento <FocusIn>
E tiver decorrido tempo superior ao intervalo de debounce
E nenhum subprocesso de especialista estiver em execução
ENTÃO a varredura deve ser realizada sem congelar a interface
E os status dos artefatos atualizados no Treeview.
```

#### J. Pendências e Status
- **Avaliação de Risco**: Alto risco de degradar a experiência do usuário devido ao I/O no OneDrive e risco de concorrência com escrita de artefatos. O benefício funcional é marginal frente ao custo operacional.
- **Status**: **NÃO RECOMENDADO COMO PRÓXIMA ENTREGA** (Motivo: `RISCO ARQUITETURAL E DE I/O NO ONEDRIVE`).

---

### CANDIDATO 4: Unifilar + AutoPranche — Comando Integrado de Geração e Plotagem

#### A. Objetivo Funcional
Executar em um único comando ou fluxo contínuo no AutoCAD a geração do diagrama unifilar, o enquadramento na prancha oficial e a chamada de plotagem em PDF, reduzindo as etapas manuais do projetista.

#### B. Fluxo Atual
```text
Fluxo Unifilar:
  AutoCAD: Comando c:UNIFILAR (unifilar/unifilar_cad.lsp linha 413)
  Pede ponto de inserção e seleção de elementos.
  Chama script Python unifilar_cli.py via arquivo de troca JSON.
  Desenha o diagrama unifilar no ModelSpace.

Fluxo AutoPranche:
  AutoCAD: Comando c:AUTOPRANCHA (prancha/autoprancha.lsp linha 352)
  Usuário seleciona a janela/elementos a enquadrar.
  LISP calcula dimensões, escolhe o formato (A0..A4) e insere o bloco do prancha.dwg.
  Comando c:RECARREGAR_PRANCHA para reinserção de blocos.
  Plotagem é realizada separadamente via comandos nativos do AutoCAD ou drivers de impressão.
```

#### C. Fluxo Desejado
```text
Entrada:
  Comando AutoCAD unificado (ex: c:GERAR_PRANCHA_COMPLETA).
↓
Novo Comportamento:
  Gera unifilar no ModelSpace → Determina bounding box do unifilar gerado →
  Chama c:AUTOPRANCHA programaticamente passando a bounding box →
  Aplica carimbo com metadados do projeto →
  (Opcional) Executa plotagem via comando PLOT silencioso.
↓
Saída Esperada:
  Diagrama unifilar desenhado, enquadrado no formato correto na prancha oficial e PDF gerado na pasta do projeto.
```

#### D. Regras de Negócio e Pontos de Falha
1. **Comandos existentes:** `c:UNIFILAR` (interativo, exige seleção e ponto do usuário) e `c:AUTOPRANCHA` (interativo, exige definição de janela de seleção ou escala).
2. **Dependência de AutoCAD ativo:** Total. Ambos rodam em contexto LISP dentro do AutoCAD via Active Document.
3. **Informações necessárias para transferência:** Coordenadas exatas da bounding box do desenho gerado, ponto de origem do unifilar, metadados do carimbo (SOB, cliente, endereço) e escala gráfica desejada.
4. **Onde a automação quebra:**
   - A geração do unifilar pode ter dimensões variáveis que extrapolam um formato A3 ou A2, exigindo escolha humana de escala ou rotação.
   - A plotagem automática exige configuração de driver de plotter (ex.: `DWG to PDF.pc3`), tabela de estilos de plotagem (`monochrome.ctb`) e tamanho de papel pré-instalados na máquina do usuário.
5. **Plotagem integrada:** Plotagem em LISP é historicamente frágil e sujeita a diferenças de configuração local de drivers CAD. A plotagem não deve ser acoplada à geração geométrica.

#### E. Arquivos e Funções Reais Envolvidos
- [unifilar/unifilar_cad.lsp](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/unifilar/unifilar_cad.lsp): `c:UNIFILAR`.
- [prancha/autoprancha.lsp](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/prancha/autoprancha.lsp): `c:AUTOPRANCHA`, `c:PRANCHA`, `c:ENQUADRAR`.

#### F. Dependências
- *AutoCAD*: Dependência mandatória de sessão ativa do AutoCAD, drivers de plotagem e execução sequencial LISP.
- *Modelos*: [modelos/prancha.dwg](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/modelos/prancha.dwg).

#### G. Contrato
- **ALTERAÇÃO DE CONTRATO LISP NECESSÁRIA**: Exige criação de novo ponto de entrada AutoLISP sem prompts interativos para permitir encadeamento não assistido.
- Sem alteração no contrato Workspace/CLI.

#### H. Testabilidade
- *Unitário*: Impraticável em ambiente CI/sem AutoCAD.
- *Manual / AutoCAD*: Validação dentro de sessão de CAD com operador humano.

#### I. Critérios de Aceite
```text
DADO um projeto com diagrama unifilar a ser gerado
QUANDO o projetista executar o comando unificado no AutoCAD
ENTÃO o diagrama deve ser inserido nas coordenadas indicadas
E a folha de formato correspondente deve ser inserida e centralizada ao redor do diagrama
E os atributos do carimbo devem ser preenchidos automaticamente.
```

#### J. Pendências e Status
- **Pendência**: Falta especificação da máquina de estados LISP para encadeamento não-interativo e definição do isolamento da plotagem.
- **Status**: **REQUER ESPECIFICAÇÃO** (Motivo: `FLUXO INTERATIVO LISP NÃO FORMALIZADO`).

---

### CANDIDATO 5: Ambiental — Modelo Local de Memorial Ambiental

#### A. Objetivo Funcional
Permitir a geração do Memorial Descritivo Ambiental em modo 100% autônomo e offline, eliminando a dependência do caminho fixo em nuvem corporativa (`G:\Meu Drive\1-HBT\MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx`).

#### B. Fluxo Atual
```text
Entrada:
  Dados do projeto e arquivo KMZ (ambiental/memorial_ambiental_generator.py, ambiental/kmz_point_layer_report.lsp).
↓
Processamento Atual:
  memorial_ambiental_generator.py linha 841:
    template = r"G:\Meu Drive\1-HBT\MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx"
  kmz_point_layer_report.lsp linha 283:
    (setq docx_template "G:\\Meu Drive\\1-HBT\\MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx")
  Tentativa de carregar via docx.Document(template).
↓
Saída Atual:
  Falha com FileNotFoundError caso a máquina não possua o Google Drive montado na letra G: com a estrutura corporativa 1-HBT sincronizada.
```

#### C. Fluxo Desejado
```text
Entrada:
  Execução do módulo Ambiental pelo WorkspaceActionDispatcher ou CLI.
↓
Novo Comportamento:
  O gerador busca o modelo prioritariamente no repositório local:
  caminho_local = Path(__file__).resolve().parent.parent / "modelos" / "MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx"
  Caso não exista, busca na variável de ambiente AMBIENTAL_TEMPLATE_DOCX ou fallback para o Google Drive legado.
↓
Saída Esperada:
  Memorial descritivo DOCX gerado sem falhas mesmo em estações sem Google Drive.
```

#### D. Regras de Negócio e Diagnóstico
1. **Localização atual:** Hardcoded para o caminho de rede `G:\Meu Drive\1-HBT\...`.
2. **Existência física no repositório:** **NÃO EXISTE** na pasta `modelos/`. A pasta `modelos/` contém apenas `checklist_modelo.xlsx`, `cpfc_modelo.xlsx`, `cqt_modelo.xlsm` e `prancha.dwg`.
3. **Tamanho e impacto no repositório:** Arquivos `.docx` típicos têm entre 100 KB e 2 MB. O impacto em Git é desprezível se for versão única congelada.
4. **Risco de divergência:** Se o modelo estiver no Git e continuar sofrendo alterações pela equipe ambiental no Google Drive, o repositório ficará desatualizado.
5. **Compatibilidade do gerador:** O código de [ambiental/memorial_ambiental_generator.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/ambiental/memorial_ambiental_generator.py) já utiliza a biblioteca `python-docx` para substituir tags/tabelas; a leitura de um caminho local relativo funciona imediatamente sem qualquer refatoração estrutural.

#### E. Arquivos e Funções Reais Envolvidos
- [ambiental/memorial_ambiental_generator.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/ambiental/memorial_ambiental_generator.py): linha 841.
- [ambiental/kmz_point_layer_report.lsp](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/ambiental/kmz_point_layer_report.lsp): linha 283.
- [modelos/](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/modelos): diretório de modelos oficiais.

#### F. Dependências
- *Dependência de arquivo/modelo*: O arquivo físico `MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx` precisa ser homologado pela equipe de meio ambiente e fornecido para inclusão na pasta `modelos/`.

#### G. Contrato
- **SEM ALTERAÇÃO DE CONTRATO CLI/WORKSPACE**.
- O artefato gerado permanece sendo o mesmo `DOCX` na pasta do projeto.

#### H. Testabilidade
- *Unitário*: Testar resolução de caminho do template com fallback.
- *Integração*: Geração de documento de teste via `python-docx` lendo de `modelos/`.

#### I. Critérios de Aceite
```text
DADO o arquivo oficial MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx presente na pasta modelos/
QUANDO a geração do memorial ambiental for invocada em um ambiente sem acesso ao drive G:
ENTÃO o gerador deve carregar o modelo local com sucesso
E produzir o documento preenchido na pasta de destino do projeto.
```

#### J. Pendências e Status
- **Pendência**: Fornecimento da cópia homologada do arquivo DOCX oficial para adição em `modelos/` e congelamento de hash SHA256.
- **Status**: **REQUER ESPECIFICAÇÃO** (Motivo: `DEPENDÊNCIA DE ARQUIVO EXTERNO NÃO DISPONÍVEL NO REPOSITÓRIO`).

---

### CANDIDATO 6: SOB — Telemetria Estruturada da Busca de Croquis no SharePoint

#### A. Objetivo Funcional
Registrar de forma padronizada e estruturada (via logger interno) as métricas de execução da busca de croquis no SharePoint, indicando a estratégia utilizada (`LEVANTAMENTOS_DE_CAMPO` vs `FALLBACK_EXISTENTE`), o tempo de busca em milissegundos, tempo de download e resultado obtido (sucesso, falha ou acionamento de fallback), sem alterar nenhuma regra funcional nem expor dados sensíveis.

#### B. Fluxo Atual
```text
Entrada:
  sob/sob_sharepoint.py: buscar_e_baixar_croqui_prioritario(sob_codigo, destino)
↓
Processamento Atual:
  - self._log('[SHAREPOINT] Buscando croqui em "Levantamentos de campo"...')
  - Executa buscar_em_levantamentos_campo(sob_codigo)
  - Emite logs em texto puro na console/GUI.
  - Se falhar ou não encontrar: emite log e chama self.localizar_pasta_sob_existente(sob_codigo).
↓
Saída Atual:
  Retorna caminho da pasta ou lista de arquivos baixados. Logs são strings informativas sem medição de tempo estruturada.
```

#### C. Fluxo Desejado
```text
Entrada:
  sob/sob_sharepoint.py: buscar_e_baixar_croqui_prioritario(sob_codigo, destino)
↓
Novo Comportamento:
  - Marca timestamp inicial (t0).
  - Tenta busca prioritária em "Levantamentos de campo".
  - Registra telemetria: {"estrategia": "LEVANTAMENTOS_DE_CAMPO", "duracao_ms": ..., "sucesso": bool}.
  - Se acionar fallback: registra evento de fallback e mede t_fallback.
  - Registra métrica final de download (tamanho total, arquivos, duracao_download_ms).
↓
Saída Esperada:
  Comportamento funcional idêntico, com métricas auditáveis disponíveis no log de execução para análise de desempenho.
```

#### D. Regras de Negócio
- A telemetria deve ser 100% não-intrusiva: uma falha na coleta de telemetria NUNCA pode interromper o fluxo operacional de busca ou download.
- Não registrar credenciais, senhas, tokens ou dados pessoais (LGPD / Segurança First).
- Tempos medidos via `time.perf_counter()`.

#### E. Arquivos e Funções Reais Envolvidos
- [sob/sob_sharepoint.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/sob/sob_sharepoint.py): `buscar_e_baixar_croqui_prioritario()`, `buscar_em_levantamentos_campo()`, `_aguardar_e_processar_download()`.

#### F. Dependências
- *Interna*: Apenas biblioteca padrão Python (`time`, `logging`).
- *Sem dependências externas, normativas ou de arquivos*.

#### G. Contrato
- **SEM ALTERAÇÃO DE CONTRATO CLI/WORKSPACE/GUI/JSON**.
- As assinaturas de métodos e retornos permanecem rigorosamente inalterados.

#### H. Testabilidade
- *Unitário*: Testar emissão de métricas e estrutura do payload de log simulando retornos com mocks.
- *Integração*: Verificar que os testes existentes em `tests/test_sob_sharepoint.py` continuam 100% aprovados.

#### I. Critérios de Aceite
```text
DADO uma chamada ao método buscar_e_baixar_croqui_prioritario
QUANDO o croqui for localizado na busca prioritária
ENTÃO o log estruturado deve registrar a estratégia LEVANTAMENTOS_DE_CAMPO e a duração em ms
E QUANDO a busca prioritária não encontrar e acionar o fallback
ENTÃO o log estruturado deve registrar o acionamento do fallback e as durações individuais de cada etapa.
```

#### J. Pendências e Status
- **Pendência**: Nenhuma. Regras, código e locais de medição estão completamente identificados e isolados.
- **Status**: **PRONTO PARA IMPLEMENTAÇÃO**.

---

### CANDIDATO 7: CPFC — Limpeza dos Arquivos Temporários `cpfc_contexto_*.json`

#### A. Objetivo Funcional
Garantir que os arquivos temporários de intercâmbio de contexto (`cpfc_contexto_<SOB>_*.json`), criados no diretório `%TEMP%` do sistema operacional durante a inicialização do CPFC a partir do Workspace, sejam removidos de forma determinística após o carregamento pela interface ou no fechamento do processo, prevenindo acúmulo de arquivos residuais no disco do usuário.

#### B. Fluxo Atual
```text
Entrada:
  Usuário clica em "CPFC" no WorkspaceGUI ou chama montar_comando_cpfc no WorkspaceActionDispatcher.
↓
Processamento Atual:
  workspace/workspace_actions.py (linhas 339-350):
    - Cria tempfile.NamedTemporaryFile(mode="w", suffix=".json", prefix=f"cpfc_contexto_{sob_str}_", delete=False)
    - Escreve payload com projeto, pasta_destino, município e endereço.
    - Fecha o handle e passa o caminho absoluto como argumento CLI do cpfc_manager.py.
  cpfc/cpfc_manager.py (linhas 37-58):
    - Recebe o caminho no sys.argv[1].
    - Carrega dados em carregar_dados_intercambio(arg1).
    - Instancia CPFCManagerGUI e executa app.mainloop().
↓
Saída Atual:
  O arquivo JSON permanece indefinidamente na pasta %TEMP% do Windows porque delete=False foi utilizado e nenhuma rotina posterior invoca os.unlink().
```

#### C. Fluxo Desejado
```text
Entrada:
  Caminho do arquivo temporário passado via CLI para cpfc/cpfc_manager.py.
↓
Novo Comportamento:
  Após carregar_dados_intercambio ler com sucesso os dados na memória:
  - Ou o cpfc_manager.py remove o arquivo temporário imediatamente após a leitura (já que os dados já estão na memória do processo);
  - Ou o ciclo de vida é protegido por try/finally / registro de encerramento, garantindo unlink seguro.
↓
Saída Esperada:
  Dados carregados na interface gráfica com sucesso e arquivo temporário excluído de %TEMP%.
```

#### D. Regras de Negócio e Análise de Ciclo de Vida
1. **Onde o arquivo é criado:** Em [workspace/workspace_actions.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/workspace/workspace_actions.py#L340) via `tempfile.NamedTemporaryFile(delete=False)`.
2. **Quem deve ser o responsável por removê-lo:** O processo consumidor ([cpfc/cpfc_manager.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/cpfc/cpfc_manager.py)) após a leitura completa em `carregar_dados_intercambio()`, ou o próprio `workspace_actions.py` em caso de falha de lançamento do subprocesso.
3. **Ciclo de vida do processo:** O arquivo é apenas um DTO (Data Transfer Object) de inicialização. Assim que `carregar_dados_intercambio()` executa `json.load()`, o conteúdo já está armazenado no dicionário `dados_iniciais` da aplicação Tkinter. Ele não é mais lido durante a execução da GUI.
4. **Risco de apagar prematuramente:** Nenhum, desde que o `unlink()` ocorra **após** a leitura bem-sucedida do JSON em memória.
5. **Alternativa segura:**
   - Em [cpfc/cpfc_manager.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/cpfc/cpfc_manager.py):
     ```python
     if arg1.endswith(".json") and os.path.exists(arg1):
         dados_iniciais = carregar_dados_intercambio(arg1)
         # Limpeza segura de arquivo temporário de contexto
         if "cpfc_contexto_" in os.path.basename(arg1):
             try:
                 os.unlink(arg1)
             except OSError:
                 pass
     ```
   - Isso garante que arquivos de contexto criados pelo dispatcher sejam eliminados imediatamente após a carga, sem afetar arquivos JSON de usuários que não contenham o prefixo de intercâmbio.

#### E. Arquivos e Funções Reais Envolvidos
- [workspace/workspace_actions.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/workspace/workspace_actions.py): `montar_comando_cpfc()`.
- [cpfc/cpfc_manager.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/cpfc/cpfc_manager.py): `main()`, `carregar_dados_intercambio()`.

#### F. Dependências
- *Interna*: Apenas biblioteca padrão (`os`, `pathlib`, `tempfile`).
- Sem dependências externas, normativas ou de ferramentas de terceiros.

#### G. Contrato
- **SEM ALTERAÇÃO DE CONTRATO CLI/WORKSPACE/GUI/JSON**.
- O contrato de argumentos CLI permanece idêntico (`sys.argv[1]` continua recebendo o caminho do JSON).

#### H. Testabilidade
- *Unitário*: Testar se um arquivo temporário com prefixo `cpfc_contexto_` é removido após ser consumido por `carregar_dados_intercambio` ou na rotina de inicialização de `cpfc_manager.py`.
- *Integração*: Execução via `WorkspaceActionDispatcher.montar_comando_cpfc` e conferência de que o arquivo temporário não persiste em `%TEMP%`.

#### I. Critérios de Aceite
```text
DADO um arquivo temporário cpfc_contexto_<SOB>_*.json criado pelo WorkspaceActionDispatcher
QUANDO o cpfc_manager carregar os dados de intercâmbio na inicialização
ENTÃO os dados do projeto devem ser carregados corretamente na GUI do CPFC
E o arquivo temporário correspondente em %TEMP% deve ser excluído do sistema de arquivos.
```

#### J. Pendências e Status
- **Pendência**: Nenhuma. Arquitetura, ciclo de vida e pontos exatos de criação e exclusão estão identificados e comprovados no código.
- **Status**: **PRONTO PARA IMPLEMENTAÇÃO**.

---

## 3. PRONTO PARA IMPLEMENTAÇÃO

Os seguintes itens possuem especificação técnica completa, regras de negócio claras, código e funções reais mapeados, ausência de dependências externas bloqueantes e critérios de aceite objetivos:

1. **CPFC — Limpeza dos Arquivos Temporários `cpfc_contexto_*.json`**
   - *Por quê:* Alteração cirúrgica no consumidor [cpfc/cpfc_manager.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/cpfc/cpfc_manager.py), sem quebra de contrato, sem dependências externas, risco nulo de regressão e alta testabilidade.
2. **SOB — Telemetria Estruturada da Busca de Croquis no SharePoint**
   - *Por quê:* Adição de instrumentação observacional em [sob/sob_sharepoint.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/sob/sob_sharepoint.py), sem alterar o comportamento funcional nem as assinaturas existentes, com medição não-intrusiva de tempos de execução e estratégia utilizada.

---

## 4. REQUER ESPECIFICAÇÃO

Os seguintes itens NÃO possuem todas as informações técnicas ou normativas necessárias para entrada em desenvolvimento:

1. **CPFC — Novos Tipos de Consumidores e Faixas Tarifárias (REN 1.059)**
   - *O que falta:* Tabela regulatória com valores oficiais de Kc e Kg e fórmulas de enquadramento para as novas modalidades pretendidas da REN 1.059.
2. **CQT — Ramais Subterrâneos com Impedâncias Específicas (EPR/XLPE 1 kV)**
   - *O que falta:* Tabela normativa de concessionária contendo bitolas, resistências $R$ ($\Omega/km$), reatâncias $X$ ($\Omega/km$) e fatores $K$ homologados para cabos isolados 1 kV em eletroduto, além da atualização da lista de validação na aba `BASE DE DADOS` do modelo congelado `cqt_modelo.xlsm`.
3. **Unifilar + AutoPranche — Comando Integrado de Geração e Plotagem**
   - *O que falta:* Especificação da máquina de estados AutoLISP para encadeamento não-interativo dos comandos `c:UNIFILAR` e `c:AUTOPRANCHA`, definição do cálculo de bounding box geométrica no ModelSpace e desacoplamento do mecanismo de plotagem.
4. **Ambiental — Modelo Local de Memorial Ambiental**
   - *O que falta:* Fornecimento do arquivo físico homologado `MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx` para inclusão oficial na pasta `modelos/` e geração de hash SHA256.

---

## 5. DEPENDÊNCIAS EXTERNAS

Resumo das dependências que impedem a liberação imediata dos itens não prontos:

| Candidato | Dependência Externa Necessária | Responsável pelo Fornecimento |
| :--- | :--- | :--- |
| **CQT (Subterrâneo)** | Tabela técnica oficial da concessionária de impedâncias/fatores K para cabos EPR/XLPE 1 kV | Engenharia de Distribuição / Responsável Técnico |
| **CPFC (REN 1.059)** | Resolução homologatória da ANEEL com parâmetros Kc e Kg das modalidades adicionais | Especialista Regulatório / Concessionária |
| **Ambiental (DOCX)** | Arquivo binário oficial `MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx` desvinculado de caminhos absolutos de rede | Equipe de Meio Ambiente / Gestor do Projeto |
| **Unifilar + Prancha** | Definição operacional do padrão de escala e impressora virtual PDF padrão para plotagem batch | Coordenador de Projetos CAD |

---

## 6. RISCOS TÉCNICOS IDENTIFICADOS

1. **Workspace Auto-Refresh via `<FocusIn>`:**
   - *Risco:* Concorrência de I/O em pastas sincronizadas pelo OneDrive for Business. Varreduras disparadas a cada alternância de janela podem provocar bloqueio de arquivos temporários, download involuntário de metadados em nuvem e congelamento da UI Tkinter.
2. **Alteração do Modelo `cqt_modelo.xlsm` sem Governança:**
   - *Risco:* Inserir novos nomes de cabos em `cqt_live_calc.py` sem sincronizar a validação de dados da planilha oficial quebrará o preenchimento automático de trechos via `cqt_excel_io.py`.
3. **Acoplamento de Plotagem no AutoLISP:**
   - *Risco:* Drivers de plotagem variam amplamente entre estações de trabalho de projetistas (nomes de impressoras, suporte a PDF, arquivos de penas `.ctb`), tornando comandos automáticos de plotagem propensos a falhas silenciosas no AutoCAD.

---

## 7. PRIMEIRO INCREMENTO RECOMENDADO

Com base em evidências factuais de isolamento, ausência de dependências externas e aderência rigorosa ao baseline congelado:

```text
PRÓXIMO INCREMENTO RECOMENDADO:
Candidato 7: CPFC — Limpeza dos Arquivos Temporários cpfc_contexto_*.json
(Seguido opcionalmente pelo Candidato 6: SOB — Telemetria Estruturada no SharePoint)
```

### Justificativa Técnica:
- **Tamanho:** Mínimo (modificação cirúrgica de poucas linhas em [cpfc/cpfc_manager.py](file:///c:/Users/jonat/OneDrive%20-%20IM3%20Brasil/aux%20cad/cpfc/cpfc_manager.py)).
- **Contratos:** 100% inalterados (CLI, JSON, Dispatcher e GUI mantêm as mesmas interfaces).
- **Dependências externas:** Zero (utiliza apenas `os.unlink` da biblioteca padrão).
- **Testabilidade:** 100% testável via teste unitário isolado com mock/tempfile.
- **Impacto no Baseline V1:** Risco zero de regressão sobre a suíte de 459 testes homologada.
