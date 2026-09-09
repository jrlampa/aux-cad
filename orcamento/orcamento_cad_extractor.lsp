;; ==============================================================================
;;  orcamento_cad_extractor.lsp
;;  AUX CAD - Extrator Automático de Materiais, Postes, Condutores e Equipamentos
;;  Comandos:
;;    ORCAD : Seleção e levantamento inteligente de materiais no desenho DWG
;;    ORCUI : Abertura direta da interface gráfica de orçamento
;; ==============================================================================

(vl-load-com)

;; Função auxiliar para calcular o comprimento de qualquer entidade linear
(defun orc:get-curve-length (ent / obj data)
  (setq data (entget ent))
  (cond
    ((= (cdr (assoc 0 data)) "LINE")
     (distance (cdr (assoc 10 data)) (cdr (assoc 11 data)))
    )
    (T
     (setq obj (vlax-ename->vla-object ent))
     (vl-catch-all-apply 'vlax-curve-getDistAtParam
       (list obj (vlax-curve-getEndParam obj))
     )
    )
  )
)

;; Função auxiliar para extrair atributos de um bloco
(defun orc:get-block-attributes (ent / obj attrs res val tag)
  (setq obj (vlax-ename->vla-object ent))
  (setq res "")
  (if (and (vlax-property-available-p obj 'HasAttributes)
           (= (vlax-get-property obj 'HasAttributes) :vlax-true))
    (progn
      (setq attrs (vlax-invoke obj 'GetAttributes))
      (foreach att attrs
        (setq tag (vlax-get-property att 'TagString))
        (setq val (vlax-get-property att 'TextString))
        (setq res (strcat res " " tag ":" val))
      )
    )
  )
  res
)

;; Comando Principal de Extração CAD
(defun c:ORCAD (/ ss i ent data tip ent_name lay pt x y attrs len_val
                  postes_list cabos_list equip_list
                  json_path py_path dwg_prefix f cmd_line)

  (princ "\n=======================================================")
  (princ "\n   AUX CAD - LEVANTAMENTO AUTOMATICO DE MATERIAIS      ")
  (princ "\n=======================================================")
  (princ "\n[AVISO REN 1.059] Este orçamento serve de base para o cálculo do CPFC.")
  (princ "\nHaverá Participação Financeira (PF > 0) se o COP da obra superar o ERD.")

  (setq dwg_prefix (getvar "DWGPREFIX"))
  (if (or (null dwg_prefix) (= dwg_prefix ""))
    (setq dwg_prefix (getvar "TEMPPREFIX"))
  )

  (setq json_path (strcat dwg_prefix "orcamento_dados.json"))

  (princ "\nSelecione os elementos da rede (Postes, Cabos, Equipamentos)...")
  (princ "\n[Dica: Pressione ENTER para selecionar TODO o desenho]")
  (setq ss (ssget '((0 . "INSERT,LINE,LWPOLYLINE,POLYLINE,TEXT,MTEXT"))))

  (if (null ss)
    (progn
      (princ "\nNenhum objeto selecionado manualmente. Analisando o desenho completo...")
      (setq ss (ssget "X" '((0 . "INSERT,LINE,LWPOLYLINE,POLYLINE,TEXT,MTEXT"))))
    )
  )

  (if (null ss)
    (progn
      (princ "\n[AVISO] Nenhum objeto encontrado no desenho.")
      (exit)
    )
  )

  (setq postes_list '())
  (setq cabos_list '())
  (setq equip_list '())

  (setq i 0)
  (while (< i (sslength ss))
    (setq ent (ssname ss i))
    (setq data (entget ent))
    (setq tip (cdr (assoc 0 data)))
    (setq lay (cdr (assoc 8 data)))

    ;; 1. Blocos (Postes ou Equipamentos)
    (if (= tip "INSERT")
      (progn
        (setq ent_name (cdr (assoc 2 data)))
        (setq pt (cdr (assoc 10 data)))
        (setq x (car pt))
        (setq y (cadr pt))
        (setq attrs (orc:get-block-attributes ent))

        (setq postes_list
          (cons
            (strcat "{\"id\":\"P" (itoa (1+ (length postes_list))) "\","
                    "\"bloco\":\"" ent_name "\","
                    "\"layer\":\"" lay "\","
                    "\"x\":" (rtos x 2 2) ","
                    "\"y\":" (rtos y 2 2) ","
                    "\"attrs\":\"" attrs "\"}")
            postes_list
          )
        )
      )
    )

    ;; 2. Linhas e Polilinhas (Cabos MT e BT)
    (if (or (= tip "LINE") (= tip "LWPOLYLINE") (= tip "POLYLINE"))
      (progn
        (setq len_val (orc:get-curve-length ent))
        (if (and len_val (> len_val 0.5))
          (setq cabos_list
            (cons
              (strcat "{\"id\":\"C" (itoa (1+ (length cabos_list))) "\","
                      "\"layer\":\"" lay "\","
                      "\"comprimento\":" (rtos len_val 2 2) ","
                      "\"vaos\":1}")
              cabos_list
            )
          )
        )
      )
    )

    ;; 3. Textos de Identificação (Estruturas e Trafos)
    (if (or (= tip "TEXT") (= tip "MTEXT"))
      (progn
        (setq txt_val (cdr (assoc 1 data)))
        (if (and txt_val (> (strlen txt_val) 1))
          (setq equip_list
            (cons
              (strcat "{\"tipo\":\"" txt_val "\",\"layer\":\"" lay "\"}")
              equip_list
            )
          )
        )
      )
    )

    (setq i (1+ i))
  )

  ;; Escreve o JSON intermediario
  (setq f (open json_path "w"))
  (if f
    (progn
      (write-line "{" f)
      
      ;; Postes
      (write-line "  \"postes\": [" f)
      (setq i 0)
      (foreach p postes_list
        (write-line (strcat "    " p (if (< (1+ i) (length postes_list)) "," "")) f)
        (setq i (1+ i))
      )
      (write-line "  ]," f)

      ;; Cabos
      (write-line "  \"cabos\": [" f)
      (setq i 0)
      (foreach c cabos_list
        (write-line (strcat "    " c (if (< (1+ i) (length cabos_list)) "," "")) f)
        (setq i (1+ i))
      )
      (write-line "  ]," f)

      ;; Equipamentos e Estruturas
      (write-line "  \"equipamentos\": [" f)
      (setq i 0)
      (foreach eq equip_list
        (write-line (strcat "    " eq (if (< (1+ i) (length equip_list)) "," "")) f)
        (setq i (1+ i))
      )
      (write-line "  ]" f)

      (write-line "}" f)
      (close f)
      (princ (strcat "\n[INFO] Dados extraidos com sucesso: " (itoa (length postes_list)) " blocos, " (itoa (length cabos_list)) " trechos lineares."))
    )
    (progn
      (princ (strcat "\n[ERRO] Nao foi possivel escrever no arquivo temporario: " json_path))
      (exit)
    )
  )

  ;; Dispara o Python
  (setq py_path (findfile "orcamento_manager.py"))
  (if (null py_path)
    (setq py_path (findfile "orcamento/orcamento_manager.py"))
  )

  (if py_path
    (progn
      (setq cmd_line (strcat "python \"" py_path "\" --json \"" json_path "\""))
      (princ (strcat "\nIniciando interface grafica de orcamento..."))
      (startapp "cmd.exe" (strcat "/c " cmd_line))
    )
    (princ "\n[ERRO] Script orcamento_manager.py nao encontrado no SupportPath do AutoCAD.")
  )

  (princ)
)

;; Comando para abrir a interface diretamente sem selecao
(defun c:ORCUI (/ py_path cmd_line)
  (setq py_path (findfile "orcamento_manager.py"))
  (if (null py_path)
    (setq py_path (findfile "orcamento/orcamento_manager.py"))
  )
  (if py_path
    (progn
      (princ "\n[AVISO REN 1.059] O orçamento serve de base para o cálculo de Participação Financeira (CPFC).")
      (princ "\nSe o custo proporcionalizado da obra superar o ERD da distribuidora, haverá cobrança de PF.")
      (setq cmd_line (strcat "python \"" py_path "\""))
      (princ "\nIniciando interface grafica de orcamento...")
      (startapp "cmd.exe" (strcat "/c " cmd_line))
    )
    (princ "\n[ERRO] Script orcamento_manager.py nao encontrado no SupportPath do AutoCAD.")
  )
  (princ)
)

(princ "\n[AUX CAD] Modulo de Orcamento carregado. Comandos: ORCAD (extracao) | ORCUI (interface direta)")
(princ)
