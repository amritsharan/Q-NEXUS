from __future__ import annotations

from dataclasses import dataclass
import base64
import io
from typing import Dict, List, Optional, Tuple

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors, Draw
except Exception as exc:  # pragma: no cover - optional dependency
    Chem = None  # type: ignore
    Descriptors = None  # type: ignore
    rdMolDescriptors = None  # type: ignore
    Draw = None  # type: ignore
    _rdkit_import_error = exc
else:
    _rdkit_import_error = None

try:
    import z3
except Exception as exc:  # pragma: no cover - optional dependency
    z3 = None  # type: ignore
    _z3_import_error = exc
else:
    _z3_import_error = None

try:
    from qiskit.circuit.library import TwoLocal
    from qiskit.primitives import Estimator
    from qiskit.quantum_info import SparsePauliOp

    try:  # qiskit >= 1.0
        from qiskit_algorithms import VQE
        from qiskit_algorithms.optimizers import COBYLA
    except Exception:  # pragma: no cover - fallback for older qiskit
        from qiskit.algorithms import VQE  # type: ignore
        from qiskit.algorithms.optimizers import COBYLA  # type: ignore

except Exception as exc:  # pragma: no cover - optional dependency
    TwoLocal = None  # type: ignore
    Estimator = None  # type: ignore
    SparsePauliOp = None  # type: ignore
    VQE = None  # type: ignore
    COBYLA = None  # type: ignore
    _qiskit_import_error = exc
else:
    _qiskit_import_error = None

try:
    from qiskit_nature.second_q.drivers import PySCFDriver
    from qiskit_nature.second_q.mappers import JordanWignerMapper
    from qiskit_nature.second_q.problems import ElectronicStructureProblem
    from qiskit_nature.second_q.transformers import ActiveSpaceTransformer
    from qiskit_nature.second_q.algorithms import GroundStateEigensolver
    from qiskit_nature.second_q.circuit.library import HartreeFock, UCCSD
    from qiskit_nature.second_q.mappers import QubitConverter
except Exception as exc:  # pragma: no cover - optional dependency
    PySCFDriver = None  # type: ignore
    JordanWignerMapper = None  # type: ignore
    ElectronicStructureProblem = None  # type: ignore
    ActiveSpaceTransformer = None  # type: ignore
    GroundStateEigensolver = None  # type: ignore
    HartreeFock = None  # type: ignore
    UCCSD = None  # type: ignore
    QubitConverter = None  # type: ignore
    _qiskit_nature_import_error = exc
else:
    _qiskit_nature_import_error = None


MAX_VALENCE = {
    1: 1,   # H
    6: 4,   # C
    7: 3,   # N
    8: 2,   # O
    9: 1,   # F
    15: 5,  # P
    16: 6,  # S
    17: 1,  # Cl
    35: 1,  # Br
    53: 1,  # I
}

MAX_ATOMS_FOR_VQE = 30
ACTIVE_SPACE_ELECTRONS = 2
ACTIVE_SPACE_ORBITALS = 2
VQE_NATURE_MAXITER = 60


@dataclass
class ValidationResult:
    z3_pass: bool
    rdkit_pass: bool
    violations: List[str]
    metadata: Dict[str, float]


class DependencyError(RuntimeError):
    pass


def _require_rdkit() -> None:
    if Chem is None:
        raise DependencyError(
            "RDKit is required for validation. Install with `pip install rdkit-pypi`."
        ) from _rdkit_import_error


def _render_structure_png(mol_input) -> Optional[str]:
    if Chem is None or Draw is None:
        return None
    try:
        mol, _ = to_mol_and_canonical(mol_input)
        AllChem.Compute2DCoords(mol)
        image = Draw.MolToImage(mol, size=(300, 200))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return None


def _require_z3() -> None:
    if z3 is None:
        raise DependencyError(
            "Z3 is required for symbolic checks. Install with `pip install z3-solver`."
        ) from _z3_import_error


def _require_qiskit() -> None:
    if Estimator is None or VQE is None:
        raise DependencyError(
            "Qiskit is required for VQE stability. Install with `pip install qiskit qiskit-aer`."
        ) from _qiskit_import_error


def _require_qiskit_nature() -> None:
    if PySCFDriver is None or GroundStateEigensolver is None:
        raise DependencyError(
            "Qiskit Nature + PySCF required for general VQE. Install with `pip install qiskit-nature pyscf`."
        ) from _qiskit_nature_import_error


