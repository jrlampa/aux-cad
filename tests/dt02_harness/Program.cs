using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using MapaCadPaleta;

internal static class Program
{
    private static int _passed;

    private static int Main()
    {
        Run("empty twin", EmptyTwin);
        Run("isolated poste", IsolatedPoste);
        Run("two postes and one vao", TwoPostesOneVao);
        Run("three-poste chain", ThreePosteChain);
        Run("two incident vaos", PosteWithTwoVaos);
        Run("orphan vao", OrphanVao);
        Run("missing origin", MissingOrigin);
        Run("missing destination", MissingDestination);
        Run("self-loop", SelfLoop);
        Run("duplicate relation", DuplicateRelation);
        Run("independent components", IndependentComponents);
        Run("logical identity preserved", LogicalIdentityPreserved);
        Run("numero does not identify poste", NumeroDoesNotIdentifyPoste);
        Run("handle is not logical identity", HandleIsNotIdentity);
        Run("builder does not generate IDs", BuilderDoesNotGenerateIds);
        Run("builder does not mutate scanner result", BuilderDoesNotMutateInput);
        Run("input order does not change graph", InputOrderDoesNotChangeGraph);
        Run("scanner diagnostics reach twin", ScannerDiagnosticsReachTwin);
        Run("proximity does not create connectivity", ProximityDoesNotConnect);
        Run("components are deterministic", ComponentsAreDeterministic);
        Run("divergent relation is rejected", DivergentRelationIsRejected);
        Run("duplicate poste identity is diagnosed", DuplicatePosteIdentity);
        Run("missing explicit relation is diagnosed", MissingExplicitRelation);
        Run("direct twin exposes graph diagnostics", DirectTwinExposesGraphDiagnostics);
        Run("OSM building polygon remains closed", OsmBuildingRemainsClosed);
        Run("OSM three-point barrier remains open", OsmThreePointBarrierRemainsOpen);
        Run("OSM two-point barrier remains open", OsmTwoPointBarrierRemainsOpen);
        Run("OSM empty geometry is rejected", OsmEmptyGeometryIsRejected);
        Run("OSM invalid coordinates are rejected", OsmInvalidCoordinatesAreRejected);
        Run("OSM unknown geometry retains legacy closure", OsmUnknownGeometryRetainsFallback);
        Run("project scope identity is normalized", ProjectScopeIdentityIsNormalized);
        Run("project scope rejects invalid IDs", ProjectScopeRejectsInvalidIds);
        Run("project scope write normalizes before comparison", ProjectScopeWriteNormalizesBeforeComparison);
        Run("project scope write rejects conflicting binding", ProjectScopeWriteRejectsConflictingBinding);
        Run("project scope write rejects invalid ID", ProjectScopeWriteRejectsInvalidId);
        Run("project scope write rejects invalid existing metadata", ProjectScopeWriteRejectsInvalidExistingMetadata);
        Run("project scope distinguishes missing metadata", ProjectScopeDistinguishesMissingMetadata);
        Run("project scope detects conflicting identities", ProjectScopeDetectsConflicts);
        Run("project scope rejects unsupported metadata", ProjectScopeRejectsUnsupportedMetadata);
        Run("project scope validates matching payload", ProjectScopeValidatesMatchingPayload);
        Run("project scope rejects mismatched payload", ProjectScopeRejectsMismatchedPayload);
        Run("project scope rejects stale generation", ProjectScopeRejectsStaleGeneration);
        Run("project scope rejects invalid generation", ProjectScopeRejectsInvalidGeneration);
        Run("project scope rejects unbound payload", ProjectScopeRejectsUnboundPayload);

        Console.WriteLine($"DT-02: {_passed} tests passed.");
        return 0;
    }

    private static void Run(string name, Action test)
    {
        try
        {
            test();
            _passed++;
            Console.WriteLine($"PASS {name}");
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine($"FAIL {name}: {exception.Message}");
            Environment.Exit(1);
        }
    }

