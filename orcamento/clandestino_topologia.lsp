;;; ============================================================================
;;; clandestino_topologia.lsp - Cadastro Interativo de Topologia da Rede Clandestina
;;; TR -> LADO 1..N -> DERIVAÇÕES, persistência no DWG e configuração do modo.
;;; Depende de: clandestino_light.lsp (cálculo) e levantamento_postes.lsp (parsers/LData)
;;; ============================================================================

(vl-load-com)

;;; 1. IDENTIFICAÇÃO DE NÓS (TR / POSTE) A PARTIR DE TEXTOS DO CAD
(defun lp-clan-is-ramal-p (line / up)
  (setq up (strcase (lp-trim line)))
  (or (vl-string-search "X1" up) (vl-string-search "X2" up) (vl-string-search "X3" up)
      (vl-string-search "%%C" up) (vl-string-search "Ø" up) (vl-string-search "ø" line)))

(defun lp-clan-parse-no-poste (lines / found l up)
  (setq found (lp-parse-poste lines))
  (if (and found (/= found "-")) found
    (progn
      (setq found nil)
      (foreach l lines
        (if (null found)
          (progn
            (setq up (strcase (lp-trim l)))
            (if (and (/= up "") (not (lp-is-noise-line up)) (not (lp-clan-is-ramal-p l))
                     (not (vl-string-search "LUMIN" up)) (not (vl-string-search "IP " up)))
              (setq found up)))))
      found)))

(defun lp-clan-parse-tr (lines / found l up)
  (setq found nil)
  (foreach l lines
    (if (null found)
      (progn
        (setq up (strcase (lp-trim l)))
        (if (and (/= up "") (not (lp-is-noise-line up)) (not (lp-clan-is-ramal-p l))
                 (or (vl-string-search "TR" up) (vl-string-search "TRAFO" up) (= (substr up 1 1) "T")))
          (setq found up)))))
  (if found found (lp-clan-parse-no-poste lines)))

