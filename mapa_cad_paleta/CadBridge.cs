using System;
using System.Collections.Generic;
using System.Text.Json;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.Colors;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using acApp = Autodesk.AutoCAD.ApplicationServices.Application;

namespace MapaCadPaleta
{
    /// <summary>
    /// Dados de entrada para inserção ou atualização de poste vindo da Paleta OSM.
    /// </summary>
    public class PostePayload
    {
        public double X { get; set; }
        public double Y { get; set; }
        public string Numero { get; set; } = "01";
        public string TipoPoste { get; set; } = "11/600";
        public string EstruturaMt { get; set; } = "";
        public string EstruturaBt { get; set; } = "";
        public List<string> EstruturasMt { get; set; } = new();
        public List<string> EstruturasBt { get; set; } = new();
        public List<string> Equipamentos { get; set; } = new();
        public string CargaTri { get; set; } = "";
        public int FusoUtm { get; set; } = 23;
        public bool TemTrafo { get; set; } = false;
        public string PotenciaTrafo { get; set; } = "45kVA";
    }

    /// <summary>
    /// Ponte analítica entre a interface Web Leaflet/OSM e o banco de dados DWG do AutoCAD.
    /// </summary>
    public static class CadBridge
    {
        private const string LAYER_POSTES = "POSTES";
        private const string LAYER_NUMERO = "POSTES_NUMERO";
        private const string LAYER_DESCRICAO = "POSTES_DESCRICAO";
        private const string LAYER_CABOS_BT = "CABOS_BT";
        private const string LAYER_CABOS_MT = "CABOS_MT";
        private const string LAYER_CABOS_TEXTO = "CABOS_TEXTO";
        private const string LAYER_VIAS_EIXO = "VIAS_EIXO";
        private const string LAYER_VIAS_BORDO = "VIAS_BORDO";
        private const string LAYER_VIAS_CALCADA = "VIAS_CALCADA";
        private const string LAYER_OBSTRUCOES_EDIF = "OBSTRUCOES_EDIF";

        /// <summary>
        /// Insere um poste georreferenciado e sua anotação técnica no DWG ativo.
        /// </summary>
        public static (bool Success, string Message) InserirPoste(string jsonPayload)
        {
            Document doc = acApp.DocumentManager.MdiActiveDocument;
            if (doc == null)
            {
                return (false, "Nenhum documento DWG ativo no AutoCAD.");
            }

            PostePayload? payload;
            try
            {
                payload = JsonSerializer.Deserialize<PostePayload>(jsonPayload, new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                });
            }
            catch (Exception ex)
            {
                return (false, $"Erro ao decodificar JSON: {ex.Message}");
            }

            if (payload == null)
            {
                return (false, "Dados do poste vazios.");
            }

            Database db = doc.Database;
            Editor ed = doc.Editor;

            try
            {
                using (doc.LockDocument())
                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTable bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                    BlockTableRecord btr = (BlockTableRecord)tr.GetObject(db.CurrentSpaceId, OpenMode.ForWrite);

                    GarantirLayers(db, tr);

                    Point3d ptPoste = new Point3d(payload.X, payload.Y, 0.0);

                    // 1. Inserir Bloco POSTE_ ou Geometria Vetorial Limpa
                    InserirGeometriaPoste(db, tr, btr, bt, ptPoste);

                    // 2. Se houver Trafo, inserir o bloco específico "T" no poste
                    if (PossuiTrafo(payload))
                    {
                        InserirBlocoTrafo(db, tr, btr, bt, ptPoste, payload);
                    }

                    // 3. Inserir Bloco PONTO com afastamento seguro anti-colisão (raio livre sem sobrepor POSTE_)
                    Point3d ptNum = new Point3d(payload.X - 2.8, payload.Y + 1.8, 0.0);
                    InserirNumeroPoste(db, tr, btr, bt, ptNum, payload.Numero);

                    // 4. Inserir Descrição Técnica Empilhada à direita com folga lateral limpa
                    Point3d ptDesc = new Point3d(payload.X + 1.8, payload.Y + 1.2, 0.0);
                    InserirDescricaoTecnica(tr, btr, ptDesc, payload);

                    tr.Commit();
                }

