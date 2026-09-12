;;; ==========================================================================
;;; Módulo: autoprancha.lsp
;;; Responsabilidade Única: Enquadramento automático e inserção de pranchas
;;; diretamente no ModelSpace (Padrão Enel / HBT Engenharia).
;;; Comandos: AUTOPRANCHA, PRANCHA, ENQUADRAR, FOLHA, RECARREGAR_PRANCHA
;;; ==========================================================================

(vl-load-com)

;; --------------------------------------------------------------------------
;; Definição dos Formatos ABNT / NBR 10068 e Margens (em milímetros)
;; --------------------------------------------------------------------------
(defun prancha-get-tabela-formatos ()
  ;; Retorna: (Nome Larg_mm Alt_mm Marg_Esq Marg_Dir Marg_Sup Marg_Inf)
  '(
    ("A0" 1189.0 841.0 25.0 10.0 10.0 10.0)
    ("A1"  841.0 594.0 25.0 10.0 10.0 10.0)
    ("A2"  594.0 420.0 25.0 10.0 10.0 10.0)
    ("A3"  420.0 297.0 25.0 10.0 10.0 10.0)
    ("A4"  297.0 210.0 25.0 10.0 10.0 10.0)
   )
)

(defun prancha-escalas-normativas ()
  '(500 750 1000 1250 1500 2000)
)

