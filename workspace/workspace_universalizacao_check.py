"""Explicit external integration check; never invoked by offline pytest."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import warnings
from dataclasses import asdict

from workspace.workspace_universalizacao_client import (
    UniversalizacaoClient,
    UniversalizacaoConfig,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Integracao externa Universalizacao; uma tentativa HTTP."
    )
    parser.add_argument("--external-integration", action="store_true",
                        required=True)
    parser.add_argument("--env-credentials", action="store_true")
    args = parser.parse_args()
    print("INTEGRACAO EXTERNA: uma tentativa, sem persistir credenciais.",
          flush=True)
    if args.env_credentials:
        username = os.environ.get("UNIVERSALIZACAO_NTLM_USERNAME")
        password = os.environ.get("UNIVERSALIZACAO_NTLM_PASSWORD")
    else:
        if not sys.stdin.isatty() or not sys.stderr.isatty():
            print("Terminal interativo seguro necessario.", flush=True)
            return 2
        try:
            username = input("Usu\u00e1rio: ").strip()
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                password = getpass.getpass("Senha: ")
        except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
            print("Entrada cancelada ou terminal inseguro.", flush=True)
            return 2
    try:
        result = UniversalizacaoClient(UniversalizacaoConfig()).get_home(
            username, password
        )
    finally:
        username = password = None
    print(json.dumps(asdict(result), ensure_ascii=True), flush=True)
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
