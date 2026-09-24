;; ==============================================================================
;;  workspace_cad.lsp
;;  AUX CAD - Integração nativa do Workspace da SOB com o AutoCAD
;;  Comandos:
;;    WORKSPACE     : Inspeciona e abre o painel do Workspace para o desenho ativo
;;    SOBWORKSPACE  : Alias rápido
;;    RECARREGAR_WORKSPACE : Recarrega a rotina na sessão
;; ==============================================================================

(vl-load-com)

(defun c:WORKSPACE (/ dwgPrefix dwgName pyScript cmd)
  (princ "\n=======================================================")
  (princ "\n   AUX CAD - WORKSPACE DA SOB / PROJETO                ")
  (princ "\n=======================================================")

  (setq dwgPrefix (getvar "DWGPREFIX"))
  (setq dwgName (getvar "DWGNAME"))

  (if (or (null dwgPrefix) (= dwgPrefix ""))
    (setq dwgPrefix (getvar "TEMPPREFIX"))
  )

  ;; Localiza o script Python do Workspace
  (if (boundp '*aux-cad-root*)
    (setq pyScript (strcat *aux-cad-root* "workspace\\workspace_cli.py"))
    (setq pyScript (findfile "workspace\\workspace_cli.py"))
  )
  (if (or (null pyScript) (not (findfile pyScript)))
    (setq pyScript (findfile "workspace_cli.py"))
  )
  (if (or (null pyScript) (not (findfile pyScript)))
    (setq pyScript "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\workspace\\workspace_cli.py")
  )

  (princ (strcat "\nPasta detectada: " dwgPrefix))
  (princ "\nAbrindo Workspace da SOB...")

  (setq cmd (strcat "/c start \"\" py \"" pyScript "\" --dir \"" dwgPrefix "\" --gui"))
  (startapp "cmd.exe" cmd)

  (princ "\n[OK] Workspace acionado com sucesso.\n")
  (princ)
)

(defun c:SOBWORKSPACE ()
  (c:WORKSPACE)
)

(defun c:RECARREGAR_WORKSPACE ()
  (load "workspace\\workspace_cad.lsp")
  (princ "\n[OK] workspace_cad.lsp recarregado com sucesso.\n")
  (princ)
)

(princ "\n[AUX CAD] Módulo Workspace carregado com sucesso. Digite WORKSPACE para iniciar.")
(princ)
