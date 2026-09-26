using System;
using System.IO;
using System.Text.RegularExpressions;

namespace OxCad
{
    /// <summary>
    /// Modelo de dados com as informações de contexto do desenho (DWG) ativo.
    /// </summary>
    public class DwgContextInfo
    {
        public bool Salvo { get; set; }
        public string DwgNome { get; set; } = string.Empty;
        public string DwgCaminho { get; set; } = string.Empty;
        public string DwgDiretorio { get; set; } = string.Empty;
        public string SobId { get; set; } = string.Empty;
        public string Status { get; set; } = string.Empty;
    }

    /// <summary>
    /// Serviço de extração e análise de contexto a partir do caminho do DWG ativo.
    /// Não depende de bibliotecas externas e segue as convenções do Workspace.
    /// </summary>
    public static class DwgContextExtractor
    {
        private static readonly Regex RegexSobPrefixo = new Regex(@"SOB_([A-Za-z0-9_\-]+)", RegexOptions.Compiled);
        private static readonly Regex RegexDwgBase = new Regex(@"[A-Za-z]{2}_([A-Za-z0-9_\-]+)_DESENHO", RegexOptions.Compiled);
        private static readonly Regex RegexSobAlfa = new Regex(@"(?:^|[^A-Za-z0-9])([A-Za-z][0-9]{8,12})(?:[^A-Za-z0-9]|$)", RegexOptions.Compiled);

        /// <summary>
        /// Extrai o identificador da SOB a partir de um texto (nome de arquivo ou diretório).
        /// </summary>
        public static string? ExtrairSob(string? texto)
        {
            if (string.IsNullOrWhiteSpace(texto))
                return null;

            // 1. Padrão oficial SOB_...
            var matchPrefixo = RegexSobPrefixo.Match(texto!);
            if (matchPrefixo.Success)
            {
                string candidato = matchPrefixo.Groups[1].Value.ToUpperInvariant();
                if (ValidarSobId(candidato))
                    return candidato;
            }

            // 2. Padrão oficial de DWG {BASE}_{SOB}_DESENHO
            var matchDwg = RegexDwgBase.Match(texto!);
            if (matchDwg.Success)
            {
                string candidato = matchDwg.Groups[1].Value.ToUpperInvariant();
                if (ValidarSobId(candidato))
                    return candidato;
            }

            // 3. Padrão alfanumérico padrão de SOB da concessionária (ex: A057349839)
            var matchAlfa = RegexSobAlfa.Match(texto!);
            if (matchAlfa.Success)
            {
                string candidato = matchAlfa.Groups[1].Value.ToUpperInvariant();
                if (ValidarSobId(candidato))
                    return candidato;
            }

            return null;
        }

        /// <summary>
        /// Validação sintática do identificador puro de SOB.
        /// </summary>
        public static bool ValidarSobId(string? sobId)
        {
            if (string.IsNullOrWhiteSpace(sobId))
                return false;

            string s = sobId!.Trim().ToUpperInvariant();
            if (s.StartsWith("SOB_"))
                return false;

            if (s.Length < 3 || s.Length > 30)
                return false;

            foreach (char c in s)
            {
                bool valido = (c >= 'A' && c <= 'Z') ||
                              (c >= '0' && c <= '9') ||
                              c == '_' || c == '-';
                if (!valido) return false;
            }

            return true;
        }

        /// <summary>
        /// Constrói o contexto a partir do caminho físico do arquivo DWG.
        /// Trata arquivos não salvos de forma segura e sem lançar exceções.
        /// </summary>
        public static DwgContextInfo ConstruirContexto(string? fullPath)
        {
            var info = new DwgContextInfo();

            try
            {
                if (string.IsNullOrWhiteSpace(fullPath) || !File.Exists(fullPath))
                {
                    info.Salvo = false;
                    info.Status = "Desenho ainda não salvo.";
                    info.DwgNome = "Desenho ainda não salvo.";
                    info.DwgCaminho = "-";
                    info.DwgDiretorio = "-";
                    info.SobId = "-";
                    return info;
                }

                info.Salvo = true;
                info.DwgCaminho = fullPath!;
                info.DwgNome = Path.GetFileName(fullPath!) ?? "-";
                info.DwgDiretorio = Path.GetDirectoryName(fullPath!) ?? "-";

                // Tenta extrair SOB do nome do arquivo
                string? sob = ExtrairSob(info.DwgNome);

                // Se não encontrar no nome do arquivo, tenta no nome do diretório do projeto
                if (string.IsNullOrWhiteSpace(sob) && !string.IsNullOrWhiteSpace(info.DwgDiretorio))
                {
                    sob = ExtrairSob(info.DwgDiretorio);
                }

                if (!string.IsNullOrWhiteSpace(sob))
                {
                    info.SobId = sob!;
                    info.Status = "Contexto identificado";
                }
                else
                {
                    info.SobId = "Não identificada";
                    info.Status = "Contexto identificado (SOB não localizada)";
                }
            }
            catch (Exception ex)
            {
                info.Salvo = false;
                info.Status = $"Erro ao obter contexto: {ex.Message}";
                info.DwgNome = "Erro de leitura";
                info.DwgCaminho = "-";
                info.DwgDiretorio = "-";
                info.SobId = "-";
            }

            return info;
        }
    }
}
