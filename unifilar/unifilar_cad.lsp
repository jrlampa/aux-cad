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
                     cli-a cli-b kva pt-ins h-txt opc ss i ent-i txt-i cnt-upd x y sp x-al y-cur)

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

  ;; Solicita Ponto Elétrico
  (initget "Selecionar S")
  (setq ponto (getstring "\nInforme o Ponto Elétrico ou [S]elecionar no DWG <SG40995>: "))
  (if (or (= ponto "") (= ponto nil))
    (setq ponto "SG40995")
  )

  (if (or (= (strcase ponto) "S") (= (strcase ponto) "SELECIONAR"))
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
              (princ "\n[UNIFILAR] Nenhum texto extraído. Usando SG40995.")
              (setq ponto "SG40995")
            )
          )
        )
        (setq ponto "SG40995")
      )
    )
  )

  ;; Prepara arquivo temporário de intercâmbio JSON e log de diagnóstico
  (setq tmp-json (vl-filename-mktemp "unifilar_" nil ".json"))
  (setq tmp-log (vl-filename-mktemp "unifilar_log_" nil ".txt"))
  (setq cmd (strcat "python \"" py-script "\" --ponto \"" ponto "\" --out \"" tmp-json "\" > \"" tmp-log "\" 2>&1"))

  (princ (strcat "\n[UNIFILAR] Consultando proteção a montante para '" ponto "'..."))

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

  (if (not se) (setq se "---"))
  (if (not alim) (setq alim "--"))
  (if (not prot-rot) (setq prot-rot "Proteção"))
  (if (not cli-a) (setq cli-a "0"))
  (if (not cli-b) (setq cli-b "0"))
  (if (not kva) (setq kva "0"))

  (princ "\n--------------------------------------------------------------")
  (princ (strcat "\n[UNIFILAR] PROTEÇÃO LOCALIZADA:"))
  (princ (strcat "\n • Subestação (SE): " se))
  (princ (strcat "\n • Alimentador:     " alim))
  (princ (strcat "\n • Proteção:        " prot-rot))
  (princ (strcat "\n • Cargas/Potência: Clientes Grupo A: " cli-a " Clientes Grupo B: " cli-b " - KVA: " kva))
  (princ "\n--------------------------------------------------------------")

  ;; Pergunta se deseja Inserir Novo ou Atualizar Existente
  (initget "Inserir Atualizar I A")
  (setq opc (getkword "\nDeseja [I]nserir novo diagrama ou [A]tualizar textos no DWG? <I>: "))
  (if (or (= opc nil) (= opc "") (= opc "I") (= opc "Inserir"))
    ;; -------------------------------------------------------------------------
    ;; MODO 1: INSERIR NOVO DIAGRAMA UNIFILAR
    ;; -------------------------------------------------------------------------
    (progn
      (setq pt-ins (getpoint "\nClique no ponto de inserção do Diagrama Unifilar: "))
      (if pt-ins
        (progn
          (unifilar-ensure-layer "UNIFILAR" 3)
          (setq h-txt (getvar "TEXTSIZE"))
          (if (or (<= h-txt 0.0) (> h-txt 10.0)) (setq h-txt 2.5))

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

          (unifilar-draw-text (list x-al y-cur 0.0) (strcat "DISPOSITIVO DE PROTEÇÃO:" prot-rot) h-txt "UNIFILAR" 7 "RIGHT")
          (setq y-cur (- y-cur sp))

          (unifilar-draw-text (list x-al y-cur 0.0) (strcat "Clientes Grupo A: " cli-a " Clientes Grupo B: " cli-b " - KVA: " kva) h-txt "UNIFILAR" 7 "RIGHT")

          (princ "\n[UNIFILAR] Diagrama Unifilar inserido com sucesso!")
        )
      )
    )

    ;; -------------------------------------------------------------------------
    ;; MODO 2: ATUALIZAR TEXTOS EXISTENTES NO DWG
    ;; -------------------------------------------------------------------------
    (progn
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
               (unifilar-update-ent-text ent-i (strcat "DISPOSITIVO DE PROTEÇÃO:" prot-rot))
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
