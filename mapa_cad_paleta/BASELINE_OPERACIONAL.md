# BASELINE OPERACIONAL

**Módulo:** `mapa_cad_paleta`  
**Data da auditoria:** 2026-09-27/28  
**Escopo:** descoberta, proteção e documentação. Nenhuma alteração funcional foi feita nesta fase.

## 1. Status executivo

O módulo é uma ferramenta operacional de AutoCAD que combina uma paleta WebView2, mapa OSM, inserção de postes e desenho de vãos de rede. O DWG continua sendo o artefato de trabalho e contém geometria CAD, textos, blocos e XData v2 quando a entidade é criada pelo fluxo atual.

Há evidência de implementação e testes offline para os fluxos abaixo. Isso não prova, por si só, que cada recurso seja usado diariamente. Onde não existe telemetria, homologação assistida ou relato de uso, a coluna **Uso operacional** permanece **não confirmado**.

## 2. Inventário funcional

| ID | Funcionalidade | Entrada | Saída | Arquivos envolvidos | Estado | Risco de regressão |
|---|---|---|---|---|---|---|
| OP-01 | Abrir/recarregar paleta | `MAPAPALETA`, aliases `OSMPALETA`/`PALETAMAPA`, `RECARREGAR_MAPAPALETA` | Paleta WebView2 carregada | `mapa_paleta_loader.lsp`, `Plugin.cs`, `PaletteHost.cs`, `MapaControl.xaml.cs` | CRÍTICA; uso operacional não confirmado por runtime nesta auditoria | Alto |
| OP-02 | Mapa e posicionamento | clique no mapa Leaflet/OSM, latitude/longitude e fuso | ponto UTM/CAD e estado visual | `web/index.html`, `web/app.js`, `SnyderConverter.cs`, `MapaControl.xaml.cs` | CRÍTICA; implementação e testes offline confirmados | Alto |
| OP-03 | Capturar ponto no CAD | ação `capturar_ponto`, fuso 1–60 | retorno de coordenada para o frontend | `MapaControl.xaml.cs`, `CadBridge.cs`, `web/app.js` | IMPORTANTE; implementação confirmada, runtime não confirmado | Alto |
| OP-04 | Inserir poste | payload `inserir_poste` com IDs, coordenadas, número e atributos | bloco, número, descrição, XData e resposta `resultado_insercao` | `web/app.js`, `MapaControl.xaml.cs`, `CadBridge.cs` | CRÍTICA; contrato/testes offline confirmados | Crítico |
| OP-05 | Estruturas MT/BT e transformador | atributos do poste, estruturas e potência | blocos/atributos CAD correspondentes | `web/index.html`, `web/app.js`, `CadBridge.cs` | IMPORTANTE; uso operacional não confirmado | Alto |
| OP-06 | Seleção/edição de poste | estado do formulário e marker selecionado | atualização visual/payload de poste | `web/index.html`, `web/app.js`, `tracado.js` | AUXILIAR; existência documentada, uso não confirmado | Médio |
| OP-07 | Traçado contínuo | seleção de Poste A e B | `desenhar_vao`, polilinha, texto e relação topológica | `web/tracado.js`, `web/app.js`, `MapaControl.xaml.cs`, `CadBridge.cs` | CRÍTICA; implementação/testes offline confirmados | Crítico |
| OP-08 | Vão MT/BT e metragem | pontos, `tipoRede`, texto e IDs de origem/destino | layers `CABOS_MT`/`CABOS_BT`, texto, XData v2 | `CadBridge.cs`, `tracado.js` | CRÍTICA; uso operacional não confirmado por runtime | Crítico |
| OP-09 | Sincronizar/scan do DWG | `escanear_dwg` | `estado_dwg` v2, fallback `postes_dwg`, diagnósticos e estatísticas | `MapaControl.xaml.cs`, `CadBridge.cs`, `web/app.js` | CRÍTICA; implementação/testes offline confirmados | Crítico |
| OP-10 | Reconstruir traçado | `estado_dwg` recebido | markers, vãos e relações reconstruídos no mapa | `web/app.js`, `web/tracado.js` | IMPORTANTE; implementação confirmada, runtime não confirmado | Alto |
| OP-11 | COPY/reconciliação | entidades copiadas no AutoCAD e novo scan | remapeamento de IDs ou diagnóstico de incerteza | `CadBridge.cs` | IMPORTANTE; testes offline confirmados | Alto |
| OP-12 | MOVE | comando nativo AutoCAD e novo scan | preservação geométrica/identidade esperada | scan e reconciliação existentes | NÃO CONFIRMADA; não há comando MOVE dedicado no módulo | Alto |
| OP-13 | ERASE/orfandade | apagamento nativo ou operação CAD | diagnóstico de vão órfão no scan | `CadBridge.cs`, testes | IMPORTANTE; comportamento parcialmente coberto offline | Alto |
| OP-14 | Undo | `desfazer_vao` com `operationId`, `domainId` ou número | entidades removidas e `resultado_desfazer` | `web/app.js`, `MapaControl.xaml.cs`, `CadBridge.cs` | CRÍTICA; implementação/testes offline confirmados | Crítico |
| OP-15 | Vias, calçadas e obstruções | contexto urbano/OSM e payload de desenho | entidades urbanas no CAD | `AmbientalParser.cs`, `CadBridge.cs`, assets web | AUXILIAR; existência/testes, uso não confirmado | Médio |
| OP-16 | Restrições ambientais | KMZ/arquivo ambiental e raycasting | overlay/diagnóstico e elementos ambientais | `AmbientalParser.cs`, `web/ambiental_overlay.js` | AUXILIAR; existência/testes, uso não confirmado | Médio |
| OP-17 | Medição/régua | ferramenta visual e geodesia | distância/medição no mapa | `web/index.html`, `web/app.js`, Snyder | AUXILIAR; existência/testes, uso não confirmado | Médio |
| OP-18 | OSM/contexto urbano | consultas oficiais OSM | contexto exibido/consumido pelo fluxo | `web/app.js`, `web/urban_context.js` | IMPORTANTE; implementação/testes offline confirmados | Médio |
| OP-19 | Exportação CQT/KMZ | `exportar_cqt`, `abrir_cqtui` e fluxos de mapa postes | arquivo/abertura externa | `MapaControl.xaml.cs`, `web/app.js`, `mapa_postes` | AUXILIAR; existência/testes, uso não confirmado | Médio |

