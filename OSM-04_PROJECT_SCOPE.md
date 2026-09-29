# OSM-04 — Escopo lógico do estado OSM

**Tipo de atividade:** investigação e decisão de arquitetura; sem implementação
**Estado:** análise de código concluída; validação no AutoCAD e conteúdo OSM do template não confirmados

## Decisão executiva

`SOB_ID` é a identidade lógica persistente mais forte disponível no fluxo SOB atual: é fornecida/validada como identificador da SOB, nomeia a pasta e o DWG canônicos, é gravada no manifesto `.sob_state.json` e é o campo de identidade do `ProjectWorkspace` (descrito no código como contexto da “SOB / Projeto”). Portanto, é uma **chave candidata apropriada para escopar um projeto no fluxo SOB**, desde que seja obtida do contexto autoritativo da SOB.

Não há evidência suficiente para tratá-la como uma identidade universal e invariável de todo projeto/intervenção: não foi demonstrada a cardinalidade entre SOB, projeto lógico e DWGs em todos os fluxos, nem o comportamento de `SaveAs`, cópias externas ou reaproveitamento de um mesmo identificador para outra intervenção. O scanner também pode inferir a SOB a partir de nomes de pasta/arquivos, o que não equivale a uma associação autoritativa.

**No módulo OSM, `SOB_ID` não é atualmente recebido, consultado, gravado em XData nem incorporado à chave de identidade OSM.** Assim, OSM-04 conclui que `SOB_ID` é a melhor chave disponível para um escopo SOB conhecido, mas não que o estado OSM esteja hoje isolado por projeto. A integração desse contexto exige uma fase de implementação/aprovação separada.

## Evidências do repositório

| Evidência | O que o código comprova | Limite |
|---|---|---|
| `sob/sob_core.py`: `obter_sob_id`, `obter_sob_name`, `derivar_caminhos_sob` | O identificador é normalizado/validado e usado para construir `SOB_<ID>` e caminhos da SOB. A documentação do helper o descreve como número informado pelo usuário e usado para identificação interna. | Formato válido não prova unicidade corporativa ou semântica universal de projeto. |
| `sob/sob_manager.py` e `sob/sob_idempotencia.py` | O manifesto persiste `sob_id`, `sob_name`, `run_id` e estado da execução. O fluxo bloqueia uma repetição no mesmo destino quando encontra uma SOB existente, conforme o estado do manifesto. | Persistência do contexto da SOB não comprova que toda cópia ou DWG derivado mantenha uma relação verificável com ela. |
| `workspace/workspace_core.py`: `ProjectWorkspace` | O modelo declara explicitamente um contexto central “SOB / Projeto” e contém `sob_id`, `sob_name`, raiz e um `dwg_principal`. | Um campo do modelo não estabelece sozinho a política de identidade para DWGs externos, múltiplos desenhos ou `SaveAs`. |
| `workspace/workspace_scanner.py`: `scan`, `detectar_sob_em_diretorio`, `detectar_dwg_principal` | O scanner pode receber o ID ou inferi-lo do diretório/nomes; seleciona um DWG principal por heurísticas de nome. | Identidade inferida e escolha heurística não devem servir como prova de escopo para evitar mistura de estado. |
| `sob/sob_cad_launcher.lsp` | O launcher passa o identificador ao orquestrador, abre o caminho-base e compara o desenho ativo com o caminho esperado naquele fluxo. | Essa passagem termina no fluxo de preparação/abertura; não foi encontrado encaminhamento do ID para a paleta OSM. |
| `mapa_cad_paleta/MapaControl.xaml.cs`, `PaletteHost.cs` | A paleta mantém um controle/WebView estático durante seu ciclo de vida e processa mensagens do WebView. Não há associação observada com `SOB_ID` nem tratamento de troca de documento para resetar estado OSM. | Não comprova o comportamento em todas as sequências de abertura/fechamento no AutoCAD. |
| `mapa_cad_paleta/web/vias_obstrucoes.js` | `cacheGrid`, `waysProcessados` e `elementosAcumulados` são estado em memória da página; elementos são acumulados e enviados ao CAD. | O estado não tem partição por SOB ou desenho. O estado em memória pode ser reaproveitado enquanto a mesma página permanece ativa; não se afirma persistência entre reinicializações. |
| `mapa_cad_paleta/CadBridge.cs` | As operações usam `MdiActiveDocument` e `Database.CurrentSpaceId`; entidades OSM são indexadas e gravadas com `AUXCAD_OSM`. A chave é `osmType:osmId:categoria`, e o fingerprint é calculado separadamente. | O desenho/Database corrente fornece escopo físico da escrita, não uma identidade lógica de projeto. A chave OSM não inclui projeto. |

