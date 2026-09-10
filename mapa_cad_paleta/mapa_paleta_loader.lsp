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

(defun c:mapa-paleta-load-dll ( / dll-path )
  "Carrega a DLL da paleta em memória via NETLOAD nativo."
  (setq dll-path (c:mapa-paleta-get-dll-path))
  (if (and dll-path (findfile dll-path))
    (progn
      (princ (strcat "\n[AUX CAD] Carregando Paleta OSM: " (vl-filename-nxname dll-path) "..."))
      (setvar "FILEDIA" 0)
      (vl-catch-all-apply '(lambda () (command "_.NETLOAD" dll-path)))
      (setvar "FILEDIA" 1)
      t)
    (progn
      (princ "\n[AUX CAD ERRO] DLL MapaCadPaleta.dll não encontrada em bin/Release.")
      (princ "\nExecute 'dotnet build mapa_cad_paleta/MapaCadPaleta.csproj -c Release' para compilar.")
      nil))
)

;;; Comandos de Acesso Rápido no AutoCAD
(defun c:MAPAPALETA ()
  "Abre a Paleta Cartográfica OSM integrada no AutoCAD."
  (if (null (fboundp 'c:MAPAPALETA-NET))
    (c:mapa-paleta-load-dll))
  (vl-catch-all-apply '(lambda () (command "MAPAPALETA")))
  (princ)
)

(defun c:OSMPALETA () (c:MAPAPALETA))
(defun c:PALETAMAPA () (c:MAPAPALETA))

(defun c:RECARREGAR_MAPAPALETA ()
  "Recarrega a paleta e recarrega seus assets web."
  (c:mapa-paleta-load-dll)
  (vl-catch-all-apply '(lambda () (command "RECARREGAR_MAPAPALETA")))
  (princ "\n[AUX CAD] Paleta OSM recarregada.")
  (princ)
)

(princ "\n[AUX CAD] Módulo Paleta OSM (.NET) carregado. Digite MAPAPALETA.")
(princ)
