;;; =============================================================================
;;; tabelas_referencia.lsp - Biblioteca e Consulta de Tabelas Técnicas BT (AutoLISP)
;;; Tabelas Oficiais: Tabela 7 (Estruturas BT) e Tabela 9 (Condutores BT)
;;; Fonte: BASE.one (INFO DE PROJETO IMPORTANTE)
;;; Comandos: TABELAS, CONDUTORES_BT, ESTRUTURAS_BT
;;; =============================================================================

(vl-load-com)

;;; =============================================================================
;;; 1. BANCO DE DADOS EM MEMÓRIA - TABELA 9 (CONDUTORES DE BAIXA TENSÃO)
;;; Formato por item:
;;; (chave condutor fase neutro corrente_A tracao_daN diam_mm massa_kg_km r_ohm_km x_ohm_km)
;;; =============================================================================
(setq *TB-CONDUTORES-BT*
  '(
    ("3X150+1X80" "3x150+1x80" "3x150" "1x80"   326.0 554.0 51.0 1878.0 0.2775 0.0867)
    ("PR150"      "3x150+1x80" "3x150" "1x80"   326.0 554.0 51.0 1878.0 0.2775 0.0867)
    ("150"        "3x150+1x80" "3x150" "1x80"   326.0 554.0 51.0 1878.0 0.2775 0.0867)
    ("3X95+1X54.6" "3x95+1x54,6" "3x95" "1x54,6" 244.0 393.0 43.0 1270.0 0.4311 0.0902)
    ("PR95"       "3x95+1x54,6" "3x95" "1x54,6" 244.0 393.0 43.0 1270.0 0.4311 0.0902)
    ("95"         "3x95+1x54,6" "3x95" "1x54,6" 244.0 393.0 43.0 1270.0 0.4311 0.0902)
    ("3X50+1X54.6" "3x50+1x54,6" "3x50" "1x54,6" 169.0 260.0 37.0  765.0 0.8634 0.0943)
    ("PR50"       "3x50+1x54,6" "3x50" "1x54,6" 169.0 260.0 37.0  765.0 0.8634 0.0943)
    ("50"         "3x50+1x54,6" "3x50" "1x54,6" 169.0 260.0 37.0  765.0 0.8634 0.0943)
    ("3X35+1X54.6" "3x35+1x54,6" "3x35" "1x54,6" 136.0 235.0 37.0  700.0 1.1694 0.0974)
    ("PR35"       "3x35+1x54,6" "3x35" "1x54,6" 136.0 235.0 37.0  700.0 1.1694 0.0974)
    ("35"         "3x35+1x54,6" "3x35" "1x54,6" 136.0 235.0 37.0  700.0 1.1694 0.0974)
   )
)

