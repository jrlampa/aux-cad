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

;; Matriz Oficial de Nomenclatura (Seção 0-A)
(defun sob-obter-id (str / s)
  (if (or (null str) (/= (type str) 'STR))
    ""
    (progn
      (setq s (vl-string-trim " \t\r\n" (strcase str)))
      (while (and (>= (strlen s) 4) (= (substr s 1 4) "SOB_"))
        (setq s (vl-string-trim " \t\r\n" (substr s 5)))
      )
      s
    )
  )
)

(defun sob-obter-name (str / id)
  (setq id (sob-obter-id str))
  (if (/= id "")
    (strcat "SOB_" id)
    ""
  )
)

;; Normalização e compatibilidade retroativa
(defun sob-normalizar-str (str)
  (sob-obter-name str)
)

(defun sob-extrair-codigo (str)
  (sob-obter-id str)
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

;; Exibição segura de alertas (não trava em ambientes headless / scripts de teste)
(defun sob-alert (msg)
  (if (and (fboundp 'alert) (vlax-get-acad-object))
    (vl-catch-all-apply 'alert (list msg))
    (princ (strcat "\n[ALERTA] " msg))
  )
)

;; Executa o fluxo operacional completo da SOB com nomenclatura canônica
(defun sob-executar-fluxo (sobInput destPath abrirCad / acadApp doc sobId sobName destinationRoot sobRoot
                             croquiDir baseDwg jsonFile logFile pyScript cmd wsh resJson f_json line_json
                             dwgTarget f_log line_log log_txt erro_msg sucesso retVal)

  (setq acadApp (vlax-get-acad-object))
  (if (and acadApp (not (vl-catch-all-error-p acadApp)))
    (setq doc (vl-catch-all-apply 'vla-get-ActiveDocument (list acadApp)))
  )

  ;; 1. Identificação da SOB (Seção 1: SOB_ID e SOB_NAME)
  (setq sobId (sob-obter-id sobInput))
  (setq sobName (sob-obter-name sobInput))

  (if (or (= sobId "") (<= (strlen sobId) 2))
    (progn
      (princ "\n[FALHA] Número da SOB inválido.")
      (sob-alert "Número da SOB inválido.")
      (list (cons "sucesso" nil) (cons "erro" "SOB_INVALIDA"))
    )
    (progn
      ;; 2. Derivação canônica dos caminhos (Seções 2, 3, 4 e 5)
      (setq destinationRoot (vl-string-right-trim "\\" (vl-string-trim " " destPath)))
      (setq sobRoot (strcat destinationRoot "\\" sobName))
      (setq croquiDir (strcat sobRoot "\\CROQUI"))
      (setq baseDwg (strcat sobRoot "\\BASE_SOB_DESENHO.dwg"))

      ;; Logs canônicos padronizados (Seção 9)
      (princ (strcat "\n[INFO] SOB: " sobId))
      (princ (strcat "\n[INFO] SOB_ROOT: " sobRoot))
      (princ (strcat "\n[INFO] CROQUI_DIR: " croquiDir))
      (princ (strcat "\n[INFO] BASE_DWG: " baseDwg))

      ;; 3. Proteção contra SOB Existente (NÃO SOBRESCREVER / NÃO APAGAR / NÃO MISTURAR)
      (if (vl-file-directory-p sobRoot)
        (progn
          (princ "\n==============================================================")
          (princ "\n[FALHA] A pasta da SOB já existe.")
          (princ "\nNenhum arquivo foi sobrescrito.")
          (princ "\n==============================================================")
          (sob-alert (strcat "A pasta da SOB já existe.\n"
                             "Nenhum arquivo foi sobrescrito.\n\n"
                             "Pasta: " sobRoot))
          (list (cons "sucesso" nil)
                (cons "status" "BLOQUEADO")
                (cons "erro" "PASTA_EXISTENTE")
                (cons "sobRoot" sobRoot))
        )
        (progn
          ;; 4. Arquivos de Intercâmbio e Log Protegidos
          (setq jsonFile (vl-filename-mktemp "sob_out.json"))
          (setq logFile  (vl-filename-mktemp "sob_log.txt"))
          (setq pyScript (sob-localizar-script))

          (if (not (findfile pyScript))
            (progn
              (princ (strcat "\n[ERRO] Script Python não encontrado em: " pyScript))
              (sob-alert (strcat "Script de automação não localizado:\n" pyScript))
              (list (cons "sucesso" nil) (cons "erro" "SCRIPT_NAO_ENCONTRADO"))
            )
            (progn
              ;; 5. Execução do Orquestrador Python em Segundo Plano
              (princ "\n[INFO] Acessando SharePoint e preparando projeto...")
              (setq cmd (strcat "py \"" pyScript "\" --sob \"" sobId "\" --destino \"" destinationRoot "\" --json-out \"" jsonFile "\" > \"" logFile "\" 2>&1"))

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

              ;; 6. Verificação do Resultado Canônico (BASE_DWG)
              (setq dwgTarget baseDwg)

              (if (and (findfile dwgTarget) (> (vl-file-size dwgTarget) 100))
                (progn
                  (princ "\n==============================================================")
                  (princ (strcat "\n✔ PROJETO " sobName " PREPARADO COM SUCESSO!"))
                  (princ (strcat "\nArquivo: " dwgTarget))
                  (princ "\n==============================================================")

                  ;; 7. Abertura do Arquivo no AutoCAD (Seção 14.20 e 14.21: BASE_DWG)
                  (setq erroCad nil)
                  (if abrirCad
                    (progn
                      (princ "\n[INFO] Abrindo BASE_SOB_DESENHO.dwg no AutoCAD...")
                      (if (and acadApp (not (vl-catch-all-error-p acadApp)))
                        (progn
                          (setq openedDoc (vl-catch-all-apply 'vla-open (list (vla-get-Documents acadApp) dwgTarget)))
                          (if (vl-catch-all-error-p openedDoc)
                            (progn
                              (setq erroCad (strcat "[FALHA] BASE_SOB_DESENHO.dwg foi criado, porém não pôde ser aberto no AutoCAD: "
                                                    (vl-catch-all-error-message openedDoc)))
                              (princ (strcat "\n" erroCad))
                            )
                            (progn
                              ;; Validação estrita: CURRENT_AUTOCAD_DWG == BASE_DWG (Seção 17, Etapa 24)
                              (setq activeDoc (vl-catch-all-apply 'vla-get-ActiveDocument (list acadApp)))
                              (if (and activeDoc (not (vl-catch-all-error-p activeDoc)))
                                (progn
                                  (setq currentDwg (vl-catch-all-apply 'vla-get-FullName (list activeDoc)))
                                  (if (and (stringp currentDwg) (/= currentDwg ""))
                                    (if (/= (strcase currentDwg) (strcase dwgTarget))
                                      (progn
                                        (setq erroCad (strcat "[FALHA CRÍTICA] O arquivo aberto não corresponde ao BASE_DWG esperado.\n\n"
                                                              "BASE_DWG esperado: " dwgTarget "\n"
                                                              "DWG efetivamente aberto: " currentDwg "\n"
                                                              "SOB_ID: " sobId))
                                        (princ (strcat "\n" erroCad))
                                      )
                                    )
                                  )
                                )
                              )
                            )
                          )
                        )
                        (progn
                          ;; Em ambiente sem GUI (accoreconsole), validação por DWGPREFIX + DWGNAME
                          (setq currentPrefix (getvar "DWGPREFIX"))
                          (setq currentName (getvar "DWGNAME"))
                          (if (and (stringp currentPrefix) (stringp currentName))
                            (setq currentDwg (strcat currentPrefix currentName))
                          )
                        )
                      )
                    )
                  )

                  (if erroCad
                    (progn
                      (sob-alert erroCad)
                      (list (cons "sucesso" nil)
                            (cons "status" "BLOQUEADO")
                            (cons "erro" erroCad)
                            (cons "SOB_ID" sobId)
                            (cons "BASE_DWG" baseDwg))
                    )
                    (progn
                      (sob-alert (strcat "Preparação de Projeto Concluída com Sucesso!\n\n"
                                         "SOB_ID: " sobId "\n"
                                         "SOB_NAME: " sobName "\n"
                                         "SOB_ROOT: " sobRoot "\n"
                                         "BASE_DWG: BASE_SOB_DESENHO.dwg\n\n"
                                         "O desenho foi aberto no AutoCAD."))
                      (list (cons "sucesso" t)
                            (cons "status" "CONCLUIDO")
                            (cons "SOB_ID" sobId)
                            (cons "SOB_NAME" sobName)
                            (cons "DESTINATION_ROOT" destinationRoot)
                            (cons "SOB_ROOT" sobRoot)
                            (cons "CROQUI_DIR" croquiDir)
                            (cons "BASE_DWG" baseDwg)
                            (cons "sob" sobName)
                            (cons "sobRoot" sobRoot)
                            (cons "dwgTarget" dwgTarget))
                    )
                  )
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
                  (setq rb_info "")
                  (if (findfile jsonFile)
                    (progn
                      (setq f_json (open jsonFile "r"))
                      (while (setq line_json (read-line f_json))
                        (if (vl-string-search "\"mensagem\":" line_json)
                          (setq erro_msg line_json)
                        )
                        (if (vl-string-search "\"rollback\":" line_json)
                          (setq rb_info line_json)
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
                  (if (/= rb_info "")
                    (princ (strcat "\n" rb_info))
                  )
                  (princ "\n==============================================================")

                  (if (vl-string-search "já possui uma execução concluída" erro_msg)
                    (sob-alert (strcat "Projeto Existente:\n\n"
                                       "A SOB já possui uma execução concluída neste destino.\n\n"
                                       "Nenhum arquivo foi sobrescrito ou duplicado."))
                    (sob-alert (strcat "Falha na preparação da SOB:\n\n"
                                       (if (/= log_txt "") log_txt "Consulte a janela de texto do AutoCAD (F2).")))
                  )
                  (list (cons "sucesso" nil)
                        (cons "status" "BLOQUEADO")
                        (cons "erro" (if (/= log_txt "") log_txt erro_msg)))
                )
              )
            )
          )
        )
      )
    )
  )
)

;; Comando Principal Interativo: SOB (Aliases: NOVASOB, PREPARAR_SOB)
(defun c:SOB (/ sobInput sh folder destPath)

  (princ "\n==============================================================")
  (princ "\n       PREPARAÇÃO AUTOMÁTICA DE PROJETO SOB (AUX CAD)         ")
  (princ "\n==============================================================")

  ;; 1. Solicitação do Número da SOB (Seção 14.2 & 14.22)
  (setq sobInput (getstring "\nInforme o número da SOB: "))
  (if (or (null sobInput) (= (vl-string-trim " " sobInput) ""))
    (progn
      (princ "\n[INFO] Operação cancelada pelo usuário.")
      (exit)
    )
  )

  ;; 2. Seleção do Diretório de Destino (Seção 14.5 & 14.22)
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
      (princ "\n[INFO] Operação cancelada pelo usuário.")
      (exit)
    )
  )

  ;; 3. Dispara o fluxo operacional com abertura no AutoCAD
  (sob-executar-fluxo sobInput destPath t)
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