**Classificação:** CRÍTICA = fluxo que deve ser preservado no trabalho diário; IMPORTANTE = fluxo funcional com impacto relevante; AUXILIAR = suporte ou recurso eventual; NÃO CONFIRMADA = existência de código sem evidência de uso real.

## 3. Identidade e dados protegidos

| Identidade | Criador | Persistência | Uso | Pode mudar nesta fase? |
|---|---|---|---|---|
| `DomainId` | frontend propõe; C# valida/autoriza | XData `AUXCAD_POSTE` v2 | poste, scan, COPY, Undo | Não |
| `VaoId` | frontend/C# | XData `AUXCAD_VAO` v2 | vão, reconstrução e relações | Não |
| `OperationId` | frontend | XData e histórico em memória | agrupamento de inserção e Undo | Não |
| `Handle` | AutoCAD | entidade DWG; histórico em memória | remoção de entidades no Undo | Não |
| `Numero` | usuário/frontend | XData e representação visual | UX e fallback legado | Não |
| `PosteOrigemId` / `PosteDestinoId` | frontend/traçado | XData do vão | topologia, reconciliação e diagnóstico | Não |

## 4. Retrocompatibilidade do DWG

O scanner possui leitura defensiva para entidades sem XData, legado, XData inválido e versões futuras. A implementação reconhece postes legados e pode marcar relações inferidas ou ambíguas. `estado_dwg` v2 é o retorno canônico atual; `postes_dwg` é fallback legado.

Não foi feita migração automática, alteração em massa ou atualização de todos os DWGs. O comportamento de entidades nativas COPY/MOVE/ERASE deve continuar sendo validado em AutoCAD antes de qualquer evolução.

## 5. Evidência de baseline

- `dotnet build mapa_cad_paleta/MapaCadPaleta.csproj -c Release`: passou para `net8.0-windows` e `net48`; 0 erros e 2 warnings `MSB3277` de conflito de `Microsoft.VisualBasic`.
- `py -m pytest tests/test_mapa_paleta.py tests/test_mapa_postes.py -v`: **59 passed**.
- Runtime AutoCAD: **não executado**; portanto não há declaração de PASS runtime.
- As alterações preexistentes no worktree foram preservadas.
