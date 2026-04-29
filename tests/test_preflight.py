"""
Tests for raspa_mcp.validator.preflight_workspace and the new
validate_simulation_input warnings.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raspa_mcp.validator import preflight_workspace, validate_simulation_input


# ─────────────────────────────────────────────────────────────────
# Builder helpers
# ─────────────────────────────────────────────────────────────────

_GOOD_SIM_INPUT = """\
SimulationType                MonteCarlo
NumberOfCycles                10000
NumberOfInitializationCycles  2000
PrintEvery                    1000
RestartFile                   no
Forcefield                    local
CutOff                        12.0
ChargeMethod                  None

Framework                     0
FrameworkName                 frame
UnitCells                     2 2 2

Component 0 MoleculeName             CO2
            MoleculeDefinition       TraPPE
            SwapProbability          1.0
            CreateNumberOfMolecules  0
"""

_GOOD_FF_DEF = """\
# overwrite-rules
# Number of rules to overwrite the mixing rules
0
# Number of interactions to be defined explicitly
0
# Number of mixing-rule cross terms to overwrite
0
"""

_GOOD_MIX_DEF = """\
# header
shifted
yes
# number of defined interactions
1
# atom-type  interaction  epsilon  sigma
C_co2        lennard-jones  27.0   2.80
Lorentz-Berthelot
"""

_GOOD_PA_DEF = """\
1
# type print as chem oxidation mass charge polarization B-factor radii connectivity anisotropic anisotropic-type tinker-type
C_co2 yes C_co2 C 0 12.0 0.65 0.0 1.0 1.0 0 0.0 absolute 0
"""

_GOOD_MOLECULE_DEF = """\
# CO2
304.0
7376460.0
0.224
3
1
rigid
3
0  C_co2  0.0  0.0  0.0
1  C_co2  1.16 0.0  0.0
2  C_co2 -1.16 0.0  0.0
0 2 0 0 0 0 0 0 0 0 0 0 0
0 1 RIGID_BOND
0 2 RIGID_BOND
0
"""


def _good_workspace(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    (work / "frameworks" / "frame").mkdir(parents=True)
    (work / "molecules" / "TraPPE").mkdir(parents=True)
    (work / "simulation.input").write_text(_GOOD_SIM_INPUT)
    (work / "force_field.def").write_text(_GOOD_FF_DEF)
    (work / "force_field_mixing_rules.def").write_text(_GOOD_MIX_DEF)
    (work / "pseudo_atoms.def").write_text(_GOOD_PA_DEF)
    (work / "frameworks" / "frame" / "frame.cif").write_text("data_frame\n")
    (work / "molecules" / "TraPPE" / "CO2.def").write_text(_GOOD_MOLECULE_DEF)
    return work


# ─────────────────────────────────────────────────────────────────
# preflight_workspace
# ─────────────────────────────────────────────────────────────────

def test_preflight_ok_path(tmp_path: Path):
    work = _good_workspace(tmp_path)
    out = preflight_workspace(str(work))
    assert out["ok"] is True, out
    assert out["errors"] == []
    assert "frame.cif" in out["findings"]["cif_path"]
    assert out["findings"]["components"] == ["CO2"]


def test_preflight_missing_simulation_input(tmp_path: Path):
    work = tmp_path / "work"
    work.mkdir()
    out = preflight_workspace(str(work))
    assert out["ok"] is False
    assert any("simulation.input" in e for e in out["errors"])


def test_preflight_force_field_def_in_wrong_format(tmp_path: Path):
    work = _good_workspace(tmp_path)
    # Replace force_field.def with content that LOOKS like mixing rules
    (work / "force_field.def").write_text(
        "Lorentz-Berthelot\nC_co2 lennard-jones 27.0 2.80\n"
    )
    out = preflight_workspace(str(work))
    assert out["ok"] is False
    assert any("overwrite-rules" in e for e in out["errors"])


def test_preflight_missing_molecule_def(tmp_path: Path):
    work = _good_workspace(tmp_path)
    (work / "molecules" / "TraPPE" / "CO2.def").unlink()
    out = preflight_workspace(str(work))
    assert out["ok"] is False
    assert any("CO2" in e and "does not exist" in e for e in out["errors"])


def test_preflight_pseudo_missing_atom_type(tmp_path: Path):
    work = _good_workspace(tmp_path)
    # Mixing rules has C_co2 but pseudo_atoms only has 'X'.
    (work / "pseudo_atoms.def").write_text(
        "1\n# header\nX yes X X 0 12.0 0.0 0.0 1.0 1.0 0 0.0 absolute 0\n"
    )
    out = preflight_workspace(str(work))
    assert out["ok"] is False
    assert any("missing from pseudo_atoms" in e for e in out["errors"])


# ─────────────────────────────────────────────────────────────────
# New validate_simulation_input warnings
# ─────────────────────────────────────────────────────────────────

def test_validate_warns_on_moleculedefinition_local():
    sim = """\
SimulationType MonteCarlo
NumberOfCycles 5000
NumberOfInitializationCycles 1000
Forcefield local
CutOff 12.0
Framework 0
Component 0 MoleculeName CO2
            MoleculeDefinition local
            SwapProbability 1.0
"""
    res = validate_simulation_input(sim)
    assert any("local" in w and "share/raspa" in w for w in res.warnings)


def test_validate_warns_on_use_cif_charges_with_chargemethod_none():
    sim = """\
SimulationType MonteCarlo
NumberOfCycles 5000
NumberOfInitializationCycles 1000
Forcefield local
CutOff 12.0
ChargeMethod None
UseChargesFromCIFFile yes
Framework 0
Component 0 MoleculeName CO2
            MoleculeDefinition TraPPE
            SwapProbability 1.0
"""
    res = validate_simulation_input(sim)
    assert any("UseChargesFromCIFFile" in w for w in res.warnings)