    private static void EmptyTwin()
    {
        var twin = DigitalTwinBuilder.Build(new EscanearDwgResultado());
        Equal(0, twin.Postes.Count);
        Equal(0, twin.Vaos.Count);
        Equal(0, twin.GetConnectedComponents().Count);
    }

    private static void IsolatedPoste()
    {
        var twin = Build(Poste("P1"));
        Equal(1, twin.GetIsolatedPostes().Count);
        Equal("P1", twin.GetConnectedComponents()[0].PosteIds[0]);
        HasDiagnostic(twin, "TWIN_ISOLATED_POSTE");
    }

    private static void TwoPostesOneVao()
    {
        var twin = Build(new[] { Poste("P1"), Poste("P2") }, new[] { Vao("V1", "P1", "P2") });
        Equal(1, twin.GetConnectedComponents().Count);
        Sequence(new[] { "V1" }, twin.GetVaoIdsIncidentToPoste("P1"));
        Sequence(new[] { "P2" }, twin.GetConnectedPosteIds("P1"));
    }

    private static void ThreePosteChain()
    {
        var twin = Build(
            new[] { Poste("P1"), Poste("P2"), Poste("P3") },
            new[] { Vao("V1", "P1", "P2"), Vao("V2", "P2", "P3") });
        Equal(1, twin.GetConnectedComponents().Count);
        Sequence(new[] { "P1", "P2", "P3" }, twin.GetConnectedComponents()[0].PosteIds);
        Sequence(new[] { "V1", "V2" }, twin.GetConnectedComponents()[0].VaoIds);
    }

    private static void PosteWithTwoVaos()
    {
        var twin = Build(
            new[] { Poste("P1"), Poste("P2"), Poste("P3") },
            new[] { Vao("V1", "P1", "P2"), Vao("V2", "P1", "P3") });
        Sequence(new[] { "V1", "V2" }, twin.GetVaoIdsIncidentToPoste("P1"));
        Sequence(new[] { "P2", "P3" }, twin.GetConnectedPosteIds("P1"));
    }

    private static void OrphanVao()
    {
        var vao = Vao("V1", "P1", "P2");
        vao.IsOrphan = true;
        var twin = Build(new[] { Poste("P1"), Poste("P2") }, new[] { vao });
        Equal(1, twin.GetOrphanVaos().Count);
        HasDiagnostic(twin, "TWIN_ORPHAN_VAO");
        Equal(0, twin.GetVaoIdsIncidentToPoste("P1").Count);
        Equal(0, twin.GetConnectedPosteIds("P1").Count);
        Equal(2, twin.GetConnectedComponents().Count);
    }

    private static void MissingOrigin()
    {
        var twin = Build(new[] { Poste("P2") }, new[] { Vao("V1", "MISSING", "P2") });
        HasDiagnostic(twin, "TWIN_ORPHAN_POSTE_REFERENCE");
        Equal(0, twin.GetConnectedComponents().Single().VaoIds.Count);
    }

    private static void MissingDestination()
    {
        var twin = Build(new[] { Poste("P1") }, new[] { Vao("V1", "P1", "MISSING") });
        HasDiagnostic(twin, "TWIN_ORPHAN_POSTE_REFERENCE");
        Equal(0, twin.GetVaoIdsIncidentToPoste("P1").Count);
    }

    private static void SelfLoop()
    {
        var twin = Build(new[] { Poste("P1") }, new[] { Vao("V1", "P1", "P1") });
        HasDiagnostic(twin, "TWIN_SELF_LOOP");
        Equal(0, twin.GetVaoIdsIncidentToPoste("P1").Count);
    }

    private static void DuplicateRelation()
    {
        var state = State(new[] { Poste("P1"), Poste("P2") }, new[] { Vao("V1", "P1", "P2") });
        state.Relacoes.Add(Relation("V1", "P1", "P2"));
        var twin = DigitalTwinBuilder.Build(state);
        HasDiagnostic(twin, "TWIN_DUPLICATE_RELATION");
        Equal(1, twin.GetVaoIdsIncidentToPoste("P1").Count);
    }

