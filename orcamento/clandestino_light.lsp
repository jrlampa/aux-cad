;;; ============================================================================
;;; clandestino_light.lsp - Regras Normativas LIGHT para Redes Clandestinas
;;; Fonte: CQTS_ZNA853248_ATUAL.xlsx (Tabelas TAB_CLAN_DMDI e AUX_CLAN na aba DB)
;;; ============================================================================

(vl-load-com)
(if (null fboundp) (defun fboundp (s) (and s (boundp s) (member (type (eval s)) '(SUBR USUBR)))))
(if (null (fboundp 'lp-trim)) (defun lp-trim (v) (if (= (type v) 'STR) (vl-string-trim " \t\r\n{}" v) "")))

;;; 1. TABELAS NORMATIVAS LIGHT (DB!A36:B416 e DB!C36:E335)
(setq *lp-clan-dmdi-20-400* '(
  1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.62 1.64 1.68 1.72 1.75 1.79 1.81 1.85
  1.88 1.92 1.96 1.99 2.02 2.05 2.09 2.12 2.15 2.18 2.22 2.26 2.29 2.32 2.35 2.39 2.41 2.45 2.48 2.52 2.54 2.58 2.62 2.64 2.68 2.71 2.75 2.77 2.81 2.84
  2.87 2.90 2.94 2.96 3.00 3.04 3.06 3.10 3.13 3.16 3.19 3.23 3.25 3.29 3.31 3.35 3.38 3.41 3.44 3.48 3.50 3.54 3.56 3.60 3.64 3.66 3.70 3.72 3.76 3.79
  3.82 3.85 3.88 3.91 3.95 3.97 4.01 4.03 4.07 4.09 4.13 4.16 4.19 4.22 4.25 4.28 4.31 4.34 4.37 4.40 4.44 4.46 4.50 4.52 4.56 4.58 4.62 4.64 4.68 4.70
  4.74 4.76 4.80 4.82 4.86 4.90 4.92 4.96 4.98 5.02 5.04 5.08 5.10 5.14 5.16 5.20 5.22 5.26 5.28 5.32 5.34 5.38 5.40 5.44 5.46 5.48 5.52 5.54 5.58 5.60
  5.64 5.66 5.70 5.72 5.76 5.78 5.82 5.84 5.88 5.90 5.94 5.96 5.99 6.02 6.05 6.08 6.11 6.14 6.17 6.20 6.23 6.26 6.29 6.31 6.35 6.37 6.41 6.43 6.47 6.49
  6.52 6.55 6.58 6.61 6.64 6.67 6.70 6.72 6.76 6.78 6.82 6.84 6.88 6.90 6.92 6.96 6.98 7.02 7.04 7.07 7.10 7.13 7.16 7.19 7.21 7.25 7.27 7.31 7.33 7.36
  7.39 7.42 7.45 7.48 7.50 7.54 7.56 7.60 7.62 7.64 7.68 7.70 7.74 7.76 7.79 7.82 7.85 7.87 7.91 7.93 7.97 7.99 8.02 8.05 8.08 8.10 8.14 8.16 8.20 8.22
  8.24 8.28 8.30 8.33 8.36 8.39 8.41 8.45 8.47 8.51 8.53 8.56 8.59 8.62 8.64 8.68 8.70 8.72 8.76 8.78 8.81 8.84 8.87 8.89 8.93 8.95 8.99 9.01 9.04 9.07
  9.10 9.12 9.16 9.18 9.20 9.24 9.26 9.29 9.32 9.35 9.37 9.41 9.43 9.46 9.49 9.52 9.54 9.58 9.60 9.62 9.65 9.68 9.71 9.73 9.77 9.79 9.82 9.85 9.88 9.90
  9.94 9.96 9.98 10.02 10.04 10.07 10.10 10.13 10.15 10.18 10.21 10.24 10.26 10.30 10.32 10.34 10.38 10.40 10.43 10.46 10.49 10.51 10.54 10.57 10.60 10.62 10.66 10.68 10.70 10.74
  10.76 10.79 10.81 10.85 10.87 10.90 10.93 10.96 10.98 11.00 11.04 11.06 11.09 11.12 11.15 11.17 11.20 11.23 11.26 11.28 11.32 11.34 11.36 11.39 11.42 11.45 11.47 11.50 11.53 11.56
  11.58 11.62 11.64 11.66 11.69 11.72 11.75 11.77 11.80 11.83 11.86 11.88 11.92 11.94 11.96 11.99 12.02 12.05 12.07 12.10 12.13
))

(setq *lp-clan-fdiv-1-300* '(
  3.88 3.88 3.88 3.88 4.84 5.80 6.76 7.72 8.68 9.64 10.42 11.20 11.98 12.76 13.54 14.32 15.10 15.88 16.66 17.44 18.05 18.66 19.27 19.88 20.49 21.10 21.71 22.32 22.93 23.54
  24.14 24.74 25.34 25.94 26.54 27.14 27.74 28.34 28.94 29.54 30.14 30.74 31.34 31.94 32.54 33.10 33.66 34.22 34.78 35.34 35.90 36.46 37.02 37.58 38.14 38.70 39.26 39.82 40.38 40.94
  41.50 42.06 42.62 43.18 43.74 44.30 44.86 45.42 45.98 46.54 47.10 47.66 48.22 48.78 49.34 49.90 50.46 51.02 51.58 52.14 52.70 53.26 53.82 54.38 54.94 55.50 56.06 56.62 57.18 57.74
  58.30 58.86 59.42 59.98 60.54 61.10 61.66 62.22 62.78 63.34 63.59 63.84 64.09 64.34 64.59 64.84 65.09 65.34 65.59 65.84 66.09 66.34 66.59 66.84 67.09 67.34 67.59 67.84 68.09 68.34
  68.59 68.84 69.09 69.34 69.59 69.79 69.99 70.19 70.39 70.59 70.79 70.99 71.19 71.39 71.59 71.79 71.99 72.19 72.39 72.59 72.79 72.99 73.19 73.39 73.59 73.79 73.99 74.19 74.39 74.59
  74.74 74.89 75.04 75.19 75.34 75.49 75.64 75.79 75.94 76.09 76.24 76.39 76.54 76.69 76.84 76.99 77.14 77.29 77.44 77.59 77.74 77.89 78.04 78.19 78.34 78.44 78.54 78.64 78.74 78.84
  78.94 79.04 79.14 79.24 79.34 79.44 79.54 79.64 79.74 79.84 79.94 80.04 80.14 80.24 80.34 80.44 80.54 80.64 80.74 80.84 80.89 80.94 80.99 81.04 81.09 81.14 81.19 81.24 81.29 81.34
  81.39 81.44 81.49 81.54 81.59 81.64 81.69 81.74 81.79 81.84 81.89 81.94 81.99 82.04 82.09 82.12 82.15 82.18 82.21 82.24 82.27 82.30 82.33 82.36 82.39 82.42 82.45 82.48 82.50 82.52
  82.54 82.56 82.58 82.60 82.62 82.64 82.66 82.68 82.70 82.72 82.73 82.74 82.75 82.76 82.77 82.78 82.79 82.80 82.81 82.82 82.83 82.84 82.85 82.86 82.87 82.88 82.89 82.90 82.91 82.92
  82.93 82.94 82.95 82.96 82.97 82.98 82.99 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00 83.00
))

;;; 2. PERSISTÊNCIA DE CONFIGURAÇÃO E TOPOLOGIA (LData)
(setq *lp-clan-key-modo* "MODO" *lp-clan-key-area* "AREA_CLANDESTINO"
      *lp-clan-key-sentido* "SENTIDO_ACUMULACAO" *lp-clan-key-topologia* "TOPOLOGIA"
      *lp-clan-ultimo-erro* nil)

(defun lp-db-obter-modo (/ m) (if (setq m (vlax-ldata-get *lp-dict-name* *lp-clan-key-modo*)) m "NORMAL"))
(defun lp-db-salvar-modo (modo) (vlax-ldata-put *lp-dict-name* *lp-clan-key-modo* modo))
(defun lp-db-obter-area-raw (/ a) (vlax-ldata-get *lp-dict-name* *lp-clan-key-area*))
(defun lp-db-area-configurada-p (/ a) (setq a (lp-db-obter-area-raw)) (and a (numberp a) (lp-clan-inteiro-p a) (>= a 20) (<= a 400)))
(defun lp-db-obter-area (/ a) (setq a (lp-db-obter-area-raw)) (if (and a (numberp a) (lp-clan-inteiro-p a) (>= a 20) (<= a 400)) (fix a) 50))
(defun lp-db-salvar-area (area) (vlax-ldata-put *lp-dict-name* *lp-clan-key-area* (if (and area (numberp area) (lp-clan-inteiro-p area)) (fix area) 50)))
(defun lp-db-obter-sentido (/ s) (if (setq s (vlax-ldata-get *lp-dict-name* *lp-clan-key-sentido*)) s "PONTA->FONTE"))
(defun lp-db-salvar-sentido (sentido) (vlax-ldata-put *lp-dict-name* *lp-clan-key-sentido* sentido))
(defun lp-db-obter-topologia () (vlax-ldata-get *lp-dict-name* *lp-clan-key-topologia*))
(defun lp-db-salvar-topologia (topo)
  (if topo (vlax-ldata-put *lp-dict-name* *lp-clan-key-topologia* topo)
    (vlax-ldata-delete *lp-dict-name* *lp-clan-key-topologia*)))
(defun lp-clan-obter-ultimo-erro () *lp-clan-ultimo-erro*)

;;; 3. VALIDAÇÕES E FUNÇÕES PURAS DE CONSULTA E CÁLCULO
(defun lp-clan-inteiro-p (val)
  (and val (numberp val) (or (= (type val) 'INT) (= (float (fix val)) (float val)))))

(defun lp-clan-validar-area (area)
  (cond
    ((or (null area) (not (numberp area))) (princ "\n[ERRO][CLANDESTINO] Área não informada ou não numérica.") nil)
    ((not (lp-clan-inteiro-p area)) (princ (strcat "\n[ERRO][CLANDESTINO] Área decimal não suportada (" (vl-prin1-to-string area) " m²).")) nil)
    ((or (< area 20) (> area 400)) (princ (strcat "\n[ERRO][CLANDESTINO] Área fora da faixa LIGHT (" (vl-prin1-to-string area) " m²). Permitido: 20 a 400 m².")) nil)
    (t t)))

(defun lp-clan-obter-dmdi (area)
  (if (lp-clan-validar-area area) (nth (- (fix area) 20) *lp-clan-dmdi-20-400*) nil))

(defun lp-clan-validar-clientes (clientes)
  (cond
    ((or (null clientes) (not (numberp clientes))) (princ "\n[ERRO][CLANDESTINO] Clientes não informados.") nil)
    ((not (lp-clan-inteiro-p clientes)) (princ (strcat "\n[ERRO][CLANDESTINO] Clientes decimais não suportados (" (vl-prin1-to-string clientes) ").")) nil)
    ((< clientes 0) (princ (strcat "\n[ERRO][CLANDESTINO] Clientes negativos (" (vl-prin1-to-string clientes) ").")) nil)
    ((> clientes 300) (princ (strcat "\n[ERRO][CLANDESTINO] Clientes excedem limite AUX_CLAN (" (vl-prin1-to-string clientes) " > 300).")) nil)
    (t t)))

(defun lp-clan-obter-fator-div (clientes)
  (cond
    ((or (null clientes) (not (numberp clientes))) nil)
    ((and (lp-clan-inteiro-p clientes) (= (fix clientes) 0)) 0.0)
    ((lp-clan-validar-clientes clientes) (nth (1- (fix clientes)) *lp-clan-fdiv-1-300*))
    (t nil)))

(defun lp-clan-calcular-demanda (area clientes / dmdi fdiv)
  (setq dmdi (lp-clan-obter-dmdi area) fdiv (lp-clan-obter-fator-div clientes))
  (if (and dmdi fdiv) (* dmdi fdiv) nil))

(defun lp-clan-calcular-acumulada (area clientes-acumulados / dmdi fdiv)
  (setq dmdi (lp-clan-obter-dmdi area) fdiv (lp-clan-obter-fator-div clientes-acumulados))
  (if (and dmdi fdiv) (* dmdi fdiv) nil))

(defun lp-clan-format-num (num use-comma / s)
  (if (or (null num) (not (numberp num))) "-"
    (progn (setq s (rtos (float num) 2 2)) (if use-comma (vl-string-translate "." "," s) s))))

(defun lp-clan-parse-cli (c / n)
  (cond
    ((null c) 0) ((numberp c) (fix c))
    ((= (type c) 'STR) (setq n (distof c 2)) (if (null n) (setq n (distof c 1))) (if n (fix n) 0))
    (t 0)))

;;; 4. GRAFO TOPOLÓGICO DA REDE CLANDESTINA (INDEPENDÊNCIA DE ORDEM)
(defun lp-clan-eh-rotulo-ramo-p (s / up)
  (setq up (strcase (lp-trim s)))
  (or (= (substr up 1 4) "LADO") (= (substr up 1 4) "RAMO") (= (substr up 1 5) "DERIV")
      (= (substr up 1 8) "CIRCUITO") (= (substr up 1 6) "TRECHO") (= (substr up 1 3) "TR ")))

(defun lp-clan-adicionar-aresta (u v mapa / entry)
  (setq u (strcase (lp-trim u)) v (strcase (lp-trim v)))
  (if (or (= u "") (= v "") (= u v)) mapa
    (progn
      (setq entry (assoc u mapa))
      (if entry
        (if (not (member v (cdr entry))) (subst (append entry (list v)) entry mapa) mapa)
        (cons (list u v) mapa)))))

(defun lp-clan-construir-mapa-filhos (topologia pontos / mapa tr-raw tr-id lados derivs ramos item nodes n i u v poste jusante montante)
  (setq mapa '() tr-id nil lados '() derivs '() ramos '())
  (if (and topologia (listp topologia))
    (progn
      (if (assoc "TR" topologia)
        (setq tr-raw (cdr (assoc "TR" topologia)) tr-id (if (listp tr-raw) (car tr-raw) tr-raw)))
      (cond
        ((assoc "LADOS" topologia)
         (setq lados (cdr (assoc "LADOS" topologia))
               derivs (if (assoc "DERIVACOES" topologia) (cdr (assoc "DERIVACOES" topologia)) '())
               ramos (append lados derivs)))
        ((assoc "TRECHOS" topologia) (setq ramos (cdr (assoc "TRECHOS" topologia))))
        (t (setq ramos topologia)))
      (foreach item lados
        (if (listp item)
          (progn
            (setq nodes '())
            (foreach n item (if (and (= (type n) 'STR) (not (lp-clan-eh-rotulo-ramo-p n))) (setq nodes (append nodes (list n)))))
            (if (and tr-id (= (type tr-id) 'STR) (/= (lp-trim tr-id) "") (> (length nodes) 0))
              (setq mapa (lp-clan-adicionar-aresta tr-id (car nodes) mapa))))))
      (foreach item ramos
        (cond
          ((and (listp item) (= (length item) 2) (= (type (car item)) 'STR) (= (type (cadr item)) 'STR)
                (not (lp-clan-eh-rotulo-ramo-p (car item))))
           (setq mapa (lp-clan-adicionar-aresta (car item) (cadr item) mapa)))
          ((listp item)
           (setq nodes '())
           (foreach n item (if (and (= (type n) 'STR) (not (lp-clan-eh-rotulo-ramo-p n))) (setq nodes (append nodes (list n)))))
           (setq i 0)
           (while (< i (1- (length nodes)))
             (setq u (nth i nodes) v (nth (1+ i) nodes) mapa (lp-clan-adicionar-aresta u v mapa) i (1+ i))))))))
  (if pontos
    (foreach p pontos
      (setq poste (cdr (assoc "POSTE" p)))
      (if (and poste (/= poste "-") (/= poste ""))
        (progn
          (setq jusante (cdr (assoc "JUSANTE" p)))
          (if jusante
            (if (listp jusante) (foreach j jusante (setq mapa (lp-clan-adicionar-aresta poste j mapa)))
              (setq mapa (lp-clan-adicionar-aresta poste jusante mapa))))
          (setq montante (cdr (assoc "MONTANTE" p)))
          (if (and montante (/= montante "-") (/= montante ""))
            (setq mapa (lp-clan-adicionar-aresta montante poste mapa)))))))
  mapa)

(defun lp-clan-obter-jusante (poste mapa-filhos / visitados fila atual filhos)
  (setq visitados '() fila (cdr (assoc (strcase (lp-trim poste)) mapa-filhos)))
  (while (> (length fila) 0)
    (setq atual (car fila) fila (cdr fila))
    (if (not (member atual visitados))
      (progn
        (setq visitados (cons atual visitados) filhos (cdr (assoc atual mapa-filhos)))
        (if filhos (foreach f filhos (if (not (member f visitados)) (setq fila (cons f fila))))))))
  (reverse visitados))

(defun lp-clan-topologia-valida-p (topo / lados ok item nodes n)
  (if (or (null topo) (not (listp topo))) nil
    (if (assoc "LADOS" topo)
      (progn
        (setq lados (cdr (assoc "LADOS" topo)) ok nil)
        (foreach item lados
          (if (listp item)
            (progn
              (setq nodes '())
              (foreach n item (if (and (= (type n) 'STR) (not (lp-clan-eh-rotulo-ramo-p n))) (setq nodes (append nodes (list n)))))
              (if (> (length nodes) 0) (setq ok t)))))
        (and ok (> (length (lp-clan-construir-mapa-filhos topo nil)) 0)))
      (> (length (lp-clan-construir-mapa-filhos topo nil)) 0))))

(defun lp-clan-topologia-ativa-p () (lp-clan-topologia-valida-p (lp-db-obter-topologia)))

(defun lp-clan-resumo-topologia (topo / tr-raw tr lados derivs)
  (if (not (lp-clan-topologia-valida-p topo))
    "MODO LINEAR LEGADO [SEM TOPOLOGIA CADASTRADA]"
    (if (assoc "LADOS" topo)
      (progn
        (setq tr-raw (cdr (assoc "TR" topo)) tr (if (listp tr-raw) (car tr-raw) (if tr-raw tr-raw "-"))
              lados (cdr (assoc "LADOS" topo))
              derivs (if (assoc "DERIVACOES" topo) (cdr (assoc "DERIVACOES" topo)) '()))
        (strcat "TOPOLOGIA EXPLÍCITA ATIVA (TR: " tr " | Lados: " (itoa (length lados)) " | Derivações: " (itoa (length derivs)) ")"))
      "TOPOLOGIA EXPLÍCITA ATIVA")))

(defun lp-clan-status-modo-str (/ m a)
  (setq m (lp-db-obter-modo) a (lp-db-obter-area))
  (if (/= m "CLANDESTINO") "NORMAL"
    (strcat "CLANDESTINO | Área: " (itoa a) " m² | "
            (if (lp-clan-topologia-ativa-p)
              (lp-clan-resumo-topologia (lp-db-obter-topologia))
              (strcat "MODO LINEAR LEGADO (" (lp-db-obter-sentido) ") [SEM TOPOLOGIA CADASTRADA]")))))

;;; 5. RECÁLCULO TOPOLÓGICO TRANSACIONAL (FAIL-SAFE)
(defun lp-clan-atualizar-ponto-demandas (p dem-val acum-val)
  (setq p (if (assoc "DEMANDA" p)
            (subst (cons "DEMANDA" (lp-clan-format-num dem-val t)) (assoc "DEMANDA" p) p)
            (append p (list (cons "DEMANDA" (lp-clan-format-num dem-val t))))))
  (if (assoc "ACUMULADA" p)
    (subst (cons "ACUMULADA" (lp-clan-format-num acum-val t)) (assoc "ACUMULADA" p) p)
    (append p (list (cons "ACUMULADA" (lp-clan-format-num acum-val t))))))

(defun lp-clan-recalcular-pontos (pontos area sentido / topo mapa-filhos cli-lookup abort err-msg p poste cli
                                                        local-cli jusante-postes acum-cli j-cli dem-val acum-val
                                                        novos sentido-str pts-rev cli-map tot acum-tot)
  (setq *lp-clan-ultimo-erro* nil)
  (if (or (null pontos) (= (length pontos) 0)) pontos
    (if (not (lp-clan-validar-area area))
      (progn (setq *lp-clan-ultimo-erro* "Área residencial inválida ou fora da faixa de 20 a 400 m².") pontos)
      (progn
        (setq topo (if (and (listp sentido) (not (= (type sentido) 'STR))) sentido (lp-db-obter-topologia)))
        (setq mapa-filhos (lp-clan-construir-mapa-filhos topo pontos) abort nil err-msg nil cli-lookup '())
        (foreach p pontos
          (if (null abort)
            (progn
              (setq poste (strcase (lp-trim (cdr (assoc "POSTE" p)))) cli (lp-clan-parse-cli (cdr (assoc "CLIENTES" p))))
              (if (not (lp-clan-validar-clientes cli))
                (setq abort t err-msg (strcat "Poste " poste " possui clientes inválidos (" (vl-prin1-to-string (cdr (assoc "CLIENTES" p))) ").")))
              (setq cli-lookup (cons (cons poste cli) cli-lookup)))))
        (if abort
          (progn (setq *lp-clan-ultimo-erro* err-msg) (princ (strcat "\n[ERRO][CLANDESTINO] " err-msg " Dados preservados.")) pontos)
          (progn
            (setq novos '())
            (if (> (length mapa-filhos) 0)
              (progn
                (foreach p pontos
                  (if (null abort)
                    (progn
                      (setq poste (strcase (lp-trim (cdr (assoc "POSTE" p)))) local-cli (cdr (assoc poste cli-lookup))
                            jusante-postes (lp-clan-obter-jusante poste mapa-filhos) acum-cli (if local-cli local-cli 0))
                      (foreach j-nom jusante-postes
                        (setq j-cli (cdr (assoc j-nom cli-lookup))) (if j-cli (setq acum-cli (+ acum-cli j-cli))))
                      (if (> acum-cli 300)
                        (setq abort t err-msg (strcat "Poste " poste " atinge " (itoa acum-cli) " clientes acumulados (limite LIGHT: 300)."))))))
                (if abort
                  (progn (setq *lp-clan-ultimo-erro* err-msg) (princ (strcat "\n[ERRO][CLANDESTINO] " err-msg " Dados preservados.")) pontos)
                  (progn
                    (foreach p pontos
                      (setq poste (strcase (lp-trim (cdr (assoc "POSTE" p)))) local-cli (cdr (assoc poste cli-lookup))
                            jusante-postes (lp-clan-obter-jusante poste mapa-filhos) acum-cli (if local-cli local-cli 0))
                      (foreach j-nom jusante-postes
                        (setq j-cli (cdr (assoc j-nom cli-lookup))) (if j-cli (setq acum-cli (+ acum-cli j-cli))))
                      (setq dem-val (lp-clan-calcular-demanda area local-cli) acum-val (lp-clan-calcular-acumulada area acum-cli)
                            novos (append novos (list (lp-clan-atualizar-ponto-demandas p dem-val acum-val)))))
                    novos)))
              (progn
                (setq sentido-str (strcase (if (and sentido (= (type sentido) 'STR)) sentido "PONTA->FONTE")))
                (if (= sentido-str "TOPOLOGIA")
                  (progn
                    (setq *lp-clan-ultimo-erro* "Topologia explícita ausente ou inválida.")
                    (princ "\n[ERRO][CLANDESTINO] Topologia não cadastrada ou inválida. Dados preservados.")
                    pontos)
                  (if (= sentido-str "FONTE->PONTA")
                    (progn
                      (setq pts-rev (reverse pontos) cli-map '() tot 0)
                      (foreach p pts-rev
                        (setq cli (lp-clan-parse-cli (cdr (assoc "CLIENTES" p))) tot (+ tot cli))
                        (if (> tot 300) (setq abort t err-msg (strcat "Acumulação atinge " (itoa tot) " clientes (limite LIGHT: 300).")))
                        (setq cli-map (cons tot cli-map)))
                      (if abort
                        (progn (setq *lp-clan-ultimo-erro* err-msg) (princ (strcat "\n[ERRO][CLANDESTINO] " err-msg)) pontos)
                        (mapcar '(lambda (p acum-total)
                                   (setq cli (lp-clan-parse-cli (cdr (assoc "CLIENTES" p)))
                                         dem-val (lp-clan-calcular-demanda area cli)
                                         acum-val (lp-clan-calcular-acumulada area acum-total))
                                   (lp-clan-atualizar-ponto-demandas p dem-val acum-val))
                                pontos cli-map)))
                    (progn
                      (setq acum-tot 0)
                      (foreach p pontos
                        (if (null abort)
                          (progn
                            (setq cli (lp-clan-parse-cli (cdr (assoc "CLIENTES" p))) acum-tot (+ acum-tot cli))
                            (if (> acum-tot 300) (setq abort t err-msg (strcat "Acumulação atinge " (itoa acum-tot) " clientes (limite LIGHT: 300)."))))))
                      (if abort
                        (progn (setq *lp-clan-ultimo-erro* err-msg) (princ (strcat "\n[ERRO][CLANDESTINO] " err-msg)) pontos)
                        (progn
                          (setq acum-tot 0)
                          (foreach p pontos
                            (setq cli (lp-clan-parse-cli (cdr (assoc "CLIENTES" p))) acum-tot (+ acum-tot cli)
                                  dem-val (lp-clan-calcular-demanda area cli) acum-val (lp-clan-calcular-acumulada area acum-tot)
                                  novos (append novos (list (lp-clan-atualizar-ponto-demandas p dem-val acum-val)))))
                          novos)))))))))))))
