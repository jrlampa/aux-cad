;;; =============================================================================
;;; cpfc_cad_launcher.lsp - Lançador AutoLISP do Módulo CPFC no AutoCAD
;;; Módulo CPFC - Cálculo de Participação Financeira do Consumidor (REN 1.059 ANEEL)
;;;
;;; Comandos disponíveis no AutoCAD:
;;;   CPFC / CPFCUI   - Abre imediatamente a interface gráfica interativa
;;;   CPFCCAD         - Captura dados do DWG atual e dispara a interface com pasta do projeto
;;;   CPFCALERTA      - Exibe caixa com as regras da REN 1.059 sobre casos que geram PF
;;;   CPFCREGRA       - Alias para CPFCALERTA
;;; =============================================================================

(vl-load-com)

;; Compatibilidade para checagem de tipo string
(defun stringp (x) (= (type x) 'STR))

;; Localiza o script Python do gerenciador CPFC
(defun cpfc-get-py-script (/ py_script)
  (if (boundp '*aux-cad-root*)
    (setq py_script (strcat *aux-cad-root* "cpfc\\cpfc_manager.py"))
    (setq py_script (findfile "cpfc\\cpfc_manager.py"))
  )
  (if (or (null py_script) (not (findfile py_script)))
    (setq py_script (findfile "cpfc_manager.py"))
  )
  (if (or (null py_script) (not (findfile py_script)))
    (setq py_script "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\cpfc\\cpfc_manager.py")
  )
  py_script
)

;; Exibe alerta e resumo normativo no prompt do console sobre casos que geram PF
(defun cpfc-exibir-alerta-ren1059 ()
  (princ "\n-------------------------------------------------------------------------")
  (princ "\n [AVISO REGULATÓRIO - PARTICIPAÇÃO FINANCEIRA (REN 1.059 / REN 1.000)]  ")
  (princ "\n-------------------------------------------------------------------------")
  (princ "\n ⚠ CASOS QUE GERAM PARTICIPAÇÃO FINANCEIRA (PF > 0):                    ")
  (princ "\n   1. COP > ERD: Custo proporcionalizado supera o limite da concessionária;")
  (princ "\n   2. GERAÇÃO DISTRIBUÍDA: Quando Geração > Carga (Kg incide no excedente); ")
  (princ "\n   3. ALTO CUSTO POR kW: Extensões longas (MT/BT) p/ atender carga moderada;")
  (princ "\n   4. OBRAS EXCLUSIVAS / INTERESSE RESTRITO: Tensão especial ou sem rateio.  ")
  (princ "\n ✔ CASOS DE ISENÇÃO (PF = 0):                                           ")
  (princ "\n   - Quando COP <= ERD (custo absorvido 100% pela distribuidora)        ")
  (princ "\n   - Conexões do Grupo B dentro dos limites de gratuidade da ANEEL.      ")
  (princ "\n-------------------------------------------------------------------------")
)

;; Comando Direto CPFC / CPFCUI - Abertura instantânea com alerta regulatório
(defun c:CPFCUI (/ py_script dwg_dir dwg_name proj_num cmd)
  (cpfc-exibir-alerta-ren1059)
  (setq py_script (cpfc-get-py-script))
  
  (setq dwg_dir (getvar "DWGPREFIX"))
  (setq dwg_name (getvar "DWGNAME"))
  (setq proj_num (vl-filename-base dwg_name))
  (if (or (null proj_num) (= proj_num "") (= (strcase proj_num) "DRAWING1"))
    (setq proj_num "A057032667")
  )

  (princ "\n[CPFC] Iniciando Interface Gráfica de Participação Financeira...")

  (if (and dwg_dir (/= dwg_dir ""))
    (setq cmd (strcat "/c start \"\" python \"" py_script "\" \"" dwg_dir "\" \"" proj_num "\""))
    (setq cmd (strcat "/c start \"\" python \"" py_script "\""))
  )
  
  (startapp "cmd.exe" cmd)
  (princ "\n[CPFC] Interface aberta com sucesso! Preencha os campos e salve a planilha.")
  (princ)
)

(defun c:CPFC () (c:CPFCUI))

;; Comando CPFCCAD - Interativo com confirmação de projeto e pasta
(defun c:CPFCCAD (/ py_script dwg_dir dwg_name default_proj num_proj json_file f cmd)
  (princ "\n=======================================================")
  (princ "\n  CPFC - CÁLCULO DE PARTICIPAÇÃO FINANCEIRA (REN 1.059)")
  (princ "\n=======================================================")
  
  (cpfc-exibir-alerta-ren1059)

  (setq py_script (cpfc-get-py-script))
  (setq dwg_dir (getvar "DWGPREFIX"))
  (setq dwg_name (getvar "DWGNAME"))
  (setq default_proj (vl-filename-base dwg_name))
  (if (or (null default_proj) (= default_proj "") (= (strcase default_proj) "DRAWING1"))
    (setq default_proj "A057032667")
  )

  (setq num_proj (getstring (strcat "\nInforme o Número do Projeto/Ordem <" default_proj ">: ")))
  (if (or (null num_proj) (= num_proj ""))
    (setq num_proj default_proj)
  )

  ;; Exporta arquivo temporário de intercâmbio JSON
  (setq json_file (vl-filename-mktemp "cpfc_cad_input.json"))
  (setq f (open json_file "w"))
  (if f
    (progn
      (write-line "{" f)
      (write-line (strcat "  \"projeto\": \"" num_proj "\",") f)
      (write-line (strcat "  \"pasta_destino\": \"" (vl-string-translate "\\" "/" dwg_dir) "\",") f)
      (write-line (strcat "  \"desenho\": \"" dwg_name "\"") f)
      (write-line "}" f)
      (close f)
    )
  )

  (princ "\n[CPFC] Abrindo Interface com parâmetros do desenho...")
  (setq cmd (strcat "/c start \"\" python \"" py_script "\" \"" json_file "\" \"" num_proj "\""))
  (startapp "cmd.exe" cmd)
  (princ)
)

;; Comando de Alerta e Consulta Visual das Regras da REN 1.059
(defun c:CPFCALERTA (/ msg)
  (setq msg (strcat
    "=== REGRAS DE PARTICIPAÇÃO FINANCEIRA (REN 1.059 / ANEEL) ===\n\n"
    "A Participação Financeira do Consumidor (PF) ocorre quando:\n"
    "PF = max(0, COP - ERD)\n\n"
    "🚨 SITUAÇÕES QUE GERAM PARTICIPAÇÃO FINANCEIRA (PF > 0):\n"
    "1. COP > ERD: Custo proporcionalizado da obra supera o limite de\n"
    "   investimento regulatório da concessionária (ERD).\n"
    "2. GERAÇÃO DISTRIBUÍDA (MMGD): Quando a demanda de geração supera a\n"
    "   demanda de carga, incide o Fator Kgeração (Kg) sobre o excedente,\n"
    "   resultando em menor cobertura de ERD e eventual cobrança de reforço.\n"
    "3. EXTENSÕES LONGAS: Redes extensas em MT/BT com elevado custo de\n"
    "   materiais para atender demanda concentrada moderada.\n"
    "4. OBRAS DE INTERESSE RESTRITO: Atendimento em tensão fora do padrão,\n"
    "   redes expressas ou transformadores exclusivos do cliente (100% PF).\n\n"
    "✔ ISENÇÃO (PF = 0):\n"
    "• Quando COP <= ERD (a distribuidora arca com 100% dos custos).\n"
    "• Conexões do Grupo B atendidas pela gratuidade regulatória (Art. 104)."
  ))
  (alert msg)
  (princ)
)

(defun c:CPFCREGRA () (c:CPFCALERTA))

;; Função auxiliar para criar layer seguro
(defun cpfc-garantir-layer (layer_name cor / acadObj doc layers)
  (if (null (tblsearch "LAYER" layer_name))
    (progn
      (setq acadObj (vlax-get-acad-object))
      (setq doc (vla-get-ActiveDocument acadObj))
      (setq layers (vla-get-Layers doc))
      (vl-catch-all-apply
        '(lambda ()
           (vla-add layers layer_name)
           (setvar "CLAYER" layer_name)
           (command-s "._layer" "_color" (itoa cor) layer_name "")
         )
      )
    )
    (setvar "CLAYER" layer_name)
  )
)

;; Inserção direta de Nota Técnica de CPFC no AutoCAD (MText)
(defun c:CPFC_NOTAS (/ opc pt txt acadObj doc mspace mtextObj larg alt)
  (princ "\n==================================================================")
  (princ "\n NOTAS TÉCNICAS REGULATÓRIAS - PARTICIPAÇÃO FINANCEIRA (CPFC)   ")
  (princ "\n==================================================================")
  (princ "\n Selecione o enquadramento regulatório do projeto:               ")
  (princ "\n  [1] Carga x Disjuntor (Arts. 98 e 99 - Custeio Medição/Rede)   ")
  (princ "\n  [2] Ligação Nova > 50 kW (Arts. 104 e 106 - Sem Gratuidade)   ")
  (princ "\n  [3] Acréscimo Carga > 50 kW / Complementação Fase MT (105/106)")
  (princ "\n  [4] Relocação de Poste / Afastamento de Rede (Art. 110)       ")
  (princ "\n  [5] Consolidado Completo (Todas as Notas)                     ")
  
  (initget "1 2 3 4 5")
  (setq opc (getkword "\nInforme a opção [1/2/3/4/5] <1>: "))
  (if (or (null opc) (= opc "")) (setq opc "1"))

  (cond
    ((= opc "1")
     (setq txt (strcat
       "\\A1;{\\fSegoe UI|b1;NOTA TÉCNICA - PARTICIPAÇÃO FINANCEIRA (ARTS. 98 E 99 DA REN ANEEL 1.000/2021):}\n"
       "A PRESENTE SOLICITAÇÃO ENQUADRA-SE NOS TERMOS DO ART. 98 (INCISOS I A IV E § 3º) E ART. 99 (INCISOS I E II) "
       "DA RESOLUÇÃO NORMATIVA ANEEL Nº 1.000/2021. HAVENDO DISCREPÂNCIA ENTRE A CARGA INSTALADA DECLARADA (kW) E A "
       "PROTEÇÃO GERAL REQUERIDA (DISJUNTOR) OU OPÇÃO POR CONEXÃO POLIFÁSICA FORA DO PADRÃO TÉCNICO NORMATIVO, CABE AO "
       "SOLICITANTE O CUSTEIO DAS INSTALAÇÕES INTERNAS, SISTEMA DE MEDIÇÃO DIFERENCIADO, ADAPTAÇÕES DE REDE E A "
       "PARTICIPAÇÃO FINANCEIRA CALCULADA CONFORME REGULAÇÃO VIGENTE."
     )))
    ((= opc "2")
     (setq txt (strcat
       "\\A1;{\\fSegoe UI|b1;NOTA TÉCNICA - PARTICIPAÇÃO FINANCEIRA (ARTS. 104 E 106 DA REN ANEEL 1.000/2021 / REN 1.059/2023):}\n"
       "A UNIDADE CONSUMIDORA NÃO ATENDE INTEGRALMENTE AOS REQUISITOS CUMULATIVOS DE GRATUIDADE DO ART. 104 DA REN Nº 1.000/2021 "
       "(CARGA INSTALADA SUPERIOR A 50 kW, EXISTÊNCIA DE OUTRA UC NA PROPRIEDADE OU ENQUADRAMENTO NO § 2º). APLICAM-SE O "
       "ART. 106 E ART. 108, SENDO CALCULADOS O ENCARGO DE RESPONSABILIDADE DA DISTRIBUIDORA (ERD) E A PARTICIPAÇÃO "
       "FINANCEIRA DO CONSUMIDOR (PF) PELO CUSTO PROPORCIONALIZADO DA OBRA (COP)."
     )))
    ((= opc "3")
     (setq txt (strcat
       "\\A1;{\\fSegoe UI|b1;NOTA TÉCNICA - PARTICIPAÇÃO FINANCEIRA (ARTS. 105 E 106 DA REN ANEEL 1.000/2021 / REN 1.059/2023):}\n"
       "SOLICITAÇÃO DE AUMENTO DE CARGA NÃO ENQUADRADA NA GRATUIDADE DO ART. 105 DA REN Nº 1.000/2021 POR RESULTAR EM CARGA "
       "INSTALADA TOTAL SUPERIOR A 50 kW E/OU EXIGIR COMPLEMENTAÇÃO DE FASE(S) EM REDE DE TENSÃO MAIOR OU IGUAL A 2,3 kV (MT). "
       "CONFORME ART. 106, INCISO I, PROCEDEU-SE AO CÁLCULO DA PARTICIPAÇÃO FINANCEIRA DO CONSUMIDOR CONFORME PLANILHA CPFC EM ANEXO."
     )))
    ((= opc "4")
     (setq txt (strcat
       "\\A1;{\\fSegoe UI|b1;NOTA TÉCNICA - OBRAS A PEDIDO DE TERCEIROS (ART. 110 DA REN ANEEL 1.000/2021):}\n"
       "OBRA EXECUTADA A PEDIDO DO CONSUMIDOR / INTERESSADO PARA DESLOCAMENTO/REMOÇÃO DE POSTE E REDE OU MELHORIA DE ASPECTOS "
       "ESTÉTICOS/INTERESSE RESTRITO, NOS TERMOS DO ART. 110 (INCISOS I A VIII E § 1º) DA REN ANEEL Nº 1.000/2021. OS CUSTOS "
       "INTEGRAIS DO SERVIÇO, INCLUINDO EVENTUAIS REFORMAS DE CAPACIDADE OU ADEQUAÇÕES NECESSÁRIAS NA REDE, SÃO DE "
       "RESPONSABILIDADE EXCLUSIVA DO SOLICITANTE."
     )))
    ((= opc "5")
     (setq txt (strcat
       "\\A1;{\\fSegoe UI|b1;NOTAS TÉCNICAS REGULATÓRIAS - PARTICIPAÇÃO FINANCEIRA (CPFC - REN 1.000 / 1.059):}\n"
       "1. CARGA X DISJUNTOR (ARTS. 98/99): CUSTEIO PELO SOLICITANTE CASO A PROTEÇÃO GERAL REQUERIDA SUPERE A DEMANDA NORMATIVA.\n"
       "2. LIGAÇÃO NOVA > 50 kW (ARTS. 104/106): CONEXÃO FORA DA GRATUIDADE, COM CÁLCULO DE ERD E COP (PF > 0).\n"
       "3. ACRÉSCIMO DE CARGA (ARTS. 105/106): CARGA TOTAL > 50 kW E/OU COMPLEMENTAÇÃO DE FASE EM MÉDIA TENSÃO (>= 2,3 kV).\n"
       "4. OBRAS DE TERCEIROS (ART. 110): DESLOCAMENTO DE REDE/POSTE COM CUSTEIO INTEGRAL PELO SOLICITANTE."
     )))
  )

  (setq pt (getpoint "\nClique no ponto de inserção da Nota Técnica na prancha: "))
  (if pt
    (progn
      (cpfc-garantir-layer "NOTAS_CPFC" 4) ; Cor 4 (Ciano)
      (setq larg 180.0)
      (setq alt 2.0)
      (setq acadObj (vlax-get-acad-object))
      (setq doc (vla-get-ActiveDocument acadObj))
      (setq mspace (vla-get-ModelSpace doc))
      (setq mtextObj (vla-AddMText mspace (vlax-3d-point pt) larg txt))
      (vla-put-Height mtextObj alt)
      (vla-put-Layer mtextObj "NOTAS_CPFC")
      (princ "\n[CPFC] Nota Técnica inserida com sucesso no layer NOTAS_CPFC!")
    )
    (princ "\n[CPFC] Inserção cancelada pelo usuário.")
  )
  (princ)
)

(defun c:NOTAS_CPFC () (c:CPFC_NOTAS))

(princ "\n[CPFC] Rotina carregada! Comandos: CPFC, CPFCUI, CPFCALERTA e CPFC_NOTAS.")
(princ)
