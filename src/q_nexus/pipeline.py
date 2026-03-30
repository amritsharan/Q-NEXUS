from __future__ import annotations

from typing import Dict, List, Any

from .molecule_validator import evaluate_molecule


def evaluate_batch(molecules: List[Any]) -> List[Dict[str, object]]:
    """Evaluate a batch of molecule inputs.

    Each item may be:
    - a SMILES string
    - an InChI string (starts with 'InChI=')
    - a MolBlock / molfile text
    - a dict with keys: {'type': 'smiles'|'inchi'|'molblock', 'value': '...'}
    """
    return [evaluate_molecule(m) for m in molecules]
