;; IMPORTA PONTOS DO CSV (X,Y,Z,Name)
;; Uso: APPLOAD -> IMPORTCSV

(defun split (str sep / lst pos)
  (setq lst '())
  (while (setq pos (vl-string-search sep str))
    (setq lst (cons (substr str 1 pos) lst))
    (setq str (substr str (+ pos (strlen sep) 1)))
  )
  (setq lst (cons str lst))
  (reverse lst)
)

(defun c:IMPORTCSV ( / file f line parts x y z)
  (vl-load-com)

  (setq file (getfiled "Selecione o CSV" "" "csv" 0))
  (setq f (open file "r"))

  ;; ignora cabeçalho
  (read-line f)

  (while (setq line (read-line f))
    (setq parts (split line ","))

    ;; pega X Y Z
    (setq x (nth 0 parts))
    (setq y (nth 1 parts))
    (setq z (nth 2 parts))

    ;; cria o ponto
    (command "POINT" (strcat x "," y "," z))
  )

  (close f)
  (princ "\nImportação concluída!")
)
