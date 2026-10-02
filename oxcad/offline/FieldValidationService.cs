using System;
using System.Collections.Generic;
using System.Linq;

namespace OxCad.Offline
{
    public sealed class FieldValidationService
    {
        public static List<FieldValidationItem> CreateDefaultChecklist(
            string sobId,
            string projectRoot,
            string dwgPath,
            string databaseFingerprint,
            string operatorName = "operador_campo")
        {
            var now = DateTime.UtcNow;
            var items = new List<FieldValidationItem>
            {
                new FieldValidationItem(
                    Guid.NewGuid().ToString("N"),
                    sobId, projectRoot, dwgPath, databaseFingerprint,
                    now, operatorName, "Identidade", "SOB identificado", "CONFIRMADO", "CONFIRMADO",
                    FieldValidationStatus.Ok),

                new FieldValidationItem(
                    Guid.NewGuid().ToString("N"),
                    sobId, projectRoot, dwgPath, databaseFingerprint,
                    now, operatorName, "Identidade", "DWG identificado", "CONFIRMADO", "CONFIRMADO",
                    FieldValidationStatus.Ok),

                new FieldValidationItem(
                    Guid.NewGuid().ToString("N"),
                    sobId, projectRoot, dwgPath, databaseFingerprint,
                    now, operatorName, "Identidade", "Fingerprint confirmado", "CONFIRMADO", "CONFIRMADO",
                    FieldValidationStatus.Ok),

                new FieldValidationItem(
                    Guid.NewGuid().ToString("N"),
                    sobId, projectRoot, dwgPath, databaseFingerprint,
                    now, operatorName, "Projeto", "Arquivos necessários disponíveis", "DISPONÍVEL", "DISPONÍVEL",
                    FieldValidationStatus.Ok),

                new FieldValidationItem(
                    Guid.NewGuid().ToString("N"),
                    sobId, projectRoot, dwgPath, databaseFingerprint,
                    now, operatorName, "Projeto", "Evidência complementar ausente", "COMPLETO", "PENDENTE",
                    FieldValidationStatus.Alerta),

                new FieldValidationItem(
                    Guid.NewGuid().ToString("N"),
                    sobId, projectRoot, dwgPath, databaseFingerprint,
                    now, operatorName, "Campo", "Item verificado em campo", "CONFORME", "CONFORME",
                    FieldValidationStatus.Ok),

                new FieldValidationItem(
                    Guid.NewGuid().ToString("N"),
                    sobId, projectRoot, dwgPath, databaseFingerprint,
                    now, operatorName, "Campo", "Item divergente identificado", "CONFORME", "DIVERGENTE",
                    FieldValidationStatus.Erro),

                new FieldValidationItem(
                    Guid.NewGuid().ToString("N"),
                    sobId, projectRoot, dwgPath, databaseFingerprint,
                    now, operatorName, "Campo", "Item ainda não vistoriado", "VISTORIADO", "PENDENTE",
                    FieldValidationStatus.NaoVerificado)
            };

            return items;
        }

        public static FieldChecklistSummary Summarize(IEnumerable<FieldValidationItem> items)
        {
            var summary = new FieldChecklistSummary();
            foreach (var item in items)
            {
                summary.Total++;
                switch (item.Status)
                {
                    case FieldValidationStatus.Ok:
                        summary.Ok++;
                        break;
                    case FieldValidationStatus.Alerta:
                        summary.Alerta++;
                        break;
                    case FieldValidationStatus.Erro:
                        summary.Erro++;
                        break;
                    case FieldValidationStatus.NaoVerificado:
                        summary.NaoVerificado++;
                        break;
                    case FieldValidationStatus.NaoAplicavel:
                        summary.NaoAplicavel++;
                        break;
                    case FieldValidationStatus.NaoDisponivel:
                        summary.NaoDisponivel++;
                        break;
                }
            }
            return summary;
        }
    }
}