    private static void IndependentComponents()
    {
        var twin = Build(
            new[] { Poste("P1"), Poste("P2"), Poste("P3"), Poste("P4") },
            new[] { Vao("V1", "P1", "P2"), Vao("V2", "P3", "P4") });
        Equal(2, twin.GetConnectedComponents().Count);
    }

    private static void LogicalIdentityPreserved()
    {
        var twin = Build(Poste("domain-a", "different-handle"));
        Equal("domain-a", twin.GetPoste("domain-a")!.DomainId);
        Equal("different-handle", twin.GetPoste("domain-a")!.Handle);
    }

    private static void NumeroDoesNotIdentifyPoste()
    {
        var first = Poste("domain-a");
        first.Numero = "001";
        var second = Poste("domain-a");
        second.Numero = "900";
        Equal(
            DigitalTwinBuilder.Build(State(new[] { first }, Array.Empty<VaoDto>())).GetPoste("domain-a")!.DomainId,
            DigitalTwinBuilder.Build(State(new[] { second }, Array.Empty<VaoDto>())).GetPoste("domain-a")!.DomainId);
    }

    private static void HandleIsNotIdentity()
    {
        var twin = Build(Poste("domain-a", "ABC"), Poste("domain-b", "ABC"));
        Equal("domain-a", twin.GetPoste("domain-a")!.DomainId);
        Equal("domain-b", twin.GetPoste("domain-b")!.DomainId);
    }

    private static void BuilderDoesNotGenerateIds()
    {
        var state = State(new[] { Poste(string.Empty) }, Array.Empty<VaoDto>());
        var twin = DigitalTwinBuilder.Build(state);
        Equal(string.Empty, twin.Postes[0].DomainId);
        HasDiagnostic(twin, "TWIN_MISSING_POSTE_ID");
    }

    private static void BuilderDoesNotMutateInput()
    {
        var state = State(new[] { Poste("P1"), Poste("P2") }, new[] { Vao("V1", "P1", "P2") });
        var before = $"{state.Postes.Count}|{state.Vaos.Count}|{state.Relacoes.Count}|{state.Postes[0].Id}";
        _ = DigitalTwinBuilder.Build(state);
        Equal(before, $"{state.Postes.Count}|{state.Vaos.Count}|{state.Relacoes.Count}|{state.Postes[0].Id}");
    }

    private static void InputOrderDoesNotChangeGraph()
    {
        var postes = new[] { Poste("P1"), Poste("P2"), Poste("P3") };
        var vaos = new[] { Vao("V1", "P1", "P2"), Vao("V2", "P2", "P3") };
        var first = Build(postes, vaos);
        var second = Build(postes.Reverse().ToArray(), vaos.Reverse().ToArray());
        Equal(ComponentSignature(first), ComponentSignature(second));
    }

    private static void ScannerDiagnosticsReachTwin()
    {
        var state = State(Array.Empty<PosteDto>(), Array.Empty<VaoDto>());
        state.Diagnostics.Add(new DwgDiagnostic { Code = "SCAN_WARNING", Severity = "WARNING", Message = "source diagnostic" });
        HasDiagnostic(DigitalTwinBuilder.Build(state), "SCAN_WARNING");
    }

    private static void ProximityDoesNotConnect()
    {
        var first = Poste("P1");
        var second = Poste("P2");
        second.X = first.X + 0.001;
        second.Y = first.Y + 0.001;
        var twin = Build(new[] { first, second }, Array.Empty<VaoDto>());
        Equal(2, twin.GetConnectedComponents().Count);
        Equal(0, twin.GetConnectedPosteIds("P1").Count);
    }

