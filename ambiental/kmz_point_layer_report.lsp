;; ============================================================
;;  kmz_point_layer_report.lsp
;;  Verifica se pontos georreferenciados (UTM) do projeto estão
;;  dentro de camadas ambientais de um arquivo KMZ.
;;  Se houver incidência:
;;   1) Desenha as caixas de alerta ambiental no AutoCAD (Texto Amarelo + Retângulo Azul).
;;   2) Abre a tela para preenchimento e geração automática do
;;      Memorial Técnico Descritivo Ambiental em Word (.docx).
;;
;;  Comando: KMZCHECK
;; ============================================================

(vl-load-com)

;; Função auxiliar para dividir string por delimitador
(defun str-split (str delim / pos lst)
  (while (setq pos (vl-string-search delim str))
    (setq lst (cons (substr str 1 pos) lst))
    (setq str (substr str (+ pos 1 (strlen delim))))
  )
  (reverse (cons str lst))
)

;; Função que desenha a caixa de alerta ambiental (Texto Amarelo + Retângulo Azul)
(defun draw-environmental-box (ins_pt cat spec text_h / acadDoc mSpace full_text mText minPt maxPt minP maxP padX padY x1 y1 x2 y2 pts poly next_y)
  (setq acadDoc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (setq mSpace (vla-get-ModelSpace acadDoc))

  ;; Monta o conteúdo do MTEXT formatado com alinhamento centralizado (\pxqc;)
  (setq full_text (strcat "{\\pxqc;ESTE PROJETO ENCONTRA-SE DENTRO DE UMA\\P" cat))
  (if (and spec (/= spec "") (/= spec " "))
    (setq full_text (strcat full_text "\\P" spec))
  )
  (setq full_text (strcat full_text "}"))

  ;; 1. Cria o MText
  (setq mText (vla-AddMText mSpace (vlax-3d-point ins_pt) 0.0 full_text))
  (vla-put-AttachmentPoint mText 2) ;; 2 = acAttachmentPointTopCenter
  (vla-put-Height mText text_h)
  (vla-put-Color mText 2)           ;; 2 = Amarelo (Yellow)
  (vla-put-InsertionPoint mText (vlax-3d-point ins_pt))
  (vla-Update mText)

  ;; 2. Obtém os limites exatos do texto gerado
  (vla-GetBoundingBox mText 'minPt 'maxPt)
  (setq minP (vlax-safearray->list minPt))
  (setq maxP (vlax-safearray->list maxPt))

  ;; 3. Define a margem (padding) ao redor do texto
  (setq padX (* text_h 2.8))
  (setq padY (* text_h 1.2))

  (setq x1 (- (car minP) padX))
  (setq y1 (- (cadr minP) padY))
  (setq x2 (+ (car maxP) padX))
  (setq y2 (+ (cadr maxP) padY))

  ;; 4. Desenha o Retângulo Envolvente (LWPOLYLINE fechada com Cor 5 = Azul)
  (setq pts (vlax-make-safearray vlax-vbDouble '(0 . 7)))
  (vlax-safearray-fill pts (list x1 y1 x2 y1 x2 y2 x1 y2))
  (setq poly (vla-AddLightWeightPolyline mSpace pts))
  (vla-put-Closed poly :vlax-true)
  (vla-put-Color poly 5)            ;; 5 = Azul (Blue)
  (vla-Update poly)

  ;; 5. Retorna o ponto de inserção para a próxima caixa empilhada verticalmente
  (setq next_y (- y1 (* text_h 2.5)))
  (list (car ins_pt) next_y 0.0)
)

;; Comando Principal
(defun c:KMZCHECK (/ kmz_path tempdir helper_path pts_file report_txt report_json boxes_txt done_flag
                    ss i ent data pt_coords x y pt_name f fuso_str fuso cmd wsh timeout
                    line parts cat spec text_h ins_pt cur_pt count_boxes ans_txt user_h
                    ans_doc docx_template md_script cmd_md poly_lsp ans_poly)

  (princ "\n==============================================")
  (princ "\n  VERIFICADOR DE INCIDÊNCIA AMBIENTAL (KMZ)   ")
  (princ "\n==============================================")

  ;; 1. Localização do KMZ Padrão
  (setq kmz_path "G:\\Meu Drive\\1-HBT\\AMBIENTAL.kmz")
  (if (not (findfile kmz_path))
    (setq kmz_path (getfiled "Selecione o Arquivo KMZ Ambiental" "" "kmz" 16))
  )

  (if (or (not kmz_path) (not (findfile kmz_path)))
    (progn
      (princ "\n[ERRO] Nenhum arquivo KMZ válido foi selecionado.")
      (princ)
      (exit)
    )
  )

  ;; 2. Diretório temporário e script Python
  (setq tempdir
    (cond
      ((and (getvar "TEMPPREFIX") (= (type (getvar "TEMPPREFIX")) 'STR))
       (vl-string-right-trim "\\" (getvar "TEMPPREFIX")))
      (T "C:\\Temp")
    )
  )

  (setq helper_path "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\ambiental\\kmz_point_layer_report.py")
  (if (not (findfile helper_path))
    (setq helper_path (findfile "kmz_point_layer_report.py"))
  )

  (if (not helper_path)
    (progn
      (princ "\n[ERRO] O script 'kmz_point_layer_report.py' não foi localizado.")
      (princ)
      (exit)
    )
  )

  ;; 3. Solicitação do Fuso UTM (Padrão 23)
  (setq fuso_str (getstring "\nDigite o Fuso UTM do projeto [Padrão = 23]: "))
  (if (or (null fuso_str) (= fuso_str ""))
    (setq fuso 23)
    (setq fuso (atoi fuso_str))
  )

  ;; 4. Seleção de Pontos ou Blocos do Projeto
  (princ "\nSelecione os Pontos ou Blocos a verificar (Pressione Enter para selecionar TODOS os pontos/blocos do desenho): ")
  (setq ss (ssget '((0 . "POINT,INSERT"))))
  (if (not ss)
    (setq ss (ssget "X" '((0 . "POINT,INSERT"))))
  )

  (if (or (null ss) (= (sslength ss) 0))
    (progn
      (princ "\n[AVISO] Nenhum ponto ou bloco encontrado no desenho.")
      (princ)
      (exit)
    )
  )

  ;; Caminhos dos arquivos de troca
  (setq pts_file (strcat tempdir "\\kmz_points_input.json"))
  (setq report_txt (strcat tempdir "\\kmz_layer_report.txt"))
  (setq report_json (strcat tempdir "\\kmz_layer_report.json"))
  (setq boxes_txt (strcat tempdir "\\kmz_boxes.txt"))
  (setq done_flag (strcat tempdir "\\kmz_boxes.txt.done"))

  ;; Limpa arquivos antigos para evitar falsas leituras
  (if (findfile boxes_txt) (vl-file-delete boxes_txt))
  (if (findfile done_flag) (vl-file-delete done_flag))
  (if (findfile report_txt) (vl-file-delete report_txt))

  ;; 5. Exporta as coordenadas UTM para JSON
  (setq f (open pts_file "w"))
  (write-line "[" f)

  (setq i 0)
  (while (< i (sslength ss))
    (setq ent (ssname ss i))
    (setq data (entget ent))
    (setq pt_coords (cdr (assoc 10 data)))
    (setq x (car pt_coords))
    (setq y (cadr pt_coords))

    (setq blk_name "")
    (if (= (cdr (assoc 0 data)) "INSERT")
      (progn
        (setq blk_name (cdr (assoc 2 data)))
        (setq pt_name (strcat "Bloco_" blk_name "_" (itoa (1+ i))))
      )
      (setq pt_name (strcat "Ponto_" (itoa (1+ i))))
    )

    (write-line
      (strcat
        "  {\"id\": \"" pt_name "\", \"x\": " (rtos x 2 4) ", \"y\": " (rtos y 2 4) ", \"zone\": " (itoa fuso) ", \"block_name\": \"" blk_name "\"}"
        (if (< (1+ i) (sslength ss)) "," "")
      )
      f
    )
    (setq i (1+ i))
  )
  (write-line "]" f)
  (close f)

  (princ (strcat "\nProcessando " (itoa (sslength ss)) " ponto(s) contra o KMZ ambiental..."))

  ;; 6. Execução Síncrona do Python via WScript.Shell
  (setq cmd (strcat "python \"" helper_path "\" \"" kmz_path "\" \"" pts_file "\" \"" report_txt "\" \"" report_json "\" \"" boxes_txt "\" " (itoa fuso)))
  
  (setq wsh (vlax-create-object "WScript.Shell"))
  (if wsh
    (progn
      (vlax-invoke-method wsh "Run" (strcat "cmd.exe /c " cmd) 0 :vlax-true)
      (vlax-release-object wsh)
    )
    (progn
      ;; Fallback caso WScript.Shell não esteja disponível
      (startapp "cmd.exe" (strcat "/c " cmd))
    )
  )

  ;; Aguarda a conclusão da geração dos arquivos (sincronização via done_flag)
  (setq timeout 40)
  (while (and (not (findfile done_flag)) (> timeout 0))
    (vl-cmdf "_.delay" 300)
    (setq timeout (1- timeout))
  )

  ;; 7. Verifica se houve incidências ambientais para desenhar as caixas
  (if (findfile boxes_txt)
    (progn
      (setq f (open boxes_txt "r"))
      (setq count_boxes 0)
      (while (setq line (read-line f))
        (if (/= (vl-string-trim " " line) "")
          (setq count_boxes (1+ count_boxes))
        )
      )
      (close f)

      (if (> count_boxes 0)
        (progn
          (princ (strcat "\n\n>>> ATENÇÃO: " (itoa count_boxes) " INCIDÊNCIA(S) AMBIENTAL(IS) DETECTADA(S)! <<<"))
          
          ;; 6.1 Desenho Opcional das Polilinhas de Restrição no AutoCAD
          (setq poly_lsp (strcat tempdir "\\kmz_draw_polygons.lsp"))
          (if (findfile poly_lsp)
            (progn
              (initget "Sim Nao S N")
              (setq ans_poly (getkword "\nDeseja desenhar o contorno dos polígonos ambientais no AutoCAD? [Sim/Nao] <Sim>: "))
              (if (or (null ans_poly) (= ans_poly "Sim") (= ans_poly "S"))
                (progn
                  (load poly_lsp)
                  (c:KMZ_DRAW_POLYGONS)
                )
              )
            )
          )

          ;; Pergunta onde inserir as caixas no desenho
          (setq ins_pt (getpoint "\nClique no local do desenho para posicionar as Caixas de Alerta Ambiental (ou Enter para pular): "))
          (if ins_pt
            (progn
              ;; Altura do texto
              (setq text_h (getvar "TEXTSIZE"))
              (if (or (null text_h) (<= text_h 0.0)) (setq text_h 2.5))
              (setq user_h (getdist ins_pt (strcat "\nInforme a altura do texto <" (rtos text_h 2 2) ">: ")))
              (if (and user_h (> user_h 0.0)) (setq text_h user_h))

              ;; Desenha as caixas no AutoCAD
              (setq f (open boxes_txt "r"))
              (setq cur_pt ins_pt)
              (while (setq line (read-line f))
                (if (/= (vl-string-trim " " line) "")
                  (progn
                    (setq parts (str-split line "|"))
                    (setq cat (car parts))
                    (setq spec (if (> (length parts) 1) (cadr parts) ""))
                    (setq cur_pt (draw-environmental-box cur_pt cat spec text_h))
                  )
                )
              )
              (close f)
              (princ "\n[SUCESSO] Caixas de notas ambientais desenhadas no AutoCAD com sucesso!")
            )
            (princ "\n[INFO] Inserção de caixas no desenho pulada pelo usuário.")
          )

          ;; 8. Opção de gerar o Memorial Descritivo e Checklist Ambiental
          (initget "Sim Nao S N")
          (setq ans_doc (getkword "\nDeseja abrir o formulário para gerar o Memorial Descritivo e Checklist Ambiental? [Sim/Nao] <Sim>: "))
        )
        (progn
          (princ "\n\n[OK] Nenhum ponto do projeto incidiu em áreas restritas do KMZ (Livre de Restrições).")
          ;; Para projetos sem restrição ambiental, gera-se obrigatoriamente o Checklist Ambiental (.xlsx)
          (initget "Sim Nao S N")
          (setq ans_doc (getkword "\nDeseja abrir o formulário para gerar o Checklist Ambiental (.xlsx)? [Sim/Nao] <Sim>: "))
        )
      )

      ;; Execução unificada do formulário se o usuário confirmou (ou pressionou Enter)
      (if (or (null ans_doc) (= ans_doc "Sim") (= ans_doc "S"))
        (progn
          (setq docx_template "G:\\Meu Drive\\1-HBT\\MODELO MEMORIAL DESCRITIVO_AMBIENTAL.docx")
          (if (not (findfile docx_template))
            (setq docx_template "")
          )
          (setq md_script "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\ambiental\\memorial_ambiental_generator.py")
          (if (not (findfile md_script))
            (setq md_script (findfile "memorial_ambiental_generator.py"))
          )
          (if (and md_script (findfile md_script))
            (progn
              (if (> count_boxes 0)
                (princ "\nAbrindo formulário do Memorial Descritivo e Checklist Ambiental...")
                (princ "\nAbrindo formulário do Checklist Ambiental (Livre de Restrições)...")
              )
              (setq cmd_md (strcat "python \"" md_script "\" \"" docx_template "\" \"" pts_file "\" \"" boxes_txt "\" " (itoa fuso)))
              (startapp "cmd.exe" (strcat "/c " cmd_md))
            )
            (princ "\n[AVISO] Script auxiliar 'memorial_ambiental_generator.py' não localizado.")
          )
        )
      )
    )
    (princ "\n[AVISO] Não foi possível obter o resultado do processamento.")
  )

  ;; 9. Opção de consultar relatório detalhado TXT
  (initget "Sim Nao S N")
  (setq ans_txt (getkword "\nDeseja abrir o relatório detalhado em TXT? [Sim/Nao] <Nao>: "))
  (if (or (= ans_txt "Sim") (= ans_txt "S"))
    (startapp "notepad.exe" report_txt)
  )

  (princ)
)

;; Comando para recarregar a rotina na sessão atual do AutoCAD
(defun c:RECARREGAR_KMZ ()
  (load "ambiental/kmz_point_layer_report.lsp")
  (princ "\n[KMZCHECK] Rotina ambiental e de checklist recarregada com sucesso!")
  (princ)
)

(defun c:RECARREGAR_AMBIENTAL () (c:RECARREGAR_KMZ))
(defun c:RECARREGAR_CHECKLIST () (c:RECARREGAR_KMZ))

(princ "\nRotina KMZCHECK atualizada e carregada com sucesso! Digite KMZCHECK ou RECARREGAR_KMZ.")
(princ)