def to_mol_and_canonical(mol_input):
    """Convert a variety of molecule inputs to an RDKit Mol and canonical SMILES.

    Accepts:
    - RDKit Mol -> returns (mol, canonical_smiles)
    - dict like {'type': 'smiles'|'inchi'|'molblock', 'value': '...'}
    - string: autodetect InChI (starts with 'InChI='), molblock (contains 'M  END' or 'V2000'/'V3000'), else treat as SMILES
    """
    _require_rdkit()

    # If already an RDKit Mol
    if hasattr(mol_input, "GetNumAtoms"):
        Chem.SanitizeMol(mol_input)
        return mol_input, Chem.MolToSmiles(mol_input, isomericSmiles=True)

    # If a dict with explicit type
    if isinstance(mol_input, dict):
        typ = mol_input.get("type", "smiles").lower()
        val = mol_input.get("value")
    else:
        typ = None
        val = mol_input

    if not isinstance(val, str):
        raise ValueError("Molecule input must be a string, dict, or RDKit Mol")

    val_str = val.strip()

    # autodetect
    if typ is None:
        if val_str.startswith("InChI="):
            typ = "inchi"
        elif "M  END" in val_str or "V2000" in val_str or "V3000" in val_str:
            typ = "molblock"
        else:
            typ = "smiles"

    if typ == "smiles":
        mol = Chem.MolFromSmiles(val_str)
        if mol is None:
            raise ValueError("Invalid SMILES string")
    elif typ == "inchi":
        mol = Chem.MolFromInchi(val_str)
        if mol is None:
            raise ValueError("Invalid InChI string")
    elif typ in ("molblock", "molfile", "sdf"):
        mol = Chem.MolFromMolBlock(val_str, sanitize=False)
        if mol is None:
            # try sanitizing via MolFromMolBlock forgivingly
            raise ValueError("Invalid MolBlock/molfile text")
    else:
        raise ValueError(f"Unsupported molecule input type: {typ}")

    Chem.SanitizeMol(mol)
    return mol, Chem.MolToSmiles(mol, isomericSmiles=True)


def parse_smiles(smiles: str):
    """Backward-compatible wrapper that parses a SMILES string to an RDKit Mol."""
    mol, _ = to_mol_and_canonical(smiles)
    return mol


def z3_valence_check(mol) -> Tuple[bool, List[str]]:
    _require_z3()
    violations: List[str] = []

    solver = z3.Solver()
    for atom in mol.GetAtoms():
        atomic_num = atom.GetAtomicNum()
        max_valence = MAX_VALENCE.get(atomic_num, 4)
        valence = atom.GetTotalValence()
        charge = atom.GetFormalCharge()

        v = z3.Int(f"v_{atom.GetIdx()}")
        c = z3.Int(f"c_{atom.GetIdx()}")
        solver.add(v == valence)
        solver.add(c == charge)
        solver.add(v >= 0, v <= max_valence)
        solver.add(c >= -2, c <= 2)

        if valence > max_valence:
            violations.append(
                f"Atom {atom.GetIdx()} valence {valence} exceeds {max_valence}"
            )
        if abs(charge) > 2:
            violations.append(
                f"Atom {atom.GetIdx()} formal charge {charge} exceeds ±2"
            )

    z3_ok = solver.check() == z3.sat
    return z3_ok and not violations, violations


def rdkit_checks(mol) -> Tuple[bool, List[str], Dict[str, float]]:
    _require_rdkit()
    violations: List[str] = []

    rings = rdMolDescriptors.CalcNumRings(mol)
    heavy_atoms = rdMolDescriptors.CalcNumHeavyAtoms(mol)
    mol_wt = Descriptors.MolWt(mol)

    if rings > 8:
        violations.append("Ring count unusually high (>8)")

    if heavy_atoms > 60:
        violations.append("Heavy atom count too large for prototype")

    if mol_wt > 800:
        violations.append("Molecular weight too high for prototype")

    metadata = {
        "rings": float(rings),
        "heavy_atoms": float(heavy_atoms),
        "mol_wt": float(mol_wt),
    }

    return len(violations) == 0, violations, metadata


