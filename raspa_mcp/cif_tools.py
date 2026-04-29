"""
raspa_mcp.cif_tools — structural sanity checks for user-supplied CIF files.

Uses ASE for parsing because RASPA2 itself is unforgiving: it will start a long
simulation against a CIF whose unit cell is too small for the requested cutoff,
or whose charges sum to a non-zero value, and only complain (or silently
produce nonsense) much later.

These tools surface the common pitfalls *before* the simulation starts:

* Cell parameters: each axis must satisfy ``a >= 2 * CutOff`` (RASPA2 rule);
  if not, recommend a supercell.
* Atomic charges: if a ``_atom_site_charge`` (or similar) column is present,
  warn when it is not present at all, sums far from zero, or all zero.
* Atom-atom overlap: if any pair of atoms is closer than 0.5 Å, RASPA2 will
  blow up almost immediately — flag that as a hard error.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import math


def _read_atoms(cif_path: str):
    from ase.io import read  # local import to keep top-level cheap

    return read(cif_path)


def inspect_cif(cif_path: str) -> dict[str, Any]:
    """Inspect a CIF file and report structural sanity information.

    Returned keys:

    * ``status`` — ``"ok"`` or ``"error"``
    * ``formula`` — chemical formula
    * ``n_atoms`` — atom count in the conventional cell
    * ``cell`` — ``{"a", "b", "c", "alpha", "beta", "gamma", "volume"}``
    * ``charges`` — ``{"present": bool, "sum": float | None, "all_zero": bool}``
    * ``min_distance_A`` — minimum interatomic distance (PBC respected)
    * ``warnings`` — list of strings (overlap, missing charges, ...)
    """
    try:
        atoms = _read_atoms(cif_path)
    except FileNotFoundError:
        return {"status": "error", "message": f"CIF not found: {cif_path}"}
    except Exception as e:  # ase raises a wide variety
        return {
            "status": "error",
            "message": f"ASE failed to read CIF: {e}",
            "type": type(e).__name__,
        }

    cell = atoms.get_cell()
    a, b, c, alpha, beta, gamma = cell.cellpar()
    volume = float(cell.volume)

    warnings: list[str] = []

    # Charges
    initial_charges = atoms.get_initial_charges()
    has_charges = bool(getattr(initial_charges, "any", lambda: False)())
    charge_sum: float | None = float(initial_charges.sum()) if has_charges else None
    all_zero = (charge_sum == 0.0) if has_charges else True
    if not has_charges:
        warnings.append(
            "No atomic charges found in CIF. Set ChargeMethod=None or compute "
            "charges first (e.g. via DDEC6 / EQeq). Without charges, "
            "UseChargesFromCIFFile=yes is meaningless."
        )
    elif charge_sum is not None and abs(charge_sum) > 1e-3:
        warnings.append(
            f"Sum of CIF charges = {charge_sum:+.4f} e (should be ~0). "
            "RASPA2 Ewald summation assumes a neutral cell."
        )

    # Minimum interatomic distance (PBC).
    min_d: float | None = None
    n = len(atoms)
    if n >= 2:
        # all_distances is O(N^2); fine for typical MOF unit cells (<5000 atoms).
        d = atoms.get_all_distances(mic=True)
        # Mask diagonal
        for i in range(n):
            d[i, i] = math.inf
        min_d = float(d.min())
        if min_d < 0.5:
            warnings.append(
                f"Minimum interatomic distance {min_d:.3f} Å < 0.5 Å. "
                "Atoms are essentially overlapping — RASPA2 will fail. "
                "Check the CIF for duplicate atoms or wrong fractional coords."
            )

    return {
        "status": "ok",
        "formula": atoms.get_chemical_formula(),
        "n_atoms": n,
        "cell": {
            "a": float(a),
            "b": float(b),
            "c": float(c),
            "alpha": float(alpha),
            "beta": float(beta),
            "gamma": float(gamma),
            "volume": volume,
        },
        "charges": {
            "present": has_charges,
            "sum": charge_sum,
            "all_zero": all_zero,
        },
        "min_distance_A": min_d,
        "warnings": warnings,
    }


def recommend_supercell(cif_path: str, cutoff_A: float = 12.0) -> dict[str, Any]:
    """Recommend an integer supercell ``(nx, ny, nz)`` such that each axis is
    at least ``2 * cutoff_A``.

    This is the RASPA2 minimum-image rule. Without it the simulation will
    error out with ``MakeWignerSeitzCell`` or produce wrong energies.
    """
    info = inspect_cif(cif_path)
    if info.get("status") != "ok":
        return info

    cell = info["cell"]
    needed = 2.0 * cutoff_A
    # Use perpendicular widths (a*sin(beta_eff)) for non-orthogonal cells —
    # for now use the cell-edge length as a conservative proxy.
    nx = max(1, int(math.ceil(needed / cell["a"])))
    ny = max(1, int(math.ceil(needed / cell["b"])))
    nz = max(1, int(math.ceil(needed / cell["c"])))

    use_charge_method = "Ewald"
    if info["charges"]["all_zero"]:
        use_charge_method = "None"

    return {
        "status": "ok",
        "cutoff_A": cutoff_A,
        "min_axis_length_A": needed,
        "supercell": [nx, ny, nz],
        "raspa_input_line": f"UnitCells {nx} {ny} {nz}",
        "recommended_charge_method": use_charge_method,
        "rationale": (
            f"Each axis must be ≥ {needed:.1f} Å (= 2 × CutOff). "
            f"Original a,b,c = {cell['a']:.2f}, {cell['b']:.2f}, {cell['c']:.2f} Å."
        ),
        "charge_note": (
            "All CIF charges are zero — set ChargeMethod=None to skip Ewald."
            if info["charges"]["all_zero"]
            else "CIF has charges — use ChargeMethod=Ewald with UseChargesFromCIFFile=yes."
        ),
    }
