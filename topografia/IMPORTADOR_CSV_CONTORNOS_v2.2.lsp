;;; =============================================================================
;;; IMPORTADOR DE PONTOS E CONTORNOS UTM PRO v2.2 (COM SUPORTE A POLYLINES/CURVAS)
;;; =============================================================================
;;; Desenvolvido para importar CSV (X,Y,Z,Name) do Conversor UTM sisTOPOGRAFIA
;;; Suporta o desenho de contornos/polylines agrupados por nome de feature/curva
;;; =============================================================================

(defun split-csv (s / len i ch cur res)
  (setq len (strlen s) i 0 cur "" res '())
  (while (< i len)
    (setq ch (substr s (+ i 1) 1))
    (if (= ch ",")
      (progn (setq res (cons (vl-string-trim " " cur) res)) (setq cur ""))
      (setq cur (strcat cur ch))
    )
    (setq i (1+ i))
  )
  (setq res (cons (vl-string-trim " " cur) res))
  (reverse res)
)

(defun create-layer (layer-name color-code)
  (vl-load-com)
  (setq acadObj (vlax-get-acad-object)
        doc     (vla-get-ActiveDocument acadObj)
        layers  (vla-get-Layers doc))
  (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-Item (list layers layer-name)))
    (progn
      (setq newLayer (vla-Add layers layer-name))
      (vla-put-Color newLayer color-code)
    )
  )
)

