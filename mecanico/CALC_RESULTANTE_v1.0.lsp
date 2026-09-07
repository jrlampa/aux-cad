;;; =============================================================================
;;; CALCULADOR DE ESFORÇO RESULTANTE EM POSTES E REDES ELÉTRICAS (daN + ÂNGULO)
;;; Cruzamento Inteligente com Capacidade Nominal do Bloco do Poste (12/300, 12/600 etc.)
;;; Comando no AutoCAD: CALC_RESULTANTE
;;; Versão 3.0 - Verificação Estrutural Automática de Sobrecarga e Estaiamento
;;; =============================================================================

(vl-load-com)

(defun to-2d (pt)
  (list (car pt) (cadr pt) 0.0)
)

;; Extrai capacidade nominal em daN do nome do bloco do poste
(defun get-poste-nominal-force (blkName / s)
  (setq s (strcase blkName))
  (cond
    ((wcmatch s "*3000*") 3000.0)
    ((wcmatch s "*2500*") 2500.0)
    ((wcmatch s "*2000*") 2000.0)
    ((wcmatch s "*1500*") 1500.0)
    ((wcmatch s "*1200*") 1200.0)
    ((wcmatch s "*1000*") 1000.0)
    ((wcmatch s "*800*")  800.0)
    ((wcmatch s "*600*")  600.0)
    ((wcmatch s "*400*")  400.0)
    ((wcmatch s "*300*")  300.0)
    ((wcmatch s "*200*")  200.0)
    ((wcmatch s "*150*")  150.0)
    (T 0.0)
  )
)

