(vl-load-com)

;; ============================================================
;; MLRUA v2
;; Tratamento de MLINE utilizadas para representação de ruas
;;
;; FLUXO:
;;
;; MLINE
;;   ↓
;; EXPLODE
;;   ↓
;; limpeza de segmentos coincidentes
;;   ↓
;; identificação das polylines
;;   ↓
;; FILLET
;;   ↓
;; resultado final
;;
;; Comando:
;; MLRUA
;;
;; Raio padrão:
;; 2.00
;;
;; ============================================================


;; ------------------------------------------------------------
;; Distância entre dois pontos 2D
;; ------------------------------------------------------------

(defun MLRUA:Dist2D (p1 p2)
  (distance
    (list (car p1) (cadr p1) 0.0)
    (list (car p2) (cadr p2) 0.0)
  )
)


;; ------------------------------------------------------------
;; Tolerância geométrica
;; ------------------------------------------------------------

(defun MLRUA:Tol ()
  0.001
)


;; ------------------------------------------------------------
;; Retorna entidades criadas após uma entidade
;; ------------------------------------------------------------

(defun MLRUA:EntitiesAfter (ent / e lst)

  (setq lst '())
  (setq e (entnext ent))

  (while e
    (setq lst (cons e lst))
    (setq e (entnext e))
  )

  (reverse lst)
)


;; ------------------------------------------------------------
;; Obtém ponto inicial de uma LINE
;; ------------------------------------------------------------

(defun MLRUA:LineStart (e)
  (cdr (assoc 10 (entget e)))
)


;; ------------------------------------------------------------
;; Obtém ponto final de uma LINE
;; ------------------------------------------------------------

(defun MLRUA:LineEnd (e)
  (cdr (assoc 11 (entget e)))
)


;; ------------------------------------------------------------
;; Verifica se duas linhas são geometricamente iguais
;;
;; Aceita:
;;
;; A→B = C→D
;; A→B = D→C
;; ------------------------------------------------------------

(defun MLRUA:SameLine (e1 e2 / a b c d tol)

  (setq tol (MLRUA:Tol))

  (setq a (MLRUA:LineStart e1))
  (setq b (MLRUA:LineEnd   e1))

  (setq c (MLRUA:LineStart e2))
  (setq d (MLRUA:LineEnd   e2))

  (or
    (and
      (< (MLRUA:Dist2D a c) tol)
      (< (MLRUA:Dist2D b d) tol)
    )

    (and
      (< (MLRUA:Dist2D a d) tol)
      (< (MLRUA:Dist2D b c) tol)
    )
  )
)


;; ------------------------------------------------------------
;; Remove linhas exatamente duplicadas
;;
;; IMPORTANTE:
;; Não remove linhas que apenas se cruzam.
;; ------------------------------------------------------------

(defun MLRUA:RemoveDuplicates
       (ss / i j e1 e2 remove)

  (if ss

    (progn

      (setq i 0)

      (while (< i (sslength ss))

        (setq e1 (ssname ss i))
        (setq j (1+ i))

        (while (< j (sslength ss))

          (setq e2 (ssname ss j))

          (if
            (and
              (entget e1)
              (entget e2)
              (MLRUA:SameLine e1 e2)
            )

            (progn
              (entdel e2)
            )
          )

          (setq j (1+ j))
        )

        (setq i (1+ i))
      )
    )
  )
)


;; ------------------------------------------------------------
;; Seleciona linhas resultantes do EXPLODE
;; ------------------------------------------------------------

(defun MLRUA:GetLines (/ ss)

  (ssget
    "_P"
    '(
      (0 . "LINE")
    )
  )
)


;; ------------------------------------------------------------
;; EXPLODE das MLINE
;; ------------------------------------------------------------

(defun MLRUA:ExplodeMLines (ss / i e)

  (setq i 0)

  (while (< i (sslength ss))

    (setq e
      (ssname ss i)
    )

    (command-s
      "_.EXPLODE"
      e
      ""
    )

    (setq i (1+ i))
  )
)


