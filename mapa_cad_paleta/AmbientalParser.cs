using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text.Json;
using System.Xml.Linq;

namespace MapaCadPaleta
{
    /// <summary>
    /// Modelo de polígono ambiental sanitizado para envio ao Leaflet.
    /// </summary>
    public class PoligonoAmbiental
    {
        public string Nome { get; set; } = "Área Ambiental";
        public string Categoria { get; set; } = "APP";
        public List<double[]> Pontos { get; set; } = new(); // [[lat, lon], [lat, lon], ...]
    }

    /// <summary>
    /// Analisador e extrator de arquivos geoespaciais ambientais (KMZ, KML, GeoJSON).
    /// </summary>
    public static class AmbientalParser
    {
        /// <summary>
        /// Carrega e extrai polígonos de um arquivo .kmz, .kml ou .geojson/.json.
        /// </summary>
        public static List<PoligonoAmbiental> CarregarArquivo(string caminhoArquivo)
        {
            if (string.IsNullOrWhiteSpace(caminhoArquivo) || !File.Exists(caminhoArquivo))
            {
                return new List<PoligonoAmbiental>();
            }

            string ext = Path.GetExtension(caminhoArquivo).ToLowerInvariant();

            if (ext == ".kmz")
            {
                return ExtrairDeKmz(caminhoArquivo);
            }
            else if (ext == ".kml")
            {
                using var stream = File.OpenRead(caminhoArquivo);
                return ExtrairDeKmlStream(stream);
            }
            else if (ext == ".geojson" || ext == ".json")
            {
                return ExtrairDeGeoJson(File.ReadAllText(caminhoArquivo));
            }

            return new List<PoligonoAmbiental>();
        }

        private static List<PoligonoAmbiental> ExtrairDeKmz(string caminhoKmz)
        {
            var resultado = new List<PoligonoAmbiental>();
            using (var zip = ZipFile.OpenRead(caminhoKmz))
            {
                // Localiza arquivo KML dentro do KMZ (normalmente doc.kml)
                var kmlEntry = zip.Entries.FirstOrDefault(e => e.FullName.EndsWith(".kml", StringComparison.OrdinalIgnoreCase));
                if (kmlEntry != null)
                {
                    using (var stream = kmlEntry.Open())
                    {
                        resultado.AddRange(ExtrairDeKmlStream(stream));
                    }
                }
            }
            return resultado;
        }

        private static List<PoligonoAmbiental> ExtrairDeKmlStream(Stream stream)
        {
            var lista = new List<PoligonoAmbiental>();

            try
            {
                var doc = XDocument.Load(stream);

                // Busca todos os Placemarks independente de namespace XML
                var placemarks = doc.Descendants().Where(e => e.Name.LocalName == "Placemark");

                foreach (var pm in placemarks)
                {
                    string nome = pm.Elements().FirstOrDefault(e => e.Name.LocalName == "name")?.Value?.Trim() ?? "Área";
                    string desc = pm.Elements().FirstOrDefault(e => e.Name.LocalName == "description")?.Value?.Trim() ?? "";
                    string categoria = ClassificarCategoria(nome, desc);

                    // Busca todos os polígonos dentro do placemark
                    var polygons = pm.Descendants().Where(e => e.Name.LocalName == "Polygon");
                    foreach (var poly in polygons)
                    {
                        var coordsElem = poly.Descendants().FirstOrDefault(e => e.Name.LocalName == "coordinates");
                        if (coordsElem != null)
                        {
                            var pontos = ParseCoordenadasKml(coordsElem.Value);
                            if (pontos.Count >= 3)
                            {
                                lista.Add(new PoligonoAmbiental
                                {
                                    Nome = nome,
                                    Categoria = categoria,
                                    Pontos = pontos
                                });
                            }
                        }
                    }
                }
            }
            catch
            {
                // Fallback silencioso para arquivo com formatação atípica
            }

            return lista;
        }