(defun C:CALC_RESULTANTE (/ p0 p0_2d ss_blk blk_name f_nom f_nom_input ss i ent obj p1 p2 d1 d2 p_ext 
                            angle_rad force fx fy f_res ang_rad ang_deg taxa status_str color_code
                            text_lines full_text ins_pt acadObj doc ms mtextObj h_texto)

  (princ "\n==============================================================")
  (princ "\n   CÁLCULO DE ESFORÇO RESULTANTE E VERIFICAÇÃO DE POSTES      ")
  (princ "\n==============================================================")

  ;; 1. Ponto do Nó / Poste de Origem
  (setq p0 (getpoint "\nClique no Ponto do Nó / Poste de Origem: "))
  (if (not p0)
    (progn (princ "\nNenhum ponto selecionado. Cancelado.") (exit))
  )
  (setq p0_2d (to-2d p0))

  ;; 2. Tenta detectar automaticamente o bloco de poste no ponto clicado (raio 1.5m)
  (setq blk_name nil f_nom 0.0)
  (setq ss_blk (ssget "_C" (list (- (car p0) 1.5) (- (cadr p0) 1.5)) 
                           (list (+ (car p0) 1.5) (+ (cadr p0) 1.5)) 
                           '((0 . "INSERT"))))
  (if ss_blk
    (progn
      (setq blk_name (cdr (assoc 2 (entget (ssname ss_blk 0)))))
      (setq f_nom (get-poste-nominal-force blk_name))
      (if (> f_nom 0.0)
        (princ (strcat "\n[BLOCO DETECTADO] " blk_name " -> Capacidade Nominal: " (rtos f_nom 2 0) " daN"))
        (princ (strcat "\n[BLOCO DETECTADO] " blk_name " (Capacidade nominal não identificada no nome)"))
      )
    )
  )

  ;; Se não detectou a capacidade do poste, solicita ao usuário
  (if (<= f_nom 0.0)
    (progn
      (setq f_nom_input (getreal "\nInforme o esforço nominal do poste em daN [Ex: 300, 600, 1000] ou Enter para pular: "))
      (if f_nom_input
        (setq f_nom f_nom_input
              blk_name (strcat "Poste " (rtos f_nom 2 0) " daN"))
      )
    )
  )

  ;; 3. Seleção de 2 ou mais linhas conectadas
  (princ "\nSelecione 2 ou mais LINHAS conectadas ao poste: ")
  (setq ss (ssget '((0 . "LINE,LWPOLYLINE"))))
  
  (if (or (not ss) (< (sslength ss) 2))
    (progn
      (alert "Você precisa selecionar pelo menos 2 linhas conectadas ao poste!")
      (exit)
    )
  )

  (setq fx 0.0)
  (setq fy 0.0)
  (setq i 0)

  ;; 4. Loop de decomposição vetorial por linha
  (while (< i (sslength ss))
    (setq ent (ssname ss i))
    (setq obj (vlax-ename->vla-object ent))
    
    (redraw ent 3) ;; Destaca a linha
    
    (setq p1 (to-2d (vlax-curve-getStartPoint obj)))
    (setq p2 (to-2d (vlax-curve-getEndPoint obj)))
    
    (setq d1 (distance p0_2d p1))
    (setq d2 (distance p0_2d p2))
    
    (if (> d1 d2) (setq p_ext p1) (setq p_ext p2))
    
    (setq angle_rad (angle p0_2d p_ext))

    (setq force (getreal (strcat "\nInforme a tração/força em daN para a Linha " (itoa (1+ i)) ": ")))
    (if (not force) (setq force 0.0))
    
    (setq fx (+ fx (* force (cos angle_rad))))
    (setq fy (+ fy (* force (sin angle_rad))))
    
    (redraw ent 4) ;; Restaura a linha
    (setq i (1+ i))
  )

  ;; 5. Resultante (Módulo) e Ângulo
  (setq f_res (sqrt (+ (* fx fx) (* fy fy))))
  
  (if (and (= fx 0.0) (= fy 0.0))
    (setq ang_deg 0.0)
    (progn
      (setq ang_rad (atan fy fx))
      (if (< ang_rad 0.0)
        (setq ang_rad (+ ang_rad (* 2.0 pi)))
      )
      (setq ang_deg (* ang_rad (/ 180.0 pi)))
    )
  )

  ;; 6. Verificação de Sobrecarga e Cruzamento com o Poste
  (princ "\n==============================================================")
  (princ (strcat "\nESFORÇO RESULTANTE: " (rtos f_res 2 0) " daN | ÂNGULO: " (rtos ang_deg 2 0) "°"))

  (setq color_code 3) ;; Verde padrão
  (if (> f_nom 0.0)
    (progn
      (setq taxa (* (/ f_res f_nom) 100.0))
      (if (> f_res f_nom)
        (progn
          (setq color_code 1) ;; Vermelho
          (setq status_str (strcat "⚠️ SOBRECARGA ESTRUTURAL (" (rtos taxa 2 0) "%) - REQUER ESTAIAMENTO OU POSTE " (if (<= f_nom 300) "600 daN" "1000 daN")))
          (princ (strcat "\n[ALERTA] " status_str))
        )
        (progn
          (setq color_code 3) ;; Verde
          (setq status_str (strcat "✔ POSTE SUPORTA O ESFORÇO (Carregamento: " (rtos taxa 2 0) "% da capacidade)"))
          (princ (strcat "\n[STATUS] " status_str))
        )
      )
    )
    (setq status_str "")
  )
  (princ "\n==============================================================")

  ;; 7. Inserção de MText formatado no AutoCAD
  (setq ins_pt (getpoint "\nClique no local para inserir a anotação do resultado: "))
  (if ins_pt
    (progn
      (setq h_texto 1.0)
      (setq full_text (strcat "ESF. RESULTANTE: " (rtos f_res 2 0) " daN (" (rtos ang_deg 2 0) "°)"))
      (if blk_name
        (setq full_text (strcat full_text "\\PPOSTE: " blk_name " (Cap. " (rtos f_nom 2 0) " daN)"))
      )
      (if (/= status_str "")
        (setq full_text (strcat full_text "\\P" status_str))
      )

      (setq acadObj (vlax-get-acad-object)
            doc     (vla-get-ActiveDocument acadObj)
            ms      (vla-get-ModelSpace doc))

      (setq mtextObj (vla-AddMText ms (vlax-3d-point ins_pt) 0.0 full_text))
      (vla-put-Height mtextObj h_texto)
      (vla-put-Color mtextObj color_code)
      (vla-put-Layer mtextObj (getvar "CLAYER"))
      (vla-Update mtextObj)

      (princ (strcat "\nAnotação inserida no CAD com cor " (if (= color_code 1) "VERMELHA (Sobrecarga)" "VERDE (Aprovado)") "!"))
    )
  )

  (princ)
)

(princ "\n[CALC_RESULTANTE v3.0] Carregado com verificação inteligente de sobrecarga de postes!")
(princ)
