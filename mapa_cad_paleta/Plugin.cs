using System;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Runtime;
using acApp = Autodesk.AutoCAD.ApplicationServices.Application;
using System.IO;
using System.Text.Json;

[assembly: ExtensionApplication(typeof(MapaCadPaleta.Plugin))]

namespace MapaCadPaleta
{
    /// <summary>
    /// Ponto de entrada da extensão C# do AutoCAD (.NET API).
    /// </summary>
    public class Plugin : IExtensionApplication
    {
        public void Initialize()
        {
            acApp.DocumentManager.DocumentActivated += OnDocumentActivated;
            CadBridge.ProjectScopeChanged += PaletteHost.NotifyProjectScopeChanged;
            CadBridge.NotifyActiveDocumentChanged();

            Document? doc = acApp.DocumentManager.MdiActiveDocument;
            if (doc != null)
            {
                Editor ed = doc.Editor;
                ed.WriteMessage("\n=======================================================");
                ed.WriteMessage("\n [AUX CAD] Paleta Cartográfica OSM (.NET) carregada!");
                ed.WriteMessage("\n Digite MAPAPALETA ou OSMPALETA para abrir o mapa.");
                ed.WriteMessage("\n=======================================================\n");
            }
        }

        public void Terminate()
        {
            acApp.DocumentManager.DocumentActivated -= OnDocumentActivated;
            CadBridge.ProjectScopeChanged -= PaletteHost.NotifyProjectScopeChanged;
            PaletteHost.OcultarPaleta();
        }

        private static void OnDocumentActivated(object sender, DocumentCollectionEventArgs eventArgs)
        {
            CadBridge.NotifyActiveDocumentChanged();
        }

        /// <summary>
        /// Comando para exibir a Paleta com o Mapa OSM no AutoCAD.
        /// </summary>
        [CommandMethod("MAPAPALETA")]
        [CommandMethod("OSMPALETA")]
        [CommandMethod("MAPACAD")]
        public void CmdAbrirMapaPaleta()
        {
            PaletteHost.MostrarPaleta();
        }

        /// <summary>
        /// Comando para ocultar a Paleta.
        /// </summary>
        [CommandMethod("FECHAR_MAPAPALETA")]
        public void CmdFecharMapaPaleta()
        {
            PaletteHost.OcultarPaleta();
        }

        /// <summary>
        /// Comando para recarregar a Paleta.
        /// </summary>
        [CommandMethod("RECARREGAR_MAPAPALETA")]
        public void CmdRecarregarMapaPaleta()
        {
            PaletteHost.Recarregar();
        }

        [CommandMethod("AUXCAD_BIND_SOB")]
        public void CmdBindSobToActiveDrawing()
        {
            Document? document = acApp.DocumentManager.MdiActiveDocument;
            if (document == null)
                throw new InvalidOperationException("Nenhum documento DWG ativo para vincular.");

            var sobIdOptions = new PromptStringOptions("\nSOB_ID validado: ")
            {
                AllowSpaces = false
            };
            PromptResult sobIdResult = document.Editor.GetString(sobIdOptions);
            if (sobIdResult.Status != PromptStatus.OK)
                throw new InvalidOperationException("Vinculação do ProjectScope cancelada.");

            var pathOptions = new PromptStringOptions("\nCaminho BASE_DWG validado: ")
            {
                AllowSpaces = true
            };
            PromptResult pathResult = document.Editor.GetString(pathOptions);
            if (pathResult.Status != PromptStatus.OK)
                throw new InvalidOperationException("Vinculação do ProjectScope cancelada.");

            if (!ProjectScopeContract.TryNormalizeSobId(sobIdResult.StringResult, out string normalizedId))
                throw new InvalidOperationException("SOB_ID inválido.");

            string expectedPath = Path.GetFullPath(pathResult.StringResult);
            string activePath = Path.GetFullPath(document.Name);
            if (!string.Equals(expectedPath, activePath, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("O DWG ativo não corresponde ao BASE_DWG validado.");

            ValidateCompletedSobManifest(expectedPath, normalizedId);
            DwgProjectScopeStore.Write(document.Database, normalizedId);
            CadBridge.NotifyActiveDocumentChanged();
            document.Editor.WriteMessage($"\n[AUXCAD] ProjectScope vinculado: {normalizedId}");
        }

        private static void ValidateCompletedSobManifest(string baseDwgPath, string expectedSobId)
        {
            string sobRoot = Path.GetDirectoryName(baseDwgPath)
                ?? throw new InvalidOperationException("Não foi possível localizar a raiz da SOB.");
            string manifestPath = Path.Combine(sobRoot, ".sob_state.json");
            if (!File.Exists(manifestPath))
                throw new FileNotFoundException("Manifesto .sob_state.json da SOB não encontrado.", manifestPath);

            using JsonDocument manifest = JsonDocument.Parse(File.ReadAllText(manifestPath));
            JsonElement root = manifest.RootElement;
            if (!root.TryGetProperty("status", out JsonElement status) ||
                status.ValueKind != JsonValueKind.String ||
                !string.Equals(status.GetString(), "CONCLUÍDO", StringComparison.Ordinal))
                throw new InvalidOperationException("O manifesto da SOB não confirma uma preparação concluída.");

            if (!root.TryGetProperty("sob_id", out JsonElement sobId) ||
                sobId.ValueKind != JsonValueKind.String ||
                !ProjectScopeContract.TryNormalizeSobId(sobId.GetString(), out string manifestSobId) ||
                !string.Equals(manifestSobId, expectedSobId, StringComparison.Ordinal))
                throw new InvalidOperationException("O SOB_ID informado não corresponde ao manifesto da SOB.");

            if (!root.TryGetProperty("base_dwg", out JsonElement baseDwg) ||
                baseDwg.ValueKind != JsonValueKind.String ||
                string.IsNullOrWhiteSpace(baseDwg.GetString()))
                throw new InvalidOperationException("O manifesto da SOB não contém BASE_DWG válido.");

            string manifestDwgPath = baseDwg.GetString()!;
            if (!Path.IsPathRooted(manifestDwgPath))
                manifestDwgPath = Path.Combine(sobRoot, manifestDwgPath);
            manifestDwgPath = Path.GetFullPath(manifestDwgPath);
            if (!string.Equals(manifestDwgPath, baseDwgPath, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("O BASE_DWG informado não corresponde ao manifesto da SOB.");
        }
    }
}