;; --------------------------------------------------------------------------
;; Funções Auxiliares de Cálculo de Enquadramento
;; --------------------------------------------------------------------------
(defun prancha-calcular-melhor-opcao (dx dy esc-fixa fmt-fixo / 
                                      tbl-fmt escalas melhor-res menor-area-sobra
                                      dx-nec dy-nec)
  ;; Adiciona folga de respiro de 10%
  (setq dx-nec (* dx 1.10)
        dy-nec (* dy 1.10)
        tbl-fmt (prancha-get-tabela-formatos)
        escalas (if esc-fixa (list esc-fixa) (prancha-escalas-normativas))
        melhor-res nil
        menor-area-sobra 1.0e15)

  (if fmt-fixo
    (setq tbl-fmt (vl-remove-if-not '(lambda (f) (= (car f) (strcase fmt-fixo))) tbl-fmt))
  )

  (foreach f tbl-fmt
    (setq fname (nth 0 f)
          flarg (nth 1 f)
          falt  (nth 2 f)
          mesq  (nth 3 f)
          mdir  (nth 4 f)
          msup  (nth 5 f)
          minf  (nth 6 f)
          lu-mm (- flarg (+ mesq mdir))
          au-mm (- falt  (+ msup minf)))

    (foreach esc escalas
      (setq fator (/ (float esc) 1000.0)
            lu-m  (* lu-mm fator)
            au-m  (* au-mm fator)
            lf-m  (* flarg fator)
            af-m  (* falt  fator))

      (if (and (>= lu-m dx-nec) (>= au-m dy-nec))
        (progn
          (setq area-util (* lu-m au-m)
                area-proj (* dx dy)
                sobra     (- area-util area-proj))
          ;; Bônus de preferência para escala 1:1000 e formato A1 (padrão Enel)
          (if (= esc 1000) (setq sobra (- sobra (* area-proj 0.15))))
          (if (= fname "A1") (setq sobra (- sobra (* area-proj 0.20))))

          (if (< sobra menor-area-sobra)
            (setq menor-area-sobra sobra
                  melhor-res (list fname esc fator lf-m af-m lu-m au-m mesq minf flarg falt))
          )
        )
      )
    )
  )

  ;; Fallback para A0 1:2000 caso o projeto seja gigantesco
  (if (null melhor-res)
    (setq melhor-res (list "A0" 2000 2.0 (* 1189.0 2.0) (* 841.0 2.0) (* 1154.0 2.0) (* 821.0 2.0) 25.0 10.0 1189.0 841.0))
  )
  melhor-res
)

;; --------------------------------------------------------------------------
;; Criação de Camadas (Layers) Padrão
;; --------------------------------------------------------------------------
(defun prancha-garantir-layers ()
  (setvar "CMDECHO" 0)
  (if (null (tblsearch "layer" "A-PRANCHA"))
    (command "_.layer" "_m" "A-PRANCHA" "_c" "7" "" "_lw" "0.15" "" "")
  )
  (if (null (tblsearch "layer" "A-PRANCHA-MARGEM"))
    (command "_.layer" "_m" "A-PRANCHA-MARGEM" "_c" "4" "" "_lw" "0.50" "" "")
  )
  (if (null (tblsearch "layer" "A-PRANCHA-DOBRA"))
    (command "_.layer" "_m" "A-PRANCHA-DOBRA" "_c" "8" "" "_lw" "0.09" "" "")
  )
  (if (null (tblsearch "layer" "A-PRANCHA-CARIMBO"))
    (command "_.layer" "_m" "A-PRANCHA-CARIMBO" "_c" "7" "" "_lw" "0.25" "" "")
  )
  (setvar "CMDECHO" 1)
  (princ)
)

;; --------------------------------------------------------------------------
;; Desenho da Borda Externa e Margem Interna (LWPOLYLINE)
;; --------------------------------------------------------------------------
(defun prancha-desenhar-retangulo (pmin pmax layer lweight / x1 y1 x2 y2 p1 p2 p3 p4)
  (setq x1 (car pmin)  y1 (cadr pmin)
        x2 (car pmax)  y2 (cadr pmax)
        p1 (list x1 y1)
        p2 (list x2 y1)
        p3 (list x2 y2)
        p4 (list x1 y2))
  (entmake
    (list
      '(0 . "LWPOLYLINE")
      '(100 . "AcDbEntity")
      (cons 8 layer)
      '(100 . "AcDbPolyline")
      '(90 . 4)
      '(70 . 1) ; Fechada
      (cons 43 (if lweight lweight 0.0))
      (cons 10 p1)
      (cons 10 p2)
      (cons 10 p3)
      (cons 10 p4)
    )
  )
)

;; --------------------------------------------------------------------------
;; Inserção e Desenho do Carimbo Enel / HBT no Canto Inferior Direito
;; --------------------------------------------------------------------------
(defun prancha-desenhar-carimbo (p-canto-dir fator esc data-str /
                                 c-larg c-alt p-min-c p-max-c txt-h)
  ;; Carimbo: 185 mm de largura x 60 mm de altura x fator de escala
  (setq c-larg (* 185.0 fator)
        c-alt  (* 60.0  fator)
        p-min-c (list (- (car p-canto-dir) c-larg) (cadr p-canto-dir))
        p-max-c (list (car p-canto-dir) (+ (cadr p-canto-dir) c-alt))
        txt-h   (* 2.2 fator))

  ;; Contorno do Carimbo
  (prancha-desenhar-retangulo p-min-c p-max-c "A-PRANCHA-CARIMBO" 0.0)

  ;; Linhas divisórias horizontais do carimbo
  (setvar "CMDECHO" 0)
  (command "_.line" "_none" (list (car p-min-c) (+ (cadr p-min-c) (* 20.0 fator)))
                    "_none" (list (car p-max-c) (+ (cadr p-min-c) (* 20.0 fator))) "")
  (command "_.line" "_none" (list (car p-min-c) (+ (cadr p-min-c) (* 40.0 fator)))
                    "_none" (list (car p-max-c) (+ (cadr p-min-c) (* 40.0 fator))) "")

  ;; Linha divisória vertical inferior (Escala / Data / Folha)
  (command "_.line" "_none" (list (+ (car p-min-c) (* 60.0 fator)) (cadr p-min-c))
                    "_none" (list (+ (car p-min-c) (* 60.0 fator)) (+ (cadr p-min-c) (* 20.0 fator))) "")
  (command "_.line" "_none" (list (+ (car p-min-c) (* 125.0 fator)) (cadr p-min-c))
                    "_none" (list (+ (car p-min-c) (* 125.0 fator)) (+ (cadr p-min-c) (* 20.0 fator))) "")

  ;; Textos do Carimbo
  (command "_.text" "_none" (list (+ (car p-min-c) (* 5.0 fator)) (+ (cadr p-min-c) (* 50.0 fator)))
           (* 3.0 fator) "0" "ENEL BRASIL")
  (command "_.text" "_none" (list (+ (car p-min-c) (* 5.0 fator)) (+ (cadr p-min-c) (* 43.0 fator)))
           (* 2.2 fator) "0" "DISTRIBUICAO DE ENERGIA")

  (command "_.text" "_none" (list (+ (car p-min-c) (* 5.0 fator)) (+ (cadr p-min-c) (* 31.0 fator)))
           (* 2.8 fator) "0" "PROJETO DE REDE DE DISTRIBUICAO")
  (command "_.text" "_none" (list (+ (car p-min-c) (* 5.0 fator)) (+ (cadr p-min-c) (* 23.0 fator)))
           (* 2.0 fator) "0" "HBT ENGENHARIA - PROJETOS ELETRICOS")

  ;; Bloco de rodapé: Escala, Data e Folha
  (command "_.text" "_none" (list (+ (car p-min-c) (* 5.0 fator)) (+ (cadr p-min-c) (* 13.0 fator)))
           (* 1.8 fator) "0" "ESCALA:")
  (command "_.text" "_none" (list (+ (car p-min-c) (* 5.0 fator)) (+ (cadr p-min-c) (* 5.0 fator)))
           (* 2.5 fator) "0" (strcat "1:" (itoa esc)))

  (command "_.text" "_none" (list (+ (car p-min-c) (* 65.0 fator)) (+ (cadr p-min-c) (* 13.0 fator)))
           (* 1.8 fator) "0" "DATA:")
  (command "_.text" "_none" (list (+ (car p-min-c) (* 65.0 fator)) (+ (cadr p-min-c) (* 5.0 fator)))
           (* 2.2 fator) "0" data-str)

  (command "_.text" "_none" (list (+ (car p-min-c) (* 130.0 fator)) (+ (cadr p-min-c) (* 13.0 fator)))
           (* 1.8 fator) "0" "PRANCHA:")
  (command "_.text" "_none" (list (+ (car p-min-c) (* 130.0 fator)) (+ (cadr p-min-c) (* 5.0 fator)))
           (* 2.5 fator) "0" "01 / 01")

  (setvar "CMDECHO" 1)
  (princ)
)

;; --------------------------------------------------------------------------
;; Marcas de Dobra da Folha (Padrão ABNT 185mm / 210mm)
;; --------------------------------------------------------------------------
(defun prancha-desenhar-marcas-dobra (pmin pmax fator flarg / xmin ymin xmax ymax mlen x-dobra)
  (setq xmin (car pmin)  ymin (cadr pmin)
        xmax (car pmax)  ymax (cadr pmax)
        mlen (* 5.0 fator)) ; Linhas discretas de 5mm
  (setvar "CMDECHO" 0)
  ;; Marcas de dobra a partir da borda direita (módulos de 185mm no papel)
  (setq x-dobra (- xmax (* 185.0 fator)))
  (while (> x-dobra (+ xmin (* 210.0 fator)))
    (command "_.line" "_none" (list x-dobra ymin) "_none" (list x-dobra (+ ymin mlen)) "")
    (command "_.line" "_none" (list x-dobra ymax) "_none" (list x-dobra (- ymax mlen)) "")
    (setq x-dobra (- x-dobra (* 185.0 fator)))
  )
  (setvar "CMDECHO" 1)
  (princ)
)

;; --------------------------------------------------------------------------
;; Comando Principal: AUTOPRANCHA
;; --------------------------------------------------------------------------
(defun c:AUTOPRANCHA (/ pt1 pt2 xmin xmax ymin ymax dx dy cx cy
                        modo esc-fixa fmt-fixo res fname esc fator
                        lf-m af-m lu-m au-m mesq minf flarg falt
                        f-xmin f-ymin f-xmax f-ymax
                        m-xmin m-ymin m-xmax m-ymax
                        pmin-f pmax-f pmin-m pmax-m
                        data-str conf)
  (setvar "CMDECHO" 0)
  (princ "\n=======================================================")
  (princ "\n [AUTOPRANCHA] Enquadramento Inteligente de Prancha")
  (princ "\n Posicionamento direto no ModelSpace (Padrão Enel / HBT)")
  (princ "\n=======================================================")

  ;; 1. Captura da área em diagonal com retângulo elástico dinâmico
  (setq pt1 (getpoint "\nClique no 1º canto da área do projeto (diagonal): "))
  (if (null pt1)
    (progn (princ "\n[AUTOPRANCHA] Comando cancelado pelo usuário.") (exit))
  )

  (setq pt2 (getcorner pt1 "\nClique no 2º canto oposto: "))
  (if (null pt2)
    (progn (princ "\n[AUTOPRANCHA] Comando cancelado pelo usuário.") (exit))
  )

  ;; 2. Cálculo dos limites e centro da área
  (setq xmin (min (car pt1) (car pt2))
        xmax (max (car pt1) (car pt2))
        ymin (min (cadr pt1) (cadr pt2))
        ymax (max (cadr pt1) (cadr pt2))
        dx   (max 0.1 (- xmax xmin))
        dy   (max 0.1 (- ymax ymin))
        cx   (/ (+ xmin xmax) 2.0)
        cy   (/ (+ ymin ymax) 2.0))

  ;; 3. Opções de cálculo
  (initget "Auto Escala Formato")
  (setq modo (getkword "\nModo de cálculo [Auto / Escala / Formato] <Auto>: "))
  (if (null modo) (setq modo "Auto"))

  (setq esc-fixa nil fmt-fixo nil)
  (cond
    ((= modo "Escala")
     (initget 6)
     (setq esc-fixa (getint "\nInforme a escala desejada [500, 750, 1000, 1250, 1500, 2000] <1000>: "))
     (if (null esc-fixa) (setq esc-fixa 1000))
    )
    ((= modo "Formato")
     (initget "A3 A2 A1 A0")
     (setq fmt-fixo (getkword "\nInforme o formato desejado [A3 / A2 / A1 / A0] <A1>: "))
     (if (null fmt-fixo) (setq fmt-fixo "A1"))
    )
  )

  ;; 4. Cálculo matemático do enquadramento
  (setq res (prancha-calcular-melhor-opcao dx dy esc-fixa fmt-fixo))
  (setq fname (nth 0 res)
        esc   (nth 1 res)
        fator (nth 2 res)
        lf-m  (nth 3 res)
        af-m  (nth 4 res)
        lu-m  (nth 5 res)
        au-m  (nth 6 res)
        mesq  (nth 7 res)
        minf  (nth 8 res)
        flarg (nth 9 res)
        falt  (nth 10 res))

  ;; 5. Apresentação do Resumo ao Usuário
  (princ "\n-------------------------------------------------------")
  (princ (strcat "\n ENQUADRAMENTO CALCULADO (ENEL / HBT):"))
  (princ (strcat "\n - Área da rede selecionada : " (rtos dx 2 1) "m x " (rtos dy 2 1) "m"))
  (princ (strcat "\n - Formato de papel sugerido: " fname " (" (rtos flarg 2 0) " x " (rtos falt 2 0) " mm)"))
  (princ (strcat "\n - Escala de projeto        : 1:" (itoa esc)))
  (princ (strcat "\n - Dimensão da folha (Model): " (rtos lf-m 2 1) "m x " (rtos af-m 2 1) "m"))
  (princ (strcat "\n - Área útil de desenho     : " (rtos lu-m 2 1) "m x " (rtos au-m 2 1) "m"))
  (princ "\n-------------------------------------------------------")

  (initget "Sim Nao")
  (setq conf (getkword "\nConfirmar inserção da prancha no ModelSpace? [Sim / Não] <Sim>: "))
  (if (or (null conf) (= conf "Sim"))
    (progn
      ;; 6. Garantir camadas
      (prancha-garantir-layers)

      ;; 7. Calcular coordenadas exatas no ModelSpace
      ;; Centro útil coincide perfeitamente com o centro da rede (cx, cy)
      (setq f-xmin (- cx (* (+ mesq (/ (- flarg (+ mesq 10.0)) 2.0)) fator))
            f-ymin (- cy (* (+ minf (/ (- falt  (+ minf 10.0)) 2.0)) fator))
            f-xmax (+ f-xmin lf-m)
            f-ymax (+ f-ymin af-m)
            m-xmin (+ f-xmin (* mesq fator))
            m-ymin (+ f-ymin (* minf fator))
            m-xmax (- f-xmax (* 10.0 fator))
            m-ymax (- f-ymax (* 10.0 fator))
            pmin-f (list f-xmin f-ymin)
            pmax-f (list f-xmax f-ymax)
            pmin-m (list m-xmin m-ymin)
            pmax-m (list m-xmax m-ymax))

      ;; 8. Desenhar Borda Externa (A-PRANCHA)
      (prancha-desenhar-retangulo pmin-f pmax-f "A-PRANCHA" nil)

      ;; 9. Desenhar Margem Interna (A-PRANCHA-MARGEM)
      (prancha-desenhar-retangulo pmin-m pmax-m "A-PRANCHA-MARGEM" (* 0.50 fator))

      ;; 10. Desenhar Marcas de Dobra (A-PRANCHA-DOBRA)
      (prancha-desenhar-marcas-dobra pmin-f pmax-f fator flarg)

      ;; 11. Data formatada para o carimbo
      (setq data-str (menucmd "M=$(edtime,$(getvar,date),DD/MO/YYYY)"))
      (if (or (null data-str) (= data-str ""))
        (setq data-str "12/09/2026")
      )

      ;; 12. Desenhar Carimbo no Canto Inferior Direito da Margem
      (prancha-desenhar-carimbo (list m-xmax m-ymin) fator esc data-str)

      ;; 13. Zoom na folha inserida
      (command "_.zoom" "_w" "_none" pmin-f "_none" pmax-f)

      (princ (strcat "\n[AUTOPRANCHA] Prancha " fname " (1:" (itoa esc) ") inserida e enquadrada com sucesso no ModelSpace!"))
    )
    (princ "\n[AUTOPRANCHA] Operação cancelada.")
  )
  (setvar "CMDECHO" 1)
  (princ)
)

;; --------------------------------------------------------------------------
;; Comandos e Atalhos Alternativos
;; --------------------------------------------------------------------------
(defun c:PRANCHA () (c:AUTOPRANCHA))
(defun c:ENQUADRAR () (c:AUTOPRANCHA))
(defun c:FOLHA () (c:AUTOPRANCHA))

(defun c:RECARREGAR_PRANCHA ()
  (setvar "CMDECHO" 0)
  (load "prancha/autoprancha.lsp")
  (setvar "CMDECHO" 1)
  (princ "\n[AUTOPRANCHA] Rotina recarregada com sucesso!")
  (princ)
)

(princ "\n[AUTOPRANCHA] Módulo carregado! Digite AUTOPRANCHA ou PRANCHA para iniciar.")
(princ)
