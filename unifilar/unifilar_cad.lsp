;;; =============================================================================
;;; unifilar_cad.lsp - Geração do Diagrama Unifilar e Consulta de Proteção
;;; Integração com a Árvore de Dispositivos (Módulo Unifilar / AUX CAD)
;;; =============================================================================

(vl-load-com)

;; Função auxiliar para compatibilidade de checagem de tipo string
(defun stringp (x) (= (type x) 'STR))

(defun unifilar-get-module-path (/ f-lsp dir)
  (setq f-lsp (findfile "unifilar_cad.lsp"))
  (if f-lsp
    (setq dir (vl-filename-directory f-lsp))
    (setq dir (strcat *aux-cad-root* "unifilar"))
  )
  (if (not (vl-string-search "\\" (substr dir (strlen dir) 1)))
    (strcat dir "\\")
    dir
  )
)

;; Lê arquivo JSON e extrai campo simples por regex
(defun unifilar-json-get (json-str key / pos-k pos-v str-resto val)
  (setq pos-k (vl-string-search (strcat "\"" key "\"") json-str))
  (if pos-k
    (progn
      (setq str-resto (substr json-str (+ pos-k (strlen key) 3)))
      (setq pos-v (vl-string-search ":" str-resto))
      (if pos-v
        (progn
          (setq str-resto (vl-string-left-trim " \t\r\n" (substr str-resto (+ pos-v 2))))
          (cond
            ;; String entre aspas
            ((= (substr str-resto 1 1) "\"")
             (setq str-resto (substr str-resto 2))
             (setq pos-f (vl-string-search "\"" str-resto))
             (if pos-f (substr str-resto 1 pos-f) "")
            )
            ;; Número ou booleano até vírgula ou fecha-chave
            (t
             (setq pos-f (vl-string-search "," str-resto))
             (if (not pos-f) (setq pos-f (vl-string-search "}" str-resto)))
             (if pos-f (vl-string-trim " \t\r\n" (substr str-resto 1 pos-f)) "")
            )
          )
        )
      )
    )
  )
)

;; Cria layer caso não exista
(defun unifilar-ensure-layer (lay-name col / lays lay-obj)
  (setq lays (vla-get-Layers (vla-get-ActiveDocument (vlax-get-acad-object))))
  (if (vl-catch-all-error-p (vl-catch-all-apply 'vla-Item (list lays lay-name)))
    (progn
      (setq lay-obj (vla-Add lays lay-name))
      (if col (vla-put-Color lay-obj col))
    )
  )
)

;; Insere texto simples no ModelSpace via entmake
(defun unifilar-draw-text (pt txt h layer col justify / align-code)
  (if (not justify) (setq justify "LEFT"))
  (setq align-code (if (= justify "RIGHT") 2 (if (= justify "CENTER") 1 0)))
  (entmake
    (list
      '(0 . "TEXT")
      (cons 10 pt)
      (cons 40 h)
      (cons 1 txt)
      (cons 8 layer)
      (cons 62 (if col col 256))
      (cons 72 align-code)
      (cons 11 pt)
    )
  )
)

;; Insere linha simples no ModelSpace via entmake
(defun unifilar-draw-line (pt1 pt2 layer col)
  (entmake
    (list
      '(0 . "LINE")
      (cons 10 pt1)
      (cons 11 pt2)
      (cons 8 layer)
      (cons 62 (if col col 256))
    )
  )
)

;; Insere círculo simples no ModelSpace via entmake
(defun unifilar-draw-circle (pt r layer col)
  (entmake
    (list
      '(0 . "CIRCLE")
      (cons 10 pt)
      (cons 40 r)
      (cons 8 layer)
      (cons 62 (if col col 256))
    )
  )
)

;; =============================================================================
;; CONFIGURAÇÃO E GERENCIAMENTO DO BLOCO DO TRANSFORMADOR (TRAFO1)
;; =============================================================================
(if (not *UNIFILAR-BLOCO-TRAFO*)
  (setq *UNIFILAR-BLOCO-TRAFO* "TRAFO1")
)

;; Lista todos os blocos do desenho que correspondem a transformadores
(defun unifilar-listar-blocos-trafo (/ blk bname lista)
  (setq lista nil)
  (setq blk (tblnext "block" T))
  (while blk
    (setq bname (cdr (assoc 2 blk)))
    (if (and (/= (substr bname 1 1) "*")
             (or (wcmatch (strcase bname) "*TRAFO*")
                 (wcmatch (strcase bname) "*TRANSF*")
                 (= (strcase bname) "T")
                 (wcmatch (strcase bname) "T *")
                 (wcmatch (strcase bname) "TR*")))
      (setq lista (cons bname lista))
    )
    (setq blk (tblnext "block"))
  )
  (acad_strlsort lista)
)

;; Pede ao usuário o bloco do transformador com suporte a lista e seleção no CAD
(defun unifilar-obter-bloco-trafo (/ def-blk blks input sel ent ed bname num-in idx)
  (setq def-blk *UNIFILAR-BLOCO-TRAFO*)
  ;; Se TRAFO1 existir na tabela e o atual não, prioriza TRAFO1
  (if (and (null (tblsearch "BLOCK" def-blk)) (tblsearch "BLOCK" "TRAFO1"))
    (setq def-blk "TRAFO1")
  )
  ;; Fallbacks secundários se não existirem
  (if (and (null (tblsearch "BLOCK" def-blk)) (tblsearch "BLOCK" "TRAFO"))
    (setq def-blk "TRAFO")
  )

  (princ (strcat "\n[UNIFILAR] Bloco do Transformador sugerido: <" def-blk ">"))
  (setq input (getstring (strcat "\nInforme o bloco [ENTER=" def-blk " | (L)istar | (S)elecionar no CAD]: ")))
  (setq input (vl-string-trim " \t\r\n" input))

  (cond
    ;; Pressionou ENTER
    ((or (null input) (= input ""))
     (setq *UNIFILAR-BLOCO-TRAFO* def-blk)
    )

    ;; Opção LISTAR [L] ou [?]
    ((or (= (strcase input) "L") (= input "?") (= (strcase input) "LISTAR"))
     (setq blks (unifilar-listar-blocos-trafo))
     (if blks
       (progn
         (princ "\n--- BLOCOS DE TRANSFORMADOR DISPONÍVEIS NO DWG ---")
         (setq idx 1)
         (foreach b blks
           (princ (strcat "\n [" (itoa idx) "] " b (if (= b def-blk) " (atual)" "")))
           (setq idx (1+ idx))
         )
         (princ "\n---------------------------------------------------")
         (setq num-in (getint (strcat "\nSelecione o número do bloco [1-" (itoa (length blks)) "] ou 0 para cancelar: ")))
         (if (and num-in (> num-in 0) (<= num-in (length blks)))
           (setq *UNIFILAR-BLOCO-TRAFO* (nth (1- num-in) blks))
           (setq *UNIFILAR-BLOCO-TRAFO* def-blk)
         )
       )
       (progn
         (princ "\n[AVISO] Nenhum bloco com padrão TRAFO/TRANSF/T encontrado na tabela de blocos.")
         (setq *UNIFILAR-BLOCO-TRAFO* def-blk)
       )
     )
    )

    ;; Opção SELECIONAR [S] no desenho
    ((or (= (strcase input) "S") (= (strcase input) "SELECIONAR"))
     (setq sel (entsel "\nClique no bloco de transformador no desenho: "))
     (if sel
       (progn
         (setq ent (car sel)
               ed  (entget ent))
         (if (= (cdr (assoc 0 ed)) "INSERT")
           (progn
             (setq bname (cdr (assoc 2 ed)))
             (princ (strcat "\n[UNIFILAR] Bloco capturado do desenho: " bname))
             (setq *UNIFILAR-BLOCO-TRAFO* bname)
           )
           (progn
             (princ "\n[AVISO] A entidade clicada não é um bloco (INSERT). Mantendo padrão.")
             (setq *UNIFILAR-BLOCO-TRAFO* def-blk)
           )
         )
       )
       (setq *UNIFILAR-BLOCO-TRAFO* def-blk)
     )
    )

    ;; Digitou um nome explicitamente
    (t
     (setq *UNIFILAR-BLOCO-TRAFO* input)
    )
  )
  (princ (strcat "\n[UNIFILAR] Bloco do Transformador definido: '" *UNIFILAR-BLOCO-TRAFO* "'"))
  *UNIFILAR-BLOCO-TRAFO*
)

;; Insere bloco oficial ('chaves_', 'REL.', 'TRAFO1'...) ou gera fallback vetorial 2.5D caso não exista
(defun unifilar-insert-block (pt blk-name rot scale layer col fallback-type / x y h c1 c2 eff-blk)
  (setq x (car pt))
  (setq y (cadr pt))
  ;; Resolve o nome do bloco com suporte a REL. e REL
  (setq eff-blk blk-name)
  (cond
    ((tblsearch "BLOCK" blk-name) (setq eff-blk blk-name))
    ((and (= blk-name "REL.") (tblsearch "BLOCK" "REL")) (setq eff-blk "REL"))
    ((and (= blk-name "REL") (tblsearch "BLOCK" "REL.")) (setq eff-blk "REL."))
    ((and (or (= blk-name "TRAFO") (= blk-name "T")) (tblsearch "BLOCK" "TRAFO1")) (setq eff-blk "TRAFO1"))
  )
  (if (tblsearch "BLOCK" eff-blk)
    (entmake
      (list
        '(0 . "INSERT")
        (cons 2 eff-blk)
        (cons 10 pt)
        (cons 41 scale)
        (cons 42 scale)
        (cons 43 scale)
        (cons 50 rot)
        (cons 8 layer)
      )
    )
    ;; Fallback vetorial 2.5D normativo
    (cond
      ((= fallback-type "REL")
       ;; Símbolo de Religador: Quadrado técnico com letra 'R'
       (setq h (* scale 1.2))
       (unifilar-draw-line (list (- x h) (- y h) 0.0) (list (+ x h) (- y h) 0.0) layer col)
       (unifilar-draw-line (list (+ x h) (- y h) 0.0) (list (+ x h) (+ y h) 0.0) layer col)
       (unifilar-draw-line (list (+ x h) (+ y h) 0.0) (list (- x h) (+ y h) 0.0) layer col)
       (unifilar-draw-line (list (- x h) (+ y h) 0.0) (list (- x h) (- y h) 0.0) layer col)
       (unifilar-draw-text (list x (- y (* h 0.4)) 0.0) "R" (* h 1.2) layer col "CENTER")
      )
      ((or (= fallback-type "TRAFO") (= fallback-type "TRAFO1") (= fallback-type "T"))
       ;; Símbolo normativo de Transformador: Dois círculos tangentes verticais
       (setq r (* scale 0.65))
       (unifilar-draw-circle (list x (+ y (* r 0.8)) 0.0) r layer col)
       (unifilar-draw-circle (list x (- y (* r 0.8)) 0.0) r layer col)
       (unifilar-draw-text (list (+ x (* r 1.4)) (- y (* r 0.4)) 0.0) "T" (* scale 1.1) layer col "LEFT")
      )
      ((= fallback-type "PONTO")
       ;; Símbolo de Ponto: Círculo de nó
       (unifilar-draw-circle pt (* scale 1.0) layer col)
      )
      (t
       ;; Símbolo de Chave Fusível: Barras paralelas verticais e elo diagonal
       (setq h (* scale 0.9))
       (unifilar-draw-line (list (- x (* h 0.8)) (+ y h) 0.0) (list (- x (* h 0.8)) (- y h) 0.0) layer col)
       (unifilar-draw-line (list (+ x (* h 0.8)) (+ y h) 0.0) (list (+ x (* h 0.8)) (- y h) 0.0) layer col)
       (unifilar-draw-line (list (- x (* h 0.8)) (+ y h) 0.0) (list (+ x (* h 0.8)) (- y h) 0.0) layer 1)
      )
    )
  )
)

;; Desenha o Diagrama Unifilar com esquema gráfico sem escala
(defun unifilar-draw-esquema-grafico (pt-ins se alim prot-rot prot-tipo ponto-alvo cli-a cli-b kva bloco-nome bloco-trafo h-txt / x y sp x-al y-cur x-diag x-se-ini x-se-fim x-tr y-se y-ch y-pt fb-tipo)
  (unifilar-ensure-layer "UNIFILAR" 3)
  (unifilar-ensure-layer "UNIFILAR_SE" 3)
  (unifilar-ensure-layer "UNIFILAR_LINHA" 7)
  (unifilar-ensure-layer "UNIFILAR_PROTECAO" 1)
  (unifilar-ensure-layer "UNIFILAR_PONTO" 2)

  (if (or (null bloco-trafo) (= bloco-trafo "")) (setq bloco-trafo "TRAFO1"))
  (setq x (car pt-ins))
  (setq y (cadr pt-ins))
  (setq sp (* h-txt 1.6))

  ;; 1. TÍTULO E TEXTOS TÉCNICOS À ESQUERDA
  (unifilar-draw-text (list x y 0.0) "DIAGRAMA  UNIFILAR" (* h-txt 1.2) "UNIFILAR" 3 "LEFT")
  (unifilar-draw-line (list x (- y (* h-txt 0.3)) 0.0) (list (+ x (* h-txt 14.0)) (- y (* h-txt 0.3)) 0.0) "UNIFILAR" 3)

  (setq x-al (+ x (* h-txt 14.0)))
  (setq y-cur (- y (* sp 1.5)))

  (unifilar-draw-text (list x-al y-cur 0.0) (strcat "SE.: " se) h-txt "UNIFILAR" 7 "RIGHT")
  (setq y-cur (- y-cur sp))
  (unifilar-draw-text (list x-al y-cur 0.0) (strcat "ALIM.: " alim) h-txt "UNIFILAR" 7 "RIGHT")
  (setq y-cur (- y-cur sp))
  (unifilar-draw-text (list x-al y-cur 0.0) "FONTE DE ALIMENTAÇÃO" h-txt "UNIFILAR" 7 "RIGHT")
  (setq y-cur (- y-cur sp))
  (unifilar-draw-text (list x-al y-cur 0.0) (strcat "DISPOSITIVO DE PROTEÇÃO: " prot-rot) h-txt "UNIFILAR" 7 "RIGHT")
  (setq y-cur (- y-cur sp))
  (unifilar-draw-text (list x-al y-cur 0.0) (strcat "Clientes Grupo A: " cli-a " Clientes Grupo B: " cli-b " - KVA: " kva) h-txt "UNIFILAR" 7 "RIGHT")

  ;; 2. ESQUEMA UNIFILAR SEM ESCALA À DIREITA
  (setq x-diag (+ x (* h-txt 18.0)))
  (setq x-se-ini x-diag)
  (setq x-se-fim (+ x-diag (* h-txt 14.0)))
  (setq x-tr (+ x-diag (* h-txt 7.0)))
  (setq y-se (- y (* h-txt 1.2)))

  ;; 2.1 Barramento da Subestação
  (unifilar-draw-line (list x-se-ini y-se 0.0) (list x-se-fim y-se 0.0) "UNIFILAR_SE" 3)
  (unifilar-draw-line (list x-se-ini (- y-se (* h-txt 0.2)) 0.0) (list x-se-fim (- y-se (* h-txt 0.2)) 0.0) "UNIFILAR_SE" 3)
  (unifilar-draw-text (list x-tr (+ y-se (* h-txt 0.8)) 0.0) (strcat "SE " se " - ALIM " alim) (* h-txt 0.8) "UNIFILAR_SE" 3 "CENTER")

  ;; 2.2 Tronco MT
  (setq y-ch (- y-se (* h-txt 6.5)))
  (unifilar-draw-line (list x-tr (- y-se (* h-txt 0.2)) 0.0) (list x-tr (+ y-ch (* h-txt 1.5)) 0.0) "UNIFILAR_LINHA" 7)
  (unifilar-draw-text (list (+ x-tr (* h-txt 0.6)) (- y-se (* h-txt 3.2)) 0.0) "TRONCO MT" (* h-txt 0.7) "UNIFILAR_LINHA" 8 "LEFT")

  ;; 2.3 Bloco da Proteção (chaves_ ou REL.)
  (setq fb-tipo (if (or (= bloco-nome "REL.") (= bloco-nome "REL")) "REL" "CHAVE"))
  (unifilar-insert-block (list x-tr y-ch 0.0) bloco-nome 0.0 1.0 "UNIFILAR_PROTECAO" 1 fb-tipo)
  (unifilar-draw-text (list (+ x-tr (* h-txt 2.2)) y-ch 0.0) prot-rot (* h-txt 0.9) "UNIFILAR_PROTECAO" 1 "LEFT")

  ;; 2.4 Ramal MT
  (setq y-pt (- y-ch (* h-txt 6.5)))
  (unifilar-draw-line (list x-tr (- y-ch (* h-txt 1.5)) 0.0) (list x-tr (+ y-pt (* h-txt 1.2)) 0.0) "UNIFILAR_LINHA" 7)
  (unifilar-draw-text (list (+ x-tr (* h-txt 0.6)) (- y-ch (* h-txt 3.2)) 0.0) "RAMAL MT" (* h-txt 0.7) "UNIFILAR_LINHA" 8 "LEFT")

  ;; 2.5 Ponto do Projeto / Transformador (TRAFO1)
  (unifilar-insert-block (list x-tr y-pt 0.0) bloco-trafo 0.0 1.0 "UNIFILAR_PONTO" 2 "TRAFO")
  (unifilar-draw-text (list (+ x-tr (* h-txt 2.2)) y-pt 0.0) (strcat ponto-alvo " (" kva " kVA)") (* h-txt 0.9) "UNIFILAR_PONTO" 2 "LEFT")
  (princ (strcat "\n[UNIFILAR] Diagrama Unifilar gerado com bloco de transformador '" bloco-trafo "'!"))
)

;; Traça ramal geográfico do dispositivo KMZ até o ponto do projeto
(defun unifilar-draw-ramal-geografico (ponto-alvo x-prot y-prot rotulo bloco-nome bloco-trafo / pt-dest dist-m fb-tipo mid-x mid-y)
  (unifilar-ensure-layer "MT_ALIMENTADOR" 6)
  (unifilar-ensure-layer "UNIFILAR_PROTECAO" 1)
  (unifilar-ensure-layer "UNIFILAR_PONTO" 2)

  (if (or (null bloco-trafo) (= bloco-trafo "")) (setq bloco-trafo "TRAFO1"))
  (princ (strcat "\n[KMZ] Dispositivo " rotulo " localizado em UTM: X=" (rtos x-prot 2 2) ", Y=" (rtos y-prot 2 2)))
  (setq pt-dest (getpoint "\nClique no poste ou ponto de destino do projeto no desenho: "))
  (if pt-dest
    (progn
      ;; 1. Insere o bloco da proteção na coordenada real
      (setq fb-tipo (if (or (= bloco-nome "REL.") (= bloco-nome "REL")) "REL" "CHAVE"))
      (unifilar-insert-block (list x-prot y-prot 0.0) bloco-nome 0.0 1.0 "UNIFILAR_PROTECAO" 1 fb-tipo)
      (unifilar-draw-text (list (+ x-prot 2.0) (+ y-prot 1.5) 0.0) rotulo 2.5 "UNIFILAR_PROTECAO" 1 "LEFT")

      ;; 2. Traça a linha do ramal conectando a chave ao ponto
      (unifilar-draw-line (list x-prot y-prot 0.0) pt-dest "MT_ALIMENTADOR" 6)

      ;; 3. Insere o bloco do transformador no ponto de destino se houver
      (unifilar-insert-block pt-dest bloco-trafo 0.0 1.0 "UNIFILAR_PONTO" 2 "TRAFO")

      ;; 4. Mede a distância real
      (setq dist-m (distance (list x-prot y-prot 0.0) pt-dest))

      ;; 5. Texto no ponto médio da linha
      (setq mid-x (/ (+ x-prot (car pt-dest)) 2.0))
      (setq mid-y (/ (+ y-prot (cadr pt-dest)) 2.0))
      (unifilar-draw-text (list mid-x (+ mid-y 1.0) 0.0) (strcat "RAMAL MT " (rtos dist-m 2 1) "m") 2.0 "MT_ALIMENTADOR" 6 "CENTER")

      (princ (strcat "\n[UNIFILAR] Ramal MT traçado do dispositivo " rotulo " até " ponto-alvo " (Extensão: " (rtos dist-m 2 1) "m, Bloco: " bloco-trafo ")."))
    )
    (princ "\n[UNIFILAR] Traçado cancelado.")
  )
)

;; Extrai texto de entidade selecionada (TEXT, MTEXT ou INSERT com atributos)
(defun unifilar-extract-text-from-ent (ent / ed t-val)
  (setq ed (entget ent))
  (cond
    ((= (cdr (assoc 0 ed)) "TEXT")
     (cdr (assoc 1 ed))
    )
    ((= (cdr (assoc 0 ed)) "MTEXT")
     (cdr (assoc 1 ed))
    )
    ((= (cdr (assoc 0 ed)) "INSERT")
     ;; Tenta ler o primeiro atributo se houver
     (setq sub (entnext ent))
     (setq res "")
     (while (and sub (/= (cdr (assoc 0 (entget sub))) "SEQEND"))
       (if (= (cdr (assoc 0 (entget sub))) "ATTRIB")
         (setq res (strcat res " " (cdr (assoc 1 (entget sub)))))
       )
       (setq sub (entnext sub))
     )
     (vl-string-trim " " res)
    )
    (t "")
  )
)

;; Atualiza o conteúdo textual de uma entidade existente (TEXT ou MTEXT)
(defun unifilar-update-ent-text (ent new-text / ed)
  (setq ed (entget ent))
  (if (member (cdr (assoc 0 ed)) '("TEXT" "MTEXT"))
    (progn
      (setq ed (subst (cons 1 new-text) (assoc 1 ed) ed))
      (entmod ed)
      (entupd ent)
      t
    )
    nil
  )
)

;; =============================================================================
;; COMANDO PRINCIPAL: UNIFILAR
;; =============================================================================
(defun c:UNIFILAR (/ *error* mod-dir py-script tmp-json tmp-log ponto sel ent t-ext cmd
                     wsh t0 fp fp-log l-err msg-err json-content sucesso se alim prot-rot
                     cli-a cli-b kva pt-ins h-txt opc ss i ent-i txt-i cnt-upd x y sp x-al y-cur
                     bloco-prot prot-tipo utm-x-str utm-y-str utm-x utm-y aj novo-cli-a novo-cli-b novo-kva)

  (defun *error* (msg)
    (if (and msg (not (member msg '("Function cancelled" "quit / exit abort"))))
      (princ (strcat "\n[UNIFILAR] Erro ou cancelamento: " msg))
    )
    (princ)
  )

  (princ "\n==============================================================")
  (princ "\n   AUX CAD - CONSULTA ÁRVORE E DIAGRAMA UNIFILAR (PROTEÇÃO)")
  (princ "\n==============================================================")

  (setq mod-dir (unifilar-get-module-path))
  (setq py-script (strcat mod-dir "unifilar_manager.py"))

  (if (not (findfile py-script))
    (progn
      (alert (strcat "Script não encontrado:\n" py-script))
      (exit)
    )
  )

  ;; Solicita Ponto Elétrico ou linha de Resumo da Árvore
  (princ "\nInforme o Ponto Elétrico (ex: N760355), [S]elecionar no DWG")
  (setq ponto-in (getstring T "\nou cole o Resumo da Árvore SGT <N760355>: "))
  (if (or (= ponto-in "") (= ponto-in nil))
    (setq ponto-in "N760355")
  )
  (setq ponto-in (vl-string-trim " \t\r\n" ponto-in))

  ;; Verifica se foi colada uma linha de resumo do SGT/GOMNET
  (setq is-resumo nil)
  (if (or (vl-string-search "Clientes Grupo" ponto-in)
          (vl-string-search "clientes grupo" (strcase ponto-in))
          (vl-string-search "Saida do Alimentador" ponto-in)
          (vl-string-search ">" ponto-in))
    (setq is-resumo T)
  )

  (setq ponto ponto-in)
  (if (and (not is-resumo) (or (= (strcase ponto-in) "S") (= (strcase ponto-in) "SELECIONAR")))
    (progn
      (setq sel (entsel "\nSelecione o texto ou bloco do Ponto Elétrico no desenho: "))
      (if sel
        (progn
          (setq t-ext (unifilar-extract-text-from-ent (car sel)))
          (if (and t-ext (/= t-ext ""))
            (progn
              (setq ponto (vl-string-trim " \t\r\n" t-ext))
              (princ (strcat "\n[UNIFILAR] Texto selecionado: " ponto))
            )
            (progn
              (princ "\n[UNIFILAR] Nenhum texto extraído. Usando N760355.")
              (setq ponto "N760355")
            )
          )
        )
        (setq ponto "N760355")
      )
    )
  )

  ;; Prepara arquivo temporário de intercâmbio JSON e log de diagnóstico
  (setq tmp-json (vl-filename-mktemp "unifilar_" nil ".json"))
  (setq tmp-log (vl-filename-mktemp "unifilar_log_" nil ".txt"))

  (if is-resumo
    (progn
      ;; Escapa aspas duplas caso existam
      (setq ponto-clean (vl-string-subst "" "\"" ponto-in))
      (setq cmd (strcat "python \"" py-script "\" --resumo \"" ponto-clean "\" --ponto \"N760355\" --out \"" tmp-json "\" > \"" tmp-log "\" 2>&1"))
      (princ "\n[UNIFILAR] Processando resumo colado da Árvore SGT...")
    )
    (progn
      (setq cmd (strcat "python \"" py-script "\" --ponto \"" ponto "\" --out \"" tmp-json "\" > \"" tmp-log "\" 2>&1"))
      (princ (strcat "\n[UNIFILAR] Consultando proteção a montante para '" ponto "'..."))
    )
  )

  ;; Execução síncrona protegida via WScript.Shell (sem piscar tela preta e sem vl-sleep)
  (setq wsh (vl-catch-all-apply 'vlax-create-object (list "WScript.Shell")))
  (if (and wsh (not (vl-catch-all-error-p wsh)))
    (progn
      (vl-catch-all-apply 'vlax-invoke-method (list wsh "Run" (strcat "cmd.exe /c " cmd) 0 :vlax-true))
      (vlax-release-object wsh)
    )
    (progn
      (startapp "cmd.exe" (strcat "/c " cmd))
      (setq t0 (getvar "MILLISECS"))
      (while (and (not (findfile tmp-json)) (< (- (getvar "MILLISECS") t0) 6000))
      )
    )
  )

  (if (not (findfile tmp-json))
    (progn
      (setq msg-err "")
      (if (findfile tmp-log)
        (progn
          (setq fp-log (open tmp-log "r"))
          (while (setq l-err (read-line fp-log))
            (setq msg-err (strcat msg-err l-err "\n"))
          )
          (close fp-log)
        )
      )
      (alert (strcat "Não foi possível consultar o ponto " ponto ":\n" (if (/= msg-err "") msg-err "Tempo limite excedido ou Python inacessível.")))
      (exit)
    )
  )

  ;; Lê o arquivo JSON gerado
  (setq fp (open tmp-json "r"))
  (setq json-content "")
  (if fp
    (progn
      (while (setq linha (read-line fp))
        (setq json-content (strcat json-content linha "\n"))
      )
      (close fp)
    )
  )

  (setq sucesso (unifilar-json-get json-content "sucesso"))
  (if (or (not sucesso) (= sucesso "false"))
    (progn
      (setq msg-err (unifilar-json-get json-content "mensagem"))
      (alert (strcat "Não foi possível localizar proteção para o ponto " ponto ":\n" (if msg-err msg-err "Erro desconhecido.")))
      (exit)
    )
  )

  ;; Extrai os dados do JSON
  (setq se (unifilar-json-get json-content "subestacao"))
  (setq alim (unifilar-json-get json-content "alimentador"))
  (setq prot-rot (unifilar-json-get json-content "protecao_rotulo"))
  (setq cli-a (unifilar-json-get json-content "clientes_a"))
  (setq cli-b (unifilar-json-get json-content "clientes_b"))
  (setq kva (unifilar-json-get json-content "kva"))
  (setq bloco-prot (unifilar-json-get json-content "bloco_protecao"))
  (setq prot-tipo (unifilar-json-get json-content "protecao_tipo"))
  (setq utm-x-str (unifilar-json-get json-content "utm_x"))
  (setq utm-y-str (unifilar-json-get json-content "utm_y"))

  (if (not se) (setq se "---"))
  (if (not alim) (setq alim "--"))
  (if (not prot-rot) (setq prot-rot "Proteção"))
  (if (not cli-a) (setq cli-a "0"))
  (if (not cli-b) (setq cli-b "0"))
  (if (not kva) (setq kva "0"))
  (if (or (not bloco-prot) (= bloco-prot "")) (setq bloco-prot "chaves_"))
  (if (not prot-tipo) (setq prot-tipo "CHAVE_FUSIVEL"))
  (setq utm-x (if (and utm-x-str (/= utm-x-str "") (/= utm-x-str "null")) (atof utm-x-str) nil))
  (setq utm-y (if (and utm-y-str (/= utm-y-str "") (/= utm-y-str "null")) (atof utm-y-str) nil))

  (princ "\n--------------------------------------------------------------")
  (princ (strcat "\n[UNIFILAR] PROTEÇÃO LOCALIZADA:"))
  (princ (strcat "\n • Subestação (SE): " se))
  (princ (strcat "\n • Alimentador:     " alim))
  (princ (strcat "\n • Proteção:        " prot-rot " [Bloco: " bloco-prot "]"))
  (princ (strcat "\n • Cargas/Potência: Clientes Grupo A: " cli-a " Clientes Grupo B: " cli-b " - KVA: " kva))
  (if (and utm-x utm-y)
    (princ (strcat "\n • Coordenadas KMZ: UTM X=" (rtos utm-x 2 2) ", Y=" (rtos utm-y 2 2)))
    (princ "\n • Coordenadas KMZ: Não localizado nos KMZs de dispositivos.")
  )
  (princ "\n--------------------------------------------------------------")

  ;; Pergunta se deseja ajustar Clientes / KVA antes de desenhar
  (initget "Sim Nao S N")
  (setq aj (getkword "\nDeseja alterar Clientes Grupo A / B ou KVA? [S/N] <N>: "))
  (if (or (= aj "S") (= aj "Sim"))
    (progn
      (setq novo-cli-a (getstring (strcat "\nClientes Grupo A <" cli-a ">: ")))
      (if (and novo-cli-a (/= novo-cli-a "")) (setq cli-a novo-cli-a))
      (setq novo-cli-b (getstring (strcat "\nClientes Grupo B <" cli-b ">: ")))
      (if (and novo-cli-b (/= novo-cli-b "")) (setq cli-b novo-cli-b))
      (setq novo-kva (getstring (strcat "\nPotência KVA <" kva ">: ")))
      (if (and novo-kva (/= novo-kva "")) (setq kva novo-kva))
    )
  )

  ;; Menu de Opções de Geração
  (initget "1 2 3 4 A Esquema Ramal Ambos Texto Atualizar")
  (setq opc (getkword "\nOpções: [1] Esquema Prancha | [2] Ramal Geográfico DWG | [3] Ambos | [4] Somente Texto | [A]tualizar <1>: "))
  (if (or (not opc) (= opc "")) (setq opc "1"))

  (setq h-txt (getvar "TEXTSIZE"))
  (if (or (<= h-txt 0.0) (> h-txt 10.0)) (setq h-txt 2.5))

  ;; Configuração do Bloco do Transformador (Padrão: TRAFO1, com suporte a lista e seleção no CAD)
  (setq bloco-trafo "TRAFO1")
  (if (or (= opc "1") (= opc "Esquema") (= opc "2") (= opc "Ramal") (= opc "3") (= opc "Ambos"))
    (setq bloco-trafo (unifilar-obter-bloco-trafo))
  )

  (cond
    ;; -------------------------------------------------------------------------
    ;; MODO 1 OU 3: ESQUEMA GRÁFICO NA PRANCHA (+ RAMAL SE AMBOS)
    ;; -------------------------------------------------------------------------
    ((or (= opc "1") (= opc "Esquema") (= opc "3") (= opc "Ambos"))
     (setq pt-ins (getpoint "\nClique no ponto de inserção do Diagrama Unifilar na Prancha: "))
     (if pt-ins
       (unifilar-draw-esquema-grafico pt-ins se alim prot-rot prot-tipo ponto cli-a cli-b kva bloco-prot bloco-trafo h-txt)
     )
     (if (or (= opc "3") (= opc "Ambos"))
       (if (and utm-x utm-y)
         (unifilar-draw-ramal-geografico ponto utm-x utm-y prot-rot bloco-prot bloco-trafo)
         (princ "\n[UNIFILAR] Coordenadas KMZ não disponíveis para traçar o ramal no DWG.")
       )
     )
    )

    ;; -------------------------------------------------------------------------
    ;; MODO 2: APENAS RAMAL GEOGRÁFICO NO DWG
    ;; -------------------------------------------------------------------------
    ((or (= opc "2") (= opc "Ramal"))
     (if (and utm-x utm-y)
       (unifilar-draw-ramal-geografico ponto utm-x utm-y prot-rot bloco-prot bloco-trafo)
       (princ "\n[UNIFILAR] Dispositivo de proteção não possui coordenadas KMZ mapeadas para traçar no DWG.")
     )
    )

    ;; -------------------------------------------------------------------------
    ;; MODO 4: APENAS TEXTOS TÉCNICOS TRADICIONAIS
    ;; -------------------------------------------------------------------------
    ((or (= opc "4") (= opc "Texto"))
     (setq pt-ins (getpoint "\nClique no ponto de inserção do Diagrama Unifilar: "))
     (if pt-ins
       (progn
         (unifilar-ensure-layer "UNIFILAR" 3)
         (setq x (car pt-ins))
         (setq y (cadr pt-ins))
         (setq sp (* h-txt 1.6))

         ;; 1. Título Verde Sublinhado
         (unifilar-draw-text (list x y 0.0) "DIAGRAMA  UNIFILAR" (* h-txt 1.2) "UNIFILAR" 3 "LEFT")
         (unifilar-draw-line (list x (- y (* h-txt 0.3)) 0.0) (list (+ x (* h-txt 14.0)) (- y (* h-txt 0.3)) 0.0) "UNIFILAR" 3)

         ;; 2. Textos Técnicos Alinhados à Direita
         (setq x-al (+ x (* h-txt 14.0)))
         (setq y-cur (- y (* sp 1.5)))

         (unifilar-draw-text (list x-al y-cur 0.0) (strcat "SE.: " se) h-txt "UNIFILAR" 7 "RIGHT")
         (setq y-cur (- y-cur sp))

         (unifilar-draw-text (list x-al y-cur 0.0) (strcat "ALIM.: " alim) h-txt "UNIFILAR" 7 "RIGHT")
         (setq y-cur (- y-cur sp))

         (unifilar-draw-text (list x-al y-cur 0.0) "FONTE DE ALIMENTAÇÃO" h-txt "UNIFILAR" 7 "RIGHT")
         (setq y-cur (- y-cur sp))

         (unifilar-draw-text (list x-al y-cur 0.0) (strcat "DISPOSITIVO DE PROTEÇÃO: " prot-rot) h-txt "UNIFILAR" 7 "RIGHT")
         (setq y-cur (- y-cur sp))

         (unifilar-draw-text (list x-al y-cur 0.0) (strcat "Clientes Grupo A: " cli-a " Clientes Grupo B: " cli-b " - KVA: " kva) h-txt "UNIFILAR" 7 "RIGHT")

         (princ "\n[UNIFILAR] Textos do Diagrama Unifilar inseridos com sucesso!")
       )
     )
    )

    ;; -------------------------------------------------------------------------
    ;; MODO A: ATUALIZAR TEXTOS EXISTENTES NO DWG
    ;; -------------------------------------------------------------------------
    ((or (= opc "A") (= opc "Atualizar"))
     (princ "\nSelecione os textos do Diagrama Unifilar existente para preencher...")
     (setq ss (ssget '((0 . "TEXT,MTEXT"))))
     (if ss
       (progn
         (setq i 0)
         (setq cnt-upd 0)
         (while (< i (sslength ss))
           (setq ent-i (ssname ss i))
           (setq txt-i (unifilar-extract-text-from-ent ent-i))

           (cond
             ;; Substituição de SE.: xxx
             ((and (vl-string-search "SE" (strcase txt-i)) (vl-string-search "X" (strcase txt-i)))
              (unifilar-update-ent-text ent-i (strcat "SE.: " se))
              (setq cnt-upd (1+ cnt-upd))
             )
             ;; Substituição de ALIM.: xx
             ((and (vl-string-search "ALIM" (strcase txt-i)) (vl-string-search "X" (strcase txt-i)))
              (unifilar-update-ent-text ent-i (strcat "ALIM.: " alim))
              (setq cnt-upd (1+ cnt-upd))
             )
             ;; Substituição de DISPOSITIVO DE PROTEÇÃO...
             ((vl-string-search "DISPOSITIVO DE PROTE" (strcase txt-i))
              (unifilar-update-ent-text ent-i (strcat "DISPOSITIVO DE PROTEÇÃO: " prot-rot))
              (setq cnt-upd (1+ cnt-upd))
             )
             ;; Substituição de Clientes Grupo A...
             ((vl-string-search "CLIENTES GRUPO" (strcase txt-i))
              (unifilar-update-ent-text ent-i (strcat "Clientes Grupo A: " cli-a " Clientes Grupo B: " cli-b " - KVA: " kva))
              (setq cnt-upd (1+ cnt-upd))
             )
           )
           (setq i (1+ i))
         )
         (princ (strcat "\n[UNIFILAR] " (itoa cnt-upd) " textos atualizados com sucesso no DWG!"))
       )
       (princ "\n[UNIFILAR] Nenhum texto selecionado.")
     )
    )
  )

  (princ)
)

;; Aliases de comando para conveniência do usuário
(defun c:PROTECAO () (c:UNIFILAR))
(defun c:ARVORE () (c:UNIFILAR))
(defun c:BUSCAR_PROTECAO () (c:UNIFILAR))
(defun c:UNIFILARDW () (c:UNIFILAR))

(princ "\n[AUX CAD] Módulo UNIFILAR carregado com sucesso! Digite UNIFILAR ou PROTECAO.")
(princ)
