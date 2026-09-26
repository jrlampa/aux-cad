using System;
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
        public void Initialize()
        {
            try
            {
                int pid = System.Diagnostics.Process.GetCurrentProcess().Id;
                string runtime = System.Runtime.InteropServices.RuntimeInformation.FrameworkDescription;
                string acadVer = acApp.Version.ToString();

                OxCadLogger.RegistrarSessaoInicio("0.6.0", acadVer, pid, runtime);

                Document? doc = acApp.DocumentManager.MdiActiveDocument;
                if (doc != null)
                {
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
                OxCadLogger.RegistrarSessaoFim();
                PaletteHost.OcultarPaleta();
            }
            catch (System.Exception ex)
            {
                OxCadLogger.LogError("Falha ao descarregar extensão OXCAD", ex);
            }
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
