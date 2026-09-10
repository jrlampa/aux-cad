;; ============================================================
;;  app_buffer.lsp
;;  Geração de Buffers Geodésicos de Corpos Hídricos (APP_BUFFER)
;;  Em conformidade com o Código Florestal (Lei 12.651/2012):
;;   - Cursos d'água (<10m): Buffer bilateral de 30m
;;   - Nascentes e Olhos d'água: Buffer circular de raio 50m
;;
;;  Origens suportadas:
;;   [K]MZ: Extrai LineStrings (rios) e Points (nascentes) de KMZ/KML
;;   [D]WG: Seleciona linhas/polilinhas ou pontos diretamente no CAD
;;   [A]uditar: Verifica se postes/estruturas incidem na APP hídrica
;;
;;  Comandos: APP_BUFFER, BUFFER_APP, BUFFER_RIO, APP_HIDRICA
;; ============================================================

(vl-load-com)

;; Função auxiliar para obter caminho de arquivo python do módulo
(defun app-buffer-get-script-path (/ p1 p2)
  (setq p1 "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\ambiental\\app_buffer_generator.py")
  (if (findfile p1)
    p1
    (findfile "app_buffer_generator.py")
  )
)

;; Função auxiliar para obter diretório temporário
(defun app-buffer-get-tempdir ()
  (cond
    ((and (getvar "TEMPPREFIX") (= (type (getvar "TEMPPREFIX")) 'STR))
     (vl-string-right-trim "\\" (getvar "TEMPPREFIX")))
    (T "C:\\Temp")
  )
)

;; Função auxiliar para extrair coordenadas de uma entidade linear (LINE, LWPOLYLINE, POLYLINE)
(defun app-buffer-extract-linear-coords (ent / d oType pts x1 y1 x2 y2 p coords n i)
  (setq d (entget ent))
  (setq oType (cdr (assoc 0 d)))
  (cond
    ((= oType "LINE")
     (setq x1 (cadr (assoc 10 d)))
     (setq y1 (caddr (assoc 10 d)))
     (setq x2 (cadr (assoc 11 d)))
     (setq y2 (caddr (assoc 11 d)))
     (list (list x1 y1) (list x2 y2)))

    ((= oType "LWPOLYLINE")
     (setq pts nil)
     (foreach item d
       (if (= (car item) 10)
         (setq pts (cons (list (cadr item) (caddr item)) pts))
       )
     )
     (reverse pts))

    ((= oType "POLYLINE")
     (setq pts nil)
     (setq ent (entnext ent))
     (while (and ent (/= (cdr (assoc 0 (entget ent))) "SEQEND"))
       (if (= (cdr (assoc 0 (entget ent))) "VERTEX")
         (setq pts (cons (list (cadr (assoc 10 (entget ent))) (caddr (assoc 10 (entget ent)))) pts))
       )
       (setq ent (entnext ent))
     )
     (reverse pts))

    (T nil)
  )
)

;; Função para exportar feições CAD (DWG) para JSON temporário
(defun app-buffer-export-dwg-to-json (ss json_path / f i ent d oType coords name is_nascente pt x y first_item)
  (setq f (open json_path "w"))
  (if (not f)
    (progn (princ (strcat "\n[ERRO] Falha ao criar arquivo: " json_path)) nil)
    (progn
      (write-line "[" f)
      (setq first_item T)
      (setq i 0)
      (while (< i (sslength ss))
        (setq ent (ssname ss i))
        (setq d (entget ent))
        (setq oType (cdr (assoc 0 d)))
        (cond
          ;; Feição Linear (Rio/Córrego)
          ((member oType '("LINE" "LWPOLYLINE" "POLYLINE"))
           (setq coords (app-buffer-extract-linear-coords ent))
           (if (and coords (>= (length coords) 2))
             (progn
               (if (not first_item) (write-line "," f))
               (setq first_item nil)
               (write-line "  {" f)
               (write-line "    \"type\": \"LineString\"," f)
               (write-line "    \"name\": \"Rio/Córrego Selecionado (DWG)\"," f)
               (write-line "    \"category\": \"RIO\"," f)
               (write-line "    \"coordinates\": [" f)
               (setq n (length coords))
               (setq idx 0)
               (foreach pt coords
                 (setq idx (1+ idx))
                 (if (< idx n)
                   (write-line (strcat "      [" (rtos (car pt) 2 3) ", " (rtos (cadr pt) 2 3) "],") f)
                   (write-line (strcat "      [" (rtos (car pt) 2 3) ", " (rtos (cadr pt) 2 3) "]") f)
                 )
               )
               (write-line "    ]" f)
               (write-line "  }" f)
             )
           )
          )

          ;; Feição Pontual (Nascente)
          ((member oType '("POINT" "INSERT"))
           (setq pt (cdr (assoc 10 d)))
           (setq x (car pt))
           (setq y (cadr pt))
           (setq name "Nascente / Olho d'água")
           (if (= oType "INSERT")
             (setq name (strcat "Nascente: " (cdr (assoc 2 d))))
           )
           (if (not first_item) (write-line "," f))
           (setq first_item nil)
           (write-line "  {" f)
           (write-line "    \"type\": \"Point\"," f)
           (write-line (strcat "    \"name\": \"" name "\",") f)
           (write-line "    \"category\": \"NASCENTE\"," f)
           (write-line (strcat "    \"coordinates\": [" (rtos x 2 3) ", " (rtos y 2 3) "]") f)
           (write-line "  }" f)
          )
        )
        (setq i (1+ i))
      )
      (write-line "]" f)
      (close f)
      T
    )
  )
)

;; Função para exportar pontos de postes selecionados para JSON
(defun app-buffer-export-postes-json (ss json_path / f i ent d pt x y name first_item)
  (setq f (open json_path "w"))
  (if (not f)
    nil
    (progn
      (write-line "[" f)
      (setq first_item T)
      (setq i 0)
      (while (< i (sslength ss))
        (setq ent (ssname ss i))
        (setq d (entget ent))
        (setq pt (cdr (assoc 10 d)))
        (setq x (car pt))
        (setq y (cadr pt))
        (setq name "Poste")
        (if (= (cdr (assoc 0 d)) "INSERT")
          (setq name (cdr (assoc 2 d)))
        )
        (if (not first_item) (write-line "," f))
        (setq first_item nil)
        (write-line (strcat "  {\"name\": \"" name "\", \"x\": " (rtos x 2 3) ", \"y\": " (rtos y 2 3) "}") f)
        (setq i (1+ i))
      )
      (write-line "]" f)
      (close f)
      T
    )
  )
)

;; ============================================================
;;  Comando Principal: APP_BUFFER
;; ============================================================
(defun c:APP_BUFFER (/ helper_script tempdir opt kmz_path ss_dwg ss_postes fuso_str fuso
                       dist_rio_str dist_rio dist_nasc_str dist_nasc
                       cad_json postes_json out_lisp out_report out_boxes done_flag
                       cmd wsh timeout)
  (princ "\n============================================================")
  (princ "\n    BUFFER GEODÉSICO DE CORPOS HÍDRICOS (APP - LEI 12.651)  ")
  (princ "\n============================================================")

  (setq helper_script (app-buffer-get-script-path))
  (if (not helper_script)
    (progn
      (princ "\n[ERRO] Script 'app_buffer_generator.py' não encontrado na pasta ambiental.")
      (exit)
    )
  )

  (setq tempdir (app-buffer-get-tempdir))

  ;; 1. Menu de Opções
  (initget "K D A")
  (setq opt (getkword "\nOrigem dos corpos hídricos [KMZ / DWG / Auditar postes apenas] <KMZ>: "))
  (if (or (null opt) (= opt "")) (setq opt "K"))

  (setq kmz_path nil)
  (setq cad_json (strcat tempdir "\\app_cad_hydro.json"))
  (setq postes_json (strcat tempdir "\\kmz_points_input.json"))
  (setq out_lisp (strcat tempdir "\\app_draw_buffers.lsp"))
  (setq out_report (strcat tempdir "\\app_hydro_report.txt"))
  (setq out_boxes (strcat tempdir "\\kmz_boxes.txt"))
  (setq done_flag (strcat out_lisp ".done"))

  ;; Limpa artefatos antigos
  (if (findfile out_lisp) (vl-file-delete out_lisp))
  (if (findfile done_flag) (vl-file-delete done_flag))
  (if (findfile cad_json) (vl-file-delete cad_json))

  ;; 2. Coleta de Entidades Conforme a Opção
  (cond
    ((= opt "K")
     (setq kmz_path "G:\\Meu Drive\\1-HBT\\AMBIENTAL.kmz")
     (if (not (findfile kmz_path))
       (setq kmz_path (getfiled "Selecione o Arquivo KMZ com Cursos d'Água / Nascentes" "" "kmz" 16))
     )
     (if (or (not kmz_path) (not (findfile kmz_path)))
       (progn
         (princ "\n[ERRO] Nenhum KMZ válido foi selecionado.")
         (exit)
       )
     )
    )

    ((= opt "D")
     (princ "\nSelecione as LINHAS/POLILINHAS (rios/córregos) ou PONTOS/BLOCOS (nascentes) no desenho:")
     (setq ss_dwg (ssget '((0 . "LINE,LWPOLYLINE,POLYLINE,POINT,INSERT"))))
     (if (or (null ss_dwg) (= (sslength ss_dwg) 0))
       (progn
         (princ "\n[AVISO] Nenhuma entidade hidrográfica selecionada.")
         (exit)
       )
     )
     (app-buffer-export-dwg-to-json ss_dwg cad_json)
     (princ (strcat "\n[APP] " (itoa (sslength ss_dwg)) " feições exportadas do CAD."))
    )
  )

  ;; 3. Pergunta se deseja auditar postes
  (initget "S N")
  (setq ans_postes (getkword "\nDeseja auditar e verificar se há postes em faixa de APP? [S/N] <S>: "))
  (if (or (null ans_postes) (= ans_postes "")) (setq ans_postes "S"))

  (if (= ans_postes "S")
    (progn
      (princ "\nSelecione os POSTES ou BLOCOS a auditar (Pressione Enter para selecionar TODOS do desenho): ")
      (setq ss_postes (ssget '((0 . "POINT,INSERT"))))
      (if (not ss_postes)
        (setq ss_postes (ssget "X" '((0 . "POINT,INSERT"))))
      )
      (if (and ss_postes (> (sslength ss_postes) 0))
        (progn
          (app-buffer-export-postes-json ss_postes postes_json)
          (princ (strcat "\n[APP] " (itoa (sslength ss_postes)) " postes exportados para auditoria."))
        )
        (setq postes_json nil)
      )
    )
    (setq postes_json nil)
  )

  ;; 4. Fuso UTM e Parâmetros de Buffer
  (setq fuso_str (getstring "\nDigite o Fuso UTM do projeto [Padrão = 23]: "))
  (if (or (null fuso_str) (= fuso_str ""))
    (setq fuso 23)
    (setq fuso (atoi fuso_str))
  )

  (setq dist_rio_str (getstring "\nRaio do Buffer para Cursos d'água em metros [Padrão Lei 12.651 = 30.0m]: "))
  (if (or (null dist_rio_str) (= dist_rio_str ""))
    (setq dist_rio 30.0)
    (setq dist_rio (atof dist_rio_str))
  )

  (setq dist_nasc_str (getstring "\nRaio do Buffer para Nascentes em metros [Padrão Lei 12.651 = 50.0m]: "))
  (if (or (null dist_nasc_str) (= dist_nasc_str ""))
    (setq dist_nasc 50.0)
    (setq dist_nasc (atof dist_nasc_str))
  )

  ;; 5. Monta a linha de comando Python
  (setq cmd (strcat "python \"" helper_script "\""))
  (if kmz_path
    (setq cmd (strcat cmd " --kmz \"" kmz_path "\""))
  )
  (if (and (= opt "D") (findfile cad_json))
    (setq cmd (strcat cmd " --cad-json \"" cad_json "\""))
  )
  (if (and postes_json (findfile postes_json))
    (setq cmd (strcat cmd " --postes-json \"" postes_json "\""))
  )
  (setq cmd (strcat cmd " --fuso " (itoa fuso)))
  (setq cmd (strcat cmd " --buffer-rio " (rtos dist_rio 2 1)))
  (setq cmd (strcat cmd " --buffer-nascente " (rtos dist_nasc 2 1)))
  (setq cmd (strcat cmd " --out-lisp \"" out_lisp "\""))
  (setq cmd (strcat cmd " --out-report \"" out_report "\""))
  (setq cmd (strcat cmd " --out-boxes \"" out_boxes "\""))

  (princ "\n[APP] Processando geometria geodésica e gerando buffers...")
  (setq wsh (vlax-create-object "WScript.Shell"))
  (vlax-invoke-method wsh 'Run (strcat "cmd.exe /c " cmd " && echo done > \"" done_flag "\"") 0 :vlax-false)
  (vlax-release-object wsh)

  ;; Aguarda a conclusão
  (setq timeout 40)
  (while (and (> timeout 0) (not (findfile done_flag)))
    (vl-cmdf "delay" 500)
    (setq timeout (1- timeout))
  )

  ;; 6. Carrega e Desenha os Buffers no AutoCAD
  (if (findfile out_lisp)
    (progn
      (princ "\n[APP] Desenhando polígonos de APP no AutoCAD...")
      (load out_lisp)
      (princ "\n[SUCESSO] Buffers de corpos hídricos desenhados na camada AMBIENTAL_APP_HIDRICA!")
    )
    (princ "\n[AVISO] Nenhum buffer gerado ou tempo limite excedido.")
  )

  ;; 7. Exibe relatório na tela
  (if (findfile out_report)
    (progn
      (setq f (open out_report "r"))
      (princ "\n------------------------------------------------------------")
      (while (setq line (read-line f))
        (princ (strcat "\n" line))
      )
      (close f)
      (princ "\n------------------------------------------------------------")
    )
  )

  ;; 8. Alerta se foram encontradas invasões de APP
  (if (findfile out_boxes)
    (princ "\n[ALERTA] Foram detectados postes ou elementos em Área de Preservação Permanente (APP)!")
  )
  (princ "\n[APP_BUFFER] Concluído com sucesso!")
  (princ)
)

;; Aliases do Comando
(defun c:BUFFER_APP () (c:APP_BUFFER))
(defun c:BUFFER_RIO () (c:APP_BUFFER))
(defun c:APP_HIDRICA () (c:APP_BUFFER))

(defun c:RECARREGAR_BUFFER ()
  (load "C:\\Users\\jonat\\OneDrive - IM3 Brasil\\aux cad\\ambiental\\app_buffer.lsp")
  (princ "\n[APP] Rotina APP_BUFFER recarregada na memória do AutoCAD!")
  (princ)
)

(princ "\n[APP] Módulo de Buffer Geodésico de Corpos Hídricos carregado (Digite APP_BUFFER ou BUFFER_RIO).")
(princ)