    private static void ComponentsAreDeterministic()
    {
        var twin = Build(
            new[] { Poste("P4"), Poste("P2"), Poste("P3"), Poste("P1") },
            new[] { Vao("V2", "P3", "P4"), Vao("V1", "P1", "P2") });
        Sequence(new[] { "P1", "P3" }, twin.GetConnectedComponents().Select(component => component.PosteIds[0]));
    }

    private static void DivergentRelationIsRejected()
    {
        var state = State(
            new[] { Poste("P1"), Poste("P2"), Poste("P3") },
            new[] { Vao("V1", "P1", "P2") });
        state.Relacoes.Add(Relation("V1", "P1", "P3"));
        var twin = DigitalTwinBuilder.Build(state);
        HasDiagnostic(twin, "TWIN_INVALID_TOPOLOGY");
        Equal(0, twin.GetVaoIdsIncidentToPoste("P1").Count);
    }

    private static void DuplicatePosteIdentity()
    {
        var twin = Build(Poste("P1", "H1"), Poste("P1", "H2"));
        HasDiagnostic(twin, "TWIN_DUPLICATE_POSTE_ID");
        Equal(0, twin.GetConnectedComponents().Count);
    }

    private static void MissingExplicitRelation()
    {
        var state = State(new[] { Poste("P1"), Poste("P2") }, new[] { Vao("V1", "P1", "P2") });
        state.Relacoes.Clear();
        var twin = DigitalTwinBuilder.Build(state);
        HasDiagnostic(twin, "TWIN_INVALID_TOPOLOGY");
        Equal(2, twin.GetConnectedComponents().Count);
    }

    private static void DirectTwinExposesGraphDiagnostics()
    {
        var twin = new DigitalTwin(
            1,
            "DWG_SCAN",
            new[]
            {
                new PosteTwin(
                    "P1",
                    "HANDLE-P1",
                    "1",
                    0,
                    0,
                    null,
                    string.Empty,
                    string.Empty,
                    false,
                    string.Empty,
                    false,
                    new TwinDataSource("DWG_SCAN", TwinDataStatus.Disponivel))
            },
            Array.Empty<VaoTwin>(),
            Array.Empty<TwinTopologyRelation>(),
            Array.Empty<TwinDiagnostic>());
        HasDiagnostic(twin, "TWIN_ISOLATED_POSTE");
    }

    private static void OsmBuildingRemainsClosed() =>
        Equal(true, OsmGeometryPolicy.ShouldClose("EDIFICACAO", false));

    private static void OsmThreePointBarrierRemainsOpen()
    {
        using var document = JsonDocument.Parse("[[1,2],[3,4],[5,6]]");
        Equal(true, OsmGeometryPolicy.TryReadCoordinates(document.RootElement, out var coordinates));
        Equal(3, coordinates.Count);
        Equal(false, OsmGeometryPolicy.ShouldClose("BARREIRA", true));
    }

    private static void OsmTwoPointBarrierRemainsOpen()
    {
        using var document = JsonDocument.Parse("[[1,2],[3,4]]");
        Equal(true, OsmGeometryPolicy.TryReadCoordinates(document.RootElement, out var coordinates));
        Equal(2, coordinates.Count);
        Equal(false, OsmGeometryPolicy.ShouldClose("BARREIRA", true));
    }

    private static void OsmEmptyGeometryIsRejected()
    {
        using var document = JsonDocument.Parse("[]");
        Equal(false, OsmGeometryPolicy.TryReadCoordinates(document.RootElement, out var coordinates));
        Equal(0, coordinates.Count);
    }

    private static void OsmInvalidCoordinatesAreRejected()
    {
        using var document = JsonDocument.Parse("[[1,2],[3,\"invalid\"]]");
        Equal(false, OsmGeometryPolicy.TryReadCoordinates(document.RootElement, out var coordinates));
        Equal(0, coordinates.Count);
    }

    private static void OsmUnknownGeometryRetainsFallback()
    {
        Equal(true, OsmGeometryPolicy.ShouldClose("TIPO_DESCONHECIDO", true));
        Equal(false, OsmGeometryPolicy.ShouldClose("TIPO_DESCONHECIDO", false));
    }

