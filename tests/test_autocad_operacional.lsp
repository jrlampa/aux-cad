;;; =============================================================================
;;; test_autocad_operacional.lsp
;;; Bateria de Validação Operacional no AutoCAD Real (accoreconsole 2026)
;;; =============================================================================

(princ "\n[TESTE OPERACIONAL AUTOCAD] Iniciando...")

;; TESTE 01: Comandos Carregados
(if (and (fboundp 'c:SOB) (fboundp 'c:NOVASOB) (fboundp 'sob-executar-fluxo))
  (princ "\n[PASS] AUTOCAD-01: Comandos e rotinas SOB carregados com sucesso.")
  (princ "\n[FAIL] AUTOCAD-01: Rotinas SOB nao encontradas.")
)

;; TESTE 02: Normalização Canônica
(setq idTest (sob-obter-id "SOB_A057349839"))
(setq nameTest (sob-obter-name "A057349839"))
(if (and (= idTest "A057349839") (= nameTest "SOB_A057349839"))
  (princ "\n[PASS] AUTOCAD-02: Normalizacao canonica de SOB_ID e SOB_NAME comprovada.")
  (princ (strcat "\n[FAIL] AUTOCAD-02: Erro na normalizacao. id=" idTest " name=" nameTest))
)

;; TESTE 03: Rejeição de Entrada Inválida
(setq resInvalido (sob-executar-fluxo "" "C:\\Temp" nil))
(if (and resInvalido (null (cdr (assoc "sucesso" resInvalido))))
  (princ "\n[PASS] AUTOCAD-03: Entrada vazia rejeitada corretamente.")
  (princ "\n[FAIL] AUTOCAD-03: Falha ao rejeitar entrada vazia.")
)

;; TESTE 04: Execução de Fluxo em Diretório Temporário com SOB Real Única
(setq destTmp (getvar "TEMPPREFIX"))
(setq sobTeste "A056895307")
(setq sobRootEsperado (strcat (vl-string-right-trim "\\" destTmp) "\\SOB_" sobTeste))

;; Limpa teste anterior se existir para testar criação limpa
(if (vl-file-directory-p sobRootEsperado)
  (progn
    (setq wsh (vl-catch-all-apply 'vlax-create-object (list "WScript.Shell")))
    (if (and wsh (not (vl-catch-all-error-p wsh)))
      (progn
        (vl-catch-all-apply 'vlax-invoke-method (list wsh "Run" (strcat "cmd.exe /c rd /s /q \"" sobRootEsperado "\"") 0 :vlax-true))
        (vlax-release-object wsh)
      )
    )
  )
)

(princ (strcat "\n[INFO] Testando execucao em: " destTmp))
(setq resFluxo (sob-executar-fluxo sobTeste destTmp nil))

(if (and resFluxo (cdr (assoc "sucesso" resFluxo)))
  (progn
    (princ "\n[PASS] AUTOCAD-04: Fluxo de preparacao executado com sucesso.")
    (setq dwgGerado (cdr (assoc "BASE_DWG" resFluxo)))
    (if (and (findfile dwgGerado) (> (vl-file-size dwgGerado) 100))
      (princ (strcat "\n[PASS] AUTOCAD-05: Arquivo BASE_DWG validado fisicamente: " dwgGerado))
      (princ (strcat "\n[FAIL] AUTOCAD-05: BASE_DWG invalido ou inexistente: " dwgGerado))
    )
  )
  (princ (strcat "\n[FAIL] AUTOCAD-04: Falha no fluxo: " (vl-prin1-to-string resFluxo)))
)

;; TESTE 06: Proteção contra Pasta Existente (NÃO SOBRESCREVER)
(setq resExistente (sob-executar-fluxo sobTeste destTmp nil))
(if (and resExistente (null (cdr (assoc "sucesso" resExistente))) (= (cdr (assoc "status" resExistente)) "BLOQUEADO"))
  (princ "\n[PASS] AUTOCAD-06: Bloqueio de pasta existente validado (status BLOQUEADO).")
  (princ "\n[FAIL] AUTOCAD-06: Nao bloqueou pasta existente.")
)

(princ "\n[TESTE OPERACIONAL AUTOCAD] Concluido com sucesso!\n")
(command "_.QUIT")
