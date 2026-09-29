;;; ==============================================================================
;;; AUX CAD - Carregador e Orquestrador da Paleta Cartográfica OSM C# (.NET)
;;; Compatibilidade: AutoCAD 2018 até 2026+ (net48 e net8.0-windows)
;;; ==============================================================================

(vl-load-com)

(defun c:mapa-paleta-get-dll-path ( / acad-ver v-num base-dir rel-path full-path )
  "Determina o caminho da DLL compilada baseado na versão ativa do AutoCAD."
  (setq acad-ver (getvar "ACADVER"))
  (setq v-num (atof acad-ver))
  
  ;; Pasta raiz deste arquivo
  (setq base-dir (if load-aux-find-root
                   (strcat (load-aux-find-root) "\\mapa_cad_paleta")
                   (vl-filename-directory (findfile "mapa_paleta_loader.lsp"))))
  
  (if (null base-dir)
    (setq base-dir (strcat (getvar "DWGPREFIX") "mapa_cad_paleta")))
  
  ;; AutoCAD 2025/2026+ (ACADVER >= 25.0) roda em .NET 8.0
  ;; AutoCAD 2018-2024 (ACADVER < 25.0) roda em .NET Framework 4.8
  (if (>= v-num 25.0)
    (setq rel-path "\\bin\\Release\\net8.0-windows\\MapaCadPaleta.dll")
    (setq rel-path "\\bin\\Release\\net48\\MapaCadPaleta.dll"))
  
  (setq full-path (strcat base-dir rel-path))
  
  (if (findfile full-path)
    full-path
    ;; Fallback: tentar compilação Debug
    (progn
      (if (>= v-num 25.0)
        (setq rel-path "\\bin\\Debug\\net8.0-windows\\MapaCadPaleta.dll")
        (setq rel-path "\\bin\\Debug\\net48\\MapaCadPaleta.dll"))
      (setq full-path (strcat base-dir rel-path))
      (if (findfile full-path) full-path nil)))
)

(defun c:mapa-paleta-load-dll ( / dll-path dll-dir native-dir curr-path )
  "Carrega a DLL da paleta em memória via NETLOAD nativo."
  (setq dll-path (c:mapa-paleta-get-dll-path))
  (if (and dll-path (findfile dll-path))
    (progn
      ;; Adiciona a pasta da DLL e runtimes ao PATH do processo do AutoCAD para resolver WebView2Loader.dll
      (setq dll-dir (vl-filename-directory dll-path))
      (setq native-dir (strcat dll-dir "\\runtimes\\win-x64\\native"))
      (setq curr-path (getenv "PATH"))
      (if (and curr-path (not (vl-string-search dll-dir curr-path)))
        (setenv "PATH" (strcat dll-dir ";" native-dir ";" curr-path)))
      (princ (strcat "\n[AUX CAD] Carregando Paleta OSM: " (vl-filename-nxname dll-path) "..."))
      (setvar "FILEDIA" 0)
      (vl-catch-all-apply '(lambda () (command "_.NETLOAD" dll-path)))
      (setvar "FILEDIA" 1)
      (if (getcname "AUXCAD_BIND_SOB")
        t
        (progn
          (princ "\n[AUX CAD ERRO] NETLOAD terminou, mas AUXCAD_BIND_SOB não foi registrado.")
          nil)))
    (progn
      (princ "\n[AUX CAD ERRO] DLL MapaCadPaleta.dll não encontrada em bin/Release.")
      (princ "\nExecute 'dotnet build mapa_cad_paleta/MapaCadPaleta.csproj -c Release' para compilar.")
      nil))
)

;;; Comandos de Acesso Rápido no AutoCAD
(defun c:MAPAPALETA ( / command-result )
  "Abre a Paleta Cartográfica OSM integrada no AutoCAD."
  (if (or (getcname "AUXCAD_BIND_SOB")
          (c:mapa-paleta-load-dll))
    (progn
      (setq command-result
        (vl-catch-all-apply '(lambda () (command "MAPAPALETA"))))
      (if (vl-catch-all-error-p command-result)
        (princ (strcat "\n[AUX CAD ERRO] Falha ao abrir a paleta: "
                       (vl-catch-all-error-message command-result)))))
    (princ "\n[AUX CAD ERRO] A paleta não será aberta porque a DLL não foi carregada."))
  (princ)
)

(defun c:OSMPALETA () (c:MAPAPALETA))
(defun c:PALETAMAPA () (c:MAPAPALETA))

(defun c:RECARREGAR_MAPAPALETA ( / command-result )
  "Recarrega a paleta e recarrega seus assets web."
  (if (or (getcname "AUXCAD_BIND_SOB")
          (c:mapa-paleta-load-dll))
    (progn
      (setq command-result
        (vl-catch-all-apply '(lambda () (command "RECARREGAR_MAPAPALETA"))))
      (if (vl-catch-all-error-p command-result)
        (princ (strcat "\n[AUX CAD ERRO] Falha ao recarregar a paleta: "
                       (vl-catch-all-error-message command-result)))
        (princ "\n[AUX CAD] Solicitação de recarga da paleta concluída.")))
    (princ "\n[AUX CAD ERRO] Recarga cancelada porque a DLL não foi carregada."))
  (princ)
)

(princ "\n[AUX CAD] Módulo Paleta OSM (.NET) carregado. Digite MAPAPALETA.")
(princ)
