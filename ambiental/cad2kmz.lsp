;;; =============================================================================
;;; cad2kmz.lsp
;;; Exporta Postes (Pontos/Blocos) e Redes (Linhas/Polilinhas) do AutoCAD
;;; diretamente para arquivo Google Earth (.KMZ) georreferenciado
;;; Comando no AutoCAD: CAD2KMZ
;;; =============================================================================

(vl-load-com)

;; Sanitiza strings para não corromper a sintaxe do JSON
(defun cad2kmz-clean-str (str /)
  (if (or (null str) (not (stringp str)))
    ""
    (vl-string-translate "\"\\\n\r\t" "'/   " str)
  )
)

;; Tenta extrair o atributo de número de um bloco (ex: NUMERO, NUM, PONTO)
(defun cad2kmz-get-attr-num (ent / next found val tag ed)
  (setq next (entnext ent) found nil val "")
  (while (and next (not found))
    (setq ed (entget next))
    (if (= (cdr (assoc 0 ed)) "ATTRIB")
      (progn
        (setq tag (strcase (cdr (assoc 2 ed))))
        (if (or (vl-string-search "NUM" tag)
                (vl-string-search "PONTO" tag)
                (= tag "N")
                (= tag "Nº")
                (= tag "POSTE"))
          (progn
            (setq val (vl-string-trim " " (cdr (assoc 1 ed))))
            (if (/= val "") (setq found T))
          )
        )
      )
      (if (= (cdr (assoc 0 ed)) "SEQEND")
        (setq found T)
      )
    )
    (setq next (entnext next))
  )
  val
)

