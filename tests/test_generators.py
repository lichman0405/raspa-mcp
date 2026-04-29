"""
Tests for raspa_mcp.generators — the four file-generator helpers.

Covers:
  * Default arguments produce parseable RASPA2 content.
  * return_only / dry-run does not touch disk.
  * Sandbox enforcement rejects paths outside RASPA_MCP_WORKSPACE_BASE.
  * Round-trip content correctness (key tokens present in expected sections).
  * Bad inputs raise sensible ValueError.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raspa_mcp.generators import (
    render_force_field_def,
    render_force_field_mixing_rules_def,
    render_pseudo_atoms_def,
    render_molecule_def,
    write_force_field_def,
    write_force_field_mixing_rules_def,
    write_pseudo_atoms_def,
    write_molecule_def,
)
from raspa_mcp.server import (
    generate_force_field_def,
    generate_force_field_mixing_rules_def,
    generate_pseudo_atoms_def,
    generate_molecule_def,
)


# ─────────────────────────────────────────────────────────────────
# render_force_field_def
# ─────────────────────────────────────────────────────────────────

def test_render_ff_def_default_is_three_zeros():
    txt = render_force_field_def()
    # Three "count: 0" sections.
    assert txt.count("\n0\n") >= 3
    assert "do NOT confuse" in txt or "OVERWRITE" in txt
    assert "force_field_mixing_rules.def" in txt


def test_render_ff_def_with_overrides_emits_counts():
    txt = render_force_field_def(
        rules_to_overwrite=[{"line": "C_co2 lennard-jones 27.0 2.80", "comment": "tweak"}],
        interactions_to_define=[{"line": "Na buckingham 1000 0.3 50"}],
    )
    assert "\n1\n" in txt  # the rules count
    assert "C_co2 lennard-jones" in txt
    assert "Na buckingham" in txt


# ─────────────────────────────────────────────────────────────────
# render_force_field_mixing_rules_def
# ─────────────────────────────────────────────────────────────────

def test_render_mixing_rules_basic():
    txt = render_force_field_mixing_rules_def(
        atom_types=[
            {"name": "C_co2", "epsilon_K": 27.0, "sigma_A": 2.80},
            {"name": "O_co2", "epsilon_K": 79.0, "sigma_A": 3.05},
        ],
    )
    assert "Lorentz-Berthelot" in txt
    assert "shifted" in txt
    assert "C_co2" in txt and "O_co2" in txt
    assert "27.0000" in txt
    assert "number of defined interactions" in txt


def test_render_mixing_rules_rejects_bad_rule():
    with pytest.raises(ValueError):
        render_force_field_mixing_rules_def(
            atom_types=[{"name": "X", "epsilon_K": 1.0, "sigma_A": 1.0}],
            general_mixing_rule="ApocryphalRule",
        )


def test_render_mixing_rules_rejects_empty_atom_types():
    with pytest.raises(ValueError):
        render_force_field_mixing_rules_def(atom_types=[])


def test_render_mixing_rules_missing_field():
    with pytest.raises(ValueError):
        render_force_field_mixing_rules_def(
            atom_types=[{"name": "X", "epsilon_K": 1.0}]  # no sigma
        )


# ─────────────────────────────────────────────────────────────────
# render_pseudo_atoms_def
# ─────────────────────────────────────────────────────────────────

def test_render_pseudo_atoms_basic():
    txt = render_pseudo_atoms_def(
        atoms=[
            {"name": "C_co2", "chem": "C", "mass": 12.011, "charge": 0.6512},
            {"name": "O_co2", "chem": "O", "mass": 15.9994, "charge": -0.3256},
            {"name": "He", "chem": "He", "mass": 4.0026, "charge": 0.0},
        ]
    )
    assert "C_co2" in txt and "O_co2" in txt and "He" in txt
    # The header count line.
    assert "\n3\n" in txt
    assert "0.6512" in txt
    assert "-0.3256" in txt


def test_render_pseudo_atoms_rejects_missing_mass():
    with pytest.raises(ValueError):
        render_pseudo_atoms_def(atoms=[{"name": "X", "chem": "X", "charge": 0.0}])


# ─────────────────────────────────────────────────────────────────
# render_molecule_def
# ─────────────────────────────────────────────────────────────────

def test_render_molecule_def_co2_like():
    txt = render_molecule_def(
        molecule_name="CO2",
        critical_temperature_K=304.13,
        critical_pressure_Pa=7.376e6,
        acentric_factor=0.224,
        atoms=[
            {"type": "C_co2", "x": 0.0, "y": 0.0, "z": 0.0},
            {"type": "O_co2", "x": 1.161, "y": 0.0, "z": 0.0},
            {"type": "O_co2", "x": -1.161, "y": 0.0, "z": 0.0},
        ],
        bonds=[(0, 1, "RIGID_BOND"), (0, 2, "RIGID_BOND")],
        rigid=True,
    )
    assert "CO2" in txt
    assert "RIGID_BOND" in txt
    assert "304.1300" in txt
    # Counts line: 0 bonds=2 0 bends=0 ...
    assert "0 2 0 0 0 0" in txt


def test_render_molecule_def_rejects_empty_atoms():
    with pytest.raises(ValueError):
        render_molecule_def(
            molecule_name="X",
            critical_temperature_K=1, critical_pressure_Pa=1, acentric_factor=0,
            atoms=[],
        )


# ─────────────────────────────────────────────────────────────────
# Disk writes — sandbox enforcement
# ─────────────────────────────────────────────────────────────────

def test_write_ff_def_inside_sandbox(tmp_path: Path, monkeypatch):
    base = tmp_path / "wsbase"
    base.mkdir()
    monkeypatch.setenv("RASPA_MCP_WORKSPACE_BASE", str(base))
    work = base / "run1"
    work.mkdir()

    out = write_force_field_def(str(work))
    assert out["success"] is True
    assert (work / "force_field.def").exists()
    assert "warning" in out


def test_write_ff_def_outside_sandbox_rejected(tmp_path: Path, monkeypatch):
    base = tmp_path / "wsbase"
    base.mkdir()
    monkeypatch.setenv("RASPA_MCP_WORKSPACE_BASE", str(base))
    rogue = tmp_path / "elsewhere"
    rogue.mkdir()

    out = write_force_field_def(str(rogue))
    assert out["success"] is False
    assert any("outside allowed base" in e for e in out["errors"])
    assert not (rogue / "force_field.def").exists()


def test_write_mixing_rules_writes_file(tmp_path: Path, monkeypatch):
    base = tmp_path / "wsbase"
    base.mkdir()
    monkeypatch.setenv("RASPA_MCP_WORKSPACE_BASE", str(base))
    work = base / "run1"
    work.mkdir()

    out = write_force_field_mixing_rules_def(
        str(work),
        atom_types=[{"name": "C_co2", "epsilon_K": 27.0, "sigma_A": 2.80}],
    )
    assert out["success"] is True
    p = Path(out["path"])
    assert p.exists()
    assert "C_co2" in p.read_text()


def test_write_molecule_def_in_subdirectory(tmp_path: Path, monkeypatch):
    base = tmp_path / "wsbase"
    base.mkdir()
    monkeypatch.setenv("RASPA_MCP_WORKSPACE_BASE", str(base))
    work = base / "run1"
    work.mkdir()

    out = write_molecule_def(
        str(work),
        molecule_name="CO2",
        subdirectory="TraPPE",
        critical_temperature_K=304.13,
        critical_pressure_Pa=7.376e6,
        acentric_factor=0.224,
        atoms=[{"type": "C_co2", "x": 0.0, "y": 0.0, "z": 0.0}],
    )
    assert out["success"] is True
    expected = work / "molecules" / "TraPPE" / "CO2.def"
    assert expected.exists()


# ─────────────────────────────────────────────────────────────────
# MCP-tool layer (return_only path + error wrapping)
# ─────────────────────────────────────────────────────────────────

def test_tool_generate_ff_def_dry_run_does_not_write(tmp_path: Path, monkeypatch):
    base = tmp_path / "wsbase"
    base.mkdir()
    monkeypatch.setenv("RASPA_MCP_WORKSPACE_BASE", str(base))
    work = base / "run1"
    work.mkdir()

    out = generate_force_field_def(str(work), return_only=True)
    assert out["success"] is True
    assert out["dry_run"] is True
    assert "OVERWRITE" in out["content"] or "do NOT confuse" in out["content"]
    assert not (work / "force_field.def").exists()


def test_tool_generate_mixing_rules_validation_error_wrapped(tmp_path, monkeypatch):
    base = tmp_path / "wsbase"
    base.mkdir()
    monkeypatch.setenv("RASPA_MCP_WORKSPACE_BASE", str(base))
    work = base / "run1"
    work.mkdir()

    out = generate_force_field_mixing_rules_def(
        str(work), atom_types=[], return_only=True
    )
    assert out["success"] is False
    assert out["type"] == "ValueError"


def test_tool_generate_pseudo_atoms_writes(tmp_path, monkeypatch):
    base = tmp_path / "wsbase"
    base.mkdir()
    monkeypatch.setenv("RASPA_MCP_WORKSPACE_BASE", str(base))
    work = base / "run1"
    work.mkdir()

    out = generate_pseudo_atoms_def(
        str(work),
        atoms=[
            {"name": "C_co2", "chem": "C", "mass": 12.0, "charge": 0.65},
        ],
    )
    assert out["success"] is True
    assert (work / "pseudo_atoms.def").exists()


def test_tool_generate_molecule_def_with_bonds(tmp_path, monkeypatch):
    base = tmp_path / "wsbase"
    base.mkdir()
    monkeypatch.setenv("RASPA_MCP_WORKSPACE_BASE", str(base))
    work = base / "run1"
    work.mkdir()

    out = generate_molecule_def(
        str(work),
        molecule_name="N2",
        critical_temperature_K=126.2,
        critical_pressure_Pa=3.396e6,
        acentric_factor=0.037,
        atoms=[
            {"type": "N_n2", "x": 0.55, "y": 0.0, "z": 0.0},
            {"type": "N_n2", "x": -0.55, "y": 0.0, "z": 0.0},
        ],
        bonds=[[0, 1, "RIGID_BOND"]],
    )
    assert out["success"] is True
    txt = (work / "molecules" / "TraPPE" / "N2.def").read_text()
    assert "RIGID_BOND" in txt
