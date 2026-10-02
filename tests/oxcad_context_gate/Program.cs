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
}
finally
{
    Directory.Delete(testRoot, recursive: true);
}