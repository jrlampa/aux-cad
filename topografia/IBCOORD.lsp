(defun c:IBCOORD (/ ss i ent obj min max pt oldAttDia oldAttReq)
  (vl-load-com)

  ;; Salva estado atual
  (setq oldAttDia (getvar "ATTDIA"))
  (setq oldAttReq (getvar "ATTREQ"))

  ;; Desativa diálogo de atributos
  (setvar "ATTDIA" 0)
  (setvar "ATTREQ" 1)

  ;; Seleção de entidades
  (setq ss (ssget "_:L"))

  (if ss
    (progn
      (setq i 0)
      (repeat (sslength ss)

        (setq ent (ssname ss i))
        (setq obj (vlax-ename->vla-object ent))

        ;; Bounding Box
        (vla-getboundingbox obj 'min 'max)
        (setq min (vlax-safearray->list min))
        (setq max (vlax-safearray->list max))

        ;; Centro geométrico
        (setq pt (mapcar '(lambda (a b) (/ (+ a b) 2.0)) min max))

        ;; Insere bloco sem diálogo
        (command "-insert" "coord" pt 1 1 0)

        (setq i (1+ i))
      )
    )
  )

  ;; Restaura variáveis
  (setvar "ATTDIA" oldAttDia)
  (setvar "ATTREQ" oldAttReq)

  (princ "\nBloco inserido sem diálogo de atributos.")
  (princ)
)
