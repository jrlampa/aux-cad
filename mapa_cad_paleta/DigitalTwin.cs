using System;
using System.Collections.Generic;
using System.Linq;

namespace MapaCadPaleta
{
    public enum TwinDataStatus
    {
        Disponivel,
        Derivavel,
        NaoDisponivel
    }

    public sealed class TwinDataSource
    {
        public TwinDataSource(string source, TwinDataStatus status)
        {
            Source = source ?? string.Empty;
            Status = status;
        }

        public string Source { get; }
        public TwinDataStatus Status { get; }
    }

    public sealed class PosteTwin
    {
        public PosteTwin(
            string domainId,
            string handle,
            string numero,
            double x,
            double y,
            double? z,
            string operationId,
            string tipoPoste,
            bool temTrafo,
            string potenciaTrafo,
            bool isLegacy,
            TwinDataSource source)
        {
            DomainId = domainId ?? string.Empty;
            Handle = handle ?? string.Empty;
            Numero = numero ?? string.Empty;
            X = x;
            Y = y;
            Z = z;
            OperationId = operationId ?? string.Empty;
            TipoPoste = tipoPoste ?? string.Empty;
            TemTrafo = temTrafo;
            PotenciaTrafo = potenciaTrafo ?? string.Empty;
            IsLegacy = isLegacy;
            Source = source ?? throw new ArgumentNullException(nameof(source));
        }

        public string DomainId { get; }
        public string Handle { get; }
        public string Numero { get; }
        public double X { get; }
        public double Y { get; }
        public double? Z { get; }
        public string OperationId { get; }
        public string TipoPoste { get; }
        public bool TemTrafo { get; }
        public string PotenciaTrafo { get; }
        public bool IsLegacy { get; }
        public TwinDataSource Source { get; }
    }

    public sealed class VaoTwin
    {
        public VaoTwin(
            string vaoId,
            string handle,
            string posteOrigemId,
            string posteDestinoId,
            double x1,
            double y1,
            double x2,
            double y2,
            double extensaoMetros,
            string operationId,
            string tipoRede,
            string textoVao,
            bool isLegacy,
            bool isOrphan,
            TwinDataSource source)
        {
            VaoId = vaoId ?? string.Empty;
            Handle = handle ?? string.Empty;
            PosteOrigemId = posteOrigemId ?? string.Empty;
            PosteDestinoId = posteDestinoId ?? string.Empty;
            X1 = x1;
            Y1 = y1;
            X2 = x2;
            Y2 = y2;
            ExtensaoMetros = extensaoMetros;
            OperationId = operationId ?? string.Empty;
            TipoRede = tipoRede ?? string.Empty;
            TextoVao = textoVao ?? string.Empty;
            IsLegacy = isLegacy;
            IsOrphan = isOrphan;
            Source = source ?? throw new ArgumentNullException(nameof(source));
        }

        public string VaoId { get; }
        public string Handle { get; }
        public string PosteOrigemId { get; }
        public string PosteDestinoId { get; }
        public double X1 { get; }
        public double Y1 { get; }
        public double X2 { get; }
        public double Y2 { get; }
        public double ExtensaoMetros { get; }
        public string OperationId { get; }
        public string TipoRede { get; }
        public string TextoVao { get; }
        public bool IsLegacy { get; }
        public bool IsOrphan { get; }
        public TwinDataSource Source { get; }
    }

    public sealed class TwinTopologyRelation
    {
        public TwinTopologyRelation(string vaoId, string posteOrigemId, string posteDestinoId, string method, string confidence)
        {
            VaoId = vaoId ?? string.Empty;
            PosteOrigemId = posteOrigemId ?? string.Empty;
            PosteDestinoId = posteDestinoId ?? string.Empty;
            Method = method ?? string.Empty;
            Confidence = confidence ?? string.Empty;
        }

        public string VaoId { get; }
        public string PosteOrigemId { get; }
        public string PosteDestinoId { get; }
        public string Method { get; }
        public string Confidence { get; }
    }

    public sealed class TwinDiagnostic
    {
        public TwinDiagnostic(string code, string severity, string entityType, string entityId, string handle, string message)
        {
            Code = code ?? string.Empty;
            Severity = severity ?? string.Empty;
            EntityType = entityType ?? string.Empty;
            EntityId = entityId ?? string.Empty;
            Handle = handle ?? string.Empty;
            Message = message ?? string.Empty;
        }

