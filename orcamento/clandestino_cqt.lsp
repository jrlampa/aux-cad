;;; ============================================================================
;;; clandestino_cqt.lsp - Motor de Cálculo de CQT Previsto para Redes CLANDESTINO
;;; Fórmulas e Parâmetros Oficiais da Light S.A. (CQTS_ZNA853248_ATUAL.xlsx / DB)
;;; ============================================================================

(vl-load-com)

;;; 1. CONSTANTES ELÉTRICAS NORMATIVAS (LIGHT S.A.)
(setq *lp-cqt-v-trf*       220.0                ; Tensão de Linha Trifásica (V)
      *lp-cqt-v-mono*      127.01705922171767   ; T_LINHA_MONO = 220 / sqrt(3) (V)
      *lp-cqt-qt-mttr*     0.06714854379084968  ; Queda Inicial MT + Trafo (6.71485%)
      *lp-cqt-r7-sq-100*   484.0                ; (V_L^2) / 100 = (220^2) / 100
      *lp-cqt-v-base-tri*  0.381051177665153    ; (220 * sqrt(3)) / 1000 (kV)
      *lp-cqt-vao-padrao*  30.0)                ; Vão padrão quando sem coordenadas (m)

;;; 2. TABELA DE CONDUTORES (TABELA 'CABOS' DA ABA DB!A1:I32)
;;; Formato: (Nome Iz Resistência Reatância Alpha Divisor_R Temp_Lim Delta_T K_Term)
(setq *lp-clan-cabos* '(
  ("25 Al - Arm" 95.0 1.569300 0.103900 0.004030 1.241800 90.0 60.0 1.583333)
  ("50 Al - Arm" 150.0 0.838800 0.103900 0.004030 1.282100 90.0 60.0 2.500000)
  ("95 Al - Arm" 237.0 0.419700 0.098000 0.004030 1.282100 90.0 60.0 3.950000)
  ("150 Al - Arm" 300.0 0.266000 0.096000 0.004030 1.282100 90.0 60.0 5.000000)
  ("240 Al - Arm" 395.0 0.166500 0.085800 0.004030 1.282100 90.0 60.0 6.583333)
  ("25 Al" 90.0 1.569300 0.109000 0.004030 1.282100 90.0 60.0 1.500000)
  ("35 Cu" 140.0 0.688700 0.104800 0.003930 1.275100 90.0 60.0 2.333333)
  ("70 Cu" 240.0 0.352300 0.102400 0.003930 1.275100 90.0 60.0 4.000000)
  ("95 Al" 225.0 0.419500 0.095800 0.004030 1.282100 90.0 60.0 3.750000)
  ("120 Cu" 340.0 0.202300 0.097100 0.003930 1.275100 90.0 60.0 5.666667)
  ("240 Al" 476.0 0.166300 0.089700 0.004030 1.282100 90.0 60.0 7.933333)
  ("240 Cu" 430.0 0.103500 0.089700 0.003930 1.275100 90.0 60.0 7.166667)
  ("500 Cu" 700.0 0.056800 0.084900 0.003930 1.275100 90.0 60.0 11.666667)
  ("10 Cu_CONC_bi" 63.0 2.380102 0.101000 0.003930 1.275100 90.0 60.0 1.050000)
  ("10 Cu_CONC_Tri" 63.0 2.380102 0.101000 0.003930 1.275100 90.0 60.0 1.050000)
  ("16 Al_CONC_bi" 63.0 2.497787 0.085000 0.004030 1.282100 90.0 60.0 1.050000)
  ("16 Al_CONC_Tri" 63.0 2.497787 0.850000 0.004030 1.282100 90.0 60.0 1.050000)
  ("13 Al - DX" 63.0 2.665500 0.102200 0.004030 1.201500 70.0 40.0 1.575000)
  ("13 Al - TX" 63.0 2.665500 0.115800 0.004030 1.201500 70.0 40.0 1.575000)
  ("13 Al - QX" 63.0 2.665500 0.138400 0.004030 1.201500 70.0 40.0 1.575000)
  ("21 Al - QX" 63.0 1.677000 0.135000 0.004030 1.201500 70.0 40.0 1.575000)
  ("53 Al - QX" 63.0 0.664100 0.131100 0.004030 1.201500 70.0 40.0 1.575000)
  ("53 AA" 163.0 0.664100 0.131100 0.004030 1.282100 90.0 60.0 2.716667)
  ("70 Al - MX" 202.0 0.569700 0.126000 0.004030 1.282100 90.0 60.0 3.366667)
  ("185 Al - MX" 355.0 0.214900 0.117800 0.004030 1.282100 90.0 60.0 5.916667)
  ("240 Al - MX" 473.0 0.163000 0.090300 0.004030 1.282100 90.0 60.0 7.883333)
  ("6 AWG" 65.0 1.300000 0.090000 0.004030 1.282100 90.0 60.0 1.083333)
  ("2 AWG" 100.0 0.820000 0.085000 0.004030 1.282100 90.0 60.0 1.666667)
  ("1/0 AWG" 150.0 0.520000 0.080000 0.004030 1.282100 90.0 60.0 2.500000)
  ("3/0 AWG" 200.0 0.330000 0.078000 0.004030 1.282100 90.0 60.0 3.333333)
  ("4/0 AWG" 230.0 0.260000 0.075000 0.004030 1.282100 90.0 60.0 3.833333)
))

