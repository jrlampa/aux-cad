;;; =============================================================================
;;; acaddoc.lsp - Carregador Automático de Rotinas do AUX CAD (Distribuição / IM3)
;;; Executado AUTOMATICAMENTE pelo AutoCAD a cada desenho (.dwg) aberto ou criado.
;;; =============================================================================

(vl-load-com)

;; =============================================================================
;;  FUNÇÕES DE COMPATIBILIDADE GLOBAL PARA TODAS AS ROTINAS AUTOLISP
;; =============================================================================
(defun stringp (x) (= (type x) 'STR))

(defun fboundp (sym)
  (and sym
       (or (= (type sym) 'SUBR)
           (= (type sym) 'USUBR)
           (and (= (type sym) 'SYM)
                (boundp sym)
                (or (= (type (eval sym)) 'SUBR)
                    (= (type (eval sym)) 'USUBR))))))

(if (not (fboundp 'vl-symbol-p))
  (defun vl-symbol-p (x) (= (type x) 'SYM))
)

(if (not (fboundp 'vl-sleep))
  (defun vl-sleep (ms)
    (vl-cmdf "_.delay" ms)
  )
)

(if (not (fboundp 'vl-filename-nxname))
  (defun vl-filename-nxname (filename)
    (strcat (vl-filename-base filename) (vl-filename-extension filename))
  )
)

;; Adiciona pastas dos projetos ao SupportPath do AutoCAD dinamicamente
(defun add-support-path (dir / files acadApp pref filesObj curPaths newPath)
  (setq acadApp (vlax-get-acad-object))
  (if (and acadApp (not (vl-catch-all-error-p acadApp)))
    (progn
      (setq pref (vl-catch-all-apply 'vla-get-Preferences (list acadApp)))
      (if (and pref (not (vl-catch-all-error-p pref)))
        (progn
          (setq filesObj (vla-get-Files pref))
          (setq curPaths (vla-get-SupportPath filesObj))
          (if (and dir (vl-file-directory-p dir))
            (if (not (vl-string-search (strcase dir) (strcase curPaths)))
              (vla-put-SupportPath filesObj (strcat curPaths ";" dir))
            )
          )
        )
      )
    )
  )
)

;; Registra raiz e subpastas de projetos dinamicamente (Protegido contra colisão multi-projeto)
(setq *aux-cad-root*
  (cond
    ((vl-file-directory-p "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\")
     "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\")
    ((findfile "aux_cad_menu.cuix")
     (strcat (vl-filename-directory (findfile "aux_cad_menu.cuix")) "\\"))
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
(add-support-path (strcat *aux-cad-root* "mapa_cad_paleta"))
(add-support-path (strcat *aux-cad-root* "prancha"))
(add-support-path (strcat *aux-cad-root* "sob"))

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

;; =============================================================================
;;  CARREGAMENTO DOS MÓDULOS DE ENGENHARIA DE DISTRIBUIÇÃO
;; =============================================================================

;; 1. Comum / Barra de Ferramentas nativa no AutoCAD
(load-aux-safe "aux_cad_toolbar.lsp")

;; 2. Módulo Queda de Tensão BT (CQT) e Quadros
(load-aux-safe "cqt\\cqt_cad_extractor.lsp")

;; 3. Módulo Meio Ambiente, KMZ, Memorial e Ortofoto
(load-aux-safe "ambiental\\kmz_point_layer_report.lsp")
(load-aux-safe "ambiental\\croqui_cad_inserter.lsp")
(load-aux-safe "ambiental\\cad2kmz.lsp")
(load-aux-safe "ambiental\\app_buffer.lsp")

;; 4. Módulo Cálculo Estrutural e Mecânico de Postes
(load-aux-safe "mecanico\\CALC_RESULTANTE_v1.0.lsp")

;; 5. Módulo Topografia, Pontos, Vias e Importadores de CSV e KMZ
(load-aux-safe "topografia\\addbloco.lsp")
(load-aux-safe "topografia\\kmz_pontos_importer.lsp")
(load-aux-safe "topografia\\IMPORTADOR_CSV_CONTORNOS_v2.2.lsp")
(load-aux-safe "topografia\\IMPORTADOR_CSV_PRO_v2.1.lsp")
(load-aux-safe "topografia\\TLENTAB.lsp")
(load-aux-safe "topografia\\IBCOORD.lsp")
(load-aux-safe "topografia\\pt2blk.lsp")
(load-aux-safe "topografia\\mlrua.lsp")

;; 6. Módulo Orçamento e Levantamento Automático de Materiais
(load-aux-safe "orcamento\\orcamento_cad_extractor.lsp")

;; 7. Módulo Estúdio Web de Satélite de Postes & Cargas
(load-aux-safe "mapa_postes\\mapa_cad_launcher.lsp")

;; 8. Módulo Dados Técnicos e Tabelas de Referência (Tabela 7 e Tabela 9 BT/MT)
(load-aux-safe "dados_tecnicos\\tabelas_referencia.lsp")

;; 9. Módulo Participação Financeira do Consumidor (CPFC - REN 1.059 ANEEL)
(load-aux-safe "cpfc\\cpfc_cad_launcher.lsp")

;; 10. Módulo Diagrama Unifilar e Consulta da Árvore de Dispositivos
(load-aux-safe "unifilar\\unifilar_cad.lsp")

;; 11. Módulo Paleta Cartográfica OSM C# (.NET) - Menos 1 tela
(load-aux-safe "mapa_cad_paleta\\mapa_paleta_loader.lsp")

;; 12. Módulo AutoPrancha Enel / HBT (Enquadramento Inteligente no ModelSpace)
(load-aux-safe "prancha\\autoprancha.lsp")

;; 13. Módulo Preparação de Projeto SOB (Pastas, SharePoint, Base DWG)
(load-aux-safe "sob\\sob_cad_launcher.lsp")


;; =============================================================================
;;  COMANDO GERAL DE RECARREGAMENTO (RECARREGAR_TUDO / RELOAD_AUXCAD)
;; =============================================================================
(defun c:RECARREGAR_TUDO (/ res)
  (princ "\n==============================================================")
  (princ "\n       RECARREGANDO TODOS OS MÓDULOS DO AUX CAD...            ")
  (princ "\n==============================================================")
  (setq res (vl-catch-all-apply 'load (list (strcat *aux-cad-root* "acaddoc.lsp"))))
  (if (vl-catch-all-error-p res)
    (princ (strcat "\n[ERRO AO RECARREGAR] -> " (vl-catch-all-error-message res)))
    (princ "\n[SUCESSO] Todos os módulos do AUX CAD foram recarregados com sucesso na memória!")
  )
  (princ)
)

(defun c:RELOAD_AUXCAD () (c:RECARREGAR_TUDO))


;; =============================================================================
;;  COMANDOS DE CONSULTA E AJUDA (COMANDOS / AJUDA / AUXCAD / ROTINAS)
;; =============================================================================

(defun c:COMANDOS (/ msg)
  (textscr) ;; Abre a janela de texto do AutoCAD (F2) para visualização completa
  (princ "\n==============================================================")
  (princ "\n               GUIA RÁPIDO DE COMANDOS - AUX CAD              ")
  (princ "\n==============================================================")
  (princ "\n")
  (princ "\n  [PREPARAÇÃO DE PROJETO SOB]
   - SOB ou NOVASOB ou PREPARAR_SOB : Prepara pasta, baixa croqui do SharePoint e abre BASE_SOB_DESENHO.dwg
   - RECARREGAR_SOB : Recarrega rotinas de preparação da SOB

  [DIAGRAMA UNIFILAR & PROTEÇÃO]")
  (princ "\n   - UNIFILAR ou PROTECAO : Localiza proteção a montante (SG) e insere/atualiza no DWG")
  (princ "\n")
  (princ "\n  [QUEDA DE TENSÃO BT - CQT]")
  (princ "\n   - CQT ou CQTUI ou QUEDATENSAO : Interface de cálculo CQT multi-cenários")
  (princ "\n   - CQTCAD : Extrai vãos e trechos do CAD para CQT")
  (princ "\n   - CQTQUADROS : Desenha os Quadros de CQT no AutoCAD")
  (princ "\n   - CQTEXCEL : Atalho para selecionar planilha Excel e desenhar quadros")
  (princ "\n   - RECARREGAR_CQT : Recarrega as rotinas de CQT na sessão atual")
  (princ "\n")
  (princ "\n  [AMBIENTAL, ORTOFOTO & CHECKLIST]")
  (princ "\n   - KMZCHECK ou MEMORIAL ou CHECKLIST : Checa KMZ e gera Checklist (.xlsx) / Memorial (.docx)")
  (princ "\n   - APP_BUFFER ou BUFFER_RIO ou APP_HIDRICA : Buffer geodésico de rios/nascentes (Lei 12.651) e auditoria de postes")
  (princ "\n   - INSCROQUI ou ORTOFOTO ou CROQUI : Insere Ortofoto/Croqui georreferenciado no CAD")
  (princ "\n   - CAD2KMZ : Exporta postes e redes para o Google Earth (KMZ)")
  (princ "\n   - RECARREGAR_KMZ ou RECARREGAR_CHECKLIST ou RECARREGAR_BUFFER : Recarrega rotinas ambientais")
  (princ "\n")
  (princ "\n  [CÁLCULO ESTRUTURAL & MECÂNICO]")
  (princ "\n   - CALC_RESULTANTE ou TRACAO ou ESFORCO : Tração resultante e sobrecarga em postes")
  (princ "\n   - RECARREGAR_RESULTANTE ou RECARREGAR_MECANICO : Recarrega módulo mecânico")
  (princ "\n")
  (princ "\n  [TABELAS TÉCNICAS & CONSULTA RÁPIDA (BT/MT)]")
  (princ "\n   - TABELAS ou CONSULTAR_TABELA ou TABELAS_BT : Menu de consulta de Condutores e Estruturas")
  (princ "\n   - CONDUTORES_BT ou BT : Consulta rápida de condutores BT (Tração, In, Ø, Massa, R, X)")
  (princ "\n   - CABOS_MT ou MT : Consulta rápida de cabos MT (vão padrão 40m e curvas por fase)")
  (princ "\n   - ESTRUTURAS_BT : Consulta de estruturas BT (Resistência mínima, Ângulo, Fixação)")
  (princ "\n")
  (princ "\n  [ORÇAMENTO & LEVANTAMENTO DE MATERIAIS]")
  (princ "\n   - ORCAD ou ORCAMENTO : Levantamento de postes, cabos e materiais no DWG")
  (princ "\n   - ORCUI : Abre a interface de orçamento e banco de preços")
  (princ "\n")
  (princ "\n  [PARTICIPAÇÃO FINANCEIRA - CPFC REN 1.000 / 1.059]")
  (princ "\n   - CPFC ou CPFCUI : Abre a interface de cálculo de Participação Financeira")
  (princ "\n   - CPFCCAD : Extrai dados do DWG e abre a interface com pasta do projeto")
  (princ "\n   - CPFC_NOTAS ou NOTAS_CPFC : Insere Notas Técnicas Regulatórias (Arts. 98, 104, 105, 110) na prancha")
  (princ "\n   - CPFCALERTA ou CPFCREGRA : Consulta regras e casos que geram PF (COP > ERD, MMGD, etc.)")
  (princ "\n")
  (princ "\n  [TOPOGRAFIA, EIXOS VIÁRIOS & IMPORTADORES]")
  (princ "\n   - MAPAPALETA ou OSMPALETA : Paleta C# (.NET) com Mapa OSM e inserção direta no CAD (Menos 1 tela)")
  (princ "\n   - MAPAPOSTES ou MAPA : Estúdio Web de Satélite (lançar coordenadas, postes e clientes)")
  (princ "\n   - IMPORTAR_KMZ_POSTES ou KMZPOSTES : Importa KMZ/KML com POSTE_, PONTO e descrição")
  (princ "\n   - ADDBLOCO : Insere blocos alinhados ao UCS da tela")
  (princ "\n   - IMPORTAR_PONTOS_UTM : Importa CSV UTM clássico")
  (princ "\n   - IMPORTAR_PONTOS_UTM_CONTORNOS : Importa CSV com contornos")
  (princ "\n   - TLENTAB : Tabela automática de comprimentos de linhas/polilinhas")
  (princ "\n   - IBCOORD : Insere bloco de coordenadas no centróide")
  (princ "\n   - PONTOSPARABLOCOS : Converte pontos do CAD em blocos")
  (princ "\n   - MLRUA : Tratamento automático de eixos viários MLINE")
  (princ "\n")
  (princ "\n  [SISTEMA & RECARREGAMENTO]")
  (princ "\n   - RECARREGAR_TUDO ou RELOAD_AUXCAD : Recarrega todos os módulos de uma vez")
  (princ "\n   - AUXCADBAR ou BARRAAUXCAD : Exibe barra de botões com 1 clique")
  (princ "\n==============================================================\n")

  ;; Exibe também caixa de diálogo visual na tela
  (setq msg (strcat
    "=== GUIA DE COMANDOS AUX CAD ===\n\n"
    "• PREPARAÇÃO DE SOB: Digite SOB (ou NOVASOB / PREPARAR_SOB)\n"
    "• ENQUADRAMENTO / PRANCHA: Digite AUTOPRANCHA (ou PRANCHA)\n"
    "• DIAGRAMA UNIFILAR: Digite UNIFILAR (ou PROTECAO)\n"
    "• QUEDA DE TENSÃO BT: Digite CQT (ou CQTQUADROS / CQTEXCEL)\n"
    "• MEMORIAL / CHECKLIST: Digite KMZCHECK (ou CHECKLIST)\n"
    "• ORTOFOTO / CROQUI: Digite INSCROQUI (ou ORTOFOTO)\n"
    "• TRAÇÃO EM POSTES: Digite CALC_RESULTANTE (ou TRACAO)\n"
    "• TABELAS TÉCNICAS: Digite TABELAS (ou BT / MT)\n"
    "• ORÇAMENTO DE MATERIAIS: Digite ORCAD (ou ORCAMENTO)\n"
    "• PARTICIPAÇÃO FINANCEIRA: Digite CPFC (ou CPFCUI)\n"
    "• ESTÚDIO MAPA WEB: Digite MAPAPOSTES (ou MAPA)\n"
    "• KMZ PARA POSTES: Digite IMPORTAR_KMZ_POSTES (ou KMZPOSTES)\n"
    "• EXPORTAR GOOGLE EARTH: Digite CAD2KMZ\n"
    "• TABELA DE COMPRIMENTOS: Digite TLENTAB\n"
    "• RECARREGAR TUDO: Digite RECARREGAR_TUDO\n"
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
(defun c:ENQUADRAMENTO () (c:AUTOPRANCHA))
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
(defun c:BT () (c:CONDUTORES_BT))
(defun c:MT () (c:CABOS_MT))

;; Mensagem informativa na linha de comando ao abrir qualquer desenho
(princ "\n[AUX CAD] Ferramentas carregadas com sucesso! Digite COMANDOS ou AUXCADBAR para começar.")

;; =============================================================================
;;  INTEGRAÇÃO MULTI-CONCESSIONÁRIA: AUX CAD LIGHT (Light / IM3 Brasil)
;; =============================================================================
(setq _aux_light_init "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\AUX CAD LIGHT\\acaddoc.lsp")
(if (and (findfile _aux_light_init) (not *AUX_CAD_LIGHT_LOADED*))
  (progn
    (setq *AUX_CAD_LIGHT_LOADED* t)
    (vl-catch-all-apply 'load (list _aux_light_init))
  )
)

(princ)

