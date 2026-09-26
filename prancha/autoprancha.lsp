;;; ==========================================================================
;;; Módulo: autoprancha.lsp
;;; Responsabilidade Única: Enquadramento inteligente e inserção de pranchas
;;; oficiais (PRANCHA / PRANCHA_A4) diretamente no ModelSpace com carimbo IM3.
;;; Comandos: AUTOPRANCHA, PRANCHA, ENQUADRAR, FOLHA, RECARREGAR_PRANCHA
;;; ==========================================================================

(vl-load-com)

;; --------------------------------------------------------------------------
;; Tabela de Formatos Normativos e Margens ABNT (milímetros)
;; --------------------------------------------------------------------------
(defun prancha-get-tabela-formatos ()
  ;; Retorna: (Nome Larg_mm Alt_mm Marg_Esq Marg_Dir Marg_Sup Marg_Inf Bloco)
  '(
    ("A1"  841.0 594.0 25.0 10.0 10.0 10.0 "PRANCHA")
    ("A2"  594.0 420.0 25.0 10.0 10.0 10.0 "PRANCHA")
    ("A3"  420.0 297.0 25.0 10.0 10.0 10.0 "PRANCHA")
    ("A4"  297.0 210.0 25.0 10.0 10.0 10.0 "PRANCHA_A4")
   )
)

(defun prancha-escalas-normativas ()
  '(500 750 1000 1250 1500 2000)
)

;; --------------------------------------------------------------------------
;; Motor Matemático de Enquadramento Ótimo
;; --------------------------------------------------------------------------
(defun prancha-calcular-melhor-opcao (dx dy esc-fixa fmt-fixo / 
                                      tbl-fmt escalas melhor-res menor-sobra
                                      dx-nec dy-nec)
  ;; Margem de segurança de 10%
  (setq dx-nec (* dx 1.10)
        dy-nec (* dy 1.10)
        tbl-fmt (prancha-get-tabela-formatos)
        escalas (if esc-fixa (list esc-fixa) (prancha-escalas-normativas))
        melhor-res nil
        menor-sobra 1.0e15)

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
          bname (nth 7 f)
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
          ;; Prioridade para escala padrão 1:1000 e folha A1
          (if (= esc 1000) (setq sobra (- sobra (* area-proj 0.15))))
          (if (= fname "A1") (setq sobra (- sobra (* area-proj 0.20))))

          (if (< sobra menor-sobra)
            (setq menor-sobra sobra
                  melhor-res (list fname esc fator lf-m af-m lu-m au-m mesq minf flarg falt bname))
          )
        )
      )
    )
  )

  ;; Fallback para A1 1:2000 se o projeto for muito extenso
  (if (null melhor-res)
    (setq melhor-res (list "A1" 2000 2.0 (* 841.0 2.0) (* 594.0 2.0) (* 806.0 2.0) (* 574.0 2.0) 25.0 10.0 841.0 594.0 "PRANCHA"))
  )
  melhor-res
)

;; --------------------------------------------------------------------------
;; Carregamento de Metadados Cadastrais da SOB
;; --------------------------------------------------------------------------
(defun prancha-carregar-contexto (/ dwg-dir cand cand-temp)
  (setq dwg-dir (getvar "DWGPREFIX"))
  (setq cand (strcat dwg-dir "prancha_contexto.lsp"))
  (setq cand-temp (strcat (getenv "TEMP") "\\prancha_contexto.lsp"))
  (cond
    ((findfile cand) (load cand))
    ((findfile cand-temp) (load cand-temp))
  )
)

(defun prancha-extrair-sob-dwg (/ base-dwg m-pos)
  (setq base-dwg (vl-filename-base (getvar "DWGNAME")))
  (setq m-pos (vl-string-search "_" base-dwg))
  (if m-pos
    (setq base-dwg (substr base-dwg (+ m-pos 2)))
  )
  (setq m-pos (vl-string-search "_" base-dwg))
  (if m-pos
    (setq base-dwg (substr base-dwg 1 m-pos))
  )
  (if (and base-dwg (/= base-dwg ""))
    base-dwg
    "-"
  )
)

