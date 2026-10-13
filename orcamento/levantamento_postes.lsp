;;; ============================================================================
;;; levantamento_postes.lsp - Levantamento de Postes e Clientes no DWG
;;; Comandos: LEVANTAR_POSTES, LP
;;; Coleta TEXT/MTEXT por ponto, calcula clientes, posições e CS,
;;; e gera tabela nativa do AutoCAD com persistência isolada por DWG (LData).
;;; ============================================================================

(vl-load-com)

;;; ----------------------------------------------------------------------------
;;; 1. UTILITÁRIOS DE STRING E SANITIZAÇÃO DE TEXTO
;;; ----------------------------------------------------------------------------

(defun lp-trim (value)
  (if (= (type value) 'STR)
    (vl-string-trim " \t\r\n{}" value)
    ""))

(defun lp-strip-mtext (value / index len char next end result)
  "Remove códigos de formatação MText mantendo quebras de linha normalizadas."
  (if (not (= (type value) 'STR))
    ""
    (progn
      (setq index 1
            len (strlen value)
            result "")
      (while (<= index len)
        (setq char (substr value index 1))
        (cond
          ((or (= char "{") (= char "}"))
           (setq index (1+ index)))
          ((= char "\\")
           (setq next (if (< index len) (substr value (1+ index) 1) ""))
           (cond
             ((or (= (strcase next) "P") (= next "~"))
              (setq result (strcat result "\n")
                    index (+ index 2)))
             (t
              (setq end (+ index 1))
              (while (and (<= end len) (/= (substr value end 1) ";"))
                (setq end (1+ end)))
              (if (<= end len)
                (setq index (1+ end))
                (setq index (+ index 2))))))
          (t
           (setq result (strcat result char)
                 index (1+ index)))))
      (lp-trim result))))

(defun lp-split-lines (text / len idx char line lines)
  "Divide uma string contendo quebras de linha em uma lista de linhas."
  (setq len (strlen text)
        idx 1
        line ""
        lines '())
  (while (<= idx len)
    (setq char (substr text idx 1))
    (if (or (= char "\n") (= char "\r"))
      (progn
        (if (/= (lp-trim line) "")
          (setq lines (append lines (list (lp-trim line)))))
        (setq line "")
        (if (and (< idx len)
                 (or (and (= char "\r") (= (substr text (1+ idx) 1) "\n"))
                     (and (= char "\n") (= (substr text (1+ idx) 1) "\r"))))
          (setq idx (1+ idx))))
      (setq line (strcat line char)))
    (setq idx (1+ idx)))
  (if (/= (lp-trim line) "")
    (setq lines (append lines (list (lp-trim line)))))
  lines)

;;; ----------------------------------------------------------------------------
;;; 2. FILTRAGEM DE RUÍDO E TEXTOS AUXILIARES
;;; ----------------------------------------------------------------------------

(defun lp-is-noise-line (line / upper)
  "Verifica se a linha contém dados auxiliares (esforço daN, demanda, etc.)."
  (setq upper (strcase (lp-trim line)))
  (or (= upper "")
      (vl-string-search "DAN" upper)
      (vl-string-search "ESF. RES" upper)
      (vl-string-search "ESF." upper)
      (vl-string-search "ESFORCO" upper)
      (vl-string-search "DEM.:" upper)
      (vl-string-search "DEM." upper)
      (vl-string-search "DEMANDA" upper)
      (vl-string-search "ACUM.:" upper)
      (vl-string-search "ACUM." upper)
      (vl-string-search "ACUMULADO" upper)
      (vl-string-search "KVA" upper)
      (vl-string-search "CLIENTE" upper)))

(defun lp-format-val (val)
  "Formata valor para exibição em tabelas e console."
  (cond
    ((numberp val) (itoa val))
    ((= (type val) 'STR) val)
    (t "-")))

;;; ----------------------------------------------------------------------------
;;; 3. PARSERS MODULARES
;;; ----------------------------------------------------------------------------

;; 3.1 Parser de Código de Poste
(defun lp-parse-poste (lines / item found upper len i ch all-digits)
  "Localiza e extrai o código do poste (ex: P112600B, P212600B, P01)."
  (setq found nil)
  (foreach item lines
    (if (not found)
      (progn
        (setq upper (strcase (lp-trim item)))
        (if (and (not (lp-is-noise-line upper))
                 (>= (strlen upper) 2)
                 (= (substr upper 1 1) "P"))
          (progn
            (setq ch (substr upper 2 1))
            ;; O segundo caractere deve ser dígito ou traço seguido de dígito
            (if (or (and (>= (ascii ch) 48) (<= (ascii ch) 57))
                    (= ch "-"))
              (setq found upper)))))))
  found)

;; 3.2 Parser de Ramais e Clientes
(defun lp-parse-phase-qty (token / up x-pos qty phase)
  "Extrai (quantidade fase) de um token como 12x1ø ou 1x3%%c."
  (setq up (strcase (lp-trim token)))
  (setq x-pos (vl-string-search "X" up))
  (if x-pos
    (progn
      (setq qty (atoi (substr up 1 x-pos)))
      (cond
        ((or (vl-string-search "3" (substr up (+ x-pos 2)))
             (vl-string-search "TRI" up))
         (setq phase 3))
        ((or (vl-string-search "2" (substr up (+ x-pos 2)))
             (vl-string-search "BI" up))
         (setq phase 2))
        (t
         (setq phase 1)))
      (if (> qty 0) (list qty phase) nil))
    nil))

(defun lp-parse-ramais-e-clientes (lines / ramais-found mono-qty bi-qty tri-qty
                                          ramal-str upper parts tokens token pq)
  "Extrai ramais normalizados, total de clientes e contagem por fase exclusivamente dos ramais."
  (setq mono-qty 0
        bi-qty 0
        tri-qty 0
        ramais-found '())

  (foreach line lines
    (setq upper (strcase (lp-trim line)))
    (if (not (lp-is-noise-line upper))
      (progn
        ;; Detecção de ramais por fase (ex: 12x1ø | 1x3ø ou 12x%%C1)
        (if (or (vl-string-search "X1" upper)
                (vl-string-search "X2" upper)
                (vl-string-search "X3" upper)
                (vl-string-search "Ø" upper)
                (vl-string-search "ø" line)
                (vl-string-search "%%C" upper))
          (progn
            ;; Divide tokens por separadores comuns: barra vertical, vírgula, mais
            (setq parts (vl-string-translate "|,+" "   " upper))
            (setq tokens (lp-split-lines (vl-string-translate " " "\n" parts)))
            (foreach token tokens
              (setq pq (lp-parse-phase-qty token))
              (if pq
                (cond
                  ((= (cadr pq) 1)
                   (setq mono-qty (+ mono-qty (car pq))))
                  ((= (cadr pq) 2)
                   (setq bi-qty (+ bi-qty (car pq))))
                  ((= (cadr pq) 3)
                   (setq tri-qty (+ tri-qty (car pq))))))))))))

  ;; Monta representação normalizada com %%C (ex: 12x%%C1 | 1x%%C3)
  (if (> mono-qty 0)
    (setq ramais-found (append ramais-found (list (strcat (itoa mono-qty) "x%%C1")))))
  (if (> bi-qty 0)
    (setq ramais-found (append ramais-found (list (strcat (itoa bi-qty) "x%%C2")))))
  (if (> tri-qty 0)
    (setq ramais-found (append ramais-found (list (strcat (itoa tri-qty) "x%%C3")))))

  (setq ramal-str "")
  (if ramais-found
    (progn
      (setq ramal-str (car ramais-found))
      (foreach item (cdr ramais-found)
        (setq ramal-str (strcat ramal-str " | " item)))))

  ;; Se não há ramais identificados, clientes é '-'
  (if (null ramais-found)
    (list "-" "-" 0 0 0)
    (list ramal-str (+ mono-qty bi-qty tri-qty) mono-qty bi-qty tri-qty)))

;; 3.3 Parser de Luminária
(defun lp-parse-luminaria (lines / lum upper)
  "Extrai identificação de luminária (ex: IP, LUM., LED, etc.) ou '-'."
  (setq lum "-")
  (foreach line lines
    (if (= lum "-")
      (progn
        (setq upper (strcase (lp-trim line)))
        (if (and (not (lp-is-noise-line upper))
                 (or (vl-string-search "IP" upper)
                     (vl-string-search "LUM" upper)
                     (vl-string-search "LED" upper)
                     (vl-string-search "PÉTALA" upper)
                     (vl-string-search "PETALA" upper)
                     (and (vl-string-search "W" upper)
                          (or (vl-string-search "70" upper)
                              (vl-string-search "100" upper)
                              (vl-string-search "150" upper)
                              (vl-string-search "250" upper)))))
          (setq lum (lp-trim line))))))
  lum)

;; 3.4 Parsers de Demanda e Demanda Acumulada
(defun lp-extract-value-after-key (text key / up pos len idx ch val has-digit)
  "Extrai o valor numérico após uma chave (ex: 'DEM' ou 'ACUM') preservando decimais."
  (setq up (strcase text)
        pos (vl-string-search key up))
  (if pos
    (progn
      (setq len (strlen text)
            idx (+ pos (strlen key) 1)
            val ""
            has-digit nil)
      ;; Pula caracteres separadores iniciais
      (while (and (<= idx len)
                  (member (substr up idx 1) '("." ":" " " "-" "=" "\t")))
        (setq idx (1+ idx)))
      ;; Coleta dígitos e separadores decimais (',' ou '.')
      (while (and (<= idx len)
                  (or (and (>= (ascii (substr text idx 1)) 48)
                           (<= (ascii (substr text idx 1)) 57))
                      (= (substr text idx 1) ",")
                      (= (substr text idx 1) ".")))
        (setq ch (substr text idx 1))
        (if (and (>= (ascii ch) 48) (<= (ascii ch) 57))
          (setq has-digit t))
        (setq val (strcat val ch)
              idx (1+ idx)))
      ;; Remove ponto ou vírgula no final se houver
      (while (and (> (strlen val) 0)
                  (or (= (substr val (strlen val) 1) ".")
                      (= (substr val (strlen val) 1) ",")))
        (setq val (substr val 1 (1- (strlen val)))))
      (if (and has-digit (> (strlen val) 0))
        val
        nil))
    nil))

(defun lp-extract-demanda-line (line / upper prefixes val prefix)
  "Tenta extrair valor de Demanda da linha."
  (setq upper (strcase (lp-trim line)))
  (setq prefixes '("DEMANDA" "DEM.:" "DEM:" "DEM." "DEM"))
  (setq val nil)
  (foreach prefix prefixes
    (if (and (null val) (vl-string-search prefix upper))
      (setq val (lp-extract-value-after-key line prefix))))
  val)

(defun lp-parse-demanda (lines / found-val ambig item candidate)
  "Extrai o valor de Demanda (kVA) preservando formato, ou '-' se ausente/ambíguo."
  (setq found-val nil
        ambig nil)
  (foreach item lines
    (setq candidate (lp-extract-demanda-line item))
    (if candidate
      (if (null found-val)
        (setq found-val candidate)
        (if (/= found-val candidate)
          (setq ambig t)))))
  (if (or (null found-val) ambig)
    "-"
    found-val))

(defun lp-extract-acumulada-line (line / upper prefixes val prefix)
  "Tenta extrair valor de Demanda Acumulada da linha."
  (setq upper (strcase (lp-trim line)))
  (setq prefixes '("ACUMULADA" "ACUMULADO" "ACUM.:" "ACUM:" "ACUM." "ACUM"))
  (setq val nil)
  (foreach prefix prefixes
    (if (and (null val) (vl-string-search prefix upper))
      (setq val (lp-extract-value-after-key line prefix))))
  val)

(defun lp-parse-acumulada (lines / found-val ambig item candidate)
  "Extrai o valor de Demanda Acumulada (kVA) preservando formato, ou '-' se ausente/ambíguo."
  (setq found-val nil
        ambig nil)
  (foreach item lines
    (setq candidate (lp-extract-acumulada-line item))
    (if candidate
      (if (null found-val)
        (setq found-val candidate)
        (if (/= found-val candidate)
          (setq ambig t)))))
  (if (or (null found-val) ambig)
    "-"
    found-val))

;; 3.5 Extrator de Coordenadas do Bloco CO
;; A rotina ADDBLOCO (topografia/addbloco.lsp) preenche exatamente os atributos
;; N e E do bloco CO como N=Y e E=X, já formatados com duas casas.  Esta rotina
;; reutiliza essa fonte persistida; nunca infere coordenadas pelo ponto local.
(defun lp-coord-numero-valido (value / clean normalized number index char dots digits valid)
  "Converte valor de atributo CO em número positivo, aceitando vírgula decimal."
  (setq clean (lp-trim value))
  (if (and (>= (strlen clean) 2)
           (or (= (strcase (substr clean 1 2)) "N:")
               (= (strcase (substr clean 1 2)) "E:")))
    (setq clean (lp-trim (substr clean 3))))
  (setq normalized (vl-string-translate "," "." clean)
        index 1
        dots 0
        digits 0
        valid (> (strlen normalized) 0))
  ;; ATOF aceita prefixos; por isso valida a string inteira antes de aceitá-la.
  (while (and valid (<= index (strlen normalized)))
    (setq char (substr normalized index 1))
    (cond
      ((and (= index 1) (or (= char "+") (= char "-"))))
      ((and (>= (ascii char) 48) (<= (ascii char) 57))
       (setq digits (1+ digits)))
      ((= char ".")
       (setq dots (1+ dots))
       (if (> dots 1) (setq valid nil)))
      (t (setq valid nil)))
    (setq index (1+ index)))
  (setq number (if valid (atof normalized) 0.0))
  (if (and valid (> digits 0) (> (abs number) 0.0001))
    number
    nil))

(defun lp-extrair-coordenadas-bloco (ent / edata tip obj has-atts atts-result atts-list tag val-n val-e n e)
  "Lê N/E do mecanismo CO; retorna '-' quando o bloco não traz coordenadas válidas."
  (if (or (null ent) (not (listp (setq edata (entget ent)))))
    "-"
    (progn
      (setq tip (cdr (assoc 0 edata)))
      (if (/= tip "INSERT")
        "-"
        (progn
          (setq val-n nil
                val-e nil)
          ;; O contrato real do CO é formado pelos atributos N e E de ADDBLOCO.
          (setq obj (vl-catch-all-apply 'vlax-ename->vla-object (list ent))
                has-atts nil)
          (if (not (vl-catch-all-error-p obj))
            (setq has-atts
              (vl-catch-all-apply 'vlax-get-property (list obj 'HasAttributes))))
          (if (and has-atts (not (vl-catch-all-error-p has-atts))
                   (= has-atts :vlax-true))
            (progn
              (setq atts-result (vl-catch-all-apply 'vlax-invoke (list obj 'GetAttributes)))
              (if (not (vl-catch-all-error-p atts-result))
                (progn
                  (setq atts-list (vlax-safearray->list (vlax-variant-value atts-result)))
                  (foreach att atts-list
                    (setq tag (strcase (vla-get-TagString att)))
                    (cond
                      ((= tag "N")
                       (setq val-n (lp-trim (vla-get-TextString att))))
                      ((= tag "E")
                       (setq val-e (lp-trim (vla-get-TextString att))))))))))
          (setq n (lp-coord-numero-valido val-n)
                e (lp-coord-numero-valido val-e))
          (if (and n e)
            (strcat "N: " (rtos n 2 2) "\nE: " (rtos e 2 2))
            "-"))))))

;;; ----------------------------------------------------------------------------
;;; 4. CÁLCULO DE POSIÇÕES E CAIXAS DE SERVIÇO (CS)
;;; ----------------------------------------------------------------------------

(defun lp-calc-posicoes (mono bi tri)
  "Calcula Total de Posições = (1ø * 1) + (2ø * 2) + (3ø * 3)."
  (if (and (= mono 0) (= bi 0) (= tri 0))
    "-"
    (+ (* mono 1) (* bi 2) (* tri 3))))

(defun lp-calc-cs (posicoes)
  "Calcula Total CS = teto(posicoes / 9)."
  (if (or (not (numberp posicoes)) (<= posicoes 0))
    "-"
    (/ (+ posicoes 8) 9)))

;;; ----------------------------------------------------------------------------
;;; 5. PROCESSAMENTO DE UM PONTO
;;; ----------------------------------------------------------------------------

(defun lp-process-point-texts (raw-texts-list seq coords / lines poste ram-res
                                                          ramais clientes mono bi tri
                                                          lum posicoes cs dem acum)
  "Consolida os textos brutos de um ponto e retorna o registro estruturado com coordenadas."
  (setq lines '())
  (foreach txt raw-texts-list
    (setq lines (append lines (lp-split-lines (lp-strip-mtext txt)))))

  (setq poste (lp-parse-poste lines))
  (if (null poste) (setq poste "-"))

  (setq ram-res (lp-parse-ramais-e-clientes lines))
  (setq ramais   (nth 0 ram-res)
        clientes (nth 1 ram-res)
        mono     (nth 2 ram-res)
        bi       (nth 3 ram-res)
        tri      (nth 4 ram-res))

  (setq lum (lp-parse-luminaria lines))
  (setq posicoes (lp-calc-posicoes mono bi tri))
  (setq cs (lp-calc-cs posicoes))
  (setq dem (lp-parse-demanda lines))
  (setq acum (lp-parse-acumulada lines))

  (if (or (null coords) (= coords ""))
    (setq coords "-"))

  (list (cons "SEQ" seq)
        (cons "POSTE" poste)
        (cons "RAMAIS" ramais)
        (cons "LUM" lum)
        (cons "CLIENTES" clientes)
        (cons "POSICOES" posicoes)
        (cons "CS" cs)
        (cons "DEMANDA" dem)
        (cons "ACUMULADA" acum)
        (cons "COORDENADAS" coords)
        (cons "RAW" raw-texts-list)))

;;; ----------------------------------------------------------------------------
;;; 6. PERSISTÊNCIA ISOLADA POR DWG (AutoCAD LData)
;;; ----------------------------------------------------------------------------

(setq *lp-dict-name* "OXCAD_LEVANTAMENTO")
(setq *lp-key-name*  "PONTOS")

(defun lp-db-obter-pontos (/ dados)
  "Lê os pontos armazenados no LData do DWG ativo."
  (setq dados (vlax-ldata-get *lp-dict-name* *lp-key-name*))
  (if (listp dados) dados '()))

(defun lp-db-salvar-pontos (pontos)
  "Salva a lista de pontos no LData do DWG ativo."
  (vlax-ldata-put *lp-dict-name* *lp-key-name* pontos))

(defun lp-db-limpar-pontos ()
  "Remove a lista de pontos do LData do DWG ativo."
  (vlax-ldata-delete *lp-dict-name* *lp-key-name*))

;;; ----------------------------------------------------------------------------
;;; 7. GERAÇÃO DA TABELA NATIVA DO AUTOCAD
;;; ----------------------------------------------------------------------------

(defun lp-gerar-tabela-cad (pontos / acad doc space pt row-count col-count table
                                    row-idx p seq poste ramais lum clientes pos cs
                                    dem acum coords table-res fill-res)
  "Insere a tabela nativa de 10 colunas no desenho ativo com proteção transacional."
  (if (or (null pontos) (= (length pontos) 0))
    (progn
      (princ "\n[LEVANTAR_POSTES] Nenhum ponto coletado para gerar tabela.")
      nil)
    (progn
      (setq pt (getpoint "\nPonto de inserção da tabela de postes e clientes: "))
      (if (null pt)
        (progn
          (princ "\n[LEVANTAR_POSTES] Inserção cancelada pelo usuário. Coleta mantida.")
          nil)
        (progn
          (setq acad (vlax-get-acad-object)
                doc  (vla-get-ActiveDocument acad)
                space (vla-get-Block (vla-get-ActiveLayout doc))
                row-count (+ 2 (length pontos))
                col-count 10)
          (setq table-res
            (vl-catch-all-apply
              'vla-AddTable
              (list space (vlax-3d-point pt) row-count col-count 6.0 35.0)))
          (if (vl-catch-all-error-p table-res)
            (progn
              (princ (strcat "\n[LEVANTAR_POSTES][ERRO] Falha ao criar tabela: "
                             (vl-catch-all-error-message table-res)))
              (princ "\n[LEVANTAR_POSTES] A coleta foi preservada no DWG.")
              nil)
            (progn
              (setq table table-res)
              (setq fill-res
                (vl-catch-all-apply
                  '(lambda ()
                     (vla-put-Layer table "0")
                     ;; Título mesclado (10 colunas: de 0 a 9)
                     (vla-MergeCells table 0 0 0 9)
                     (vla-SetText table 0 0 "LEVANTAMENTO DE POSTES E CLIENTES")

                     ;; Cabeçalhos (ordem normativa - 10 colunas)
                     (vla-SetText table 1 0 "PONTO")
                     (vla-SetText table 1 1 "POSTE")
                     (vla-SetText table 1 2 "RAMAIS")
                     (vla-SetText table 1 3 "LUMINÁRIA")
                     (vla-SetText table 1 4 "TOTAL CLIENTES")
                     (vla-SetText table 1 5 "TOTAL POSIÇÕES")
                     (vla-SetText table 1 6 "TOTAL CS")
                     (vla-SetText table 1 7 "DEMANDA (kVA)")
                     (vla-SetText table 1 8 "ACUMULADA (kVA)")
                     (vla-SetText table 1 9 "COORDENADAS")

                     ;; Larguras ajustadas
                     (vla-SetColumnWidth table 0 22.0)
                     (vla-SetColumnWidth table 1 35.0)
                     (vla-SetColumnWidth table 2 50.0)
                     (vla-SetColumnWidth table 3 35.0)
                     (vla-SetColumnWidth table 4 38.0)
                     (vla-SetColumnWidth table 5 38.0)
                     (vla-SetColumnWidth table 6 25.0)
                     (vla-SetColumnWidth table 7 38.0)
                     (vla-SetColumnWidth table 8 38.0)
                     (vla-SetColumnWidth table 9 45.0)

                     ;; Preenchimento das linhas
                     (setq row-idx 2)
                     (foreach p pontos
                       (vla-SetText table row-idx 0 (lp-format-val (cdr (assoc "SEQ" p))))
                       (vla-SetText table row-idx 1 (lp-format-val (cdr (assoc "POSTE" p))))
                       (vla-SetText table row-idx 2 (lp-format-val (cdr (assoc "RAMAIS" p))))
                       (vla-SetText table row-idx 3 (lp-format-val (cdr (assoc "LUM" p))))
                       (vla-SetText table row-idx 4 (lp-format-val (cdr (assoc "CLIENTES" p))))
                       (vla-SetText table row-idx 5 (lp-format-val (cdr (assoc "POSICOES" p))))
                       (vla-SetText table row-idx 6 (lp-format-val (cdr (assoc "CS" p))))
                       (vla-SetText table row-idx 7 (lp-format-val (cdr (assoc "DEMANDA" p))))
                       (vla-SetText table row-idx 8 (lp-format-val (cdr (assoc "ACUMULADA" p))))
                       (vla-SetText table row-idx 9 (lp-format-val (cdr (assoc "COORDENADAS" p))))
                       (setq row-idx (1+ row-idx)))

                     (vla-Update table))))
              (if (vl-catch-all-error-p fill-res)
                (progn
                  (princ (strcat "\n[LEVANTAR_POSTES][ERRO] Falha ao preencher células da tabela: "
                                 (vl-catch-all-error-message fill-res)))
                  (princ "\n[LEVANTAR_POSTES] A coleta foi preservada no DWG.")
                  nil)
                (progn
                  (princ (strcat "\n[LEVANTAR_POSTES] Tabela criada com sucesso com "
                                 (itoa (length pontos)) " pontos."))
                  t)))))))))

;;; ----------------------------------------------------------------------------
;;; 8. REVISÃO E MANIPULAÇÃO DA COLETA
;;; ----------------------------------------------------------------------------

(defun lp-exibir-revisao (pontos / p seq poste ramais lum clientes pos cs dem acum coords)
  (textscr)
  (princ "\n==================================================================================================================================")
  (princ "\n                                          REVISÃO DE PONTOS COLETADOS - OXCAD                                                     ")
  (princ "\n==================================================================================================================================")
  (princ "\n PONTO | POSTE      | RAMAIS               | LUMINÁRIA   | CLI | POS | CS | DEMANDA (kVA) | ACUMULADA (kVA) | COORDENADAS           ")
  (princ "\n----------------------------------------------------------------------------------------------------------------------------------")
  (foreach p pontos
    (setq seq      (lp-format-val (cdr (assoc "SEQ" p)))
          poste    (lp-format-val (cdr (assoc "POSTE" p)))
          ramais   (lp-format-val (cdr (assoc "RAMAIS" p)))
          lum      (lp-format-val (cdr (assoc "LUM" p)))
          clientes (lp-format-val (cdr (assoc "CLIENTES" p)))
          pos      (lp-format-val (cdr (assoc "POSICOES" p)))
          cs       (lp-format-val (cdr (assoc "CS" p)))
          dem      (lp-format-val (cdr (assoc "DEMANDA" p)))
          acum     (lp-format-val (cdr (assoc "ACUMULADA" p)))
          coords   (vl-string-translate "\n" " | " (lp-format-val (cdr (assoc "COORDENADAS" p)))))
    (princ (strcat "\n " seq
                   (substr "    " 1 (max 1 (- 5 (strlen seq))))
                   " | " poste
                   (substr "          " 1 (max 1 (- 10 (strlen poste))))
                   " | " ramais
                   (substr "                    " 1 (max 1 (- 20 (strlen ramais))))
                   " | " lum
                   (substr "           " 1 (max 1 (- 11 (strlen lum))))
                   " | " clientes
                   (substr "   " 1 (max 1 (- 3 (strlen clientes))))
                   " | " pos
                   (substr "   " 1 (max 1 (- 3 (strlen pos))))
                   " | " cs
                   (substr "  " 1 (max 1 (- 2 (strlen cs))))
                   " | " dem
                   (substr "             " 1 (max 1 (- 13 (strlen dem))))
                   " | " acum
                   (substr "              " 1 (max 1 (- 14 (strlen acum))))
                   " | " coords)))
  (princ "\n==================================================================================================================================\n")
  (graphscr))

(defun lp-verificar-duplicidade (pontos novo-poste / count ocorrencias)
  (setq count 0
        ocorrencias '())
  (if (and (/= novo-poste "-") (/= novo-poste ""))
    (foreach p pontos
      (if (= (strcase (cdr (assoc "POSTE" p))) (strcase novo-poste))
        (progn
          (setq count (1+ count))
          (setq ocorrencias (append ocorrencias (list (cdr (assoc "SEQ" p)))))))))
  ocorrencias)

;;; ----------------------------------------------------------------------------
;;; 9. COMANDO PRINCIPAL: LEVANTAR_POSTES (LP)
;;; ----------------------------------------------------------------------------

(defun c:LEVANTAR_POSTES (/ *error* old-pickadd pontos opt looping sel idx ent
                           raw-texts novo-ponto novo-poste dups table-ok sel-blk coords)
  (vl-load-com)

  (defun *error* (msg)
    (if (numberp old-pickadd) (setvar "PICKADD" old-pickadd))
    (if (and msg (/= msg "Function cancelled") (/= msg "quit / exit abort"))
      (princ (strcat "\n[LEVANTAR_POSTES][ERRO] " msg)))
    (princ "\n[LEVANTAR_POSTES] Operação finalizada. Coleta preservada no DWG.")
    (princ))

  (setq old-pickadd (getvar "PICKADD"))
  (setvar "PICKADD" 2)

  (setq pontos (lp-db-obter-pontos))
  (setq looping t)

  (while looping
    (setq pontos (lp-db-obter-pontos))
    (if (> (length pontos) 0)
      (progn
        (princ (strcat "\n[LEVANTAR_POSTES] " (itoa (length pontos))
                       " ponto(s) na coleta do desenho ativo."))
        (initget "Adicionar Revisar Excluir Gerar Limpar Sair")
        (setq opt (getkword "\nOpção [Adicionar/Revisar/Excluir/Gerar/Limpar/Sair] <Adicionar>: "))
        (if (null opt) (setq opt "Adicionar")))
      (setq opt "Adicionar"))

    (cond
      ;; OPÇÃO: ADICIONAR NOVO PONTO
      ((= opt "Adicionar")
       (princ (strcat "\nSelecione textos (TEXT/MTEXT) do Ponto "
                      (itoa (1+ (length pontos)))
                      " (Enter para voltar ao menu): "))
       (setq sel (ssget '((0 . "TEXT,MTEXT"))))
       (if sel
         (progn
           (setq raw-texts '()
                 idx 0)
           (repeat (sslength sel)
             (setq ent (ssname sel idx))
             (setq raw-texts (append raw-texts (list (cdr (assoc 1 (entget ent))))))
             (setq idx (1+ idx)))

           ;; Seleção opcional do bloco poste / bloco CO
           (setq sel-blk (entsel "\nSelecione o bloco do poste / bloco CO (Enter se não houver): "))
           (setq coords (lp-extrair-coordenadas-bloco (if sel-blk (car sel-blk) nil)))
           (if (= coords "-")
             (princ "\n[AVISO] Bloco de coordenadas não selecionado ou inválido. Registrado como ausente (-).")
             (princ (strcat "\n[COORDENADAS] " (vl-string-translate "\n" " | " coords))))

            (setq novo-ponto (lp-process-point-texts raw-texts (1+ (length pontos)) coords))
            ;; Mantém no LData a associação auditável entre o ponto e o bloco escolhido.
            (if sel-blk
              (setq novo-ponto
                (cons (cons "BLOCO_POSTE_HANDLE" (cdr (assoc 5 (entget (car sel-blk))))) novo-ponto)))
           (setq novo-poste (cdr (assoc "POSTE" novo-ponto)))

           ;; Detecção de duplicidade informativa
           (setq dups (lp-verificar-duplicidade pontos novo-poste))
           (if (> (length dups) 0)
             (princ (strcat "\n[AVISO] Poste " novo-poste " já coletado no(s) ponto(s): "
                            (vl-prin1-to-string dups)
                            ". Registrado como nova ocorrência.")))

           ;; Feedback resumido ao usuário
           (princ (strcat "\n[PONTO " (lp-format-val (cdr (assoc "SEQ" novo-ponto))) "]"
                          " Poste: " novo-poste
                          " | Ramais: " (lp-format-val (cdr (assoc "RAMAIS" novo-ponto)))
                          " | Lum: " (lp-format-val (cdr (assoc "LUM" novo-ponto)))
                          " | Clientes: " (lp-format-val (cdr (assoc "CLIENTES" novo-ponto)))
                          " | Posições: " (lp-format-val (cdr (assoc "POSICOES" novo-ponto)))
                          " | CS: " (lp-format-val (cdr (assoc "CS" novo-ponto)))
                          " | Dem: " (lp-format-val (cdr (assoc "DEMANDA" novo-ponto)))
                          " | Acum: " (lp-format-val (cdr (assoc "ACUMULADA" novo-ponto)))
                          " | Coords: " (vl-string-translate "\n" " " (lp-format-val (cdr (assoc "COORDENADAS" novo-ponto))))))

           (setq pontos (append pontos (list novo-ponto)))
           (lp-db-salvar-pontos pontos))
         (if (= (length pontos) 0)
           (setq looping nil))))

      ;; OPÇÃO: REVISAR PONTOS
      ((= opt "Revisar")
       (if (> (length pontos) 0)
         (lp-exibir-revisao pontos)
         (princ "\nNenhum ponto registrado para revisão.")))

      ;; OPÇÃO: EXCLUIR PONTO
      ((= opt "Excluir")
       (if (> (length pontos) 0)
         (progn
           (initget 6)
           (setq idx (getint (strcat "\nNúmero do ponto a excluir (1 a "
                                     (itoa (length pontos)) "): ")))
           (if (and idx (>= idx 1) (<= idx (length pontos)))
             (progn
               (setq pontos (vl-remove-if '(lambda (p) (= (cdr (assoc "SEQ" p)) idx)) pontos))
               ;; Reindexação estável
               (setq idx 1
                     pontos (mapcar '(lambda (p)
                                       (subst (cons "SEQ" idx) (assoc "SEQ" p) p))
                                    pontos))
               (lp-db-salvar-pontos pontos)
               (princ "\nPonto removido e sequência atualizada."))
             (princ "\nNúmero de ponto inválido.")))
         (princ "\nNenhum ponto para excluir.")))

      ;; OPÇÃO: GERAR TABELA
      ((= opt "Gerar")
       (if (> (length pontos) 0)
         (progn
           (setq table-ok (lp-gerar-tabela-cad pontos))
           (if table-ok
             (progn
               ;; Limpeza confirmada APENAS após sucesso
               (lp-db-limpar-pontos)
               (princ "\n[SUCESSO] Tabela gerada e memória do DWG limpa.")
               (setq looping nil))
             (princ "\nA tabela não foi criada. A coleta foi preservada.")))
         (princ "\nNenhum ponto para gerar tabela.")))

      ;; OPÇÃO: LIMPAR EXPLICITAMENTE
      ((= opt "Limpar")
       (initget "Sim Nao")
       (if (= (getkword "\nDeseja realmente descartar todos os pontos coletados? [Sim/Nao] <Nao>: ") "Sim")
         (progn
           (lp-db-limpar-pontos)
           (setq pontos '())
           (princ "\nColeta descartada com sucesso.")
           (setq looping nil))
         (princ "\nLimpeza cancelada.")))

      ;; OPÇÃO: SAIR / PAUSAR
      ((= opt "Sair")
       (princ "\nColeta mantida no DWG para continuação posterior.")
       (setq looping nil))))

  (if (numberp old-pickadd) (setvar "PICKADD" old-pickadd))
  (princ))

(defun c:LP () (c:LEVANTAR_POSTES))

(princ "\n[LEVANTAMENTO] Módulo de Postes carregado. Use LEVANTAR_POSTES ou LP.")
(princ)