    private static void ProjectScopeIdentityIsNormalized()
    {
        ProjectScope scope = ProjectScopeContract.Resolve(
            ProjectScopeContract.MetadataVersion,
            ProjectScopeContract.Encode(" ab_123 "));
        Equal(ProjectScopeStatus.Bound, scope.Status);
        Equal("AB_123", scope.SobId);
    }

    private static void ProjectScopeRejectsInvalidIds()
    {
        ProjectScope scope = ProjectScopeContract.Resolve(
            ProjectScopeContract.MetadataVersion,
            new[] { new KeyValuePair<string, string>(ProjectScopeContract.SobIdField, "SOB_123") });
        Equal(ProjectScopeStatus.Invalid, scope.Status);
        Equal(null, scope.SobId);
    }

    private static void ProjectScopeWriteNormalizesBeforeComparison()
    {
        ProjectScope existing = ProjectScopeContract.Resolve(
            ProjectScopeContract.MetadataVersion,
            ProjectScopeContract.Encode("ABC"));
        Equal("ABC", ProjectScopeContract.ValidateWrite(existing, " abc "));
    }

    private static void ProjectScopeWriteRejectsConflictingBinding()
    {
        ProjectScope existing = ProjectScopeContract.Resolve(
            ProjectScopeContract.MetadataVersion,
            ProjectScopeContract.Encode("ABC"));
        Throws<InvalidOperationException>(() => ProjectScopeContract.ValidateWrite(existing, "XYZ"));
    }

    private static void ProjectScopeWriteRejectsInvalidId()
    {
        Throws<ArgumentException>(() => ProjectScopeContract.ValidateWrite(ProjectScopeContract.Unbound(), null));
    }

    private static void ProjectScopeWriteRejectsInvalidExistingMetadata()
    {
        Throws<InvalidOperationException>(() =>
            ProjectScopeContract.ValidateWrite(ProjectScopeContract.Invalid("BROKEN"), "ABC"));
        Throws<InvalidOperationException>(() =>
            ProjectScopeContract.ValidateWrite(
                ProjectScopeContract.Resolve(
                    ProjectScopeContract.MetadataVersion,
                    new[]
                    {
                        new KeyValuePair<string, string>(ProjectScopeContract.SobIdField, "ABC"),
                        new KeyValuePair<string, string>(ProjectScopeContract.SobIdField, "XYZ")
                    }),
                "ABC"));
    }

    private static void ProjectScopeDistinguishesMissingMetadata()
    {
        Equal(ProjectScopeStatus.Unbound, ProjectScopeContract.Unbound().Status);
        Equal(
            ProjectScopeStatus.Invalid,
            ProjectScopeContract.Resolve(
                ProjectScopeContract.MetadataVersion,
                Array.Empty<KeyValuePair<string, string>>()).Status);
    }

    private static void ProjectScopeDetectsConflicts()
    {
        ProjectScope scope = ProjectScopeContract.Resolve(
            ProjectScopeContract.MetadataVersion,
            new[]
            {
                new KeyValuePair<string, string>(ProjectScopeContract.SobIdField, "ABC"),
                new KeyValuePair<string, string>(ProjectScopeContract.SobIdField, "XYZ")
            });
        Equal(ProjectScopeStatus.Ambiguous, scope.Status);
    }

    private static void ProjectScopeRejectsUnsupportedMetadata()
    {
        ProjectScope scope = ProjectScopeContract.Resolve(
            ProjectScopeContract.MetadataVersion + 1,
            ProjectScopeContract.Encode("ABC"));
        Equal(ProjectScopeStatus.Invalid, scope.Status);
        Equal("UNSUPPORTED_METADATA_VERSION", scope.Detail);
    }