        public string Code { get; }
        public string Severity { get; }
        public string EntityType { get; }
        public string EntityId { get; }
        public string Handle { get; }
        public string Message { get; }
    }

    public sealed class TwinConnectedComponent
    {
        public TwinConnectedComponent(IEnumerable<string> posteIds, IEnumerable<string> vaoIds)
        {
            PosteIds = (posteIds ?? throw new ArgumentNullException(nameof(posteIds))).ToList().AsReadOnly();
            VaoIds = (vaoIds ?? throw new ArgumentNullException(nameof(vaoIds))).ToList().AsReadOnly();
        }

        public IReadOnlyList<string> PosteIds { get; }
        public IReadOnlyList<string> VaoIds { get; }
    }

    public sealed class DigitalTwin
    {
        private readonly TwinTopologyGraph _graph;

        public DigitalTwin(
            int modelVersion,
            string constructionSource,
            IEnumerable<PosteTwin> postes,
            IEnumerable<VaoTwin> vaos,
            IEnumerable<TwinTopologyRelation> topology,
            IEnumerable<TwinDiagnostic> diagnostics)
            : this(modelVersion, constructionSource, postes, vaos, topology, diagnostics, null)
        {
        }

        internal DigitalTwin(
            int modelVersion,
            string constructionSource,
            IEnumerable<PosteTwin> postes,
            IEnumerable<VaoTwin> vaos,
            IEnumerable<TwinTopologyRelation> topology,
            IEnumerable<TwinDiagnostic> diagnostics,
            TwinTopologyGraph? graph)
        {
            ModelVersion = modelVersion;
            ConstructionSource = constructionSource ?? string.Empty;
            Postes = (postes ?? throw new ArgumentNullException(nameof(postes))).ToList().AsReadOnly();
            Vaos = (vaos ?? throw new ArgumentNullException(nameof(vaos))).ToList().AsReadOnly();
            Topology = (topology ?? throw new ArgumentNullException(nameof(topology))).ToList().AsReadOnly();
            var allDiagnostics = (diagnostics ?? throw new ArgumentNullException(nameof(diagnostics))).ToList();
            _graph = graph ?? new TwinTopologyGraph(Postes, Vaos, Topology);
            if (graph == null)
            {
                allDiagnostics.AddRange(_graph.Diagnostics);
            }

            Diagnostics = allDiagnostics
                .OrderBy(diagnostic => diagnostic.Code, StringComparer.OrdinalIgnoreCase)
                .ThenBy(diagnostic => diagnostic.EntityType, StringComparer.OrdinalIgnoreCase)
                .ThenBy(diagnostic => diagnostic.EntityId, StringComparer.OrdinalIgnoreCase)
                .ThenBy(diagnostic => diagnostic.EntityId, StringComparer.Ordinal)
                .ThenBy(diagnostic => diagnostic.Handle, StringComparer.OrdinalIgnoreCase)
                .ThenBy(diagnostic => diagnostic.Handle, StringComparer.Ordinal)
                .ThenBy(diagnostic => diagnostic.Message, StringComparer.OrdinalIgnoreCase)
                .ThenBy(diagnostic => diagnostic.Message, StringComparer.Ordinal)
                .ThenBy(diagnostic => diagnostic.Severity, StringComparer.OrdinalIgnoreCase)
                .ToList()
                .AsReadOnly();
        }

        public int ModelVersion { get; }
        public string ConstructionSource { get; }
        public IReadOnlyList<PosteTwin> Postes { get; }
        public IReadOnlyList<VaoTwin> Vaos { get; }
        public IReadOnlyList<TwinTopologyRelation> Topology { get; }
        public IReadOnlyList<TwinDiagnostic> Diagnostics { get; }