;;; 3. BUSCA E CONSULTA DE CONDUTORES (ALIASES E SELEÇÃO MANUAL)
(setq *lp-cqt-aliases-cabos*
  '(
    ("185AMX"     . "185 Al - MX")
    ("185 AMX"    . "185 Al - MX")
    ("185ALMX"    . "185 Al - MX")
    ("185 AL MX"  . "185 Al - MX")
    ("185-AL-MX"  . "185 Al - MX")
    ("185-AMX"    . "185 Al - MX")
    ("70AMX"      . "70 Al - MX")
    ("70 AMX"     . "70 Al - MX")
    ("70ALMX"     . "70 Al - MX")
    ("70 AL MX"   . "70 Al - MX")
    ("70-AL-MX"   . "70 Al - MX")
    ("70-AMX"     . "70 Al - MX")
    ("240AMX"     . "240 Al - MX")
    ("240 AMX"    . "240 Al - MX")
    ("240ALMX"    . "240 Al - MX")
    ("240 AL MX"  . "240 Al - MX")
    ("240CU"      . "240 Cu")
    ("240 CU"     . "240 Cu")
    ("240-CU"     . "240 Cu")
    ("240AL"      . "240 Al")
    ("240 AL"     . "240 Al")
    ("240-AL"     . "240 Al")
    ("53AA"       . "53 AA")
  ))

