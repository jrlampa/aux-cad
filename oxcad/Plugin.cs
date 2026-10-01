using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Runtime;
using acApp = Autodesk.AutoCAD.ApplicationServices.Application;

[assembly: ExtensionApplication(typeof(OxCad.Plugin))]

namespace OxCad
{
    /// <summary>
    /// Ponto de entrada da extensão C# (.NET API) do OXCAD para AutoCAD.
    /// Registra os comandos nativos e orquestra o ciclo de vida do plugin.
    /// </summary>
    public class Plugin : IExtensionApplication
    {
        private static readonly HashSet<Document> DocumentosObservados =
            new HashSet<Document>(DocumentReferenceComparer.Instance);

        public void Initialize()
        {
            try
            {
                acApp.DocumentManager.DocumentActivated += OnDocumentActivated;
                acApp.DocumentManager.DocumentCreated += OnDocumentCreated;
                acApp.DocumentManager.DocumentToBeDestroyed += OnDocumentToBeDestroyed;
                acApp.DocumentManager.DocumentDestroyed += OnDocumentDestroyed;

                int pid = System.Diagnostics.Process.GetCurrentProcess().Id;
                string runtime = System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription;
                string acadVer = acApp.Version.ToString();

                OxCadLogger.RegistrarSessaoInicio("0.6.0", acadVer, pid, runtime);

                Document? doc = acApp.DocumentManager.MdiActiveDocument;
                if (doc != null)
                {
                    ObservarDocumento(doc);
                    Editor ed = doc.Editor;
                    ed.WriteMessage("\n=======================================================");
                    ed.WriteMessage("\n [AUX CAD] Extensão OXCAD (.NET) 0.6.0 carregada!");
                    ed.WriteMessage("\n Digite OXCAD para abrir a paleta de contexto.");
                    ed.WriteMessage("\n Digite OXCAD_DIAGNOSTICO para diagnóstico de observabilidade.");
                    ed.WriteMessage("\n=======================================================\n");
                }
            }
            catch (System.Exception ex)
            {
                OxCadLogger.LogError("Falha ao inicializar extensão OXCAD", ex);
            }
        }

        public void Terminate()
        {
            try
            {
                acApp.DocumentManager.DocumentActivated -= OnDocumentActivated;
                acApp.DocumentManager.DocumentCreated -= OnDocumentCreated;
                acApp.DocumentManager.DocumentToBeDestroyed -= OnDocumentToBeDestroyed;
                acApp.DocumentManager.DocumentDestroyed -= OnDocumentDestroyed;
                foreach (Document document in DocumentosObservados)
                {
                    document.CommandEnded -= OnDocumentCommandEnded;
                    document.CommandCancelled -= OnDocumentCommandCancelled;
                }
                DocumentosObservados.Clear();

                OxCadLogger.RegistrarSessaoFim();
                PaletteHost.OcultarPaleta();
            }
            catch (System.Exception ex)
            {
                OxCadLogger.LogError("Falha ao descarregar extensão OXCAD", ex);
            }
        }

        private static void OnDocumentActivated(
            object sender,
            DocumentCollectionEventArgs eventArgs)
        {
            if (eventArgs.Document != null)
                ObservarDocumento(eventArgs.Document);
            PaletteHost.NotificarDocumentoAtivoAlterado();
        }

        private static void OnDocumentCreated(
            object sender,
            DocumentCollectionEventArgs eventArgs)
        {
            if (eventArgs.Document != null)
                ObservarDocumento(eventArgs.Document);
            if (ReferenceEquals(eventArgs.Document, acApp.DocumentManager.MdiActiveDocument))
                PaletteHost.NotificarDocumentoAtivoAlterado();
        }

