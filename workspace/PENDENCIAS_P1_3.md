# OXCAD P1.3: pendências técnicas

As pendências são criadas **somente por ação explícita**. As ações CLI
`pendencia_criar`, `pendencia_listar`, `pendencia_obter`,
`pendencia_atualizar`, `pendencia_resolver`, `pendencia_descartar` e
`pendencia_reabrir` exigem envelope de contexto do host AutoCAD capturado
do DWG ativo (Xrecord/FingerprintGuid) e entregue ao subprocesso via stdin.
Flags `--sob`/`--dwg-identity` fornecidas manualmente não provam identidade.
São ações P0.3: retornam ExecutionId/CorrelationId e estados de
execução; o ProjectScope é obrigatório mesmo sem a flag opcional do CLI.

Use `--pending-description` e `--pending-severity ALERTA|ERRO` para criar.
`--pending-id` identifica a pendência nas demais ações; `--pending-status`
define a transição em `pendencia_atualizar`. `--pending-responsible` recebe
apenas um valor informado por um operador, nunca é inferido. Uma pendência
baseada em validação P1.1 requer um resultado já obtido, passado em
`--pending-validation-json` ou `pending_validation` na API Python. Apenas
`ALERTA`/`ERRO` são aceitos, com SOB/DWG/fingerprint compatíveis. Armazena-se
somente referência à regra, estado, origem, timestamp e ExecutionId/CorrelationId
do resultado, e à fonte/posição quando presentes; não se copia o valor técnico
nem se recalcula CQT. `--snapshot-id` pode referenciar manifesto P1.2 íntegro.
Sem fonte comprovada, o campo `evidence` fica nulo.

O cadastro é `.oxcad/pending.json` por SOB/projeto. Segue o padrão local de
JSON atômico (`time.json`), com lock entre processos, esquema explícito,
histórico por item e rejeição de arquivo corrompido. `application.jsonl`
existente recebe eventos adicionais de ação/ID/status/evidência e estados de
execução; por ser rotativo, **não** é a fonte de verdade para consultar
pendências. O arquivo não é banco de dados nem é inserido em entregáveis.

Estados: `ABERTA` -> `EM_ANDAMENTO`, `RESOLVIDA` ou `DESCARTADA`;
`EM_ANDAMENTO` -> `ABERTA`, `RESOLVIDA` ou `DESCARTADA`;
`RESOLVIDA`/`DESCARTADA` -> `ABERTA` apenas por reabertura explícita.
Mudanças inválidas e atualizações silenciosas de itens terminais falham.
Cada alteração registra data, estado anterior/novo e IDs da execução.

Limites: não há botões de pendência na paleta nesta etapa. O CLI não relê o
FingerprintGuid internamente; rejeita headless sem contexto host. Não há autenticação
nem assinatura do resultado/manifesto: usuários com acesso de escrita local
podem adulterar arquivo e referências, e nomes de responsáveis informados
manualmente não são verificados. Escritas atômicas evitam JSON parcial, mas
não garantem transação entre cadastro e logger rotativo; falhas de log podem
impedir auditoria externa sem perder o histórico do item. Não há aprovação,
atribuição automática, notificações ou migração para GED.
