# COMMANDS BASELINE

Inventário de comandos e contratos observados na auditoria. **Nenhum comando deve ser alterado nesta fase.**

## 1. Comandos AutoCAD/AutoLISP

| Comando | Finalidade | Disparo | Fluxo interno | Resultado esperado | Arquivos/dependências |
|---|---|---|---|---|---|
| `MAPAPALETA` | Abrir a paleta cartográfica | linha de comando AutoCAD | carrega DLL se necessário e chama comando .NET | paleta OSM disponível | `mapa_paleta_loader.lsp`, DLL, AutoCAD |
| `OSMPALETA` | Alias de `MAPAPALETA` | linha de comando | delega para `c:MAPAPALETA` | mesma paleta | `mapa_paleta_loader.lsp` |
| `PALETAMAPA` | Alias de `MAPAPALETA` | linha de comando | delega para `c:MAPAPALETA` | mesma paleta | `mapa_paleta_loader.lsp` |
| `RECARREGAR_MAPAPALETA` | Recarregar DLL/assets | linha de comando | NETLOAD e chamada do comando .NET | paleta recarregada | `mapa_paleta_loader.lsp`, `Plugin.cs` |
| `MAPAPALETA-NET` | Comando .NET registrado | chamado pelo loader/AutoCAD | abre ou ativa `PaletteHost` | host visível | `Plugin.cs`, `PaletteHost.cs` |
| `RECARREGAR_MAPAPALETA` (.NET) | Recarregar conteúdo | chamado pelo LISP | recria/recarrega host/assets | conteúdo atualizado | `Plugin.cs`, `PaletteHost.cs` |

## 2. Ações WebView2 JS → C#

| Ação | Finalidade | Payload mínimo | Resposta/efeito |
|---|---|---|---|
| `inserir_poste` | criar poste e seus elementos | IDs, `x`, `y`, número e atributos | `resultado_insercao` |
| `capturar_ponto` | capturar ponto no AutoCAD | `fuso` opcional | `resultado_captura`/erro e atualização do frontend |
| `escanear_dwg` | ler/reconciliar o DWG | `fuso` opcional | `estado_dwg` v2 e `postes_dwg` |
| `desenhar_vao` | criar vão MT/BT | pontos, tipo, texto e IDs | `resultado_vao` |
| `desfazer_vao` | desfazer operação | `domainId`, `operationId` ou número | `resultado_desfazer` |
| `abrir_kmz_ambiental` | abrir contexto ambiental | ação sem payload | abertura do arquivo ambiental |
| `desenhar_elementos_urbanos` | inserir vias/calçadas/obstruções | JSON de contexto urbano | status CAD |
| `exportar_cqt` | exportar dados para CQT | JSON do projeto | arquivo/integração CQT |
| `abrir_cqtui` | abrir integração CQT | JSON do projeto | abertura da UI externa |

## 3. Contrato de compatibilidade

- Assinaturas de comandos, aliases e ações acima permanecem estáveis.
- `DomainId`, `VaoId`, `OperationId`, `Handle`, `Numero`, `PosteOrigemId` e `PosteDestinoId` não mudam de semântica.
- O frontend continua recebendo `resultado_insercao`, `resultado_vao`, `resultado_desfazer`, `estado_dwg` e `postes_dwg`.
- Nenhuma alteração de XData v2, layers, blocos, textos, coordenadas ou fluxo de inserção/traçado será feita nesta fase.
- Novos comandos só podem ser adicionados depois de definir teste de contrato, rollback e impacto no DWG.