;; --------------------------------------------------------------------------
;; Validação e Garantia da Definição dos Blocos Oficiais
;; --------------------------------------------------------------------------
(defun prancha-validar-compatibilidade-bloco (blk-name / blk-def ent edata etype txt pt
                                                         is-a4 has-folha has-escala has-data has-bairro
                                                         has-marcador-resp)
  (setq blk-def (tblsearch "block" blk-name))
  (if (null blk-def)
    'NAO_EXISTE
    (progn
      (setq is-a4 (= (strcase blk-name) "PRANCHA_A4"))
      (setq ent (cdr (assoc -2 blk-def)))
      (while ent
        (setq edata (entget ent)
              etype (cdr (assoc 0 edata)))
        (if (or (= etype "TEXT") (= etype "MTEXT"))
          (progn
            (setq txt (cdr (assoc 1 edata))
                  pt  (cdr (assoc 10 edata)))
            (if is-a4
              (progn
                ;; A4 Folha (261.11, 30.24)
                (if (and (vl-string-search "Folha" txt)
                         (<= (distance (list (car pt) (cadr pt)) '(261.11 30.24)) 4.0))
                  (setq has-folha T))
                ;; A4 Escala (261.09, 25.46)
                (if (and (vl-string-search "Escala" txt)
                         (<= (distance (list (car pt) (cadr pt)) '(261.09 25.46)) 4.0))
                  (setq has-escala T))
                ;; A4 DATA (210.42, 15.76)
                (if (and (vl-string-search "DATA" txt)
                         (<= (distance (list (car pt) (cadr pt)) '(210.42 15.76)) 4.0))
                  (setq has-data T))
                ;; A4 BAIRRO (179.22, 15.73)
                (if (and (vl-string-search "BAIRRO" txt)
                         (<= (distance (list (car pt) (cadr pt)) '(179.22 15.73)) 4.0))
                  (setq has-bairro T))
                ;; A4 Projetista Oficial IM3 (160.03, 10.55)
                (if (and (vl-string-search "JONATAS LAMPA" txt)
                         (<= (distance (list (car pt) (cadr pt)) '(160.03 10.55)) 4.0))
                  (setq has-marcador-resp T))
              )
              (progn
                ;; PRANCHA Folha (-35.89, 30.24)
                (if (and (vl-string-search "Folha" txt)
                         (<= (distance (list (car pt) (cadr pt)) '(-35.89 30.24)) 4.0))
                  (setq has-folha T))
                ;; PRANCHA Escala (-35.91, 25.46)
                (if (and (vl-string-search "Escala" txt)
                         (<= (distance (list (car pt) (cadr pt)) '(-35.91 25.46)) 4.0))
                  (setq has-escala T))
                ;; PRANCHA DATA (-86.58, 15.76)
                (if (and (vl-string-search "DATA" txt)
                         (<= (distance (list (car pt) (cadr pt)) '(-86.58 15.76)) 4.0))
                  (setq has-data T))
                ;; PRANCHA BAIRRO (-117.78, 15.73)
                (if (and (vl-string-search "BAIRRO" txt)
                         (<= (distance (list (car pt) (cadr pt)) '(-117.78 15.73)) 4.0))
                  (setq has-bairro T))
                ;; PRANCHA HBT Engenharia (-138.45, 24.87)
                (if (and (vl-string-search "HBT" txt)
                         (<= (distance (list (car pt) (cadr pt)) '(-138.45 24.87)) 4.0))
                  (setq has-marcador-resp T))
              )
            )
          )
        )
        (setq ent (entnext ent))
      )
      (if (and has-folha has-escala has-data has-bairro has-marcador-resp)
        'COMPATIVEL
        'INCOMPATIVEL
      )
    )
  )
)

(defun prancha-garantir-bloco (blk-name / status model-path temp-src e-before e-after post-status)
  (setq status (prancha-validar-compatibilidade-bloco blk-name))
  (cond
    ((eq status 'COMPATIVEL)
      (princ (strcat "\n[AUTOPRANCHA] Bloco oficial '" blk-name "' existente e compativel. Reutilizando definicao."))
      T
    )
    ((eq status 'INCOMPATIVEL)
      (princ (strcat "\n[ERRO CRITICO AUTOPRANCHA] O bloco '" blk-name "' ja existe no desenho, mas e INCOMPATIVEL com o modelo oficial IM3."))
      (princ "\n[ERRO CRITICO AUTOPRANCHA] Operacao abortada para proteger a integridade do desenho contra blocos legados.")
      nil
    )
    (T ;; 'NAO_EXISTE: Realizar importacao oficial do modelo
      (princ (strcat "\n[AUTOPRANCHA] Bloco oficial '" blk-name "' nao encontrado no desenho."))
      (princ "\n[AUTOPRANCHA] Importando definicao do modelo corporativo prancha.dwg...")
      
      (setq model-path "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\models\\prancha.dwg")
      (if (null (findfile model-path))
        (setq model-path (strcat (getvar "DWGPREFIX") "modelos\\prancha.dwg"))
      )
      
      (if (findfile model-path)
        (progn
          (setvar "CMDECHO" 0)
          (setvar "ATTREQ" 0)
          (setvar "ATTDIA" 0)
          (setq temp-src (strcat (getenv "TEMP") "\\temp_prancha_source.dwg"))
          (vl-file-copy model-path temp-src)
          (if (findfile temp-src)
            (progn
              (setq e-before (entlast))
              (command ".-insert" temp-src '(0.0 0.0 0.0) 1.0 1.0 0.0)
              (setq e-after (entlast))
              (if (and e-after (not (equal e-before e-after)))
                (entdel e-after)
              )
              (vl-file-delete temp-src)
            )
          )
          (setvar "CMDECHO" 1)
        )
        (princ (strcat "\n[ERRO AUTOPRANCHA] Arquivo modelo nao encontrado: " model-path))
      )
      
      (setq post-status (prancha-validar-compatibilidade-bloco blk-name))
      (if (eq post-status 'COMPATIVEL)
        (progn
          (princ (strcat "\n[AUTOPRANCHA] Bloco oficial '" blk-name "' importado e validado com sucesso."))
          T
        )
        (progn
          (princ (strcat "\n[ERRO AUTOPRANCHA] Falha ao validar bloco apos importacao: '" blk-name "'."))
          nil
        )
      )
    )
  )
)

;; --------------------------------------------------------------------------
;; Atualização Determinística dos Campos Cadastrais V1 no Bloco Oficial
;; --------------------------------------------------------------------------
(defun prancha-atualizar-campos-carimbo (blk-name sob esc folha data-str tit mun bai end-str /
                                         blk-def ent edata etype txt pt is-a4 x-base)
  (setq blk-def (tblsearch "block" blk-name))
  (if blk-def
    (progn
      (setq is-a4 (= (strcase blk-name) "PRANCHA_A4"))
      (setq x-base (if is-a4 297.0 0.0))
      (setq ent (cdr (assoc -2 blk-def)))

      (while ent
        (setq edata (entget ent)
              etype (cdr (assoc 0 edata)))

        (if (or (= etype "TEXT") (= etype "MTEXT"))
          (progn
            (setq txt (cdr (assoc 1 edata))
                  pt  (cdr (assoc 10 edata)))

            ;; 1. SOB: PRANCHA (-115.35, 7.44) / PRANCHA_A4 (179.39, 9.74)
            (if (or (and (not is-a4) (<= (distance pt (list (+ x-base -115.35) 7.44)) 2.0))
                    (and is-a4 (<= (distance pt '(179.39 9.74)) 2.0)))
              (progn
                (setq edata (subst (cons 1 sob) (assoc 1 edata) edata))
                (entmod edata)
              )
            )

            ;; 2. ESCALA: (-22.90, 25.57) / PRANCHA_A4 (274.10, 25.57)
            (if (and (or (= txt "1/1000") (= txt "X ") (= (substr txt 1 2) "1:"))
                     (<= (distance pt (list (+ x-base -22.90) 25.57)) 2.0))
              (progn
                (setq edata (subst (cons 1 (strcat "1:" (itoa esc))) (assoc 1 edata) edata))
                (entmod edata)
              )
            )

            ;; 3. FOLHA: (-23.41, 30.22) / PRANCHA_A4 (273.59, 30.22)
            (if (and (or (= txt "1 de 1") (= txt "X ") (= txt "1 / 1"))
                     (<= (distance pt (list (+ x-base -23.41) 30.22)) 2.0))
              (progn
                (setq edata (subst (cons 1 folha) (assoc 1 edata) edata))
                (entmod edata)
              )
            )

            ;; 4. DATA: (-79.21, 15.52)
            (if (and (not is-a4) (<= (distance pt (list (+ x-base -79.21) 15.52)) 2.0))
              (progn
                (setq edata (subst (cons 1 data-str) (assoc 1 edata) edata))
                (entmod edata)
              )
            )

            ;; 5. TÍTULO: (-115.49, 32.71) / PRANCHA_A4 (181.51, 32.71)
            (if (<= (distance pt (list (+ x-base -115.49) 32.71)) 2.0)
              (progn
                (setq edata (subst (cons 1 tit) (assoc 1 edata) edata))
                (entmod edata)
              )
            )

            ;; 6. MUNICÍPIO: (-104.46, 20.28) / PRANCHA_A4 (192.54, 20.28)
            (if (<= (distance pt (list (+ x-base -104.46) 20.28)) 2.0)
              (progn
                (setq edata (subst (cons 1 mun) (assoc 1 edata) edata))
                (entmod edata)
              )
            )

            ;; 7. BAIRRO: (-107.70, 15.69) / PRANCHA_A4 (189.30, 15.69)
            (if (<= (distance pt (list (+ x-base -107.70) 15.69)) 2.0)
              (progn
                (setq edata (subst (cons 1 bai) (assoc 1 edata) edata))
                (entmod edata)
              )
            )

            ;; 8. ENDEREÇO: (-115.38, 25.52) / PRANCHA_A4 (181.62, 25.52)
            (if (<= (distance pt (list (+ x-base -115.38) 25.52)) 2.0)
              (progn
                (setq edata (subst (cons 1 end-str) (assoc 1 edata) edata))
                (entmod edata)
              )
            )
          )
        )
        (setq ent (entnext ent))
      )
    )
  )
)

;; --------------------------------------------------------------------------
;; Comando Principal: AUTOPRANCHA
;; --------------------------------------------------------------------------
(defun c:AUTOPRANCHA (/ pt1 pt2 xmin xmax ymin ymax dx dy cx cy
                        modo esc-fixa fmt-fixo res fname esc fator
                        lf-m af-m lu-m au-m mesq minf flarg falt bname
                        f-xmin f-ymin f-xmax f-ymax x-ins y-ins
                        data-str conf sob tit mun bai end-str folha ins-ref)
  (setvar "CMDECHO" 0)
  (princ "\n=======================================================")
  (princ "\n [AUTOPRANCHA V1] Enquadramento Inteligente de Prancha ")
  (princ "\n Inserção dos Blocos Oficiais IM3 Brasil no ModelSpace ")
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
     (initget "A1 A2 A3 A4")
     (setq fmt-fixo (getkword "\nInforme o formato desejado [A1 / A2 / A3 / A4] <A1>: "))
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
        falt  (nth 10 res)
        bname (nth 11 res))

  ;; 5. Apresentação do Resumo ao Usuário
  (princ "\n-------------------------------------------------------")
  (princ "\n ENQUADRAMENTO CALCULADO (IM3 BRASIL):")
  (princ (strcat "\n - Área selecionada       : " (rtos dx 2 1) "m x " (rtos dy 2 1) "m"))
  (princ (strcat "\n - Formato de papel       : " fname " (" (rtos flarg 2 0) " x " (rtos falt 2 0) " mm)"))
  (princ (strcat "\n - Escala de projeto      : 1:" (itoa esc)))
  (princ (strcat "\n - Bloco oficial aplicado : " bname))
  (princ (strcat "\n - Dimensão da folha      : " (rtos lf-m 2 1) "m x " (rtos af-m 2 1) "m"))
  (princ (strcat "\n - Área útil de desenho   : " (rtos lu-m 2 1) "m x " (rtos au-m 2 1) "m"))
  (princ "\n-------------------------------------------------------")

  (initget "Sim Nao")
  (setq conf (getkword "\nConfirmar inserção do bloco oficial no ModelSpace? [Sim / Não] <Sim>: "))
  (if (or (null conf) (= conf "Sim"))
    (progn
      ;; 6. Garantir bloco oficial no desenho
      (if (null (prancha-garantir-bloco bname))
        (progn
          (princ (strcat "\n[ERRO CRÍTICO] Bloco oficial " bname " não está disponível no desenho e não pôde ser importado."))
          (exit)
        )
      )

      ;; 7. Carregar dados cadastrais da SOB do contexto do Workspace
      (setq *prancha-sob* nil *prancha-titulo* nil *prancha-municipio* nil
            *prancha-bairro* nil *prancha-endereco* nil *prancha-folha* nil
            *prancha-data* nil)
      (prancha-carregar-contexto)

      (setq sob (if *prancha-sob* *prancha-sob* (prancha-extrair-sob-dwg)))
      (setq tit (if (and *prancha-titulo* (/= *prancha-titulo* "")) *prancha-titulo* "-"))
      (setq mun (if *prancha-municipio* *prancha-municipio* "-"))
      (setq bai (if *prancha-bairro* *prancha-bairro* "-"))
      (setq end-str (if *prancha-endereco* *prancha-endereco* "-"))
      (setq folha (if *prancha-folha* *prancha-folha* "1 de 1"))
      (setq data-str (menucmd "M=$(edtime,$(getvar,date),DD/MO/YYYY)"))
      (if (and *prancha-data* (/= *prancha-data* "")) (setq data-str *prancha-data*))

      ;; 8. Calcular coordenadas exatas no ModelSpace
      (setq f-xmin (- cx (* (+ mesq (/ (- flarg (+ mesq 10.0)) 2.0)) fator))
            f-ymin (- cy (* (+ minf (/ (- falt  (+ minf 10.0)) 2.0)) fator))
            f-xmax (+ f-xmin lf-m)
            f-ymax (+ f-ymin af-m))

      ;; 9. Determinar ponto de inserção oficial conforme a ancoragem do bloco:
      ;; PRANCHA (A1/A2/A3): Canto inferior direito (f-xmax, f-ymin)
      ;; PRANCHA_A4 (A4): Canto inferior esquerdo (f-xmin, f-ymin)
      (if (= (strcase bname) "PRANCHA")
        (setq x-ins f-xmax y-ins f-ymin)
        (setq x-ins f-xmin y-ins f-ymin)
      )

      ;; 10. Atualizar campos do carimbo determinísticamente
      (prancha-atualizar-campos-carimbo bname sob esc folha data-str tit mun bai end-str)

      ;; 11. Inserir bloco oficial no ModelSpace
      (setvar "ATTREQ" 0)
      (setvar "ATTDIA" 0)
      (command ".-insert" bname (list x-ins y-ins 0.0) fator fator 0.0)
      (setq ins-ref (entlast))

      ;; 12. Zoom na folha inserida
      (command "_.zoom" "_w" "_none" (list f-xmin f-ymin) "_none" (list f-xmax f-ymax))

      (princ (strcat "\n[AUTOPRANCHA] Sucesso! Bloco " bname " (1:" (itoa esc) ") inserido no ModelSpace."))
      (princ (strcat "\n[AUTOPRANCHA] SOB " sob " | Folha " folha " | Escala 1:" (itoa esc) " | Data " data-str))
    )
    (princ "\n[AUTOPRANCHA] Operação cancelada pelo usuário.")
  )
  (setvar "CMDECHO" 1)
  (princ)
)

;; --------------------------------------------------------------------------
;; Atalhos e Comandos Auxiliares
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
