;;; =============================================================================
;;; IMPORTADOR DE PONTOS UTM A PARTIR DE CSV (X,Y,Z,Name)
;;; Compatível com todas as versões do AutoCAD
;;; =============================================================================


;;; -----------------------------------------------------------------------------
;;; Função split-csv — divide a linha em campos separados por vírgula
;;; (não usa vl-string-split, compatível com qualquer AutoCAD)
;;; -----------------------------------------------------------------------------
(defun split-csv (s / len i ch cur res)
  (setq len (strlen s)
        i   0
        cur ""
        res '()
  )
  (while (< i len)
    (setq ch (substr s (+ i 1) 1))
    (if (= ch ",")
      (progn
        (setq res (cons (vl-string-trim " " cur) res))
        (setq cur "")
      )
      (setq cur (strcat cur ch))
    )
    (setq i (1+ i))
  )
  (setq res (cons (vl-string-trim " " cur) res))
  (reverse res)
)


;;; -----------------------------------------------------------------------------
;;; Criação de camada com VLA
;;; -----------------------------------------------------------------------------
(defun create-layer (layer-name color-code)
  (vl-load-com)
  (setq acadObj (vlax-get-acad-object))
  (setq doc     (vla-get-ActiveDocument acadObj))
  (setq layers  (vla-get-Layers doc))

  (if (vl-catch-all-error-p
        (vl-catch-all-apply 'vla-Item (list layers layer-name))
      )
    (progn
      (setq newLayer (vla-Add layers layer-name))
      (vla-put-Color newLayer color-code)
    )
  )
)


;;; -----------------------------------------------------------------------------
;;; Função principal — IMPORTAR_PONTOS_UTM
;;; -----------------------------------------------------------------------------
(defun C:IMPORTAR_PONTOS_UTM (/ file f line row x y z name
                               insert_pt text_pt
                               ptObj textObj
                               cont_pontos
                               acadObj doc modelSpace)

  (vl-load-com)

  ;; Objetos VLA
  (setq acadObj   (vlax-get-acad-object))
  (setq doc       (vla-get-ActiveDocument acadObj))
  (setq modelSpace (vla-get-ModelSpace doc))

  ;; Cria layers
  (create-layer "PONTOS_UTM" 3)    ;; verde
  (create-layer "TEXTO_UTM" 1)     ;; vermelho

  ;; Seleciona CSV
  (setq file (getfiled "Selecione arquivo CSV (X,Y,Z,Name)" "" "csv" 0))
  (if (not file)
    (progn (princ "\nImportação cancelada.") (exit))
  )

  (setq f (open file "r"))

  ;; Lê primeira linha (cabeçalho)
  (read-line f)

  (princ "\nIniciando importação de pontos UTM (X,Y,Z,Name)...")

  (setq cont_pontos 0)

  ;; Loop principal
  (while (setq line (read-line f))
    (setq line (vl-string-trim " " line))

    (if (and line (/= line ""))
      (progn

        (setq row (split-csv line))

        ;; Garante 4 colunas
        (if (>= (length row) 4)
          (progn

            ;; Converte valores
            (setq x    (atof (nth 0 row)))
            (setq y    (atof (nth 1 row)))
            (setq z    (atof (nth 2 row)))
            (setq name (nth 3 row))

            ;; Cria ponto 3D (VARIANT SAFEARRAY)
            (setq insert_pt (vlax-3d-point (list x y z)))
            (setq ptObj (vla-AddPoint modelSpace insert_pt))
            (vla-put-Layer ptObj "PONTOS_UTM")

            ;; Se houver nome → desenha texto
            (if (> (strlen name) 0)
              (progn
                (setq text_pt (vlax-3d-point (list (+ x 0.5) (+ y 0.5) z)))
                (setq textObj (vla-AddText modelSpace name text_pt 1.0))
                (vla-put-Layer textObj "TEXTO_UTM")
              )
            )

            (setq cont_pontos (1+ cont_pontos))
          )
        )
      )
    )
  )

  (close f)

  ;; Zoom Extents
  (vl-cmdf "ZOOM" "E")

  (princ (strcat "\nImportação concluída! Total de "
                 (itoa cont_pontos)
                 " pontos inseridos."))
  (princ)
)


;;; =============================================================================
;;; FIM DO ARQUIVO
;;; =============================================================================
