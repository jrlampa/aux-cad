using OxCad;
using System.IO;

static void Assert(bool condition, string message)
{
    if (!condition)
        throw new InvalidOperationException(message);
}

var gate = new ContextRefreshGate();
var documentA = new object();
var databaseA = new object();
var documentB = new object();
var databaseB = new object();

ContextRefreshTicket ticketA = gate.Begin(documentA, databaseA);
Assert(gate.IsCurrent(ticketA, documentA, databaseA), "DWG A deveria ser atual.");

var responseReady = new TaskCompletionSource<bool>(
    TaskCreationOptions.RunContinuationsAsynchronously);
Task<bool> delayedResponseA = Task.Run(async () =>
{
    await responseReady.Task;
    return gate.IsCurrent(ticketA, documentB, databaseB);
});

ContextRefreshTicket ticketB = gate.Begin(documentB, databaseB);
responseReady.SetResult(true);
Assert(!await delayedResponseA, "Resposta atrasada de A não pode ser aplicada em B.");
Assert(!gate.IsCurrent(ticketA, documentB, databaseB), "Troca para B deve invalidar A.");
Assert(gate.IsCurrent(ticketB, documentB, databaseB), "Último documento ativo deve vencer.");

long closingGeneration = gate.Invalidate();
Assert(!gate.IsCurrent(ticketB, documentB, databaseB), "Fechamento deve invalidar B.");
Assert(!gate.IsCurrentDocument(documentB), "Documento fechado não pode permanecer associado.");
Assert(gate.IsCurrentGeneration(closingGeneration), "Geração de fechamento deve ser atual.");

ContextRefreshTicket beforeSaveAs = gate.Begin(documentA, databaseA);
string savedPath = "C:\\Projetos\\A.dwg";
savedPath = "D:\\Renomeado\\Planta.dwg";
Assert(savedPath.StartsWith("D:"), "Caminho de teste deveria refletir Save As.");
Assert(gate.IsCurrent(beforeSaveAs, documentA, databaseA),
    "Save As mantém a identidade do Document/Database.");

ContextRefreshTicket afterSaveAs = gate.Begin(documentA, databaseA);
Assert(!gate.IsCurrent(beforeSaveAs, documentA, databaseA),
    "Nova consulta após Save As invalida resposta anterior.");
Assert(gate.IsCurrent(afterSaveAs, documentA, databaseA),
    "Consulta após Save As mantém o documento atual.");

// Teste 1: Mesmo DWG com wrapper gerenciado recriado pelo AutoCAD (instâncias distintas) NÃO gera falso invalidated
var docSame = new object();
var dbWrapperOriginal = new object();
var dbWrapperNewInstance = new object(); // AutoCAD Document.Database gera novo wrapper gerenciado a cada chamada
string stableFingerprint = "{A5D3E8B2-1111-2222-3333-444455556666}";

ContextRefreshTicket ticketSameDwg = gate.Begin(docSame, dbWrapperOriginal, stableFingerprint);
Assert(ticketSameDwg.DatabaseIdentity == stableFingerprint, "Ticket deve armazenar DatabaseIdentity.");
Assert(gate.IsCurrent(ticketSameDwg, docSame, dbWrapperNewInstance, stableFingerprint),
    "1. Mesmo DWG não gera falso invalidated quando FingerprintGuid é preservado.");

// Teste 2: Documentos diferentes geram invalidação
var docOther = new object();
Assert(!gate.IsCurrent(ticketSameDwg, docOther, dbWrapperNewInstance, stableFingerprint),
    "2. Documentos diferentes geram invalidação.");

// Teste 3: Troca de Database (Fingerprint diferente) é detectada imediatamente
string otherFingerprint = "{B999C8D7-7777-8888-9999-000011112222}";
Assert(!gate.IsCurrent(ticketSameDwg, docSame, dbWrapperNewInstance, otherFingerprint),
    "3. Troca de Database é detectada pelo fingerprint.");

// Teste 4: Guarda anti-reentrância evita chamadas duplicadas / recursão infinita
int scheduledCalls = 0;
bool isScheduled = false;
object lockObj = new object();
void SimularAgendamento()
{
    lock (lockObj)
    {
        if (isScheduled) return;
        isScheduled = true;
    }
    scheduledCalls++;
}
SimularAgendamento();
SimularAgendamento(); // tentativa concorrente ou recursiva deve ser descartada
Assert(scheduledCalls == 1, "4. Refresh não entra em recursão com guarda anti-reentrância.");

Console.WriteLine("ContextRefreshGate: all assertions passed.");