;;; =============================================================================
;;; 2. BANCO DE DADOS EM MEMÓRIA - TABELA 7 (ESTRUTURAS DE BAIXA TENSÃO)
;;; Formato por item:
;;; (codigo_est nome neutro fase res_min_daN angulo fixacao)
;;; =============================================================================
(setq *TB-ESTRUTURAS-BT*
  '(
    ;; SI1 - Tangente
    ("SI1" "Tangente" "54,5" "1x35 ou 2x25" 300 "0° a 30°" "Conjunto de suspensão")
    ("SI1" "Tangente" "54,6" "3X35"         300 "0° a 30°" "Conjunto de suspensão")
    ("SI1" "Tangente" "54,6" "3X50"         300 "0° a 30°" "Conjunto de suspensão")
    ("SI1" "Tangente" "54,6" "3X95"         300 "0° a 30°" "Conjunto de suspensão")
    ("SI1" "Tangente" "80"   "3X150"        300 "0° a 30°" "Conjunto de suspensão")

    ;; SI1.AF - Tangente Afastamento
    ("SI1.AF" "Tangente Afastamento" "54,5" "1x35 ou 2x25" 300 "0° a 30°" "Conjunto de suspensão")
    ("SI1.AF" "Tangente Afastamento" "54,6" "3X35"         300 "0° a 30°" "Conjunto de suspensão")
    ("SI1.AF" "Tangente Afastamento" "54,6" "3X50"         300 "0° a 30°" "Conjunto de suspensão")
    ("SI1.AF" "Tangente Afastamento" "54,6" "3X95"         600 "0° a 30°" "Conjunto de suspensão")
    ("SI1.AF" "Tangente Afastamento" "80"   "3X150"        600 "0° a 30°" "Conjunto de suspensão")

    ;; SI1.2AF - Tangente Afastamento Duplo
    ("SI1.2AF" "Tangente Afastamento Duplo" "54,5" "1x35 ou 2x25" 300 "0° a 30°" "Conjunto de suspensão")
    ("SI1.2AF" "Tangente Afastamento Duplo" "54,6" "3X35"         300 "0° a 30°" "Conjunto de suspensão")
    ("SI1.2AF" "Tangente Afastamento Duplo" "54,6" "3X50"         300 "0° a 30°" "Conjunto de suspensão")
    ("SI1.2AF" "Tangente Afastamento Duplo" "54,6" "3X95"         600 "0° a 30°" "Conjunto de suspensão")
    ("SI1.2AF" "Tangente Afastamento Duplo" "80"   "3X150"        600 "0° a 30°" "Conjunto de suspensão")

    ;; SI1B.SI3 - Tangente com Derivação Oposta
    ("SI1B.SI3" "Tangente c/ Deriv. Oposta" "54,5" "1x35 ou 2x25" 300 "0°" "Conjunto de suspensão / Suporte de ancoragem")
    ("SI1B.SI3" "Tangente c/ Deriv. Oposta" "54,6" "3X35"         300 "0°" "Conjunto de suspensão / Suporte de ancoragem")
    ("SI1B.SI3" "Tangente c/ Deriv. Oposta" "54,6" "3X50"         300 "0°" "Conjunto de suspensão / Suporte de ancoragem")
    ("SI1B.SI3" "Tangente c/ Deriv. Oposta" "54,6" "3X95"         600 "0°" "Conjunto de suspensão / Suporte de ancoragem")
    ("SI1B.SI3" "Tangente c/ Deriv. Oposta" "80"   "3X150"        600 "0°" "Conjunto de suspensão / Suporte de ancoragem")

    ;; SI1A.SI3 - Tangente com Derivação do mesmo Lado
    ("SI1A.SI3" "Tangente c/ Deriv. Mesmo Lado" "54,5" "1x35 ou 2x25" 300 "0° a 30°" "Conjunto de suspensão / Suporte de ancoragem")
    ("SI1A.SI3" "Tangente c/ Deriv. Mesmo Lado" "54,6" "3X35"         300 "0° a 30°" "Conjunto de suspensão / Suporte de ancoragem")
    ("SI1A.SI3" "Tangente c/ Deriv. Mesmo Lado" "54,6" "3X50"         300 "0° a 30°" "Conjunto de suspensão / Suporte de ancoragem")
    ("SI1A.SI3" "Tangente c/ Deriv. Mesmo Lado" "54,6" "3X95"         600 "0° a 30°" "Conjunto de suspensão / Suporte de ancoragem")
    ("SI1A.SI3" "Tangente c/ Deriv. Mesmo Lado" "80"   "3X150"        600 "0° a 30°" "Conjunto de suspensão / Suporte de ancoragem")

    ;; SI1.SI4 - Tangente com duas derivações
    ("SI1.SI4" "Tangente c/ 2 Derivações" "54,5" "1x35 ou 2x25" 300 "0°" "Conjunto de suspensão / Suporte de ancoragem")
    ("SI1.SI4" "Tangente c/ 2 Derivações" "54,6" "3X35"         300 "0°" "Conjunto de suspensão / Suporte de ancoragem")
    ("SI1.SI4" "Tangente c/ 2 Derivações" "54,6" "3X50"         300 "0°" "Conjunto de suspensão / Suporte de ancoragem")
    ("SI1.SI4" "Tangente c/ 2 Derivações" "54,6" "3X95"         600 "0°" "Conjunto de suspensão / Suporte de ancoragem")
    ("SI1.SI4" "Tangente c/ 2 Derivações" "80"   "3X150"        600 "0°" "Conjunto de suspensão / Suporte de ancoragem")

    ;; SI3.S3 - Derivação em alinhamento com a Rede Aérea Nua
    ("SI3.S3" "Derivação Alinham. Rede Nua" "54,5" "1x35 ou 2x25" 300 "0°" "Suporte de ancoragem / isolador roldana")
    ("SI3.S3" "Derivação Alinham. Rede Nua" "54,6" "3X35"         300 "0°" "Suporte de ancoragem / isolador roldana")
    ("SI3.S3" "Derivação Alinham. Rede Nua" "54,6" "3X50"         300 "0°" "Suporte de ancoragem / isolador roldana")
    ("SI3.S3" "Derivação Alinham. Rede Nua" "54,6" "3X95"         600 "0°" "Suporte de ancoragem / isolador roldana")
    ("SI3.S3" "Derivação Alinham. Rede Nua" "80"   "3X150"        600 "0°" "Suporte de ancoragem / isolador roldana")

    ;; SI4.SI3 - Ancoragem Dupla com derivação
    ("SI4.SI3" "Ancoragem Dupla c/ Derivação" "54,5" "1x35 ou 2x25" 300 "0°" "Suporte de ancoragem / Isolador castanha")
    ("SI4.SI3" "Ancoragem Dupla c/ Derivação" "54,6" "3X35"         300 "0°" "Suporte de ancoragem / Isolador castanha")
    ("SI4.SI3" "Ancoragem Dupla c/ Derivação" "54,6" "3X50"         300 "0°" "Suporte de ancoragem / Isolador castanha")
    ("SI4.SI3" "Ancoragem Dupla c/ Derivação" "54,6" "3X95"         600 "0°" "Suporte de ancoragem / Isolador castanha")
    ("SI4.SI3" "Ancoragem Dupla c/ Derivação" "80"   "3X150"        600 "0°" "Suporte de ancoragem / Isolador castanha")

    ;; SI4 - Ancoragem Dupla
    ("SI4" "Ancoragem Dupla" "54,5" "1x35 ou 2x25" 300 "0°" "Suporte de ancoragem")
    ("SI4" "Ancoragem Dupla" "54,6" "3X35"         300 "0°" "Suporte de ancoragem")
    ("SI4" "Ancoragem Dupla" "54,6" "3X50"         300 "0°" "Suporte de ancoragem")
    ("SI4" "Ancoragem Dupla" "54,6" "3X95"         600 "0°" "Suporte de ancoragem")
    ("SI4" "Ancoragem Dupla" "80"   "3X150"        600 "0°" "Suporte de ancoragem")

    ;; SI3 - Ancoragem
    ("SI3" "Ancoragem" "54,5" "1x35 ou 2x25" 300 "30° a 90°" "Suporte de ancoragem")
    ("SI3" "Ancoragem" "54,6" "3X35"         300 "30° a 90°" "Suporte de ancoragem")
    ("SI3" "Ancoragem" "54,6" "3X50"         300 "30° a 90°" "Suporte de ancoragem")
    ("SI3" "Ancoragem" "54,6" "3X95"         600 "30° a 90°" "Suporte de ancoragem")
    ("SI3" "Ancoragem" "80"   "3X150"        600 "30° a 90°" "Suporte de ancoragem")

    ;; SI3.SI3 - Ancoragem dupla
    ("SI3.SI3" "Ancoragem Dupla Angular" "54,5" "1x35 ou 2x25" 300 "60° a 90°" "Suporte de ancoragem / isolador castanha")
    ("SI3.SI3" "Ancoragem Dupla Angular" "54,6" "3X35"         300 "60° a 90°" "Suporte de ancoragem / isolador castanha")
    ("SI3.SI3" "Ancoragem Dupla Angular" "54,6" "3X50"         300 "60° a 90°" "Suporte de ancoragem / isolador castanha")
    ("SI3.SI3" "Ancoragem Dupla Angular" "54,6" "3X95"         600 "60° a 90°" "Suporte de ancoragem / isolador castanha")
    ("SI3.SI3" "Ancoragem Dupla Angular" "80"   "3X150"        600 "60° a 90°" "Suporte de ancoragem / isolador castanha")

    ;; DERIV_VAO - Derivação no Vão da Rede Secundária
    ("DERIV_VAO" "Derivação no Vão" "54,5" "1x35 ou 2x25" nil "-" "-")
    ("DERIV_VAO" "Derivação no Vão" "54,6" "3X35"         nil "-" "-")
    ("DERIV_VAO" "Derivação no Vão" "54,6" "3X50"         nil "-" "-")
    ("DERIV_VAO" "Derivação no Vão" "54,6" "3X95"         nil "-" "-")
    ("DERIV_VAO" "Derivação no Vão" "80"   "3X150"        nil "-" "-")

    ;; FLYTAP - Cruzamento (flytap) - com Conexão
    ("FLYTAP" "Cruzamento (flytap)" "54,5" "1x35 ou 2x25" nil "-" "-")
    ("FLYTAP" "Cruzamento (flytap)" "54,6" "3X35"         nil "-" "-")
    ("FLYTAP" "Cruzamento (flytap)" "54,6" "3X50"         nil "-" "-")
    ("FLYTAP" "Cruzamento (flytap)" "54,6" "3X95"         nil "-" "-")
    ("FLYTAP" "Cruzamento (flytap)" "80"   "3X150"        nil "-" "-")
   )
)