        private static void OnDocumentToBeDestroyed(
            object sender,
            DocumentCollectionEventArgs eventArgs)
        {
            if (eventArgs.Document != null)
            {
                try
                {
                    OxCadExecutionRegistry.CancelarComandosNativosDoDwg(
                        eventArgs.Document.Database.FingerprintGuid,
                        "DWG fechado durante comando AutoCAD.");
                }
                catch (System.Exception ex)
                {
                    OxCadLogger.LogError("Falha ao cancelar execução no fechamento do DWG", ex);
                }
            }
            PaletteHost.NotificarDocumentoFechando(eventArgs.Document);
            if (eventArgs.Document != null)
                DesobservarDocumento(eventArgs.Document);
        }

        private static void OnDocumentDestroyed(
            object sender,
            DocumentDestroyedEventArgs eventArgs)
        {
            PaletteHost.NotificarDocumentoAtivoAlterado();
        }

        private static void ObservarDocumento(Document document)
        {
            if (DocumentosObservados.Add(document))
            {
                document.CommandEnded += OnDocumentCommandEnded;
                document.CommandCancelled += OnDocumentCommandCancelled;
            }
        }

        private static void DesobservarDocumento(Document document)
        {
            if (DocumentosObservados.Remove(document))
            {
                document.CommandEnded -= OnDocumentCommandEnded;
                document.CommandCancelled -= OnDocumentCommandCancelled;
            }
        }

        private static void OnDocumentCommandEnded(object sender, CommandEventArgs eventArgs)
        {
            if (sender is not Document document)
                return;

            string command = (eventArgs.GlobalCommandName ?? string.Empty)
                .Trim()
                .TrimStart('_', '.')
                .ToUpperInvariant();
            try
            {
                OxCadExecutionRegistry.FinalizarComandoNativo(
                    document.Database.FingerprintGuid,
                    command,
                    OxCadExecutionState.Concluido,
                    $"Comando CAD {command} concluído.");
            }
            catch (System.Exception ex)
            {
                OxCadLogger.LogError($"Falha ao finalizar comando CAD {command}", ex);
            }

            if (command is "SAVE" or "QSAVE" or "SAVEAS" or "SAVEALL")
                PaletteHost.NotificarDocumentoSalvo(document);
        }

        private static void OnDocumentCommandCancelled(object sender, CommandEventArgs eventArgs)
        {
            if (sender is not Document document)
                return;

            string command = (eventArgs.GlobalCommandName ?? string.Empty)
                .Trim()
                .TrimStart('_', '.')
                .ToUpperInvariant();
            try
            {
                OxCadExecutionRegistry.FinalizarComandoNativo(
                    document.Database.FingerprintGuid,
                    command,
                    OxCadExecutionState.Cancelado,
                    $"Comando CAD {command} cancelado pelo usuário.");
            }
            catch (System.Exception ex)
            {
                OxCadLogger.LogError($"Falha ao cancelar execução do comando CAD {command}", ex);
            }
        }

        private sealed class DocumentReferenceComparer : IEqualityComparer<Document>
        {
            public static readonly DocumentReferenceComparer Instance = new();

            public bool Equals(Document? left, Document? right)
                => ReferenceEquals(left, right);

            public int GetHashCode(Document document)
                => RuntimeHelpers.GetHashCode(document);
        }

        /// <summary>
        /// Comando principal para exibir e trazer para frente a Paleta lateral OXCAD.
        /// </summary>
        [CommandMethod("OXCAD")]
        public void CmdAbrirOxCad()
        {
            try
            {
                OxCadLogger.LogInfo("Comando OXCAD acionado via linha de comando.", action: "oxcad.abrir");
                PaletteHost.MostrarPaleta();
            }
            catch (System.Exception ex)
            {
                OxCadLogger.LogError("Falha ao abrir paleta OXCAD", ex, action: "oxcad.abrir");
                try
                {
                    Document? doc = acApp.DocumentManager.MdiActiveDocument;
                    doc?.Editor?.WriteMessage($"\n[OXCAD ERRO] Falha ao abrir paleta: {ex.Message}\n");
                }
                catch
                {
                    // Fallback
                }
            }
        }