def validate_molecule(mol_input) -> ValidationResult:
    mol, _ = to_mol_and_canonical(mol_input)
    z3_pass, z3_violations = z3_valence_check(mol)
    rdkit_pass, rdkit_violations, metadata = rdkit_checks(mol)

    return ValidationResult(
        z3_pass=z3_pass,
        rdkit_pass=rdkit_pass,
        violations=z3_violations + rdkit_violations,
        metadata=metadata,
    )


def validate_smiles(smiles: str) -> ValidationResult:
    """Deprecated name kept for backward compatibility."""
    return validate_molecule(smiles)


def _classical_energy(mol_input) -> Dict[str, Optional[float]]:
    _require_rdkit()
    mol, _ = to_mol_and_canonical(mol_input)

    mol = Chem.AddHs(mol)
    if AllChem.EmbedMolecule(mol, randomSeed=42) != 0:
        return {"energy_kcal_mol": None, "energy_ev": None, "method": "embed_failed"}

    try:
        if AllChem.MMFFHasAllMoleculeParams(mol):
            props = AllChem.MMFFGetMoleculeProperties(mol)
            ff = AllChem.MMFFGetMoleculeForceField(mol, props)
            energy = float(ff.CalcEnergy())
            return {
                "energy_kcal_mol": energy,
                "energy_ev": energy / 23.0605,
                "method": "mmff94",
            }
    except Exception:
        pass

    try:
        ff = AllChem.UFFGetMoleculeForceField(mol)
        energy = float(ff.CalcEnergy())
        return {
            "energy_kcal_mol": energy,
            "energy_ev": energy / 23.0605,
            "method": "uff",
        }
    except Exception:
        return {"energy_kcal_mol": None, "energy_ev": None, "method": "forcefield_failed"}


def _qiskit_nature_energy(mol_input) -> Dict[str, Optional[float]]:
    _require_rdkit()
    _require_qiskit_nature()

    mol, _ = to_mol_and_canonical(mol_input)
    atom_count = mol.GetNumAtoms()
    if atom_count > MAX_ATOMS_FOR_VQE:
        return {"energy_ev": None, "method": "unsupported_size"}

    mol = Chem.AddHs(mol)
    if AllChem.EmbedMolecule(mol, randomSeed=42) != 0:
        return {"energy_ev": None, "method": "embed_failed"}

    conf = mol.GetConformer()
    symbols = [atom.GetSymbol() for atom in mol.GetAtoms()]
    coords = [conf.GetAtomPosition(i) for i in range(mol.GetNumAtoms())]
    geometry = [
        (symbols[i], [coords[i].x, coords[i].y, coords[i].z])
        for i in range(mol.GetNumAtoms())
    ]

    try:
        driver = PySCFDriver(atom=geometry, basis="sto3g", charge=0, spin=0)
        problem = ElectronicStructureProblem(driver)

        # Keep small active space to control runtime
        transformer = ActiveSpaceTransformer(
            num_electrons=ACTIVE_SPACE_ELECTRONS,
            num_spatial_orbitals=ACTIVE_SPACE_ORBITALS,
        )
        problem = transformer.transform(problem)

        mapper = JordanWignerMapper()
        converter = QubitConverter(mapper=mapper)

        second_q_ops = problem.second_q_ops()
        main_op = second_q_ops[0]
        num_particles = problem.num_particles
        num_spatial_orbitals = problem.num_spatial_orbitals

        initial_state = HartreeFock(num_spatial_orbitals, num_particles, converter)
        ansatz = UCCSD(num_spatial_orbitals, num_particles, converter, initial_state=initial_state)

        _require_qiskit()
        optimizer = COBYLA(maxiter=VQE_NATURE_MAXITER)
        estimator = Estimator()
        vqe_solver = VQE(estimator, ansatz, optimizer)

        gsc = GroundStateEigensolver(converter, vqe_solver)
        result = gsc.solve(problem)

        energy_hartree = float(result.total_energies[0].real)
        energy_ev = energy_hartree * 27.2114
        method = (
            f"vqe_nature_as_{ACTIVE_SPACE_ELECTRONS}e_{ACTIVE_SPACE_ORBITALS}o"
        )
        return {"energy_ev": energy_ev, "method": method}
    except Exception:
        return {"energy_ev": None, "method": "vqe_failed"}


