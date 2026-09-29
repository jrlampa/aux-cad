# REGRESSION MATRIX

Matriz de proteção para a evolução futura. **Testado** refere-se aos testes executados nesta fase; **runtime** não foi executado.

| Fluxo | Existe hoje | Uso operacional | Testado | Protegido | Risco |
|---|---|---|---|---|---|
| Abrir paleta por `MAPAPALETA` | Sim | Não confirmado | Estático/LISP | Sim | Alto |
| Mapa OSM e posicionamento | Sim | Não confirmado | Unitário/estático | Sim | Alto |
| Capturar ponto CAD | Sim | Não confirmado | Estático | Sim | Alto |
| Inserir poste | Sim | Não confirmado | Contrato/estático | Sim | Crítico |
| IDs e XData v2 | Sim | Não confirmado | Unitário/contrato | Sim | Crítico |
| Estruturas MT/BT e transformador | Sim | Não confirmado | Estático | Sim | Alto |
| Traçado contínuo | Sim | Não confirmado | Contrato/analítico/estático | Sim | Crítico |
| Vão MT/BT, metragem e texto | Sim | Não confirmado | Analítico/estático | Sim | Crítico |
| Scan e `estado_dwg` v2 | Sim | Não confirmado | Unitário/contrato | Sim | Crítico |
| Fallback legado `postes_dwg` | Sim | Não confirmado | Contrato | Sim | Alto |
| Reconstrução topológica | Sim | Não confirmado | Unitário/contrato | Sim | Crítico |
| COPY isolado/conjunto | Sim | Não confirmado | Unitário | Sim | Alto |
| MOVE nativo | Parcial; sem comando dedicado | Não confirmado | Não há runtime | Parcial | Alto |
| ERASE e vão órfão | Parcial | Não confirmado | Unitário | Sim | Alto |
| Undo por identidade | Sim | Não confirmado | Unitário/contrato | Sim | Crítico |
| OSM/contexto urbano | Sim | Não confirmado | Estático | Sim | Médio |
| Vias/calçadas/obstruções | Sim | Não confirmado | Estático | Sim | Médio |
| Restrições ambientais | Sim | Não confirmado | Estático | Sim | Médio |
| Medições | Sim | Não confirmado | Estático/analítico | Sim | Médio |
| Exportações CQT/KMZ | Sim | Não confirmado | Unitário em `mapa_postes` | Sim | Médio |
| Undo após fechar/reabrir | Não confirmado | Não confirmado | Não | Não | Alto |
| Compatibilidade com DWG sem XData | Sim, leitura defensiva | Não confirmado | Unitário | Sim | Alto |
| Compatibilidade com XData legado | Sim, leitura/diagnóstico | Não confirmado | Unitário | Sim | Alto |
| Runtime AutoCAD/WebView2 | Não validado nesta fase | Não confirmado | Não | Não | Crítico |

## Critério de aceite da próxima fase

Nenhuma mudança arquitetural será aceita sem:

1. preservar todos os fluxos marcados como Crítico;
2. executar testes offline e uma sessão assistida no AutoCAD;
3. abrir e escanear ao menos um DWG sem XData, um legado e um criado pelo fluxo atual;
4. validar COPY, MOVE, ERASE, salvar, fechar, reabrir, sincronizar e Undo;
5. registrar rollback e evidência, sem migração automática.
