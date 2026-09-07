import os
import sys

# Injeta a raiz do projeto e as pastas de módulos no sys.path para garantir resolução universal
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)

for path in [ROOT_DIR, os.path.join(ROOT_DIR, "cqt"), os.path.join(ROOT_DIR, "ambiental")]:
    if path not in sys.path:
        sys.path.insert(0, path)