                ed.Regen();
                return (true, $"Poste {payload.Numero} inserido com sucesso em ({payload.X:F2}, {payload.Y:F2}).");
            }
            catch (Exception ex)
            {
                return (false, $"Falha ao desenhar no CAD: {ex.Message}");
            }
        }

        /// <summary>
        /// Desenha a linha de condutores de rede (BT ou MT) entre dois postes e anota a distância do vão.
        /// </summary>
        public static (bool Success, string Message) InserirVaoCabos(double x1, double y1, double x2, double y2, string tipoRede, string textoVao)
        {
            Document doc = acApp.DocumentManager.MdiActiveDocument;
            if (doc == null)
            {
                return (false, "Nenhum documento DWG ativo no AutoCAD.");
            }

            Database db = doc.Database;
            Editor ed = doc.Editor;

            try
            {
                using (doc.LockDocument())
                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTableRecord btr = (BlockTableRecord)tr.GetObject(db.CurrentSpaceId, OpenMode.ForWrite);
                    GarantirLayers(db, tr);

                    string layerCabo = (tipoRede?.ToUpperInvariant() == "MT") ? LAYER_CABOS_MT : LAYER_CABOS_BT;

                    Point3d pt1 = new Point3d(x1, y1, 0.0);
                    Point3d pt2 = new Point3d(x2, y2, 0.0);

                    // 1. Linha do condutor entre os centros dos postes
                    Line condutor = new Line(pt1, pt2)
                    {
                        Layer = layerCabo
                    };
                    btr.AppendEntity(condutor);
                    tr.AddNewlyCreatedDBObject(condutor, true);

                    // 2. Cálculo de orientação e ponto médio para texto alinhado
                    double dx = x2 - x1;
                    double dy = y2 - y1;
                    double angulo = Math.Atan2(dy, dx);

                    // Corrige ângulo para que o texto nunca fique invertido de cabeça para baixo
                    if (angulo > Math.PI / 2.0 || angulo < -Math.PI / 2.0)
                    {
                        angulo += Math.PI;
                    }

                    // Vetor perpendicular normalizado para afastar o texto do condutor
                    double normalX = -Math.Sin(angulo);
                    double normalY = Math.Cos(angulo);
                    double offsetDist = 0.6; // 60cm de afastamento da linha

                    double mx = (x1 + x2) / 2.0;
                    double my = (y1 + y2) / 2.0;
                    Point3d ptTexto = new Point3d(mx + normalX * offsetDist, my + normalY * offsetDist, 0.0);

                    if (!string.IsNullOrWhiteSpace(textoVao))
                    {
                        DBText txtVao = new DBText
                        {
                            Position = ptTexto,
                            AlignmentPoint = ptTexto,
                            HorizontalMode = TextHorizontalMode.TextCenter,
                            VerticalMode = TextVerticalMode.TextBottom,
                            Height = 0.9,
                            TextString = textoVao.Trim(),
                            Rotation = angulo,
                            Layer = LAYER_CABOS_TEXTO
                        };
                        btr.AppendEntity(txtVao);
                        tr.AddNewlyCreatedDBObject(txtVao, true);
                    }

                    tr.Commit();
                }

                ed.Regen();
                return (true, $"Vão de rede ({tipoRede}) desenhado com sucesso.");
            }
            catch (Exception ex)
            {
                return (false, $"Erro ao traçar vão no CAD: {ex.Message}");
            }
        }

        /// <summary>
        /// Desenha vias, calçadas e edificações/obstruções no DWG com geometrias 2.5D.
        /// </summary>
        public static (bool Success, string Message) DesenharElementosUrbanos(string rawJson)
        {
            Document doc = acApp.DocumentManager.MdiActiveDocument;
            if (doc == null) return (false, "Nenhum documento DWG ativo.");

            Database db = doc.Database;
            Editor ed = doc.Editor;

            try
            {
                using var jsonDoc = JsonDocument.Parse(rawJson);
                var root = jsonDoc.RootElement;

                int totalViasRecebidas = root.TryGetProperty("vias", out var viasJson) && viasJson.ValueKind == JsonValueKind.Array ? viasJson.GetArrayLength() : 0;
                int totalCalcadasRecebidas = root.TryGetProperty("calcadas", out var calcadasJson) && calcadasJson.ValueKind == JsonValueKind.Array ? calcadasJson.GetArrayLength() : 0;
                int totalObstrucoesRecebidas = root.TryGetProperty("obstrucoes", out var obstrucoesJson) && obstrucoesJson.ValueKind == JsonValueKind.Array ? obstrucoesJson.GetArrayLength() : 0;
                int fusoRecebido = root.TryGetProperty("fuso", out var fusoProp) && fusoProp.ValueKind == JsonValueKind.Number ? fusoProp.GetInt32() : -1;
                int totalVerticesRecebidos = 0;
                int totalPolylinesCriadas = 0;
                int totalVerticesCriados = 0;

                if (root.TryGetProperty("vias", out var viasPreview) && viasPreview.ValueKind == JsonValueKind.Array)
                {
                    foreach (var item in viasPreview.EnumerateArray())
                    {
                        if (item.TryGetProperty("pontosUtm", out var pts) && pts.ValueKind == JsonValueKind.Array)
                        {
                            totalVerticesRecebidos += pts.GetArrayLength();
                            if (pts.GetArrayLength() > 0)
                            {
                                var first = pts[0].EnumerateArray().ToList();
                                if (first.Count >= 2)
                                {
                                    ed.WriteMessage($"\n[OSMPALETA][CAD][VIA][AMOSTRA] primeiroPonto={first[0].GetDouble():F3},{first[1].GetDouble():F3}; vias={totalViasRecebidas}; calcadas={totalCalcadasRecebidas}; obstrucoes={totalObstrucoesRecebidas};");
                                    break;
                                }
                            }
                        }
                    }
                }

                ed.WriteMessage($"\n[OSMPALETA][CAD][PAYLOAD] fuso={fusoRecebido}; vias={totalViasRecebidas}; calcadas={totalCalcadasRecebidas}; obstrucoes={totalObstrucoesRecebidas}; verticesTotal={totalVerticesRecebidos};");

                using (doc.LockDocument())
                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTableRecord btr = (BlockTableRecord)tr.GetObject(db.CurrentSpaceId, OpenMode.ForWrite);
                    GarantirLayers(db, tr);

                    int total = 0;

                    void DesenharViasComOffsets(JsonElement arrayElem, bool inserirNome = true)
                    {
                        if (arrayElem.ValueKind != JsonValueKind.Array) return;
                        foreach (var item in arrayElem.EnumerateArray())
                        {
                            if (item.TryGetProperty("pontosUtm", out var pts) && pts.ValueKind == JsonValueKind.Array)
                            {
                                var rawPontos = pts.EnumerateArray().ToList();
                                if (rawPontos.Count < 2) continue;

                                var pontos2d = new List<Point2d>();
                                Polyline plEixo = new Polyline { Layer = LAYER_VIAS_EIXO, Closed = false };
                                for (int i = 0; i < rawPontos.Count; i++)
                                {
                                    var pt = rawPontos[i].EnumerateArray().ToList();
                                    if (pt.Count >= 2)
                                    {
                                        var p2d = new Point2d(pt[0].GetDouble(), pt[1].GetDouble());
                                        pontos2d.Add(p2d);
                                        plEixo.AddVertexAt(i, p2d, 0, 0, 0);
                                    }
                                }

                                // 1. Eixo da via (Layer VIAS_EIXO - Invisível por padrão, serve como guia)
                                btr.AppendEntity(plEixo);
                                tr.AddNewlyCreatedDBObject(plEixo, true);
                                total++;
                                totalPolylinesCriadas++;
                                totalVerticesCriados += pontos2d.Count;

                                // 2. Extrair ou calcular larguras da pista e do passeio a partir do OSM
                                double larguraPista = 7.0;
                                double larguraCalcada = 2.0;
                                if (item.TryGetProperty("larguraPista", out var lpProp))
                                    larguraPista = lpProp.GetDouble();
                                if (item.TryGetProperty("larguraCalcada", out var lcProp))
                                    larguraCalcada = lcProp.GetDouble();

                                double halfWidth = larguraPista / 2.0;
                                double distCalcada = halfWidth + larguraCalcada;

                                // 3. Bordos da Pista / Meio-fio (Layer VIAS_BORDO)
                                AdicionarOffsetCurvas(btr, tr, plEixo, pontos2d, halfWidth, LAYER_VIAS_BORDO);
                                AdicionarOffsetCurvas(btr, tr, plEixo, pontos2d, -halfWidth, LAYER_VIAS_BORDO);
                                total += 2;
                                totalPolylinesCriadas += 2;
                                totalVerticesCriados += pontos2d.Count * 2;

                                // 4. Limites do Passeio / Calçada (Layer VIAS_CALCADA)
                                AdicionarOffsetCurvas(btr, tr, plEixo, pontos2d, distCalcada, LAYER_VIAS_CALCADA);
                                AdicionarOffsetCurvas(btr, tr, plEixo, pontos2d, -distCalcada, LAYER_VIAS_CALCADA);
                                total += 2;
                                totalPolylinesCriadas += 2;
                                totalVerticesCriados += pontos2d.Count * 2;

                                if (inserirNome && item.TryGetProperty("nome", out var nomeProp))
                                {
                                    string nomeRua = nomeProp.GetString() ?? "";
                                    if (!string.IsNullOrWhiteSpace(nomeRua) && !nomeRua.Equals("Via sem nome", StringComparison.OrdinalIgnoreCase) && !nomeRua.Equals("Rua", StringComparison.OrdinalIgnoreCase))
                                    {
                                        int midIdx = pontos2d.Count / 2;
                                        var ptMid = pontos2d[midIdx];
                                        DBText txt = new DBText
                                        {
                                            Position = new Point3d(ptMid.X, ptMid.Y, 0.0),
                                            Height = 1.6,
                                            TextString = nomeRua,
                                            Layer = LAYER_VIAS_BORDO,
                                            HorizontalMode = TextHorizontalMode.TextCenter,
                                            VerticalMode = TextVerticalMode.TextVerticalMid,
                                            AlignmentPoint = new Point3d(ptMid.X, ptMid.Y, 0.0)
                                        };
                                        btr.AppendEntity(txt);
                                        tr.AddNewlyCreatedDBObject(txt, true);
                                    }
                                }
                            }
                        }
                    }

                    void DesenharListaPolilinhas(JsonElement arrayElem, string layer, bool fechada, bool inserirNome = false)
                    {
                        if (arrayElem.ValueKind != JsonValueKind.Array) return;
                        foreach (var item in arrayElem.EnumerateArray())
                        {
                            if (item.TryGetProperty("pontosUtm", out var pts) && pts.ValueKind == JsonValueKind.Array)
                            {
                                var pontos = pts.EnumerateArray().ToList();
                                if (pontos.Count < 2) continue;

                                Polyline pl = new Polyline { Layer = layer, Closed = fechada };
                                for (int i = 0; i < pontos.Count; i++)
                                {
                                    var pt = pontos[i].EnumerateArray().ToList();
                                    if (pt.Count >= 2)
                                    {
                                        pl.AddVertexAt(i, new Point2d(pt[0].GetDouble(), pt[1].GetDouble()), 0, 0, 0);
                                    }
                                }

                                btr.AppendEntity(pl);
                                tr.AddNewlyCreatedDBObject(pl, true);
                                total++;
                                totalPolylinesCriadas++;
                                totalVerticesCriados += pontos.Count;
                            }
                        }
                    }

                    if (root.TryGetProperty("vias", out var vias))
                        DesenharViasComOffsets(vias);

                    if (root.TryGetProperty("calcadas", out var calcadas))
                        DesenharListaPolilinhas(calcadas, LAYER_VIAS_CALCADA, false);

                    if (root.TryGetProperty("obstrucoes", out var obstrucoes))
                        DesenharListaPolilinhas(obstrucoes, LAYER_OBSTRUCOES_EDIF, true);

                    tr.Commit();
                    ed.Regen();
                    ed.WriteMessage($"\n[OSMPALETA][CAD][RESULTADO] polylinesCriadas={totalPolylinesCriadas}; verticesCriados={totalVerticesCriados}; total={total};");
                    ed.WriteMessage($"\n[MAPA AUX CAD] {total} elementos urbanos (vias/calçadas/obstruções) desenhados no CAD.");
                    return (true, $"{total} elementos urbanos (vias/calçadas/obstruções) desenhados no CAD.");
                }
            }
            catch (Exception ex)
            {
                return (false, $"Erro ao desenhar elementos urbanos no CAD: {ex.Message}");
            }
        }

        private static void AdicionarOffsetCurvas(BlockTableRecord btr, Transaction tr, Polyline basePl, List<Point2d> pontos, double dist, string layer)
        {
            bool sucessoNativo = false;
            try
            {
                using var curvas = basePl.GetOffsetCurves(dist);
                if (curvas != null && curvas.Count > 0)
                {
                    foreach (DBObject obj in curvas)
                    {
                        if (obj is Entity ent)
                        {
                            ent.Layer = layer;
                            btr.AppendEntity(ent);
                            tr.AddNewlyCreatedDBObject(ent, true);
                        }
                    }
                    sucessoNativo = true;
                }
            }
            catch
            {
                sucessoNativo = false;
            }

            if (!sucessoNativo)
            {
                Polyline plAnalitica = OffsetPolylineAnalitico(pontos, dist, layer);
                if (plAnalitica != null)
                {
                    btr.AppendEntity(plAnalitica);
                    tr.AddNewlyCreatedDBObject(plAnalitica, true);
                }
            }
        }

        private static Polyline OffsetPolylineAnalitico(List<Point2d> pts, double d, string layer)
        {
            if (pts == null || pts.Count < 2) return null;
            int n = pts.Count;
            var segs = new List<Vector2d>();

            for (int i = 0; i < n - 1; i++)
            {
                double dx = pts[i + 1].X - pts[i].X;
                double dy = pts[i + 1].Y - pts[i].Y;
                double len = Math.Sqrt(dx * dx + dy * dy);
                if (len < 1e-6)
                    segs.Add(new Vector2d(0, 0));
                else
                    segs.Add(new Vector2d(-dy / len, dx / len));
            }

            Polyline pl = new Polyline { Layer = layer, Closed = false };
            for (int i = 0; i < n; i++)
            {
                if (i == 0)
                {
                    var n0 = segs[0];
                    pl.AddVertexAt(0, new Point2d(pts[0].X + d * n0.X, pts[0].Y + d * n0.Y), 0, 0, 0);
                }
                else if (i == n - 1)
                {
                    var nLast = segs[segs.Count - 1];
                    pl.AddVertexAt(i, new Point2d(pts[n - 1].X + d * nLast.X, pts[n - 1].Y + d * nLast.Y), 0, 0, 0);
                }
                else
                {
                    var n1 = segs[i - 1];
                    var n2 = segs[i];
                    double avgX = n1.X + n2.X;
                    double avgY = n1.Y + n2.Y;
                    double len = Math.Sqrt(avgX * avgX + avgY * avgY);
                    if (len < 1e-6)
                    {
                        pl.AddVertexAt(i, new Point2d(pts[i].X + d * n1.X, pts[i].Y + d * n1.Y), 0, 0, 0);
                    }
                    else
                    {
                        double ux = avgX / len;
                        double uy = avgY / len;
                        double dot = ux * n1.X + uy * n1.Y;
                        double scale = Math.Min(1.0 / Math.Max(dot, 0.2), 2.5);
                        pl.AddVertexAt(i, new Point2d(pts[i].X + d * scale * ux, pts[i].Y + d * scale * uy), 0, 0, 0);
                    }
                }
            }
            return pl;
        }

        /// <summary>
        /// Captura interativamente um ponto no DWG e retorna coordenadas UTM e Lat/Lon.
        /// </summary>
        public static (bool Success, double X, double Y, double Lat, double Lon, string Error) CapturarPontoCad(int fuso = 23)
        {
            Document doc = acApp.DocumentManager.MdiActiveDocument;
            if (doc == null)
            {
                return (false, 0, 0, 0, 0, "Nenhum documento DWG ativo.");
            }

            Editor ed = doc.Editor;
            PromptPointOptions ppo = new PromptPointOptions("\n[MAPA AUX CAD] Clique em um ponto no DWG para sincronizar com o mapa OSM: ");
            PromptPointResult ppr = ed.GetPoint(ppo);

            if (ppr.Status != PromptStatus.OK)
            {
                return (false, 0, 0, 0, 0, "Seleção cancelada pelo usuário.");
            }

            double x = ppr.Value.X;
            double y = ppr.Value.Y;

            var (lat, lon) = SnyderConverter.UtmToLatLon(x, y, fuso, 'S');
            return (true, x, y, lat, lon, string.Empty);
        }

        /// <summary>
        /// Escaneia todos os postes inseridos no DWG ativo.
        /// </summary>
        public static List<Dictionary<string, object>> EscanearPostesDwg(int fuso = 23)
        {
            var resultado = new List<Dictionary<string, object>>();
            Document doc = acApp.DocumentManager.MdiActiveDocument;
            if (doc == null) return resultado;

            Database db = doc.Database;
            using (doc.LockDocument())
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                BlockTableRecord btr = (BlockTableRecord)tr.GetObject(db.CurrentSpaceId, OpenMode.ForRead);
                foreach (ObjectId id in btr)
                {
                    Entity ent = (Entity)tr.GetObject(id, OpenMode.ForRead);
                    if (ent is BlockReference blk)
                    {
                        string blkName = blk.Name;
                        if (blkName.Equals("POSTE_", StringComparison.OrdinalIgnoreCase) ||
                            blk.Layer.Equals(LAYER_POSTES, StringComparison.OrdinalIgnoreCase))
                        {
                            double x = blk.Position.X;
                            double y = blk.Position.Y;
                            var (lat, lon) = SnyderConverter.UtmToLatLon(x, y, fuso, 'S');

                            resultado.Add(new Dictionary<string, object>
                            {
                                ["x"] = Math.Round(x, 2),
                                ["y"] = Math.Round(y, 2),
                                ["lat"] = lat,
                                ["lon"] = lon,
                                ["handle"] = blk.Handle.ToString()
                            });
                        }
                    }
                }
                tr.Commit();
            }

            return resultado;
        }

        private static void GarantirLayers(Database db, Transaction tr)
        {
            LayerTable lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_POSTES, 3);          // Verde
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_NUMERO, 4);          // Ciano
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_DESCRICAO, 2);       // Amarelo
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_CABOS_BT, 2);        // Amarelo / Yellow (BT)
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_CABOS_MT, 4);        // Ciano / Cyan (MT)
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_CABOS_TEXTO, 7);     // Branco / White (Texto)
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_VIAS_EIXO, 8, true); // Cinza escuro (Eixo Guia - Oculto por padrão)
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_VIAS_BORDO, 8);      // Cinza (Bordo / Meio-fio da Pista)
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_VIAS_CALCADA, 9);    // Cinza claro (Passeio / Calçada)
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_OBSTRUCOES_EDIF, 1); // Vermelho (Edificação)
        }

        private static void CriarLayerSeNaoExistir(Database db, Transaction tr, LayerTable lt, string nome, short colorIndex, bool isOff = false)
        {
            if (!lt.Has(nome))
            {
                lt.UpgradeOpen();
                LayerTableRecord ltr = new LayerTableRecord
                {
                    Name = nome,
                    Color = Color.FromColorIndex(ColorMethod.ByAci, colorIndex),
                    IsOff = isOff
                };
                lt.Add(ltr);
                tr.AddNewlyCreatedDBObject(ltr, true);
            }
            else
            {
                try
                {
                    ObjectId ltrId = lt[nome];
                    LayerTableRecord ltr = (LayerTableRecord)tr.GetObject(ltrId, OpenMode.ForWrite);
                    if (isOff)
                    {
                        ltr.IsOff = true;
                    }
                    else
                    {
                        ltr.IsOff = false;
                        if (ltr.IsFrozen) ltr.IsFrozen = false;
                    }
                }
                catch { }
            }
        }

        private static void InserirGeometriaPoste(Database db, Transaction tr, BlockTableRecord btr, BlockTable bt, Point3d pt)
        {
            if (bt.Has("POSTE_"))
            {
                BlockTableRecord blkPoste = (BlockTableRecord)tr.GetObject(bt["POSTE_"], OpenMode.ForRead);
                BlockReference br = new BlockReference(pt, blkPoste.ObjectId)
                {
                    Layer = LAYER_POSTES,
                    ScaleFactors = new Scale3d(1.0, 1.0, 1.0)
                };
                btr.AppendEntity(br);
                tr.AddNewlyCreatedDBObject(br, true);
            }
            else
            {
                // Fallback vetorial limpo (círculo 0.4m com cruz central)
                Circle circ = new Circle(pt, Vector3d.ZAxis, 0.4) { Layer = LAYER_POSTES };
                Line l1 = new Line(new Point3d(pt.X - 0.4, pt.Y, 0), new Point3d(pt.X + 0.4, pt.Y, 0)) { Layer = LAYER_POSTES };
                Line l2 = new Line(new Point3d(pt.X, pt.Y - 0.4, 0), new Point3d(pt.X, pt.Y + 0.4, 0)) { Layer = LAYER_POSTES };

                btr.AppendEntity(circ);
                btr.AppendEntity(l1);
                btr.AppendEntity(l2);
                tr.AddNewlyCreatedDBObject(circ, true);
                tr.AddNewlyCreatedDBObject(l1, true);
                tr.AddNewlyCreatedDBObject(l2, true);
            }
        }

        private static bool PossuiTrafo(PostePayload payload)
        {
            if (payload.TemTrafo) return true;
            if (payload.Equipamentos != null)
            {
                foreach (var eq in payload.Equipamentos)
                {
                    if (!string.IsNullOrWhiteSpace(eq) && eq.ToUpperInvariant().Contains("TRAFO"))
                        return true;
                }
            }
            return false;
        }

        private static void InserirBlocoTrafo(Database db, Transaction tr, BlockTableRecord btr, BlockTable bt, Point3d pt, PostePayload payload)
        {
            // Procura a simbologia oficial de transformador da concessionária: TRAFO1, TRAFO, T ou TRANSF
            string[] nomesBlocos = new string[] { "TRAFO1", "TRAFO", "T", "TRANSF" };
            string nomeEncontrado = null;
            foreach (string nome in nomesBlocos)
            {
                if (bt.Has(nome))
                {
                    nomeEncontrado = nome;
                    break;
                }
            }

            if (nomeEncontrado != null)
            {
                BlockTableRecord blkT = (BlockTableRecord)tr.GetObject(bt[nomeEncontrado], OpenMode.ForRead);
                BlockReference br = new BlockReference(pt, blkT.ObjectId)
                {
                    Layer = LAYER_POSTES,
                    ScaleFactors = new Scale3d(1.0, 1.0, 1.0)
                };
                btr.AppendEntity(br);
                tr.AddNewlyCreatedDBObject(br, true);

                // Atributos de capacidade ou potência se existirem no bloco
                if (blkT.HasAttributeDefinitions)
                {
                    string pot = !string.IsNullOrWhiteSpace(payload.PotenciaTrafo) ? payload.PotenciaTrafo : "45kVA";
                    foreach (ObjectId attId in blkT)
                    {
                        DBObject obj = tr.GetObject(attId, OpenMode.ForRead);
                        if (obj is AttributeDefinition attDef)
                        {
                            AttributeReference attRef = new AttributeReference();
                            attRef.SetAttributeFromBlock(attDef, br.BlockTransform);
                            string tag = attDef.Tag.ToUpperInvariant();
                            if (tag.Contains("POT") || tag.Contains("KVA") || tag.Contains("CAP") || tag == "T")
                            {
                                attRef.TextString = pot;
                            }
                            br.AttributeCollection.AppendAttribute(attRef);
                            tr.AddNewlyCreatedDBObject(attRef, true);
                        }
                    }
                }
            }
            else
            {
                // Fallback vetorial 2.5D: Símbolo padronizado de transformador (dois círculos tangentes)
                Point3d c1Center = new Point3d(pt.X, pt.Y + 0.35, 0.0);
                Point3d c2Center = new Point3d(pt.X, pt.Y + 1.05, 0.0);
                Circle circ1 = new Circle(c1Center, Vector3d.ZAxis, 0.35) { Layer = LAYER_POSTES };
                Circle circ2 = new Circle(c2Center, Vector3d.ZAxis, 0.35) { Layer = LAYER_POSTES };

                btr.AppendEntity(circ1);
                btr.AppendEntity(circ2);
                tr.AddNewlyCreatedDBObject(circ1, true);
                tr.AddNewlyCreatedDBObject(circ2, true);
            }
        }

        private static void InserirNumeroPoste(Database db, Transaction tr, BlockTableRecord btr, BlockTable bt, Point3d pt, string numero)
        {
            if (bt.Has("PONTO"))
            {
                BlockTableRecord blkPonto = (BlockTableRecord)tr.GetObject(bt["PONTO"], OpenMode.ForRead);
                BlockReference br = new BlockReference(pt, blkPonto.ObjectId)
                {
                    Layer = LAYER_NUMERO,
                    ScaleFactors = new Scale3d(1.0, 1.0, 1.0)
                };
                btr.AppendEntity(br);
                tr.AddNewlyCreatedDBObject(br, true);

                if (blkPonto.HasAttributeDefinitions)
                {
                    foreach (ObjectId attId in blkPonto)
                    {
                        DBObject obj = tr.GetObject(attId, OpenMode.ForRead);
                        if (obj is AttributeDefinition attDef)
                        {
                            AttributeReference attRef = new AttributeReference();
                            attRef.SetAttributeFromBlock(attDef, br.BlockTransform);
                            attRef.TextString = numero;
                            br.AttributeCollection.AppendAttribute(attRef);
                            tr.AddNewlyCreatedDBObject(attRef, true);
                            break;
                        }
                    }
                }
            }
            else
            {
                // Fallback vetorial com círculo e texto centralizado de alta visibilidade
                Circle c = new Circle(pt, Vector3d.ZAxis, 1.5) { Layer = LAYER_NUMERO };
                DBText txt = new DBText
                {
                    Position = pt,
                    Height = 1.4,
                    TextString = numero,
                    Layer = LAYER_NUMERO,
                    HorizontalMode = TextHorizontalMode.TextCenter,
                    VerticalMode = TextVerticalMode.TextVerticalMid,
                    AlignmentPoint = pt
                };
                btr.AppendEntity(c);
                btr.AppendEntity(txt);
                tr.AddNewlyCreatedDBObject(c, true);
                tr.AddNewlyCreatedDBObject(txt, true);
            }
        }

        private static void InserirDescricaoTecnica(Transaction tr, BlockTableRecord btr, Point3d pt, PostePayload payload)
        {
            var linhas = new List<string>();

            // Tipo / Esforço do Poste
            if (!string.IsNullOrWhiteSpace(payload.TipoPoste))
                linhas.Add(payload.TipoPoste.Trim());

            // Estruturas MT (Multi-estruturas ou formato legado)
            if (payload.EstruturasMt != null && payload.EstruturasMt.Count > 0)
            {
                foreach (string mt in payload.EstruturasMt)
                {
                    if (!string.IsNullOrWhiteSpace(mt))
                        linhas.Add(mt.Trim());
                }
            }
            else if (!string.IsNullOrWhiteSpace(payload.EstruturaMt))
            {
                linhas.Add(payload.EstruturaMt.Trim());
            }

            // Estruturas BT (Multi-estruturas ou formato legado)
            if (payload.EstruturasBt != null && payload.EstruturasBt.Count > 0)
            {
                foreach (string btStr in payload.EstruturasBt)
                {
                    if (!string.IsNullOrWhiteSpace(btStr))
                        linhas.Add(btStr.Trim());
                }
            }
            else if (!string.IsNullOrWhiteSpace(payload.EstruturaBt))
            {
                linhas.Add(payload.EstruturaBt.Trim());
            }

            // Equipamentos (IP, ATERR, DAE, TRAFO, etc.)
            if (payload.Equipamentos != null)
            {
                foreach (string eq in payload.Equipamentos)
                {
                    if (!string.IsNullOrWhiteSpace(eq))
                        linhas.Add(eq.Trim());
                }
            }

            // Cargas Especiais Trifásicas
            if (!string.IsNullOrWhiteSpace(payload.CargaTri))
                linhas.Add(payload.CargaTri.Trim());

            if (linhas.Count == 0) return;

            string conteudoFormatado = string.Join("\\P", linhas);

            MText mtext = new MText
            {
                Location = pt,
                TextHeight = 0.8,
                Contents = conteudoFormatado,
                Layer = LAYER_DESCRICAO,
                Attachment = AttachmentPoint.TopLeft
            };

            btr.AppendEntity(mtext);
            tr.AddNewlyCreatedDBObject(mtext, true);
        }
    }
}
