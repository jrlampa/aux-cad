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
                Document? doc = acApp.DocumentManager.MdiActiveDocument;
                if (doc != null)
                {
                    Editor ed = doc.Editor;
                    ed.WriteMessage("\n=======================================================");
                    ed.WriteMessage("\n [AUX CAD] Extensão OXCAD (.NET) carregada com sucesso!");
                    ed.WriteMessage("\n Digite OXCAD para abrir a paleta de contexto.");
                    ed.WriteMessage("\n=======================================================\n");
                }
            }
            catch
            {
                // Inicialização silenciosa e protegida
            }
        }

        public void Terminate()
        {
            try
            {
                PaletteHost.OcultarPaleta();
            }
            catch
            {
                // Finalização silenciosa
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
                PaletteHost.MostrarPaleta();
            }
            catch (System.Exception ex)
            {
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
                PaletteHost.OcultarPaleta();
            }
            catch
            {
                // Proteção contra falhas no fechamento
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
                PaletteHost.Recarregar();
            }
            catch
            {
                // Proteção contra falhas no recarregamento
            }
        }
    }
}
