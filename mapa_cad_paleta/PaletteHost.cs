using System;
using Autodesk.AutoCAD.Windows;

namespace MapaCadPaleta
{
    /// <summary>
    /// Gerenciador do ciclo de vida da Paleta nativa do AutoCAD (PaletteSet).
    /// </summary>
    public static class PaletteHost
    {
        private static PaletteSet? _paletteSet;
        private static MapaControl? _mapaControl;
        private static readonly Guid PaletteGuid = new Guid("E4C23A4D-7E81-4C5D-912A-18F2E7D90B31");

        /// <summary>
        /// Exibe ou cria a paleta acoplada do AutoCAD com o mapa OSM.
        /// </summary>
        public static void MostrarPaleta()
        {
            if (_paletteSet == null)
            {
                _paletteSet = new PaletteSet("Cartografia OSM & Coordenadas", PaletteGuid)
                {
                    Style = PaletteSetStyles.ShowAutoHideButton |
                            PaletteSetStyles.ShowCloseButton |
                            PaletteSetStyles.ShowPropertiesMenu,
                    MinimumSize = new System.Drawing.Size(360, 520),
                    Dock = DockSides.Right
                };

                _mapaControl = new MapaControl();
                _paletteSet.AddVisual("Mapa OSM", _mapaControl);
            }

            _paletteSet.Visible = true;
        }

        /// <summary>
        /// Oculta a paleta.
        /// </summary>
        public static void OcultarPaleta()
        {
            if (_paletteSet != null)
            {
                _paletteSet.Visible = false;
            }
        }

        /// <summary>
        /// Recarrega o controle da paleta se estiver aberto.
        /// </summary>
        public static void Recarregar()
        {
            if (_paletteSet != null && _paletteSet.Visible)
            {
                MostrarPaleta();
            }
        }
    }
}