## Identidades distintas

| Conceito | Evidência/uso observado | Não confundir com |
|---|---|---|
| **Identidade lógica de projeto no fluxo SOB** | `SOB_ID`, persistido no manifesto e usado pelo `ProjectWorkspace`. É a chave candidata para partição do estado por projeto nesse fluxo. | Nome de arquivo, caminho, `BASE_DWG`, região geográfica ou ID de uma execução. |
| **Identidade da fonte OSM** | `osmType` + `osmId` + categoria, usada para reconhecer um elemento OSM; fingerprint distingue o conteúdo observado. | Identidade do projeto. Um mesmo way OSM pode aparecer legitimamente em mais de um projeto. |
| **Identidade física CAD** | Entidade/`ObjectId` dentro do Database e espaço corrente; metadados OSM são gravados em `AUXCAD_OSM`. | Identidade lógica SOB. Handle/ObjectId não deve ser chave de projeto nem de OSM. |
| **Identidade da execução** | `run_id` gerado pelo fluxo SOB. | Identidade estável do projeto. |

## Cenários e política proposta

Estados da matriz: **CONFIRMADO** = comportamento demonstrado pelo código; **PARCIAL** = existe evidência de mecanismo, mas falta confirmar todo o cenário; **DESCONHECIDO** = repositório/evidência disponível não permite concluir.

| Cenário | Evidência atual | Classificação | Política de escopo |
|---|---|---|---|
| Reabrir o mesmo DWG de uma SOB existente | O DWG retém XData por meio do mecanismo CAD implementado; o leitor indexa `AUXCAD_OSM` no Database ativo. A validação real no AutoCAD não foi executada. | **PARCIAL** | Pode reconciliar com o estado OSM daquele DWG, após confirmar o contexto de projeto. Não reutilizar cegamente o cache da WebView. |
| Repetir consulta/desenho no mesmo DWG e mesmo projeto | A página acumula elementos; o CAD ignora uma entidade existente com chave/fingerprint iguais e substitui conteúdo divergente. | **PARCIAL** | Reutilização idempotente fica limitada ao mesmo Database/DWG e à identidade OSM; não equivale a estado compartilhado entre projetos. |
| Novo projeto com `SOB_ID` diferente, mesma região e mesmo way OSM | A chave OSM não contém `SOB_ID`; o CAD escreve no documento atualmente ativo. A WebView não particiona o acumulado por projeto. | **CONFIRMADO quanto à ausência de partição no código; runtime não validado** | Não herdar estado de cache de outra SOB. A mesma referência OSM pode ser consultada/desenhada independentemente em cada projeto/DWG. |
| Alternar documentos enquanto a mesma paleta/página continua ativa | A paleta é estática; o estado JS é em memória; o bridge resolve o `MdiActiveDocument` ao executar operações. Não foi encontrado reset/escopo por documento. | **PARCIAL** | Exigir contexto explícito e invalidar/segregar o estado da WebView ao trocar de projeto/documento antes de qualquer reutilização. |
| Criar nova SOB copiando `modelos/prancha.dwg` | `sob_manager.py` copia o template; o código valida o cabeçalho DWG. | **CONFIRMADO quanto à cópia; DESCONHECIDO quanto a `AUXCAD_OSM` no conteúdo do template** | Até prova direta em cópia controlada, tratar o template como **OSM não confirmado**; não afirmar que está limpo nem que está contaminado. |
| Duas bases/DWGs ou DWG externo associados à mesma SOB | O modelo aponta um `dwg_principal`; scanner seleciona por heurísticas. O fluxo de preparação usa caminho canônico. | **PARCIAL** | `SOB_ID` sozinho não escolhe com segurança qual Database deve ser lido/escrito. Confirmar vínculo projeto–DWG e tratar cada Database como armazenamento físico separado. |
| `SaveAs`, cópia de DWG ou mesmo ID reutilizado para outra intervenção | Não foi localizado contrato que preserve/atualize vínculo lógico nesses casos. | **DESCONHECIDO** | Não deduzir equivalência de projeto pelo caminho, nome ou conteúdo espacial. Solicitar vínculo autoritativo antes de reutilizar estado. |
| Projetos diferentes com IDs distintos e elementos OSM iguais | Identidade OSM é externa ao projeto; cada DWG possui seu próprio Database. | **CONFIRMADO no modelo de identidade; escrita real não homologada** | Permitir a mesma identidade OSM em projetos independentes; nunca transportar entidades/estado de um projeto ao outro por coincidência de `osmId`. |

