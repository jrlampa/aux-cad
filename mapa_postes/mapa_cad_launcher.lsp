;;; =============================================================================
;;; mapa_cad_launcher.lsp - Integrador do Estúdio Web de Satélite com o AutoCAD
;;; Comandos: MAPAPOSTES, MAPA, ATUALIZAR_MAPAPOSTES
;;; =============================================================================

(vl-load-com)

(defun c:MAPAPOSTES ( / root pyScript wsh lspExec res )
  (princ "\n--- ESTÚDIO DE SATÉLITE DE POSTES & CARGAS (AUX CAD) ---")

  (setq root "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\")
  (if (and (boundp '*aux-cad-root*) *aux-cad-root*)
    (setq root *aux-cad-root*)
  )

  (setq pyScript (strcat root "mapa_postes\\mapa_servidor.py"))
  (setq lspExec  (strcat root "mapa_postes\\mapa_postes_exec.lsp"))

  ;; 1. Inicia o servidor Python em background se ainda não estiver rodando
  (setq wsh (vlax-create-object "WScript.Shell"))
  (if wsh
    (progn
      (vlax-invoke-method wsh "Run" (strcat "cmd.exe /c start /min python \"" pyScript "\"") 0 :vlax-false)
      (vlax-release-object wsh)
    )
    (startapp "cmd.exe" (strcat "/c start /min python \"" pyScript "\""))
  )

  (princ "\n[OK] Servidor do Mapa Web iniciado! O navegador abrirá automaticamente em http://localhost:8765")
  (princ "\nApós marcar os postes e clicar em 'Enviar para o AutoCAD', digite ATUALIZAR_MAPAPOSTES.")

  ;; 2. Se já houver postes gerados previamente, pergunta se deseja carregar agora
  (if (and (findfile lspExec) (> (vl-file-size lspExec) 10))
    (progn
      (initget "Sim Nao")
      (if (= (getkword "\nHá postes aguardando inserção. Deseja desenhar agora no AutoCAD? [Sim/Nao] <Sim>: ") "Nao")
        (princ "\nOperação em espera. Quando terminar, use ATUALIZAR_MAPAPOSTES.")
        (progn
          (princ "\nInserindo postes do Estúdio no desenho atual...")
          (setq res (vl-catch-all-apply 'load (list lspExec)))
          (if (vl-catch-all-error-p res)
            (princ (strcat "\n[ERRO AO DESENHAR] " (vl-catch-all-error-message res)))
            (princ "\n[SUCESSO] Postes, estruturas e cargas desenhados com sucesso!")
          )
        )
      )
    )
  )

  (princ)
)

;; Comando para desenhar os postes gerados no navegador
(defun c:ATUALIZAR_MAPAPOSTES ( / root lspExec res )
  (setq root "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\")
  (if (and (boundp '*aux-cad-root*) *aux-cad-root*)
    (setq root *aux-cad-root*)
  )
  (setq lspExec (strcat root "mapa_postes\\mapa_postes_exec.lsp"))

  (if (and (findfile lspExec) (> (vl-file-size lspExec) 10))
    (progn
      (princ "\nDesenhando postes do mapa web no AutoCAD...")
      (setq res (vl-catch-all-apply 'load (list lspExec)))
      (if (vl-catch-all-error-p res)
        (alert (strcat "ERRO AO CARREGAR POSTES:\n" (vl-catch-all-error-message res)))
        (progn
          (princ "\n[SUCESSO] Postes do Mapa desenhados com sucesso!")
          (alert "Postes do Estúdio Web desenhados com sucesso no AutoCAD!")
        )
      )
    )
    (alert "Nenhum arquivo de postes gerado ainda.\nAbra o mapa (MAPAPOSTES) e clique em 'Enviar para o AutoCAD'.")
  )
  (princ)
)

;; Aliases
(defun c:MAPA () (c:MAPAPOSTES))
(defun c:ESTUDIOMAPA () (c:MAPAPOSTES))

(princ "\n[AUX CAD] Estúdio de Postes Web carregado! Digite MAPAPOSTES ou MAPA.")
(princ)
