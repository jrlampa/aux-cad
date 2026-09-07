;;; =============================================================================
;;; kmz_pontos_importer.lsp - Importador Direto de Marcadores KMZ/KML para o AutoCAD
;;; Insere:
;;;   1. Bloco "POSTE_" na coordenada UTM (vértice da rede/cabo)
;;;   2. Bloco "PONTO" com número do marcador (<name>) com offset lateral
;;;   3. Descrição técnica lateral (<description>: 11/M, N1, S1 etc.)
;;; =============================================================================

(vl-load-com)

(defun c:IMPORTAR_KMZ_POSTES ( / kmz_file fuso pyScript outLsp wsh cmd res )
  (princ "\n--- IMPORTADOR DE POSTES DO GOOGLE EARTH (KMZ / KML) ---")

  ;; 1. Seleciona o arquivo do Google Earth
  (setq kmz_file (getfiled "Selecione o arquivo do Google Earth (KMZ ou KML)" "" "kmz;kml" 0))
  (if (not kmz_file)
    (progn
      (princ "\nOperação cancelada pelo usuário.")
      (exit)
    )
  )

  ;; 2. Solicita o Fuso UTM (Padrão 23 para RJ / SP / MG / ES)
  (setq fuso (getint "\nInforme o Fuso UTM [Enter para 23]: "))
  (if (not fuso) (setq fuso 23))

  ;; 3. Localiza o script Python inteligente
  (setq pyScript (findfile "topografia\\kmz_pontos_importer.py"))
  (if (not pyScript)
    (setq pyScript (findfile "kmz_pontos_importer.py"))
  )
  (if (not pyScript)
    (progn
      (alert "ERRO: O script 'kmz_pontos_importer.py' não foi localizado no SupportPath!")
      (exit)
    )
  )

  ;; 4. Define arquivo temporário para receber o script gerado
  (setq outLsp (vl-filename-mktemp "kmz_postes.lsp"))

  ;; 5. Executa o backend Python de forma oculta e síncrona
  (princ "\nProcessando coordenadas, marcadores e descrições do KMZ...")
  (setq cmd (strcat "python \"" pyScript "\" \"" kmz_file "\" --fuso " (itoa fuso) " --saida \"" outLsp "\""))

  (setq wsh (vlax-create-object "WScript.Shell"))
  (if wsh
    (progn
      ;; Executa oculto (0) e aguarda o término (:vlax-true)
      (vlax-invoke wsh 'Run (strcat "cmd.exe /c " cmd) 0 :vlax-true)
      (vlax-release-object wsh)
    )
    (progn
      ;; Fallback caso WScript.Shell não esteja disponível
      (startapp "cmd.exe" (strcat "/c " cmd))
      (command "_.DELAY" "1500")
    )
  )

  ;; 6. Carrega e executa a rotina gerada no desenho atual
  (if (and (findfile outLsp) (> (vl-file-size outLsp) 10))
    (progn
      (princ "\nInserindo simbologias, blocos e anotações no desenho...")
      (setq res (vl-catch-all-apply 'load (list outLsp)))
      (if (vl-catch-all-error-p res)
        (princ (strcat "\n[ERRO NA EXECUÇÃO] " (vl-catch-all-error-message res)))
        (progn
          (princ "\n==============================================================")
          (princ "\n[SUCESSO] Postes e descrições do KMZ importados perfeitamente!")
          (princ "\n==============================================================")
        )
      )
      ;; Limpa arquivo temporário
      (vl-file-delete outLsp)
    )
    (alert "ERRO: Não foi possível processar o arquivo KMZ/KML.\nVerifique se o Python está instalado e se o arquivo contém marcadores com coordenadas válidas.")
  )

  (princ)
)

;; Aliases para facilidade de digitação
(defun c:KMZPOSTES () (c:IMPORTAR_KMZ_POSTES))
(defun c:POSTESKMZ () (c:IMPORTAR_KMZ_POSTES))
(defun c:KMZ2CAD_POSTES () (c:IMPORTAR_KMZ_POSTES))

(princ "\n[AUX CAD] Importador de Postes KMZ carregado! Digite IMPORTAR_KMZ_POSTES ou KMZPOSTES.")
(princ)
