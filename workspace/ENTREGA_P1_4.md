# OXCAD P1.4: pacote de entrega e aprovação

O pacote é opt-in e exige ProjectScope e FingerprintGuid obtidos pelo host
AutoCAD do DWG ativo e transportados via stdin; flags manuais não são prova.
As ações CLI são
`entrega_gerar`, `entrega_verificar`, `entrega_aprovar` e `entrega_revogar`.
Todas participam do ciclo P0.3. Não há aprovação automática ao validar,
gerar manifesto ou criar pendência.

Para gerar: informe um ou mais `--delivery-artifact` (caminhos relativos ao
projeto, além do DWG incluído automaticamente) e resultados P1.1 já obtidos
em `--delivery-validations-json`; resultados ausentes impedem geração. Podem
ser vinculados `--delivery-snapshot` da P1.2, desde que o arquivo e seu hash
correspondam ao conjunto selecionado. O CLI não recalcula validações. O
identificador retornado em `package_id` serve em `--package-id` para as
outras ações. Revisão (`--revision`) permanece nula se não for fornecida.

Em `.oxcad/deliveries/<package-id>/`, `manifest.json` lista SOB, DWG,
fingerprint, revisão conhecida, timestamp, origem, IDs de execução, versão
de esquema, arquivos relativos com tamanho/mtime/SHA-256 P1.2, estados e
fontes P1.1, retrato de pendências P1.3 e referências P1.2.
`manifest.sha256` é o checksum canônico do JSON. **Não há cópia dos arquivos**:
o manifesto preserva qual era o estado observado, enquanto a verificação
posterior retorna `INTACT`, `DIVERGENT` ou `MISSING` para cada caminho.
`approval.json`, gravado somente mediante confirmação explícita, liga a
aprovação ao checksum do manifesto. `verify` retorna `CONFIRMED` somente
quando os arquivos e as pendências correspondem ao retrato aprovado.
Pacotes alterados/inconsistentes retornam `INVALID`; divergentes nunca
mantêm `approval_valid=true`.

Para aprovar: `entrega_aprovar --package-id ... --confirm-approval`. Se
houver `ERRO` ou pendência `ABERTA`/`EM_ANDAMENTO`, exigir também
`--acknowledge-issues --decision-note "<decisão real>"`. Isso registra
condição e decisão, não estabelece critério técnico de aceitação.
`approver` é nulo: não há identidade de aprovador autenticada neste fluxo.
`entrega_revogar --package-id ... --revocation-reason "<motivo>"` é
explícita e irreversível para esse pacote; uma nova aprovação exige um novo
pacote. Os eventos P0.3 e os metadados de entrega seguem no JSONL existente,
sem transformá-lo em fonte de verdade.

Limites: o CLI não relê o DWG; a autoridade vem do processo pai AutoCAD e
do contrato host enviado por stdin, não de argumentos headless. A prova E2E
de fingerprint/Xrecord real no AutoCAD ainda depende de execução no host.
Os arquivos são referenciados, não congelados: sua
modificação ou remoção invalida a aprovação e não existe recuperação por
esse pacote (snapshots opt-in P1.2 são independentes). O checksum não é
assinatura; atores com acesso local de escrita podem alterar manifesto e
checksum juntos, ou forjar `approval.json`. Não há autenticação nova nem
comprovação de identidade pessoal. A partir de P0/P1.5, resultados CQT novos
carregam SHA-256 e mtime da fonte validada; pacote de entrega rejeita resultado
com fonte alterada ou hash ausente. Resultados antigos permanecem legíveis
para auditoria, mas não comprovam os bytes de um novo pacote. O CLI não lê o
FingerprintGuid do DWG e confia na identidade declarada pelo host; nem hash
nem manifesto autenticam um chamador que pode adulterar arquivos locais.
Não foi adicionada UI de aprovação:
capturar uma seleção e a geração de contexto reativo com confirmação segura
na paleta exigiria integração host não disponível neste escopo.