;; ------------------------------------------------------------
;; Fillet das POLYLINE
;;
;; Aqui usamos o FILLET nativo do AutoCAD.
;; ------------------------------------------------------------

(defun MLRUA:Fillet
       (ss radius / i e)

  (if ss

    (progn

      (setvar "FILLETRAD" radius)

      (setq i 0)

      (while (< i (sslength ss))

        (setq e
          (ssname ss i)
        )

        (if
          (and
            (entget e)
            (member
              (cdr (assoc 0 (entget e)))
              '(
                "LWPOLYLINE"
                "POLYLINE"
              )
            )
          )

          (progn

            ;; FILLET na polyline inteira
            (command-s
              "_.FILLET"
              "_P"
              e
            )

          )
        )

        (setq i (1+ i))
      )
    )
  )
)


;; ------------------------------------------------------------
;; Recupera layer da primeira MLINE
;; ------------------------------------------------------------

(defun MLRUA:GetLayer (e)

  (cdr
    (assoc
      8
      (entget e)
    )
  )
)


;; ------------------------------------------------------------
;; Aplica layer aos objetos
;; ------------------------------------------------------------

(defun MLRUA:SetLayer (ss layer / i e data)

  (if
    (and ss layer)
    (progn

      (setq i 0)

      (while (< i (sslength ss))

        (setq e
          (ssname ss i)
        )

        (if (entget e)

          (progn

            (setq data
              (entget e)
            )

            (if (assoc 8 data)

              (progn

                (setq data
                  (subst
                    (cons 8 layer)
                    (assoc 8 data)
                    data
                  )
                )

                (entmod data)
              )
            )
          )
        )

        (setq i (1+ i))
      )
    )
  )
)


;; ============================================================
;; COMANDO PRINCIPAL
;; ============================================================

