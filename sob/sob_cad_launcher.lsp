;;; =============================================================================
;;; sob_cad_launcher.lsp
;;; Automação de Preparação de Projeto SOB integrada ao AutoCAD
;;; Comandos: SOB, NOVASOB, PREPARAR_SOB, RECARREGAR_SOB
;;; =============================================================================

(vl-load-com)

;; Compatibilidade para checagem de tipo string
(if (not (fboundp 'stringp))
  (defun stringp (x) (= (type x) 'STR))
)

;; Normalização do número da SOB no AutoLISP
(defun sob-normalizar-str (str / s)
  (if (or (null str) (/= (type str) 'STR))
    ""
    (progn
      (setq s (vl-string-trim " \t\r\n" (strcase str)))
      (while (and (>= (strlen s) 4) (= (substr s 1 4) "SOB_"))
        (setq s (vl-string-trim " \t\r\n" (substr s 5)))
      )
      (if (/= s "")
        (strcat "SOB_" s)
        ""
      )
    )
  )
)

;; Extrai código limpo sem SOB_
(defun sob-extrair-codigo (str / norm)
  (setq norm (sob-normalizar-str str))
  (if (> (strlen norm) 4)
    (substr norm 5)
    norm
  )
)

;; Localiza o script Python do gerenciador SOB
(defun sob-localizar-script (/ pyScript)
  (setq pyScript nil)
  (if (and (boundp '*aux-cad-root*) *aux-cad-root*)
    (setq pyScript (findfile (strcat *aux-cad-root* "sob\\sob_manager.py")))
  )
  (if (not pyScript)
    (setq pyScript (findfile "sob\\sob_manager.py"))
  )
  (if (not pyScript)
    (setq pyScript (findfile "sob_manager.py"))
  )
  (if (not pyScript)
    (setq pyScript "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\sob\\sob_manager.py")
  )
  pyScript
)

;; Comando Principal: SOB (Aliases: NOVASOB, PREPARAR_SOB)
(defun c:SOB (/ acadApp doc sobInput sobNormalizada sh folder destPath sobRoot
                jsonFile logFile pyScript cmd wsh resJson f_json line_json
                dwgTarget f_log line_log log_txt erro_msg)

  (setq acadApp (vlax-get-acad-object))
  (setq doc (vla-get-ActiveDocument acadApp))

  (princ "\n==============================================================")
  (princ "\n       PREPARAÇÃO AUTOMÁTICA DE PROJETO SOB (AUX CAD)         ")
  (princ "\n==============================================================")

  ;; 1. Solicitação do Número da SOB
  (setq sobInput (getstring "\nInforme o número da SOB: "))
  (if (or (null sobInput) (= (vl-string-trim " " sobInput) ""))
    (progn
      (princ "\n[AVISO] Operação cancelada: nenhuma SOB informada.")
      (exit)
    )
  )

  ;; 2. Normalização e Validação
  (setq sobNormalizada (sob-normalizar-str sobInput))
  (if (or (= sobNormalizada "") (<= (strlen sobNormalizada) 4))
    (progn
      (princ "\n[ERRO] Número de SOB inválido. Operação interrompida.")
      (alert "Número de SOB inválido. Operação interrompida.")
      (exit)
    )
  )
  (princ (strcat "\n[INFO] SOB identificada: " sobNormalizada))

  ;; 3. Seleção do Diretório de Destino (Diálogo Nativo Windows)
  (princ "\n[INFO] Selecione onde a pasta da SOB deverá ser criada...")
  (setq destPath nil)
  (setq sh (vl-catch-all-apply 'vlax-create-object (list "Shell.Application")))
  (if (and sh (not (vl-catch-all-error-p sh)))
    (progn
      (setq folder (vl-catch-all-apply 'vlax-invoke-method
                     (list sh "BrowseForFolder" 0 "Selecione onde a pasta da SOB deverá ser criada." 0)))
      (if (and folder (not (vl-catch-all-error-p folder)))
        (setq destPath (vlax-get-property (vlax-get-property folder 'Self) 'Path))
      )
      (vlax-release-object sh)
    )
  )

  (if (or (null destPath) (= destPath ""))
    (progn
      (princ "\n[AVISO] Operação cancelada pelo usuário (diretório não selecionado).")
      (exit)
    )
  )
  (princ (strcat "\n[INFO] Diretório selecionado: " destPath))

  ;; 4. Proteção contra SOB Existente (NÃO SOBRESCREVER / NÃO APAGAR / NÃO MISTURAR)
  (setq sobRoot (strcat destPath "\\" sobNormalizada))
  (if (vl-file-directory-p sobRoot)
    (progn
      (princ "\n==============================================================")
      (princ "\n[AVISO] A pasta da SOB já existe no local selecionado.")
      (princ "\nNenhum arquivo foi sobrescrito.")
      (princ "\n==============================================================")
      (alert (strcat "A pasta da SOB já existe no local selecionado.\n"
                     "Nenhum arquivo foi sobrescrito.\n\n"
                     "Pasta: " sobRoot))
      (exit)
    )
  )

  ;; 5. Arquivos de Intercâmbio e Log Protegidos
  (setq jsonFile (vl-filename-mktemp "sob_out.json"))
  (setq logFile  (vl-filename-mktemp "sob_log.txt"))
  (setq pyScript (sob-localizar-script))

  (if (not (findfile pyScript))
    (progn
      (princ (strcat "\n[ERRO] Script Python não encontrado em: " pyScript))
      (alert (strcat "Script de automação não localizado:\n" pyScript))
      (exit)
    )
  )

  ;; 6. Execução do Orquestrador Python em Segundo Plano
  (princ "\n[INFO] Acessando SharePoint e preparando projeto...")
  (setq cmd (strcat "py \"" pyScript "\" --sob \"" sobNormalizada "\" --destino \"" destPath "\" --json-out \"" jsonFile "\" > \"" logFile "\" 2>&1"))

  (setq wsh (vl-catch-all-apply 'vlax-create-object (list "WScript.Shell")))
  (if (and wsh (not (vl-catch-all-error-p wsh)))
    (progn
      (vl-catch-all-apply 'vlax-invoke-method (list wsh "Run" (strcat "cmd.exe /c " cmd) 0 :vlax-true))
      (vlax-release-object wsh)
    )
    (progn
      (startapp "cmd.exe" (strcat "/c " cmd))
      (command "_.DELAY" "4000")
    )
  )

  ;; 7. Verificação do Resultado
  (setq dwgTarget (strcat sobRoot "\\BASE_SOB_DESENHO.dwg"))

  (if (and (findfile dwgTarget) (> (vl-file-size dwgTarget) 100))
    (progn
      (princ "\n==============================================================")
      (princ (strcat "\n✔ PROJETO " sobNormalizada " PREPARADO COM SUCESSO!"))
      (princ (strcat "\nArquivo: " dwgTarget))
      (princ "\n==============================================================")

      ;; 8. Abertura do Arquivo no AutoCAD
      (princ "\n[INFO] Abrindo BASE_SOB_DESENHO.dwg no AutoCAD...")
      (vl-catch-all-apply 'vla-open (list (vla-get-Documents acadApp) dwgTarget))
      (alert (strcat "Preparação de Projeto Concluída com Sucesso!\n\n"
                     "SOB: " sobNormalizada "\n"
                     "Pasta: " sobRoot "\n"
                     "Arquivo: BASE_SOB_DESENHO.dwg\n\n"
                     "O desenho foi aberto no AutoCAD."))
    )
    (progn
      ;; Em caso de falha, lê o log para exibir mensagem exata ao usuário
      (setq log_txt "")
      (if (findfile logFile)
        (progn
          (setq f_log (open logFile "r"))
          (while (and (setq line_log (read-line f_log)) (< (strlen log_txt) 800))
            (setq log_txt (strcat log_txt line_log "\n"))
          )
          (close f_log)
        )
      )

      ;; Lê JSON de resposta se disponível
      (setq erro_msg "")
      (if (findfile jsonFile)
        (progn
          (setq f_json (open jsonFile "r"))
          (while (setq line_json (read-line f_json))
            (if (vl-string-search "\"mensagem\":" line_json)
              (setq erro_msg line_json)
            )
          )
          (close f_json)
        )
      )

      (princ "\n==============================================================")
      (princ "\n[ERRO NA PREPARAÇÃO DA SOB]")
      (if (/= log_txt "")
        (princ (strcat "\n" log_txt))
        (princ (strcat "\n" erro_msg))
      )
      (princ "\n==============================================================")

      (alert (strcat "Falha na preparação da SOB:\n\n"
                     (if (/= log_txt "") log_txt "Consulte a janela de texto do AutoCAD (F2).")))
    )
  )

  (princ)
)

;; Aliases do Comando
(defun c:NOVASOB () (c:SOB))
(defun c:PREPARAR_SOB () (c:SOB))

;; Comando de Recarregamento Rápido
(defun c:RECARREGAR_SOB ()
  (setq _f (sob-localizar-script))
  (setq _lsp (findfile "sob\\sob_cad_launcher.lsp"))
  (if (not _lsp) (setq _lsp (findfile "sob_cad_launcher.lsp")))
  (if _lsp
    (progn
      (load _lsp)
      (princ "\n[SUCESSO] Rotina SOB recarregada com sucesso!")
    )
    (princ "\n[AVISO] Arquivo sob_cad_launcher.lsp não encontrado.")
  )
  (princ)
)

(princ "\n[SOB] Módulo de Preparação de SOB carregado! Digite SOB ou NOVASOB para iniciar.")
(princ)
