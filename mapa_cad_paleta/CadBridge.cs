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
        public List<string> Equipamentos { get; set; } = new();
        public string CargaTri { get; set; } = "";
        public int FusoUtm { get; set; } = 23;
    }

    /// <summary>
    /// Ponte analítica entre a interface Web Leaflet/OSM e o banco de dados DWG do AutoCAD.
    /// </summary>
    public static class CadBridge
    {
        private const string LAYER_POSTES = "POSTES";
        private const string LAYER_NUMERO = "POSTES_NUMERO";
        private const string LAYER_DESCRICAO = "POSTES_DESCRICAO";

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

                    // 2. Inserir Bloco PONTO ou Número do Poste
                    Point3d ptNum = new Point3d(payload.X + 0.8, payload.Y + 0.8, 0.0);
                    InserirNumeroPoste(db, tr, btr, bt, ptNum, payload.Numero);

                    // 3. Inserir Descrição Técnica Empilhada
                    Point3d ptDesc = new Point3d(payload.X + 1.2, payload.Y - 0.4, 0.0);
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
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_POSTES, 3);    // Verde
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_NUMERO, 4);    // Ciano
            CriarLayerSeNaoExistir(db, tr, lt, LAYER_DESCRICAO, 2); // Amarelo
        }

        private static void CriarLayerSeNaoExistir(Database db, Transaction tr, LayerTable lt, string nome, short colorIndex)
        {
            if (!lt.Has(nome))
            {
                lt.UpgradeOpen();
                LayerTableRecord ltr = new LayerTableRecord
                {
                    Name = nome,
                    Color = Color.FromColorIndex(ColorMethod.ByAci, colorIndex)
                };
                lt.Add(ltr);
                tr.AddNewlyCreatedDBObject(ltr, true);
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
                DBText txt = new DBText
                {
                    Position = pt,
                    Height = 0.8,
                    TextString = numero,
                    Layer = LAYER_NUMERO
                };
                btr.AppendEntity(txt);
                tr.AddNewlyCreatedDBObject(txt, true);
            }
        }

        private static void InserirDescricaoTecnica(Transaction tr, BlockTableRecord btr, Point3d pt, PostePayload payload)
        {
            var linhas = new List<string>();

            if (!string.IsNullOrWhiteSpace(payload.TipoPoste))
                linhas.Add(payload.TipoPoste.Trim());

            if (!string.IsNullOrWhiteSpace(payload.EstruturaMt))
                linhas.Add(payload.EstruturaMt.Trim());

            if (!string.IsNullOrWhiteSpace(payload.EstruturaBt))
                linhas.Add(payload.EstruturaBt.Trim());

            if (payload.Equipamentos != null)
            {
                foreach (string eq in payload.Equipamentos)
                {
                    if (!string.IsNullOrWhiteSpace(eq))
                        linhas.Add(eq.Trim());
                }
            }

            if (!string.IsNullOrWhiteSpace(payload.CargaTri))
                linhas.Add(payload.CargaTri.Trim());

            if (linhas.Count == 0) return;

            string conteudoFormatado = string.Join("\\P", linhas);

            MText mtext = new MText
            {
                Location = pt,
                TextHeight = 0.6,
                Contents = conteudoFormatado,
                Layer = LAYER_DESCRICAO,
                Attachment = AttachmentPoint.TopLeft
            };

            btr.AppendEntity(mtext);
            tr.AddNewlyCreatedDBObject(mtext, true);
        }
    }
}
