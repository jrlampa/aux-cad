;;; ==============================================================================
;;; AUX CAD - Carregador e Orquestrador da Paleta OXCAD C# (.NET)
;;; Compatibilidade: AutoCAD 2018 até 2026+ (net48 e net8.0-windows)
;;; ==============================================================================

(vl-load-com)

;; Funções utilitárias locais autossuficientes
(if (not (fboundp 'stringp))
  (defun stringp (x) (= (type x) 'STR)))

(if (not (fboundp 'vl-filename-nxname))
  (defun vl-filename-nxname (filename)
    (if (stringp filename)
      (strcat (vl-filename-base filename) (vl-filename-extension filename))
      "")))

(defun c:oxcad-get-dll-path ( / acad-ver v-num base-dir rel-path full-path env-root )
  "Determina o caminho da DLL compilada baseado na versao ativa do AutoCAD."
  (setq acad-ver (getvar "ACADVER"))
  (setq v-num (if (stringp acad-ver) (atof acad-ver) 25.0))
  (setq env-root (getenv "AUXCAD_ROOT"))
  
  ;; Resolucao dinamica e agnostica do diretorio base do modulo oxcad
  (setq base-dir
    (cond
      ;; 1. Se *aux-cad-root* existir e for string valida
      ((and (boundp '*aux-cad-root*) (stringp *aux-cad-root*) (> (strlen *aux-cad-root*) 0))
       (strcat *aux-cad-root* "oxcad"))
      ;; 2. Se a variavel de ambiente AUXCAD_ROOT estiver definida
      ((and (stringp env-root) (> (strlen env-root) 0))
       (strcat env-root "\\oxcad"))
      ;; 3. Se encontrar oxcad/oxcad_loader.lsp no search path
      ((findfile "oxcad/oxcad_loader.lsp")
       (vl-filename-directory (findfile "oxcad/oxcad_loader.lsp")))
      ;; 4. Se encontrar oxcad_loader.lsp no search path
      ((findfile "oxcad_loader.lsp")
       (vl-filename-directory (findfile "oxcad_loader.lsp")))
      ;; 5. Se aux_cad_menu.cuix estiver no search path
      ((findfile "aux_cad_menu.cuix")
       (strcat (vl-filename-directory (findfile "aux_cad_menu.cuix")) "\\oxcad"))
      ;; 6. Fallback pelo DWGPREFIX
      (t (strcat (getvar "DWGPREFIX") "oxcad"))
    )
  )
  
  ;; AutoCAD 2025/2026+ (ACADVER >= 25.0) roda em .NET 8.0
  ;; AutoCAD 2018-2024 (ACADVER < 25.0) roda em .NET Framework 4.8
  (if (>= v-num 25.0)
    (setq rel-path "\\bin\\Release\\net8.0-windows\\OxCadPaleta.dll")
    (setq rel-path "\\bin\\Release\\net48\\OxCadPaleta.dll"))
  
  (setq full-path (strcat base-dir rel-path))
  
  (if (findfile full-path)
    full-path
    ;; Fallback: tentar compilacao Debug
    (progn
      (if (>= v-num 25.0)
        (setq rel-path "\\bin\\Debug\\net8.0-windows\\OxCadPaleta.dll")
        (setq rel-path "\\bin\\Debug\\net48\\OxCadPaleta.dll"))
      (setq full-path (strcat base-dir rel-path))
      (if (findfile full-path) full-path nil)))
)

(defun c:oxcad-load-dll ( / dll-path dll-dir curr-path dll-name )
  "Carrega a DLL da paleta OXCAD em memoria via NETLOAD nativo."
  (setq dll-path (c:oxcad-get-dll-path))
  (if (and dll-path (stringp dll-path) (findfile dll-path))
    (progn
      (setq dll-dir (vl-filename-directory dll-path))
      (setq curr-path (getenv "PATH"))
      (if (and (stringp curr-path) (not (vl-string-search dll-dir curr-path)))
        (setenv "PATH" (strcat dll-dir ";" curr-path)))
      (setq dll-name (strcat (vl-filename-base dll-path) (vl-filename-extension dll-path)))
      (princ (strcat "\n[AUX CAD] Carregando Paleta OXCAD: " dll-name "..."))
      (setvar "FILEDIA" 0)
      (vl-catch-all-apply '(lambda () (vl-cmdf "_.NETLOAD" dll-path)))
      (setvar "FILEDIA" 1)
      t)
    (progn
      (princ "\n[AUX CAD ERRO] DLL OxCadPaleta.dll nao encontrada em bin/Release.")
      (princ "\nExecute 'dotnet build oxcad/OxCadPaleta.csproj -c Release' para compilar.")
      nil))
)

;;; Comandos de Acesso Rapido no AutoCAD
(defun c:OXCAD ()
  "Abre a Paleta lateral OXCAD integrada no AutoCAD."
  (c:oxcad-load-dll)
  (vl-catch-all-apply '(lambda () (vl-cmdf "_.OXCAD")))
  (princ)
)

(defun c:FECHAR_OXCAD ()
  "Fecha ou oculta a Paleta OXCAD."
  (vl-catch-all-apply '(lambda () (vl-cmdf "_.FECHAR_OXCAD")))
  (princ "\n[AUX CAD] Paleta OXCAD fechada.")
  (princ)
)

(defun c:RECARREGAR_OXCAD ()
  "Recarrega o contexto ativo na Paleta OXCAD."
  (c:oxcad-load-dll)
  (vl-catch-all-apply '(lambda () (vl-cmdf "_.RECARREGAR_OXCAD")))
  (princ "\n[AUX CAD] Paleta OXCAD recarregada.")
  (princ)
)

(princ "\n[AUX CAD] Modulo Paleta OXCAD (.NET) registrado. Digite OXCAD.")
(princ)
