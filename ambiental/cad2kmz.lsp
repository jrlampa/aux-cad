;;; =============================================================================
;;; cad2kmz.lsp
;;; Exporta Postes (Pontos/Blocos) e Redes (Linhas/Polilinhas) do AutoCAD
;;; diretamente para arquivo Google Earth (.KMZ) georreferenciado
;;; Comando no AutoCAD: CAD2KMZ
;;; =============================================================================

(vl-load-com)

(defun c:CAD2KMZ (/ acadApp doc ssPts ssLines fusoStr fuso tempDir jsonFile kmzFile
                   pyScript cmd wsh i ent edata pt x y z blkName obj nPts idx ptCoords
                   f defaultKmz userKmz)

  (vl-load-com)
  (setq acadApp (vlax-get-acad-object))
  (setq doc (vla-get-ActiveDocument acadApp))

  (princ "\n==============================================================")
  (princ "\n    EXPORTADOR DIRETO AUTOCAD PARA GOOGLE EARTH (.KMZ)        ")
  (princ "\n==============================================================")

  ;; 1. Fuso UTM
  (setq fusoStr (getstring "\nInforme o Fuso UTM do Projeto [Padrão = 23]: "))
  (if (or (null fusoStr) (= fusoStr ""))
    (setq fuso 23)
    (setq fuso (atoi fusoStr))
  )

  ;; 2. Seleção de Postes (Pontos ou Blocos)
  (princ "\nSelecione os Postes/Pontos (Pressione Enter para selecionar TODOS do desenho): ")
  (setq ssPts (ssget '((0 . "POINT,INSERT"))))
  (if (not ssPts)
    (setq ssPts (ssget "X" '((0 . "POINT,INSERT"))))
  )

  ;; 3. Seleção de Redes e Linhas
  (princ "\nSelecione as Linhas da Rede (Pressione Enter para selecionar TODAS do desenho): ")
  (setq ssLines (ssget '((0 . "LINE,LWPOLYLINE"))))
  (if (not ssLines)
    (setq ssLines (ssget "X" '((0 . "LINE,LWPOLYLINE"))))
  )

  (if (and (not ssPts) (not ssLines))
    (progn
      (princ "\n[AVISO] Nenhuma entidade encontrada para exportar.")
      (princ)
      (exit)
    )
  )

  (setq tempDir (cond ((getvar "TEMP") (getvar "TEMP")) (T "C:\\Temp")))
  (setq jsonFile (strcat tempDir "\\cad2kmz_input.json"))

  ;; 4. Nome e Destino do KMZ
  (setq defaultKmz (strcat (getvar "DWGPREFIX") (vl-filename-base (getvar "DWGNAME")) ".kmz"))
  (setq userKmz (getfiled "Salvar Arquivo KMZ do Google Earth" defaultKmz "kmz" 1))
  (if (or (not userKmz) (= userKmz ""))
    (setq kmzFile defaultKmz)
    (setq kmzFile userKmz)
  )

  ;; 5. Gravação do JSON de Intercâmbio
  (setq f (open jsonFile "w"))
  (write-line "{" f)
  (write-line (strcat "  \"titulo\": \"" (vl-filename-base (getvar "DWGNAME")) "\",") f)
  (write-line (strcat "  \"fuso\": " (itoa fuso) ",") f)
  
  ;; Seção de Postes
  (write-line "  \"postes\": [" f)
  (if ssPts
    (progn
      (setq i 0)
      (while (< i (sslength ssPts))
        (setq ent (ssname ssPts i))
        (setq edata (entget ent))
        (setq pt (cdr (assoc 10 edata)))
        (setq x (car pt))
        (setq y (cadr pt))
        (setq z (if (caddr pt) (caddr pt) 0.0))
        (setq blkName "")
        (if (= (cdr (assoc 0 edata)) "INSERT")
          (setq blkName (cdr (assoc 2 edata)))
          (setq blkName "PONTO")
        )
        (write-line
          (strcat "    {\"id\": \"P" (itoa (1+ i)) "\", \"block\": \"" blkName "\", \"x\": " (rtos x 2 4) ", \"y\": " (rtos y 2 4) "}"
                  (if (< (1+ i) (sslength ssPts)) "," ""))
          f
        )
        (setq i (1+ i))
      )
    )
  )
  (write-line "  ]," f)

  ;; Seção de Linhas
  (write-line "  \"linhas\": [" f)
  (if ssLines
    (progn
      (setq i 0)
      (while (< i (sslength ssLines))
        (setq ent (ssname ssLines i))
        (setq edata (entget ent))
        (setq obj (vlax-ename->vla-object ent))
        (setq lay (cdr (assoc 8 edata)))

        (write-line "    {" f)
        (write-line (strcat "      \"layer\": \"" lay "\",") f)
        (write-line "      \"coords\": [" f)

        (cond
          ;; Linha Simples
          ((= (cdr (assoc 0 edata)) "LINE")
           (setq p1 (cdr (assoc 10 edata)))
           (setq p2 (cdr (assoc 11 edata)))
           (write-line (strcat "        [" (rtos (car p1) 2 4) ", " (rtos (cadr p1) 2 4) "],") f)
           (write-line (strcat "        [" (rtos (car p2) 2 4) ", " (rtos (cadr p2) 2 4) "]") f)
          )
          ;; Polilinha Leve (LWPOLYLINE)
          ((= (cdr (assoc 0 edata)) "LWPOLYLINE")
           (setq ptCoords '())
           (foreach item edata
             (if (= (car item) 10)
               (setq ptCoords (cons (cdr item) ptCoords))
             )
           )
           (setq ptCoords (reverse ptCoords))
           (setq idx 0)
           (while (< idx (length ptCoords))
             (setq p (nth idx ptCoords))
             (write-line
               (strcat "        [" (rtos (car p) 2 4) ", " (rtos (cadr p) 2 4) "]"
                       (if (< (1+ idx) (length ptCoords)) "," ""))
               f
             )
             (setq idx (1+ idx))
           )
          )
        )

        (write-line "      ]" f)
        (write-line (strcat "    }" (if (< (1+ i) (sslength ssLines)) "," "")) f)
        (setq i (1+ i))
      )
    )
  )
  (write-line "  ]" f)
  (write-line "}" f)
  (close f)

  ;; 6. Execução do Script Python
  (setq pyScript "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\ambiental\\cad_to_kmz_exporter.py")
  (if (not (findfile pyScript))
    (setq pyScript (findfile "cad_to_kmz_exporter.py"))
  )

  (princ (strcat "\nGerando arquivo KMZ do Google Earth: " kmzFile " ..."))

  (setq cmd (strcat "python \"" pyScript "\" \"" jsonFile "\" \"" kmzFile "\" " (itoa fuso)))
  (setq wsh (vlax-create-object "WScript.Shell"))
  (if wsh
    (progn
      (vlax-invoke-method wsh "Run" (strcat "cmd.exe /c " cmd) 0 :vlax-true)
      (vlax-release-object wsh)
    )
    (startapp "cmd.exe" (strcat "/c " cmd))
  )

  (princ (strcat "\n✔ Arquivo KMZ exportado com sucesso!\nSalvo em: " kmzFile))
  (princ)
)

(princ "\n[CAD2KMZ] Carregado! Digite CAD2KMZ para exportar o projeto para o Google Earth.")
(princ)