        public PosteTwin? GetPoste(string domainId) => _graph.GetPoste(domainId);
        public VaoTwin? GetVao(string vaoId) => _graph.GetVao(vaoId);
        public IReadOnlyList<string> GetVaoIdsIncidentToPoste(string domainId) =>
            _graph.GetVaoIdsIncidentToPoste(domainId);
        public IReadOnlyList<string> GetConnectedPosteIds(string domainId) =>
            _graph.GetConnectedPosteIds(domainId);
        public IReadOnlyList<PosteTwin> GetIsolatedPostes() => _graph.GetIsolatedPostes();
        public IReadOnlyList<VaoTwin> GetOrphanVaos() => _graph.GetOrphanVaos();
        public IReadOnlyList<TwinConnectedComponent> GetConnectedComponents() =>
            _graph.GetConnectedComponents();
    }

    public static class DigitalTwinBuilder
    {
        public const int ModelVersion = 1;
        public const string ConstructionSource = "DWG_SCAN";

        public static DigitalTwin Build(EscanearDwgResultado state)
        {
            if (state == null) throw new ArgumentNullException(nameof(state));

            var diagnostics = state.Diagnostics
                .Select(ToDiagnostic)
                .ToList();
            var postes = state.Postes
                .Select(poste => new PosteTwin(
                    poste.Id,
                    poste.Handle,
                    poste.Numero,
                    poste.X,
                    poste.Y,
                    null,
                    poste.OperationId,
                    poste.TipoPoste,
                    poste.TemTrafo,
                    poste.PotenciaTrafo,
                    poste.IsLegacy,
                    new TwinDataSource("DWG_SCAN", TwinDataStatus.Disponivel)))
                .OrderBy(poste => poste.DomainId, StringComparer.OrdinalIgnoreCase)
                .ThenBy(poste => poste.DomainId, StringComparer.Ordinal)
                .ThenBy(poste => poste.Handle, StringComparer.OrdinalIgnoreCase)
                .ThenBy(poste => poste.Handle, StringComparer.Ordinal)
                .ThenBy(poste => poste.Numero, StringComparer.OrdinalIgnoreCase)
                .ThenBy(poste => poste.Numero, StringComparer.Ordinal)
                .ToList();
            var vaos = state.Vaos
                .Select(vao => new VaoTwin(
                    vao.Id,
                    vao.Handle,
                    vao.PosteOrigemId,
                    vao.PosteDestinoId,
                    vao.X1,
                    vao.Y1,
                    vao.X2,
                    vao.Y2,
                    vao.ExtensaoMetros,
                    vao.OperationId,
                    vao.TipoRede,
                    vao.TextoVao,
                    vao.IsLegacy,
                    vao.IsOrphan,
                    new TwinDataSource("DWG_SCAN", TwinDataStatus.Disponivel)))
                .OrderBy(vao => vao.VaoId, StringComparer.OrdinalIgnoreCase)
                .ThenBy(vao => vao.VaoId, StringComparer.Ordinal)
                .ThenBy(vao => vao.Handle, StringComparer.OrdinalIgnoreCase)
                .ThenBy(vao => vao.Handle, StringComparer.Ordinal)
                .ToList();
            var topology = state.Relacoes
                .Select(relation => new TwinTopologyRelation(
                    relation.VaoId,
                    relation.PosteOrigemId,
                    relation.PosteDestinoId,
                    relation.Method,
                    relation.Confidence))
                .OrderBy(relation => relation.VaoId, StringComparer.OrdinalIgnoreCase)
                .ThenBy(relation => relation.VaoId, StringComparer.Ordinal)
                .ThenBy(relation => relation.PosteOrigemId, StringComparer.OrdinalIgnoreCase)
                .ThenBy(relation => relation.PosteOrigemId, StringComparer.Ordinal)
                .ThenBy(relation => relation.PosteDestinoId, StringComparer.OrdinalIgnoreCase)
                .ThenBy(relation => relation.PosteDestinoId, StringComparer.Ordinal)
                .ThenBy(relation => relation.Method, StringComparer.OrdinalIgnoreCase)
                .ThenBy(relation => relation.Method, StringComparer.Ordinal)
                .ThenBy(relation => relation.Confidence, StringComparer.OrdinalIgnoreCase)
                .ThenBy(relation => relation.Confidence, StringComparer.Ordinal)
                .ToList();

            AddIdentityDiagnostics(postes, vaos, diagnostics);
            var graph = new TwinTopologyGraph(postes, vaos, topology);
            diagnostics.AddRange(graph.Diagnostics);
            var orderedDiagnostics = diagnostics
                .OrderBy(diagnostic => diagnostic.Code, StringComparer.OrdinalIgnoreCase)
                .ThenBy(diagnostic => diagnostic.EntityType, StringComparer.OrdinalIgnoreCase)
                .ThenBy(diagnostic => diagnostic.EntityId, StringComparer.OrdinalIgnoreCase)
                .ThenBy(diagnostic => diagnostic.EntityId, StringComparer.Ordinal)
                .ThenBy(diagnostic => diagnostic.Handle, StringComparer.OrdinalIgnoreCase)
                .ThenBy(diagnostic => diagnostic.Handle, StringComparer.Ordinal)
                .ThenBy(diagnostic => diagnostic.Message, StringComparer.OrdinalIgnoreCase)
                .ThenBy(diagnostic => diagnostic.Message, StringComparer.Ordinal)
                .ThenBy(diagnostic => diagnostic.Severity, StringComparer.OrdinalIgnoreCase)
                .ToList();

            return new DigitalTwin(
                ModelVersion,
                ConstructionSource,
                postes,
                vaos,
                topology,
                orderedDiagnostics,
                graph);
        }

