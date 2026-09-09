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

(princ "\n[CPFC] Rotina carregada! Digite CPFC, CPFCUI ou CPFCALERTA.")
(princ)
