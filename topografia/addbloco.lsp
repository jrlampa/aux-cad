(defun c:ADDBLOCO ( / blkName ss i ent edata pt x y sx sy sz ucsRot refLayer strN strE doc space newBlk attsList tag )
  (vl-load-com)
  
  ;; Captura o documento e define se estamos no Model ou Paper Space
  (setq doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (if (= (getvar "CVPORT") 1)
    (setq space (vla-get-PaperSpace doc))
    (setq space (vla-get-ModelSpace doc))
  )
  
  (setq blkName (getstring t "\nDigite o nome do NOVO bloco a ser inserido (ex: co): "))
  
  (if (tblsearch "BLOCK" blkName)
    (progn
      (prompt "\nSelecione os blocos que servirão de referência: ")
      (if (setq ss (ssget '((0 . "INSERT"))))
        (progn
          (vla-StartUndoMark doc)
          (setq i 0)
          
          ;; ---------------------------------------------------------
          ;; A MÁGICA ACONTECE AQUI:
          ;; Lê a angulação atual do seu UCS em radianos.
          ;; Isso garante que o bloco fique "reto" em relação à sua TELA.
          (setq ucsRot (angle '(0 0 0) (getvar "UCSXDIR")))
          ;; ---------------------------------------------------------
          
          (while (< i (sslength ss))
            (setq ent (ssname ss i))
            (setq edata (entget ent))
            
            ;; 1. Coleta e extrai coordenadas exatas do Ponto Base
            (setq pt (cdr (assoc 10 edata)))
            (setq x (car pt))
            (setq y (cadr pt))
            
            ;; 2. Coleta propriedades de escala
            (setq sx (if (assoc 41 edata) (cdr (assoc 41 edata)) 1.0))
            (setq sy (if (assoc 42 edata) (cdr (assoc 42 edata)) 1.0))
            (setq sz (if (assoc 43 edata) (cdr (assoc 43 edata)) 1.0))
            
            (setq refLayer (if (assoc 8 edata) (cdr (assoc 8 edata)) "0"))
            
            ;; 3. Formata os textos finais (Com duas casas decimais)
            (setq strN (strcat "N: " (rtos y 2 2)))
            (setq strE (strcat "E: " (rtos x 2 2)))
            
            ;; 4. Insere o bloco usando a rotação do UCS atual
            (setq newBlk (vla-InsertBlock space (vlax-3d-point pt) blkName sx sy sz ucsRot))
            (vla-put-Layer newBlk refLayer)
            
            ;; 5. Edita os Atributos convertendo a array ActiveX de modo seguro
            (if (= (vla-get-HasAttributes newBlk) :vlax-true)
              (progn
                (setq attsList (vlax-safearray->list (vlax-variant-value (vla-GetAttributes newBlk))))
                (foreach att attsList
                  (setq tag (strcase (vla-get-TagString att)))
                  (cond
                    ((= tag "N") (vla-put-TextString att strN))
                    ((= tag "E") (vla-put-TextString att strE))
                  )
                )
              )
            )
            
            (setq i (1+ i))
          )
          
          (vla-EndUndoMark doc)
          (princ (strcat "\nSucesso! O bloco '" blkName "' foi inserido retinho com sua tela em " (itoa (sslength ss)) " posições."))
        )
        (princ "\nNenhum bloco de referência selecionado.")
      )
    )
    (princ (strcat "\nERRO: O bloco '" blkName "' não foi encontrado neste arquivo."))
  )
  (princ)
)