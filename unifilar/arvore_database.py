# -*- coding: utf-8 -*-
"""
Módulo de Banco de Dados Local e Cache da Árvore de Dispositivos.
Responsabilidade única: Persistência e busca indexada em SQLite a partir
da planilha oficial 'documentos/Árvore de Dispositivos.xlsx'.
"""

import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, Optional

from arvore_parser import (
    ResultadoProtecao,
    localizar_protecao_a_montante,
)


def get_base_dir() -> Path:
    """Retorna a pasta raiz do projeto aux cad."""
    return Path(__file__).resolve().parent.parent


def get_db_path() -> Path:
    """Retorna o caminho do banco SQLite local de cache."""
    return Path(__file__).resolve().parent / "arvore_cache.sqlite3"


def get_excel_default_path() -> Path:
    """Retorna o caminho padrão da planilha oficial de dispositivos."""
    return get_base_dir() / "documentos" / "Árvore de Dispositivos.xlsx"


class ArvoreDatabase:
    """Gerenciador de busca e persistência local da árvore de dispositivos."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Cria as tabelas e índices caso não existam."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS arvore_dispositivos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    indice INTEGER,
                    ingr_alim TEXT,
                    cliente_vital INTEGER,
                    dispositivo TEXT,
                    arvore TEXT,
                    descricao_tipo TEXT,
                    total_clientes INTEGER,
                    total_potencia REAL
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_disp ON arvore_dispositivos(dispositivo)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_alim ON arvore_dispositivos(ingr_alim)"
            )
            conn.commit()

    def total_registros(self) -> int:
        """Retorna o total de registros armazenados no banco SQLite."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM arvore_dispositivos")
            row = cursor.fetchone()
            return row[0] if row else 0

    def sincronizar_de_planilha(self, excel_path: Optional[Path] = None) -> int:
        """
        Lê a planilha oficial via openpyxl (modo read_only) e indexa no SQLite.
        Retorna a quantidade de registros importados.
        """
        import openpyxl

        caminho_xlsx = excel_path or get_excel_default_path()
        if not caminho_xlsx.exists():
            raise FileNotFoundError(f"Planilha não encontrada: {caminho_xlsx}")

        wb = openpyxl.load_workbook(str(caminho_xlsx), read_only=True, data_only=True)
        ws = wb.active

        registros = []
        # Cabeçalho esperado:
        # 0: INDICE, 1: INGR_ALIM, 2: CLIENTE_VITAL, 3: DISPOSITIVO,
        # 4: ARVORE, 5: DESCRICAO_TIPO, 6: TOTAL_CLIENTES, 7: TOTAL_POTENCIA
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                continue  # Pula cabeçalho
            if not row or len(row) < 5:
                continue

            disp = str(row[3] or "").strip()
            if not disp:
                continue

            indice = int(row[0]) if row[0] is not None and str(row[0]).isdigit() else 0
            ingr_alim = str(row[1] or "").strip()
            cliente_vital = int(row[2]) if row[2] is not None and str(row[2]).isdigit() else 0
            arvore = str(row[4] or "").strip()
            desc_tipo = str(row[5] or "").strip() if len(row) > 5 else ""

            try:
                tot_cli = int(row[6]) if len(row) > 6 and row[6] is not None else 0
            except (ValueError, TypeError):
                tot_cli = 0

            try:
                tot_pot = float(row[7]) if len(row) > 7 and row[7] is not None else 0.0
            except (ValueError, TypeError):
                tot_pot = 0.0

            registros.append((
                indice,
                ingr_alim,
                cliente_vital,
                disp,
                arvore,
                desc_tipo,
                tot_cli,
                tot_pot,
            ))

        wb.close()

        # Inserção atômica em lote no SQLite
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM arvore_dispositivos")
            cursor.executemany(
                """
                INSERT INTO arvore_dispositivos (
                    indice, ingr_alim, cliente_vital, dispositivo,
                    arvore, descricao_tipo, total_clientes, total_potencia
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                registros,
            )
            conn.commit()

        return len(registros)

    def buscar_dispositivo(self, codigo: str) -> Optional[Dict[str, Any]]:
        """
        Busca um dispositivo pelo código no banco SQLite.
        Se o banco estiver vazio, tenta sincronizar automaticamente da planilha padrão.
        """
        if self.total_registros() == 0 and get_excel_default_path().exists():
            self.sincronizar_de_planilha()

        cod_limpo = codigo.strip().upper()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Busca exata
            cursor.execute(
                "SELECT * FROM arvore_dispositivos WHERE UPPER(dispositivo) = ? LIMIT 1",
                (cod_limpo,),
            )
            row = cursor.fetchone()

            # Se não achou exato, tenta por LIKE no código ou na árvore
            if not row:
                cursor.execute(
                    "SELECT * FROM arvore_dispositivos WHERE UPPER(dispositivo) LIKE ? LIMIT 1",
                    (f"%{cod_limpo}%",),
                )
                row = cursor.fetchone()

            if not row:
                cursor.execute(
                    "SELECT * FROM arvore_dispositivos WHERE UPPER(arvore) LIKE ? LIMIT 1",
                    (f"%{cod_limpo}%",),
                )
                row = cursor.fetchone()

            if row:
                return dict(row)
            return None

    def consultar_protecao_dispositivo(self, codigo: str) -> ResultadoProtecao:
        """
        Localiza o dispositivo no banco e resolve sua proteção a montante,
        enriquecendo com os dados consolidados da proteção.
        """
        dado = self.buscar_dispositivo(codigo)
        if not dado:
            return ResultadoProtecao(
                sucesso=False,
                ponto_alvo=codigo,
                subestacao="",
                alimentador="",
                protecao_tipo="",
                protecao_codigo="",
                protecao_rotulo="",
                mensagem=f"Dispositivo '{codigo}' não encontrado na base de dados.",
            )

        caminho = dado.get("arvore", "")
        resultado = localizar_protecao_a_montante(caminho, codigo)

        # Se encontrou a proteção, tenta buscar o registro específico dela no banco
        # para obter clientes e potência consolidados
        if resultado.sucesso and resultado.protecao_codigo:
            prot_dados = self.buscar_dispositivo(resultado.protecao_codigo)
            if prot_dados:
                tot_cli = prot_dados.get("total_clientes", 0)
                tot_pot = prot_dados.get("total_potencia", 0.0)

                # Se a proteção tiver total_clientes e o resultado anterior for 0, atualiza
                if resultado.clientes_b == 0 and tot_cli > 0:
                    resultado.clientes_b = tot_cli
                if resultado.kva == 0.0 and tot_pot > 0.0:
                    resultado.kva = float(tot_pot)

        return resultado
