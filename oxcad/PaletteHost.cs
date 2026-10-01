using System;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.Windows;

namespace OxCad
{
    /// <summary>
    /// Gerenciador singleton do ciclo de vida da Paleta nativa OXCAD no AutoCAD (PaletteSet).
    /// Garante que apenas uma instância exista e reabra de forma determinística.
    /// </summary>
    public static class PaletteHost
    {
        private static PaletteSet? _paletteSet;
        private static OxCadControl? _oxCadControl;

        /// <summary>
        /// GUID exclusivo e estável da paleta OXCAD.
        /// </summary>
        public static readonly Guid PaletteGuid = new Guid("8A4F1D9C-2B7E-4E6A-B35D-9F0A1C8E7B2D");

        /// <summary>
        /// Exibe ou cria a paleta nativa acoplada do AutoCAD com o controle OXCAD.
        /// </summary>
        public static void MostrarPaleta()
        {
            if (_paletteSet == null)
            {
                _paletteSet = new PaletteSet("OXCAD", PaletteGuid)
                {
                    Style = PaletteSetStyles.ShowAutoHideButton |
                            PaletteSetStyles.ShowCloseButton |
                            PaletteSetStyles.ShowPropertiesMenu,
                    MinimumSize = new System.Drawing.Size(320, 480),
                    Dock = DockSides.Right
                };

                _oxCadControl = new OxCadControl();
                _paletteSet.AddVisual("OXCAD", _oxCadControl);
            }

            _paletteSet.Visible = true;

            // Atualiza os dados de contexto para o desenho que estiver ativo no momento
            _oxCadControl?.AtualizarContexto();
        }

        /// <summary>
        /// Oculta a paleta OXCAD caso esteja visível.
        /// </summary>
        public static void OcultarPaleta()
        {
            if (_paletteSet != null)
            {
                _paletteSet.Visible = false;
            }
        }

        /// <summary>
        /// Recarrega o controle da paleta e atualiza o contexto ativo.
        /// </summary>
        public static void Recarregar()
        {
            if (_paletteSet != null && _paletteSet.Visible)
            {
                _oxCadControl?.AtualizarContexto();
            }
            else
            {
                MostrarPaleta();
            }
        }

        public static void NotificarDocumentoAtivoAlterado()
        {
            _oxCadControl?.NotificarDocumentoAtivoAlterado();
        }

        public static void NotificarDocumentoFechando(Document? document)
        {
            _oxCadControl?.NotificarDocumentoFechando(document);
        }

        public static void NotificarDocumentoSalvo(Document document)
        {
            _oxCadControl?.NotificarDocumentoSalvo(document);
        }
    }
}