        private static TwinDiagnostic ToDiagnostic(DwgDiagnostic diagnostic) =>
            new TwinDiagnostic(
                diagnostic.Code,
                diagnostic.Severity,
                diagnostic.EntityType,
                diagnostic.EntityId,
                diagnostic.Handle,
                diagnostic.Message);

        private static void AddIdentityDiagnostics(
            IEnumerable<PosteTwin> postes,
            IEnumerable<VaoTwin> vaos,
            ICollection<TwinDiagnostic> diagnostics)
        {
            foreach (var group in postes.Where(poste => string.IsNullOrWhiteSpace(poste.DomainId))
                                         .GroupBy(poste => poste.Handle))
            {
                diagnostics.Add(new TwinDiagnostic(
                    "TWIN_MISSING_POSTE_ID",
                    "WARNING",
                    "POSTE",
                    string.Empty,
                    group.Key,
                    "Poste sem DomainId persistente; nenhuma identidade foi gerada."));
            }

            foreach (var group in vaos.Where(vao => string.IsNullOrWhiteSpace(vao.VaoId))
                                      .GroupBy(vao => vao.Handle))
            {
                diagnostics.Add(new TwinDiagnostic(
                    "TWIN_MISSING_VAO_ID",
                    "WARNING",
                    "VAO",
                    string.Empty,
                    group.Key,
                    "Vão sem VaoId persistente; nenhuma identidade foi gerada."));
            }

            AddDuplicateDiagnostics(postes.Where(poste => !string.IsNullOrWhiteSpace(poste.DomainId))
                                           .Select(poste => new IdentityHandle(poste.DomainId, poste.Handle)),
                "TWIN_DUPLICATE_POSTE_ID", "POSTE", diagnostics);
            AddDuplicateDiagnostics(vaos.Where(vao => !string.IsNullOrWhiteSpace(vao.VaoId))
                                        .Select(vao => new IdentityHandle(vao.VaoId, vao.Handle)),
                "TWIN_DUPLICATE_VAO_ID", "VAO", diagnostics);
        }

        private static void AddDuplicateDiagnostics(
            IEnumerable<IdentityHandle> entities,
            string code,
            string entityType,
            ICollection<TwinDiagnostic> diagnostics)
        {
            foreach (var group in entities.GroupBy(entity => entity.Id, StringComparer.OrdinalIgnoreCase)
                                           .Where(group => group.Count() > 1))
            {
                diagnostics.Add(new TwinDiagnostic(
                    code,
                    "ERROR",
                    entityType,
                    group.Select(entity => entity.Id)
                        .OrderBy(id => id, StringComparer.Ordinal)
                        .First(),
                    string.Join(",", group.Select(entity => entity.Handle)
                        .OrderBy(handle => handle, StringComparer.OrdinalIgnoreCase)
                        .ThenBy(handle => handle, StringComparer.Ordinal)),
                    "Identidade lógica duplicada no estado persistido."));
            }
        }

        private sealed class IdentityHandle
        {
            public IdentityHandle(string id, string handle)
            {
                Id = id;
                Handle = handle;
            }

