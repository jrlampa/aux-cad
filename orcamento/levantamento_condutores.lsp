;;; ============================================================================
;;; levantamento_condutores.lsp - Levantamento genérico de condutores no DWG
;;; Comando: LEVANTAR_CONDUTORES
;;; Soma DIMENSION, TEXT e MTEXT por condutor e operação (instalar/retirar).
;;; Suporta coleta incremental com pausa, retomada e persistência isolada por DWG.
;;; ============================================================================

(vl-load-com)

;;; ----------------------------------------------------------------------------
;;; 1. UTILITÁRIOS DE STRING E SANITIZAÇÃO DE TEXTO
;;; ----------------------------------------------------------------------------

(defun lc-trim (value)
  (vl-string-trim " \t\r\n{}" value)
)

(defun lc-strip-mtext (value / index length char next end result)
  (setq index 1
        length (strlen value)
        result "")
  (while (<= index length)
    (setq char (substr value index 1))
    (cond
      ((or (= char "{") (= char "}"))
       (setq index (1+ index)))
      ((= char "\\")
       (setq next (if (< index length) (substr value (1+ index) 1) ""))
       (cond
         ((or (= (strcase next) "P") (= next "~"))
          (setq result (strcat result " ")
                index (+ index 2)))
         (t
          (setq end (+ index 1))
          (while (and (<= end length) (/= (substr value end 1) ";"))
            (setq end (1+ end)))
          (if (<= end length)
            (setq index (1+ end))
            (setq index (+ index 2))))))
      (t
       (setq result (strcat result char)
             index (1+ index)))))
  (lc-trim result)
)