;;; =============================================================================
;;; 3. FUNÇÕES UTILITÁRIAS DE ACESSO RÁPIDO (LISP API)
;;; =============================================================================

;; Limpa e padroniza string para busca
(defun tb-norm-str (str / s)
  (setq s (strcase (vl-string-trim " \t\r\n" str)))
  (while (vl-string-search "," s)
    (setq s (vl-string-subst "." "," s))
  )
  s
)

;; Busca condutor por string (ex: "3x150+1x80", "150", "95", "50", "35")
;; Retorna alist ou nil
(defun tb-get-condutor (chave / s res)
  (setq s (tb-norm-str chave))
  (if (and (> (strlen s) 2) (= (substr s 1 2) "PR"))
    (setq s (vl-string-trim " -_" (substr s 3)))
  )
  (if (and (> (strlen s) 2) (= (substr s 1 2) "BT"))
    (setq s (vl-string-trim " -_" (substr s 3)))
  )
  (foreach item *TB-CONDUTORES-BT*
    (if (and (not res)
             (or (= (car item) s)
                 (vl-string-search s (car item))
                 (vl-string-search s (nth 2 item))))
      (setq res
        (list
          (cons 'condutor  (nth 1 item))
          (cons 'fase      (nth 2 item))
          (cons 'neutro    (nth 3 item))
          (cons 'corrente  (nth 4 item))
          (cons 'tracao    (nth 5 item))
          (cons 'diametro  (nth 6 item))
          (cons 'massa     (nth 7 item))
          (cons 'r         (nth 8 item))
          (cons 'x         (nth 9 item))
        )
      )
    )
  )
  res
)

;; Retorna tração nominal em daN como número float (ex: 554.0) ou 0.0
(defun tb-get-tracao (chave / c)
  (setq c (tb-get-condutor chave))
  (if c (cdr (assoc 'tracao c)) 0.0)
)

;; Lista com os nomes oficiais dos condutores BT
(defun tb-list-condutores ()
  (mapcar '(lambda (x) (nth 1 x)) *TB-CONDUTORES-BT*)
)

;; Lista de códigos de estruturas BT disponíveis
(defun tb-list-estruturas (/ lista cod)
  (setq lista '())
  (foreach item *TB-ESTRUTURAS-BT*
    (setq cod (car item))
    (if (not (member cod lista))
      (setq lista (append lista (list cod)))
    )
  )
  lista
)

;; Busca detalhes de estrutura por código (ex: "SI1", "SI3") e fase (ex: "3X95", "3X150")
;; Retorna alist com os dados completos
(defun tb-get-estrutura (cod_est fase / cod_norm fase_norm res)
  (setq cod_norm (tb-norm-str cod_est))
  (setq fase_norm (if fase (tb-norm-str fase) ""))
  (foreach item *TB-ESTRUTURAS-BT*
    (if (and (not res)
             (= (tb-norm-str (car item)) cod_norm)
             (or (= fase_norm "") (vl-string-search fase_norm (tb-norm-str (nth 3 item)))))
      (setq res
        (list
          (cons 'codigo      (nth 0 item))
          (cons 'estrutura   (nth 1 item))
          (cons 'cabo_neutro (nth 2 item))
          (cons 'cabo_fase   (nth 3 item))
          (cons 'res_min_daN (nth 4 item))
          (cons 'angulo      (nth 5 item))
          (cons 'fixacao     (nth 6 item))
        )
      )
    )
  )
  res
)

;;; =============================================================================
;;; 4. COMANDOS INTERATIVOS NO AUTOCAD (TABELAS / CONDUTORES_BT / ESTRUTURAS_BT)
;;; =============================================================================

;;; =============================================================================
;;; 3. BANCO DE DADOS EM MEMÓRIA - ESFORÇOS CABOS MÉDIA TENSÃO (MT) E INTERPOLAÇÃO
;;; =============================================================================
(setq *TB-CABOS-MT*
  '(
    ("1/0CAA"    "1/0 CAA"     160.0  320.0  480.0  128.0)
    ("4/0CAA"    "4/0 CAA"     320.0  640.0  960.0  256.0)
    ("336.4CAA"  "336,4 CAA"   589.0 1178.0 1767.0  471.0)
    ("336CAA"    "336,4 CAA"   589.0 1178.0 1767.0  471.0)
    ("4CAA"      "4 CAA"        75.0  150.0  225.0   60.0)
    ("1/0CA"     "1/0 CA"      125.0  250.0  375.0  100.0)
    ("4/0CA"     "4/0 CA"      190.0  380.0  570.0  152.0)
    ("336.4CA"   "336,4 CA"    325.0  650.0  975.0  260.0)
    ("336CA"     "336,4 CA"    325.0  650.0  975.0  260.0)
    ("2CA"       "2 CA"         96.0  192.0  288.0   77.0)
    ("50XLPE"    "35/50 XLPE"  259.0  517.0  776.0   60.0)
    ("35XLPE"    "35/50 XLPE"  259.0  517.0  776.0   60.0)
    ("185XLPE"   "185 XLPE"    336.0  672.0 1008.0  100.0)
   )
)

;; Matriz de curvas de esforço MT por vão (daN para 3 fases)
(setq *TB-MT-CURVAS*
  '(
    ("1/0CAA"   ((20 375.0) (30 420.0) (40 480.0) (50 566.0) (60 653.0) (70 739.0) (80 825.0) (100 945.0) (120 1065.0) (150 1200.0) (200 1395.0)))
    ("4/0CAA"   ((20 540.0) (30 750.0) (40 960.0) (50 1133.0) (60 1307.0) (70 1480.0) (80 1653.0) (100 1805.0) (150 2118.0) (200 2352.0)))
    ("336CAA"   ((20 1167.0) (30 1467.0) (40 1767.0) (50 1982.0) (60 2198.0) (70 2413.0) (80 2628.0) (100 2867.0) (150 3420.0) (200 3885.0)))
    ("4CAA"     ((20 180.0) (30 203.0) (40 225.0) (50 270.0) (60 315.0) (70 360.0) (80 405.0) (100 465.0) (150 611.0) (200 747.0)))
    ("1/0CA"    ((20 330.0) (30 360.0) (40 375.0) (50 421.0) (60 467.0) (70 512.0) (80 558.0)))
    ("4/0CA"    ((20 465.0) (30 510.0) (40 570.0) (50 664.0) (60 758.0) (70 851.0) (80 945.0) (100 1125.0)))
    ("336CA"    ((20 738.0) (30 857.0) (40 975.0) (50 1094.0) (60 1212.0) (70 1331.0) (80 1449.0) (100 1683.0) (120 1917.0)))
    ("2CA"      ((20 228.0) (30 273.0) (40 288.0) (50 316.0) (60 344.0) (70 371.0) (80 399.0) (100 455.0)))
    ("50XLPE"   ((10 461.0) (20 563.0) (30 679.0) (40 776.0) (50 857.0) (60 926.0) (70 984.0) (80 1035.0)))
    ("35XLPE"   ((10 461.0) (20 563.0) (30 679.0) (40 776.0) (50 857.0) (60 926.0) (70 984.0) (80 1035.0)))
    ("185XLPE"  ((10 514.0) (20 706.0) (30 841.0) (40 1008.0) (50 1126.0) (60 1229.0) (70 1320.0) (80 1399.0)))
   )
)

;; Interpolação linear contínua e regra de 3 para cabos MT em função do vão
(defun tb-interpolar-mt (chave_cabo vao_m / s curva pontos p_min p_max p1 p2 v1 v2 f1 f2 res i p_prev)
  (setq s (tb-norm-str chave_cabo))
  (foreach item *TB-MT-CURVAS*
    (if (and (not curva)
             (or (= (car item) s)
                 (vl-string-search (car item) s)
                 (vl-string-search s (car item))))
      (setq curva item)
    )
  )
  (if (not curva)
    (setq res 0.0)
    (progn
      (setq pontos (cadr curva))
      (setq p_min (car pontos))
      (setq p_max (last pontos))
      (cond
        ;; Abaixo do vão mínimo: regra de 3 proporcional ao menor vão
        ((< vao_m (car p_min))
         (setq res (* (cadr p_min) (/ (max vao_m 1.0) (float (car p_min))))))
        ;; Acima do vão máximo: extrapolação linear baseada no último intervalo
        ((> vao_m (car p_max))
         (setq p_prev (nth (- (length pontos) 2) pontos))
         (setq res (+ (cadr p_max) (* (/ (- (cadr p_max) (cadr p_prev)) (float (- (car p_max) (car p_prev)))) (- vao_m (car p_max))))))
        ;; Interpolação linear entre os dois vãos adjacentes
        (t
         (setq i 0)
         (while (< i (1- (length pontos)))
           (setq p1 (nth i pontos) p2 (nth (1+ i) pontos))
           (if (and (<= (car p1) vao_m) (<= vao_m (car p2)))
             (progn
               (setq v1 (float (car p1)) v2 (float (car p2)))
               (setq f1 (cadr p1) f2 (cadr p2))
               (if (= v1 v2)
                 (setq res f1)
                 (setq res (+ f1 (* (/ (- vao_m v1) (- v2 v1)) (- f2 f1))))
               )
             )
           )
           (setq i (1+ i))
         )
        )
      )
    )
  )
  (if res (float res) 0.0)
)

;; Retorna tração em daN para MT (vão típico 40m se omitido)
(defun tb-get-tracao-mt (chave_cabo n_fases / s res val)
  (setq s (tb-norm-str chave_cabo))
  (foreach item *TB-CABOS-MT*
    (if (and (not res)
             (or (= (car item) s)
                 (vl-string-search s (car item))
                 (vl-string-search (car item) s)))
      (setq res item)
    )
  )
  (if res
    (cond
      ((= n_fases 1) (nth 2 res))
      ((= n_fases 2) (nth 3 res))
      ((= n_fases 4) (nth 5 res)) ;; neutro
      (t (nth 4 res))             ;; 3 fases padrão
    )
    0.0
  )
)

;; Retorna tração nominal em daN como número float (busca BT primeiro, depois MT)
(defun tb-get-tracao (chave / c val)
  (setq c (tb-get-condutor chave))
  (if c
    (cdr (assoc 'tracao c))
    (progn
      (setq val (tb-get-tracao-mt chave 3))
      (if (> val 0.0) val 0.0)
    )
  )
)

;; Separa string por delimitador
(defun tb-str-split (delim str / pos lst)
  (setq lst '())
  (while (setq pos (vl-string-search delim str))
    (setq lst (append lst (list (vl-string-trim " " (substr str 1 pos)))))
    (setq str (substr str (+ pos 1 (strlen delim))))
  )
  (if (> (strlen str) 0)
    (setq lst (append lst (list (vl-string-trim " " str))))
  )
  lst
)

;; Calcula esforço total para uma linha com vão medido (suporta MT, BT, Manual e MT + BT colineares)
(defun tb-calcular-linha-esforco (input vao_m / s partes sub_res total mt_tot bt_tot f_man f_mt f_bt desc_list)
  (setq s (strcase (vl-string-trim " \t\r\n" input)))
  (cond
    ((= s "")
     '((total . 0.0) (mt . 0.0) (bt . 0.0) (desc . "0 daN")))

    ;; Caso composto com '+' (ex: "1/0 + 150" ou "4/0CAA + PR95")
    ((vl-string-search "+" s)
     (setq partes (tb-str-split "+" s))
     (setq total 0.0 mt_tot 0.0 bt_tot 0.0 desc_list '())
     (foreach p partes
       (setq sub_res (tb-calcular-linha-esforco p vao_m))
       (setq total (+ total (cdr (assoc 'total sub_res))))
       (setq mt_tot (+ mt_tot (cdr (assoc 'mt sub_res))))
       (setq bt_tot (+ bt_tot (cdr (assoc 'bt sub_res))))
       (setq desc_list (append desc_list (list (cdr (assoc 'desc sub_res)))))
     )
     (list
       (cons 'total total)
       (cons 'mt mt_tot)
       (cons 'bt bt_tot)
       (cons 'desc (strcat (apply 'strcat (mapcar '(lambda (x) (strcat x " + ")) (reverse (cdr (reverse desc_list)))))
                           (last desc_list)
                           " = " (rtos total 2 0) " daN"))
     )
    )

    ;; Valor manual com 'd', 'dan' ou '='
    ((or (wcmatch s "*DAN") (wcmatch s "*D") (wcmatch s "=*"))
     (setq s (vl-string-subst "" "DAN" s))
     (setq s (vl-string-subst "" "D" s))
     (setq s (vl-string-subst "" "=" s))
     (setq f_man (distof s 2))
     (if (not f_man) (setq f_man 0.0))
     (list (cons 'total f_man) (cons 'mt 0.0) (cons 'bt 0.0) (cons 'desc (strcat "Manual " (rtos f_man 2 0) " daN")))
    )

    ;; Cabo de MT (1/0, 4/0, 336, 4CAA, XLPE etc.) com interpolação de vão
    ((or (wcmatch s "*CAA*") (wcmatch s "*XLPE*") (wcmatch s "*1/0*") (wcmatch s "*4/0*") (wcmatch s "*336*") (wcmatch s "*2CA*") (wcmatch s "*4CA*"))
     (setq f_mt (tb-interpolar-mt s vao_m))
     (if (<= f_mt 0.0) (setq f_mt (tb-get-tracao-mt s 3)))
     (list (cons 'total f_mt) (cons 'mt f_mt) (cons 'bt 0.0) (cons 'desc (strcat "MT " s " (" (rtos vao_m 2 0) "m: " (rtos f_mt 2 0) " daN)")))
    )

    ;; Cabo de BT (PR150, PR95, PR50, PR35, 150, 95, 50, 35)
    ((or (wcmatch s "PR*") (wcmatch s "*3X*") (member s '("150" "95" "50" "35")))
     (setq f_bt (tb-get-tracao s))
     (list (cons 'total f_bt) (cons 'mt 0.0) (cons 'bt f_bt) (cons 'desc (strcat "BT " s " (" (rtos f_bt 2 0) " daN)")))
    )

    ;; Valor numérico direto
    ((distof s 2)
     (setq f_man (distof s 2))
     (list (cons 'total f_man) (cons 'mt 0.0) (cons 'bt 0.0) (cons 'desc (strcat "Manual " (rtos f_man 2 0) " daN")))
    )

    (t
     '((total . 0.0) (mt . 0.0) (bt . 0.0) (desc . "Não identificado (0 daN)"))
    )
  )
)

;;; =============================================================================
;;; 4. COMANDOS INTERATIVOS NO AUTOCAD (TABELAS / CONDUTORES_BT / ESTRUTURAS_BT / CABOS_MT)
;;; =============================================================================

(defun c:CONDUTORES_BT ()
  (textscr)
  (princ "\n================================================================================")
  (princ "\n                   TABELA 9 - CONDUTORES DE BAIXA TENSÃO                        ")
  (princ "\n================================================================================")
  (princ "\n Condutor       | In(A) | Tração(daN) | Ø(mm) | Massa(kg/km) | R(Ω/km) | X(Ω/km)")
  (princ "\n----------------+-------+-------------+-------+--------------+---------+--------")
  (foreach item '(("3X150+1X80" "3x150+1x80" 326.0 554.0 51.0 1878.0 0.2775 0.0867)
                  ("3X95+1X54.6" "3x95+1x54,6" 244.0 393.0 43.0 1270.0 0.4311 0.0902)
                  ("3X50+1X54.6" "3x50+1x54,6" 169.0 260.0 37.0  765.0 0.8634 0.0943)
                  ("3X35+1X54.6" "3x35+1x54,6" 136.0 235.0 37.0  700.0 1.1694 0.0974))
    (princ (strcat "\n " (nth 1 item)
                   " | " (rtos (nth 2 item) 2 0) " A"
                   " | " (rtos (nth 3 item) 2 0) " daN"
                   " | " (rtos (nth 4 item) 2 0) " mm"
                   " | " (rtos (nth 5 item) 2 0) " kg/km"
                   " | " (rtos (nth 6 item) 2 4)
                   " | " (rtos (nth 7 item) 2 4)))
  )
  (princ "\n================================================================================")
  (princ)
)

(defun c:CABOS_MT ()
  (textscr)
  (princ "\n================================================================================")
  (princ "\n       ESFORÇOS DE CABOS DE MÉDIA TENSÃO - MT (daN para Vão de 40m)            ")
  (princ "\n================================================================================")
  (princ "\n Cabo MT       | 1 Fase (daN) | 2 Fases (daN) | 3 Fases (daN) | Neutro (daN)")
  (princ "\n---------------+--------------+---------------+---------------+--------------")
  (foreach item *TB-CABOS-MT*
    (princ (strcat "\n " (nth 1 item)
                   "     | " (rtos (nth 2 item) 2 0) " daN"
                   "      | " (rtos (nth 3 item) 2 0) " daN"
                   "      | " (rtos (nth 4 item) 2 0) " daN"
                   "      | " (rtos (nth 5 item) 2 0) " daN"))
  )
  (princ "\n================================================================================")
  (princ "\n* Fonte: Diretório CALC_ESF (Vão padrão de distribuição urbana: 40m)")
  (princ)
)

(defun c:ESTRUTURAS_BT (/ cod lista_cods res_lista)
  (textscr)
  (princ "\n================================================================================")
  (princ "\n                   TABELA 7 - ESTRUTURAS DE BAIXA TENSÃO                        ")
  (princ "\n================================================================================")
  (setq lista_cods (tb-list-estruturas))
  (princ (strcat "\nCódigos disponíveis: " (vl-string-trim " " (apply 'strcat (mapcar '(lambda (x) (strcat x " ")) lista_cods)))))
  (setq cod (getstring "\nDigite o código da estrutura para detalhar [ou Enter p/ todos]: "))
  (if (or (not cod) (= cod ""))
    (setq cod nil)
    (setq cod (tb-norm-str cod))
  )
  (princ "\n Cód.    | Fase / Neutro(mm²) | Res. Mín(daN) | Ângulo     | Fixação")
  (princ "\n---------+--------------------+---------------+------------+------------------------")
  (foreach item *TB-ESTRUTURAS-BT*
    (if (or (not cod) (= (tb-norm-str (car item)) cod))
      (princ (strcat "\n " (car item)
                     " | " (nth 3 item) " (N:" (nth 2 item) ")"
                     " | " (if (nth 4 item) (strcat (itoa (nth 4 item)) " daN") " -      ")
                     " | " (nth 5 item)
                     " | " (nth 6 item)))
    )
  )
  (princ "\n================================================================================")
  (princ)
)

(defun c:TABELAS (/ opc)
  (initget "Condutores Estruturas Cabos MT_Cabos BT_Condutores BT_Estruturas C E M 1 2 3 BT MT")
  (setq opc (getkword "\nConsultar Tabelas: [C]ondutores BT / [E]struturas BT / [M]T Cabos <C>: "))
  (cond
    ((or (= opc "M") (= opc "MT") (= opc "MT_Cabos") (= opc "Cabos") (= opc "3"))
     (c:CABOS_MT))
    ((or (= opc "E") (= opc "Estruturas") (= opc "BT_Estruturas") (= opc "2"))
     (c:ESTRUTURAS_BT))
    (t
     (c:CONDUTORES_BT))
  )
  (princ)
)

;; Aliases diretos para consulta imediata no AutoCAD
(defun c:BT () (c:CONDUTORES_BT))
(defun c:MT () (c:CABOS_MT))

(princ "\n[AUX CAD] Tabelas Técnicas BT/MT carregadas. Comandos: TABELAS, CONDUTORES_BT (ou BT), ESTRUTURAS_BT, CABOS_MT (ou MT)")
(princ)
