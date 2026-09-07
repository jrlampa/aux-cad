(defun c:PontosParaBlocos ( / blkName ss i pt ent)
  (setq blkName (getstring "\nDigite o nome do bloco que deseja inserir: "))
  (prompt "\nSelecione os pontos na tela: ")
  (if (setq ss (ssget '((0 . "POINT"))))
    (progn
      (setq i 0)
      (while (< i (sslength ss))
        (setq ent (entget (ssname ss i)))
        (setq pt (cdr (assoc 10 ent)))
        
        ;; Inserção raiz via banco de dados (ignora prompts, osnaps e auto placement)
        (entmakex (list '(0 . "INSERT")
                        (cons 2 blkName)
                        (cons 10 pt)
                        '(41 . 1.0) ; Escala X cravada em 1
                        '(42 . 1.0) ; Escala Y cravada em 1
                        '(43 . 1.0) ; Escala Z cravada em 1
                        '(50 . 0.0) ; Rotação cravada em 0
                  )
        )
        
        (setq i (1+ i))
      )
      (princ (strcat "\n" (itoa i) " blocos inseridos com sucesso e sem alterar a escala!"))
    )
    (princ "\nNenhum ponto selecionado.")
  )
  (princ)
)