;;; ============================================================
;;; TLENTAB+  |  Total Length Table (Master Version)
;;; Soma comprimentos de linhas/polylines selecionadas
;;; Insere relatório em TABLE (AcDbTable)
;;; NÃO altera o layer atual do usuário
;;; ============================================================

(defun CopyToClipboard (txt / html)
  (setq html (vlax-create-object "htmlfile"))
  (vlax-invoke
    (vlax-get
      (vlax-get html 'ParentWindow)
      'ClipboardData
    )
    'SetData
    "Text"
    txt
  )
  (vlax-release-object html)
)

(defun GetSelection ( / ss)
  ;; Usa pré-seleção se existir, senão solicita seleção
  (setq ss (ssget "_I" '((0 . "LINE,LWPOLYLINE,POLYLINE"))))
  (if (null ss)
    (setq ss (ssget '((0 . "LINE,LWPOLYLINE,POLYLINE"))))
  )
  ss
)

(defun c:TLENTAB+ ( / ss i ent obj total
                      doc ms lay pt tbl rows cols oldLay)

  (vl-load-com)

  ;; ================= CONFIGURAÇÕES =================
  (setq lay  "REL_COMPRIMENTO_TOTAL") ; layer da tabela
  (setq rows 4)
  (setq cols 2)
  ;; =================================================

  ;; Preserva layer atual do usuário
  (setq oldLay (getvar "CLAYER"))

  (setq total 0.0)

  ;; Seleção (pré ou manual)
  (setq ss (GetSelection))

  (if (not ss)
    (princ "\nNenhuma entidade válida selecionada.")
    (progn

      ;; Soma dos comprimentos
      (setq i 0)
      (repeat (sslength ss)
        (setq ent (ssname ss i))
        (setq obj (vlax-ename->vla-object ent))
        (if (vlax-property-available-p obj 'Length)
          (setq total (+ total (vla-get-Length obj)))
        )
        (setq i (1+ i))
      )

      ;; Clipboard (somente valor)
      (CopyToClipboard (rtos total 2 0))

      ;; Documento / ModelSpace
      (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
      (setq ms  (vla-get-ModelSpace doc))

      ;; Cria layer do relatório se não existir
      (if (not (tblsearch "LAYER" lay))
        (vla-add (vla-get-Layers doc) lay)
      )

      ;; Ponto de inserção
      (setq pt (getpoint "\nPonto de inserção da tabela: "))
      (if (null pt)
        (progn
          (setvar "CLAYER" oldLay)
          (princ "\nComando cancelado.")
          (exit)
        )
      )

      ;; Criação da tabela
      (setq tbl
        (vla-AddTable
          ms
          (vlax-3d-point pt)
          rows
          cols
          4.0
          40.0
        )
      )

      ;; Layer da tabela (sem alterar CLAYER)
      (vla-put-Layer tbl lay)

      ;; Conteúdo da tabela
      (vla-SetText tbl 0 0 "RELATÓRIO DE COMPRIMENTO")
      (vla-MergeCells tbl 0 0 0 1)

      (vla-SetText tbl 1 0 "Descrição")
      (vla-SetText tbl 1 1 "Comprimento Total")

      (vla-SetText tbl 2 0 "Unidade")
      (vla-SetText tbl 2 1 "m")

      (vla-SetText tbl 3 0 "Valor")
      (vla-SetText tbl 3 1 (rtos total 2 0))

      (princ
        (strcat
          "\nComprimento total = "
          (rtos total 2 0)
          " m (copiado para o clipboard)"
        )
      )
    )
  )

  ;; Restaura layer original
  (setvar "CLAYER" oldLay)

  (princ)
)