        /// <summary>
        /// Comando para fechar ou ocultar a Paleta OXCAD.
        /// </summary>
        [CommandMethod("FECHAR_OXCAD")]
        public void CmdFecharOxCad()
        {
            try
            {
                OxCadLogger.LogInfo("Comando FECHAR_OXCAD acionado.", action: "oxcad.fechar");
                PaletteHost.OcultarPaleta();
            }
            catch (System.Exception ex)
            {
                OxCadLogger.LogError("Falha ao ocultar paleta OXCAD", ex, action: "oxcad.fechar");
            }
        }

        /// <summary>
        /// Comando para recarregar o contexto na Paleta OXCAD.
        /// </summary>
        [CommandMethod("RECARREGAR_OXCAD")]
        public void CmdRecarregarOxCad()
        {
            try
            {
                OxCadLogger.LogInfo("Comando RECARREGAR_OXCAD acionado.", action: "oxcad.recarregar");
                PaletteHost.Recarregar();
            }
            catch (System.Exception ex)
            {
                OxCadLogger.LogError("Falha ao recarregar paleta OXCAD", ex, action: "oxcad.recarregar");
            }
        }

        /// <summary>
        /// Comando para exibir diagnóstico rápido de observabilidade e status do OXCAD.
        /// </summary>
        [CommandMethod("OXCAD_DIAGNOSTICO")]
        public void CmdDiagnosticoOxCad()
        {
            try
            {
                Document? doc = acApp.DocumentManager.MdiActiveDocument;
                Editor? ed = doc?.Editor;
                if (ed == null) return;

                int pid = System.Diagnostics.Process.GetCurrentProcess().Id;
                string root = WorkspaceService.ObterDiretorioRaizProjeto(doc?.Name);
                string logDir = OxCadLogger.ObterDiretorioLogs(doc?.Name);
                string logApp = System.IO.Path.Combine(logDir, "application.jsonl");
                long logBytes = System.IO.File.Exists(logApp) ? new System.IO.FileInfo(logApp).Length : 0;
                string pyExe = WorkspaceService.ObterExecutavelPython();
                bool pyOk = System.IO.File.Exists(pyExe);

                ed.WriteMessage("\n=======================================================");
                ed.WriteMessage("\n [OXCAD] DIAGNÓSTICO DE OBSERVABILIDADE & STATUS");
                ed.WriteMessage("\n=======================================================");
                ed.WriteMessage($"\n Versão OXCAD:     0.6.0");
                ed.WriteMessage($"\n Versão AutoCAD:   {acApp.Version}");
                ed.WriteMessage($"\n Host PID:         {pid}");
                ed.WriteMessage($"\n .NET Runtime:     {System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription}");
                ed.WriteMessage($"\n Diretório Raiz:   {root}");
                ed.WriteMessage($"\n Pasta de Logs:    {logDir}");
                ed.WriteMessage($"\n Arquivo de Log:   application.jsonl ({logBytes:N0} bytes)");
                ed.WriteMessage($"\n Status Python:    {(pyOk ? "OK" : "NÃO ENCONTRADO")} ({pyExe})");
                ed.WriteMessage("\n-------------------------------------------------------");
                ed.WriteMessage("\n ÚLTIMOS EVENTOS REGISTRADOS:");

                var ultimos = OxCadLogger.ObterUltimosEventos(5, doc?.Name);
                if (ultimos.Count == 0)
                {
                    ed.WriteMessage("\n (Nenhum evento registrado ainda)");
                }
                else
                {
                    foreach (var linha in ultimos)
                    {
                        ed.WriteMessage($"\n {linha}");
                    }
                }
                ed.WriteMessage("\n=======================================================\n");

                OxCadLogger.LogInfo("Comando OXCAD_DIAGNOSTICO executado com sucesso.", action: "oxcad.diagnostico");
            }
            catch (System.Exception ex)
            {
                OxCadLogger.LogError("Falha ao executar OXCAD_DIAGNOSTICO", ex);
            }
        }
    }
}