(defun lc-parse-meters (value / text length index char digits dots valid)
  (if (not (= (type value) 'STR))
    nil
    (progn
      (setq text (lc-trim (vl-string-translate "," "." value)))
      (setq length (strlen text))
      (if (and (> length 0) (= (strcase (substr text length 1)) "M"))
        (setq text (lc-trim (substr text 1 (1- length)))))
      (setq length (strlen text)
            index 1
            digits 0
            dots 0
            valid (> length 0))
      (while (and valid (<= index length))
        (setq char (substr text index 1))
        (cond
          ((and (= index 1) (or (= char "+") (= char "-"))))
          ((and (>= (ascii char) 48) (<= (ascii char) 57))
           (setq digits (1+ digits)))
          ((= char ".")
           (setq dots (1+ dots))
           (if (> dots 1) (setq valid nil)))
          (t (setq valid nil)))
        (setq index (1+ index)))
      (if (and valid (> digits 0))
        (progn
          (setq length (atof text))
          (if (> length 0.0) length nil))
        nil))))

(defun lc-get-entity-meters (entity / data entity-type object result override raw)
  (setq data (entget entity)
        entity-type (cdr (assoc 0 data)))
  (cond
    ((= entity-type "DIMENSION")
     ;; DXF group 1 stores the displayed override; never substitute Measurement
     ;; when an explicit numeric override exists.
     (setq override (cdr (assoc 1 data)))
     (if (or (not (= (type override) 'STR))
             (= (lc-trim override) "")
             (vl-string-search "<>" override))
       (progn
         (setq object (vlax-ename->vla-object entity))
         (setq result
           (vl-catch-all-apply 'vlax-get-property (list object 'Measurement)))
         (if (and (not (vl-catch-all-error-p result)) (numberp result) (> result 0.0))
           result
           nil))
       (lc-parse-meters (lc-strip-mtext override))))
    ((or (= entity-type "TEXT") (= entity-type "MTEXT"))
     (setq raw (if (= entity-type "MTEXT")
                 (lc-strip-mtext (cdr (assoc 1 data)))
                 (lc-trim (cdr (assoc 1 data)))))
     (lc-parse-meters raw))
    (t nil)))

(defun lc-get-entity-reading (entity / data entity-type override)
  (setq data (entget entity)
        entity-type (cdr (assoc 0 data)))
  (cond
    ((= entity-type "DIMENSION")
     (setq override (cdr (assoc 1 data)))
     (if (and (= (type override) 'STR)
              (/= (lc-trim override) "")
              (not (vl-string-search "<>" override)))
       (list "OVERRIDE" (lc-strip-mtext override))
       (list "MEASUREMENT" (if (= (type override) 'STR) override "<sem override>"))))
    ((= entity-type "TEXT")
     (list "TEXT" (lc-trim (cdr (assoc 1 data)))))
    ((= entity-type "MTEXT")
     (list "MTEXT" (lc-strip-mtext (cdr (assoc 1 data)))))
    (t (list entity-type ""))))

(defun lc-add-total (key label column amount rows / row current updated)
  (setq row (assoc key rows))
  (if row
    (progn
      (setq updated
        (list key (nth 1 row)
              (if (= column 2) (+ (nth 2 row) amount) (nth 2 row))
              (if (= column 3) (+ (nth 3 row) amount) (nth 3 row))
              (if (= column 4) (+ (nth 4 row) amount) (nth 4 row))))
      (subst updated row rows))
    (append rows
      (list (list key label
                  (if (= column 2) amount 0.0)
                  (if (= column 3) amount 0.0)
                  (if (= column 4) amount 0.0))))))

(defun lc-format-meters (amount / whole)
  ;; Comprimentos positivos: arredondamento sempre para cima, sem casas decimais.
  (setq whole (fix amount))
  (if (> (- amount whole) 0.00000001)
    (setq whole (1+ whole)))
  (strcat (itoa whole) "m"))

;;; ----------------------------------------------------------------------------
;;; 2. PERSISTÊNCIA ISOLADA POR DWG (AutoCAD LData)
;;; ----------------------------------------------------------------------------

(setq *lc-dict-name* "OXCAD_LEVANTAMENTO_CONDUTORES")
(setq *lc-key-name*  "ESTADO")

(defun lc-db-obter-estado (/ dados)
  "Recupera o estado da coleta persistida no DWG ativo (itens e rows)."
  (setq dados (vlax-ldata-get *lc-dict-name* *lc-key-name*))
  (if (listp dados) dados nil))

(defun lc-db-salvar-estado (items rows)
  "Persiste atômicamente no DWG ativo a lista de itens e totais agregados."
  (vlax-ldata-put *lc-dict-name* *lc-key-name*
    (list (cons "ITENS" items) (cons "ROWS" rows))))

(defun lc-db-limpar-estado ()
  "Remove a coleta persistida do DWG ativo."
  (vlax-ldata-delete *lc-dict-name* *lc-key-name*))

;;; ----------------------------------------------------------------------------
;;; 3. AUDITORIA DE ENTIDADES E PREVENÇÃO DE INCONSISTÊNCIAS
;;; ----------------------------------------------------------------------------

(defun lc-verificar-integridade-itens (items / problemas ent handle curr-amount old-amount)
  "Identifica entidades coletadas que foram excluídas do DWG ou tiveram metragem alterada."
  (setq problemas '())
  (foreach item items
    (setq handle (car item)
          ent (handent handle))
    (cond
      ((or (null ent) (null (entget ent)))
       (setq problemas (append problemas (list (list "EXCLUIDA" handle item)))))
      (t
       (setq curr-amount (lc-get-entity-meters ent)
             old-amount (nth 3 (cdr item)))
       (if (or (null curr-amount) (> (abs (- curr-amount old-amount)) 0.0001))
         (setq problemas
           (append problemas
             (list (list "MODIFICADA" handle item (if curr-amount curr-amount 0.0)))))))))
  problemas)

(defun lc-exibir-revisao (items rows / problemas r)
  "Exibe resumo dos condutores acumulados e auditoria de entidades no console de texto."
  (textscr)
  (princ "\n==========================================================================================")
  (princ "\n          REVISÃO DE LEVANTAMENTO DE CONDUTORES NO DWG - OXCAD                            ")
  (princ "\n==========================================================================================")
  (princ "\n CONDUTOR                                | INSTALAR      | RETIRAR       | REAPROVEITAR   ")
  (princ "\n------------------------------------------------------------------------------------------")
  (foreach r rows
    (princ (strcat "\n " (nth 1 r)
                   (substr "                                        " 1 (max 1 (- 40 (strlen (nth 1 r)))))
                   " | " (if (> (nth 2 r) 0.0) (lc-format-meters (nth 2 r)) "-")
                   (substr "              " 1 (max 1 (- 13 (strlen (if (> (nth 2 r) 0.0) (lc-format-meters (nth 2 r)) "-")))))
                   " | " (if (> (nth 3 r) 0.0) (lc-format-meters (nth 3 r)) "-")
                   (substr "              " 1 (max 1 (- 13 (strlen (if (> (nth 3 r) 0.0) (lc-format-meters (nth 3 r)) "-")))))
                   " | " (if (> (nth 4 r) 0.0) (lc-format-meters (nth 4 r)) "-"))))
  (princ "\n------------------------------------------------------------------------------------------")
  (princ (strcat "\n Total de entidades rastreadas por Handle: " (itoa (length items))))

  (setq problemas (lc-verificar-integridade-itens items))
  (if (> (length problemas) 0)
    (progn
      (princ "\n\n [ATENÇÃO] INCONSISTÊNCIAS DETECTADAS NO DWG:")
      (foreach p problemas
        (if (= (car p) "EXCLUIDA")
          (princ (strcat "\n   - [EXCLUÍDA] Handle #" (cadr p) " ("
                         (nth 1 (caddr p)) " / " (nth 2 (caddr p)) "): Entidade não encontrada no DWG."))
          (princ (strcat "\n   - [MODIFICADA] Handle #" (cadr p) " ("
                         (nth 1 (caddr p)) " / " (nth 2 (caddr p)) "): Valor original "
                         (lc-format-meters (nth 3 (caddr p)))
                         " alterado no DWG para " (lc-format-meters (nth 3 p)) "."))))
      (princ "\n Use a opção de reconciliação para sincronizar com as entidades atuais."))
    (princ "\n [OK] Todas as entidades rastreadas permanecem íntegras e sincronizadas."))
  (princ "\n==========================================================================================\n")
  (graphscr))

(defun lc-reconciliar-itens (items / new-items new-rows ent handle curr-amount condutor oper col)
  "Reconstrói os itens e totais acumulados com base nas entidades válidas no DWG."
  (setq new-items '()
        new-rows '())
  (foreach item items
    (setq handle (car item)
          ent (handent handle))
    (if (and ent (entget ent))
      (progn
        (setq curr-amount (lc-get-entity-meters ent))
        (if (and curr-amount (> curr-amount 0.0))
          (progn
            (setq condutor (nth 1 (cdr item))
                  oper     (nth 2 (cdr item))
                  col      (cond
                             ((= (strcase oper) "REAPROVEITAR") 4)
                             ((= (strcase oper) "RETIRAR") 3)
                             (t 2)))
            (setq new-items
              (append new-items
                (list (cons handle (list (nth 0 (cdr item)) condutor oper curr-amount
                                         (nth 4 (cdr item)) (nth 5 (cdr item)))))))
            (setq new-rows
              (lc-add-total (strcase (lc-trim condutor)) condutor col curr-amount new-rows)))))))
  (list new-items new-rows))

;;; ----------------------------------------------------------------------------
;;; 4. GERAÇÃO DA TABELA NATIVA DO AUTOCAD
;;; ----------------------------------------------------------------------------

(defun lc-create-table (rows / acad document space point table row-count index item table-res fill-res)
  (setq acad (vlax-get-acad-object)
        document (vla-get-ActiveDocument acad)
        space (vla-get-Block (vla-get-ActiveLayout document))
        point (getpoint "\nPonto de inserção da tabela: "))
  (if point
    (progn
      (setq row-count (+ 2 (length rows)))
      (setq table-res
        (vl-catch-all-apply
          '(lambda ()
             (vla-AddTable space (vlax-3d-point point) row-count 4 6.0 32.0))))
      (if (vl-catch-all-error-p table-res)
        (progn
          (princ (strcat "\n[LEVANTAMENTO][ERRO] Falha ao criar tabela: "
                         (vl-catch-all-error-message table-res)))
          nil)
        (progn
          (setq table table-res)
          (setq fill-res
            (vl-catch-all-apply
              '(lambda ()
                 (vla-put-Layer table "0")
                 (vla-MergeCells table 0 0 0 3)
                 (vla-SetText table 0 0 "TABELA DE CONDUTORES")
                 (vla-SetText table 1 0 "CONDUTOR")
                 (vla-SetText table 1 1 "INSTALAR (m)")
                 (vla-SetText table 1 2 "RETIRAR (m)")
                 (vla-SetText table 1 3 "REAPROVEITAR (m)")
                 (vla-SetColumnWidth table 0 42.0)
                 (vla-SetColumnWidth table 1 30.0)
                 (vla-SetColumnWidth table 2 30.0)
                 (vla-SetColumnWidth table 3 35.0)
                 (setq index 0)
                 (foreach item rows
                   (vla-SetText table (+ index 2) 0 (nth 1 item))
                   (vla-SetText table (+ index 2) 1
                     (if (> (nth 2 item) 0.0) (lc-format-meters (nth 2 item)) "-"))
                   (vla-SetText table (+ index 2) 2
                     (if (> (nth 3 item) 0.0) (lc-format-meters (nth 3 item)) "-"))
                   (vla-SetText table (+ index 2) 3
                     (if (> (nth 4 item) 0.0) (lc-format-meters (nth 4 item)) "-"))
                   (setq index (1+ index)))
                 (vla-Update table))))
          (if (vl-catch-all-error-p fill-res)
            (progn
              (princ (strcat "\n[LEVANTAMENTO][ERRO] Falha ao preencher tabela: "
                             (vl-catch-all-error-message fill-res)))
              nil)
            (progn
              (princ (strcat "\nTabela criada com " (itoa (length rows)) " condutores."))
              t)))))
    (progn
      (princ "\nComando cancelado; tabela não criada.")
      nil)))

;;; ----------------------------------------------------------------------------
;;; 5. COMANDO PRINCIPAL: LEVANTAR_CONDUTORES
;;; ----------------------------------------------------------------------------

(defun c:LEVANTAR_CONDUTORES (/ *error* rows conductor key operation column selection
                                preselected entity amount accepted index old-pickadd reading
                                valid-count skipped-count duplicate-count row estado items
                                opt looping table-ok handle rec-res prob-count problemas
                                paused ja-existe-mesma-op)
  (vl-load-com)

  ;; Recupera estado persistido no DWG ativo
  (setq estado (lc-db-obter-estado))
  (if estado
    (setq items (cdr (assoc "ITENS" estado))
          rows  (cdr (assoc "ROWS" estado)))
    (setq items '()
          rows  '()))

  (setq paused nil)

  (defun *error* (message)
    (if (numberp old-pickadd) (setvar "PICKADD" old-pickadd))
    (if (and message (/= message "Function cancelled") (/= message "quit / exit abort"))
      (princ (strcat "\n[LEVANTAMENTO][ERRO] " message)))
    (if (and items (> (length items) 0))
      (princ "\n[LEVANTAMENTO] Operação interrompida. Dados preservados no DWG ativo. Use LEVANTAR_CONDUTORES para continuar."))
    (princ))

  ;; Menu contextual quando já existe coleta pendente no DWG
  (if (and items (> (length items) 0))
    (progn
      (princ (strcat "\n[LEVANTAMENTO] Coleta ativa encontrada no DWG ("
                     (itoa (length rows)) " condutores, "
                     (itoa (length items)) " entidades)."))
      (initget "Continuar Pausar Revisar Concluir Gerar Descartar")
      (setq opt (getkword "\nOpção [Continuar/Pausar/Revisar/Concluir/Descartar] <Continuar>: "))
      (if (null opt) (setq opt "Continuar"))
      (cond
        ((= opt "Pausar")
         (princ "\n[LEVANTAMENTO] Coleta pausada. Dados preservados no DWG ativo sem gerar tabela.")
         (setq paused t
               conductor ""))

        ((or (= opt "Concluir") (= opt "Gerar"))
         (setq problemas (lc-verificar-integridade-itens items))
         (if (> (length problemas) 0)
           (progn
             (princ (strcat "\n[ATENÇÃO] Foram detectadas " (itoa (length problemas))
                            " inconsistências em entidades do DWG."))
             (initget "Revisar Ignorar Cancelar")
             (setq opt (getkword "\nOpção [Revisar/Ignorar/Cancelar] <Revisar>: "))
             (if (null opt) (setq opt "Revisar"))
             (if (= opt "Revisar")
               (progn
                 (lc-exibir-revisao items rows)
                 (initget "Sim Nao")
                 (if (= (getkword "\nDeseja reconciliar as medidas com as entidades atuais? [Sim/Nao] <Sim>: ") "Nao")
                   (princ "\nValores originais mantidos.")
                   (progn
                     (setq rec-res (lc-reconciliar-itens items)
                           items   (car rec-res)
                           rows    (cadr rec-res))
                     (lc-db-salvar-estado items rows)
                     (princ "\nColeta reconciliada com o DWG ativo.")))))))
         (if (and rows (> (length rows) 0))
           (progn
             (setq table-ok (lc-create-table rows))
             (if table-ok
               (progn
                 (lc-db-limpar-estado)
                 (princ "\n[SUCESSO] Tabela inserida e memória de condutores limpa."))
               (princ "\nA tabela não foi gerada; coleta mantida no DWG.")))
           (princ "\nNenhum condutor registrado; tabela não criada."))
         (setq conductor ""))

        ((= opt "Revisar")
         (lc-exibir-revisao items rows)
         (initget "Sim Nao")
         (if (= (getkword "\nDeseja reconciliar medidas alteradas/excluídas? [Sim/Nao] <Nao>: ") "Sim")
           (progn
             (setq rec-res (lc-reconciliar-itens items)
                   items   (car rec-res)
                   rows    (cadr rec-res))
             (lc-db-salvar-estado items rows)
             (princ "\nColeta reconciliada com o DWG ativo.")))
         (initget "Continuar Pausar Sair")
         (setq opt (getkword "\nDeseja continuar a seleção de condutores? [Continuar/Pausar/Sair] <Continuar>: "))
         (if (or (= opt "Sair") (= opt "Pausar"))
           (progn
             (princ "\n[LEVANTAMENTO] Coleta mantida no DWG ativo.")
             (setq paused t
                   conductor ""))
           (setq conductor nil)))

        ((= opt "Descartar")
         (initget "Sim Nao")
         (if (= (getkword "\nDeseja realmente descartar toda a coleta pendente deste DWG? [Sim/Nao] <Nao>: ") "Sim")
           (progn
             (lc-db-limpar-estado)
             (setq items '()
                   rows  '())
             (princ "\nColeta de condutores descartada com sucesso."))
           (princ "\nDescarte cancelado; coleta mantida."))
         (setq conductor ""))

        ((= opt "Continuar")
         (setq conductor nil))))
    (setq conductor nil))

  ;; Preserve implied selection before command prompts clear the selection context.
  (if (and (null paused) (null conductor))
    (progn
      (setq preselected (ssget "_I" '((0 . "DIMENSION,TEXT,MTEXT"))))
      (if preselected
        (princ (strcat "\n[LEVANTAMENTO][PRESELECAO] entidades=" (itoa (sslength preselected))))
        (princ "\n[LEVANTAMENTO][PRESELECAO] nenhuma entidade compatível; será usada seleção manual."))
      (princ "\nLevantamento genérico. Tipos aceitos: cotas, TEXT e MTEXT com medida em metros.")
      (setq conductor (getstring T "\nCondutor (Enter para concluir ou 'P' para pausar): "))))

  (while (and conductor
              (/= (lc-trim conductor) "")
              (/= (strcase (lc-trim conductor)) "P")
              (/= (strcase (lc-trim conductor)) "PAUSAR"))
    (setq key (strcase (lc-trim conductor)))
    (initget "Instalar Retirar Reaproveitar")
    (setq operation (getkword "\nOperação [Instalar/Retirar/Reaproveitar] <Instalar>: "))
    (if (null operation) (setq operation "Instalar"))
    (setq column (cond
                   ((= (strcase operation) "REAPROVEITAR") 4)
                   ((= (strcase operation) "RETIRAR") 3)
                   (t 2))
          accepted 0
          valid-count 0
          skipped-count 0
          duplicate-count 0)
    (if preselected
      (progn
        (setq selection preselected
              preselected nil)
        (princ (strcat "\n[LEVANTAMENTO][SELECAO] usando pré-seleção para " conductor
                       " / " (strcase operation) ".")))
      (progn
        (setq old-pickadd (getvar "PICKADD"))
        ;; Native selection semantics: click adds, Shift+click removes before Enter.
        (setvar "PICKADD" 2)
        (princ (strcat "\nSelecione cotas/TEXT/MTEXT de " conductor
                       " para " (strcase operation)
                       ". Clique adiciona; Shift+clique remove; Enter conclui: "))
        (setq selection (ssget '((0 . "DIMENSION,TEXT,MTEXT"))))))
    (if selection
      (progn
        (setq index 0)
        (repeat (sslength selection)
          (setq entity (ssname selection index)
                handle (cdr (assoc 5 (entget entity)))
                amount (lc-get-entity-meters entity)
                reading (lc-get-entity-reading entity))
          (setq ja-existe-mesma-op
            (vl-some '(lambda (it)
                        (and (= (car it) handle)
                             (= (strcase (nth 0 (cdr it))) key)
                             (= (strcase (nth 2 (cdr it))) (strcase operation))))
                     items))
          (cond
            ;; Prevenção de dupla contabilização na mesma operação para o mesmo condutor
            (ja-existe-mesma-op
             (setq duplicate-count (1+ duplicate-count))
             (princ (strcat "\n[LEVANTAMENTO][IGNORADO] Handle #" handle
                            " motivo=entidade já contabilizada nesta operação (" (strcase operation)
                            ") para o condutor " conductor)))
            ;; Nova medição válida
            (amount
             (setq items (append items
                           (list (cons handle (list key conductor operation amount
                                                    (car reading) (cadr reading))))))
             (setq rows (lc-add-total key conductor column amount rows)
                   accepted (1+ accepted)
                   valid-count (1+ valid-count)
                   row (assoc key rows))
             (princ (strcat "\n[LEVANTAMENTO][ITEM] tipo=" (cdr (assoc 0 (entget entity)))
                            " origem=" (car reading)
                            " texto=\"" (cadr reading) "\" valor="
                            (lc-format-meters amount) " total_" (strcase operation) "="
                            (lc-format-meters (nth column row)))))
            ;; Entidade sem valor métrico
            (t
             (setq skipped-count (1+ skipped-count))
             (princ (strcat "\n[LEVANTAMENTO][IGNORADO] tipo=" (cdr (assoc 0 (entget entity)))
                            " texto=\"" (cadr reading)
                            "\" motivo=sem medida numérica válida em metros"))))
          (setq index (1+ index)))

        ;; Salva estado imediatamente no DWG ativo (garante sobrevivência a pausas e interrupções)
        (lc-db-salvar-estado items rows)

        (princ (strcat "\n[LEVANTAMENTO][RESUMO] condutor=" conductor
                       " operação=" (strcase operation)
                       " válidas=" (itoa valid-count)
                       " ignoradas=" (itoa skipped-count)
                       (if (> duplicate-count 0)
                         (strcat " duplicadas=" (itoa duplicate-count))
                         ""))))
      (princ (strcat "\n[LEVANTAMENTO][RESUMO] nenhuma entidade selecionada para " conductor ".")))

    (if (numberp old-pickadd)
      (progn
        (setvar "PICKADD" old-pickadd)
        (setq old-pickadd nil)))
    (if (= accepted 0)
      (princ (strcat "\nNenhuma medida válida registrada para " conductor ".")))
    (setq conductor (getstring T "\nPróximo condutor (Enter para concluir ou 'P' para pausar): ")))

  ;; Se o usuário solicitou pausar durante a entrada de condutores
  (if (or (= (strcase (lc-trim (if conductor conductor ""))) "P")
          (= (strcase (lc-trim (if conductor conductor ""))) "PAUSAR"))
    (progn
      (setq paused t)
      (princ "\n[LEVANTAMENTO] Coleta pausada com sucesso. Dados preservados no DWG ativo sem gerar tabela.")))

  ;; Conclusão do levantamento (somente se não estiver pausado)
  (if (and (null paused) rows (> (length rows) 0))
    (progn
      (setq table-ok (lc-create-table rows))
      (if table-ok
        (progn
          (lc-db-limpar-estado)
          (princ "\n[SUCESSO] Tabela inserida e memória de condutores limpa."))
        (princ "\nNenhum comprimento foi inserido na prancha; coleta preservada no DWG.")))
    (if (and (null paused) (null estado))
      (princ "\nNenhum comprimento foi registrado; tabela não criada.")))

  (if (numberp old-pickadd) (setvar "PICKADD" old-pickadd))
  (princ))

(defun c:RECARREGAR_CONDUTORES (/ _path)
  (setq _path (findfile "orcamento\\levantamento_condutores.lsp"))
  (if (null _path) (setq _path (findfile "levantamento_condutores.lsp")))
  (if _path
    (progn
      (load _path)
      (princ "\n[SUCESSO] Módulo LEVANTAR_CONDUTORES recarregado na sessão."))
    (princ "\n[ERRO] Arquivo levantamento_condutores.lsp não encontrado."))
  (princ))

(princ "\n[LEVANTAMENTO] Módulo carregado. Use LEVANTAR_CONDUTORES ou RECARREGAR_CONDUTORES.")
(princ)
