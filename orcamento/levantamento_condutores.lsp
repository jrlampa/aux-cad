;;; ============================================================================
;;; levantamento_condutores.lsp - Levantamento genérico de condutores no DWG
;;; Comando: LEVANTAR_CONDUTORES
;;; Soma DIMENSION, TEXT e MTEXT por condutor e operação (instalar/retirar).
;;; ============================================================================

(vl-load-com)

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
      (setq current (nth column row)
            updated (list key (nth 1 row)
                          (if (= column 2) (+ current amount) (nth 2 row))
                          (if (= column 3) (+ current amount) (nth 3 row))))
      (subst updated row rows))
    (append rows
      (list (list key label
                  (if (= column 2) amount 0.0)
                  (if (= column 3) amount 0.0))))))

(defun lc-format-meters (amount / whole)
  ;; Comprimentos positivos: arredondamento sempre para cima, sem casas decimais.
  (setq whole (fix amount))
  (if (> (- amount whole) 0.00000001)
    (setq whole (1+ whole)))
  (strcat (itoa whole) "m"))

(defun lc-create-table (rows / acad document space point table row-count index item)
  (setq acad (vlax-get-acad-object)
        document (vla-get-ActiveDocument acad)
        space (vla-get-Block (vla-get-ActiveLayout document))
        point (getpoint "\nPonto de inserção da tabela: "))
  (if point
    (progn
      (setq row-count (+ 2 (length rows)))
      (setq table (vla-AddTable space (vlax-3d-point point) row-count 3 6.0 32.0))
      (vla-put-Layer table "0")
      (vla-MergeCells table 0 0 0 2)
      (vla-SetText table 0 0 "TABELA DE CONDUTORES")
      (vla-SetText table 1 0 "CONDUTOR")
      (vla-SetText table 1 1 "INSTALAR")
      (vla-SetText table 1 2 "RETIRAR")
      (vla-SetColumnWidth table 0 42.0)
      (vla-SetColumnWidth table 1 30.0)
      (vla-SetColumnWidth table 2 30.0)
      (setq index 0)
      (foreach item rows
        (vla-SetText table (+ index 2) 0 (nth 1 item))
        (vla-SetText table (+ index 2) 1
          (if (> (nth 2 item) 0.0) (lc-format-meters (nth 2 item)) "-"))
        (vla-SetText table (+ index 2) 2
          (if (> (nth 3 item) 0.0) (lc-format-meters (nth 3 item)) "-"))
        (setq index (1+ index)))
      (vla-Update table)
      (princ (strcat "\nTabela criada com " (itoa (length rows)) " condutores.")))
    (princ "\nComando cancelado; tabela não criada.")))

(defun c:LEVANTAR_CONDUTORES (/ *error* rows conductor key operation column selection preselected entity amount accepted index old-pickadd reading valid-count skipped-count row)
  (vl-load-com)
  (setq rows '())
  (defun *error* (message)
    (if (numberp old-pickadd) (setvar "PICKADD" old-pickadd))
    (if (and message (/= message "Function cancelled") (/= message "quit / exit abort"))
      (princ (strcat "\n[LEVANTAMENTO][ERRO] " message)))
    (princ))

  ;; Preserve implied selection before command prompts clear the selection context.
  (setq preselected (ssget "_I" '((0 . "DIMENSION,TEXT,MTEXT"))))
  (if preselected
    (princ (strcat "\n[LEVANTAMENTO][PRESELECAO] entidades=" (itoa (sslength preselected))))
    (princ "\n[LEVANTAMENTO][PRESELECAO] nenhuma entidade compatível; será usada seleção manual."))
  (princ "\nLevantamento genérico. Tipos aceitos: cotas, TEXT e MTEXT com medida em metros.")
  (setq conductor (getstring T "\nCondutor (Enter para concluir): "))
  (while (/= (lc-trim conductor) "")
    (setq key (strcase (lc-trim conductor)))
    (initget "Instalar Retirar")
    (setq operation (getkword "\nOperação [Instalar/Retirar] <Instalar>: "))
    (if (null operation) (setq operation "Instalar"))
    (setq column (if (= (strcase operation) "RETIRAR") 3 2)
          accepted 0
          valid-count 0
          skipped-count 0)
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
                amount (lc-get-entity-meters entity)
                reading (lc-get-entity-reading entity))
          (if amount
            (progn
              (setq rows (lc-add-total key conductor column amount rows)
                    accepted (1+ accepted)
                    valid-count (1+ valid-count)
                    row (assoc key rows))
              (princ (strcat "\n[LEVANTAMENTO][ITEM] tipo=" (cdr (assoc 0 (entget entity)))
                             " origem=" (car reading)
                             " texto=\"" (cadr reading) "\" valor="
                             (lc-format-meters amount) " total_" (strcase operation) "="
                             (lc-format-meters (nth column row)))))
            (progn
              (setq skipped-count (1+ skipped-count))
              (princ (strcat "\n[LEVANTAMENTO][IGNORADO] tipo=" (cdr (assoc 0 (entget entity)))
                             " texto=\"" (cadr reading)
                             "\" motivo=sem medida numérica válida em metros"))))
          (setq index (1+ index)))
        (princ (strcat "\n[LEVANTAMENTO][RESUMO] condutor=" conductor
                       " operação=" (strcase operation)
                       " válidas=" (itoa valid-count)
                       " ignoradas=" (itoa skipped-count))))
      (princ (strcat "\n[LEVANTAMENTO][RESUMO] nenhuma entidade selecionada para " conductor ".")))
    (if (numberp old-pickadd)
      (progn
        (setvar "PICKADD" old-pickadd)
        (setq old-pickadd nil)))
    (if (= accepted 0)
      (princ (strcat "\nNenhuma medida válida registrada para " conductor ".")))
    (setq conductor (getstring T "\nPróximo condutor (Enter para gerar tabela): ")))

  (if rows
    (lc-create-table rows)
    (princ "\nNenhum comprimento foi registrado; tabela não criada."))
  (princ))

(princ "\n[LEVANTAMENTO] Módulo carregado. Use LEVANTAR_CONDUTORES.")
(princ)