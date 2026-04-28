"""
Regression tests for bug fixes:

- Energy unit conversion (K → kJ/mol via R, not /1000)
- parse_msd_output gracefully handles short trajectories
- create_workspace enforces RASPA_MCP_WORKSPACE_BASE sandbox
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from raspa_mcp.parser import _parse_energy, parse_msd_output
from raspa_mcp.server import create_workspace


# ─────────────────────────────────────────────────────────────────
# Energy unit conversion (K → kJ/mol)
# ─────────────────────────────────────────────────────────────────

_R_KJ_PER_MOL_K = 8.314462618e-3


def test_energy_converted_via_R_not_divided_by_1000():
    # 12000 K is a typical magnitude for host-adsorbate energy.
    text = "Average Host-Adsorbate energy:   12000.0 +/- 150.0"
    result = _parse_energy(text)

    assert result is not None
    assert "host_adsorbate_energy_kJ_mol" in result

    expected = 12000.0 * _R_KJ_PER_MOL_K  # ≈ 99.77 kJ/mol
    assert math.isclose(
        result["host_adsorbate_energy_kJ_mol"], expected, rel_tol=1e-9
    ), f"got {result['host_adsorbate_energy_kJ_mol']!r}, expected ~{expected:.4f}"

    # Sanity check: confirm we are NOT using the buggy /1000 path,
    # which would produce 12.0 kJ/mol — about an order of magnitude off.
    assert result["host_adsorbate_energy_kJ_mol"] > 50.0

    # Error bar should use the same conversion factor.
    assert math.isclose(
        result["host_adsorbate_energy_err"], 150.0 * _R_KJ_PER_MOL_K, rel_tol=1e-9
    )


# ─────────────────────────────────────────────────────────────────
# parse_msd_output: short-trajectory guard
# ─────────────────────────────────────────────────────────────────

def _write_msd_file(dirpath: Path, molecule: str, rows: list[tuple[float, float]]) -> Path:
    """Create a minimal RASPA-style MSD .dat file inside ``Output/System_0``.

    Uses the 2-column fallback format (time, msd_total) which the parser
    accepts when the 6-column block format is not present.
    """
    out_dir = dirpath / "Output" / "System_0"
    out_dir.mkdir(parents=True, exist_ok=True)
    fpath = out_dir / f"MSDSelf_{molecule}_System_0.dat"
    lines = ["# t [ps]    MSD [A^2]"]
    for t, msd in rows:
        lines.append(f"{t}\t{msd}")
    fpath.write_text("\n".join(lines) + "\n")
    return fpath


def test_msd_short_trajectory_does_not_crash(tmp_path: Path):
    # Only 2 points — below the parser's minimum of 4. Must NOT crash.
    _write_msd_file(tmp_path, "CO2", [(0.0, 0.0), (1.0, 2.0)])

    result = parse_msd_output(str(tmp_path), molecule="CO2", diffusion_type="self")

    assert result["status"] == "ok"
    assert result["n_datasets"] == 1
    ds = result["datasets"][0]
    # Either a warning (existing < 4 guard) or an error (new latter-half guard)
    # — both are acceptable as long as no slope was fitted.
    assert ("warning" in ds) or ("error" in ds)
    assert "slope_A2_per_ps" not in ds


def test_msd_long_trajectory_still_fits(tmp_path: Path):
    # 10 points along a clean line: MSD = 6 * t  ->  D = 1 A^2/ps
    rows = [(float(i), 6.0 * i) for i in range(10)]
    _write_msd_file(tmp_path, "N2", rows)

    result = parse_msd_output(str(tmp_path), molecule="N2", diffusion_type="self")

    assert result["status"] == "ok"
    ds = result["datasets"][0]
    assert "error" not in ds
    assert "warning" not in ds
    assert math.isclose(ds["D_A2_per_ps"], 1.0, rel_tol=1e-6)


# ─────────────────────────────────────────────────────────────────
# create_workspace path sandbox
# ─────────────────────────────────────────────────────────────────

def _touch_cif(tmp_path: Path) -> Path:
    cif = tmp_path / "frame.cif"
    cif.write_text("data_frame\n_cell_length_a 10.0\n")
    return cif


def test_create_workspace_inside_base_succeeds(tmp_path: Path, monkeypatch):
    base = tmp_path / "wsbase"
    base.mkdir()
    monkeypatch.setenv("RASPA_MCP_WORKSPACE_BASE", str(base))

    cif = _touch_cif(tmp_path)
    work = base / "run1"

    result = create_workspace(str(work), "frame", str(cif))

    assert result["success"] is True, result
    assert (work / "frameworks" / "frame" / "frame.cif").exists()


def test_create_workspace_outside_base_rejected(tmp_path: Path, monkeypatch):
    base = tmp_path / "wsbase"
    base.mkdir()
    monkeypatch.setenv("RASPA_MCP_WORKSPACE_BASE", str(base))

    cif = _touch_cif(tmp_path)
    # tmp_path is OUTSIDE base.
    rogue = tmp_path / "elsewhere" / "run1"

    result = create_workspace(str(rogue), "frame", str(cif))

    assert result["success"] is False
    assert any("outside allowed base" in e for e in result["errors"])
    # Must not have created the directory tree.
    assert not rogue.exists()


def test_create_workspace_default_base_is_home(tmp_path: Path, monkeypatch):
    # When the env var is unset, the default is ~/raspa_workspaces.
    # Point HOME at tmp_path so we don't touch the real home dir.
    monkeypatch.delenv("RASPA_MCP_WORKSPACE_BASE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    cif = _touch_cif(tmp_path)
    work = tmp_path / "raspa_workspaces" / "run1"

    result = create_workspace(str(work), "frame", str(cif))
    assert result["success"] is True, result


@pytest.mark.parametrize("escape", ["/etc/raspa_run", "/tmp/../etc/run"])
def test_create_workspace_path_traversal_rejected(escape: str, tmp_path: Path, monkeypatch):
    base = tmp_path / "wsbase"
    base.mkdir()
    monkeypatch.setenv("RASPA_MCP_WORKSPACE_BASE", str(base))

    cif = _touch_cif(tmp_path)

    result = create_workspace(escape, "frame", str(cif))
    assert result["success"] is False