(defun c:CAD2KMZ (/ acadApp doc ssPts ssLines fusoStr fuso jsonFile logFile kmzFile
                   pyScript cmd wsh i ent edata pt x y blkName pid obj lay ptCoords
                   sub idx p p1 p2 f defaultKmz userKmz dwgName dwgPrefix log_txt
                   f_log line_log)

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
  (if (or (< fuso 18) (> fuso 25)) (setq fuso 23))

  ;; 2. Seleção de Postes (Pontos ou Blocos)
  (princ "\nSelecione os Postes/Pontos (Pressione Enter para selecionar TODOS do desenho): ")
  (setq ssPts (ssget '((0 . "POINT,INSERT"))))
  (if (not ssPts)
    (setq ssPts (ssget "X" '((0 . "POINT,INSERT"))))
  )

  ;; 3. Seleção de Redes e Linhas
  (princ "\nSelecione as Linhas da Rede (Pressione Enter para selecionar TODAS do desenho): ")
  (setq ssLines (ssget '((0 . "LINE,LWPOLYLINE,POLYLINE"))))
  (if (not ssLines)
    (setq ssLines (ssget "X" '((0 . "LINE,LWPOLYLINE,POLYLINE"))))
  )

  (if (and (not ssPts) (not ssLines))
    (progn
      (princ "\n[AVISO] Nenhuma entidade linear ou pontual encontrada para exportar.")
      (princ)
    )
    (progn
      ;; 4. Nome e Destino do KMZ
      (setq dwgName (getvar "DWGNAME"))
      (setq dwgPrefix (getvar "DWGPREFIX"))
      (if (or (null dwgName) (= dwgName "")) (setq dwgName "Projeto_Rede"))
      (if (or (null dwgPrefix) (= dwgPrefix "")) (setq dwgPrefix "C:\\Temp\\"))

      (setq defaultKmz (strcat dwgPrefix (vl-filename-base dwgName) ".kmz"))
      (setq userKmz (getfiled "Salvar Arquivo KMZ do Google Earth" defaultKmz "kmz" 1))

      (if (or (null userKmz) (= userKmz ""))
        (princ "\n[INFO] Exportação cancelada pelo usuário.")
        (progn
          (setq kmzFile userKmz)

          ;; 5. Arquivos temporários protegidos (pasta Temp do usuário)
          (setq jsonFile (vl-filename-mktemp "cad2kmz_in.json"))
          (setq logFile  (vl-filename-mktemp "cad2kmz_log.txt"))

          ;; 6. Gravação do JSON de Intercâmbio
          (setq f (open jsonFile "w"))
          (if (not f)
            (princ (strcat "\n[ERRO] Não foi possível criar o arquivo de troca temporário em: " jsonFile))
            (progn
              (write-line "{" f)
              (write-line (strcat "  \"titulo\": \"" (cad2kmz-clean-str (vl-filename-base dwgName)) "\",") f)
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
                    (setq blkName "PONTO")
                    (setq pid (strcat "P" (itoa (1+ i))))

                    (if (= (cdr (assoc 0 edata)) "INSERT")
                      (progn
                        (setq blkName (cdr (assoc 2 edata)))
                        (setq attrVal (cad2kmz-get-attr-num ent))
                        (if (and attrVal (/= attrVal ""))
                          (setq pid attrVal)
                        )
                      )
                    )

                    (write-line
                      (strcat "    {\"id\": \"" (cad2kmz-clean-str pid) "\", "
                              "\"block\": \"" (cad2kmz-clean-str blkName) "\", "
                              "\"x\": " (rtos x 2 4) ", "
                              "\"y\": " (rtos y 2 4) "}"
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
                    (setq lay (cdr (assoc 8 edata)))
                    (if (null lay) (setq lay "REDE"))
                    (setq ptCoords '())

                    (cond
                      ;; Linha Simples (LINE)
                      ((= (cdr (assoc 0 edata)) "LINE")
                       (setq p1 (cdr (assoc 10 edata)))
                       (setq p2 (cdr (assoc 11 edata)))
                       (setq ptCoords (list (list (car p1) (cadr p1)) (list (car p2) (cadr p2))))
                      )

                      ;; Polilinha Leve (LWPOLYLINE)
                      ((= (cdr (assoc 0 edata)) "LWPOLYLINE")
                       (foreach item edata
                         (if (= (car item) 10)
                           (setq ptCoords (cons (cdr item) ptCoords))
                         )
                       )
                       (setq ptCoords (reverse ptCoords))
                      )

                      ;; Polilinha Clássica 2D/3D (POLYLINE)
                      ((= (cdr (assoc 0 edata)) "POLYLINE")
                       (setq sub (entnext ent))
                       (while (and sub (= (cdr (assoc 0 (entget sub))) "VERTEX"))
                         (setq p (cdr (assoc 10 (entget sub))))
                         (setq ptCoords (cons (list (car p) (cadr p)) ptCoords))
                         (setq sub (entnext sub))
                       )
                       (setq ptCoords (reverse ptCoords))
                      )
                    )

                    (if (and ptCoords (>= (length ptCoords) 2))
                      (progn
                        (write-line "    {" f)
                        (write-line (strcat "      \"layer\": \"" (cad2kmz-clean-str lay) "\",") f)
                        (write-line "      \"coords\": [" f)

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

                        (write-line "      ]" f)
                        (write-line (strcat "    }" (if (< (1+ i) (sslength ssLines)) "," "")) f)
                      )
                    )
                    (setq i (1+ i))
                  )
                )
              )
              (write-line "  ]" f)
              (write-line "}" f)
              (close f)

              ;; 7. Localização do Script Python do Exportador
              (setq pyScript nil)
              (if (and (boundp '*aux-cad-root*) *aux-cad-root*)
                (setq pyScript (findfile (strcat *aux-cad-root* "ambiental\\cad_to_kmz_exporter.py")))
              )
              (if (not pyScript)
                (setq pyScript (findfile "ambiental\\cad_to_kmz_exporter.py"))
              )
              (if (not pyScript)
                (setq pyScript (findfile "cad_to_kmz_exporter.py"))
              )
              (if (not pyScript)
                (setq pyScript "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\ambiental\\cad_to_kmz_exporter.py")
              )

              (princ (strcat "\nGerando arquivo KMZ do Google Earth: " kmzFile " ..."))

              ;; Execução protegida com redirecionamento para log de diagnóstico
              (setq cmd (strcat "\"python \"" pyScript "\" \"" jsonFile "\" \"" kmzFile "\" " (itoa fuso) " > \"" logFile "\" 2>&1\""))

              (setq wsh (vl-catch-all-apply 'vlax-create-object (list "WScript.Shell")))
              (if (and wsh (not (vl-catch-all-error-p wsh)))
                (progn
                  (vl-catch-all-apply 'vlax-invoke-method (list wsh "Run" (strcat "cmd.exe /c " cmd) 0 :vlax-true))
                  (vlax-release-object wsh)
                )
                (progn
                  (startapp "cmd.exe" (strcat "/c " cmd))
                  (command "_.DELAY" "2000")
                )
              )

              ;; 8. Verificação do Arquivo KMZ Gerado
              (if (and (findfile kmzFile) (> (vl-file-size kmzFile) 100))
                (progn
                  (princ "\n==============================================================")
                  (princ (strcat "\n✔ ARQUIVO KMZ EXPORTADO COM SUCESSO!\nSalvo em: " kmzFile))
                  (princ "\n==============================================================")
                  (alert (strcat "Exportação para o Google Earth concluída com sucesso!\n\nArquivo salvo em:\n" kmzFile))
                )
                (progn
                  (setq log_txt "")
                  (if (findfile logFile)
                    (progn
                      (setq f_log (open logFile "r"))
                      (while (and (setq line_log (read-line f_log)) (< (strlen log_txt) 600))
                        (setq log_txt (strcat log_txt line_log "\n"))
                      )
                      (close f_log)
                    )
                  )
                  (if (= (vl-string-trim " \n\r\t" log_txt) "")
                    (setq log_txt "Verifique se o Python está acessível ou se o destino possui permissão de gravação.")
                  )
                  (alert (strcat "ERRO AO GERAR ARQUIVO KMZ:\n\n" log_txt))
                )
              )

              ;; Limpeza dos arquivos temporários
              (if (findfile jsonFile) (vl-file-delete jsonFile))
              (if (findfile logFile)  (vl-file-delete logFile))
            )
          )
        )
      )
    )
  )

  (princ)
)

;; Aliases para facilidade de digitação
(defun c:DWG2KMZ () (c:CAD2KMZ))
(defun c:EXPORTARKMZ () (c:CAD2KMZ))

(princ "\n[CAD2KMZ] Carregado! Digite CAD2KMZ para exportar postes e redes para o Google Earth.")
(princ)
