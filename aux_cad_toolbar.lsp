;;; =============================================================================
;;; aux_cad_toolbar.lsp
;;; Cria e exibe automaticamente a Barra de Ferramentas visual do AUX CAD no AutoCAD
;;; Contém botões de atalho para todas as rotinas de engenharia de distribuição
;;; Comando no AutoCAD: AUXCADBAR ou BARRAAUXCAD
;;; =============================================================================

(vl-load-com)

(defun c:AUXCADBAR (/ acadApp menuGroups mg tb count item)
  (setq acadApp (vlax-get-acad-object))
  (setq menuGroups (vla-get-MenuGroups acadApp))
  
  ;; Tenta usar o grupo padrão ACAD ou o primeiro disponível
  (setq mg (vl-catch-all-apply 'vla-Item (list menuGroups "ACAD")))
  (if (vl-catch-all-error-p mg)
    (setq mg (vla-Item menuGroups 0))
  )

  (if mg
    (progn
      ;; Verifica se a barra já existe no grupo
      (setq tb (vl-catch-all-apply 'vla-Item (list (vla-get-Toolbars mg) "AUX CAD - Engenharia")))
      (if (vl-catch-all-error-p tb)
        (progn
          ;; Cria nova Barra de Ferramentas
          (setq tb (vla-Add (vla-get-Toolbars mg) "AUX CAD - Engenharia"))
          
          ;; 0. Botão de Ajuda e Lista de Comandos
          (vla-AddToolbarItem tb (vla-get-Count tb) "❓ Guia de Comandos (COMANDOS)" "Exibe a lista de todos os comandos das rotinas" "^C^CCOMANDOS ")

          ;; 1. Botão ORCAD (Orçamento)
          (vla-AddToolbarItem tb (vla-get-Count tb) "📦 Orçamento DWG (ORCAD)" "Levantamento automático de materiais no CAD" "^C^CORCAD ")

          ;; 2. Botão ORCUI (Interface Orçamento)
          (vla-AddToolbarItem tb (vla-get-Count tb) "📋 Tabela de Materiais (ORCUI)" "Abre a interface de orçamento e preços" "^C^CORCUI ")

          ;; 2.1 Botão CPFC (Participação Financeira REN 1.059)
          (vla-AddToolbarItem tb (vla-get-Count tb) "💰 CPFC (Part. Financeira)" "Abre o cálculo de Participação Financeira do Consumidor" "^C^CCPFCCAD ")

          ;; 2.2 Botão Diagrama Unifilar (Proteção a Montante)
          (vla-AddToolbarItem tb (vla-get-Count tb) "⚡ Diagrama Unifilar" "Localiza a proteção a montante e insere/atualiza no DWG" "^C^CUNIFILAR ")

          ;; 3. Botão CQT
          (vla-AddToolbarItem tb (vla-get-Count tb) "⚡ CQT (Queda de Tensão)" "Abre a Interface CQT multi-cenários" "^C^CCQT ")
          
          ;; 4. Botão CQTCAD
          (vla-AddToolbarItem tb (vla-get-Count tb) "📐 Extrair Vãos CAD" "Extrai vãos do CAD para a planilha CQT" "^C^CCQTCAD ")

          ;; 5. Botão CQTQUADROS
          (vla-AddToolbarItem tb (vla-get-Count tb) "📊 Desenhar Quadros CQT" "Desenha os quadros de CQT no AutoCAD" "^C^CCQTQUADROS ")

          ;; 5.1 Botão CQTEXCEL
          (vla-AddToolbarItem tb (vla-get-Count tb) "📥 Quadros CQT via Excel" "Seleciona planilha CQT e desenha quadros no CAD" "^C^CCQTEXCEL ")

          ;; 6. Botão KMZCHECK
          (vla-AddToolbarItem tb (vla-get-Count tb) "🌳 KMZ Ambiental" "Verifica áreas ambientais e gera Memorial/Checklist" "^C^CKMZCHECK ")

          ;; 6.1 Botão APP_BUFFER
          (vla-AddToolbarItem tb (vla-get-Count tb) "🌊 APP Hídrica (APP_BUFFER)" "Gera buffers de rios/nascentes (Lei 12.651) e audita postes" "^C^CAPP_BUFFER ")

          ;; 7. Botão INSCROQUI
          (vla-AddToolbarItem tb (vla-get-Count tb) "🖼️ Inserir Ortofoto" "Insere a Ortofoto/Croqui de satélite no CAD" "^C^CINSCROQUI ")

          ;; 8. Botão CALC_RESULTANTE
          (vla-AddToolbarItem tb (vla-get-Count tb) "⚙️ Resultante em Postes" "Calcula tração resultante e checa sobrecarga" "^C^CCALC_RESULTANTE ")

          ;; 8.1 Botão TABELAS (Tabelas Técnicas BT/MT)
          (vla-AddToolbarItem tb (vla-get-Count tb) "📚 Tabelas Técnicas" "Consulta rápida de cabos MT, condutores e estruturas BT" "^C^CTABELAS ")

          ;; 9. Botão TLENTAB (Comprimentos em Tabela)
          (vla-AddToolbarItem tb (vla-get-Count tb) "📏 Tabela Comprimentos" "Soma comprimentos de linhas e gera tabela no CAD" "^C^CTLENTAB ")

          ;; 10. Botão ADDBLOCO
          (vla-AddToolbarItem tb (vla-get-Count tb) "📍 Add Bloco no UCS" "Insere blocos sobre referências orientado à tela" "^C^CADDBLOCO ")

          ;; 11. Botão Estúdio Mapa Web
          (vla-AddToolbarItem tb (vla-get-Count tb) "🌍 Estúdio Mapa Satélite (MAPAPOSTES)" "Abre o mapa com satélite para lançar coordenadas, postes e clientes" "^C^CMAPAPOSTES ")

          ;; 12. Botão KMZ Postes
          (vla-AddToolbarItem tb (vla-get-Count tb) "📍 KMZ ➔ Postes & Textos" "Importa pontos do KMZ com bloco POSTE_, PONTO e descricao" "^C^CIMPORTAR_KMZ_POSTES ")

          ;; 13. Botão CSV UTM
          (vla-AddToolbarItem tb (vla-get-Count tb) "📥 Importar CSV UTM" "Importa pontos topográficos de arquivo CSV" "^C^CIMPORTAR_PONTOS_UTM ")

          ;; 14. Botão Recarregar Tudo
          (vla-AddToolbarItem tb (vla-get-Count tb) "🔄 Recarregar Tudo" "Recarrega todas as rotinas do AUX CAD na memória" "^C^CRECARREGAR_TUDO ")
        )
      )

      ;; Posiciona e torna visível a barra
      (vla-put-Visible tb :vlax-true)
      (vla-Dock tb 1) ;; 1 = acToolbarDockTop (ancora no topo da tela)
      (princ "\n✔ Barra de Ferramentas 'AUX CAD - Engenharia' carregada e ativada no topo da tela!")
    )
  )
  (princ)
)

(defun c:BARRAAUXCAD () (c:AUXCADBAR))

(princ "\n[AUX CAD TOOLBAR] Carregada! Digite AUXCADBAR para exibir a barra de botões.")
(princ)