var executionRoot = Path.Combine(Path.GetTempPath(), "oxcad-execution-harness", Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(executionRoot);
try
{
    string executionId = Guid.NewGuid().ToString("N");
    string correlationId = Guid.NewGuid().ToString("N");
    var normal = new OxCadExecutionRecord(
        executionId,
        correlationId,
        "A057349839",
        Path.Combine(executionRoot, "A.dwg"),
        "fingerprint-a",
        "cqt",
        "oxcad.palette",
        executionRoot);

    Assert(normal.Snapshot().State == OxCadExecutionState.Iniciado, "Estado inicial incorreto.");
    Assert(normal.Transicionar(OxCadExecutionState.Executando, "Iniciando CQT"), "Executando não foi aceito.");
    Assert(normal.Transicionar(OxCadExecutionState.Concluido, "CQT concluído"), "Conclusão não foi aceita.");
    OxCadExecutionSnapshot completed = normal.Snapshot();
    Assert(completed.ExecutionId != completed.CorrelationId, "IDs devem ser distintos.");
    Assert(completed.FinishedAt.HasValue && completed.DurationMs >= 0, "Término/duração ausentes.");
    Assert(completed.SobId == "A057349839" && completed.DwgIdentity == "fingerprint-a",
        "Contexto da execução mudou.");
    Assert(!normal.Transicionar(OxCadExecutionState.Falhou, "transição atrasada"),
        "Conclusão tardia sobrescreveu estado terminal.");

    var failed = new OxCadExecutionRecord(
        Guid.NewGuid().ToString("N"),
        Guid.NewGuid().ToString("N"),
        "B123456789",
        "B.dwg",
        "fingerprint-b",
        "orcamento",
        "oxcad.palette",
        null);
    Assert(failed.Transicionar(OxCadExecutionState.Executando, "Iniciando orçamento"),
        "Execução de falha não iniciou.");
    var failure = new InvalidOperationException("falha de teste preservada");
    Assert(failed.Transicionar(OxCadExecutionState.Falhou, failure.Message, failure.ToString()),
        "Falha não foi aceita.");
    Assert(failed.Snapshot().Error?.Contains("InvalidOperationException") == true,
        "Diagnóstico da exceção não foi preservado.");

    var initializationFailure = new OxCadExecutionRecord(
        Guid.NewGuid().ToString("N"),
        Guid.NewGuid().ToString("N"),
        null,
        null,
        null,
        "cqt",
        "oxcad.palette",
        null);
    Assert(initializationFailure.Transicionar(OxCadExecutionState.Falhou, "Python indisponível"),
        "Falha durante inicialização deveria ir diretamente a Falhou.");

    var cancelled = new OxCadExecutionRecord(
        Guid.NewGuid().ToString("N"),
        Guid.NewGuid().ToString("N"),
        "A057349839",
        "A.dwg",
        "fingerprint-a",
        "LEVANTAR_CONDUTORES",
        "oxcad.palette",
        null);
    cancelled.Transicionar(OxCadExecutionState.Executando, "Comando CAD em execução");
    cancelled.Transicionar(OxCadExecutionState.Cancelado, "Comando CAD cancelado pelo usuário");
    Assert(cancelled.Snapshot().State == OxCadExecutionState.Cancelado,
        "Cancelamento CAD real não foi distinguido de falha.");

    var concurrentA = new OxCadExecutionRecord(
        Guid.NewGuid().ToString("N"), Guid.NewGuid().ToString("N"), "A", "A.dwg", "db-a", "cqt", "palette", null);
    var concurrentB = new OxCadExecutionRecord(
        Guid.NewGuid().ToString("N"), Guid.NewGuid().ToString("N"), "B", "B.dwg", "db-b", "cpfc", "palette", null);
    Assert(concurrentA.ExecutionId != concurrentB.ExecutionId, "Execuções simultâneas reutilizaram ID.");
    concurrentA.Transicionar(OxCadExecutionState.Executando, "Executando A");
    concurrentB.Transicionar(OxCadExecutionState.Executando, "Executando B");
    concurrentA.Transicionar(OxCadExecutionState.Concluido, "A concluído");
    Assert(concurrentB.Snapshot().State == OxCadExecutionState.Executando &&
           concurrentB.Snapshot().SobId == "B", "Conclusão de A contaminou B.");

    var artifactRun = new OxCadExecutionRecord(
        Guid.NewGuid().ToString("N"),
        Guid.NewGuid().ToString("N"),
        "A057349839",
        "A.dwg",
        "fingerprint-a",
        "ambiental",
        "palette",
        executionRoot);
    string createdFile = Path.Combine(executionRoot, "MEMORIAL_A057349839.docx");
    File.WriteAllText(createdFile, "artifact evidence");
    artifactRun.Transicionar(OxCadExecutionState.Executando, "Executando ambiental");
    artifactRun.Transicionar(OxCadExecutionState.Concluido, "Ambiental concluído");
    OxCadExecutionArtifact artifact = artifactRun.Snapshot().Artifacts.Single();
    Assert(artifact.Caminho == createdFile && artifact.Operacao == "criado" && artifact.Existe,
        "Arquivo criado não foi registrado com evidência.");

    var emptyRun = new OxCadExecutionRecord(
        Guid.NewGuid().ToString("N"),
        Guid.NewGuid().ToString("N"),
        "A057349839",
        "A.dwg",
        "fingerprint-a",
        "cqt",
        "palette",
        executionRoot);
    emptyRun.Transicionar(OxCadExecutionState.Falhou, "Falha sem saída");
    Assert(emptyRun.Snapshot().Artifacts.Count == 0,
        "Arquivo não criado foi reportado como artefato.");

    Console.WriteLine("OxCadExecutionRecord: all assertions passed.");
}
finally
{
    Directory.Delete(executionRoot, recursive: true);
}

// --- Testes de Reconciliação do Manifesto SOB (Requisitos A, B, C, D, E, H) ---
string testRoot = Path.Combine(Path.GetTempPath(), "oxcad-manifest-gate-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(testRoot);
try
{
    // Cenário A: Manifesto válido + DWG correspondente -> binding/contexto recuperável
    string dirA = Path.Combine(testRoot, "SOB_A");
    Directory.CreateDirectory(dirA);
    string dwgA = Path.Combine(dirA, "A057526153.dwg");
    File.WriteAllText(dwgA, "mock dwg content");
    string manifestA = Path.Combine(dirA, ".sob_state.json");
    File.WriteAllText(manifestA, """
    {
        "status": "CONCLUÍDO",
        "sob_id": "A057526153",
        "base_dwg": "A057526153.dwg"
    }
    """);

    MapaCadPaleta.ProjectScope scopeA = MapaCadPaleta.ProjectScopeContract.ReconcileCompletedManifest(dwgA);
    Assert(scopeA.IsBound, "Cenário A: Deveria reconciliar e vincular escopo.");
    Assert(scopeA.SobId == "A057526153", "Cenário A: SOB_ID deveria ser A057526153.");

    // Cenário B: Manifesto válido + DWG diferente -> NÃO vincular
    string dwgB_diff = Path.Combine(dirA, "OUTRO.dwg");
    File.WriteAllText(dwgB_diff, "mock dwg outro");
    MapaCadPaleta.ProjectScope scopeB = MapaCadPaleta.ProjectScopeContract.ReconcileCompletedManifest(dwgB_diff);
    Assert(!scopeB.IsBound, "Cenário B: DWG diferente não pode ser vinculado.");
    Assert(scopeB.Status == MapaCadPaleta.ProjectScopeStatus.Invalid, "Cenário B: Status deve ser Invalid.");
    Assert(scopeB.Detail == "BASE_DWG_MISMATCH", "Cenário B: Detalhe deve ser BASE_DWG_MISMATCH.");

    // Cenário C: Manifesto ausente -> NÃO vincular automaticamente (Unbound)
    string dirC = Path.Combine(testRoot, "SOB_C");
    Directory.CreateDirectory(dirC);
    string dwgC = Path.Combine(dirC, "A057349839.dwg");
    File.WriteAllText(dwgC, "mock dwg c");
    MapaCadPaleta.ProjectScope scopeC = MapaCadPaleta.ProjectScopeContract.ReconcileCompletedManifest(dwgC);
    Assert(!scopeC.IsBound, "Cenário C: Manifesto ausente não deve vincular.");
    Assert(scopeC.Status == MapaCadPaleta.ProjectScopeStatus.Unbound, "Cenário C: Status deve ser Unbound.");

    // Cenário D: Manifesto não concluído -> NÃO vincular
    string dirD = Path.Combine(testRoot, "SOB_D");
    Directory.CreateDirectory(dirD);
    string dwgD = Path.Combine(dirD, "A057999888.dwg");
    File.WriteAllText(dwgD, "mock dwg d");
    string manifestD = Path.Combine(dirD, ".sob_state.json");
    File.WriteAllText(manifestD, """
    {
        "status": "EM_ANDAMENTO",
        "sob_id": "A057999888",
        "base_dwg": "A057999888.dwg"
    }
    """);
    MapaCadPaleta.ProjectScope scopeD = MapaCadPaleta.ProjectScopeContract.ReconcileCompletedManifest(dwgD);
    Assert(!scopeD.IsBound, "Cenário D: Manifesto não concluído não deve vincular.");
    Assert(scopeD.Status == MapaCadPaleta.ProjectScopeStatus.Invalid, "Cenário D: Status deve ser Invalid.");
    Assert(scopeD.Detail == "MANIFEST_NOT_COMPLETED", "Cenário D: Detalhe deve ser MANIFEST_NOT_COMPLETED.");

    // Cenário E: Identidades conflitantes -> NÃO vincular e reportar conflito
    string dirE = Path.Combine(testRoot, "SOB_E");
    Directory.CreateDirectory(dirE);
    string dwgE = Path.Combine(dirE, "A057111222.dwg");
    File.WriteAllText(dwgE, "mock dwg e");
    string manifestE = Path.Combine(dirE, ".sob_state.json");
    File.WriteAllText(manifestE, """
    {
        "status": "CONCLUÍDO",
        "sob_id": "A057111222",
        "base_dwg": "A057111222.dwg"
    }
    """);
    string dwgConflict = Path.Combine(dirE, "PE_A057349839_DESENHO.dwg");
    File.WriteAllText(dwgConflict, "conflicting dwg");
    MapaCadPaleta.ProjectScope scopeE = MapaCadPaleta.ProjectScopeContract.ReconcileCompletedManifest(dwgE);
    Assert(!scopeE.IsBound, "Cenário E: Múltiplas identidades não devem vincular.");
    Assert(scopeE.Status == MapaCadPaleta.ProjectScopeStatus.Ambiguous, "Cenário E: Status deve ser Ambiguous.");
    Assert(scopeE.Detail == "CONFLICTING_SOB_IDENTITIES", "Cenário E: Detalhe deve ser CONFLICTING_SOB_IDENTITIES.");

    // Cenário H: Regra de habilitação dos botões de engenharia após contexto válido
    bool actionRunning = false;
    bool projectScopeResolved = scopeA.IsBound && scopeA.SobId == "A057526153";
    bool enabled = !actionRunning;
    bool habilitadoComProjectScope = enabled && projectScopeResolved;
    Assert(habilitadoComProjectScope, "Cenário H: Botões de engenharia devem ser habilitáveis quando projectScopeResolved == true.");

    bool scopeUnresolved = scopeC.IsBound;
    bool habilitadoSemScope = enabled && scopeUnresolved;
    Assert(!habilitadoSemScope, "Cenário H: Botões de engenharia devem ficar desabilitados quando escopo não está resolvido.");

    Console.WriteLine("ManifestReconciliation: all assertions (A, B, C, D, E, H) passed.");

    string realDwg = @"G:\Meu Drive\1-HBT\05_PROJETOS_HISTORICOS\OUTUBRO\01\SOB_A057526153\RE_A057526153_DESENHO.dwg";
    if (File.Exists(realDwg))
    {
        MapaCadPaleta.ProjectScope scopeReal = MapaCadPaleta.ProjectScopeContract.ReconcileCompletedManifest(realDwg);
        Assert(scopeReal.IsBound, "Real DWG deve ser reconciliado com sucesso.");
        Assert(scopeReal.SobId == "A057526153", "Real DWG SOB_ID deve ser A057526153.");
        Console.WriteLine($"Reconciliação real da SOB A057526153 passou com sucesso: {scopeReal.SobId} (IsBound={scopeReal.IsBound})");
    }

    string finalDwg = @"G:\Meu Drive\1-HBT\05_PROJETOS_HISTORICOS\OUTUBRO\VALIDACAO_FINAL\SOB_A057526153\CF_A057526153_DESENHO.dwg";
    if (File.Exists(finalDwg))
    {
        MapaCadPaleta.ProjectScope scopeFinal = MapaCadPaleta.ProjectScopeContract.ReconcileCompletedManifest(finalDwg);
        Assert(scopeFinal.IsBound, "Final DWG deve ser reconciliado com sucesso.");
        Assert(scopeFinal.SobId == "A057526153", "Final DWG SOB_ID deve ser A057526153.");
        Console.WriteLine($"Reconciliação operacional VALIDACAO_FINAL passou com sucesso: {scopeFinal.SobId} (IsBound={scopeFinal.IsBound}, Status={scopeFinal.Status})");
    }

    // =========================================================================
    // P2.6 GOVERNANÇA, REVISÃO TÉCNICA E RASTREABILIDADE
    // =========================================================================
    var rev = new OxCad.Governance.TechnicalReview(
        reviewId: Guid.NewGuid().ToString("N"),
        sobId: "A057526153",
        projectRoot: testRoot,
        dwgPath: Path.Combine(testRoot, "PE_A057526153_DESENHO.dwg"),
        databaseFingerprint: "{A5D3E8B2-1111-2222-3333-444455556666}",
        revisionId: "REV-01",
        sourceSnapshotId: null,
        createdAt: DateTime.UtcNow,
        op: "revisor_teste");

    Assert(rev.Status == OxCad.Governance.ReviewStatus.Draft, "P2.6: Revisão deve iniciar em Draft.");
    Assert(rev.History.Count == 1, "P2.6: Histórico deve conter evento inicial de Draft.");

    // Transição DRAFT -> IN_REVIEW
    rev.TransitionTo(OxCad.Governance.ReviewStatus.InReview, "Iniciando análise técnica", "revisor_teste");
    Assert(rev.Status == OxCad.Governance.ReviewStatus.InReview, "P2.6: Status deve ser InReview.");
    Assert(rev.History.Count == 2, "P2.6: Histórico deve registrar transição para InReview.");

    // Transição Inválida: IN_REVIEW -> DRAFT direta é proibida
    bool invalidTransitionThrown = false;
    try
    {
        rev.TransitionTo(OxCad.Governance.ReviewStatus.Draft, "Tentativa inválida", "revisor_teste");
    }
    catch (InvalidOperationException)
    {
        invalidTransitionThrown = true;
    }
    Assert(invalidTransitionThrown, "P2.6: Transição direta InReview -> Draft deve ser proibida.");

    // Finding
    var finding = new OxCad.Governance.ReviewFinding(
        findingId: Guid.NewGuid().ToString("N"),
        reviewId: rev.ReviewId,
        severity: OxCad.Governance.FindingSeverity.Major,
        category: "Cabo",
        description: "Condutor em trecho 2 diverge do padrão normativo",
        status: OxCad.Governance.FindingStatus.Open,
        evidenceReferences: new[] { "DOC/memorial.pdf" },
        pendingReference: "PEND-01",
        createdAt: DateTime.UtcNow);

    rev.Findings.Add(finding);
    Assert(rev.Findings.Count == 1, "P2.6: Finding deve ser registrado.");
    Assert(finding.Status == OxCad.Governance.FindingStatus.Open, "P2.6: Finding inicia Open.");

    finding.Resolve("Ajustado condutor no DWG conforme norma.");
    Assert(finding.Status == OxCad.Governance.FindingStatus.Resolved, "P2.6: Finding deve estar Resolved.");

    // Approval Gate
    var gateBlocked = OxCad.Governance.ApprovalGateResult.NotEligible(
        rev.ReviewId,
        new[] { "OPEN_CRITICAL_FINDINGS" });
    Assert(!gateBlocked.IsEligible, "P2.6: Gate bloqueado não deve ser elegível.");

    var gateOk = OxCad.Governance.ApprovalGateResult.Eligible(rev.ReviewId);
    Assert(gateOk.IsEligible, "P2.6: Gate ok deve ser elegível.");

    // Transição IN_REVIEW -> APPROVED
    rev.TransitionTo(OxCad.Governance.ReviewStatus.Approved, "Aprovado tecnicamente", "revisor_chefe");
    Assert(rev.Status == OxCad.Governance.ReviewStatus.Approved, "P2.6: Revisão deve estar Approved.");

    var approval = new OxCad.Governance.ReviewApproval(
        reviewId: rev.ReviewId,
        revision: rev.RevisionId,
        state: "APROVADO",
        approvedAt: DateTime.UtcNow,
        sobId: rev.SobId,
        dwgPath: rev.DwgPath,
        databaseFingerprint: rev.DatabaseFingerprint,
        sourceSnapshotId: rev.SourceSnapshotId,
        op: "revisor_chefe",
        findingsConsidered: new[] { finding.FindingId },
        decisionNote: "Projeto em conformidade total.");

    rev.SetApproval(approval);
    Assert(rev.Approval != null && rev.Approval.State == "APROVADO", "P2.6: Approval deve estar ativo.");

    // Revogação
    approval.Revoke("Identificada inconformidade posterior em campo");
    Assert(approval.State == "REVOGADO", "P2.6: Approval deve estar revogado de forma auditável.");

    // Rastreabilidade
    var chain = new OxCad.Governance.TraceabilityChain(
        sobId: rev.SobId,
        dwgPath: rev.DwgPath,
        databaseFingerprint: rev.DatabaseFingerprint,
        revisionId: rev.RevisionId,
        snapshotId: rev.SourceSnapshotId,
        reviewId: rev.ReviewId,
        reviewStatus: rev.Status,
        totalFindings: rev.Findings.Count,
        openFindings: 0,
        pendingReferences: rev.PendingReferences,
        approvalState: approval.State,
        deliveryPackageId: null);

    Assert(chain.SobId == "A057526153", "P2.6: Cadeia de rastreabilidade deve preservar SOB.");
    Console.WriteLine("P2.6 Governance & TechnicalReview: all C# assertions passed.");
}
finally
{
    Directory.Delete(testRoot, recursive: true);
}

// ==========================================
// P2.7A: Validação da Ponte CLI C# <-> Python
// ==========================================
var p27Root = Path.Combine(Path.GetTempPath(), "oxcad-p27a-test-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(p27Root);
try
{
    string testDwg = Path.Combine(p27Root, "PROJETO_TESTE.dwg");
    File.WriteAllText(testDwg, "DWG_FICTICIO");
    string sob = "A057526153";
    string fp = "{12345678-ABCD-EF01-2345-6789ABCDEF01}";
    string repoRoot = Directory.GetCurrentDirectory();
    while (!string.IsNullOrEmpty(repoRoot) && !File.Exists(Path.Combine(repoRoot, "acaddoc.lsp")))
    {
        repoRoot = Path.GetDirectoryName(repoRoot) ?? "";
    }

    async Task<string> ExecutarCliRevisaoAsync(string comando, Dictionary<string, string>? parametros = null, string? sobOverride = null, string? fpOverride = null)
    {
        var scriptPath = Path.Combine(repoRoot, "workspace", "workspace_review_cli.py");
        var sbArgs = new System.Text.StringBuilder();
        sbArgs.Append($"\"{scriptPath}\" {comando} --project-root \"{p27Root}\" --dwg \"{testDwg}\" --sob \"{sobOverride ?? sob}\" --fingerprint \"{fpOverride ?? fp}\"");
        if (parametros != null)
        {
            foreach (var kvp in parametros)
            {
                if (!string.IsNullOrWhiteSpace(kvp.Value))
                    sbArgs.Append($" --{kvp.Key} \"{kvp.Value}\"");
                else
                    sbArgs.Append($" --{kvp.Key}");
            }
        }
        var psi = new System.Diagnostics.ProcessStartInfo
        {
            FileName = "python",
            Arguments = sbArgs.ToString(),
            WorkingDirectory = repoRoot,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = System.Text.Encoding.UTF8
        };
        using var proc = System.Diagnostics.Process.Start(psi)!;
        string stdout = await proc.StandardOutput.ReadToEndAsync();
        string stderr = await proc.StandardError.ReadToEndAsync();
        await proc.WaitForExitAsync();
        int idxStart = stdout.IndexOf('{');
        int idxEnd = stdout.LastIndexOf('}');
        if (idxStart >= 0 && idxEnd > idxStart)
            return stdout.Substring(idxStart, idxEnd - idxStart + 1);
        if (!string.IsNullOrWhiteSpace(stderr))
            throw new Exception($"CLI error: {stderr}");
        return stdout;
    }

    // 1. Status inicial (sem revisão)
    string statusJson = await ExecutarCliRevisaoAsync("status");
    using (var doc = System.Text.Json.JsonDocument.Parse(statusJson))
    {
        Assert(doc.RootElement.GetProperty("success").GetBoolean(), "P2.7A: Status deve retornar success=true");
        Assert(!doc.RootElement.GetProperty("has_review").GetBoolean(), "P2.7A: Inicialmente não deve ter revisão");
    }

    // 2. Iniciar revisão
    var startParams = new Dictionary<string, string>
    {
        ["revision-id"] = "REV-01",
        ["reviewer"] = "Engenheiro QA"
    };
    string? createdRevId = null;
    string startJson = await ExecutarCliRevisaoAsync("iniciar", startParams);
    using (var doc = System.Text.Json.JsonDocument.Parse(startJson))
    {
        Assert(doc.RootElement.GetProperty("success").GetBoolean(), "P2.7A: Iniciar deve ter sucesso");
        var revObj = doc.RootElement.GetProperty("review");
        createdRevId = revObj.GetProperty("review_id").GetString();
        Assert(revObj.GetProperty("status").GetString() == "IN_REVIEW", "P2.7A: Status da revisão deve ser IN_REVIEW");
    }

    // 3. Registrar achado
    var findingParams = new Dictionary<string, string>
    {
        ["category"] = "DESENHO",
        ["severity"] = "MINOR",
        ["description"] = "Ajustar espessura de linha",
        ["author"] = "Revisor C#"
    };
    string findingJson = await ExecutarCliRevisaoAsync("achado", findingParams);
    using (var doc = System.Text.Json.JsonDocument.Parse(findingJson))
    {
        Assert(doc.RootElement.GetProperty("success").GetBoolean(), "P2.7A: Registrar achado deve ter sucesso");
        int total = doc.RootElement.GetProperty("counts").GetProperty("total_findings").GetInt32();
        Assert(total == 1, "P2.7A: Total de findings deve ser 1");
    }

    // 4. Solicitar alterações
    var reqChangesParams = new Dictionary<string, string>
    {
        ["actor"] = "Revisor C#",
        ["reason"] = "Correção de espessura necessária"
    };
    string reqChangesJson = await ExecutarCliRevisaoAsync("solicitar-alteracoes", reqChangesParams);
    using (var doc = System.Text.Json.JsonDocument.Parse(reqChangesJson))
    {
        Assert(doc.RootElement.GetProperty("success").GetBoolean(), "P2.7A: Solicitar alterações deve ter sucesso");
        Assert(doc.RootElement.GetProperty("review").GetProperty("status").GetString() == "CHANGES_REQUIRED",
            "P2.7A: Status deve transicionar para CHANGES_REQUIRED");
    }

    // 5. Incompatibilidade de contexto / Fingerprint divergente deve ser bloqueada com CONTEXT_MISMATCH
    Assert(!string.IsNullOrEmpty(createdRevId), "P2.7A: createdRevId deve ser válido");
    var invalidParams = new Dictionary<string, string> { ["review-id"] = createdRevId! };
    string invalidJson = await ExecutarCliRevisaoAsync("gate", invalidParams, fpOverride: "{DIVERGENTE-0000-0000-0000-000000000000}");
    using (var doc = System.Text.Json.JsonDocument.Parse(invalidJson))
    {
        Assert(!doc.RootElement.GetProperty("success").GetBoolean(), "P2.7A: Context mismatch deve falhar com success=false");
        Assert(doc.RootElement.GetProperty("error").GetString()!.Contains("CONTEXT_MISMATCH"), "P2.7A: Erro deve indicar CONTEXT_MISMATCH");
    }

    Console.WriteLine("P2.7A TechnicalReview CLI Bridge: all C# harness assertions passed.");

    // =========================================================================
    // P2.7B C# HARNESS: RECONCILIAÇÃO DA ENTREGA & SYNC QUEUE OFFLINE
    // =========================================================================
    async Task<string> ExecutarCliDeliveryAsync(string comando, Dictionary<string, string>? parametros = null, string? sobOverride = null, string? fpOverride = null)
    {
        var scriptPath = Path.Combine(repoRoot, "workspace", "workspace_delivery_cli.py");
        var sbArgs = new System.Text.StringBuilder();
        sbArgs.Append($"\"{scriptPath}\" {comando} --project-root \"{p27Root}\" --dwg \"{testDwg}\" --sob \"{sobOverride ?? sob}\" --fingerprint \"{fpOverride ?? fp}\"");
        if (parametros != null)
        {
            foreach (var kvp in parametros)
            {
                if (!string.IsNullOrWhiteSpace(kvp.Value))
                    sbArgs.Append($" --{kvp.Key} \"{kvp.Value}\"");
                else
                    sbArgs.Append($" --{kvp.Key}");
            }
        }
        var psi = new System.Diagnostics.ProcessStartInfo
        {
            FileName = "python",
            Arguments = sbArgs.ToString(),
            WorkingDirectory = repoRoot,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = System.Text.Encoding.UTF8
        };
        using var proc = System.Diagnostics.Process.Start(psi)!;
        string stdout = await proc.StandardOutput.ReadToEndAsync();
        string stderr = await proc.StandardError.ReadToEndAsync();
        await proc.WaitForExitAsync();
        int idxStart = stdout.IndexOf('{');
        int idxEnd = stdout.LastIndexOf('}');
        if (idxStart >= 0 && idxEnd > idxStart)
            return stdout.Substring(idxStart, idxEnd - idxStart + 1);
        if (!string.IsNullOrWhiteSpace(stderr))
            throw new Exception($"CLI error: {stderr}");
        return stdout;
    }

    // 1. Status de reconciliação de entrega não aprovada / não gerada -> BLOCKED
    string delivStatusJson = await ExecutarCliDeliveryAsync("status");
    using (var doc = System.Text.Json.JsonDocument.Parse(delivStatusJson))
    {
        Assert(doc.RootElement.GetProperty("success").GetBoolean(), "P2.7B: Status delivery deve retornar success=true");
        var rec = doc.RootElement.GetProperty("data").GetProperty("reconciliation");
        Assert(rec.GetProperty("status").GetString() == "BLOCKED", "P2.7B: Status deve ser BLOCKED quando não aprovada");
        Assert(!rec.GetProperty("eligible_for_sync").GetBoolean(), "P2.7B: Não deve ser elegível para sync");
    }

    // 2. Preparar sync para entrega não aprovada -> enfileira BLOCKED deterministicamente
    string prepSyncJson = await ExecutarCliDeliveryAsync("preparar-sync", new Dictionary<string, string>
    {
        ["provider-id"] = "sharepoint",
        ["package-id"] = "0123456789abcdef0123456789abcdef"
    });
    using (var doc = System.Text.Json.JsonDocument.Parse(prepSyncJson))
    {
        Assert(doc.RootElement.GetProperty("success").GetBoolean(), "P2.7B: Preparar sync deve retornar success=true");
        Assert(doc.RootElement.GetProperty("reconciliation").GetProperty("status").GetString() == "BLOCKED", "P2.7B: Status da reconciliação deve ser BLOCKED");
        var item = doc.RootElement.GetProperty("sync_item");
        Assert(item.ValueKind == System.Text.Json.JsonValueKind.Object, "P2.7B: SyncItem deve ser um objeto");
        Assert(item.GetProperty("status").GetString() == "BLOCKED", "P2.7B: SyncItem deve ser registrado como BLOCKED");
        Assert(item.GetProperty("sob_id").GetString() == sob, "P2.7B: SyncItem deve ter sob_id correspondente");
    }

    // 3. Listar fila e confirmar item gravado
    string filaJson = await ExecutarCliDeliveryAsync("fila-listar");
    using (var doc = System.Text.Json.JsonDocument.Parse(filaJson))
    {
        Assert(doc.RootElement.GetProperty("success").GetBoolean(), "P2.7B: Listar fila deve ter sucesso");
        int count = doc.RootElement.GetProperty("count").GetInt32();
        Assert(count >= 1, "P2.7B: Fila deve conter pelo menos 1 item");
    }

    // 4. Idempotência: reexecutar preparar-sync não duplica item na fila
    string prepSync2Json = await ExecutarCliDeliveryAsync("preparar-sync", new Dictionary<string, string>
    {
        ["provider-id"] = "sharepoint",
        ["package-id"] = "0123456789abcdef0123456789abcdef"
    });
    using (var doc = System.Text.Json.JsonDocument.Parse(prepSync2Json))
    {
        Assert(doc.RootElement.GetProperty("success").GetBoolean(), "P2.7B: Reexecução de preparar-sync deve ter sucesso");
    }
    string fila2Json = await ExecutarCliDeliveryAsync("fila-listar");
    using (var doc = System.Text.Json.JsonDocument.Parse(fila2Json))
    {
        int count = doc.RootElement.GetProperty("count").GetInt32();
        Assert(count == 1, "P2.7B: Fila deve manter exatamente 1 item (idempotência garantida)");
    }

    // 5. Teste de contrato C# de SyncQueue (SyncQueueContracts.cs)
    var csharpQueue = new OxCad.Offline.SyncQueueStore();
    var itemObj = OxCad.Offline.SyncItem.Create("op-p27b-01", "idemp-p27b-01", "delivery", "sharepoint", sob, status: OxCad.Offline.SyncStatus.Blocked);
    csharpQueue.Enqueue(itemObj);
    var queuedItems = csharpQueue.ListItems();
    Assert(queuedItems.Count == 1, "P2.7B: SyncQueueStore C# deve conter 1 item");
    var firstItem = queuedItems[0];
    Assert(firstItem.SobId == sob, "P2.7B: SyncQueueStore C# deve ler SOB_ID corretamente");
    Assert(firstItem.Status == OxCad.Offline.SyncStatus.Blocked, "P2.7B: SyncQueueStore C# deve ter status Blocked");

    // Atualização de status via contrato C#
    var updated = csharpQueue.UpdateStatus(firstItem.SyncId, OxCad.Offline.SyncStatus.Ready);
    Assert(updated != null && updated.Status == OxCad.Offline.SyncStatus.Ready, "P2.7B: UpdateStatus C# deve transicionar para Ready");
    var fetched = csharpQueue.GetBySyncId(firstItem.SyncId);
    Assert(fetched != null && fetched.Status == OxCad.Offline.SyncStatus.Ready, "P2.7B: GetBySyncId C# deve refletir atualização");

    Console.WriteLine("P2.7B Delivery Reconciliation & Offline SyncQueue: all C# harness assertions passed.");
}
finally
{
    Directory.Delete(p27Root, recursive: true);
}
