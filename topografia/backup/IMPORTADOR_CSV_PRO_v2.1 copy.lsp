;;; =============================================================================
;;; IMPORTADOR DE PONTOS UTM PRO v3.0 - FOCO EM POSTES E ATRIBUTOS
;;; =============================================================================

(defun C:IMPORTAR_POSTES (/ dcl_id dcl_file f lst_blocks opt_pline opt_dim opt_blk 
                             blk_name do_import file f_csv line row x y z name desc
                             insert_pt acadObj doc modelSpace lista_pts cont_pontos)

  (vl-load-com)
  (setq acadObj (vlax-get-acad-object)
        doc (vla-get-ActiveDocument acadObj)
        modelSpace (vla-get-ModelSpace doc))

  ;; 1. LISTA DE BLOCOS E DEFINIÇÃO DE PADRÃO
  (setq lst_blocks (get-block-list))
  (setq blk_name (car lst_blocks)) ; Default
  
  ;; Tenta encontrar "poste_" ou "p1" na lista para fixar
  (foreach b lst_blocks
    (if (or (wcmatch (strcase b) "POSTE*") (wcmatch (strcase b) "P1"))
        (setq blk_name b)
    )
  )

  ;; 2. INTERFACE SIMPLIFICADA (Opcional, se quiser pular o DCL, podemos bypassar aqui)
  ;; Mantendo o DCL mas já vindo com o bloco "Poste" pré-selecionado se existir
  (setq dcl_file (vl-filename-mktemp "import_utm.dcl"))
  (setq f (open dcl_file "w"))
  (write-line "import_utm_dlg : dialog { label = \"Importador de Postes/Pontos\";" f)
  (write-line "  : boxed_column { label = \"Configurações\";" f)
  (write-line "    : toggle { key = \"tog_blk\"; label = \"Inserir Blocos (Postes)\"; value = \"1\"; }" f)
  (write-line "    : text { label = \"Bloco identificado: \"; }" f)
  (write-line (strcat "    : text { label = \"" blk_name "\"; }") f)
  (write-line "  }" f)
  (write-line "  ok_cancel;" f)
  (write-line "}" f)
  (close f)

  (setq dcl_id (load_dialog dcl_file))
  (new_dialog "import_utm_dlg" dcl_id)
  (setq do_import (start_dialog))
  (unload_dialog dcl_id)
  (vl-file-delete dcl_file)

  (if (= do_import 1)
    (progn
      (setq file (getfiled "Selecione o CSV gerado pelo Python" "" "csv" 0))
      (if (not file) (exit))

      (create-layer "ELETRICA_POSTES" 4)
      (setq f_csv (open file "r"))
      (read-line f_csv) ; Pula cabeçalho se houver

      (while (setq line (read-line f_csv))
        (setq row (split-csv line))
        (if (>= (length row) 4)
          (progn
            (setq x (atof (nth 0 row))
                  y (atof (nth 1 row))
                  z (atof (nth 2 row))
                  name (nth 3 row)
                  ;; Supondo que a 5ª coluna do CSV seja o atributo do poste
                  desc (if (nth 4 row) (nth 4 row) ""))

            (setq insert_pt (vlax-3d-point (list x y z)))
            
            ;; INSERÇÃO COM ATRIBUTO
            (setq newBlk (vla-InsertBlock modelSpace insert_pt blk_name 1.0 1.0 1.0 0.0))
            (vla-put-Layer newBlk "ELETRICA_POSTES")
            
            ;; Se o bloco tiver atributos, preenche o primeiro com a descrição
            (setq atts (vlax-invoke newBlk 'GetAttributes))
            (if (and atts desc)
                (vla-put-TextString (car atts) desc)
            )
          )
        )
      )
      (close f_csv)
      (princ "\nPostes importados com sucesso.")
    )
  )
  (princ)
)