        private static List<double[]> ParseCoordenadasKml(string rawCoords)
        {
            var pontos = new List<double[]>();
            if (string.IsNullOrWhiteSpace(rawCoords)) return pontos;

            // Coordenadas KML são separadas por espaços/quebras de linha: "lon,lat,alt lon,lat,alt ..."
            var tokens = rawCoords.Split(new[] { ' ', '\t', '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);

            foreach (var token in tokens)
            {
                var partes = token.Split(',');
                if (partes.Length >= 2)
                {
                    if (double.TryParse(partes[0].Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out double lon) &&
                        double.TryParse(partes[1].Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out double lat))
                    {
                        // Leaflet usa [lat, lon]
                        pontos.Add(new double[] { lat, lon });
                    }
                }
            }

            return pontos;
        }

        private static List<PoligonoAmbiental> ExtrairDeGeoJson(string jsonText)
        {
            var lista = new List<PoligonoAmbiental>();
            try
            {
                using var doc = JsonDocument.Parse(jsonText);
                var root = doc.RootElement;

                if (root.TryGetProperty("features", out var features) && features.ValueKind == JsonValueKind.Array)
                {
                    foreach (var feat in features.EnumerateArray())
                    {
                        string nome = "Área";
                        string categoria = "APP";

                        if (feat.TryGetProperty("properties", out var props))
                        {
                            if (props.TryGetProperty("name", out var n) || props.TryGetProperty("nome", out n) || props.TryGetProperty("rotulo", out n))
                                nome = n.GetString() ?? "Área";

                            if (props.TryGetProperty("tipo", out var t) || props.TryGetProperty("categoria", out t) || props.TryGetProperty("layer", out t))
                                categoria = t.GetString() ?? "";
                        }

                        categoria = ClassificarCategoria(nome, categoria);

                        if (feat.TryGetProperty("geometry", out var geom))
                        {
                            string geomType = geom.TryGetProperty("type", out var gt) ? gt.GetString() ?? "" : "";
                            if (geom.TryGetProperty("coordinates", out var coords))
                            {
                                if (geomType.Equals("Polygon", StringComparison.OrdinalIgnoreCase))
                                {
                                    var pontos = ExtrairPontosAnelGeoJson(coords);
                                    if (pontos.Count >= 3)
                                    {
                                        lista.Add(new PoligonoAmbiental { Nome = nome, Categoria = categoria, Pontos = pontos });
                                    }
                                }
                                else if (geomType.Equals("MultiPolygon", StringComparison.OrdinalIgnoreCase) && coords.ValueKind == JsonValueKind.Array)
                                {
                                    foreach (var polyCoords in coords.EnumerateArray())
                                    {
                                        var pontos = ExtrairPontosAnelGeoJson(polyCoords);
                                        if (pontos.Count >= 3)
                                        {
                                            lista.Add(new PoligonoAmbiental { Nome = nome, Categoria = categoria, Pontos = pontos });
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            catch
            {
            }
            return lista;
        }

        private static List<double[]> ExtrairPontosAnelGeoJson(JsonElement anelCoords)
        {
            var pontos = new List<double[]>();
            if (anelCoords.ValueKind != JsonValueKind.Array) return pontos;

            // GeoJSON Polygon tem anéis: [ [ [lon, lat], [lon, lat], ... ] ]
            var primeiroAnel = anelCoords.EnumerateArray().FirstOrDefault();
            if (primeiroAnel.ValueKind == JsonValueKind.Array)
            {
                foreach (var pt in primeiroAnel.EnumerateArray())
                {
                    if (pt.ValueKind == JsonValueKind.Array)
                    {
                        var arr = pt.EnumerateArray().ToList();
                        if (arr.Count >= 2)
                        {
                            double lon = arr[0].GetDouble();
                            double lat = arr[1].GetDouble();
                            pontos.Add(new double[] { lat, lon });
                        }
                    }
                }
            }
            return pontos;
        }

        private static string ClassificarCategoria(string nome, string extra)
        {
            string texto = (nome + " " + extra).ToUpperInvariant();
            if (texto.Contains("EXCLUSAO") || texto.Contains("RESTRICAO") || texto.Contains("PERIGO") || texto.Contains("FERROVIA"))
                return "Exclusão";
            if (texto.Contains("UC") || texto.Contains("PARQUE") || texto.Contains("RESERVA") || texto.Contains("FLORESTA"))
                return "UC";
            if (texto.Contains("RIO") || texto.Contains("CORREGO") || texto.Contains("AGUA") || texto.Contains("LAGOA") || texto.Contains("HIDRICA") || texto.Contains("NASCENTE"))
                return "Hídrica";

            return "APP";
        }
    }
}
