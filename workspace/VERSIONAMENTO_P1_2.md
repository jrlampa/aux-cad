# OXCAD P1.2: snapshots de artefatos

As ações `versao_capturar`, `versao_listar`, `versao_verificar` e
`versao_recuperar` são opt-in e usam o mesmo ProjectScope/ExecutionId do CLI
operacional. Exigem contexto verificado pelo AutoCAD: Xrecord do DWG ativo,
FingerprintGuid da Database e envelope entregue via stdin do subprocesso.
`--sob`/`--dwg-identity` manuais não são prova e não liberam essas ações.
`--alvo` é um caminho
relativo ao projeto para captura/listagem; `--snapshot-id` seleciona uma
versão para verificação/recuperação. O host não oferece botões de restauração
automática nesta fase.

Cada captura de **um arquivo explicitamente selecionado** cria uma pasta
`.auxcad_versions/<snapshot-id>/` na raiz da SOB, contendo `payload` (bytes
congelados) e `manifest.json`. O manifesto armazena esquema, SOB_ID, caminho e
identidade do DWG, revisão opcional, UTC da captura, ExecutionId/CorrelationId,
origem e lista de arquivos com caminho relativo, nome, tamanho, mtime em ns,
tipo e SHA-256. A serialização ordena as chaves; o identificador aleatório
distingue capturas do mesmo conteúdo. Revisão permanece `null` quando a origem
não fornece uma revisão real. Não se converte timestamp em número de revisão.

Verificação compara **bytes** com SHA-256, retornando `INTACT`, `CHANGED`,
`MISSING`, `MISSING_SNAPSHOT`, `MANIFEST_INCONSISTENT` ou `CONTEXT_MISMATCH`.
Recuperação só ocorre após validar manifesto, identidade e hash do payload;
cria exclusivamente `<nome>.recuperado-<snapshot-id><ext>` no mesmo diretório
do artefato. Nunca substitui o arquivo atual, nem a recuperação anterior.
Falhas deixam estado explícito e cópias parciais são removidas. Eventos das
ações seguem no JSONL existente; o manifesto SOB `.sob_state.json` não é
modificado. Snapshots não são inseridos automaticamente em entregáveis.

Limites: o CLI não pode verificar diretamente o FingerprintGuid no DWG; confia
na identidade recebida do host. O manifesto é auditável, mas não assinado:
adulteração simultânea do manifesto e payload por alguém com escrita no
diretório não é detectável sem armazenamento externo confiável. Capturas não
são automáticas nem cobrem versões anteriores à primeira captura. A captura
recusa arquivo que mude durante a cópia ao detectar hash/tamanho divergente;
escritores concorrentes posteriores ainda podem mudar o arquivo corrente.
Não há substituição in-place, rollback de DWG aberto, retenção automática ou
UI de gerenciamento nesta fase. O E2E Tk depende de Tcl/Tk utilizável no
Python instalado; a ausência desse suporte é limitação de ambiente.