(defun get-block-list ( / blk blks )
  (setq blks '())
  (setq blk (tblnext "BLOCK" T))
  (while blk
    ;; Ignora XREFs e blocos anônimos
    (if (and (= (logand (cdr (assoc 70 blk)) 4) 0) 
             (/= (substr (cdr (assoc 2 blk)) 1 1) "*"))
        (setq blks (cons (cdr (assoc 2 blk)) blks))
    )
    (setq blk (tblnext "BLOCK"))
  )
  (if blks (vl-sort blks '<) '("Nenhum bloco no desenho"))
)

(defun draw-polyline-group (pts layer-name / p)
  (if (and pts (> (length pts) 1))
    (progn
      (command "_.LAYER" "M" layer-name "")
      (command "_.PLINE")
      (foreach p pts (command (list (nth 0 p) (nth 1 p) (nth 2 p))))
      (command "")
    )
  )
)

(defun C:IMPORTAR_PONTOS_UTM_CONTORNOS (/ dcl_id dcl_file f lst_blocks 
                                         opt_pline opt_group opt_dim opt_blk blk_idx blk_name do_import
                                         file f_csv line row x y z name insert_pt text_pt
                                         ptObj textObj cont_pontos cont_contornos acadObj doc modelSpace
                                         lista_pts current_group_pts current_group_name
                                         dim_offset p1 p2 midx midy midz dimpos idx)

  ;; 1. CRIAR ARQUIVO DCL TEMPORÁRIO
  (setq dcl_file (vl-filename-mktemp "import_utm_contornos.dcl"))
  (setq f (open dcl_file "w"))
  (write-line "import_utm_dlg : dialog { label = \"Importador de Pontos e Contornos UTM Pro v2.2\";" f)
  (write-line "  : boxed_column { label = \"Opções de Traçado e Contornos\";" f)
  (write-line "    : toggle { key = \"tog_pline\"; label = \"Desenhar Polylines nos pontos\"; value = \"1\"; }" f)
  (write-line "    : toggle { key = \"tog_group\"; label = \"Agrupar Polylines por Contorno/Nome (Recomendado KMZ)\"; value = \"1\"; }" f)
  (write-line "    : toggle { key = \"tog_dim\"; label = \"Criar Cotas Alinhadas (DIMALIGNED)\"; value = \"0\"; }" f)
  (write-line "  }" f)
  (write-line "  : boxed_column { label = \"Inserção de Blocos\";" f)
  (write-line "    : toggle { key = \"tog_blk\"; label = \"Inserir bloco nas coordenadas\"; value = \"0\"; }" f)
  (write-line "    : popup_list { key = \"lst_blks\"; label = \"Selecione o Bloco:\"; edit_width = 30; is_enabled = false; }" f)
  (write-line "  }" f)
  (write-line "  ok_cancel;" f)
  (write-line "}" f)
  (close f)

  ;; 2. CARREGAR A INTERFACE
  (setq dcl_id (load_dialog dcl_file))
  (if (not (new_dialog "import_utm_dlg" dcl_id))
    (progn (princ "\nErro ao carregar a interface.") (exit))
  )

  ;; 3. PREENCHER A LISTA DE BLOCOS
  (setq lst_blocks (get-block-list))
  (start_list "lst_blks")
  (mapcar 'add_list lst_blocks)
  (end_list)

  ;; 4. AÇÕES DA INTERFACE
  (action_tile "tog_blk" "(mode_tile \"lst_blks\" (if (= $value \"1\") 0 1))")
  (action_tile "tog_pline" "(mode_tile \"tog_group\" (if (= $value \"1\") 0 1))")
  
  (action_tile "accept" 
    "(setq opt_pline (= (get_tile \"tog_pline\") \"1\"))
     (setq opt_group (= (get_tile \"tog_group\") \"1\"))
     (setq opt_dim (= (get_tile \"tog_dim\") \"1\"))
     (setq opt_blk (= (get_tile \"tog_blk\") \"1\"))
     (setq blk_idx (atoi (get_tile \"lst_blks\")))
     (done_dialog 1)"
  )
  (action_tile "cancel" "(done_dialog 0)")

  ;; 5. INICIAR DIÁLOGO
  (setq do_import (start_dialog))
  (unload_dialog dcl_id)
  (vl-file-delete dcl_file)

  ;; 6. EXECUTAR A IMPORTAÇÃO (SE CLICOU EM OK)
  (if (= do_import 1)
    (progn
      (setq file (getfiled "Selecione arquivo CSV de Contornos (X,Y,Z,Name)" "" "csv" 0))
      (if (not file)
        (progn (princ "\nImportação cancelada.") (exit))
      )

      (vl-load-com)
      (setq acadObj (vlax-get-acad-object)
            doc (vla-get-ActiveDocument acadObj)
            modelSpace (vla-get-ModelSpace doc)
            dim_offset 2.0
            cont_pontos 0
            cont_contornos 0
            lista_pts '()
            current_group_pts '()
            current_group_name nil)

      (create-layer "PONTOS_UTM" 3)      ; Verde
      (create-layer "TEXTO_UTM" 1)       ; Vermelho
      (create-layer "COTAS_UTM" 2)       ; Amarelo
      (create-layer "CONTORNOS_UTM" 4)   ; Ciano

      (setq f_csv (open file "r"))
      (setq line (read-line f_csv))
      (if (and line (wcmatch (strcase line) "*[0-9]*"))
        (progn (setq f_csv (open file "r")) (setq line nil))
      )

      (princ "\nLendo CSV e inserindo pontos e contornos...")
      (while (setq line (read-line f_csv))
        (setq line (vl-string-trim " " line))
        (if (and line (/= line ""))
          (progn
            (setq row (split-csv line))
            (if (>= (length row) 4)
              (progn
                (setq x (atof (nth 0 row))
                      y (atof (nth 1 row))
                      z (atof (nth 2 row))
                      name (nth 3 row))

                (setq insert_pt (vlax-3d-point (list x y z)))
                (setq ptObj (vla-AddPoint modelSpace insert_pt))
                (vla-put-Layer ptObj "PONTOS_UTM")

                (if (> (strlen name) 0)
                  (progn
                    (setq text_pt (vlax-3d-point (list (+ x 0.5) (+ y 0.5) z)))
                    (setq textObj (vla-AddText modelSpace name text_pt 1.0))
                    (vla-put-Layer textObj "TEXTO_UTM")
                  )
                )

                (setq lista_pts (append lista_pts (list (list x y z))))
                (setq cont_pontos (1+ cont_pontos))

                ;; PROCESSAMENTO DE AGRUPAMENTO DE CONTORNOS/POLYLINES
                (if (and opt_pline opt_group)
                  (progn
                    (if (or (null current_group_name) (/= name current_group_name))
                      (progn
                        (if (and current_group_pts (> (length current_group_pts) 1))
                          (progn
                            (draw-polyline-group current_group_pts "CONTORNOS_UTM")
                            (setq cont_contornos (1+ cont_contornos))
                          )
                        )
                        (setq current_group_name name)
                        (setq current_group_pts (list (list x y z)))
                      )
                      (setq current_group_pts (append current_group_pts (list (list x y z))))
                    )
                  )
                )

              )
            )
          )
        )
      )
      (close f_csv)

      ;; DESENHA O ÚLTIMO GRUPO DE CONTORNO PENDENTE
      (if (and opt_pline opt_group current_group_pts (> (length current_group_pts) 1))
        (progn
          (draw-polyline-group current_group_pts "CONTORNOS_UTM")
          (setq cont_contornos (1+ cont_contornos))
        )
      )

      ;; DESENHA POLYLINE ÚNICA (CASO NÃO SEJA POR GRUPO)
      (if (and opt_pline (not opt_group) (> (length lista_pts) 1))
        (progn
          (princ "\nCriando polyline única contínua...")
          (draw-polyline-group lista_pts "CONTORNOS_UTM")
          (setq cont_contornos 1)
        )
      )

      ;; DESENHA COTAS ALINHADAS
      (if (and opt_dim (> (length lista_pts) 1))
        (progn
          (princ "\nCriando cotas alinhadas...")
          (command "_.LAYER" "M" "COTAS_UTM" "")
          (setq idx 0)
          (repeat (- (length lista_pts) 1)
            (setq p1 (nth idx lista_pts) p2 (nth (+ idx 1) lista_pts))
            (setq midx (/ (+ (nth 0 p1) (nth 0 p2)) 2.0)
                  midy (/ (+ (nth 1 p1) (nth 1 p2)) 2.0)
                  midz (/ (+ (nth 2 p1) (nth 2 p2)) 2.0)
                  dimpos (list midx (+ midy dim_offset) midz))
            (command "_.DIMALIGNED" (list (nth 0 p1) (nth 1 p1) (nth 2 p1)) (list (nth 0 p2) (nth 1 p2) (nth 2 p2)) dimpos)
            (setq idx (1+ idx))
          )
        )
      )

      ;; INSERE BLOCOS
      (if opt_blk
        (progn
          (setq blk_name (nth blk_idx lst_blocks))
          (if (and blk_name (/= blk_name "Nenhum bloco no desenho"))
            (progn
              (princ (strcat "\nInserindo o bloco '" blk_name "'..."))
              (foreach p lista_pts
                (entmakex (list '(0 . "INSERT") (cons 2 blk_name) (cons 10 p) '(41 . 1.0) '(42 . 1.0) '(43 . 1.0) '(50 . 0.0)))
              )
            )
          )
        )
      )

      (vl-cmdf "ZOOM" "E")
      (princ (strcat "\nSucesso! " (itoa cont_pontos) " pontos e " (itoa cont_contornos) " contornos/polylines gerados."))
    )
  )
  (princ)
)

(defun C:IMPORTAR_CONTORNOS () (C:IMPORTAR_PONTOS_UTM_CONTORNOS))