    private static void ProjectScopeValidatesMatchingPayload()
    {
        ProjectScope scope = ProjectScopeContract.Resolve(
            ProjectScopeContract.MetadataVersion,
            ProjectScopeContract.Encode("ABC"));
        using JsonDocument payload = JsonDocument.Parse(
            "{\"projectScope\":{\"sobId\":\"abc\",\"generation\":7}}");

        Equal(true, ProjectScopeContract.TryValidatePayload(
            payload.RootElement, scope, 7, out string error));
        Equal(string.Empty, error);
    }

    private static void ProjectScopeRejectsMismatchedPayload()
    {
        ProjectScope scope = ProjectScopeContract.Resolve(
            ProjectScopeContract.MetadataVersion,
            ProjectScopeContract.Encode("ABC"));
        using JsonDocument payload = JsonDocument.Parse(
            "{\"projectScope\":{\"sobId\":\"XYZ\",\"generation\":7}}");

        Equal(false, ProjectScopeContract.TryValidatePayload(
            payload.RootElement, scope, 7, out string error));
        Equal("PROJECT_SCOPE_MISMATCH", error);
    }

    private static void ProjectScopeRejectsStaleGeneration()
    {
        ProjectScope scope = ProjectScopeContract.Resolve(
            ProjectScopeContract.MetadataVersion,
            ProjectScopeContract.Encode("ABC"));
        using JsonDocument payload = JsonDocument.Parse(
            "{\"projectScope\":{\"sobId\":\"ABC\",\"generation\":6}}");

        Equal(false, ProjectScopeContract.TryValidatePayload(
            payload.RootElement, scope, 7, out string error));
        Equal("PROJECT_SCOPE_GENERATION_STALE", error);
    }

    private static void ProjectScopeRejectsInvalidGeneration()
    {
        ProjectScope scope = ProjectScopeContract.Resolve(
            ProjectScopeContract.MetadataVersion,
            ProjectScopeContract.Encode("ABC"));

        using JsonDocument negativeGeneration = JsonDocument.Parse(
            "{\"projectScope\":{\"sobId\":\"ABC\",\"generation\":-1}}");
        Equal(false, ProjectScopeContract.TryValidatePayload(
            negativeGeneration.RootElement, scope, 7, out string negativeError));
        Equal("PROJECT_SCOPE_GENERATION_INVALID", negativeError);

        using JsonDocument nonNumericGeneration = JsonDocument.Parse(
            "{\"projectScope\":{\"sobId\":\"ABC\",\"generation\":\"7\"}}");
        Equal(false, ProjectScopeContract.TryValidatePayload(
            nonNumericGeneration.RootElement, scope, 7, out string nonNumericError));
        Equal("PROJECT_SCOPE_GENERATION_INVALID", nonNumericError);
    }

    private static void ProjectScopeRejectsUnboundPayload()
    {
        using JsonDocument payload = JsonDocument.Parse(
            "{\"projectScope\":{\"sobId\":\"ABC\",\"generation\":7}}");

        Equal(false, ProjectScopeContract.TryValidatePayload(
            payload.RootElement, ProjectScopeContract.Unbound(), 7, out string error));
        Equal("ACTIVE_PROJECT_SCOPE_UNBOUND", error);
    }

    private static string ComponentSignature(DigitalTwin twin) =>
        string.Join(";", twin.GetConnectedComponents().Select(component =>
            $"{string.Join(",", component.PosteIds)}:{string.Join(",", component.VaoIds)}"));

    private static DigitalTwin Build(params PosteDto[] postes) =>
        DigitalTwinBuilder.Build(State(postes, Array.Empty<VaoDto>()));

    private static DigitalTwin Build(PosteDto[] postes, VaoDto[] vaos) =>
        DigitalTwinBuilder.Build(State(postes, vaos));

    private static EscanearDwgResultado State(PosteDto[] postes, VaoDto[] vaos)
    {
        var state = new EscanearDwgResultado();
        state.Postes.AddRange(postes);
        state.Vaos.AddRange(vaos);
        foreach (var vao in vaos)
        {
            state.Relacoes.Add(Relation(vao.Id, vao.PosteOrigemId, vao.PosteDestinoId));
        }

        return state;
    }

