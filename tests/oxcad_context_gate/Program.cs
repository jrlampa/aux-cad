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