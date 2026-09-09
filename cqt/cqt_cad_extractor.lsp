;; ============================================================
;;  cqt_cad_extractor.lsp
;;  Automação para Cálculo de Queda de Tensão (CQT) em BT.
;;  Suporta:
;;   - Seleção gráfica de vãos no AutoCAD (soma automática)
;;   - Inserção Manual de metragens e vãos diretamente no prompt
;;   - Escolha do local de destino para salvar a planilha .xlsm
;;   - Disparo da Interface Gráfica interativa
;;
;;  Comando: CQTCAD
;; ============================================================

(vl-load-com)

;; Compatibilidade para checagem de tipo string
(defun stringp (x) (= (type x) 'STR))

;; Função auxiliar para calcular o comprimento exato de qualquer entidade linear
(defun get-curve-length (ent / obj len data)
  (setq data (entget ent))
  (cond
    ;; Linha comum (LINE)
    ((= (cdr (assoc 0 data)) "LINE")
     (distance (cdr (assoc 10 data)) (cdr (assoc 11 data)))
    )
    ;; Polilinha ou Curva (LWPOLYLINE, POLYLINE, ARC, SPLINE)
    (T
     (setq obj (vlax-ename->vla-object ent))
     (vl-catch-all-apply 'vlax-curve-getDistAtParam
       (list obj (vlax-curve-getEndParam obj))
     )
    )
  )
)

;; Comando Principal
(defun c:CQTCAD (/ num_proj ponto_trafo pot_trafo cenario_opt cenario_txt modo has_lines default_modo
                  letras idx letra montante_padrao montante ss i ent d_len total_comp qtd_vaos
                  continuar opt_m ans trechos_list temp_dir json_file py_script xlsm_file cmd
                  dest_file ans_dest f tr wsh root)

  (princ "\n=======================================================")
  (princ "\n  EXTRATOR DE VÃOS E TOPOLOGIA DE CQT - BAIXA TENSÃO   ")
  (princ "\n=======================================================")

  ;; 1. Informações do Projeto e Transformador
  (setq num_proj (getstring "\nDigite o Número do Projeto/Ordem [ex: A057100646]: "))
  (if (or (null num_proj) (= num_proj "")) (setq num_proj "A057100646"))

  (setq ponto_trafo (getstring "\nDigite o Ponto Elétrico do Trafo [ex: A55323]: "))
  (if (or (null ponto_trafo) (= ponto_trafo "")) (setq ponto_trafo "A55323"))

  (setq pot_trafo (getstring "\nDigite a Potência do Trafo em kVA [10/15/30/45/75/112.5/150] <45>: "))
  (if (or (null pot_trafo) (= pot_trafo "")) (setq pot_trafo "45"))

  ;; 2. Escolha do Cenário Inicial
  (initget "Atual Atual+NC Projetado A N P")
  (setq cenario_opt (getkword "\nEscolha o Cenário para preenchimento: [A]tual / [N] Atual+NC / [P]rojetado <Atual>: "))
  (cond
    ((or (= cenario_opt "Atual+NC") (= cenario_opt "N")) (setq cenario_txt "ATUAL+NC"))
    ((or (= cenario_opt "Projetado") (= cenario_opt "P")) (setq cenario_txt "PROJETADO"))
    (T (setq cenario_txt "ATUAL"))
  )

  ;; 3. Escolha do Modo de Trabalho (Detecta se o desenho possui linhas/polilinhas)
  (setq has_lines (ssget "X" '((0 . "LINE,LWPOLYLINE,POLYLINE,ARC"))))
  (setq default_modo (if (and has_lines (> (sslength has_lines) 0)) "Desenho" "Interface"))
  (if (= default_modo "Interface")
    (princ "\n[INFO] Desenho sem linhas ou polilinhas detectadas. Sugestão: Interface direta para estudo prévio.")
  )

  (initget "Desenho Manual Interface D M I")
  (setq modo (getkword (strcat "\nEscolha o modo de trabalho: [D]esenho (selecionar vãos) / [M]anual (digitar metragens) / [I]nterface direta <" default_modo ">: ")))
  (if (or (null modo) (= modo "")) (setq modo default_modo))

  (setq letras '("A" "B" "C" "D" "E" "F" "G" "H" "I" "J" "K" "L" "M" "N" "O" "P" "Q" "R" "S" "T" "U" "V" "W" "X" "Y" "Z"))
  (setq idx 0)
  (setq trechos_list '())
  (setq continuar T)

  ;; Se o usuário optou por abrir a interface direta, não entra no loop de trechos
  (if (or (= modo "Interface") (= modo "I"))
    (setq continuar nil)
  )

  ;; 3. Loop de Captura de Trechos
  (while (and continuar (< idx (length letras)))
    (setq letra (nth idx letras))
    (setq montante_padrao (if (= idx 0) "TRAFO" (nth (1- idx) letras)))
    (setq total_comp 0.0)
    (setq qtd_vaos 1)

    (princ (strcat "\n\n>>> DEFININDO TRECHO " letra " <<<"))

    (if (or (= modo "Manual") (= modo "M"))
      ;; MODO 100% MANUAL
      (progn
        (setq total_comp (getdist (strcat "\nInforme o comprimento do Trecho " letra " em metros: ")))
        (if (and total_comp (> total_comp 0.0))
          (progn
            (setq qtd_vaos (getint (strcat "\nInforme a quantidade de vãos do Trecho " letra " <1>: ")))
            (if (or (null qtd_vaos) (<= qtd_vaos 0)) (setq qtd_vaos 1))
          )
          (setq total_comp nil)
        )
      )
      ;; MODO SELEÇÃO NO DESENHO (COM FALLBACK PARA DIGITAÇÃO MANUAL)
      (progn
        (princ "\nSelecione os vãos deste trecho no desenho [ou pressione Enter para opções]: ")
        (setq ss (ssget '((0 . "LINE,LWPOLYLINE,POLYLINE,ARC"))))

        (if (and ss (> (sslength ss) 0))
          (progn
            (setq total_comp 0.0)
            (setq qtd_vaos (sslength ss))
            (setq i 0)
            (while (< i qtd_vaos)
              (setq ent (ssname ss i))
              (setq d_len (get-curve-length ent))
              (if (and d_len (numberp d_len))
                (setq total_comp (+ total_comp d_len))
              )
              (setq i (1+ i))
            )
          )
          (progn
            ;; Se não selecionou nada, oferece digitar manualmente
            (initget "Manual Encerrar M E")
            (setq opt_m (getkword "\nNenhum vão selecionado. Deseja [M]anual (digitar metragem) ou [E]ncerrar trechos? <Manual>: "))
            (if (or (null opt_m) (= opt_m "Manual") (= opt_m "M"))
              (progn
                (setq total_comp (getdist (strcat "\nInforme o comprimento do Trecho " letra " em metros: ")))
                (if (and total_comp (> total_comp 0.0))
                  (progn
                    (setq qtd_vaos (getint (strcat "\nInforme a quantidade de vãos do Trecho " letra " <1>: ")))
                    (if (or (null qtd_vaos) (<= qtd_vaos 0)) (setq qtd_vaos 1))
                  )
                  (setq total_comp nil)
                )
              )
              (setq total_comp nil)
            )
          )
        )
      )
    )

    (if (and total_comp (> total_comp 0.0))
      (progn
        (princ (strcat "\n-> Trecho " letra ": " (itoa qtd_vaos) " vão(s). Comprimento Total = " (rtos total_comp 2 2) " metros."))

        ;; Pergunta o Trecho Montante (permite bifurcações e ramais)
        (setq montante (getstring (strcat "\nInforme o Trecho Montante de onde deriva o Trecho " letra " [Padrão: " montante_padrao "]: ")))
        (if (or (null montante) (= montante "")) (setq montante montante_padrao))
        (setq montante (strcase montante))

        ;; Guarda os dados do trecho na lista
        (setq trechos_list
          (cons
            (list
              (cons "letra" letra)
              (cons "montante" montante)
              (cons "vaos" qtd_vaos)
              (cons "comp" total_comp)
            )
            trechos_list
          )
        )

        (setq idx (1+ idx))

        ;; Pergunta se deseja adicionar o próximo trecho
        (if (< idx (length letras))
          (progn
            (initget "Sim Nao S N")
            (setq ans (getkword (strcat "\nDeseja adicionar o próximo trecho (Trecho " (nth idx letras) ")? [Sim/Nao] <Sim>: ")))
            (if (or (= ans "Nao") (= ans "N"))
              (setq continuar nil)
            )
          )
        )
      )
      (setq continuar nil)
    )
  )

  ;; 4. Escolha do Local Onde Salvar o Excel Preenchido (Opcional)
  (setq dest_file "")
  (initget "Sim Nao S N")
  (setq ans_dest (getkword "\nDeseja escolher a pasta/arquivo para salvar o Excel CQT? [Sim/Nao] <Sim>: "))
  (if (or (null ans_dest) (= ans_dest "Sim") (= ans_dest "S"))
    (progn
      (setq dest_file (getfiled "Salvar Planilha CQT Preenchida Como" (strcat "CQT_" num_proj ".xlsm") "xlsm" 1))
      (if (null dest_file) (setq dest_file ""))
    )
  )

  ;; 5. Montagem do JSON de Intercâmbio e Execução da Interface
  ;; Gera nome de arquivo temporário atômico garantido pelo Visual LISP
  (setq json_file (vl-filename-mktemp "cqt_cad_input.json"))

  ;; Localiza o script Python do gerenciador CQT
  (if (boundp '*aux-cad-root*)
    (setq py_script (strcat *aux-cad-root* "cqt\\cqt_excel_manager.py"))
    (setq py_script (findfile "cqt\\cqt_excel_manager.py"))
  )
  (if (or (null py_script) (not (findfile py_script)))
    (setq py_script (findfile "cqt_excel_manager.py"))
  )
  (if (or (null py_script) (not (findfile py_script)))
    (setq py_script "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\cqt\\cqt_excel_manager.py")
  )

  (setq xlsm_file "G:\\Meu Drive\\1-HBT\\HBT\\SETEMBRO\\CQT TRECHO.xlsm")

  (setq trechos_list (reverse trechos_list))

  ;; Garante que dest_file seja string válida
  (if (or (null dest_file) (/= (type dest_file) 'STR))
    (setq dest_file "")
  )

  ;; Grava o JSON de intercâmbio de forma protegida
  (setq f (open json_file "w"))
  (if f
    (progn
      (write-line "{" f)
      (write-line (strcat "  \"projeto\": \"" num_proj "\",") f)
      (write-line (strcat "  \"ponto_trafo\": \"" ponto_trafo "\",") f)
      (write-line (strcat "  \"potencia_trafo\": \"" pot_trafo "\",") f)
      (write-line (strcat "  \"cenario\": \"" cenario_txt "\",") f)
      (write-line (strcat "  \"salvar_em\": \"" (vl-string-translate "\\" "/" dest_file) "\",") f)
      (write-line "  \"trechos\": [" f)

      (setq i 0)
      (while (< i (length trechos_list))
        (setq tr (nth i trechos_list))
        (write-line
          (strcat
            "    {\"letra\": \"" (cdr (assoc "letra" tr)) "\", "
            "\"montante\": \"" (cdr (assoc "montante" tr)) "\", "
            "\"vaos\": " (itoa (cdr (assoc "vaos" tr))) ", "
            "\"comprimento_m\": " (rtos (cdr (assoc "comp" tr)) 2 2) "}"
            (if (< (1+ i) (length trechos_list)) "," "")
          )
          f
        )
        (setq i (1+ i))
      )
      (write-line "  ]" f)
      (write-line "}" f)
      (close f)
      (princ (strcat "\n[INFO] Parâmetros exportados com sucesso para: " json_file))
    )
    (princ (strcat "\n[AVISO] Falha ao criar arquivo de troca: " json_file))
  )

  (princ "\nAbrindo Interface Gráfica do CQT...")

  ;; Disparo infalível e independente via startapp (idêntico ao CQTUI)
  (if (and dest_file (/= dest_file ""))
    (setq cmd (strcat "/c start \"\" python \"" py_script "\" \"" xlsm_file "\" \"" json_file "\" \"" dest_file "\""))
    (setq cmd (strcat "/c start \"\" python \"" py_script "\" \"" xlsm_file "\" \"" json_file "\""))
  )
  (startapp "cmd.exe" cmd)

  (princ)
)

;; ============================================================
;;  Comando Rápido: CQT / CQTUI
;;  Abre diretamente a interface gráfica interativa do CQT
;;  Ideal para estudos preliminares de viabilidade sem desenho.
;; ============================================================
(defun c:CQTUI (/ py_script xlsm_file cmd)
  (princ "\nAbrindo Gerenciador CQT para estudo prévio...")
  (if (boundp '*aux-cad-root*)
    (setq py_script (strcat *aux-cad-root* "cqt\\cqt_excel_manager.py"))
    (setq py_script (findfile "cqt\\cqt_excel_manager.py"))
  )
  (if (or (null py_script) (not (findfile py_script)))
    (setq py_script "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\cqt\\cqt_excel_manager.py")
  )
  (setq xlsm_file "G:\\Meu Drive\\1-HBT\\HBT\\SETEMBRO\\CQT TRECHO.xlsm")
  (setq cmd (strcat "/c start \"\" python \"" py_script "\" \"" xlsm_file "\""))
  (startapp "cmd.exe" cmd)
  (princ)
)

(defun c:CQT ()
  (c:CQTUI)
)

;; ============================================================
;;  Comando: CQTQUADROS / CQTEXCEL
;;  Carrega e executa a rotina gerada para desenhar os quadros:
;;  - Quadro de Resumo do Trafo (47.03 x 47.10 - Verde)
;;  - Quadros de CQT por Trecho (33.21 x 13.64 - Vermelho)
;;  Suporta:
;;   - Selecionar planilha Excel existente (.xlsx / .xlsm)
;;   - Usar últimos quadros gerados em C:\Temp\cqt_draw_quadros.lsp
;; ============================================================
(defun c:CQTQUADROS (/ lsp_file py_script opc xls_path pt_trafo tmp_log cmd wsh fp l msg_err t0)
  (setq lsp_file "C:\\Temp\\cqt_draw_quadros.lsp")

  ;; Localiza o script Python gerador de quadros
  (setq py_script (findfile "cqt_quadros_generator.py"))
  (if (not py_script)
    (if (boundp '*aux-cad-root*)
      (setq py_script (strcat *aux-cad-root* "cqt\\cqt_quadros_generator.py"))
    )
  )
  (if (not (and py_script (findfile py_script)))
    (setq py_script "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\cqt\\cqt_quadros_generator.py")
  )

  ;; Pergunta se deseja selecionar planilha Excel existente ou usar o último gerado
  (initget "Selecionar Usar S U")
  (if (findfile lsp_file)
    (setq opc (getkword "\n[CQTQUADROS] Desenhar a partir de: [S]elecionar planilha Excel / [U]sar últimos quadros em C:\\Temp <Selecionar>: "))
    (setq opc "S")
  )
  (if (or (null opc) (= opc "") (= opc "S") (= opc "Selecionar"))
    (progn
      ;; Diálogo nativo do Windows para selecionar a planilha (flag 16 garante caminho absoluto completo)
      (setq cur_dir (getvar "DWGPREFIX"))
      (if (null cur_dir) (setq cur_dir ""))
      (setq xls_path (getfiled "Selecione a Planilha CQT (.xlsx ou .xlsm)" cur_dir "xlsx;xlsm" 16))
      (if (and xls_path (/= xls_path ""))
        (progn
          ;; Garante caminho absoluto completo caso o AutoCAD tenha retornado caminho relativo
          (cond
            ((findfile xls_path)
             (setq xls_path (findfile xls_path)))
            ((and (/= cur_dir "") (findfile (strcat cur_dir xls_path)))
             (setq xls_path (findfile (strcat cur_dir xls_path))))
          )

          (setq pt_trafo (getstring "\nPonto Elétrico do Trafo [ou Enter para detectar automaticamente]: "))
          (if (or (null pt_trafo) (= pt_trafo "")) (setq pt_trafo "auto"))

          (princ (strcat "\n[CQTQUADROS] Extraindo dados da planilha: " (vl-filename-base xls_path) (vl-filename-extension xls_path) " ..."))

          ;; Prepara execução via WScript.Shell
          (setq tmp_log (vl-filename-mktemp "cqt_log_" nil ".txt"))
          (setq cmd (strcat "python \"" py_script "\" \"" xls_path "\" \"" pt_trafo "\" > \"" tmp_log "\" 2>&1"))

          ;; Remove o lsp anterior para ter certeza do novo
          (if (findfile lsp_file) (vl-file-delete lsp_file))

          (setq wsh (vl-catch-all-apply 'vlax-create-object (list "WScript.Shell")))
          (if (and wsh (not (vl-catch-all-error-p wsh)))
            (progn
              (vl-catch-all-apply 'vlax-invoke-method (list wsh "Run" (strcat "cmd.exe /c " cmd) 0 :vlax-true))
              (vlax-release-object wsh)
            )
            (progn
              (startapp "cmd.exe" (strcat "/c " cmd))
              (setq t0 (getvar "MILLISECS"))
              (while (and (not (findfile lsp_file)) (< (- (getvar "MILLISECS") t0) 8000))
              )
            )
          )

          (if (findfile lsp_file)
            (progn
              (princ "\n[CQTQUADROS] Dados extraídos com sucesso! Carregando rotina gráfica...")
              (load lsp_file)
              (if (and (boundp 'cqt-exec-draw-quadros) (fboundp 'cqt-exec-draw-quadros))
                (cqt-exec-draw-quadros)
                (c:CQTQUADROS)
              )
            )
            (progn
              (setq msg_err "")
              (if (findfile tmp_log)
                (progn
                  (setq fp (open tmp_log "r"))
                  (while (setq l (read-line fp))
                    (setq msg_err (strcat msg_err l "\n"))
                  )
                  (close fp)
                )
              )
              (alert (strcat "Erro ao processar planilha Excel:\n\n" (if (/= msg_err "") msg_err "Verifique se o arquivo possui as abas ATUAL / CQT ATUAL.")))
            )
          )
        )
        (princ "\n[CQTQUADROS] Operação cancelada pelo usuário.")
      )
    )
    (progn
      ;; Opção [U]: Usar o arquivo lsp existente
      (if (findfile lsp_file)
        (progn
          (princ "\n[CQTQUADROS] Carregando últimos quadros gerados em C:\\Temp\\cqt_draw_quadros.lsp...")
          (load lsp_file)
          (if (and (boundp 'cqt-exec-draw-quadros) (fboundp 'cqt-exec-draw-quadros))
            (cqt-exec-draw-quadros)
            (c:CQTQUADROS)
          )
        )
        (princ "\n[AVISO] Nenhum quadro gerado anteriormente foi encontrado.")
      )
    )
  )
  (princ)
)

;; Aliases diretos para desenhar quadros a partir do Excel
(defun c:CQTEXCEL () (c:CQTQUADROS))
(defun c:CQTQUADROS_EXCEL () (c:CQTQUADROS))

;; Comando para forçar recarga imediata da rotina na sessão atual do AutoCAD
(defun c:RECARREGAR_CQT ()
  (load "cqt\\cqt_cad_extractor.lsp")
  (princ "\n[CQT] Rotina CQTCAD recarregada na memória do AutoCAD!")
  (princ)
)

(princ "\nRotinas de Queda de Tensão (CQT) carregadas com sucesso!")
(princ "\n  - CQTCAD     : Medir vãos no desenho ou inserir via prompt")
(princ "\n  - CQT / CQTUI: Abrir diretamente a Interface (desenho vazio / estudo prévio)")
(princ "\n  - CQTQUADROS : Desenhar os Quadros de Resumo e CQT (a partir de Excel ou gerador)")
(princ "\n  - CQTEXCEL   : Atalho para selecionar planilha Excel e desenhar quadros")
(princ "\n  - RECARREGAR_CQT : Recarregar a rotina na sessão atual")
(princ)