    private static PosteDto Poste(string id, string handle = "") =>
        new PosteDto { Id = id, Handle = handle.Length == 0 ? $"HANDLE-{id}" : handle };

    private static VaoDto Vao(string id, string origin, string destination) =>
        new VaoDto
        {
            Id = id,
            Handle = $"HANDLE-{id}",
            PosteOrigemId = origin,
            PosteDestinoId = destination
        };

    private static DwgRelation Relation(string vaoId, string origin, string destination) =>
        new DwgRelation { VaoId = vaoId, PosteOrigemId = origin, PosteDestinoId = destination };

    private static void HasDiagnostic(DigitalTwin twin, string code)
    {
        if (!twin.Diagnostics.Any(diagnostic => diagnostic.Code == code))
        {
            throw new InvalidOperationException($"Missing diagnostic {code}.");
        }
    }

    private static void Sequence<T>(IEnumerable<T> expected, IEnumerable<T> actual)
    {
        if (!expected.SequenceEqual(actual))
        {
            throw new InvalidOperationException($"Expected [{string.Join(",", expected)}], got [{string.Join(",", actual)}].");
        }
    }

    private static void Equal<T>(T expected, T actual)
    {
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
        {
            throw new InvalidOperationException($"Expected '{expected}', got '{actual}'.");
        }
    }

    private static void Throws<TException>(Action action) where TException : Exception
    {
        try
        {
            action();
        }
        catch (TException)
        {
            return;
        }

        throw new InvalidOperationException($"Expected {typeof(TException).Name}.");
    }
}

namespace MapaCadPaleta
{
    public sealed class DwgDiagnostic
    {
        public string Code { get; set; } = string.Empty;
        public string Severity { get; set; } = "INFO";
        public string EntityType { get; set; } = string.Empty;
        public string EntityId { get; set; } = string.Empty;
        public string Handle { get; set; } = string.Empty;
        public string Message { get; set; } = string.Empty;
    }

    public sealed class DwgRelation
    {
        public string VaoId { get; set; } = string.Empty;
        public string PosteOrigemId { get; set; } = string.Empty;
        public string PosteDestinoId { get; set; } = string.Empty;
        public string Method { get; set; } = "Identity";
        public string Confidence { get; set; } = "Exact";
    }

    public sealed class PosteDto
    {
        public string Id { get; set; } = string.Empty;
        public string Numero { get; set; } = string.Empty;
        public string Handle { get; set; } = string.Empty;
        public string OperationId { get; set; } = string.Empty;
        public string TipoPoste { get; set; } = string.Empty;
        public bool TemTrafo { get; set; }
        public string PotenciaTrafo { get; set; } = string.Empty;
        public double X { get; set; }
        public double Y { get; set; }
        public bool IsLegacy { get; set; }
    }

    public sealed class VaoDto
    {
        public string Id { get; set; } = string.Empty;
        public string Handle { get; set; } = string.Empty;
        public string PosteOrigemId { get; set; } = string.Empty;
        public string PosteDestinoId { get; set; } = string.Empty;
        public double X1 { get; set; }
        public double Y1 { get; set; }
        public double X2 { get; set; }
        public double Y2 { get; set; }
        public double ExtensaoMetros { get; set; }
        public string OperationId { get; set; } = string.Empty;
        public string TipoRede { get; set; } = string.Empty;
        public string TextoVao { get; set; } = string.Empty;
        public bool IsLegacy { get; set; }
        public bool IsOrphan { get; set; }
    }

    public sealed class EscanearDwgResultado
    {
        public List<PosteDto> Postes { get; } = new List<PosteDto>();
        public List<VaoDto> Vaos { get; } = new List<VaoDto>();
        public List<DwgRelation> Relacoes { get; } = new List<DwgRelation>();
        public List<DwgDiagnostic> Diagnostics { get; } = new List<DwgDiagnostic>();
    }
}