(defun lp-clan-extrair-id-entidade (ent tipo-tr / edata tip raw lines nxt ndata)
  (if (null ent) nil
    (progn
      (setq edata (entget ent) tip (cdr (assoc 0 edata)) raw "")
      (cond
        ((member tip '("TEXT" "MTEXT" "ATTRIB"))
         (foreach par edata (if (member (car par) '(1 3)) (setq raw (strcat raw (cdr par))))))
        ((= tip "INSERT")
         (setq nxt (entnext ent))
         (while (and nxt (= (cdr (assoc 0 (setq ndata (entget nxt)))) "ATTRIB"))
           (setq raw (strcat raw "\n" (cdr (assoc 1 ndata))) nxt (entnext nxt)))))
      (setq lines (lp-split-lines (lp-strip-mtext raw)))
      (if tipo-tr (lp-clan-parse-tr lines) (lp-clan-parse-no-poste lines)))))

(defun lp-clan-selecionar-no-cad (prompt-msg tipo-tr / looping sel id)
  (setq looping t id nil)
  (while looping
    (setvar "ERRNO" 0)
    (setq sel (entsel prompt-msg))
    (cond
      (sel
       (setq id (lp-clan-extrair-id-entidade (car sel) tipo-tr))
       (if (and id (/= id "") (/= id "-")) (setq looping nil)
         (princ "\n[AVISO] Texto inválido. Selecione o texto identificador (TEXT/MTEXT).")))
      ((= (getvar "ERRNO") 7)
       (princ "\n[AVISO] Nenhum texto atingido pelo clique. Tente novamente (ou Enter para encerrar)."))
      (t (setq looping nil))))
  id)

(defun lp-clan-solicitar-poste-ponto (/ id dig)
  (setq id (lp-clan-selecionar-no-cad "\n[CLANDESTINO] Poste não detectado nos textos. Selecione o texto do Poste (Enter para digitar): " nil))
  (if (or (null id) (= id "-"))
    (progn
      (setq dig (strcase (lp-trim (getstring t "\nDigite o identificador do Poste (ex: P1): "))))
      (if (/= dig "") dig "-"))
    id))

;;; 2. COLETA DE RAMOS (LADOS E DERIVAÇÕES)
(defun lp-clan-coletar-sequencia-postes (nome-ramo no-origem / postes cont ord ant p-id)
  (princ (strcat "\n--- Cadastro de " nome-ramo " (partindo de " no-origem ") ---"))
  (setq postes '() cont t ord 1 ant no-origem)
  (while cont
    (setq p-id (lp-clan-selecionar-no-cad
                 (strcat "\nSelecione o texto do " (itoa ord) "º poste de " nome-ramo
                         " (após " ant ") [Enter para encerrar " nome-ramo "]: ") nil))
    (if p-id
      (if (or (= (strcase p-id) (strcase no-origem)) (member (strcase p-id) postes))
        (princ (strcat "\n[AVISO] Poste " p-id " já incluído neste ramo. Selecione o próximo poste a jusante."))
        (progn
          (setq postes (append postes (list (strcase p-id))) ant (strcase p-id) ord (1+ ord))
          (princ (strcat "\n  [" nome-ramo "] " no-origem " -> " (vl-prin1-to-string postes)))))
      (setq cont nil)))
  postes)

(defun lp-clan-no-existe-em-ramos-p (no tr-id lados derivs / alvo ok item n)
  (setq alvo (strcase (lp-trim no)) ok (and tr-id (= alvo (strcase (lp-trim tr-id)))))
  (foreach item (append lados derivs)
    (if (listp item)
      (foreach n item
        (if (and (= (type n) 'STR) (not (lp-clan-eh-rotulo-ramo-p n)) (= (strcase (lp-trim n)) alvo))
          (setq ok t)))))
  ok)

;;; 3. APLICAÇÃO TRANSACIONAL DA TOPOLOGIA (VALIDA -> RECALCULA -> PERSISTE)
(defun lp-clan-aplicar-topologia (nova-topo / area pontos recalc tbl)
  (if (not (lp-clan-topologia-valida-p nova-topo))
    (progn (princ "\n[ERRO][TOPOLOGIA] Topologia inválida ou vazia. Dados anteriores preservados.") nil)
    (progn
      (setq area (lp-db-obter-area) pontos (lp-db-obter-pontos) tbl (lp-db-obter-tabela-handle))
      (if (> (length pontos) 0)
        (progn
          (setq recalc (lp-clan-recalcular-pontos pontos area nova-topo))
          (if (lp-clan-obter-ultimo-erro)
            (progn (princ "\n[ERRO][TOPOLOGIA] Topologia rejeitada por exceder limites nos pontos. Dados preservados.") nil)
            (progn
              (lp-db-salvar-modo "CLANDESTINO")
              (if (not (lp-db-area-configurada-p)) (lp-db-salvar-area area))
              (lp-db-salvar-topologia nova-topo) (lp-db-salvar-sentido "TOPOLOGIA")
              (lp-db-salvar-pontos recalc)
              (if tbl (lp-sincronizar-levantamento recalc tbl))
              (princ (strcat "\n[SUCESSO] " (lp-clan-resumo-topologia nova-topo) " salva e demandas recalculadas!"))
              nova-topo)))
        (progn
          (lp-db-salvar-modo "CLANDESTINO")
          (if (not (lp-db-area-configurada-p)) (lp-db-salvar-area area))
          (lp-db-salvar-topologia nova-topo) (lp-db-salvar-sentido "TOPOLOGIA")
          (princ (strcat "\n[SUCESSO] " (lp-clan-resumo-topologia nova-topo) " salva no DWG!"))
          nova-topo)))))

;;; 4. EDITOR INTERATIVO (LADO / DERIVACAO / CONCLUIR / CANCELAR)
(defun lp-clan-executar-editor-topologia (tr-id lados derivs / editando op-t nome-l seq-l p-orig dig nome-d seq-d nova-topo res)
  (setq editando t res nil)
  (while editando
    (princ (strcat "\n[TOPOLOGIA EM EDIÇÃO] TR: " tr-id " | Lados: " (itoa (length lados)) " | Derivações: " (itoa (length derivs))))
    (initget "Lado Derivacao Concluir Cancelar")
    (setq op-t (getkword "\nTopologia [Lado/Derivacao/Concluir/Cancelar] <Concluir>: "))
    (if (null op-t) (setq op-t "Concluir"))
    (cond
      ((= op-t "Lado")
       (setq nome-l (strcat "LADO " (itoa (1+ (length lados)))) seq-l (lp-clan-coletar-sequencia-postes nome-l tr-id))
       (if (> (length seq-l) 0)
         (progn (setq lados (append lados (list (cons nome-l seq-l))))
                (princ (strcat "\n[OK] " nome-l " cadastrado com " (itoa (length seq-l)) " poste(s).")))
         (princ (strcat "\n[AVISO] " nome-l " sem postes não foi adicionado."))))
      ((= op-t "Derivacao")
       (setq p-orig (lp-clan-selecionar-no-cad "\nSelecione o texto do poste de ORIGEM da derivação (Enter para digitar): " nil))
       (if (null p-orig)
         (progn (setq dig (strcase (lp-trim (getstring t "\nCódigo do poste de ORIGEM da derivação (Enter para cancelar): "))))
                (if (/= dig "") (setq p-orig dig))))
       (if p-orig
         (if (not (lp-clan-no-existe-em-ramos-p p-orig tr-id lados derivs))
           (princ (strcat "\n[ERRO][TOPOLOGIA] O poste de origem '" p-orig "' não consta nos lados/derivações cadastrados."))
           (progn
             (setq nome-d (strcat "DERIVACAO " (itoa (1+ (length derivs))) " (" p-orig ")")
                   seq-d (lp-clan-coletar-sequencia-postes nome-d p-orig))
             (if (> (length seq-d) 0)
               (progn (setq derivs (append derivs (list (cons nome-d (cons p-orig seq-d)))))
                      (princ (strcat "\n[OK] Derivação partindo de " p-orig " cadastrada: " (vl-prin1-to-string seq-d))))
               (princ "\n[AVISO] Derivação sem postes a jusante não foi adicionada."))))))
      ((= op-t "Concluir")
       (setq nova-topo (list (cons "TR" tr-id) (cons "LADOS" lados) (cons "DERIVACOES" derivs)))
       (setq res (lp-clan-aplicar-topologia nova-topo) editando nil))
      ((= op-t "Cancelar")
       (princ "\n[TOPOLOGIA] Edição cancelada. Topologia e cálculos anteriores preservados.")
       (setq editando nil res nil))))
  res)

(defun lp-clan-iniciar-novo-cadastro-topologia (/ tr-id seq-l1)
  (setq tr-id (lp-clan-selecionar-no-cad "\nSelecione o texto identificador do Transformador (TR) no desenho (Enter para cancelar): " t))
  (if (null tr-id)
    (progn (princ "\n[AVISO] Seleção do TR cancelada. Topologia anterior preservada.") nil)
    (progn
      (princ (strcat "\n[TR IDENTIFICADO] " tr-id))
      (setq seq-l1 (lp-clan-coletar-sequencia-postes "LADO 1" tr-id))
      (if (= (length seq-l1) 0)
        (progn (princ "\n[AVISO] Nenhum poste cadastrado no LADO 1. Cadastro cancelado; dados preservados.") nil)
        (lp-clan-executar-editor-topologia tr-id (list (cons "LADO 1" seq-l1)) '())))))

(defun lp-clan-cadastrar-topologia (/ topo-atual acao tr-raw tr-id lados derivs)
  (princ "\n=== CADASTRO DE TOPOLOGIA DA REDE CLANDESTINA (TR / LADOS / DERIVAÇÕES) ===")
  (setq topo-atual (lp-db-obter-topologia))
  (if (lp-clan-topologia-valida-p topo-atual)
    (progn
      (princ (strcat "\n[TOPOLOGIA ATUAL] " (lp-clan-resumo-topologia topo-atual)))
      (initget "Manter Editar Recadastrar Cancelar")
      (setq acao (getkword "\nTopologia existente [Manter/Editar/Recadastrar/Cancelar] <Manter>: "))
      (if (null acao) (setq acao "Manter"))
      (cond
        ((= acao "Manter") (lp-clan-aplicar-topologia topo-atual))
        ((= acao "Editar")
         (setq tr-raw (cdr (assoc "TR" topo-atual)) tr-id (if (listp tr-raw) (car tr-raw) (if tr-raw tr-raw "TR-01"))
               lados (if (assoc "LADOS" topo-atual) (cdr (assoc "LADOS" topo-atual)) topo-atual)
               derivs (if (assoc "DERIVACOES" topo-atual) (cdr (assoc "DERIVACOES" topo-atual)) '()))
         (lp-clan-executar-editor-topologia tr-id lados derivs))
        ((= acao "Recadastrar") (lp-clan-iniciar-novo-cadastro-topologia))
        (t (princ "\n[TOPOLOGIA] Operação cancelada. Topologia mantida.") topo-atual)))
    (lp-clan-iniciar-novo-cadastro-topologia)))

;;; 5. CONFIGURAÇÃO DO MODO (MENU "Configurar" DO LEVANTAR_POSTES)
(defun lp-configurar-modo (/ cur-m cur-a cur-s opt nova-a opt-tipo opt-s novo-s old-topo pontos recalc tbl-handle)
  (setq cur-m (lp-db-obter-modo) cur-a (lp-db-obter-area) cur-s (lp-db-obter-sentido))
  (princ (strcat "\n--- CONFIGURAÇÃO DO LEVANTAMENTO ---\nStatus: " (lp-clan-status-modo-str)))
  (initget "Normal Clandestino Topologia Cancelar")
  (setq opt (getkword "\nSelecione a opção [Normal/Clandestino/Topologia/Cancelar] <Clandestino>: "))
  (if (null opt) (setq opt "Clandestino"))
  (cond
    ((= opt "Topologia")
     (if (not (lp-db-area-configurada-p)) (lp-db-salvar-area cur-a))
     (lp-clan-cadastrar-topologia))
    ((= opt "Normal")
     (lp-db-salvar-modo "NORMAL")
     (princ "\n[LEVANTAR_POSTES] Modo definido como NORMAL."))
    ((= opt "Clandestino")
     (initget 6)
     (setq nova-a (getint (strcat "\nÁrea média das residências em m² (20 a 400) <" (itoa cur-a) ">: ")))
     (if (null nova-a) (setq nova-a cur-a))
     (if (lp-clan-validar-area nova-a)
       (progn
         (initget "Topologia Linear Cancelar")
         (setq opt-tipo (getkword "\nModo de acumulação da rede clandestina [Topologia/Linear/Cancelar] <Topologia>: "))
         (if (null opt-tipo) (setq opt-tipo "Topologia"))
         (cond
           ((= opt-tipo "Topologia")
            (lp-db-salvar-modo "CLANDESTINO") (lp-db-salvar-area nova-a)
            (lp-clan-cadastrar-topologia))
           ((= opt-tipo "Linear")
            (initget "Ponta Fonte")
            (setq opt-s (getkword (strcat "\nSentido linear legado [Ponta->Fonte / Fonte->Ponta] <"
                                          (if (= cur-s "FONTE->PONTA") "Fonte" "Ponta") ">: ")))
            (if (null opt-s) (setq opt-s (if (= cur-s "FONTE->PONTA") "Fonte" "Ponta")))
            (setq novo-s (if (= opt-s "Fonte") "FONTE->PONTA" "PONTA->FONTE")
                  old-topo (lp-db-obter-topologia)
                  pontos (lp-db-obter-pontos) tbl-handle (lp-db-obter-tabela-handle))
            (lp-db-salvar-topologia nil)
            (if (> (length pontos) 0)
              (progn
                (setq recalc (lp-clan-recalcular-pontos pontos nova-a novo-s))
                (if (lp-clan-obter-ultimo-erro)
                  (progn (lp-db-salvar-topologia old-topo)
                         (princ "\n[ERRO] Configuração não aplicada pois os pontos excedem limites normativos."))
                  (progn
                    (lp-db-salvar-modo "CLANDESTINO") (lp-db-salvar-area nova-a)
                    (lp-db-salvar-sentido novo-s) (lp-db-salvar-pontos recalc)
                    (if tbl-handle (lp-sincronizar-levantamento recalc tbl-handle))
                    (princ (strcat "\n[LEVANTAR_POSTES] Modo CLANDESTINO LINEAR LEGADO configurado: " (itoa nova-a) " m² | " novo-s ".")))))
              (progn
                (lp-db-salvar-modo "CLANDESTINO") (lp-db-salvar-area nova-a) (lp-db-salvar-sentido novo-s)
                (princ (strcat "\n[LEVANTAR_POSTES] Modo CLANDESTINO LINEAR LEGADO configurado: " (itoa nova-a) " m² | " novo-s ".")))))
           (t (princ "\nConfiguração cancelada; dados anteriores preservados."))))
       (princ "\n[AVISO] Configuração não alterada devido a área inválida.")))
    (t (princ "\nConfiguração cancelada.")))
  (princ))
