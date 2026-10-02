using System;
using System.Collections.Generic;
using System.Windows.Media;
using OxCad.Integration;

namespace OxCad
{
    public sealed class IntegrationUiItem
    {
        public string DisplayName { get; }
        public string StatusText { get; }
        public Brush StatusBackground { get; }
        public Brush StatusForeground { get; }

        public IntegrationUiItem(string displayName, string statusText, Brush background, Brush foreground)
        {
            DisplayName = displayName;
            StatusText = statusText;
            StatusBackground = background;
            StatusForeground = foreground;
        }
    }

    public partial class OxCadControl
    {
        private void InicializarSecaoIntegracoes()
        {
            try
            {
                var registry = IntegrationRegistry.CreateDefault();
                var items = new List<IntegrationUiItem>();

                var brushConfigured = new SolidColorBrush(Color.FromRgb(82, 183, 136));     // Verde
                var brushNotConfigured = new SolidColorBrush(Color.FromRgb(160, 160, 176)); // Cinza claro
                var bgConfigured = new SolidColorBrush(Color.FromRgb(26, 46, 38));          // Verde escuro
                var bgNotConfigured = new SolidColorBrush(Color.FromRgb(37, 37, 50));       // Cinza escuro

                // Selecionar os provedores requeridos pelo P2.4 na ordem canônica da especificação
                var idsDesejados = new[]
                {
                    "microsoft.graph",
                    "microsoft.entra",
                    "sharepoint",
                    "onedrive",
                    "sap",
                    "salesforce",
                    "rest",
                    "soap"
                };

                foreach (var id in idsDesejados)
                {
                    var provider = registry.Get(id);
                    if (provider == null)
                        continue;

                    var desc = provider.Descriptor;
                    string statusText = desc.ConfigurationStatus == ConfigurationStatus.Configured ? "Disponível" : "Não configurado";
                    var fg = desc.ConfigurationStatus == ConfigurationStatus.Configured ? brushConfigured : brushNotConfigured;
                    var bg = desc.ConfigurationStatus == ConfigurationStatus.Configured ? bgConfigured : bgNotConfigured;

                    items.Add(new IntegrationUiItem(desc.DisplayName, statusText, bg, fg));
                }

                if (ListaIntegracoes != null)
                {
                    ListaIntegracoes.ItemsSource = items;
                }
            }
            catch
            {
                // UI não bloqueante: falhas visuais não afetam o Core do OXCAD
            }
        }
    }
}