            public string Id { get; }
            public string Handle { get; }
        }

    }

    internal sealed class TwinTopologyGraph
    {
        private static readonly StringComparer IdComparer = StringComparer.OrdinalIgnoreCase;

        private readonly IReadOnlyDictionary<string, PosteTwin> _postesById;
        private readonly IReadOnlyDictionary<string, VaoTwin> _vaosById;
        private readonly IReadOnlyDictionary<string, IReadOnlyList<string>> _vaosByPoste;
        private readonly IReadOnlyDictionary<string, IReadOnlyList<string>> _postesByPoste;
        private readonly IReadOnlyList<TwinDiagnostic> _diagnostics;

        public TwinTopologyGraph(
            IEnumerable<PosteTwin> postes,
            IEnumerable<VaoTwin> vaos,
            IEnumerable<TwinTopologyRelation> topology)
        {
            var posteGroups = postes
                .Where(poste => !string.IsNullOrWhiteSpace(poste.DomainId))
                .GroupBy(poste => poste.DomainId, IdComparer)
                .ToDictionary(group => group.Key, group => group.ToList(), IdComparer);
            var vaoGroups = vaos
                .Where(vao => !string.IsNullOrWhiteSpace(vao.VaoId))
                .GroupBy(vao => vao.VaoId, IdComparer)
                .ToDictionary(group => group.Key, group => group.ToList(), IdComparer);
            _postesById = posteGroups
                .Where(group => group.Value.Count == 1)
                .ToDictionary(group => group.Key, group => group.Value[0], IdComparer);
            _vaosById = vaoGroups
                .Where(group => group.Value.Count == 1)
                .ToDictionary(group => group.Key, group => group.Value[0], IdComparer);

            var diagnostics = new List<TwinDiagnostic>();
            var incidentVaos = _postesById.Keys.ToDictionary(
                id => id,
                _ => new SortedSet<string>(IdComparer),
                IdComparer);
            var connectedPostes = _postesById.Keys.ToDictionary(
                id => id,
                _ => new SortedSet<string>(IdComparer),
                IdComparer);
            foreach (var vao in vaos.OrderBy(vao => vao.VaoId, IdComparer)
                                    .ThenBy(vao => vao.VaoId, StringComparer.Ordinal))
            {
                if (vao.IsOrphan ||
                    !ContainsUniquePoste(vao.PosteOrigemId) ||
                    !ContainsUniquePoste(vao.PosteDestinoId))
                {
                    diagnostics.Add(new TwinDiagnostic(
                        "TWIN_ORPHAN_VAO",
                        "WARNING",
                        "VAO",
                        vao.VaoId,
                        vao.Handle,
                        "Vão referencia poste de origem ou destino ausente."));
                }
            }

            var relationsByVao = topology
                .GroupBy(relation => relation.VaoId ?? string.Empty, IdComparer)
                .OrderBy(group => group.Key, IdComparer)
                .ThenBy(group => group.Key, StringComparer.Ordinal)
                .ToList();

            foreach (var group in relationsByVao)
            {
                var relations = group
                    .OrderBy(relation => relation.PosteOrigemId, IdComparer)
                    .ThenBy(relation => relation.PosteDestinoId, IdComparer)
                    .ThenBy(relation => relation.Method, IdComparer)
                    .ThenBy(relation => relation.Confidence, IdComparer)
                    .ToList();

                if (string.IsNullOrWhiteSpace(group.Key) || !_vaosById.TryGetValue(group.Key, out var vao))
                {
                    diagnostics.Add(InvalidRelation(group.Key, "Relação sem vão único correspondente."));
                    continue;
                }

                var distinctRelations = relations
                    .Select(relation => new RelationEndpoints(relation.PosteOrigemId, relation.PosteDestinoId))
                    .Distinct()
                    .ToList();
                if (distinctRelations.Count > 1)
                {
                    diagnostics.Add(InvalidRelation(group.Key, "O mesmo VaoId possui relações com endpoints divergentes."));
                    continue;
                }

                if (relations.Count > 1)
                {
                    diagnostics.Add(new TwinDiagnostic(
                        "TWIN_DUPLICATE_RELATION",
                        "WARNING",
                        "VAO",
                        group.Key,
                        vao.Handle,
                        "Relação topológica duplicada; uma única relação foi considerada no grafo."));
                }

                var relation = relations[0];
                if (string.IsNullOrWhiteSpace(relation.PosteOrigemId) ||
                    string.IsNullOrWhiteSpace(relation.PosteDestinoId))
                {
                    diagnostics.Add(InvalidRelation(group.Key, "Relação possui endpoint vazio."));
                    continue;
                }

                if (!IdComparer.Equals(vao.PosteOrigemId, relation.PosteOrigemId) ||
                    !IdComparer.Equals(vao.PosteDestinoId, relation.PosteDestinoId))
                {
                    diagnostics.Add(InvalidRelation(group.Key, "Endpoints da relação divergem dos dados do vão."));
                    continue;
                }

                var origemExiste = ContainsUniquePoste(relation.PosteOrigemId);
                var destinoExiste = ContainsUniquePoste(relation.PosteDestinoId);
                if (!origemExiste || !destinoExiste)
                {
                    if (!origemExiste)
                    {
                        diagnostics.Add(OrphanReference(relation, "origem"));
                    }

                    if (!destinoExiste)
                    {
                        diagnostics.Add(OrphanReference(relation, "destino"));
                    }

                    continue;
                }

                if (vao.IsOrphan)
                {
                    continue;
                }

                if (IdComparer.Equals(relation.PosteOrigemId, relation.PosteDestinoId))
                {
                    diagnostics.Add(new TwinDiagnostic(
                        "TWIN_SELF_LOOP",
                        "WARNING",
                        "VAO",
                        relation.VaoId,
                        vao.Handle,
                        "Vão conecta um poste a si mesmo e não foi incluído no grafo."));
                    continue;
                }

                incidentVaos[relation.PosteOrigemId].Add(relation.VaoId);
                incidentVaos[relation.PosteDestinoId].Add(relation.VaoId);
                connectedPostes[relation.PosteOrigemId].Add(relation.PosteDestinoId);
                connectedPostes[relation.PosteDestinoId].Add(relation.PosteOrigemId);
            }

            var relatedVaoIds = new HashSet<string>(
                relationsByVao.Select(group => group.Key),
                IdComparer);
            foreach (var vao in _vaosById.Values
                         .Where(vao => !vao.IsOrphan && !relatedVaoIds.Contains(vao.VaoId))
                         .OrderBy(vao => vao.VaoId, IdComparer)
                         .ThenBy(vao => vao.VaoId, StringComparer.Ordinal))
            {
                diagnostics.Add(InvalidRelation(vao.VaoId, "Vão sem relação topológica explícita no estado do scanner."));
            }

            foreach (var poste in _postesById.Values.OrderBy(poste => poste.DomainId, IdComparer))
            {
                if (incidentVaos[poste.DomainId].Count == 0)
                {
                    diagnostics.Add(new TwinDiagnostic(
                        "TWIN_ISOLATED_POSTE",
                        "INFO",
                        "POSTE",
                        poste.DomainId,
                        poste.Handle,
                        "Poste sem relações topológicas válidas incidentes."));
                }
            }

            _vaosByPoste = incidentVaos.ToDictionary(
                pair => pair.Key,
                pair => (IReadOnlyList<string>)pair.Value.ToList().AsReadOnly(),
                IdComparer);
            _postesByPoste = connectedPostes.ToDictionary(
                pair => pair.Key,
                pair => (IReadOnlyList<string>)pair.Value.ToList().AsReadOnly(),
                IdComparer);
            _diagnostics = diagnostics
                .OrderBy(diagnostic => diagnostic.Code, IdComparer)
                .ThenBy(diagnostic => diagnostic.EntityId, IdComparer)
                .ThenBy(diagnostic => diagnostic.Handle, IdComparer)
                .ThenBy(diagnostic => diagnostic.Message, IdComparer)
                .ThenBy(diagnostic => diagnostic.Message, StringComparer.Ordinal)
                .ToList()
                .AsReadOnly();
        }

