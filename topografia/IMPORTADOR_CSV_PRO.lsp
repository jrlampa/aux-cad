;;; =============================================================================
;;; IMPORTADOR DE PONTOS UTM A PARTIR DE CSV (X,Y,Z,Name)
;;; Compatível com ArcGIS for AutoCAD e qualquer AutoCAD
;;; Inclui:
;;; - Importação de pontos
;;; - Textos dos nomes
;;; - Polyline conectando os pontos
;;; - Cotas alinhadas (DIMALIGNED) entre cada par consecutivo
;;; =============================================================================


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


;;; cria camada via VLA
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



(defun C:IMPORTAR_PONTOS_UTM (/ file f line row x y z name
                               insert_pt text_pt
                               ptObj textObj
                               cont_pontos
                               acadObj doc modelSpace
                               lista_pts
                               dim_offset)

  (vl-load-com)

  (setq acadObj   (vlax-get-acad-object))
  (setq doc       (vla-get-ActiveDocument acadObj))
  (setq modelSpace (vla-get-ModelSpace doc))

  ;; ajuste rápido: deslocamento vertical (em unidades do desenho) para posicionar as cotas
  (setq dim_offset 2.0)

  (create-layer "PONTOS_UTM" 3)
  (create-layer "TEXTO_UTM" 1)
  (create-layer "COTAS_UTM" 2)

  (setq file (getfiled "Selecione arquivo CSV (X,Y,Z,Name)" "" "csv" 0))
  (if (not file)
    (progn (princ "\nImportação cancelada.") (exit))
  )

  (setq f (open file "r"))

  ;; tenta pular cabeçalho se houver
  (setq line (read-line f))
  ;; Se a primeira linha contém números (não cabeçalho) vamos processá-la; caso contrário continuamos
  (if (and line (wcmatch (strcase line) "*[0-9]*"))
    (progn
      ;; volta para processar essa linha como primeira
      (setq f (open file "r"))
      (setq line nil)
    )
    ;; caso seja cabeçalho, seguimos com o file já posicionado após o read-line
  )

  (princ "\nIniciando importação...")

  (setq cont_pontos 0)
  (setq lista_pts '())

  ;; Loop CSV
  (while (setq line (read-line f))
    (setq line (vl-string-trim " " line))

    (if (and line (/= line ""))
      (progn
        (setq row (split-csv line))

        (if (>= (length row) 4)
          (progn
            (setq x    (atof (nth 0 row)))
            (setq y    (atof (nth 1 row)))
            (setq z    (atof (nth 2 row)))
            (setq name (nth 3 row))

            ;; ponto
            (setq insert_pt (vlax-3d-point (list x y z)))
            (setq ptObj (vla-AddPoint modelSpace insert_pt))
            (vla-put-Layer ptObj "PONTOS_UTM")

            ;; texto
            (if (> (strlen name) 0)
              (progn
                (setq text_pt (vlax-3d-point (list (+ x 0.5) (+ y 0.5) z)))
                (setq textObj (vla-AddText modelSpace name text_pt 1.0))
                (vla-put-Layer textObj "TEXTO_UTM")
              )
            )

            ;; guarda p/ polyline e cotas
            (setq lista_pts (append lista_pts (list (list x y z))))
            (setq cont_pontos (1+ cont_pontos))
          ) ; progn do >=4 campos
        ) ; if >=4
      ) ; progn line não vazio
    ) ; if and line
  ) ; while

  (close f)


  ;; =============================================
  ;; POLYLINE AUTOMÁTICA
  ;; =============================================
  (if (> (length lista_pts) 1)
    (progn
      (princ "\nCriando polyline...")

      (command "_.LAYER" "S" "0" "")

      (command "_.PLINE")
      (foreach p lista_pts
        (command (list (nth 0 p) (nth 1 p) (nth 2 p)))
      )
      (command "")
    )
  )



  ;; =============================================
  ;; CRIAÇÃO DAS COTAS DIMALIGNED
  ;; =============================================

  (if (> (length lista_pts) 1)
    (progn
      (princ "\nCriando cotas alinhadas...")

      (command "_.LAYER" "M" "COTAS_UTM" "")

      (setq idx 0)

      (repeat (- (length lista_pts) 1)

        (setq p1 (nth idx lista_pts))
        (setq p2 (nth (+ idx 1) lista_pts))

        ;; midpoint
        (setq midx (/ (+ (nth 0 p1) (nth 0 p2)) 2.0))
        (setq midy (/ (+ (nth 1 p1) (nth 1 p2)) 2.0))
        (setq midz (/ (+ (nth 2 p1) (nth 2 p2)) 2.0))

        ;; posição da cota (deslocada dim_offset acima)
        (setq dimpos (list midx (+ midy dim_offset) midz))

        ;; cota alinhada
        (command
          "_.DIMALIGNED"
          (list (nth 0 p1) (nth 1 p1) (nth 2 p1))
          (list (nth 0 p2) (nth 1 p2) (nth 2 p2))
          dimpos
        )

        (setq idx (1+ idx))
      )
    )
  )

  (vl-cmdf "ZOOM" "E")

  (princ (strcat "\nImportação concluída! "
                 (itoa cont_pontos)
                 " pontos, polyline e cotas criadas."))
  (princ)
)


;;; =============================================================================
;;; FIM
;;; =============================================================================
