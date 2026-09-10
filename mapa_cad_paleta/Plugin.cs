using System;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Runtime;
using acApp = Autodesk.AutoCAD.ApplicationServices.Application;

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
            try
            {
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
            catch
            {
                // Inicialização silenciosa e segura
            }
        }

        public void Terminate()
        {
            PaletteHost.OcultarPaleta();
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
    }
}