        public IReadOnlyList<TwinDiagnostic> Diagnostics => _diagnostics;

        public PosteTwin? GetPoste(string domainId) =>
            !string.IsNullOrWhiteSpace(domainId) && _postesById.TryGetValue(domainId, out var poste)
                ? poste
                : null;

        public VaoTwin? GetVao(string vaoId) =>
            !string.IsNullOrWhiteSpace(vaoId) && _vaosById.TryGetValue(vaoId, out var vao)
                ? vao
                : null;

        public IReadOnlyList<string> GetVaoIdsIncidentToPoste(string domainId) =>
            !string.IsNullOrWhiteSpace(domainId) && _vaosByPoste.TryGetValue(domainId, out var ids)
                ? ids
                : Array.Empty<string>();

        public IReadOnlyList<string> GetConnectedPosteIds(string domainId) =>
            !string.IsNullOrWhiteSpace(domainId) && _postesByPoste.TryGetValue(domainId, out var ids)
                ? ids
                : Array.Empty<string>();

        public IReadOnlyList<PosteTwin> GetIsolatedPostes() =>
            _postesById.Values
                .Where(poste => _vaosByPoste[poste.DomainId].Count == 0)
                .OrderBy(poste => poste.DomainId, IdComparer)
                .ToList()
                .AsReadOnly();