(defun lp-cqt-normalizar-nome-cabo (nome / clean)
  (if (or (null nome) (not (= (type nome) 'STR))) ""
    (strcase (vl-string-trim " \t\r\n" nome))))

(defun lp-cqt-resolver-cabo (nome contexto / n-up opt oficial)
  "Resolve o condutor a partir do texto no CAD, tratando aliases e ambiguidades (RAMAL vs BT)."
  (setq n-up (lp-cqt-normalizar-nome-cabo nome))
  (cond
    ;; Tratamento estrito do caso ambíguo: '53 Al - QX' vs '53 AA'
    ((or (= n-up "53 AL - QX") (= n-up "53ALQX") (= n-up "53 QX") (= n-up "53-AL-QX")
         (= n-up "53 AL") (= n-up "53AL") (= n-up "53"))
     (cond
       ;; Contexto de ramal: capacidade 63 A (Linha 23 da tabela DB)
       ((and contexto (or (= (strcase contexto) "RAMAL") (= (strcase contexto) "R")))
        "53 Al - QX")
       ;; Contexto de rede aérea BT: capacidade 163 A (Linha 24 da tabela DB)
       ((and contexto (or (= (strcase contexto) "BT") (= (strcase contexto) "REDE") (= (strcase contexto) "B")))
        "53 AA")
       ;; Sem contexto fornecido: solicita seleção manual interativa
       (t
        (princ (strcat "\n[CONDUTOR] Ambiguidade no condutor '" nome "':"))
        (initget "Ramal BT")
        (setq opt (getkword "\nSelecione a aplicação [Ramal (63A) / BT Rede (163A)] <BT>: "))
        (if (= opt "Ramal")
          "53 Al - QX"
          "53 AA"))))

    ;; Aliases diretos e inequívocos (ex: 185AMX -> 185 Al - MX)
    ((assoc n-up *lp-cqt-aliases-cabos*)
     (cdr (assoc n-up *lp-cqt-aliases-cabos*)))

    ;; Nome exato oficial na tabela DB
    ((assoc nome *lp-clan-cabos*)
     nome)

    ;; Busca por correspondência exata insensível a maiúsculas na tabela DB
    (t
     (setq oficial nil)
     (foreach item *lp-clan-cabos*
       (if (and (null oficial) (= n-up (lp-cqt-normalizar-nome-cabo (car item))))
         (setq oficial (car item))))
     (if oficial oficial nome))))

(defun lp-cqt-obter-cabo-contexto (nome contexto / resolvido n-res encontrado item)
  "Retorna o registro oficial completo da tabela DB para o condutor e contexto indicados."
  (setq resolvido (lp-cqt-resolver-cabo nome contexto)
        n-res (lp-cqt-normalizar-nome-cabo resolvido)
        encontrado nil)
  (foreach item *lp-clan-cabos*
    (if (null encontrado)
      (if (= n-res (lp-cqt-normalizar-nome-cabo (car item)))
        (setq encontrado item))))
  (if encontrado encontrado (assoc "70 Al - MX" *lp-clan-cabos*)))

(defun lp-cqt-obter-cabo (nome)
  "Retorna o registro oficial da tabela DB delegando para a resolução por aliases."
  (lp-cqt-obter-cabo-contexto nome nil))

;;; 4. SELEÇÃO DE CONDUTORES PREVISTOS (NORMA LIGHT S.A.)
(defun lp-cqt-selecionar-condutor (s-acum tr-p / ib)
  "Seleciona o condutor normativo previsto com base na ampacidade e posição."
  (if tr-p
    "240 Cu"
    (progn
      (setq ib (if (and s-acum (numberp s-acum) (> s-acum 0.0))
                 (/ (float s-acum) *lp-cqt-v-base-tri*)
                 0.0))
      (cond
        ((<= ib 202.0) "70 Al - MX")
        ((<= ib 355.0) "185 Al - MX")
        (t             "240 Al - MX")))))

;;; 5. CÁLCULO DE QUEDA DE TENSÃO POR TRECHO (FÓRMULA EXATA LIGHT)
(defun lp-cqt-calcular-trecho (s-acum comp cond-nome fase tr-p v-acum-ant /
                               cabo r-tab x alpha div-r t-lim dt k-term
                               mult-fase v-base t-regime r-20 r-corr z
                               qt-ponto v-acum qt-perc v-127)
  "Calcula os valores elétricos de um trecho segundo o modelo oficial da Light."
  (setq cabo (lp-cqt-obter-cabo cond-nome)
        s-acum (float (if (and s-acum (numberp s-acum)) s-acum 0.0))
        comp   (float (if (and comp (numberp comp) (> comp 0.0)) comp *lp-cqt-vao-padrao*))
        v-acum-ant (float (if (and v-acum-ant (numberp v-acum-ant)) v-acum-ant 0.0)))
  
  (setq r-tab   (nth 2 cabo)
        x       (nth 3 cabo)
        alpha   (nth 4 cabo)
        div-r   (nth 5 cabo)
        t-lim   (nth 6 cabo)
        dt      (nth 7 cabo)
        k-term  (nth 8 cabo))

  (setq mult-fase (cond ((= fase "MONO") 6.0) ((= fase "BIF") 2.0) (t 1.0))
        v-base    (cond ((= fase "MONO") (/ *lp-cqt-v-mono* 1000.0))
                        ((= fase "BIF")  (/ *lp-cqt-v-trf* 1000.0))
                        (t               *lp-cqt-v-base-tri*)))

  ;; 1. Temperatura em regime
  (setq t-regime (+ (/ s-acum (* v-base k-term)) 30.0))
  (if (> t-regime t-lim) (setq t-regime t-lim))

  ;; 2. Resistência corrigida e Impedância
  (setq r-20  (/ r-tab div-r)
        r-corr (* r-20 (+ 1.0 (* alpha (- t-regime 20.0))))
        z      (sqrt (+ (* r-corr r-corr) (* x x))))

  ;; 3. Queda de tensão no trecho (V)
  (setq qt-ponto (* mult-fase s-acum (/ z *lp-cqt-r7-sq-100*) comp (/ *lp-cqt-v-mono* 100.0)))
  (if tr-p
    (setq qt-ponto (+ qt-ponto (* *lp-cqt-v-mono* *lp-cqt-qt-mttr*))))

  ;; 4. Queda acumulada (V), percentual (%) e Tensão resultante (V)
  (setq v-acum   (+ v-acum-ant qt-ponto)
        qt-perc  (* (/ v-acum *lp-cqt-v-mono*) 100.0)
        v-127    (* *lp-cqt-v-mono* (- 1.0 (/ qt-perc 100.0))))

  (list (cons "QT_TRECHO_V" qt-ponto)
        (cons "V_ACUM" v-acum)
        (cons "QT_PERC" qt-perc)
        (cons "V_127" v-127)
        (cons "CONDUTOR" (car cabo))
        (cons "COMP" comp)
        (cons "T_REGIME" t-regime)))

;;; 6. PARSER DE COORDENADAS E DISTÂNCIA EUCLIDIANA ENTRE POSTES
(defun lp-cqt-extrair-numero-coord (s / pos)
  (if (or (null s) (not (= (type s) 'STR))) nil
    (progn
      (setq pos (vl-string-search ":" s))
      (if pos (setq s (substr s (+ pos 2))))
      (lp-parse-num s))))

(defun lp-cqt-parse-coords (coord-str / s lines x y)
  (if (or (null coord-str) (not (= (type coord-str) 'STR)) (= (lp-trim coord-str) "-") (= (lp-trim coord-str) ""))
    nil
    (progn
      (setq s (vl-string-translate "|" "\n" coord-str)
            lines (lp-split-lines s))
      (if (>= (length lines) 2)
        (progn
          (setq x (lp-cqt-extrair-numero-coord (car lines))
                y (lp-cqt-extrair-numero-coord (cadr lines)))
          (if (and x y) (list x y) nil))
        nil))))

(defun lp-cqt-distancia-pontos (p1 p2 / c1 c2 dx dy)
  (setq c1 (if p1 (lp-cqt-parse-coords (cdr (assoc "COORDENADAS" p1))) nil)
        c2 (if p2 (lp-cqt-parse-coords (cdr (assoc "COORDENADAS" p2))) nil))
  (if (and c1 c2)
    (progn
      (setq dx (- (car c2) (car c1)) dy (- (cadr c2) (cadr c1)))
      (sqrt (+ (* dx dx) (* dy dy))))
    *lp-cqt-vao-padrao*))

(defun lp-cqt-vao-estimado-p (p1 p2 / c1 c2)
  "Retorna T se o vão entre p1 e p2 é estimado por ausência de coordenadas em qualquer um dos postes."
  (setq c1 (if p1 (lp-cqt-parse-coords (cdr (assoc "COORDENADAS" p1))) nil)
        c2 (if p2 (lp-cqt-parse-coords (cdr (assoc "COORDENADAS" p2))) nil))
  (null (and c1 c2)))

;;; 7. MAPA MONTANTE A PARTIR DA TOPOLOGIA EXPLÍCITA
(defun lp-cqt-construir-mapa-montante (topologia / tr-raw tr-id lados derivs ramos mapa item nodes i pai filho u v)
  (setq mapa '() tr-id nil lados '() derivs '() ramos '())
  (if (and topologia (listp topologia))
    (progn
      (if (assoc "TR" topologia)
        (setq tr-raw (cdr (assoc "TR" topologia))
              tr-id (if (listp tr-raw) (car tr-raw) tr-raw)))
      (cond
        ((assoc "LADOS" topologia)
         (setq lados (cdr (assoc "LADOS" topologia))
               derivs (if (assoc "DERIVACOES" topologia) (cdr (assoc "DERIVACOES" topologia)) '())
               ramos (append lados derivs))
         (foreach item lados
           (if (listp item)
             (progn
               (setq nodes '())
               (foreach n item (if (and (= (type n) 'STR) (not (lp-clan-eh-rotulo-ramo-p n))) (setq nodes (append nodes (list (strcase (lp-trim n)))))))
               (if (and tr-id (> (length nodes) 0))
                 (setq mapa (cons (cons (car nodes) (strcase (lp-trim tr-id))) mapa)))))))
        ((assoc "TRECHOS" topologia)
         (setq ramos (cdr (assoc "TRECHOS" topologia))))
        (t (setq ramos topologia)))
      (foreach item ramos
        (cond
          ((and (listp item) (= (length item) 2) (= (type (car item)) 'STR) (= (type (cadr item)) 'STR)
                (not (lp-clan-eh-rotulo-ramo-p (car item))))
           (setq u (strcase (lp-trim (car item)))
                 v (strcase (lp-trim (cadr item))))
           (if (null (assoc v mapa))
             (setq mapa (cons (cons v u) mapa))))
          ((listp item)
           (setq nodes '())
           (foreach n item (if (and (= (type n) 'STR) (not (lp-clan-eh-rotulo-ramo-p n))) (setq nodes (append nodes (list (strcase (lp-trim n)))))))
           (setq i 0)
           (while (< i (1- (length nodes)))
             (setq pai (nth i nodes) filho (nth (1+ i) nodes))
             (if (null (assoc filho mapa))
               (setq mapa (cons (cons filho pai) mapa)))
             (setq i (1+ i))))))))
  mapa)

;;; 7.1 BUSCA E CONSULTA DE TRECHOS SALVOS (COMPRIMENTO E CONDUTOR)
(defun lp-cqt-obter-trechos-salvos (/ trs topo)
  "Retorna a lista de trechos salvos no LData ou na topologia ativa."
  (setq trs (vlax-ldata-get "OXCAD_LEVANTAMENTO" "TRECHOS"))
  (if (null trs)
    (progn
      (setq topo (lp-db-obter-topologia))
      (if (and topo (listp topo) (assoc "TRECHOS" topo))
        (setq trs (cdr (assoc "TRECHOS" topo))))))
  trs)

(defun lp-cqt-obter-trecho-dados (filho pai / trs item f-alvo p-alvo encontrado comp-val)
  "Busca os dados de comprimento e condutor de um vão cadastrado (filho para pai)."
  (setq trs (lp-cqt-obter-trechos-salvos)
        f-alvo (strcase (lp-trim filho))
        p-alvo (if (and pai (/= (lp-trim pai) "")) (strcase (lp-trim pai)) nil)
        encontrado nil)
  (foreach item trs
    (if (null encontrado)
      (cond
        ;; Formato lista simples: (filho pai comp condutor origem handle)
        ((and (listp item) (>= (length item) 4)
              (= (strcase (lp-trim (nth 0 item))) f-alvo)
              (or (null p-alvo) (= (strcase (lp-trim (nth 1 item))) p-alvo)))
         (setq comp-val (nth 2 item)
               comp-val (cond ((numberp comp-val) (float comp-val))
                              ((= (type comp-val) 'STR) (distof comp-val))
                              (t nil)))
         (setq encontrado (list (cons "FILHO" (nth 0 item))
                                (cons "PAI" (nth 1 item))
                                (cons "COMP" comp-val)
                                (cons "CONDUTOR" (nth 3 item))
                                (cons "ORIGEM" (if (> (length item) 4) (nth 4 item) "MANUAL"))
                                (cons "HANDLE" (if (> (length item) 5) (nth 5 item) nil)))))
        ;; Formato associacao (alist)
        ((and (listp item) (assoc "FILHO" item)
              (= (strcase (lp-trim (cdr (assoc "FILHO" item)))) f-alvo)
              (or (null p-alvo) (null (assoc "PAI" item))
                  (= (strcase (lp-trim (cdr (assoc "PAI" item)))) p-alvo)))
         (setq comp-val (cdr (assoc "COMP" item))
               comp-val (cond ((numberp comp-val) (float comp-val))
                              ((= (type comp-val) 'STR) (distof comp-val))
                              (t nil)))
         (setq encontrado (subst (cons "COMP" comp-val) (assoc "COMP" item) item))))))
  encontrado)

(defun lp-cqt-verificar-sobrecarga (cond-nome s-acum / cabo iz ib sobrecarga)
  "Verifica se a corrente Ib calculada supera a capacidade nominal Iz do condutor."
  (setq cabo (lp-cqt-obter-cabo cond-nome)
        iz (if cabo (nth 1 cabo) 0.0)
        ib (if (and s-acum (numberp s-acum) (> s-acum 0.0))
             (/ (float s-acum) *lp-cqt-v-base-tri*)
             0.0)
        sobrecarga (> ib iz))
  (list sobrecarga ib iz))

;;; 7.2 UTILITÁRIOS DE RÓTULOS, NÓS E CIRCUITOS
(defun lp-cqt-identificar-lado (poste raiz-id topo / lados derivs ramos achou r-nome n)
  "Identifica o lado/ramo topológico do poste (TRAFO, LADO 1, LADO 2, etc.)."
  (setq poste (strcase (lp-trim poste))
        raiz-id (if raiz-id (strcase (lp-trim raiz-id)) nil))
  (cond
    ((and raiz-id (= poste raiz-id)) "TRAFO")
    ((null topo) "LADO 1")
    (t
     (setq lados (if (assoc "LADOS" topo) (cdr (assoc "LADOS" topo)) '())
           derivs (if (assoc "DERIVACOES" topo) (cdr (assoc "DERIVACOES" topo)) '())
           ramos (append lados derivs)
           achou nil)
     (foreach r ramos
       (if (and (null achou) (listp r) (> (length r) 0))
         (progn
           (setq r-nome (car r))
           (foreach n (cdr r)
             (if (and (= (type n) 'STR) (= (strcase (lp-trim n)) poste))
               (setq achou r-nome))))))
     (if achou achou "LADO 1"))))

(defun lp-cqt-obter-montante-seq (poste raiz-id mapa-montante lookup-pts / m-nom m-ponto m-seq)
  "Retorna a sequência numérica do montante (0 para trafo, ou SEQ do poste pai)."
  (setq poste (strcase (lp-trim poste))
        raiz-id (if raiz-id (strcase (lp-trim raiz-id)) nil))
  (if (and raiz-id (= poste raiz-id))
    "0"
    (progn
      (setq m-nom (cdr (assoc poste mapa-montante)))
      (if (and m-nom (/= (lp-trim m-nom) ""))
        (progn
          (setq m-ponto (cdr (assoc (strcase (lp-trim m-nom)) lookup-pts)))
          (setq m-seq (if m-ponto (cdr (assoc "SEQ" m-ponto)) nil))
          (if m-seq (if (= (type m-seq) 'INT) (itoa m-seq) (vl-prin1-to-string m-seq)) "-"))
        "-"))))

(defun lp-cqt-obter-trecho-rotulo (poste raiz-id mapa-montante / m-nom)
  "Retorna o rótulo do vão (TR, P1 ou PAI, FILHO)."
  (setq poste (strcase (lp-trim poste))
        raiz-id (if raiz-id (strcase (lp-trim raiz-id)) nil))
  (if (and raiz-id (= poste raiz-id))
    (strcat "TR, " poste)
    (progn
      (setq m-nom (cdr (assoc poste mapa-montante)))
      (if (and m-nom (/= (lp-trim m-nom) ""))
        (strcat (strcase (lp-trim m-nom)) ", " poste)
        (strcat "-, " poste)))))

(defun _cqt-upsert (alist key val / pair)
  (setq pair (assoc key alist))
  (if pair
    (subst (cons key val) pair alist)
    (append alist (list (cons key val)))))

;;; 8. MOTOR DE CÁLCULO DE CQT PREVISTO PARA TODOS OS PONTOS DA REDE
(defun lp-cqt-calcular-rede-pontos (pontos / topo mapa-montante lookup-pts lookup-res tr-raw tr-id
                                             novos p poste pai p-pai s-acum comp cond-sel tr-p
                                             v-acum-ant res qt-trecho-v v-acum qt-perc v-127
                                             cond-nome c-previsto cqt-str ten-str status-cqt
                                             tem-vao-est sobrecarga raiz-id tr-up comp-str
                                             trecho-rotulo trecho-jusante lado-rotulo cli-acum
                                             cqt-no-ponto)
  "Calcula o CQT Previsto para todos os pontos e enriquece a lista com metadados."
  (if (or (null pontos) (= (length pontos) 0)) pontos
    (progn
      (setq topo (lp-db-obter-topologia)
            mapa-montante (lp-cqt-construir-mapa-montante topo)
            tr-raw (cond
                     ((and topo (listp topo) (assoc "TR" topo)) (cdr (assoc "TR" topo)))
                     ((vlax-ldata-get "OXCAD_LEVANTAMENTO" "TR_ID"))
                     (t nil))
            tr-id (if (listp tr-raw) (car tr-raw) (if tr-raw tr-raw "TR-01"))
            lookup-pts '()
            lookup-res '())
      (foreach p pontos
        (setq poste (strcase (lp-trim (cdr (assoc "POSTE" p)))))
        (setq lookup-pts (cons (cons poste p) lookup-pts)))
      
      (setq raiz-id nil)
      (if (and tr-id (/= (lp-trim tr-id) ""))
        (progn
          (setq tr-up (strcase (lp-trim tr-id)))
          (if (assoc tr-up lookup-pts)
            (setq raiz-id tr-up)
            (foreach item mapa-montante
              (if (and (null raiz-id)
                       (or (= (cdr item) tr-up)
                           (wcmatch (cdr item) "*TR*"))
                       (assoc (car item) lookup-pts))
                (setq raiz-id (car item)))))))
      (if (and (null raiz-id) (> (length pontos) 0))
        (setq raiz-id (strcase (lp-trim (cdr (assoc "POSTE" (car pontos)))))))

      (defun _obter-res-poste (nom-poste stack / p-cur m-nom m-res s-ac comp-m cond-nom
                                                 p-montante vao-est tr-dado chk sobrecarga
                                                 ib iz res)
        (setq nom-poste (strcase (lp-trim nom-poste)))
        (cond
          ((assoc nom-poste lookup-res)
           (cdr (assoc nom-poste lookup-res)))
          ((member nom-poste stack)
           (princ (strcat "\n[ERRO][TOPOLOGIA] Ciclo detectado envolvendo o poste " nom-poste "!"))
           (list (cons "STATUS_CQT" "ERRO: CICLO DETECTADO")
                 (cons "CONDUTOR" "-") (cons "COMP" 0.0)
                 (cons "QT_PERC" 0.0) (cons "V_127" 0.0)
                 (cons "VAO_ESTIMADO" t) (cons "SOBRECARGA" nil)))
          ((null (assoc nom-poste lookup-pts))
           nil)
          ((= nom-poste raiz-id)
           (setq p-cur (cdr (assoc nom-poste lookup-pts))
                 s-ac (lp-parse-num (cdr (assoc "ACUMULADA" p-cur)))
                 cond-nom "240 Cu"
                 comp-m 4.0
                 vao-est nil
                 chk (lp-cqt-verificar-sobrecarga cond-nom s-ac)
                 sobrecarga (car chk)
                 ib (cadr chk)
                 iz (caddr chk))
           (if sobrecarga
             (princ (strcat "\n[AVISO][SOBRECARGA] Trafo/Poste " nom-poste
                            ": Corrente total Ib=" (rtos ib 2 1)
                            "A excede a capacidade Iz=" (rtos iz 2 1)
                            "A do condutor interno " cond-nom "!")))
           (setq res (lp-cqt-calcular-trecho s-ac comp-m cond-nom "TRI" t 0.0))
           (setq res (append res (list (cons "VAO_ESTIMADO" vao-est)
                                       (cons "SOBRECARGA" sobrecarga)
                                       (cons "IB" ib)
                                       (cons "IZ" iz))))
           (setq lookup-res (cons (cons nom-poste res) lookup-res))
           res)
          (t
           (setq p-cur (cdr (assoc nom-poste lookup-pts))
                 m-nom (cdr (assoc nom-poste mapa-montante)))
           (cond
             ((or (null m-nom) (= (lp-trim m-nom) ""))
              (princ (strcat "\n[AVISO][TOPOLOGIA] Poste " nom-poste " desconectado do trafo."))
              (setq res (list (cons "STATUS_CQT" "ERRO: DESCONECTADO DO TRAFO")
                              (cons "CONDUTOR" "-") (cons "COMP" 0.0)
                              (cons "QT_PERC" 0.0) (cons "V_127" 0.0)
                              (cons "VAO_ESTIMADO" t) (cons "SOBRECARGA" nil)))
              (setq lookup-res (cons (cons nom-poste res) lookup-res))
              res)
             ((null (assoc m-nom lookup-pts))
              (princ (strcat "\n[AVISO][TOPOLOGIA] Poste " nom-poste " possui montante inexistente: " m-nom "."))
              (setq res (list (cons "STATUS_CQT" (strcat "ERRO: MONTANTE INEXISTENTE (" m-nom ")"))
                              (cons "CONDUTOR" "-") (cons "COMP" 0.0)
                              (cons "QT_PERC" 0.0) (cons "V_127" 0.0)
                              (cons "VAO_ESTIMADO" t) (cons "SOBRECARGA" nil)))
              (setq lookup-res (cons (cons nom-poste res) lookup-res))
              res)
             (t
              (setq m-res (_obter-res-poste m-nom (cons nom-poste stack)))
              (if (and m-res (cdr (assoc "STATUS_CQT" m-res))
                       (vl-string-search "ERRO" (cdr (assoc "STATUS_CQT" m-res))))
                (progn
                  (setq res (list (cons "STATUS_CQT" (cdr (assoc "STATUS_CQT" m-res)))
                                  (cons "CONDUTOR" "-") (cons "COMP" 0.0)
                                  (cons "QT_PERC" 0.0) (cons "V_127" 0.0)
                                  (cons "VAO_ESTIMADO" t) (cons "SOBRECARGA" nil)))
                  (setq lookup-res (cons (cons nom-poste res) lookup-res))
                  res)
                (progn
                  (setq s-ac (lp-parse-num (cdr (assoc "ACUMULADA" p-cur)))
                        p-montante (cdr (assoc m-nom lookup-pts))
                        tr-dado (lp-cqt-obter-trecho-dados nom-poste m-nom))
                  (setq comp-m (cond
                                 ((and tr-dado (assoc "COMP" tr-dado) (numberp (cdr (assoc "COMP" tr-dado)))
                                       (> (cdr (assoc "COMP" tr-dado)) 0.0))
                                  (cdr (assoc "COMP" tr-dado)))
                                 (p-montante
                                  (lp-cqt-distancia-pontos p-montante p-cur))
                                 (t *lp-cqt-vao-padrao*)))
                  (setq vao-est (cond
                                  ((and tr-dado (assoc "COMP" tr-dado) (numberp (cdr (assoc "COMP" tr-dado)))
                                        (> (cdr (assoc "COMP" tr-dado)) 0.0))
                                   nil)
                                  ((and m-res (cdr (assoc "VAO_ESTIMADO" m-res))) t)
                                  (p-montante
                                   (lp-cqt-vao-estimado-p p-montante p-cur))
                                  (t t)))
                  (setq cond-nom (cond
                                   ((and tr-dado (assoc "CONDUTOR" tr-dado)
                                         (= (type (cdr (assoc "CONDUTOR" tr-dado))) 'STR)
                                         (/= (strcase (lp-trim (cdr (assoc "CONDUTOR" tr-dado)))) "")
                                         (/= (strcase (lp-trim (cdr (assoc "CONDUTOR" tr-dado)))) "AUTO"))
                                    (lp-cqt-resolver-cabo (cdr (assoc "CONDUTOR" tr-dado)) "BT"))
                                   (t
                                    (lp-cqt-selecionar-condutor s-ac nil))))
                  (setq chk (lp-cqt-verificar-sobrecarga cond-nom s-ac)
                        sobrecarga (car chk)
                        ib (cadr chk)
                        iz (caddr chk))
                  (if sobrecarga
                    (princ (strcat "\n[AVISO][SOBRECARGA] Trecho " m-nom " -> " nom-poste
                                   ": Corrente Ib=" (rtos ib 2 1)
                                   "A excede a capacidade Iz=" (rtos iz 2 1)
                                   "A do condutor " cond-nom "!")))
                  (setq res (lp-cqt-calcular-trecho
                              s-ac comp-m cond-nom "TRI" nil
                              (if m-res (cdr (assoc "V_ACUM" m-res)) 0.0)))
                  (setq res (append res (list (cons "VAO_ESTIMADO" vao-est)
                                              (cons "SOBRECARGA" sobrecarga)
                                              (cons "IB" ib)
                                              (cons "IZ" iz))))
                  (setq lookup-res (cons (cons nom-poste res) lookup-res))
                  res)))))))

      (setq novos '() tem-vao-est nil)
      (foreach p pontos
        (setq poste (strcase (lp-trim (cdr (assoc "POSTE" p))))
              res (_obter-res-poste poste '()))
        (if res
          (progn
            (setq status-cqt (cdr (assoc "STATUS_CQT" res)))
            (if (and status-cqt (vl-string-search "ERRO" status-cqt))
              (setq cond-nome "-" cqt-str "- (ERRO)" ten-str "-" comp-str "-" cqt-no-ponto "- (ERRO)")
              (progn
                (setq cond-nome (cdr (assoc "CONDUTOR" res))
                      qt-perc   (cdr (assoc "QT_PERC" res))
                      v-127     (cdr (assoc "V_127" res))
                      comp      (cdr (assoc "COMP" res))
                      vao-est   (cdr (assoc "VAO_ESTIMADO" res))
                      sobrecarga (cdr (assoc "SOBRECARGA" res)))
                (if vao-est (setq tem-vao-est t))
                (setq comp-str  (if vao-est (strcat (rtos comp 2 1) " (EST)") (rtos comp 2 1))
                      cqt-str   (if vao-est (strcat (rtos qt-perc 2 2) "%*") (strcat (rtos qt-perc 2 2) "%"))
                      ten-str   (if vao-est (strcat (rtos v-127 2 2) " V*") (strcat (rtos v-127 2 2) " V"))
                      cqt-no-ponto (if (<= qt-perc 7.0001)
                                     (strcat "✔ " (rtos v-127 2 2))
                                     (strcat "✖ " (rtos v-127 2 2)))
                      status-cqt (cond
                                   ((and vao-est sobrecarga)
                                    "PREVISTO (VÃO ESTIMADO - PENDENTE CONFIRMAÇÃO) [SOBRECARGA]")
                                   (vao-est "PREVISTO (VÃO ESTIMADO - PENDENTE CONFIRMAÇÃO)")
                                   (sobrecarga "PREVISTO (COORDENADAS REAIS) [SOBRECARGA]")
                                   (t "PREVISTO (COORDENADAS REAIS)")))))
            
            (setq trecho-rotulo  (lp-cqt-obter-trecho-rotulo poste raiz-id mapa-montante)
                  trecho-jusante (lp-cqt-obter-montante-seq poste raiz-id mapa-montante lookup-pts)
                  lado-rotulo    (lp-cqt-identificar-lado poste raiz-id topo)
                  cli-acum       (if (assoc "CLIENTES_ACUMULADOS" p)
                                   (cdr (assoc "CLIENTES_ACUMULADOS" p))
                                   (cdr (assoc "CLIENTES" p))))
            
            (setq p (_cqt-upsert p "CONDUTOR_PREVISTO" cond-nome))
            (setq p (_cqt-upsert p "CQT_PREVISTO" cqt-str))
            (setq p (_cqt-upsert p "TENSAO_PREVISTA" ten-str))
            (setq p (_cqt-upsert p "COMPRIMENTO_VÃO" comp-str))
            (setq p (_cqt-upsert p "STATUS_CQT" status-cqt))
            (setq p (_cqt-upsert p "TRECHO" trecho-rotulo))
            (setq p (_cqt-upsert p "TRECHO_JUSANTE" trecho-jusante))
            (setq p (_cqt-upsert p "LADO" lado-rotulo))
            (setq p (_cqt-upsert p "CLT_ACUMULADO" cli-acum))
            (setq p (_cqt-upsert p "CQT_NO_PONTO" cqt-no-ponto))
            (setq novos (append novos (list p))))
          (setq novos (append novos (list p)))))
      (if tem-vao-est
        (princ "\n[AVISO][CQT] Rede possui vãos estimados (sem coordenadas CAD). Valores assinalados com '*'."))
      novos)))

;;; 9. INTEGRAÇÃO COM TABELAS DO CAD (ACAD_TABLE - 11 COLUNAS CQT)
(defun lp-cqt-colunas-adicionais-p ()
  "Verifica se o modo ativo é CLANDESTINO para acionar a tabela especializada CQT."
  (and (fboundp 'lp-db-obter-modo) (= (lp-db-obter-modo) "CLANDESTINO")))

(defun lp-cqt-obter-valores-linha (p)
  "Gera a lista com os 11 valores ordenados da linha CQT."
  (list (cdr (assoc "TRECHO" p))
        (cdr (assoc "SEQ" p))
        (cdr (assoc "TRECHO_JUSANTE" p))
        (cdr (assoc "COMPRIMENTO_VÃO" p))
        (cdr (assoc "CLIENTES" p))
        (cdr (assoc "CLT_ACUMULADO" p))
        (cdr (assoc "DEMANDA" p))
        (cdr (assoc "ACUMULADA" p))
        (cdr (assoc "LADO" p))
        (cdr (assoc "CONDUTOR_PREVISTO" p))
        (cdr (assoc "CQT_NO_PONTO" p))))

(defun lp-cqt-gerar-tabela-cad (pontos pt / acad doc space row-count col-count table
                                           row-idx p table-res fill-res headers widths col-idx)
  "Insere no DWG a tabela especializada de 11 colunas de CQT para o modo CLANDESTINO."
  (setq acad (vlax-get-acad-object)
        doc  (vla-get-ActiveDocument acad)
        space (vla-get-Block (vla-get-ActiveLayout doc))
        row-count (+ 2 (length pontos))
        col-count 11)
  (setq table-res
    (vl-catch-all-apply
      'vla-AddTable
      (list space (vlax-3d-point pt) row-count col-count 6.0 30.0)))
  (if (vl-catch-all-error-p table-res)
    (progn
      (princ (strcat "\n[LEVANTAR_POSTES][ERRO] Falha ao criar tabela CQT: "
                     (vl-catch-all-error-message table-res)))
      nil)
    (progn
      (setq table table-res)
      (setq fill-res
        (vl-catch-all-apply
          '(lambda ()
             (vla-put-Layer table "0")
             (vla-MergeCells table 0 0 0 10)
             (vla-SetText table 0 0 "CÁLCULO DE QUEDA DE TENSÃO - REDE BT (CLANDESTINO)")
             (setq headers '("TRECHO" "PONTO" "TRECHO jusante" "M" "CLIENTES" "CLT ACUMULAD" "TOTAL DO TRECHO" "ACUMULADA" "LADO" "CONDUTOR" "CQT NO PONTO")
                   widths  '(28.0 20.0 28.0 18.0 24.0 28.0 34.0 32.0 26.0 30.0 32.0)
                   col-idx 0)
             (mapcar '(lambda (h w)
                        (vla-SetText table 1 col-idx h)
                        (vla-SetColumnWidth table col-idx w)
                        (setq col-idx (1+ col-idx)))
                     headers widths)
             (setq row-idx 2)
             (foreach p pontos
               (setq col-idx 0)
               (foreach val (lp-cqt-obter-valores-linha p)
                 (vla-SetText table row-idx col-idx (lp-format-val val))
                 (setq col-idx (1+ col-idx)))
               (setq row-idx (1+ row-idx)))
             (vla-Update table))))
      (if (vl-catch-all-error-p fill-res)
        (progn
          (princ (strcat "\n[LEVANTAR_POSTES][ERRO] Falha ao preencher tabela CQT: "
                         (vl-catch-all-error-message fill-res)))
          nil)
        (progn
          (if (fboundp 'lp-db-salvar-tabela-handle)
            (lp-db-salvar-tabela-handle (vla-get-Handle table)))
          table)))))

(defun lp-cqt-atualizar-celulas-tabela (table pontos / row-idx rows-existentes rows-necessarias p col-idx)
  "Atualiza as células da tabela nativa CQT de 11 colunas existente no desenho."
  (setq rows-existentes (vla-get-Rows table)
        rows-necessarias (+ 2 (length pontos)))
  (if (> rows-necessarias rows-existentes)
    (vl-catch-all-apply 'vla-InsertRows
                        (list table rows-existentes 6.0 (- rows-necessarias rows-existentes))))
  (setq row-idx 2)
  (foreach p pontos
    (if (< row-idx (vla-get-Rows table))
      (progn
        (setq col-idx 0)
        (foreach val (lp-cqt-obter-valores-linha p)
          (vla-SetText table row-idx col-idx (lp-format-val val))
          (setq col-idx (1+ col-idx)))))
    (setq row-idx (1+ row-idx)))
  (vla-Update table)
  t)

;;; 10. EXPORTAÇÃO PARA PLANILHA EXCEL (.XLSX)
(defun lp-cqt-exportar-excel (pontos / json-path xlsx-path dwg-prefix dwg-name py-script cmd f i p)
  "Exporta os dados de CQT Clandestino para planilha Excel (.xlsx) formatada."
  (if (or (null pontos) (= (length pontos) 0))
    (progn (princ "\n[CQT_EXCEL] Nenhum ponto coletado para exportar.") nil)
    (progn
      (setq dwg-prefix (getvar "DWGPREFIX")
            dwg-name   (getvar "DWGNAME"))
      (if (or (null dwg-prefix) (= dwg-prefix "")) (setq dwg-prefix (getvar "TEMPPREFIX")))
      (if (or (null dwg-name) (= dwg-name "")) (setq dwg-name "CQT_LEVANTAMENTO"))
      (setq xlsx-path (strcat dwg-prefix "CQT_" (vl-filename-base dwg-name) ".xlsx")
            json-path (vl-filename-mktemp "cqt_pontos" (getvar "TEMPPREFIX") ".json"))
      
      (setq f (open json-path "w"))
      (if f
        (progn
          (write-line "[" f)
          (setq i 0)
          (foreach p pontos
            (write-line (strcat
              "  {\"SEQ\": " (vl-prin1-to-string (cdr (assoc "SEQ" p)))
              ", \"POSTE\": \"" (if (cdr (assoc "POSTE" p)) (cdr (assoc "POSTE" p)) "") "\""
              ", \"TRECHO\": \"" (if (cdr (assoc "TRECHO" p)) (cdr (assoc "TRECHO" p)) "") "\""
              ", \"TRECHO_JUSANTE\": \"" (if (cdr (assoc "TRECHO_JUSANTE" p)) (vl-prin1-to-string (cdr (assoc "TRECHO_JUSANTE" p))) "0") "\""
              ", \"COMPRIMENTO_VÃO\": \"" (if (cdr (assoc "COMPRIMENTO_VÃO" p)) (cdr (assoc "COMPRIMENTO_VÃO" p)) "30.0") "\""
              ", \"CLIENTES\": " (vl-prin1-to-string (if (cdr (assoc "CLIENTES" p)) (cdr (assoc "CLIENTES" p)) 0))
              ", \"CLT_ACUMULADO\": " (vl-prin1-to-string (if (cdr (assoc "CLT_ACUMULADO" p)) (cdr (assoc "CLT_ACUMULADO" p)) (if (cdr (assoc "CLIENTES_ACUMULADOS" p)) (cdr (assoc "CLIENTES_ACUMULADOS" p)) 0)))
              ", \"DEMANDA\": \"" (if (cdr (assoc "DEMANDA" p)) (cdr (assoc "DEMANDA" p)) "0,00") "\""
              ", \"ACUMULADA\": \"" (if (cdr (assoc "ACUMULADA" p)) (cdr (assoc "ACUMULADA" p)) "0,00") "\""
              ", \"LADO\": \"" (if (cdr (assoc "LADO" p)) (cdr (assoc "LADO" p)) "LADO 1") "\""
              ", \"CONDUTOR_PREVISTO\": \"" (if (cdr (assoc "CONDUTOR_PREVISTO" p)) (cdr (assoc "CONDUTOR_PREVISTO" p)) "70 Al - MX") "\""
              ", \"TENSAO_PREVISTA\": \"" (if (cdr (assoc "TENSAO_PREVISTA" p)) (cdr (assoc "TENSAO_PREVISTA" p)) "127.00 V") "\""
              ", \"CQT_PREVISTO\": \"" (if (cdr (assoc "CQT_PREVISTO" p)) (cdr (assoc "CQT_PREVISTO" p)) "0.00%") "\""
              ", \"STATUS_CQT\": \"" (if (cdr (assoc "STATUS_CQT" p)) (cdr (assoc "STATUS_CQT" p)) "") "\""
              ", \"CQT_NO_PONTO\": \"" (if (cdr (assoc "CQT_NO_PONTO" p)) (cdr (assoc "CQT_NO_PONTO" p)) "") "\""
              "}" (if (< (setq i (1+ i)) (length pontos)) "," "")) f))
          (write-line "]" f)
          (close f)

          (setq py-script (findfile "clandestino_excel.py"))
          (if (null py-script) (setq py-script (findfile "orcamento/clandestino_excel.py")))
          (if py-script
            (progn
              (setq cmd (strcat "python \"" py-script "\" --json \"" json-path "\" --out \"" xlsx-path "\" --open"))
              (startapp "cmd.exe" (strcat "/c " cmd))
              (princ (strcat "\n[SUCESSO][CQT_EXCEL] Planilha exportada para: " xlsx-path))
              xlsx-path)
            (progn
              (princ "\n[AVISO][CQT_EXCEL] Script clandestino_excel.py não localizado no search path.")
              nil)))
        (progn
          (princ "\n[ERRO][CQT_EXCEL] Não foi possível criar arquivo temporário de intercâmbio.")
          nil)))))

(defun c:LP_EXCEL ()
  (lp-cqt-exportar-excel (lp-recalcular-demandas-acumuladas (lp-db-obter-pontos))))

(defun c:CQT_EXCEL ()
  (lp-cqt-exportar-excel (lp-recalcular-demandas-acumuladas (lp-db-obter-pontos))))

