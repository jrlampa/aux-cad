;;; =============================================================================
;;; kmz_pontos_importer.lsp - Importador Direto de Marcadores KMZ/KML para o AutoCAD
;;; Insere:
;;;   1. Bloco "POSTE_" na coordenada UTM (vértice da rede/cabo)
;;;   2. Bloco "PONTO" com número do marcador (<name>) com offset lateral
;;;   3. Descrição técnica lateral (<description>: 11/M, N1, S1 etc.)
;;; =============================================================================

(vl-load-com)

(defun c:IMPORTAR_KMZ_POSTES ( / kmz_file fuso pyScript outLsp logFile wsh cmd res f_log log_txt line_log )
  (princ "\n--- IMPORTADOR DE POSTES DO GOOGLE EARTH (KMZ / KML) ---")

  ;; 1. Seleciona o arquivo do Google Earth
  (setq kmz_file (getfiled "Selecione o arquivo do Google Earth (KMZ ou KML)" "" "kmz;kml" 0))
  (if (or (not kmz_file) (not (findfile kmz_file)))
    (progn
      (princ "\nOperação cancelada pelo usuário.")
      (exit)
    )
  )

  ;; 2. Solicita o Fuso UTM (Padrão 23 para RJ / SP / MG / ES)
  (setq fuso (getint "\nInforme o Fuso UTM [Enter para 23]: "))
  (if (not fuso) (setq fuso 23))

  ;; 3. Localiza o script Python
  (setq pyScript nil)
  (if (and (boundp '*aux-cad-root*) *aux-cad-root*)
    (setq pyScript (findfile (strcat *aux-cad-root* "topografia\\kmz_pontos_importer.py")))
  )
  (if (not pyScript)
    (setq pyScript (findfile "topografia\\kmz_pontos_importer.py"))
  )
  (if (not pyScript)
    (setq pyScript (findfile "kmz_pontos_importer.py"))
  )
  (if (not pyScript)
    (progn
      (alert "ERRO: O script 'kmz_pontos_importer.py' não foi localizado no SupportPath!")
      (exit)
    )
  )

  ;; 4. Define arquivos temporários para script LISP e log de diagnóstico
  (setq outLsp  (vl-filename-mktemp "kmz_postes.lsp"))
  (setq logFile (vl-filename-mktemp "kmz_log.txt"))

  ;; 5. Executa o backend Python de forma protegida e síncrona
  (princ "\nProcessando coordenadas, marcadores e descrições do KMZ...")
  ;; Aspas extras ao redor do comando completo para o cmd.exe /c do Windows
  (setq cmd (strcat "\"python \"" pyScript "\" \"" kmz_file "\" --fuso " (itoa fuso) " --saida \"" outLsp "\" > \"" logFile "\" 2>&1\""))

  (setq wsh (vlax-create-object "WScript.Shell"))
  (if wsh
    (progn
      (vlax-invoke-method wsh "Run" (strcat "cmd.exe /c " cmd) 0 :vlax-true)
      (vlax-release-object wsh)
    )
    (progn
      (startapp "cmd.exe" (strcat "/c " cmd))
      (command "_.DELAY" "2000")
    )
  )

  ;; 6. Carrega e executa a rotina gerada no desenho atual
  (if (and (findfile outLsp) (> (vl-file-size outLsp) 10))
    (progn
      (princ "\nInserindo simbologias, blocos e anotações no desenho...")
      (setq res (vl-catch-all-apply 'load (list outLsp)))
      (if (vl-catch-all-error-p res)
        (princ (strcat "\n[ERRO NA EXECUÇÃO DO LISP] " (vl-catch-all-error-message res)))
        (progn
          (princ "\n==============================================================")
          (princ "\n[SUCESSO] Postes e descrições do KMZ importados perfeitamente!")
          (princ "\n==============================================================")
        )
      )
      (if (findfile outLsp) (vl-file-delete outLsp))
      (if (findfile logFile) (vl-file-delete logFile))
    )
    (progn
      ;; Lê o log do Python para exibir o erro exato
      (setq log_txt "")
      (if (findfile logFile)
        (progn
          (setq f_log (open logFile "r"))
          (while (and (setq line_log (read-line f_log)) (< (strlen log_txt) 500))
            (setq log_txt (strcat log_txt line_log "\n"))
          )
          (close f_log)
        )
      )
      (if (= (vl-string-trim " \n\r\t" log_txt) "")
        (setq log_txt "Verifique se o comando 'python' está configurado nas variáveis de ambiente do Windows.")
      )
      (alert (strcat "ERRO AO PROCESSAR KMZ/KML:\n\n" log_txt))
      (if (findfile logFile) (vl-file-delete logFile))
    )
  )

  (princ)
)

;; Aliases para facilidade de digitação
(defun c:KMZPOSTES () (c:IMPORTAR_KMZ_POSTES))
(defun c:POSTESKMZ () (c:IMPORTAR_KMZ_POSTES))
(defun c:KMZ2CAD_POSTES () (c:IMPORTAR_KMZ_POSTES))

(princ "\n[AUX CAD] Importador de Postes KMZ carregado! Digite IMPORTAR_KMZ_POSTES ou KMZPOSTES.")
(princ)
