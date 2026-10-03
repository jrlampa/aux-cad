using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Text;
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
        public string Id { get; set; } = "";
        public string OperationId { get; set; } = "";
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
    /// Registro de operação realizada no DWG para possibilitar Undo/Rollback atômico e rastreabilidade BIM.
    /// </summary>
    public class CadOperacaoRegistro
    {
        public string OperationId { get; set; } = "";
        public string DomainId { get; set; } = "";
        public string Tipo { get; set; } = ""; // "POSTE" ou "VAO"
        public string Identificador { get; set; } = ""; // número visual do poste ou vão
        public List<Handle> Handles { get; set; } = new();
        public DateTime CriadoEm { get; set; } = DateTime.UtcNow;
    }

    /// <summary>
    /// <summary>
    /// Diagnóstico estruturado emitido durante o escaneamento e reconciliação do DWG.
    /// </summary>
    public class DwgDiagnostic
    {
        public string Code { get; set; } = "";
        public string Severity { get; set; } = "INFO"; // "INFO", "WARNING", "ERROR"
        public string EntityType { get; set; } = "";   // "POSTE", "VAO", "SET", "DWG"
        public string EntityId { get; set; } = "";
        public string Handle { get; set; } = "";
        public string Message { get; set; } = "";

        public Dictionary<string, object> ToDictionary() => new()
        {
            ["code"] = Code,
            ["severity"] = Severity,
            ["entityType"] = EntityType,
            ["entityId"] = EntityId,
            ["handle"] = Handle,
            ["message"] = Message
        };
    }

    /// <summary>
    /// Relação topológica entre Poste e Vão com método de resolução e rastreabilidade.
    /// </summary>
    public class DwgRelation
    {
        public string VaoId { get; set; } = "";
        public string PosteOrigemId { get; set; } = "";
        public string PosteDestinoId { get; set; } = "";
        public string Method { get; set; } = "Identity"; // "Identity", "Geometry", "Unresolved"
        public string Confidence { get; set; } = "Exact"; // "Exact", "Inferred", "Ambiguous"

        public Dictionary<string, object> ToDictionary() => new()
        {
            ["vaoId"] = VaoId,
            ["posteOrigemId"] = PosteOrigemId,
            ["posteDestinoId"] = PosteDestinoId,
            ["method"] = Method,
            ["confidence"] = Confidence
        };
    }

    /// <summary>
    /// Estatísticas consolidadas do escaneamento do DWG.
    /// </summary>
    public class DwgStatistics
    {
        public int TotalPostes { get; set; }
        public int TotalVaos { get; set; }
        public int PostesValidos { get; set; }
        public int VaosValidos { get; set; }
        public int PostesLegados { get; set; }
        public int VaosLegados { get; set; }
        public int VaosOrfaos { get; set; }
        public int ClonesReparados { get; set; }
        public int ErrosXData { get; set; }

        public Dictionary<string, object> ToDictionary() => new()
        {
            ["totalPostes"] = TotalPostes,
            ["totalVaos"] = TotalVaos,
            ["postesValidos"] = PostesValidos,
            ["vaosValidos"] = VaosValidos,
            ["postesLegados"] = PostesLegados,
            ["vaosLegados"] = VaosLegados,
            ["vaosOrfaos"] = VaosOrfaos,
            ["clonesReparados"] = ClonesReparados,
            ["errosXData"] = ErrosXData
        };
    }

    /// <summary>
    /// DTO canônico de poste extraído do DWG com identidade de domínio independente.
    /// </summary>
    public class PosteDto
    {
        public string Id { get; set; } = "";
        public string Numero { get; set; } = "";
        public string OperationId { get; set; } = "";
        public string TipoPoste { get; set; } = "11/600";
        public bool TemTrafo { get; set; } = false;
        public string PotenciaTrafo { get; set; } = "";
        public double X { get; set; }
        public double Y { get; set; }
        public double Lat { get; set; }
        public double Lon { get; set; }
        public double Latitude { get => Lat; set => Lat = value; }
        public double Longitude { get => Lon; set => Lon = value; }
        public string Handle { get; set; } = "";
        public bool IsLegacy { get; set; } = false;
        public bool IsValid { get; set; } = true;
        public string InvalidReason { get; set; } = "";

        public Dictionary<string, object> ToDictionary() => new()
        {
            ["id"] = Id,
            ["numero"] = Numero,
            ["operationId"] = OperationId,
            ["tipoPoste"] = TipoPoste,
            ["temTrafo"] = TemTrafo,
            ["potenciaTrafo"] = PotenciaTrafo,
            ["x"] = X,
            ["y"] = Y,
            ["lat"] = Lat,
            ["lon"] = Lon,
            ["handle"] = Handle,
            ["isLegacy"] = IsLegacy,
            ["isValid"] = IsValid,
            ["invalidReason"] = InvalidReason
        };
    }

    /// <summary>
    /// DTO canônico de vão de cabos de rede extraído do DWG com identificadores de origem/destino.
    /// </summary>
    public class VaoDto
    {
        public string Id { get; set; } = "";
        public string OperationId { get; set; } = "";
        public string PosteOrigemId { get; set; } = "";
        public string PosteDestinoId { get; set; } = "";
        public string NumDe { get; set; } = "";
        public string NumPara { get; set; } = "";
        public string De { get => NumDe; set => NumDe = value; }
        public string Para { get => NumPara; set => NumPara = value; }
        public string TipoRede { get; set; } = "BT";
        public string TextoVao { get; set; } = "";
        public string Extensao { get; set; } = "";
        public double ExtensaoMetros { get; set; }
        public double X1 { get; set; }
        public double Y1 { get; set; }
        public double X2 { get; set; }
        public double Y2 { get; set; }
        public string Handle { get; set; } = "";
        public bool IsLegacy { get; set; } = false;
        public bool IsValid { get; set; } = true;
        public string InvalidReason { get; set; } = "";
        public bool IsOrphan { get; set; } = false;
        public string OrphanReason { get; set; } = "";
        public string ResolutionMethod { get; set; } = "Identity"; // "Identity", "Geometry", "Unresolved"
        public string ResolutionConfidence { get; set; } = "Exact"; // "Exact", "Inferred", "Ambiguous"

        public Dictionary<string, object> ToDictionary() => new()
        {
            ["id"] = Id,
            ["operationId"] = OperationId,
            ["posteOrigemId"] = PosteOrigemId,
            ["posteDestinoId"] = PosteDestinoId,
            ["de"] = NumDe,
            ["para"] = NumPara,
            ["tipoRede"] = TipoRede,
            ["textoVao"] = TextoVao,
            ["extensao"] = Extensao,
            ["x1"] = X1,
            ["y1"] = Y1,
            ["x2"] = X2,
            ["y2"] = Y2,
            ["handle"] = Handle,
            ["isLegacy"] = IsLegacy,
            ["isValid"] = IsValid,
            ["invalidReason"] = InvalidReason,
            ["isOrphan"] = IsOrphan,
            ["orphanReason"] = OrphanReason,
            ["resolutionMethod"] = ResolutionMethod,
            ["resolutionConfidence"] = ResolutionConfidence
        };
    }

    /// <summary>
    /// Resultado consolidado da reconciliação e escaneamento topológico do DWG.
    /// </summary>
    public class EscanearDwgResultado
    {
        public int Version { get; set; } = 2;
        public List<PosteDto> Postes { get; set; } = new();
        public List<VaoDto> Vaos { get; set; } = new();
        public List<DwgRelation> Relacoes { get; set; } = new();
        public List<DwgDiagnostic> Diagnostics { get; set; } = new();
        public DwgStatistics Statistics { get; set; } = new();
    }

    /// <summary>
    /// Ponte analítica entre a interface Web Leaflet/OSM e o banco de dados DWG do AutoCAD.
    /// </summary>
    public static class CadBridge
    {
        public const string REGAPP_POSTE = "AUXCAD_POSTE";
        public const string REGAPP_VAO = "AUXCAD_VAO";
        public const string REGAPP_OSM = "AUXCAD_OSM";
        public const short XDATA_SCHEMA_VERSION = 2;

        private static readonly List<CadOperacaoRegistro> _historicoOperacoes = new();
        private static ProjectScope _currentProjectScope = ProjectScopeContract.Unbound();
        private static long _activeDocumentGeneration;

        public static long ActiveDocumentGeneration => Interlocked.Read(ref _activeDocumentGeneration);

        public static event EventHandler<ProjectScopeChangedEventArgs>? ProjectScopeChanged;

        public static ProjectScope GetCurrentProjectScope()
        {
            Document? document = acApp.DocumentManager.MdiActiveDocument;
            return document == null
                ? ProjectScopeContract.Unbound()
                : DwgProjectScopeStore.Read(document.Database);
        }

        public static void NotifyActiveDocumentChanged()
        {
            ProjectScope nextScope = GetCurrentProjectScope();
            ProjectScope previousScope = _currentProjectScope;
            _currentProjectScope = nextScope;
            long generation = Interlocked.Increment(ref _activeDocumentGeneration);
            ProjectScopeChanged?.Invoke(
                null,
                new ProjectScopeChangedEventArgs(previousScope, nextScope, generation));
        }

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

        private sealed class OsmEntityRef
        {
            public ObjectId ObjectId { get; set; }
            public string Fingerprint { get; set; } = "";
        }

        private sealed class OsmMetadata
        {
            public string Key { get; set; } = "";
            public string Fingerprint { get; set; } = "";
        }

        /// <summary>
        /// Insere um poste georreferenciado e sua anotação técnica no DWG ativo.
        /// Retorna Success, Message e o DomainId canônico persistido.
        /// </summary>
        public static (bool Success, string Message, string DomainId) InserirPoste(string jsonPayload)
        {
            Document doc = acApp.DocumentManager.MdiActiveDocument;
            if (doc == null)
            {
                return (false, "Nenhum documento DWG ativo no AutoCAD.", "");
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
                return (false, $"Erro ao decodificar JSON: {ex.Message}", "");
            }

            if (payload == null)
            {
                return (false, "Dados do poste vazios.", "");
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
                    // Autoridade do C#: Valida se o ID recebido é um GUID RFC4122 canônico válido. Se não for, emite um novo GUID canônico.
                    string domainId = (!string.IsNullOrWhiteSpace(payload.Id) && Guid.TryParse(payload.Id, out var gParsed))
                        ? gParsed.ToString("D")
                        : Guid.NewGuid().ToString("D");
                    payload.Id = domainId;

                    string opId = !string.IsNullOrWhiteSpace(payload.OperationId)
                        ? payload.OperationId
                        : Guid.NewGuid().ToString("N");
                    payload.OperationId = opId;

                    List<Entity> todasEntidades = new();

                    // 1. Inserir Bloco POSTE_ ou Geometria Vetorial Limpa
                    var entsPoste = InserirGeometriaPoste(db, tr, btr, bt, ptPoste);
                    todasEntidades.AddRange(entsPoste);

                    // 2. Se houver Trafo, inserir o bloco específico "T" no poste
                    if (PossuiTrafo(payload))
                    {
                        var entsTrafo = InserirBlocoTrafo(db, tr, btr, bt, ptPoste, payload);
                        todasEntidades.AddRange(entsTrafo);
                    }

                    // 3. Inserir Bloco PONTO com afastamento seguro anti-colisão (raio livre sem sobrepor POSTE_)
                    Point3d ptNum = new Point3d(payload.X - 2.8, payload.Y + 1.8, 0.0);
                    var entsNum = InserirNumeroPoste(db, tr, btr, bt, ptNum, payload.Numero);
                    todasEntidades.AddRange(entsNum);

                    // 4. Inserir Descrição Técnica Empilhada à direita com folga lateral limpa
                    Point3d ptDesc = new Point3d(payload.X + 1.8, payload.Y + 1.2, 0.0);
                    var entDesc = InserirDescricaoTecnica(tr, btr, ptDesc, payload);
                    if (entDesc != null) todasEntidades.Add(entDesc);

                    // 5. Gravar XData BIM nas entidades criadas
                    foreach (var ent in todasEntidades)
                    {
                        GravarXDataPoste(ent, db, tr, payload, opId);
                    }

                    // 6. Registrar operação para Undo/Rollback seguro
                    lock (_historicoOperacoes)
                    {
                        _historicoOperacoes.Add(new CadOperacaoRegistro
                        {
                            OperationId = opId,
                            DomainId = domainId,
                            Tipo = "POSTE",
                            Identificador = payload.Numero,
                            Handles = todasEntidades.Select(e => e.Handle).ToList()
                        });
                    }

                    tr.Commit();
                }

                ed.Regen();
                return (true, $"Poste {payload.Numero} inserido com sucesso em ({payload.X:F2}, {payload.Y:F2}).", payload.Id);
            }
            catch (Exception ex)
            {
                return (false, $"Falha ao desenhar no CAD: {ex.Message}", "");
            }
        }

        /// <summary>
        /// Desenha a linha de condutores de rede (BT ou MT) entre dois postes e anota a distância do vão com VaoId de domínio.
        /// Retorna Success, Message e o VaoId canônico persistido.
        /// </summary>
        public static (bool Success, string Message, string VaoId) InserirVaoCabos(
            double x1, double y1, double x2, double y2,
            string tipoRede, string textoVao,
            string? operationId = null, string? numDe = null, string? numPara = null,
            string? vaoId = null, string? posteOrigemId = null, string? posteDestinoId = null)
        {
            Document doc = acApp.DocumentManager.MdiActiveDocument;
            if (doc == null)
            {
                return (false, "Nenhum documento DWG ativo no AutoCAD.", "");
            }

            Database db = doc.Database;
            Editor ed = doc.Editor;

            // Autoridade do C#: Valida se vaoId é GUID válido. Se não, gera novo GUID canônico.
            string vId = (!string.IsNullOrWhiteSpace(vaoId) && Guid.TryParse(vaoId, out var gVao))
                ? gVao.ToString("D")
                : Guid.NewGuid().ToString("D");

            string opId = (!string.IsNullOrWhiteSpace(operationId))
                ? operationId!
                : Guid.NewGuid().ToString("N");

            try
            {
                using (doc.LockDocument())
                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    BlockTableRecord btr = (BlockTableRecord)tr.GetObject(db.CurrentSpaceId, OpenMode.ForWrite);
                    GarantirLayers(db, tr);

                    List<Entity> entidadesVao = new();

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
                    entidadesVao.Add(condutor);

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
                        entidadesVao.Add(txtVao);
                    }

                    // 3. Gravar XData BIM nas entidades do vão
                    foreach (var ent in entidadesVao)
                    {
                        GravarXDataVao(ent, db, tr, vId, posteOrigemId, posteDestinoId, tipoRede ?? "BT", textoVao ?? "", opId, numDe, numPara);
                    }

                    // 4. Registrar no histórico de operações para Rollback
                    lock (_historicoOperacoes)
                    {
                        _historicoOperacoes.Add(new CadOperacaoRegistro
                        {
                            OperationId = opId,
                            DomainId = vId,
                            Tipo = "VAO",
                            Identificador = !string.IsNullOrWhiteSpace(numPara) ? numPara! : (textoVao ?? "VAO"),
                            Handles = entidadesVao.Select(e => e.Handle).ToList()
                        });
                    }

                    tr.Commit();
                }

                ed.Regen();
                return (true, $"Vão de rede ({tipoRede}) desenhado com sucesso [ID: {vId}].", vId);
            }
            catch (Exception ex)
            {
                return (false, $"Erro ao traçar vão no CAD: {ex.Message}", "");
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
                ProjectScope activeScope = DwgProjectScopeStore.Read(db);
                if (!ProjectScopeContract.TryValidatePayload(
                        root,
                        activeScope,
                        ActiveDocumentGeneration,
                        out string scopeError))
                {
                    ed.WriteMessage($"\n[OSMPALETA][CAD][ESCOPO] Payload rejeitado: {scopeError}.");
                    return (false, $"Payload OSM rejeitado por escopo inválido ou desatualizado ({scopeError}).");
                }

                int totalViasRecebidas = root.TryGetProperty("vias", out var viasJson) && viasJson.ValueKind == JsonValueKind.Array ? viasJson.GetArrayLength() : 0;
                int totalCalcadasRecebidas = root.TryGetProperty("calcadas", out var calcadasJson) && calcadasJson.ValueKind == JsonValueKind.Array ? calcadasJson.GetArrayLength() : 0;
                int totalObstrucoesRecebidas = root.TryGetProperty("obstrucoes", out var obstrucoesJson) && obstrucoesJson.ValueKind == JsonValueKind.Array ? obstrucoesJson.GetArrayLength() : 0;
                int fusoRecebido = root.TryGetProperty("fuso", out var fusoProp) && fusoProp.ValueKind == JsonValueKind.Number ? fusoProp.GetInt32() : -1;
                int totalVerticesRecebidos = 0;
                int totalPolylinesCriadas = 0;
                int totalVerticesCriados = 0;
                int totalItensAtualizados = 0;
                int totalItensIgnorados = 0;

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
                    var entidadesOsm = IndexarEntidadesOsm(db, tr);

                    int total = 0;

                    bool PrepararItemOsm(JsonElement item, string categoria, out string chave, out string fingerprint)
                    {
                        chave = ConstruirChaveOsm(item, categoria);
                        fingerprint = CalcularFingerprintOsm(item, categoria);
                        if (string.IsNullOrWhiteSpace(chave))
                        {
                            ed.WriteMessage($"\n[OSMPALETA][CAD][IDEMPOTENCIA] item sem osmId; categoria={categoria}; desenhando sem reconciliação.");
                            return true;
                        }

                        if (entidadesOsm.TryGetValue(chave, out var existentes))
                        {
                            string fingerprintAtual = fingerprint;
                            bool mesmoConteudo = existentes.Count > 0
                                && existentes.All(e => string.Equals(e.Fingerprint, fingerprintAtual, StringComparison.Ordinal));
                            if (mesmoConteudo)
                            {
                                totalItensIgnorados++;
                                return false;
                            }

                            foreach (var existente in existentes)
                            {
                                if (!existente.ObjectId.IsNull && !existente.ObjectId.IsErased)
                                {
                                    var entidade = (Entity)tr.GetObject(existente.ObjectId, OpenMode.ForWrite);
                                    entidade.Erase(true);
                                }
                            }
                            totalItensAtualizados++;
                            entidadesOsm.Remove(chave);
                        }
                        return true;
                    }

                    void MarcarOsm(Entity entidade, string chave, string fingerprint, string categoria, JsonElement item)
                    {
                        if (string.IsNullOrWhiteSpace(chave)) return;
                        GravarXDataOsm(entidade, db, tr, chave, fingerprint, categoria, item);
                        if (!entidadesOsm.TryGetValue(chave, out var entidades))
                        {
                            entidades = new List<OsmEntityRef>();
                            entidadesOsm[chave] = entidades;
                        }
                        entidades.Add(new OsmEntityRef
                        {
                            ObjectId = entidade.ObjectId,
                            Fingerprint = fingerprint
                        });
                    }

                    void DesenharViasComOffsets(JsonElement arrayElem, bool inserirNome = true)
                    {
                        if (arrayElem.ValueKind != JsonValueKind.Array) return;
                        foreach (var item in arrayElem.EnumerateArray())
                        {
                            if (item.TryGetProperty("pontosUtm", out var pts) && pts.ValueKind == JsonValueKind.Array)
                            {
                                var rawPontos = pts.EnumerateArray().ToList();
                                if (rawPontos.Count < 2) continue;
                                if (!PrepararItemOsm(item, "via", out var chave, out var fingerprint)) continue;

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
                                MarcarOsm(plEixo, chave, fingerprint, "via", item);
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
                                foreach (var bordo in AdicionarOffsetCurvas(btr, tr, plEixo, pontos2d, halfWidth, LAYER_VIAS_BORDO))
                                    MarcarOsm(bordo, chave, fingerprint, "via", item);
                                foreach (var bordo in AdicionarOffsetCurvas(btr, tr, plEixo, pontos2d, -halfWidth, LAYER_VIAS_BORDO))
                                    MarcarOsm(bordo, chave, fingerprint, "via", item);
                                total += 2;
                                totalPolylinesCriadas += 2;
                                totalVerticesCriados += pontos2d.Count * 2;

                                // 4. Limites do Passeio / Calçada (Layer VIAS_CALCADA)
                                foreach (var calcada in AdicionarOffsetCurvas(btr, tr, plEixo, pontos2d, distCalcada, LAYER_VIAS_CALCADA))
                                    MarcarOsm(calcada, chave, fingerprint, "via", item);
                                foreach (var calcada in AdicionarOffsetCurvas(btr, tr, plEixo, pontos2d, -distCalcada, LAYER_VIAS_CALCADA))
                                    MarcarOsm(calcada, chave, fingerprint, "via", item);
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
                                        MarcarOsm(txt, chave, fingerprint, "via", item);
                                    }
                                }
                            }
                        }
                    }

                    void DesenharListaPolilinhas(JsonElement arrayElem, string layer, bool fechada, string categoria)
                    {
                        if (arrayElem.ValueKind != JsonValueKind.Array) return;
                        foreach (var item in arrayElem.EnumerateArray())
                        {
                            if (!item.TryGetProperty("pontosUtm", out var pts)
                                || !OsmGeometryPolicy.TryReadCoordinates(pts, out var pontos))
                                continue;
                            if (!PrepararItemOsm(item, categoria, out var chave, out var fingerprint)) continue;

                            string? tipoGeometria = categoria == "obstrucao"
                                && item.TryGetProperty("tipo", out var tipoProp)
                                && tipoProp.ValueKind == JsonValueKind.String
                                    ? tipoProp.GetString()
                                    : null;
                            bool itemFechado = categoria == "obstrucao"
                                ? OsmGeometryPolicy.ShouldClose(tipoGeometria, fechada)
                                : fechada;
                            Polyline pl = new Polyline { Layer = layer, Closed = itemFechado };
                            for (int i = 0; i < pontos.Count; i++)
                            {
                                pl.AddVertexAt(i, new Point2d(pontos[i].X, pontos[i].Y), 0, 0, 0);
                            }

                            btr.AppendEntity(pl);
                            tr.AddNewlyCreatedDBObject(pl, true);
                            MarcarOsm(pl, chave, fingerprint, categoria, item);
                            total++;
                            totalPolylinesCriadas++;
                            totalVerticesCriados += pontos.Count;
                        }
                    }

                    if (root.TryGetProperty("vias", out var vias))
                        DesenharViasComOffsets(vias);

                    if (root.TryGetProperty("calcadas", out var calcadas))
                        DesenharListaPolilinhas(calcadas, LAYER_VIAS_CALCADA, false, "calcada");

                    if (root.TryGetProperty("obstrucoes", out var obstrucoes))
                        DesenharListaPolilinhas(obstrucoes, LAYER_OBSTRUCOES_EDIF, true, "obstrucao");

                    tr.Commit();
                    ed.Regen();
                    ed.WriteMessage($"\n[OSMPALETA][CAD][RESULTADO] polylinesCriadas={totalPolylinesCriadas}; verticesCriados={totalVerticesCriados}; total={total}; atualizados={totalItensAtualizados}; ignorados={totalItensIgnorados};");
                    ed.WriteMessage($"\n[MAPA AUX CAD] {total} elementos urbanos (vias/calçadas/obstruções) desenhados no CAD.");
                    return (true, $"{total} elementos urbanos (vias/calçadas/obstruções) desenhados no CAD.");
                }
            }
            catch (Exception ex)
            {
                return (false, $"Erro ao desenhar elementos urbanos no CAD: {ex.Message}");
            }
        }

        private static List<Entity> AdicionarOffsetCurvas(BlockTableRecord btr, Transaction tr, Polyline basePl, List<Point2d> pontos, double dist, string layer)
        {
            var entidades = new List<Entity>();
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
                            entidades.Add(ent);
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
                Polyline? plAnalitica = OffsetPolylineAnalitico(pontos, dist, layer);
                if (plAnalitica != null)
                {
                    btr.AppendEntity(plAnalitica);
                    tr.AddNewlyCreatedDBObject(plAnalitica, true);
                    entidades.Add(plAnalitica);
                }
            }
            return entidades;
        }

        private static Polyline? OffsetPolylineAnalitico(List<Point2d> pts, double d, string layer)
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
        /// Escaneia o DWG ativo recuperando o modelo topológico completo (Postes e Vãos),
        /// com identidade de domínio persistente (DomainId, VaoId), relacionamentos por ID,
        /// detecção de órfãos e reconciliação rastreável de colisões.
        /// </summary>
        public static EscanearDwgResultado EscanearDwg(int fuso = 23)
        {
            var resultado = new EscanearDwgResultado();
            Document doc = acApp.DocumentManager.MdiActiveDocument;
            if (doc == null) return resultado;

            Database db = doc.Database;
            using (doc.LockDocument())
            {
                // 1. Leitura pura do estado atual do DWG
                LerEstadoDwg(db, fuso, resultado);

                // 2. Reconciliação lógica e topológica (sem mutação do desenho)
                ReconciliarTopologiaDwg(db, resultado);

                // 3. Execução explícita de reparos necessários (se houver clones a corrigir)
                ExecutarReparosDwg(db, fuso, resultado);
            }

            return resultado;
        }

        /// <summary>
        /// Realiza a varredura estritamente somente-leitura do DWG, deserializando XData v1/v2 com tratamento defensivo.
        /// </summary>
        private static void LerEstadoDwg(Database db, int fuso, EscanearDwgResultado resultado)
        {
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                BlockTableRecord btr = (BlockTableRecord)tr.GetObject(db.CurrentSpaceId, OpenMode.ForRead);
                int indiceLegado = 1;
                var handlesPostesProcessados = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                var handlesVaosProcessados = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

                foreach (ObjectId id in btr)
                {
                    Entity ent = (Entity)tr.GetObject(id, OpenMode.ForRead);
                    string handleStr = ent.Handle.ToString();

                    // 1. POSTE
                    bool isPoste = false;
                    Point3d posPoste = Point3d.Origin;
                    if (ent is BlockReference blk)
                    {
                        if (blk.Name.Equals("POSTE_", StringComparison.OrdinalIgnoreCase) ||
                            blk.Layer.Equals(LAYER_POSTES, StringComparison.OrdinalIgnoreCase))
                        {
                            isPoste = true;
                            posPoste = blk.Position;
                        }
                    }
                    else if (ent is Circle circ && circ.Layer.Equals(LAYER_POSTES, StringComparison.OrdinalIgnoreCase))
                    {
                        isPoste = true;
                        posPoste = circ.Center;
                    }

                    if (isPoste && !handlesPostesProcessados.Contains(handleStr))
                    {
                        handlesPostesProcessados.Add(handleStr);
                        double x = posPoste.X;
                        double y = posPoste.Y;
                        var (lat, lon) = SnyderConverter.UtmToLatLon(x, y, fuso, 'S');

                        string domainId = "";
                        string numero = "";
                        string tipoPoste = "11/600";
                        string opId = "";
                        bool temTrafo = false;
                        string potenciaTrafo = "";
                        bool isLegacy = true;
                        bool isValid = true;
                        string invalidReason = "";

                        ResultBuffer? rb = ent.GetXDataForApplication(REGAPP_POSTE);
                        if (rb != null)
                        {
                            try
                            {
                                var arr = rb.AsArray();
                                short schemaVer = 1;
                                var vInt = arr.FirstOrDefault(tv => tv.TypeCode == (short)DxfCode.ExtendedDataInteger16);
                                if (vInt.Value != null)
                                {
                                    try { schemaVer = Convert.ToInt16(vInt.Value); } catch { }
                                }

                                var strings = arr.Where(tv => tv.TypeCode == (short)DxfCode.ExtendedDataAsciiString)
                                                 .Select(tv => tv.Value?.ToString() ?? "")
                                                 .ToList();

                                string? jsonStr = strings.FirstOrDefault(s => s.StartsWith("{"));
                                if (!string.IsNullOrWhiteSpace(jsonStr))
                                {
                                    try
                                    {
                                        using var metaDoc = JsonDocument.Parse(jsonStr);
                                        var mRoot = metaDoc.RootElement;
                                        if (mRoot.TryGetProperty("id", out var pId)) domainId = pId.GetString() ?? "";
                                        else if (mRoot.TryGetProperty("domainId", out var pDId)) domainId = pDId.GetString() ?? "";

                                        if (mRoot.TryGetProperty("numero", out var pN)) numero = pN.GetString() ?? "";
                                        if (mRoot.TryGetProperty("tipoPoste", out var pTp)) tipoPoste = pTp.GetString() ?? tipoPoste;
                                        if (mRoot.TryGetProperty("temTrafo", out var pTt)) temTrafo = pTt.GetBoolean();
                                        if (mRoot.TryGetProperty("potenciaTrafo", out var pPt)) potenciaTrafo = pPt.GetString() ?? "";
                                        if (mRoot.TryGetProperty("operationId", out var pOp)) opId = pOp.GetString() ?? "";
                                    }
                                    catch (Exception exJson)
                                    {
                                        isValid = false;
                                        invalidReason = $"JSON_CORROMPIDO: {exJson.Message}";
                                        resultado.Diagnostics.Add(new DwgDiagnostic
                                        {
                                            Code = "INVALID_XDATA_JSON",
                                            Severity = "WARNING",
                                            EntityType = "POSTE",
                                            EntityId = domainId,
                                            Handle = handleStr,
                                            Message = $"Metadados JSON inválidos: {exJson.Message}"
                                        });
                                    }
                                }

                                if (string.IsNullOrWhiteSpace(domainId) && strings.Count >= 1)
                                {
                                    if (Guid.TryParse(strings[0], out _) || strings[0].StartsWith("poste_", StringComparison.OrdinalIgnoreCase))
                                    {
                                        domainId = strings[0];
                                        if (string.IsNullOrWhiteSpace(numero) && strings.Count >= 2) numero = strings[1];
                                    }
                                    else
                                    {
                                        if (string.IsNullOrWhiteSpace(numero)) numero = strings[0];
                                    }
                                }

                                if (string.IsNullOrWhiteSpace(tipoPoste) && strings.Count >= 3)
                                {
                                    tipoPoste = strings[2];
                                }

                                isLegacy = false;
                                if (schemaVer < 2)
                                {
                                    resultado.Diagnostics.Add(new DwgDiagnostic
                                    {
                                        Code = "LEGACY_ENTITY",
                                        Severity = "INFO",
                                        EntityType = "POSTE",
                                        EntityId = domainId,
                                        Handle = handleStr,
                                        Message = $"Poste possui schema de dados legado (v{schemaVer})."
                                    });
                                }
                                else if (schemaVer > XDATA_SCHEMA_VERSION)
                                {
                                    resultado.Diagnostics.Add(new DwgDiagnostic
                                    {
                                        Code = "UNSUPPORTED_XDATA_VERSION",
                                        Severity = "WARNING",
                                        EntityType = "POSTE",
                                        EntityId = domainId,
                                        Handle = handleStr,
                                        Message = $"Poste possui versão de schema de dados futura não suportada (v{schemaVer} > v{XDATA_SCHEMA_VERSION})."
                                    });
                                }
                            }
                            catch (Exception exRb)
                            {
                                isValid = false;
                                invalidReason = $"XDATA_CORROMPIDO: {exRb.Message}";
                                resultado.Diagnostics.Add(new DwgDiagnostic
                                {
                                    Code = "INVALID_XDATA",
                                    Severity = "ERROR",
                                    EntityType = "POSTE",
                                    EntityId = handleStr,
                                    Handle = handleStr,
                                    Message = $"Falha ao decodificar XData: {exRb.Message}"
                                });
                            }
                        }

                        if (isLegacy || string.IsNullOrWhiteSpace(domainId))
                        {
                            domainId = $"LEGACY_{handleStr}";
                            isLegacy = true;
                        }

                        if (string.IsNullOrWhiteSpace(numero))
                        {
                            numero = indiceLegado < 10 ? $"0{indiceLegado}" : $"{indiceLegado}";
                            indiceLegado++;
                        }

                        resultado.Postes.Add(new PosteDto
                        {
                            Id = domainId,
                            Numero = numero,
                            OperationId = opId,
                            TipoPoste = tipoPoste,
                            TemTrafo = temTrafo,
                            PotenciaTrafo = potenciaTrafo,
                            X = Math.Round(x, 2),
                            Y = Math.Round(y, 2),
                            Latitude = lat,
                            Longitude = lon,
                            Handle = handleStr,
                            IsLegacy = isLegacy,
                            IsValid = isValid,
                            InvalidReason = invalidReason
                        });
                    }

                    // 2. VÃO
                    bool isVao = false;
                    Line? linhaVao = null;
                    if (ent is Line line && (line.Layer.Equals(LAYER_CABOS_BT, StringComparison.OrdinalIgnoreCase) ||
                                             line.Layer.Equals(LAYER_CABOS_MT, StringComparison.OrdinalIgnoreCase)))
                    {
                        isVao = true;
                        linhaVao = line;
                    }

                    if (isVao && linhaVao != null && !handlesVaosProcessados.Contains(handleStr))
                    {
                        handlesVaosProcessados.Add(handleStr);
                        string vaoId = "";
                        string opId = "";
                        string posteOrigemId = "";
                        string posteDestinoId = "";
                        string tipoRede = linhaVao.Layer.Equals(LAYER_CABOS_MT, StringComparison.OrdinalIgnoreCase) ? "MT" : "BT";
                        string textoVao = "";
                        string de = "";
                        string para = "";
                        bool isLegacy = true;
                        bool isValid = true;
                        string invalidReason = "";

                        ResultBuffer? rb = linhaVao.GetXDataForApplication(REGAPP_VAO);
                        if (rb != null)
                        {
                            try
                            {
                                var arr = rb.AsArray();
                                short schemaVer = 1;
                                var vInt = arr.FirstOrDefault(tv => tv.TypeCode == (short)DxfCode.ExtendedDataInteger16);
                                if (vInt.Value != null)
                                {
                                    try { schemaVer = Convert.ToInt16(vInt.Value); } catch { }
                                }

                                var strings = arr.Where(tv => tv.TypeCode == (short)DxfCode.ExtendedDataAsciiString)
                                                 .Select(tv => tv.Value?.ToString() ?? "")
                                                 .ToList();

                                string? jsonStr = strings.FirstOrDefault(s => s.StartsWith("{"));
                                if (!string.IsNullOrWhiteSpace(jsonStr))
                                {
                                    try
                                    {
                                        using var metaDoc = JsonDocument.Parse(jsonStr);
                                        var mRoot = metaDoc.RootElement;
                                        if (mRoot.TryGetProperty("id", out var pId)) vaoId = pId.GetString() ?? "";
                                        else if (mRoot.TryGetProperty("vaoId", out var pVId)) vaoId = pVId.GetString() ?? "";

                                        if (mRoot.TryGetProperty("posteOrigemId", out var pOrig)) posteOrigemId = pOrig.GetString() ?? "";
                                        if (mRoot.TryGetProperty("posteDestinoId", out var pDest)) posteDestinoId = pDest.GetString() ?? "";
                                        if (mRoot.TryGetProperty("tipoRede", out var pTr)) tipoRede = pTr.GetString() ?? tipoRede;
                                        if (mRoot.TryGetProperty("textoVao", out var pTv)) textoVao = pTv.GetString() ?? "";
                                        if (mRoot.TryGetProperty("de", out var pDe)) de = pDe.GetString() ?? "";
                                        if (mRoot.TryGetProperty("para", out var pPara)) para = pPara.GetString() ?? "";
                                        if (mRoot.TryGetProperty("operationId", out var pOp)) opId = pOp.GetString() ?? "";
                                    }
                                    catch (Exception exJson)
                                    {
                                        isValid = false;
                                        invalidReason = $"JSON_CORROMPIDO: {exJson.Message}";
                                        resultado.Diagnostics.Add(new DwgDiagnostic
                                        {
                                            Code = "INVALID_XDATA_JSON",
                                            Severity = "WARNING",
                                            EntityType = "VAO",
                                            EntityId = vaoId,
                                            Handle = handleStr,
                                            Message = $"Metadados JSON do vão inválidos: {exJson.Message}"
                                        });
                                    }
                                }

                                if (string.IsNullOrWhiteSpace(vaoId) && strings.Count >= 1)
                                {
                                    if (Guid.TryParse(strings[0], out _) || strings[0].StartsWith("vao_", StringComparison.OrdinalIgnoreCase))
                                    {
                                        vaoId = strings[0];
                                        if (strings.Count >= 3)
                                        {
                                            if (string.IsNullOrWhiteSpace(posteOrigemId)) posteOrigemId = strings[1];
                                            if (string.IsNullOrWhiteSpace(posteDestinoId)) posteDestinoId = strings[2];
                                        }
                                    }
                                }

                                isLegacy = false;
                                if (schemaVer < 2)
                                {
                                    resultado.Diagnostics.Add(new DwgDiagnostic
                                    {
                                        Code = "LEGACY_ENTITY",
                                        Severity = "INFO",
                                        EntityType = "VAO",
                                        EntityId = vaoId,
                                        Handle = handleStr,
                                        Message = $"Vão possui schema de dados legado (v{schemaVer})."
                                    });
                                }
                                else if (schemaVer > XDATA_SCHEMA_VERSION)
                                {
                                    resultado.Diagnostics.Add(new DwgDiagnostic
                                    {
                                        Code = "UNSUPPORTED_XDATA_VERSION",
                                        Severity = "WARNING",
                                        EntityType = "VAO",
                                        EntityId = vaoId,
                                        Handle = handleStr,
                                        Message = $"Vão possui versão de schema de dados futura não suportada (v{schemaVer} > v{XDATA_SCHEMA_VERSION})."
                                    });
                                }
                            }
                            catch (Exception exRb)
                            {
                                isValid = false;
                                invalidReason = $"XDATA_CORROMPIDO: {exRb.Message}";
                                resultado.Diagnostics.Add(new DwgDiagnostic
                                {
                                    Code = "INVALID_XDATA",
                                    Severity = "ERROR",
                                    EntityType = "VAO",
                                    EntityId = handleStr,
                                    Handle = handleStr,
                                    Message = $"Falha ao ler XData do vão: {exRb.Message}"
                                });
                            }
                        }

                        if (isLegacy || string.IsNullOrWhiteSpace(vaoId))
                        {
                            vaoId = $"LEGACY_{handleStr}";
                            isLegacy = true;
                        }

                        double extensao = Math.Round(linhaVao.Length, 2);
                        if (string.IsNullOrWhiteSpace(textoVao))
                        {
                            textoVao = $"{extensao:F1}m";
                        }

                        resultado.Vaos.Add(new VaoDto
                        {
                            Id = vaoId,
                            OperationId = opId,
                            PosteOrigemId = posteOrigemId,
                            PosteDestinoId = posteDestinoId,
                            TipoRede = tipoRede,
                            TextoVao = textoVao,
                            Extensao = extensao.ToString("F1"),
                            ExtensaoMetros = extensao,
                            X1 = Math.Round(linhaVao.StartPoint.X, 2),
                            Y1 = Math.Round(linhaVao.StartPoint.Y, 2),
                            X2 = Math.Round(linhaVao.EndPoint.X, 2),
                            Y2 = Math.Round(linhaVao.EndPoint.Y, 2),
                            Handle = handleStr,
                            De = de,
                            Para = para,
                            IsLegacy = isLegacy,
                            IsValid = isValid,
                            InvalidReason = invalidReason
                        });
                    }
                }

                tr.Commit();
            }
        }

        /// <summary>
        /// Executa a reconciliação topológica em memória, detectando órfãos, inferindo conexões geométricas legadas e avaliando colisões.
        /// </summary>
        private static void ReconciliarTopologiaDwg(Database db, EscanearDwgResultado resultado)
        {
            var mapaPostes = resultado.Postes.ToDictionary(p => p.Id, StringComparer.OrdinalIgnoreCase);

            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                foreach (var vao in resultado.Vaos)
                {
                    bool temOrigemId = !string.IsNullOrWhiteSpace(vao.PosteOrigemId);
                    bool temDestinoId = !string.IsNullOrWhiteSpace(vao.PosteDestinoId);

                    // 1. Resolução Canônica por Identidade
                    if (temOrigemId && temDestinoId)
                    {
                        bool origExiste = mapaPostes.ContainsKey(vao.PosteOrigemId);
                        bool destExiste = mapaPostes.ContainsKey(vao.PosteDestinoId);

                        if (origExiste && destExiste)
                        {
                            vao.ResolutionMethod = "Identity";
                            vao.ResolutionConfidence = "Exact";
                            resultado.Relacoes.Add(new DwgRelation
                            {
                                VaoId = vao.Id,
                                PosteOrigemId = vao.PosteOrigemId,
                                PosteDestinoId = vao.PosteDestinoId,
                                Method = "Identity",
                                Confidence = "Exact"
                            });
                        }
                        else
                        {
                            // Vão com referência quebrada (Poste apagado via ERASE nativo)
                            vao.IsOrphan = true;
                            vao.OrphanReason = !origExiste && !destExiste
                                ? "Ambos os postes de origem e destino foram removidos do DWG."
                                : (!origExiste ? $"Poste de origem '{vao.PosteOrigemId}' não encontrado no DWG." : $"Poste de destino '{vao.PosteDestinoId}' não encontrado no DWG.");

                            resultado.Diagnostics.Add(new DwgDiagnostic
                            {
                                Code = "ORPHAN_VAO",
                                Severity = "WARNING",
                                EntityType = "VAO",
                                EntityId = vao.Id,
                                Handle = vao.Handle,
                                Message = $"Vão órfão detectado: {vao.OrphanReason}"
                            });
                        }
                        continue;
                    }

                    // 2. Resolução Topológica por Proximidade Geométrica (Legado / Não anotado)
                    try
                    {
                        ObjectId lId = db.GetObjectId(false, new Handle(Convert.ToInt64(vao.Handle, 16)), 0);
                        if (!lId.IsNull && lId.IsValid)
                        {
                            Line line = (Line)tr.GetObject(lId, OpenMode.ForRead);
                            var p1 = line.StartPoint;
                            var p2 = line.EndPoint;

                            double DistP(PosteDto p, Point3d pt)
                            {
                                double dx = p.X - pt.X;
                                double dy = p.Y - pt.Y;
                                return Math.Sqrt(dx * dx + dy * dy);
                            }

                            const double LIMITE_DIST_LEGADO = 1.0;

                            // Candidatos de Origem
                            var candsOrigem = resultado.Postes
                                .Select(p => new { Poste = p, Dist = DistP(p, p1) })
                                .Where(c => c.Dist <= LIMITE_DIST_LEGADO)
                                .OrderBy(c => c.Dist)
                                .ToList();

                            // Candidatos de Destino
                            var candsDestino = resultado.Postes
                                .Select(p => new { Poste = p, Dist = DistP(p, p2) })
                                .Where(c => c.Dist <= LIMITE_DIST_LEGADO)
                                .OrderBy(c => c.Dist)
                                .ToList();

                            bool origemResolvida = false;
                            bool destinoResolvido = false;

                            if (candsOrigem.Count == 1)
                            {
                                vao.PosteOrigemId = candsOrigem[0].Poste.Id;
                                if (string.IsNullOrWhiteSpace(vao.De)) vao.De = candsOrigem[0].Poste.Numero;
                                origemResolvida = true;
                            }
                            else if (candsOrigem.Count > 1)
                            {
                                resultado.Diagnostics.Add(new DwgDiagnostic
                                {
                                    Code = "AMBIGUOUS_GEOMETRY_MATCH",
                                    Severity = "WARNING",
                                    EntityType = "VAO",
                                    EntityId = vao.Id,
                                    Handle = vao.Handle,
                                    Message = $"Ambiguidade geométrica na origem: {candsOrigem.Count} postes a < 1.0m da extremidade."
                                });
                            }

                            if (candsDestino.Count == 1)
                            {
                                vao.PosteDestinoId = candsDestino[0].Poste.Id;
                                if (string.IsNullOrWhiteSpace(vao.Para)) vao.Para = candsDestino[0].Poste.Numero;
                                destinoResolvido = true;
                            }
                            else if (candsDestino.Count > 1)
                            {
                                resultado.Diagnostics.Add(new DwgDiagnostic
                                {
                                    Code = "AMBIGUOUS_GEOMETRY_MATCH",
                                    Severity = "WARNING",
                                    EntityType = "VAO",
                                    EntityId = vao.Id,
                                    Handle = vao.Handle,
                                    Message = $"Ambiguidade geométrica no destino: {candsDestino.Count} postes a < 1.0m da extremidade."
                                });
                            }

                            if (origemResolvida && destinoResolvido)
                            {
                                vao.ResolutionMethod = "Geometry";
                                vao.ResolutionConfidence = "Inferred";
                                resultado.Relacoes.Add(new DwgRelation
                                {
                                    VaoId = vao.Id,
                                    PosteOrigemId = vao.PosteOrigemId,
                                    PosteDestinoId = vao.PosteDestinoId,
                                    Method = "Geometry",
                                    Confidence = "Inferred"
                                });
                            }
                            else
                            {
                                vao.ResolutionMethod = "Unresolved";
                                vao.ResolutionConfidence = (candsOrigem.Count > 1 || candsDestino.Count > 1) ? "Ambiguous" : "Unresolved";
                                vao.IsOrphan = true;
                                vao.OrphanReason = "Vão legado sem ancoragem geométrica unívoca em postes.";
                                resultado.Diagnostics.Add(new DwgDiagnostic
                                {
                                    Code = "ORPHAN_VAO",
                                    Severity = "WARNING",
                                    EntityType = "VAO",
                                    EntityId = vao.Id,
                                    Handle = vao.Handle,
                                    Message = "Vão legado sem ancoragem unívoca em postes."
                                });
                            }
                        }
                    }
                    catch { }
                }

                tr.Commit();
            }
        }

        /// <summary>
        /// Executa mutação explícita controlada no DWG para reparar colisões de IDs geradas por comandos COPY/ARRAY,
        /// preservando rastreabilidade total nos diagnósticos.
        /// </summary>
        private static void ExecutarReparosDwg(Database db, int fuso, EscanearDwgResultado resultado)
        {
            var domainIdsPostesVistos = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var vaoIdsVistos = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var remapeamentoPostesClonados = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            int clonesReparados = 0;

            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                // 1. Reparação de Postes Duplicados por COPY
                foreach (var p in resultado.Postes)
                {
                    if (p.IsLegacy) continue;

                    if (domainIdsPostesVistos.Contains(p.Id))
                    {
                        string idAntigo = p.Id;
                        string novoDomainId = Guid.NewGuid().ToString("D");
                        p.Id = novoDomainId;
                        remapeamentoPostesClonados[idAntigo] = novoDomainId;
                        clonesReparados++;

                        try
                        {
                            ObjectId pId = db.GetObjectId(false, new Handle(Convert.ToInt64(p.Handle, 16)), 0);
                            if (!pId.IsNull && pId.IsValid)
                            {
                                Entity ent = (Entity)tr.GetObject(pId, OpenMode.ForWrite);
                                var payloadClone = new PostePayload
                                {
                                    Id = novoDomainId,
                                    Numero = p.Numero,
                                    TipoPoste = p.TipoPoste,
                                    TemTrafo = p.TemTrafo,
                                    PotenciaTrafo = p.PotenciaTrafo,
                                    FusoUtm = fuso,
                                    X = p.X,
                                    Y = p.Y
                                };
                                GravarXDataPoste(ent, db, tr, payloadClone, p.OperationId);

                                resultado.Diagnostics.Add(new DwgDiagnostic
                                {
                                    Code = "COPY_REPAIRED",
                                    Severity = "INFO",
                                    EntityType = "POSTE",
                                    EntityId = novoDomainId,
                                    Handle = p.Handle,
                                    Message = $"Colisão de COPY detectada no poste {p.Numero}. DomainId reatribuído de '{idAntigo}' para '{novoDomainId}'."
                                });
                            }
                        }
                        catch (Exception exRep)
                        {
                            resultado.Diagnostics.Add(new DwgDiagnostic
                            {
                                Code = "REPAIR_FAILED",
                                Severity = "ERROR",
                                EntityType = "POSTE",
                                EntityId = p.Id,
                                Handle = p.Handle,
                                Message = $"Falha ao gravar reparo no DWG: {exRep.Message}"
                            });
                        }
                    }

                    domainIdsPostesVistos.Add(p.Id);
                }

                // 2. Reparação de Vãos Duplicados e Reconstrução de Conjunto Copiado (Poste + Vão)
                foreach (var v in resultado.Vaos)
                {
                    if (v.IsLegacy) continue;

                    bool precisaGravar = false;
                    string idAntigoVao = v.Id;

                    if (vaoIdsVistos.Contains(v.Id))
                    {
                        string novoVaoId = Guid.NewGuid().ToString("D");
                        v.Id = novoVaoId;
                        precisaGravar = true;
                        clonesReparados++;

                        resultado.Diagnostics.Add(new DwgDiagnostic
                        {
                            Code = "COPY_REPAIRED",
                            Severity = "INFO",
                            EntityType = "VAO",
                            EntityId = novoVaoId,
                            Handle = v.Handle,
                            Message = $"Colisão de COPY detectada no vão. VaoId reatribuído de '{idAntigoVao}' para '{novoVaoId}'."
                        });
                    }

                    // Auditoria de Integridade de COPY SET:
                    // Um vão só pertence com certeza ao conjunto copiado se AMBOS os postes (origem e destino)
                    // foram remapeados na mesma operação de cópia.
                    // Se apenas um foi clonado ou se há incerteza, o sistema emite COPY_SET_UNCERTAIN
                    // e NÃO redireciona referências arbitrariamente.
                    bool origemClonada = remapeamentoPostesClonados.TryGetValue(v.PosteOrigemId, out var novoOrigemId);
                    bool destinoClonada = remapeamentoPostesClonados.TryGetValue(v.PosteDestinoId, out var novoDestinoId);

                    if (origemClonada && destinoClonada)
                    {
                        v.PosteOrigemId = novoOrigemId!;
                        v.PosteDestinoId = novoDestinoId!;
                        precisaGravar = true;
                        resultado.Diagnostics.Add(new DwgDiagnostic
                        {
                            Code = "COPY_SET_REPAIRED",
                            Severity = "INFO",
                            EntityType = "VAO",
                            EntityId = v.Id,
                            Handle = v.Handle,
                            Message = $"Conjunto copiado íntegro detectado e remapeado com sucesso (Origem '{novoOrigemId}', Destino '{novoDestinoId}')."
                        });
                    }
                    else if (origemClonada != destinoClonada)
                    {
                        // Apenas um poste foi copiado ou o vão foi copiado parcialmente: ambiguidade topológica
                        resultado.Diagnostics.Add(new DwgDiagnostic
                        {
                            Code = "COPY_SET_UNCERTAIN",
                            Severity = "WARNING",
                            EntityType = "VAO",
                            EntityId = v.Id,
                            Handle = v.Handle,
                            Message = $"Cópia de conjunto ambígua: apenas uma das extremidades foi remapeada. Referências originais preservadas sem redirecionamento arbitrário."
                        });
                    }

                    if (precisaGravar)
                    {
                        try
                        {
                            ObjectId vId = db.GetObjectId(false, new Handle(Convert.ToInt64(v.Handle, 16)), 0);
                            if (!vId.IsNull && vId.IsValid)
                            {
                                Line linhaVao = (Line)tr.GetObject(vId, OpenMode.ForWrite);
                                GravarXDataVao(linhaVao, db, tr, v.Id, v.PosteOrigemId, v.PosteDestinoId, v.TipoRede, v.TextoVao, v.OperationId, v.De, v.Para);
                            }
                        }
                        catch { }
                    }

                    vaoIdsVistos.Add(v.Id);
                }

                tr.Commit();
            }

            // Estatísticas consolidadas
            resultado.Statistics = new DwgStatistics
            {
                TotalPostes = resultado.Postes.Count,
                TotalVaos = resultado.Vaos.Count,
                PostesValidos = resultado.Postes.Count(p => p.IsValid),
                VaosValidos = resultado.Vaos.Count(v => v.IsValid),
                PostesLegados = resultado.Postes.Count(p => p.IsLegacy),
                VaosLegados = resultado.Vaos.Count(v => v.IsLegacy),
                VaosOrfaos = resultado.Vaos.Count(v => v.IsOrphan),
                ClonesReparados = clonesReparados,
                ErrosXData = resultado.Diagnostics.Count(d => d.Code.StartsWith("INVALID_XDATA"))
            };
        }

        /// <summary>
        /// Escaneia todos os postes inseridos no DWG ativo (mantido para compatibilidade legado).
        /// </summary>
        public static List<Dictionary<string, object>> EscanearPostesDwg(int fuso = 23)
        {
            return EscanearDwg(fuso).Postes.Select(p => p.ToDictionary()).ToList();
        }

        /// <summary>
        /// Desfaz com segurança cirúrgica as entidades criadas pela última operação ou operação específica no DWG.
        /// Prioriza OperationId e DomainId sobre número visual (GAP-005).
        /// </summary>
        public static (bool Success, string Message) DesfazerUltimaOperacao(string? domainId = null, string? opId = null, string? numero = null)
        {
            Document doc = acApp.DocumentManager.MdiActiveDocument;
            if (doc == null)
            {
                return (false, "Nenhum documento DWG ativo no AutoCAD.");
            }

            Database db = doc.Database;
            Editor ed = doc.Editor;
            int totalApagados = 0;

            try
            {
                using (doc.LockDocument())
                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    List<CadOperacaoRegistro> operacoesAlvo = new();

                    lock (_historicoOperacoes)
                    {
                        if (!string.IsNullOrWhiteSpace(opId))
                        {
                            operacoesAlvo = _historicoOperacoes.Where(o => o.OperationId == opId).ToList();
                        }
                        else if (!string.IsNullOrWhiteSpace(domainId))
                        {
                            operacoesAlvo = _historicoOperacoes.Where(o => o.DomainId == domainId).ToList();
                        }
                        else if (!string.IsNullOrWhiteSpace(numero))
                        {
                            string numLimpo = numero!.Trim().TrimStart('P', 'p');
                            operacoesAlvo = _historicoOperacoes.Where(o =>
                                (o.Identificador != null && o.Identificador.Equals(numero.Trim(), StringComparison.OrdinalIgnoreCase)) ||
                                (o.Identificador != null && o.Identificador.Equals(numLimpo, StringComparison.OrdinalIgnoreCase)) ||
                                (o.Identificador != null && o.Identificador.Equals($"P{numLimpo}", StringComparison.OrdinalIgnoreCase))).ToList();
                        }
                        else if (_historicoOperacoes.Count > 0)
                        {
                            operacoesAlvo.Add(_historicoOperacoes.Last());
                        }

                        foreach (var op in operacoesAlvo)
                        {
                            _historicoOperacoes.Remove(op);
                        }
                    }

                    // Apaga entidades pelos Handles registrados na sessão
                    foreach (var op in operacoesAlvo)
                    {
                        foreach (var h in op.Handles)
                        {
                            try
                            {
                                ObjectId objId = db.GetObjectId(false, h, 0);
                                if (!objId.IsNull && objId.IsValid)
                                {
                                    DBObject obj = tr.GetObject(objId, OpenMode.ForWrite);
                                    if (obj is Entity ent && !ent.IsErased)
                                    {
                                        ent.Erase(true);
                                        totalApagados++;
                                    }
                                }
                            }
                            catch
                            {
                                // Entidade já excluída ou handle inválido
                            }
                        }
                    }

                    // Fallback persistente caso a sessão do AutoCAD tenha sido reiniciada (via XData)
                    // GAP-005: Utiliza DomainId e OperationId como chaves primárias.
                    if (totalApagados == 0 && (!string.IsNullOrWhiteSpace(opId) || !string.IsNullOrWhiteSpace(domainId) || !string.IsNullOrWhiteSpace(numero)))
                    {
                        BlockTableRecord btr = (BlockTableRecord)tr.GetObject(db.CurrentSpaceId, OpenMode.ForWrite);
                        foreach (ObjectId id in btr)
                        {
                            Entity ent = (Entity)tr.GetObject(id, OpenMode.ForRead);
                            bool deveApagar = false;

                            ResultBuffer? rb = ent.GetXDataForApplication(REGAPP_POSTE) ?? ent.GetXDataForApplication(REGAPP_VAO);
                            if (rb != null)
                            {
                                var arr = rb.AsArray();
                                var strings = arr.Where(tv => tv.TypeCode == (short)DxfCode.ExtendedDataAsciiString)
                                                 .Select(tv => tv.Value?.ToString() ?? "")
                                                 .ToList();

                                // 1. Checagem em JSON metadata por id/domainId/operationId
                                string? jsonStr = strings.FirstOrDefault(s => s.StartsWith("{"));
                                if (!string.IsNullOrWhiteSpace(jsonStr))
                                {
                                    try
                                    {
                                        using var metaDoc = JsonDocument.Parse(jsonStr);
                                        var mRoot = metaDoc.RootElement;
                                        if (!string.IsNullOrWhiteSpace(opId) && mRoot.TryGetProperty("operationId", out var pOp) && pOp.GetString() == opId)
                                        {
                                            deveApagar = true;
                                        }
                                        else if (!string.IsNullOrWhiteSpace(domainId))
                                        {
                                            if (mRoot.TryGetProperty("id", out var pId) && pId.GetString() == domainId) deveApagar = true;
                                            else if (mRoot.TryGetProperty("domainId", out var pDId) && pDId.GetString() == domainId) deveApagar = true;
                                        }
                                    }
                                    catch { }
                                }

                                // 2. Checagem em strings do ResultBuffer
                                if (!deveApagar)
                                {
                                    foreach (var s in strings)
                                    {
                                        if (!string.IsNullOrWhiteSpace(opId) && s == opId)
                                        {
                                            deveApagar = true;
                                            break;
                                        }
                                        if (!string.IsNullOrWhiteSpace(domainId) && s == domainId)
                                        {
                                            deveApagar = true;
                                            break;
                                        }
                                    }
                                }

                                // 3. Fallback estritamente legado se e somente se opId e domainId forem nulos
                                if (!deveApagar && string.IsNullOrWhiteSpace(opId) && string.IsNullOrWhiteSpace(domainId) && !string.IsNullOrWhiteSpace(numero))
                                {
                                    string numLimpo = numero!.Trim().TrimStart('P', 'p');
                                    foreach (var s in strings)
                                    {
                                        if (s.Equals(numero.Trim(), StringComparison.OrdinalIgnoreCase) ||
                                            s.Equals(numLimpo, StringComparison.OrdinalIgnoreCase) ||
                                            s.Equals($"P{numLimpo}", StringComparison.OrdinalIgnoreCase))
                                        {
                                            deveApagar = true;
                                            break;
                                        }
                                    }
                                }
                            }

                            if (deveApagar)
                            {
                                ent.UpgradeOpen();
                                ent.Erase(true);
                                totalApagados++;
                            }
                        }
                    }

                    tr.Commit();
                }

                ed.Regen();
                string msg = totalApagados > 0
                    ? $"↩️ Rollback DWG: {totalApagados} entidade(s) removida(s) no AutoCAD."
                    : "↩️ Traçado desfeito no mapa (nenhuma entidade pendente no CAD).";
                return (true, msg);
            }
            catch (Exception ex)
            {
                return (false, $"Erro ao desfazer no CAD: {ex.Message}");
            }
        }

        private static Dictionary<string, List<OsmEntityRef>> IndexarEntidadesOsm(Database db, Transaction tr)
        {
            var resultado = new Dictionary<string, List<OsmEntityRef>>(StringComparer.Ordinal);
            var btr = (BlockTableRecord)tr.GetObject(db.CurrentSpaceId, OpenMode.ForRead);
            foreach (ObjectId objectId in btr)
            {
                if (objectId.IsNull || objectId.IsErased) continue;
                if (tr.GetObject(objectId, OpenMode.ForRead, false) is not Entity entidade) continue;
                var metadata = LerMetadataOsm(entidade);
                if (metadata == null || string.IsNullOrWhiteSpace(metadata.Key)) continue;
                if (!resultado.TryGetValue(metadata.Key, out var entidades))
                {
                    entidades = new List<OsmEntityRef>();
                    resultado[metadata.Key] = entidades;
                }
                entidades.Add(new OsmEntityRef { ObjectId = objectId, Fingerprint = metadata.Fingerprint });
            }
            return resultado;
        }

        private static OsmMetadata? LerMetadataOsm(Entity entidade)
        {
            try
            {
                using ResultBuffer? rb = entidade.GetXDataForApplication(REGAPP_OSM);
                if (rb == null) return null;
                string? json = rb.AsArray()
                    .Where(tv => tv.TypeCode == (short)DxfCode.ExtendedDataAsciiString)
                    .Select(tv => tv.Value?.ToString())
                    .LastOrDefault(value => !string.IsNullOrWhiteSpace(value));
                if (json == null || json.Length == 0) return null;
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;
                string key = root.TryGetProperty("key", out var keyProp) ? keyProp.GetString() ?? "" : "";
                string fingerprint = root.TryGetProperty("fingerprint", out var fpProp) ? fpProp.GetString() ?? "" : "";
                return new OsmMetadata { Key = key, Fingerprint = fingerprint };
            }
            catch
            {
                return null;
            }
        }

        private static string ConstruirChaveOsm(JsonElement item, string categoria)
        {
            if (!item.TryGetProperty("osmId", out var idProp)) return "";
            string osmId = idProp.ValueKind switch
            {
                JsonValueKind.String => idProp.GetString() ?? "",
                JsonValueKind.Number => idProp.GetRawText(),
                _ => ""
            };
            if (string.IsNullOrWhiteSpace(osmId)) return "";
            string osmType = item.TryGetProperty("osmType", out var typeProp)
                ? typeProp.GetString() ?? "way"
                : "way";
            return $"{osmType}:{osmId}:{categoria}";
        }

        private static string CalcularFingerprintOsm(JsonElement item, string categoria)
        {
            string material = $"{categoria}|{item.GetRawText()}";
            using var sha256 = SHA256.Create();
            byte[] hash = sha256.ComputeHash(Encoding.UTF8.GetBytes(material));
            return BitConverter.ToString(hash).Replace("-", "");
        }

        private static void GravarXDataOsm(Entity ent, Database db, Transaction tr, string key, string fingerprint, string categoria, JsonElement item)
        {
            GarantirRegApp(db, tr, REGAPP_OSM);
            string osmId = item.TryGetProperty("osmId", out var idProp) ? idProp.ToString() : "";
            string osmType = item.TryGetProperty("osmType", out var typeProp) ? typeProp.GetString() ?? "way" : "way";
            string jsonMetadata = JsonSerializer.Serialize(new
            {
                schemaVersion = 1,
                source = "OSM",
                key,
                fingerprint,
                osmType,
                osmId,
                categoria
            });
            using var rb = new ResultBuffer(
                new TypedValue((int)DxfCode.ExtendedDataRegAppName, REGAPP_OSM),
                new TypedValue((int)DxfCode.ExtendedDataInteger16, 1),
                new TypedValue((int)DxfCode.ExtendedDataAsciiString, key),
                new TypedValue((int)DxfCode.ExtendedDataAsciiString, fingerprint),
                new TypedValue((int)DxfCode.ExtendedDataAsciiString, jsonMetadata)
            );
            ent.XData = rb;
        }

        private static void GarantirRegApp(Database db, Transaction tr, string appName)
        {
            RegAppTable rat = (RegAppTable)tr.GetObject(db.RegAppTableId, OpenMode.ForRead);
            if (!rat.Has(appName))
            {
                rat.UpgradeOpen();
                RegAppTableRecord ratr = new RegAppTableRecord { Name = appName };
                rat.Add(ratr);
                tr.AddNewlyCreatedDBObject(ratr, true);
            }
        }

        private static void GravarXDataPoste(Entity ent, Database db, Transaction tr, PostePayload payload, string operationId)
        {
            try
            {
                GarantirRegApp(db, tr, REGAPP_POSTE);
                string domainId = !string.IsNullOrWhiteSpace(payload.Id) ? payload.Id : Guid.NewGuid().ToString("D");
                string jsonMetadata = JsonSerializer.Serialize(new
                {
                    schemaVersion = (int)XDATA_SCHEMA_VERSION,
                    id = domainId,
                    domainId = domainId,
                    numero = payload.Numero,
                    tipoPoste = payload.TipoPoste,
                    estruturasMt = payload.EstruturasMt,
                    estruturasBt = payload.EstruturasBt,
                    equipamentos = payload.Equipamentos,
                    cargaTri = payload.CargaTri,
                    temTrafo = payload.TemTrafo,
                    potenciaTrafo = payload.PotenciaTrafo,
                    fusoUtm = payload.FusoUtm,
                    operationId = operationId
                });

                using var rb = new ResultBuffer(
                    new TypedValue((int)DxfCode.ExtendedDataRegAppName, REGAPP_POSTE),
                    new TypedValue((int)DxfCode.ExtendedDataInteger16, XDATA_SCHEMA_VERSION),
                    new TypedValue((int)DxfCode.ExtendedDataAsciiString, domainId),
                    new TypedValue((int)DxfCode.ExtendedDataAsciiString, payload.Numero ?? ""),
                    new TypedValue((int)DxfCode.ExtendedDataAsciiString, payload.TipoPoste ?? ""),
                    new TypedValue((int)DxfCode.ExtendedDataAsciiString, operationId ?? ""),
                    new TypedValue((int)DxfCode.ExtendedDataAsciiString, jsonMetadata)
                );
                ent.XData = rb;
            }
            catch { }
        }

        private static void GravarXDataVao(Entity ent, Database db, Transaction tr,
            string vaoId, string? posteOrigemId, string? posteDestinoId,
            string tipoRede, string textoVao, string operationId,
            string? numDe = null, string? numPara = null)
        {
            try
            {
                GarantirRegApp(db, tr, REGAPP_VAO);
                string vId = !string.IsNullOrWhiteSpace(vaoId) ? vaoId : Guid.NewGuid().ToString("D");
                string jsonMetadata = JsonSerializer.Serialize(new
                {
                    schemaVersion = (int)XDATA_SCHEMA_VERSION,
                    id = vId,
                    vaoId = vId,
                    posteOrigemId = posteOrigemId ?? "",
                    posteDestinoId = posteDestinoId ?? "",
                    tipoRede = tipoRede,
                    textoVao = textoVao,
                    de = numDe,
                    para = numPara,
                    operationId = operationId
                });

                using var rb = new ResultBuffer(
                    new TypedValue((int)DxfCode.ExtendedDataRegAppName, REGAPP_VAO),
                    new TypedValue((int)DxfCode.ExtendedDataInteger16, XDATA_SCHEMA_VERSION),
                    new TypedValue((int)DxfCode.ExtendedDataAsciiString, vId),
                    new TypedValue((int)DxfCode.ExtendedDataAsciiString, posteOrigemId ?? ""),
                    new TypedValue((int)DxfCode.ExtendedDataAsciiString, posteDestinoId ?? ""),
                    new TypedValue((int)DxfCode.ExtendedDataAsciiString, tipoRede ?? ""),
                    new TypedValue((int)DxfCode.ExtendedDataAsciiString, textoVao ?? ""),
                    new TypedValue((int)DxfCode.ExtendedDataAsciiString, operationId ?? ""),
                    new TypedValue((int)DxfCode.ExtendedDataAsciiString, jsonMetadata)
                );
                ent.XData = rb;
            }
            catch { }
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
                    Color = Autodesk.AutoCAD.Colors.Color.FromColorIndex(ColorMethod.ByAci, colorIndex),
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

        private static List<Entity> InserirGeometriaPoste(Database db, Transaction tr, BlockTableRecord btr, BlockTable bt, Point3d pt)
        {
            var criadas = new List<Entity>();
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
                criadas.Add(br);
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
                criadas.Add(circ);
                criadas.Add(l1);
                criadas.Add(l2);
            }
            return criadas;
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

        private static List<Entity> InserirBlocoTrafo(Database db, Transaction tr, BlockTableRecord btr, BlockTable bt, Point3d pt, PostePayload payload)
        {
            var criadas = new List<Entity>();
            // Procura a simbologia oficial de transformador da concessionária: TRAFO1, TRAFO, T ou TRANSF
            string[] nomesBlocos = new string[] { "TRAFO1", "TRAFO", "T", "TRANSF" };
            string? nomeEncontrado = null;
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
                criadas.Add(br);

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
                criadas.Add(circ1);
                criadas.Add(circ2);
            }
            return criadas;
        }

        private static List<Entity> InserirNumeroPoste(Database db, Transaction tr, BlockTableRecord btr, BlockTable bt, Point3d pt, string numero)
        {
            var criadas = new List<Entity>();
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
                criadas.Add(br);

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
                criadas.Add(c);
                criadas.Add(txt);
            }
            return criadas;
        }

        private static Entity? InserirDescricaoTecnica(Transaction tr, BlockTableRecord btr, Point3d pt, PostePayload payload)
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

            if (linhas.Count == 0) return null;

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
            return mtext;
        }
    }
}