        public IReadOnlyList<VaoTwin> GetOrphanVaos() =>
            _vaosById.Values
                .Where(vao => vao.IsOrphan ||
                              !ContainsUniquePoste(vao.PosteOrigemId) ||
                              !ContainsUniquePoste(vao.PosteDestinoId))
                .OrderBy(vao => vao.VaoId, IdComparer)
                .ToList()
                .AsReadOnly();

        public IReadOnlyList<TwinConnectedComponent> GetConnectedComponents()
        {
            var unvisited = new SortedSet<string>(_postesById.Keys, IdComparer);
            var components = new List<TwinConnectedComponent>();
            while (unvisited.Count > 0)
            {
                var first = unvisited.Min!;
                var queue = new Queue<string>();
                var componentPostes = new SortedSet<string>(IdComparer);
                var componentVaos = new SortedSet<string>(IdComparer);
                unvisited.Remove(first);
                queue.Enqueue(first);

                while (queue.Count > 0)
                {
                    var current = queue.Dequeue();
                    componentPostes.Add(current);
                    foreach (var vaoId in _vaosByPoste[current])
                    {
                        componentVaos.Add(vaoId);
                    }

                    foreach (var connectedId in _postesByPoste[current])
                    {
                        if (unvisited.Remove(connectedId))
                        {
                            queue.Enqueue(connectedId);
                        }
                    }
                }

                components.Add(new TwinConnectedComponent(componentPostes, componentVaos));
            }

            return components
                .OrderBy(component => component.PosteIds[0], IdComparer)
                .ToList()
                .AsReadOnly();
        }

        private bool ContainsUniquePoste(string id) =>
            !string.IsNullOrWhiteSpace(id) && _postesById.ContainsKey(id);

        private static TwinDiagnostic InvalidRelation(string vaoId, string message) =>
            new TwinDiagnostic(
                "TWIN_INVALID_TOPOLOGY",
                "ERROR",
                "VAO",
                vaoId,
                string.Empty,
                message);

        private static TwinDiagnostic OrphanReference(TwinTopologyRelation relation, string endpoint) =>
            new TwinDiagnostic(
                "TWIN_ORPHAN_POSTE_REFERENCE",
                "WARNING",
                "VAO",
                relation.VaoId,
                string.Empty,
                $"Relação topológica referencia poste de {endpoint} ausente.");

        private sealed class RelationEndpoints : IEquatable<RelationEndpoints>
        {
            public RelationEndpoints(string originId, string destinationId)
            {
                OriginId = originId ?? string.Empty;
                DestinationId = destinationId ?? string.Empty;
            }

            private string OriginId { get; }
            private string DestinationId { get; }

            public bool Equals(RelationEndpoints? other) =>
                other != null &&
                IdComparer.Equals(OriginId, other.OriginId) &&
                IdComparer.Equals(DestinationId, other.DestinationId);

            public override bool Equals(object? obj) => Equals(obj as RelationEndpoints);

            public override int GetHashCode() =>
                unchecked((IdComparer.GetHashCode(OriginId) * 397) ^ IdComparer.GetHashCode(DestinationId));
        }
    }
}
