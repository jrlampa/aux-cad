;;; =============================================================================
;;; croqui_cad_inserter.lsp
;;; Insere automaticamente a Ortofoto / Croqui de Satélite Ambiental no AutoCAD
;;; Funciona perfeitamente tanto no ModelSpace (em metros) quanto no PaperSpace (prancha)
;;; Comando no AutoCAD: INSCROQUI
;;; =============================================================================

(vl-load-com)

(defun c:INSCROQUI (/ acadApp doc space imgPath curDir tempDir foundList file pt defScale scaleStr userScale rasterObj)
  (setq acadApp (vlax-get-acad-object))
  (setq doc (vla-get-ActiveDocument acadApp))
  
  ;; Determina se está no PaperSpace (Layout) ou ModelSpace
  (if (= (getvar "CVPORT") 1)
    (setq space (vla-get-PaperSpace doc)
          defScale 180.0)  ;; No PaperSpace: padrão 180 mm (cabe perfeito em prancha A3/A4)
    (setq space (vla-get-ModelSpace doc)
          defScale 120.0)  ;; No ModelSpace: padrão 120 metros
  )

  (princ "\n============================================================")
  (princ "\n     INSERÇÃO AUTOMÁTICA DE ORTOFOTO / CROQUI AMBIENTAL      ")
  (princ "\n============================================================")

  ;; 1. Localiza imagens geradas recentemente
  (setq imgPath nil)
  (setq curDir (getvar "DWGPREFIX"))
  (setq tempDir (cond ((getvar "TEMP") (getvar "TEMP")) (T "C:\\Temp")))

  ;; Varre possíveis locais pelo arquivo mais recente
  (setq foundList (vl-directory-files curDir "CROQUI_AMBIENTAL_*.png" 1))
  (if foundList
    (setq imgPath (strcat curDir (last (vl-sort foundList '<))))
  )

  (if (not imgPath)
    (progn
      (setq foundList (vl-directory-files tempDir "CROQUI_AMBIENTAL_*.png" 1))
      (if foundList
        (setq imgPath (strcat tempDir "\\" (last (vl-sort foundList '<))))
      )
    )
  )

  ;; Se não achar automático, abre diálogo para selecionar
  (if (or (not imgPath) (not (findfile imgPath)))
    (setq imgPath (getfiled "Selecione o Croqui / Ortofoto (.png)" curDir "png" 16))
  )

  (if (or (not imgPath) (not (findfile imgPath)))
    (progn
      (princ "\n[AVISO] Nenhuma imagem de croqui foi selecionada.")
      (princ)
      (exit)
    )
  )

  (princ (strcat "\nImagem selecionada: " imgPath))

  ;; 2. Ponto de Inserção
  (setq pt (getpoint "\nClique no Ponto de Inserção para a Ortofoto: "))
  (if (not pt)
    (progn
      (princ "\nOperação cancelada pelo usuário.")
      (princ)
      (exit)
    )
  )

  ;; 3. Escala / Largura da imagem
  (setq scaleStr (getstring (strcat "\nInforme a Largura da imagem no desenho [Padrão = " (rtos defScale 2 1) "]: ")))
  (if (or (null scaleStr) (= scaleStr ""))
    (setq userScale defScale)
    (setq userScale (atof scaleStr))
  )

  ;; 4. Inserção nativa via ActiveX (AddRaster)
  (setq rasterObj
    (vl-catch-all-apply
      'vla-AddRaster
      (list space imgPath (vlax-3d-point pt) userScale 0.0)
    )
  )

  (if (vl-catch-all-error-p rasterObj)
    (princ (strcat "\n[ERRO] Falha ao inserir imagem: " (vl-catch-all-error-message rasterObj)))
    (progn
      (vla-put-Transparency rasterObj :vlax-true)
      (vla-Update rasterObj)
      (princ "\n✔ Ortofoto / Croqui inserido com sucesso!")
    )
  )
  (princ)
)

(princ "\n[INSCROQUI] Comando carregado! Digite INSCROQUI para inserir a ortofoto no CAD.")
(princ)