def qiskit_stability(mol_input) -> Dict[str, Optional[float]]:
    """
    VQE stability proxy for toy molecules.
    Currently supports H2 with a fixed Hamiltonian; returns unsupported otherwise.
    """
    _require_rdkit()
    mol, _ = to_mol_and_canonical(mol_input)

    atoms = [atom.GetAtomicNum() for atom in mol.GetAtoms()]
    is_h2 = len(atoms) == 2 and all(a == 1 for a in atoms)

    try:
        if is_h2:
            _require_qiskit()

            # H2 Hamiltonian at ~0.735 Å (in Hartree)
            h2_op = SparsePauliOp.from_list(
                [
                    ("II", -0.810547980537326),
                    ("ZI", 0.17218393261915543),
                    ("IZ", 0.17218393261915543),
                    ("ZZ", -0.22575349222402472),
                    ("XX", 0.1209126326177663),
                ]
            )

            ansatz = TwoLocal(2, ["ry", "rz"], "cz", reps=2, entanglement="full")
            optimizer = COBYLA(maxiter=200)
            estimator = Estimator()
            vqe = VQE(estimator, ansatz, optimizer)
            result = vqe.compute_minimum_eigenvalue(h2_op)
            energy_hartree = float(result.eigenvalue.real)
            energy_ev = energy_hartree * 27.2114
            stable = energy_hartree < -1.0
            return {
                "energy_ev": energy_ev,
                "stable": stable,
                "method": "vqe_h2",
            }

        nature_result = _qiskit_nature_energy(smiles)
        if nature_result["energy_ev"] is not None:
            stable = nature_result["energy_ev"] < -1.0
            return {
                "energy_ev": nature_result["energy_ev"],
                "stable": stable,
                "method": nature_result["method"],
            }

        return {"energy_ev": None, "stable": None, "method": nature_result["method"]}
    except Exception:
        return {"energy_ev": None, "stable": None, "method": "unavailable"}


def evaluate_molecule(mol_input) -> Dict[str, object]:
    """Evaluate a molecule input (string, dict, or RDKit Mol) and return results.

    Returned dict keeps the `smiles` key as canonical SMILES when possible.
    """
    # validate and compute energies from the mol_input
    validation = validate_molecule(mol_input)
    qiskit_result = qiskit_stability(mol_input)
    classical = _classical_energy(mol_input)
    structure_png = _render_structure_png(mol_input)

    classical_threshold = 50.0
    classical_ok = (
        classical["energy_kcal_mol"] is not None
        and classical["energy_kcal_mol"] < classical_threshold
    )

    passed = validation.z3_pass and validation.rdkit_pass and (
        qiskit_result["stable"] is True or (qiskit_result["stable"] is None and classical_ok)
    )

    reasons: List[str] = []
    if validation.z3_pass:
        reasons.append("Z3 constraints satisfied (valence/charge)")
    if validation.rdkit_pass:
        reasons.append("RDKit structural checks passed")
    if qiskit_result["stable"] is True:
        reasons.append("VQE/heuristic stability threshold met")
    elif qiskit_result["stable"] is None:
        reasons.append("Quantum stability not computed; classical energy used")

    if classical["energy_kcal_mol"] is not None:
        reasons.append(f"Classical energy computed ({classical['method']})")
        reasons.append(f"Classical threshold: < {classical_threshold} kcal/mol")

    if not passed and not validation.violations and qiskit_result["stable"] is False:
        reasons.append("Failed due to stability threshold")

    verdict = "PASS" if passed else "FAIL"

    # canonical smiles where available
    try:
        _, canonical = to_mol_and_canonical(mol_input)
    except Exception:
        canonical = None

    return {
        "smiles": canonical,
        "z3_pass": validation.z3_pass,
        "rdkit_pass": validation.rdkit_pass,
        "energy_ev": qiskit_result["energy_ev"],
        "energy_kcal_mol": classical["energy_kcal_mol"],
        "stable": qiskit_result["stable"],
        "method": qiskit_result["method"],
        "classical_method": classical["method"],
        "structure_png": structure_png,
        "violations": validation.violations,
        "reasons": reasons,
        "metadata": validation.metadata,
        "verdict": verdict,
    }


def evaluate_smiles(smiles: str) -> Dict[str, object]:
    """Deprecated wrapper kept for compatibility with older callers."""
    return evaluate_molecule(smiles)