## Política recomendada para a próxima implementação (não implementada)

1. Usar `SOB_ID` como escopo lógico **somente quando recebido de contexto SOB autoritativo e validado**. Não promover extração de nome de pasta/arquivo a prova de identidade.
2. Manter as identidades separadas: chave do projeto (`SOB_ID` no domínio SOB), chave da fonte OSM (`osmType`, `osmId`, categoria) e referência física CAD (entidade/Database). Não incorporar Handle, número visual, coordenadas ou caminho à identidade lógica.
3. Associar e validar explicitamente o documento CAD ativo com o projeto antes de consultar, reaproveitar ou enviar estado OSM. Se o vínculo estiver ausente ou ambíguo, não reutilizar cache de outra sessão/projeto.
4. Particionar o estado transitório da WebView por contexto confirmado (projeto e documento), e invalidá-lo ao trocar de contexto. Uma nova leitura/reconsulta deve produzir um conjunto atual substituível/reconciliável, não um append não delimitado de resultados antigos.
5. Manter a reconciliação de entidades persistidas dentro do Database do desenho correto. A presença da mesma referência OSM em um segundo projeto não autoriza copiar ou compartilhar entidades CAD.
6. Manter o conteúdo de `modelos/prancha.dwg` classificado como **não confirmado** até inspeção em ambiente controlado/cópia, sem abrir ou alterar o DWG do usuário.

Essas recomendações não alteram a arquitetura vigente: DWG permanece fonte operacional; estado OSM em memória é transitório; qualquer projeção/cache de projeto é derivada e não deve reparar ou escrever fora do fluxo CAD explícito.

## Fora do escopo e limitações

- Nenhum código funcional foi alterado; nenhum cliente ou serviço de escopo foi criado.
- Nenhum DWG foi aberto, alterado ou inspecionado no AutoCAD. O conteúdo OSM/XData de `modelos/prancha.dwg` continua **DESCONHECIDO**.
- Não foi executado teste real de AutoCAD; persistência e comportamento runtime continuam sem homologação.
- `OSM-01R` continua **PENDENTE**; não se afirma idempotência real/homologação.
- Não houve consultas OSM adicionais nem teste de outros projetos.
- `DT-01H` e validação runtime do Digital Twin não são abrangidas nem alteradas por esta investigação.
- O contrato da Universalização permanece independente e incompleto; nenhum dado ou integração foi alterado.

## Próximos passos recomendados

1. Aprovar a política de escopo antes de qualquer implementação.
2. Definir de forma autoritativa o vínculo `SOB_ID`–projeto–DWG, incluindo `SaveAs`, cópia e múltiplos DWGs.
3. Em ambiente controlado e com cópias, verificar conteúdo OSM do template e validar troca de documentos, reabertura e persistência no AutoCAD.
4. Só então planejar alterações de contexto/invalidação da WebView e testes automatizados que cubram a partição de cache sem alegar homologação de runtime.