(defun c:MLRUA
  (/ *error*
     oldecho
     oldpedit
     ss
     ssLines
     ssPoly
     radius
     layer
     i
     e
     original
     backup
  )

  (vl-load-com)

  ;; ----------------------------------------------------------
  ;; ERROR HANDLER
  ;; ----------------------------------------------------------

  (defun *error* (msg)

    (setvar "CMDECHO" oldecho)
    (setvar "PEDITACCEPT" oldpedit)

    (if
      (and
        msg
        (/= msg "Function cancelled")
        (/= msg "quit / exit abort")
      )

      (prompt
        (strcat
          "\nERRO: "
          msg
        )
      )
    )

    (princ)
  )


  ;; ----------------------------------------------------------
  ;; Variáveis
  ;; ----------------------------------------------------------

  (setq oldecho
    (getvar "CMDECHO")
  )

  (setq oldpedit
    (getvar "PEDITACCEPT")
  )

  (setvar "CMDECHO" 0)
  (setvar "PEDITACCEPT" 1)


  ;; ----------------------------------------------------------
  ;; Seleção
  ;; ----------------------------------------------------------

  (prompt
    "\n=========================================="
  )

  (prompt
    "\n MLRUA - LIMPEZA E AJUSTE DE RUAS"
  )

  (prompt
    "\n=========================================="
  )

  (prompt
    "\nSelecione as MLINE das ruas:"
  )

  (setq ss
    (ssget
      '(
        (0 . "MLINE")
      )
    )
  )


  ;; ----------------------------------------------------------
  ;; Nenhuma seleção
  ;; ----------------------------------------------------------

  (if

    (null ss)

    (prompt
      "\nNenhuma MLINE selecionada."
    )

    (progn

      ;; ------------------------------------------------------
      ;; Layer da primeira MLINE
      ;; ------------------------------------------------------

      (setq layer
        (MLRUA:GetLayer
          (ssname ss 0)
        )
      )


      ;; ------------------------------------------------------
      ;; Guarda entidades originais
      ;; ------------------------------------------------------

      (setq original '())

      (setq i 0)

      (while (< i (sslength ss))

        (setq original
          (cons
            (ssname ss i)
            original
          )
        )

        (setq i
          (1+ i)
        )
      )


      ;; ------------------------------------------------------
      ;; Raio
      ;; ------------------------------------------------------

      (setq radius
        (getdist
          "\nRaio do arredondamento <2.00>: "
        )
      )

      (if
        (null radius)

        (setq radius 2.0)
      )


      ;; ------------------------------------------------------
      ;; Verificação
      ;; ------------------------------------------------------

      (if
        (<= radius 0.0)

        (prompt
          "\nRaio inválido. Operação cancelada."
        )

        (progn

          ;; --------------------------------------------------
          ;; EXPLODE
          ;; --------------------------------------------------

          (prompt
            "\n[1/5] Explodindo MLINE..."
          )

          (MLRUA:ExplodeMLines ss)


          ;; --------------------------------------------------
          ;; Recupera linhas
          ;; --------------------------------------------------

          (setq ssLines
            (MLRUA:GetLines
            )
          )


          ;; --------------------------------------------------
          ;; Remove duplicidades
          ;; --------------------------------------------------

          (if ssLines

            (progn

              (prompt
                "\n[2/5] Eliminando segmentos coincidentes..."
              )

              (MLRUA:RemoveDuplicates
                ssLines
              )
            )
          )


          ;; --------------------------------------------------
          ;; Atualiza seleção
          ;; --------------------------------------------------

          (setq ssLines
            (ssget
              "_P"
              '(
                (0 . "LINE")
              )
            )
          )


          ;; --------------------------------------------------
          ;; JOIN
          ;; --------------------------------------------------

          (if ssLines

            (progn

              (prompt
                "\n[3/5] Unindo segmentos..."
              )

              (command-s
                "_.PEDIT"
                "_M"
                ssLines
                ""
                "_Y"
                "_J"
                ""
                ""
              )
            )
          )


          ;; --------------------------------------------------
          ;; Recupera polylines
          ;; --------------------------------------------------

          (setq ssPoly
            (ssget
              "_P"
              '(
                (-4 . "<OR")
                (0 . "LWPOLYLINE")
                (0 . "POLYLINE")
                (-4 . "OR>")
              )
            )
          )


          ;; --------------------------------------------------
          ;; Layer
          ;; --------------------------------------------------

          (if ssPoly

            (MLRUA:SetLayer
              ssPoly
              layer
            )
          )


          ;; --------------------------------------------------
          ;; FILLET
          ;; --------------------------------------------------

          (if ssPoly

            (progn

              (prompt
                (strcat
                  "\n[4/5] Aplicando arredondamento R="
                  (rtos radius 2 2)
                  "..."
                )
              )

              (MLRUA:Fillet
                ssPoly
                radius
              )
            )
          )


          ;; --------------------------------------------------
          ;; Apaga MLINE originais
          ;; --------------------------------------------------

          (prompt
            "\n[5/5] Removendo MLINE originais..."
          )

          (foreach e original

            (if
              (entget e)

              (entdel e)
            )
          )


          ;; --------------------------------------------------
          ;; Final
          ;; --------------------------------------------------

          (prompt
            "\n=========================================="
          )

          (prompt
            "\n MLRUA CONCLUÍDO"
          )

          (prompt
            (strcat
              "\n Raio utilizado: "
              (rtos radius 2 2)
            )
          )

          (prompt
            "\n=========================================="
          )
        )
      )
    )
  )


  ;; ----------------------------------------------------------
  ;; Restaura
  ;; ----------------------------------------------------------

  (setvar "CMDECHO" oldecho)
  (setvar "PEDITACCEPT" oldpedit)

  (princ)
)


(princ "\nMLRUA carregado. Digite MLRUA para executar.")

(princ)