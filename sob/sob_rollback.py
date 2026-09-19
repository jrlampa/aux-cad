"""
Módulo de Rollback Seguro da Fase B (Seção 18).

Garante que qualquer falha durante ou após o início da Fase B realize o desfazimento
atômico e seguro exclusivamente dos recursos criados pela execução atual,
protegendo dados preexistentes e o arquivo-modelo BASE_TEMPLATE com proteção absoluta.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger("SOB.Rollback")


@dataclass
class RecursoRastreado:
    """
    Representa o estado e posse de um recurso no sistema de arquivos (Seção 18.3).
    """
    nome: str
    caminho: Path
    tipo: str  # 'dir' ou 'file'
    estado_antes: str  # 'NÃO_EXISTIA' ou 'EXISTIA'
    criado_nesta_execucao: bool = False
    acao_executada: Optional[str] = None
    estado_depois: Optional[str] = None


@dataclass
class RecursoRemanescente:
    """
    Detalhe de um recurso que não pôde ser removido pelo rollback (Seção 18.12).
    """
    caminho: str
    motivo: str
    acao_necessaria: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "caminho": self.caminho,
            "motivo": self.motivo,
            "acao_necessaria": self.acao_necessaria,
        }


class RollbackContext:
    """
    Gerenciador de contexto para rastreamento e rollback seguro da Fase B (Seção 18).
    """

    def __init__(
        self,
        sob_id: str,
        destination_root: Union[str, Path],
        sob_root: Union[str, Path],
        croqui_dir: Union[str, Path],
        base_dwg: Union[str, Path],
        base_template: Union[str, Path],
        logger_instance: Optional[logging.Logger] = None,
    ):
        self.sob_id = sob_id
        self.destination_root = Path(destination_root).resolve()
        self.sob_root = Path(sob_root).resolve()
        self.croqui_dir = Path(croqui_dir).resolve()
        self.base_dwg = Path(base_dwg).resolve()
        self.base_template = Path(base_template).resolve()
        self.logger = logger_instance or logger

        self.recursos: Dict[str, RecursoRastreado] = {}
        self.download_created_files: List[Path] = []
        self.dwg_aberto_no_autocad: bool = False

        self.etapa_falha: Optional[str] = None
        self.motivo_falha: Optional[str] = None
        self.estado_rollback: str = "ROLLBACK_NÃO_NECESSÁRIO"

        self.recursos_removidos: List[str] = []
        self.recursos_preservados: List[str] = []
        self.recursos_remanescentes: List[RecursoRemanescente] = []

    def inicializar_fase_b(self) -> None:
        """
        Registra internamente o estado inicial dos recursos antes de iniciar a Fase B (Seção 18.2).
        """
        self.recursos["SOB_ROOT"] = RecursoRastreado(
            nome="SOB_ROOT",
            caminho=self.sob_root,
            tipo="dir",
            estado_antes="EXISTIA" if self.sob_root.exists() else "NÃO_EXISTIA",
        )
        self.recursos["CROQUI_DIR"] = RecursoRastreado(
            nome="CROQUI_DIR",
            caminho=self.croqui_dir,
            tipo="dir",
            estado_antes="EXISTIA" if self.croqui_dir.exists() else "NÃO_EXISTIA",
        )
        self.recursos["BASE_DWG"] = RecursoRastreado(
            nome="BASE_DWG",
            caminho=self.base_dwg,
            tipo="file",
            estado_antes="EXISTIA" if self.base_dwg.exists() else "NÃO_EXISTIA",
        )
        self.recursos["BASE_TEMPLATE"] = RecursoRastreado(
            nome="BASE_TEMPLATE",
            caminho=self.base_template,
            tipo="file",
            estado_antes="EXISTIA" if self.base_template.exists() else "NÃO_EXISTIA",
        )

    def registrar_criacao(self, nome_recurso: str, caminho: Path, tipo: str = "dir") -> None:
        """
        Registra a criação de um recurso durante a Fase B (Seção 18.3).
        """
        p = Path(caminho).resolve()
        if nome_recurso in self.recursos:
            rec = self.recursos[nome_recurso]
            rec.criado_nesta_execucao = True
            rec.acao_executada = "criação"
            rec.estado_depois = "existente"
        else:
            self.recursos[nome_recurso] = RecursoRastreado(
                nome=nome_recurso,
                caminho=p,
                tipo=tipo,
                estado_antes="NÃO_EXISTIA",
                criado_nesta_execucao=True,
                acao_executada="criação",
                estado_depois="existente",
            )

    def registrar_download_arquivo(self, arquivo_path: Union[str, Path]) -> None:
        """
        Registra um arquivo físico criado durante o download do SharePoint (Seção 18.9).
        """
        p = Path(arquivo_path).resolve()
        if p not in self.download_created_files:
            self.download_created_files.append(p)

    def marcar_dwg_aberto(self) -> None:
        """
        Registra que o BASE_DWG foi aberto no AutoCAD (Seção 18.11).
        """
        self.dwg_aberto_no_autocad = True

    def houve_alteracao_em_disco(self) -> bool:
        """
        Verifica se algum recurso foi efetivamente criado no disco pela execução atual.
        """
        criados = any(r.criado_nesta_execucao for r in self.recursos.values())
        return criados or len(self.download_created_files) > 0

    def executar_rollback(
        self,
        etapa_falha: str,
        motivo_falha: str,
        fechador_cad_callback: Optional[Callable[[Path], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Executa o rollback seguro em ordem inversa (Seção 18.10).
        """
        self.etapa_falha = etapa_falha
        self.motivo_falha = motivo_falha

        if not self.houve_alteracao_em_disco():
            self.estado_rollback = "ROLLBACK_NÃO_NECESSÁRIO"
            self.logger.info("Rollback não necessário: nenhuma alteração em disco realizada.")
            return self.obter_relatorio()

        self.estado_rollback = "ROLLBACK_INICIADO"
        self.logger.warning(f"Iniciando rollback seguro da Fase B (Falha na etapa: {etapa_falha})...")

        # 1. PASSO 1: Fechar / desassociar BASE_DWG do AutoCAD se necessário (18.11)
        cad_fechado_ou_nao_aberto = True
        if self.dwg_aberto_no_autocad:
            if fechador_cad_callback:
                try:
                    sucesso_fechar = fechador_cad_callback(self.base_dwg)
                    if not sucesso_fechar:
                        cad_fechado_ou_nao_aberto = False
                except Exception as e:
                    self.logger.warning(f"Falha ao tentar fechar DWG no AutoCAD: {e}")
                    cad_fechado_ou_nao_aberto = False
            else:
                cad_fechado_ou_nao_aberto = False

        # 2. PASSO 2: Remover BASE_DWG criado pela execução (18.7)
        rec_base = self.recursos.get("BASE_DWG")
        if rec_base and rec_base.criado_nesta_execucao and self.base_dwg.exists():
            # Proteção absoluta de BASE_TEMPLATE (18.8 e 18.16)
            if self.base_dwg.resolve() == self.base_template.resolve():
                self.logger.critical("[FALHA CRÍTICA] Tentativa de remover BASE_TEMPLATE abortada.")
                self.recursos_preservados.append(str(self.base_template))
            elif not cad_fechado_ou_nao_aberto:
                self.recursos_remanescentes.append(
                    RecursoRemanescente(
                        caminho=str(self.base_dwg),
                        motivo="Arquivo ainda pode estar em uso pelo AutoCAD.",
                        acao_necessaria="Fechar o arquivo no AutoCAD antes de removê-lo.",
                    )
                )
            else:
                try:
                    self.base_dwg.unlink()
                    if not self.base_dwg.exists():
                        self.recursos_removidos.append(str(self.base_dwg))
                        self.logger.info(f"BASE_DWG removido pelo rollback: {self.base_dwg}")
                    else:
                        self.recursos_remanescentes.append(
                            RecursoRemanescente(
                                caminho=str(self.base_dwg),
                                motivo="Não foi possível excluir o arquivo (permissão ou em uso).",
                                acao_necessaria="Remover manualmente após liberar processos.",
                            )
                        )
                except Exception as e:
                    self.recursos_remanescentes.append(
                        RecursoRemanescente(
                            caminho=str(self.base_dwg),
                            motivo=f"Erro ao remover arquivo: {e}",
                            acao_necessaria="Verificar permissões e remover manualmente.",
                        )
                    )

        # 3. PASSO 3: Remover arquivos baixados pela execução (18.5 & 18.9)
        for arq in reversed(self.download_created_files):
            if arq.exists():
                # Limite de segurança: deve estar estritamente dentro de SOB_ROOT (18.17)
                try:
                    arq.resolve().relative_to(self.sob_root.resolve())
                except ValueError:
                    self.logger.warning(f"Arquivo fora de SOB_ROOT ignorado por segurança: {arq}")
                    self.recursos_preservados.append(str(arq))
                    continue

                try:
                    arq.unlink()
                    if not arq.exists():
                        self.recursos_removidos.append(str(arq))
                    else:
                        self.recursos_remanescentes.append(
                            RecursoRemanescente(
                                caminho=str(arq),
                                motivo="Arquivo não pôde ser removido.",
                                acao_necessaria="Verificar permissão e remover manualmente.",
                            )
                        )
                except Exception as e:
                    self.recursos_remanescentes.append(
                        RecursoRemanescente(
                            caminho=str(arq),
                            motivo=f"Erro ao remover arquivo baixado: {e}",
                            acao_necessaria="Remover manualmente.",
                        )
                    )

        # 4. PASSO 4: Remover CROQUI_DIR se vazio e criado pela execução (18.5 & 18.6)
        rec_croqui = self.recursos.get("CROQUI_DIR")
        if rec_croqui and rec_croqui.criado_nesta_execucao and self.croqui_dir.exists():
            itens_croqui = list(self.croqui_dir.iterdir())
            if not itens_croqui:
                try:
                    self.croqui_dir.rmdir()
                    if not self.croqui_dir.exists():
                        self.recursos_removidos.append(str(self.croqui_dir))
                        self.logger.info(f"CROQUI_DIR vazio removido: {self.croqui_dir}")
                    else:
                        self.recursos_remanescentes.append(
                            RecursoRemanescente(
                                caminho=str(self.croqui_dir),
                                motivo="Não foi possível remover diretório CROQUI_DIR.",
                                acao_necessaria="Remover diretório manualmente.",
                            )
                        )
                except Exception as e:
                    self.recursos_remanescentes.append(
                        RecursoRemanescente(
                            caminho=str(self.croqui_dir),
                            motivo=f"Erro ao remover CROQUI_DIR: {e}",
                            acao_necessaria="Remover diretório manualmente.",
                        )
                    )
            else:
                self.logger.warning(f"CROQUI_DIR contém {len(itens_croqui)} item(ns) preservado(s); mantido.")
                self.recursos_preservados.append(str(self.croqui_dir))

        # 5. PASSO 5: Remover SOB_ROOT se vazio e criado pela execução (18.4)
        rec_sob = self.recursos.get("SOB_ROOT")
        if rec_sob and rec_sob.criado_nesta_execucao and self.sob_root.exists():
            manifesto = self.sob_root / ".sob_state.json"
            manifesto_tmp = self.sob_root / ".sob_state.json.tmp"
            itens_sob = [item for item in self.sob_root.iterdir() if item.name not in (".sob_state.json", ".sob_state.json.tmp")]

            if not itens_sob:
                # Remove arquivos de manifesto da própria execução para liberar a remoção do diretório
                for m in (manifesto, manifesto_tmp):
                    if m.exists():
                        try:
                            m.unlink()
                            self.recursos_removidos.append(str(m))
                        except Exception:
                            pass
                try:
                    self.sob_root.rmdir()
                    if not self.sob_root.exists():
                        self.recursos_removidos.append(str(self.sob_root))
                        self.logger.info(f"SOB_ROOT vazio removido: {self.sob_root}")
                    else:
                        self.recursos_remanescentes.append(
                            RecursoRemanescente(
                                caminho=str(self.sob_root),
                                motivo="Não foi possível remover diretório SOB_ROOT.",
                                acao_necessaria="Remover diretório manualmente.",
                            )
                        )
                except Exception as e:
                    self.recursos_remanescentes.append(
                        RecursoRemanescente(
                            caminho=str(self.sob_root),
                            motivo=f"Erro ao remover SOB_ROOT: {e}",
                            acao_necessaria="Remover diretório manualmente.",
                        )
                    )
            else:
                self.logger.warning(f"SOB_ROOT contém {len(itens_sob)} item(ns) preservado(s); mantido.")
                self.recursos_preservados.append(str(self.sob_root))

        # 6. PASSO 6: Validação pós-rollback (18.18)
        if self.base_template.exists():
            if str(self.base_template) not in self.recursos_preservados:
                self.recursos_preservados.append(str(self.base_template))

        if self.recursos_remanescentes:
            self.estado_rollback = "ROLLBACK_PARCIAL"
            self.logger.warning(f"Rollback parcial: {len(self.recursos_remanescentes)} recurso(s) remanescente(s).")
        else:
            self.estado_rollback = "ROLLBACK_CONCLUÍDO"
            self.logger.info("Rollback seguro concluído com sucesso.")

        return self.obter_relatorio()

    def obter_relatorio(self) -> Dict[str, Any]:
        """
        Gera o dicionário de registro estruturado conforme Seção 18.19.
        """
        recursos_criados = [
            str(r.caminho) for r in self.recursos.values() if r.criado_nesta_execucao
        ] + [str(p) for p in self.download_created_files]

        return {
            "sob_id": self.sob_id,
            "etapa_da_falha": self.etapa_falha,
            "motivo_da_falha": self.motivo_falha,
            "rollback_iniciado": self.estado_rollback in ("ROLLBACK_INICIADO", "ROLLBACK_CONCLUÍDO", "ROLLBACK_PARCIAL"),
            "recursos_criados_pela_execucao": list(dict.fromkeys(recursos_criados)),
            "recursos_removidos": list(dict.fromkeys(self.recursos_removidos)),
            "recursos_preservados": list(dict.fromkeys(self.recursos_preservados)),
            "recursos_remanescentes": [r.to_dict() for r in self.recursos_remanescentes],
            "resultado_do_rollback": self.estado_rollback,
        }
