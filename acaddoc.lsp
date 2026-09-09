;;; =============================================================================
;;; acaddoc.lsp - Carregador Automático de Rotinas do AUX CAD (Distribuição / IM3)
;;; Executado AUTOMATICAMENTE pelo AutoCAD a cada desenho (.dwg) aberto ou criado.
;;; =============================================================================

(vl-load-com)

;; Compatibilidade para checagem de tipo string e função em rotinas LISP legadas/portadas
(defun stringp (x) (= (type x) 'STR))
(defun fboundp (sym)
  (and sym
       (or (= (type sym) 'SUBR)
           (= (type sym) 'USUBR)
           (and (= (type sym) 'SYM)
                (or (= (type (eval sym)) 'SUBR)
                    (= (type (eval sym)) 'USUBR))))))

;; Adiciona pastas dos projetos ao SupportPath do AutoCAD dinamicamente
(defun add-support-path (dir / files acadApp pref filesObj curPaths newPath)
  (setq acadApp (vlax-get-acad-object))
  (setq pref (vla-get-Preferences acadApp))
  (setq filesObj (vla-get-Files pref))
  (setq curPaths (vla-get-SupportPath filesObj))
  (if (and dir (vl-file-directory-p dir))
    (if (not (vl-string-search (strcase dir) (strcase curPaths)))
      (vla-put-SupportPath filesObj (strcat curPaths ";" dir))
    )
  )
)

;; Registra raiz e subpastas de projetos dinamicamente
(setq *aux-cad-root*
  (cond
    ((findfile "acaddoc.lsp")
     (strcat (vl-filename-directory (findfile "acaddoc.lsp")) "\\"))
    (t "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\")
  )
)
(add-support-path *aux-cad-root*)
(add-support-path (strcat *aux-cad-root* "cqt"))
(add-support-path (strcat *aux-cad-root* "ambiental"))
(add-support-path (strcat *aux-cad-root* "mecanico"))
(add-support-path (strcat *aux-cad-root* "topografia"))
(add-support-path (strcat *aux-cad-root* "orcamento"))
(add-support-path (strcat *aux-cad-root* "mapa_postes"))
(add-support-path (strcat *aux-cad-root* "dados_tecnicos"))
(add-support-path (strcat *aux-cad-root* "cpfc"))
(add-support-path (strcat *aux-cad-root* "unifilar"))

(defun load-aux-safe (subpath / fullpath res)
  (setq fullpath (strcat *aux-cad-root* subpath))
  (if (not (findfile fullpath))
    (setq fullpath (findfile (vl-filename-base subpath)))
  )
  (if (not fullpath)
    (setq fullpath (findfile subpath))
  )
  (if fullpath
    (progn
      (setq res (vl-catch-all-apply 'load (list fullpath)))
      (if (vl-catch-all-error-p res)
        (princ (strcat "\n[ERRO AO CARREGAR] " subpath " -> " (vl-catch-all-error-message res)))
      )
    )
    (princ (strcat "\n[AVISO] Arquivo LISP não localizado: " subpath))
  )
)

;; 1. Comum / Barra de Ferramentas nativa no AutoCAD
(load-aux-safe "aux_cad_toolbar.lsp")

;; 2. Módulo Queda de Tensão BT (CQT) e Quadros
(load-aux-safe "cqt\\cqt_cad_extractor.lsp")

;; 3. Módulo Meio Ambiente, KMZ, Memorial e Ortofoto
(load-aux-safe "ambiental\\kmz_point_layer_report.lsp")
(load-aux-safe "ambiental\\croqui_cad_inserter.lsp")
(load-aux-safe "ambiental\\cad2kmz.lsp")

;; 4. Módulo Cálculo Estrutural e Mecânico de Postes
(load-aux-safe "mecanico\\CALC_RESULTANTE_v1.0.lsp")

;; 5. Módulo Topografia, Pontos e Importadores de CSV e KMZ
(load-aux-safe "topografia\\addbloco.lsp")
(load-aux-safe "topografia\\kmz_pontos_importer.lsp")
(load-aux-safe "topografia\\IMPORTADOR_CSV_CONTORNOS_v2.2.lsp")
(load-aux-safe "topografia\\IMPORTADOR_CSV_PRO_v2.1.lsp")

;; 6. Módulo Orçamento e Levantamento Automático de Materiais
(load-aux-safe "orcamento\\orcamento_cad_extractor.lsp")

;; 7. Módulo Estúdio Web de Satélite de Postes & Cargas
(load-aux-safe "mapa_postes\\mapa_cad_launcher.lsp")

;; 8. Módulo Dados Técnicos e Tabelas de Referência (Tabela 7 e Tabela 9 BT)
(load-aux-safe "dados_tecnicos\\tabelas_referencia.lsp")

;; 9. Módulo Participação Financeira do Consumidor (CPFC - REN 1.059 ANEEL)
(load-aux-safe "cpfc\\cpfc_cad_launcher.lsp")

;; 10. Módulo Diagrama Unifilar e Consulta da Árvore de Dispositivos
(load-aux-safe "unifilar\\unifilar_cad.lsp")


;; =============================================================================
;;  COMANDOS DE CONSULTA E AJUDA (COMANDOS / AJUDA / AUXCAD / ROTINAS)
;; =============================================================================

(defun c:COMANDOS (/ msg)
  (textscr) ;; Abre a janela de texto do AutoCAD (F2) para visualização completa
  (princ "\n==============================================================")
  (princ "\n               GUIA RÁPIDO DE COMANDOS - AUX CAD              ")
  (princ "\n==============================================================")
  (princ "\n")
  (princ "\n  [DIAGRAMA UNIFILAR & ÁRVORE DE DISPOSITIVOS]")
  (princ "\n   - UNIFILAR ou PROTECAO : Localiza proteção a montante e insere/atualiza no DWG")
  (princ "\n")
  (princ "\n  [AMBIENTAL & ORTOFOTO]")
  (princ "\n   - INSCROQUI ou ORTOFOTO ou CROQUI : Insere Ortofoto/Croqui no CAD")
  (princ "\n   - KMZCHECK ou MEMORIAL ou CHECKLIST : Checa KMZ e gera Memorial/Checklist")
  (princ "\n   - CAD2KMZ : Exporta postes e redes para o Google Earth (KMZ)")
  (princ "\n")
  (princ "\n  [ORÇAMENTO & LEVANTAMENTO DE MATERIAIS]")
  (princ "\n   - ORCAD ou ORCAMENTO : Levantamento de postes, cabos e materiais no DWG")
  (princ "\n   - ORCUI : Abre a interface de orçamento e banco de preços")
  (princ "\n")
  (princ "\n  [PARTICIPAÇÃO FINANCEIRA - CPFC REN 1.059]")
  (princ "\n   - CPFC ou CPFCUI : Abre a interface de cálculo de Participação Financeira")
  (princ "\n   - CPFCCAD : Captura dados do DWG e abre a interface para preencher o modelo")
  (princ "\n   - CPFCALERTA ou CPFCREGRA : Exibe resumo dos casos que geram PF (COP > ERD, MMGD, etc.)")
  (princ "\n")
  (princ "\n  [QUEDA DE TENSÃO BT - CQT]")
  (princ "\n   - CQT ou CQTUI ou QUEDATENSAO : Interface de cálculo CQT (QT <= 6%)")
  (princ "\n   - CQTCAD : Extrai vãos e trechos do CAD para CQT")
  (princ "\n   - CQTQUADROS : Desenha os Quadros de CQT no AutoCAD")
  (princ "\n")
  (princ "\n  [CÁLCULO ESTRUTURAL & MECÂNICO]")
  (princ "\n   - CALC_RESULTANTE ou TRACAO ou ESFORCO : Tração resultante em postes")
  (princ "\n")
  (princ "\n  [TABELAS TÉCNICAS & CONSULTA RÁPIDA (BT)]")
  (princ "\n   - TABELAS ou CONSULTAR_TABELA : Menu de consulta de Condutores e Estruturas BT")
  (princ "\n   - CONDUTORES_BT : Consulta rápida da Tabela 9 (Tração, Corrente, Diâmetro, Massa, R, X)")
  (princ "\n   - ESTRUTURAS_BT : Consulta rápida da Tabela 7 (Resistência mínima, Ângulo, Fixação)")
  (princ "\n")
  (princ "\n  [TOPOGRAFIA, KMZ & MAPA WEB]")
  (princ "\n   - MAPAPOSTES ou MAPA : Estúdio Web de Satélite (lançar coordenadas, postes e clientes)")
  (princ "\n   - IMPORTAR_KMZ_POSTES ou KMZPOSTES : Importa KMZ/KML com POSTE_, PONTO e descrição")
  (princ "\n   - ADDBLOCO : Insere blocos alinhados ao UCS da tela")
  (princ "\n   - IMPORTAR_PONTOS_UTM : Importa CSV UTM clássico")
  (princ "\n   - IMPORTAR_PONTOS_UTM_CONTORNOS : Importa CSV com contornos")
  (princ "\n")
  (princ "\n  [BARRA DE FERRAMENTAS]")
  (princ "\n   - AUXCADBAR ou BARRAAUXCAD : Exibe barra de botões com 1 clique")
  (princ "\n==============================================================\n")

  ;; Exibe também caixa de diálogo visual na tela
  (setq msg (strcat
    "=== GUIA DE COMANDOS AUX CAD ===\n\n"
    "• DIAGRAMA UNIFILAR: Digite UNIFILAR (ou PROTECAO)\n"
    "• ESTÚDIO MAPA WEB: Digite MAPAPOSTES (ou MAPA)\n"
    "• KMZ PARA POSTES: Digite IMPORTAR_KMZ_POSTES (ou KMZPOSTES)\n"
    "• ORTOFOTO / CROQUI: Digite INSCROQUI (ou ORTOFOTO)\n"
    "• MEMORIAL / CHECKLIST: Digite KMZCHECK (ou MEMORIAL)\n"
    "• ORÇAMENTO DE MATERIAIS: Digite ORCAD (ou ORCAMENTO)\n"
    "• PARTICIPAÇÃO FINANCEIRA: Digite CPFC (ou CPFCUI)\n"
    "• QUEDA DE TENSÃO BT: Digite CQT (ou CQTCAD)\n"
    "• TRAÇÃO EM POSTES: Digite CALC_RESULTANTE (ou TRACAO)\n"
    "• EXPORTAR GOOGLE EARTH: Digite CAD2KMZ\n"
    "• BARRA DE BOTÕES: Digite AUXCADBAR\n\n"
    "(Consulte a janela de texto F2 para detalhes completos)"
  ))
  (alert msg)
  (princ)
)

;; Aliases para facilitar a memorização
(defun c:AJUDA () (c:COMANDOS))
(defun c:AUXCAD () (c:COMANDOS))
(defun c:ROTINAS () (c:COMANDOS))

;; Aliases diretos para as ferramentas
(defun c:KMZPOSTES () (c:IMPORTAR_KMZ_POSTES))
(defun c:ORTOFOTO () (c:INSCROQUI))
(defun c:CROQUI () (c:INSCROQUI))
(defun c:MEMORIAL () (c:KMZCHECK))
(defun c:CHECKLIST () (c:KMZCHECK))
(defun c:ORCAMENTO () (c:ORCAD))
(defun c:QUEDATENSAO () (c:CQT))
(defun c:TRACAO () (c:CALC_RESULTANTE))
(defun c:ESFORCO () (c:CALC_RESULTANTE))
(defun c:CONSULTAR_TABELA () (c:TABELAS))
(defun c:TABELAS_BT () (c:TABELAS))

;; Mensagem informativa na linha de comando ao abrir qualquer desenho
(princ "\n[AUX CAD] Ferramentas carregadas! Digite COMANDOS ou AJUDA para listar todas.")
(princ)

