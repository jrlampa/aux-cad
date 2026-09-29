# MAPA_CAD_PALETA — BASELINE ESTRATÉGICO

## Conclusão

O que deve ser protegido é uma ferramenta operacional de desenho: abertura da paleta, mapa/posicionamento, inserção de postes, traçado de vãos, identidades CAD, XData v2, sincronização do DWG, reconstrução, COPY/reconciliação e Undo. Esses fluxos já formam um contrato de compatibilidade, mesmo quando o uso diário ainda não foi confirmado por telemetria ou runtime assistido.

O produto atual não deve ser tratado como protótipo descartável. A evolução segura é:

```text
produto atual
    ↓
baseline operacional
    ↓
contrato de compatibilidade
    ↓
riscos de regressão
    ↓
arquitetura revalidada
    ↓
evolução incremental
    ↓
Digital Twin
```

## Decisões do dossiê anterior

| Decisão | Classificação nesta fase | Conclusão |
|---|---|---|
| Digital Twin evolui sobre o módulo atual | CONFIRMADA | princípio obrigatório |
| Identidade persistente por IDs | CONFIRMADA | preservar `DomainId`, `VaoId`, `OperationId` e relações |
| DWG como artefato operacional | CONFIRMADA | retrocompatibilidade é requisito |
| DWG como fonte de verdade absoluta | PRECISA DE VALIDAÇÃO | hoje `estado_dwg` é fonte canônica da sincronização, mas não se deve extrapolar para todos os domínios |
| XData v3/DT-01 | PREMATURA | não implementar nesta fase |
| Duplicar coordenadas no XData | PREMATURA | geometria CAD já representa posição; provar necessidade antes |
| Timestamp, proveniência e confiança no XData | HIPÓTESE | podem pertencer a camada posterior, não duplicar sem caso de uso |
| Sidecar | PRECISA DE VALIDAÇÃO | não criar sem requisito de versionamento/histórico que o DWG não suporte |
| GeoJSON | PRECISA DE VALIDAÇÃO | exportação aberta pode ser útil, mas não é requisito do baseline |
| `ObjectModified` | PREMATURA | não adicionar listener nesta fase |
| `RedeTopologica` em JS | HIPÓTESE | frontend reconstrói estado; autoridade e sincronização devem continuar no contrato atual |
| Twin autoritativo externo | REJEITADA nesta fase | não há evidência de necessidade nem autorização para separar a fonte operacional |

## Contrato de compatibilidade

### Funcional
Inserção, traçado, scan, reconstrução, Undo, COPY/reconciliação, OSM e exportações existentes continuam disponíveis.

### Visual e CAD
Layers, blocos, textos, cores, geometria 2.5D e convenções de coordenadas não mudam sem decisão explícita.

### Dados
XData v2, IDs, relações de origem/destino e diagnósticos legados permanecem legíveis. Não há migração automática.

### UX e arquivos
Comandos, aliases, botões e mensagens WebView2 preservam nomes e payloads. DWGs já produzidos continuam sendo lidos defensivamente.

### Performance
Nenhuma evolução deve degradar significativamente a abertura, inserção, traçado ou sincronização.

## Arquitetura segura em camadas

1. **Camada 0 — produto operacional atual:** congelar contratos e medir uso real.
2. **Camada 1 — identidade preservada:** consolidar evidência e compatibilidade dos IDs existentes, sem novo schema.
3. **Camada 2 — modelo semântico derivado:** explicitar postes, vãos e relações a partir do scan, sem substituir a geometria.
4. **Camada 3 — evidência/proveniência:** somente após caso de uso e formato compatível.
5. **Camada 4 — histórico:** somente após definir persistência e rollback.
6. **Camadas 5–7 — diagnóstico, projeto e as-built:** posteriores, condicionadas às anteriores.

## Próxima fase mínima

Executar uma homologação assistida no AutoCAD com cópias de DWGs representativos e registrar evidência para:

- abrir/recarregar a paleta;
- inserir postes e traçar vãos MT/BT;
- salvar, fechar, reabrir e sincronizar;
- COPY isolado/conjunto, MOVE, ERASE e Undo;
- DWG sem XData, legado e XData v2;
- WebView2, OSM e exportações realmente usadas.

DT-01 foi implementado como projeção semântica read-only e isolada, sem alterar o scanner, os contratos ou o DWG. XData v3, sidecar, banco, `ObjectModified` e sincronização bidirecional continuam fora do escopo.
