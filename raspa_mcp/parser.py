"""
raspa_mcp.parser — RASPA2 output file parser.

Converts RASPA2 text output into clean JSON-serializable dicts
so Claude can read numbers directly without Fortran-style parsing.
"""

from __future__ import annotations

import re
from pathlib import Path


def _find_output_files(output_dir: str) -> list[Path]:
    """Find all RASPA2 output files in the given directory tree."""
    root = Path(output_dir)
    if not root.exists():
        return []
    return sorted(root.rglob("output_*.data")) + sorted(root.rglob("*.headOutput"))


# ─────────────────────────────────────────────────────────────────
# GCMC / adsorption output parser
# ─────────────────────────────────────────────────────────────────

def _parse_loading(text: str) -> dict | None:
    """
    Extract average loading from RASPA2 output (single-component).
    Returns mol/kg, mol/L, molecules/uc.
    """
    result = {}

    # molecules per unit cell
    m = re.search(
        r"Average loading absolute \[molecules/unit cell\]\s+([\d.eE+\-]+)\s+\+/-\s+([\d.eE+\-]+)",
        text,
    )
    if m:
        result["loading_molec_uc"] = float(m.group(1))
        result["loading_molec_uc_err"] = float(m.group(2))

    # mol/kg
    m = re.search(
        r"Average loading absolute \[mol/kg framework\]\s+([\d.eE+\-]+)\s+\+/-\s+([\d.eE+\-]+)",
        text,
    )
    if m:
        result["loading_mol_kg"] = float(m.group(1))
        result["loading_mol_kg_err"] = float(m.group(2))

    # mg/g
    m = re.search(
        r"Average loading absolute \[mg/g framework\]\s+([\d.eE+\-]+)\s+\+/-\s+([\d.eE+\-]+)",
        text,
    )
    if m:
        result["loading_mg_g"] = float(m.group(1))
        result["loading_mg_g_err"] = float(m.group(2))

    # cm3/g  (gas STP)
    m = re.search(
        r"Average loading absolute \[cm\^3 \(STP\)/g framework\]\s+([\d.eE+\-]+)\s+\+/-\s+([\d.eE+\-]+)",
        text,
    )
    if m:
        result["loading_cm3_stp_g"] = float(m.group(1))
        result["loading_cm3_stp_g_err"] = float(m.group(2))

    return result if result else None


def _parse_loading_per_component(text: str) -> list[dict] | None:
    """
    4-3: Extract per-component loading from multi-component (mixture) RASPA2 output.

    RASPA2 writes a separate block per component:
      Component 0 [CO2]  (N molecules)
        Average loading absolute [mol/kg framework]  X.XX +/- Y.YY
        ...
      Component 1 [N2]  (N molecules)
        ...

    Returns a list of dicts (one per component), or None if no components found.
    Each dict has the same keys as _parse_loading() plus 'component_index' and 'molecule_name'.
    """
    # Split on Component block headers
    component_pattern = re.compile(
        r"Component\s+(\d+)\s+\[([^\]]+)\]",
        re.MULTILINE,
    )
    matches = list(component_pattern.finditer(text))
    if len(matches) < 2:
        return None  # single-component — caller falls back to _parse_loading()

    components = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segment = text[start:end]

        comp_idx = int(match.group(1))
        mol_name = match.group(2).strip()

        entry: dict = {"component_index": comp_idx, "molecule_name": mol_name}

        loading = _parse_loading(segment)
        if loading:
            entry.update(loading)

        components.append(entry)

    return components if components else None


def _parse_energy(text: str) -> dict | None:
    """Extract average total energy and isosteric heat of adsorption from RASPA2 output."""
    result = {}
    m = re.search(
        r"Average Host-Adsorbate energy:\s+([\d.eE+\-]+)\s+\+/-\s+([\d.eE+\-]+)",
        text,
    )
    if m:
        result["host_adsorbate_energy_kJ_mol"] = float(m.group(1)) / 1000.0  # K → kJ/mol (approx)
        result["host_adsorbate_energy_err"] = float(m.group(2)) / 1000.0

    # 1-4: Isosteric heat of adsorption Qst [kJ/mol] — computed by RASPA2 from energy fluctuations
    m = re.search(
        r"Average\s+Isosteric\s+heat\s+of\s+adsorption:\s+([\d.eE+\-]+)\s+\+/-\s+([\d.eE+\-]+)\s*\[KJ/mol\]",
        text,
        re.IGNORECASE,
    )
    if m:
        result["Qst_kJ_mol"] = float(m.group(1))
        result["Qst_kJ_mol_err"] = float(m.group(2))

    return result if result else None


def _parse_henry(text: str) -> dict | None:
    """Extract Henry coefficient and excess chemical potential from Widom insertion output."""
    import math

    result = {}

    # Henry coefficient [mol/(kg·Pa)]
    m = re.search(
        r"Henry coefficient:\s+([\d.eE+\-]+)\s+\[mol/kg/Pa\]",
        text,
    )
    if m:
        result["henry_mol_kg_Pa"] = float(m.group(1))

    # Widom Rosenbluth factor
    m = re.search(
        r"Average Widom Rosenbluth factor:\s+([\d.eE+\-]+)\s+\+/-\s+([\d.eE+\-]+)",
        text,
    )
    if m:
        result["widom_rosenbluth"] = float(m.group(1))
        result["widom_rosenbluth_err"] = float(m.group(2))

        # 3-8: Excess chemical potential mu_ex = -RT ln(W)  [kJ/mol]
        W = float(m.group(1))  # noqa: N806 — Rosenbluth factor, standard notation
        t_match = re.search(r"External temperature:\s+([\d.eE+\-]+)\s*\[K\]", text)
        if t_match and W > 0:
            T = float(t_match.group(1))  # noqa: N806 — temperature in K
            R = 8.314e-3  # noqa: N806 — gas constant kJ/(mol·K)
            result["mu_ex_kJ_mol"] = -R * T * math.log(W)

    return result if result else None


def _parse_void_fraction(text: str) -> dict | None:
    """Extract helium void fraction from output."""
    m = re.search(r"Void fraction:\s+([\d.eE+\-]+)", text)
    if m:
        return {"helium_void_fraction": float(m.group(1))}
    return None


def _parse_conditions(text: str) -> dict:
    """Extract simulation conditions from output header."""
    result = {}
    m = re.search(r"External temperature:\s+([\d.eE+\-]+)\s*\[K\]", text)
    if m:
        result["temperature_K"] = float(m.group(1))
    m = re.search(r"External pressure:\s+([\d.eE+\-]+)\s*\[Pa\]", text)
    if m:
        result["pressure_Pa"] = float(m.group(1))
        result["pressure_bar"] = result["pressure_Pa"] / 1e5
    return result


# ─────────────────────────────────────────────────────────────────
# 3-3: Radial distribution function parser
# ─────────────────────────────────────────────────────────────────

def parse_rdf_output(
    output_dir: str,
    component_a: str = "",
    component_b: str = "",
) -> dict:
    """
    Parse RASPA2 radial distribution function (RDF) output files.

    RASPA2 writes RDF data to files named RDF_<A>_<B>.dat in the Output directory
    when ComputeRDF yes is set in simulation.input.
    Each file contains two columns: r (Å) and g(r).

    component_a / component_b: optional filters on the pair name.
    Leave empty to return all RDF datasets found.
    """
    root = Path(output_dir)
    if not root.exists():
        return {
            "status": "no_output_found",
            "output_dir": output_dir,
            "rdf_data": [],
        }

    rdf_files = sorted(root.rglob("RDF_*.dat"))
    if not rdf_files:
        return {
            "status": "no_rdf_files",
            "output_dir": output_dir,
            "message": (
                "No RDF_*.dat files found. "
                "Ensure 'ComputeRDF yes' is set in simulation.input."
            ),
            "rdf_data": [],
        }

    results = []
    for fpath in rdf_files:
        fname = fpath.stem  # e.g. RDF_CO2_CO2
        if component_a and component_a.lower() not in fname.lower():
            continue
        if component_b and component_b.lower() not in fname.lower():
            continue

        try:
            lines = fpath.read_text(errors="replace").splitlines()
        except OSError as e:
            results.append({"file": str(fpath), "error": str(e)})
            continue

        r_values: list[float] = []
        g_values: list[float] = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    r_values.append(float(parts[0]))
                    g_values.append(float(parts[1]))
                except ValueError:
                    continue

        if r_values:
            peak_idx = g_values.index(max(g_values))
            results.append({
                "file": str(fpath),
                "pair": fname.replace("RDF_", ""),
                "r_angstrom": r_values,
                "g_r": g_values,
                "n_points": len(r_values),
                "r_min": min(r_values),
                "r_max": max(r_values),
                "first_peak_r": r_values[peak_idx],
                "first_peak_g": g_values[peak_idx],
            })

    return {
        "status": "ok" if results else "no_matching_files",
        "output_dir": output_dir,
        "n_rdf_datasets": len(results),
        "rdf_data": results,
    }


# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────

def parse_output(output_dir: str) -> dict:
    """
    Parse all RASPA2 output files in *output_dir* and return structured results.

    Returns a dict with keys:
      - "status": "ok" | "no_output_found" | "partial"
      - "output_dir": path
      - "results": list of per-file parsed dicts
      - "isotherm": condensed loading vs pressure list (if multiple pressures detected)
      - "components": per-component loading list (only present for mixture simulations)
    """
    files = _find_output_files(output_dir)

    if not files:
        return {
            "status": "no_output_found",
            "output_dir": output_dir,
            "message": (
                f"No RASPA2 output files found in '{output_dir}'. "
                "Check that the simulation completed and OutputDirectory is correct."
            ),
            "results": [],
        }

    parsed_results = []
    all_components: list[dict] = []

    for fpath in files:
        try:
            text = fpath.read_text(errors="replace")
        except OSError as e:
            parsed_results.append({"file": str(fpath), "error": str(e)})
            continue

        entry: dict = {"file": str(fpath)}
        entry.update(_parse_conditions(text))

        # 4-3: Try multi-component parse first; fall back to single-component
        per_component = _parse_loading_per_component(text)
        if per_component:
            entry["components"] = per_component
            # Propagate first component loading to top level for backward compat
            if per_component:
                first = {k: v for k, v in per_component[0].items()
                         if k not in ("component_index", "molecule_name")}
                entry.update(first)
            all_components.extend(per_component)
        else:
            loading = _parse_loading(text)
            if loading:
                entry.update(loading)

        energy = _parse_energy(text)
        if energy:
            entry.update(energy)

        henry = _parse_henry(text)
        if henry:
            entry.update(henry)

        void_frac = _parse_void_fraction(text)
        if void_frac:
            entry.update(void_frac)

        if len(entry) == 1:
            entry["warning"] = "No recognised data extracted from this output file."

        parsed_results.append(entry)

    # Build isotherm summary if pressure data exists across multiple points
    isotherm_points = [
        {
            "pressure_bar": r.get("pressure_bar"),
            "loading_mol_kg": r.get("loading_mol_kg"),
            "loading_mol_kg_err": r.get("loading_mol_kg_err"),
            "loading_cm3_stp_g": r.get("loading_cm3_stp_g"),
        }
        for r in parsed_results
        if r.get("pressure_bar") is not None and r.get("loading_mol_kg") is not None
    ]
    isotherm_points.sort(key=lambda x: x["pressure_bar"])

    result: dict = {
        "status": "ok",
        "output_dir": output_dir,
        "n_files_parsed": len(files),
        "results": parsed_results,
        "isotherm": isotherm_points if len(isotherm_points) > 1 else None,
    }
    if all_components:
        result["components"] = all_components
    return result


# ─────────────────────────────────────────────────────────────────
# 2-1 / 3-1 / 3-2: MSD parser → self- and collective-diffusion coefficients
# ─────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────
# 1-8: Thermodynamic Integration — free energy parser
# ─────────────────────────────────────────────────────────────────

def parse_ti_output(output_dir: str) -> dict:
    """
    Parse RASPA2 Thermodynamic Integration (TI) output and compute ΔA.

    Workflow: user runs N separate simulations at lambda = 0.0, 0.1, …, 1.0
    (one simulation.input per λ, each in its own subdirectory named by λ value).
    Each output file contains a line like:
      Average <dU/dlambda>:   X.XXXXX +/- Y.YYYYY [K]

    This function:
      1. Recursively finds all RASPA2 output files.
      2. Extracts λ and ⟨∂U/∂λ⟩ from each file.
      3. Sorts by λ and integrates with numpy.trapz → ΔA [kJ/mol].

    Returns dict with keys:
      lambda_points, dU_dlambda, dU_dlambda_err, delta_A_K, delta_A_kJ_mol.
    """
    try:
        import numpy as np
    except ImportError:
        return {"status": "error", "message": "numpy not installed; run: pip install numpy"}

    root = Path(output_dir)
    if not root.exists():
        return {"status": "no_output_found", "output_dir": output_dir, "lambda_points": []}

    # Pattern for ⟨dU/dλ⟩ line
    du_pat = re.compile(
        r"Average\s+<dU/dlambda>\s*[=:]?\s*([\-\d.eE+]+)\s+\+/-\s+([\d.eE+]+)",
        re.IGNORECASE,
    )
    # Pattern for lambda echo in output (RASPA2 echoes simulation.input)
    lambda_pat = re.compile(r"\bLambda\b\s+([\d.eE+\-]+)", re.IGNORECASE)

    records: list[dict] = []
    for fpath in _find_output_files(output_dir):
        try:
            text = fpath.read_text(errors="replace")
        except OSError:
            continue

        m_du = du_pat.search(text)
        if not m_du:
            continue

        du_val = float(m_du.group(1))
        du_err = float(m_du.group(2))

        # Try to extract λ from output (echoed input) or parent directory name
        lam: float | None = None
        m_lam = lambda_pat.search(text)
        if m_lam:
            lam = float(m_lam.group(1))
        else:
            # Fall back: try parent directory name (e.g. "lambda_0.5" or "0.5")
            for part in reversed(fpath.parts):
                try:
                    candidate = float(part.replace("lambda_", "").replace("lambda", ""))
                    if 0.0 <= candidate <= 1.0:
                        lam = candidate
                        break
                except ValueError:
                    continue

        if lam is None:
            continue

        records.append({"lambda": lam, "dU_dlambda_K": du_val, "dU_dlambda_err_K": du_err})

    if not records:
        return {
            "status": "no_ti_data",
            "output_dir": output_dir,
            "message": (
                "No 'Average <dU/dlambda>' lines found. "
                "Ensure Lambda and LambdaDefinition are set and "
                "simulations were run for each λ value."
            ),
            "lambda_points": [],
        }

    records.sort(key=lambda r: r["lambda"])
    lam_arr = np.array([r["lambda"] for r in records])
    du_arr = np.array([r["dU_dlambda_K"] for r in records])
    du_err_arr = np.array([r["dU_dlambda_err_K"] for r in records])

    # ΔA = ∫₀¹ ⟨∂U/∂λ⟩ dλ  [K]
    delta_a_k = float(np.trapezoid(du_arr, lam_arr))
    # Convert K → kJ/mol:  ΔA [kJ/mol] = ΔA[K] × R  (R = 8.314e-3 kJ/mol/K)
    r_kj = 8.314e-3
    delta_a_kj = delta_a_k * r_kj

    # Error estimate via trapz on upper-bound error array
    delta_a_err_kj = float(np.trapezoid(du_err_arr, lam_arr)) * r_kj

    return {
        "status": "ok",
        "output_dir": output_dir,
        "n_lambda_points": len(records),
        "lambda_range": [float(lam_arr[0]), float(lam_arr[-1])],
        "lambda_points": [
            {
                "lambda": r["lambda"],
                "dU_dlambda_K": r["dU_dlambda_K"],
                "dU_dlambda_err_K": r["dU_dlambda_err_K"],
            }
            for r in records
        ],
        "delta_A_K": round(delta_a_k, 4),
        "delta_A_kJ_mol": round(delta_a_kj, 4),
        "delta_A_kJ_mol_err": round(delta_a_err_kj, 4),
        "note": (
            "ΔA = ∫⟨∂U/∂λ⟩dλ via trapezoidal rule. "
            "Full λ coverage (0→1) recommended; partial range gives relative ΔA."
        ),
    }


# ─────────────────────────────────────────────────────────────────
# 3-4: 3D density grid parser + 2D slice extractor
# ─────────────────────────────────────────────────────────────────

def parse_density_grid(
    output_dir: str,
    molecule: str = "",
    slice_axis: str = "z",
    slice_index: int = -1,
) -> dict:
    """
    Parse RASPA2 3D density grid files (.grid) and extract a 2D slice.

    RASPA2 writes density grids when 'WriteDensityProfile3DVTKGrid yes' or
    'ComputeNumberDensityHistogram yes' is set. Grid files are ASCII with format:

      Line 1:  comment / grid name
      Line 2:  Nx  Ny  Nz      (grid point counts along a, b, c)
      Line 3:  a  b  c  alpha  beta  gamma   (cell parameters)
      Lines 4+: density values (Nx*Ny*Nz floats, row-major a→b→c)

    Returns the grid metadata, cell parameters, and a 2D slice through the
    specified axis at slice_index (defaults to midpoint).

    slice_axis: 'x'|'y'|'z'  (mapped to a|b|c grid indices)
    slice_index: integer grid plane index; -1 = midpoint
    """
    root = Path(output_dir)
    if not root.exists():
        return {"status": "no_output_found", "output_dir": output_dir, "datasets": []}

    grid_files = sorted(root.rglob("*.grid"))
    if not grid_files:
        return {
            "status": "no_grid_files",
            "output_dir": output_dir,
            "message": (
                "No .grid files found. Set 'WriteDensityProfile3DVTKGrid yes' "
                "and 'DensityAveragingTypeVTK number_of_molecules' in simulation.input."
            ),
            "datasets": [],
        }

    axis_map = {"x": 0, "y": 1, "z": 2, "a": 0, "b": 1, "c": 2}
    ax_idx = axis_map.get(slice_axis.lower(), 2)

    datasets = []
    for fpath in grid_files:
        if molecule and molecule.lower() not in fpath.name.lower():
            continue
        try:
            lines = [ln.strip() for ln in fpath.read_text(errors="replace").splitlines()
                     if ln.strip() and not ln.startswith("#")]
        except OSError as e:
            datasets.append({"file": str(fpath), "error": str(e)})
            continue

        if len(lines) < 3:
            datasets.append({"file": str(fpath), "warning": "File too short to parse"})
            continue

        # Parse header
        try:
            grid_tokens = lines[0].split()
            nx, ny, nz = int(grid_tokens[0]), int(grid_tokens[1]), int(grid_tokens[2])
            cell_tokens = lines[1].split()
            cell = [float(x) for x in cell_tokens[:6]]
            data_lines = lines[2:]
        except (ValueError, IndexError):
            # Try alternative: first non-numeric line is title, grid dims on next
            try:
                nx, ny, nz = int(lines[1].split()[0]), int(lines[1].split()[1]), int(lines[1].split()[2])
                cell = [float(x) for x in lines[2].split()[:6]]
                data_lines = lines[3:]
            except (ValueError, IndexError):
                datasets.append({"file": str(fpath), "warning": "Cannot parse grid header"})
                continue

        # Parse density values
        values: list[float] = []
        for line in data_lines:
            for tok in line.split():
                try:
                    values.append(float(tok))
                except ValueError:
                    continue

        expected = nx * ny * nz
        if len(values) < expected:
            datasets.append({
                "file": str(fpath),
                "warning": f"Expected {expected} values, got {len(values)}",
                "grid": [nx, ny, nz],
            })
            continue

        values = values[:expected]

        # Reshape: values indexed as [ia][ib][ic]
        import numpy as np
        grid_3d = np.array(values).reshape(nx, ny, nz)

        dims = [nx, ny, nz]
        si = slice_index if slice_index >= 0 else dims[ax_idx] // 2
        si = min(si, dims[ax_idx] - 1)

        # Extract 2D slice
        if ax_idx == 0:
            plane = grid_3d[si, :, :].tolist()
            plane_shape = [ny, nz]
            plane_axes = ["b", "c"]
        elif ax_idx == 1:
            plane = grid_3d[:, si, :].tolist()
            plane_shape = [nx, nz]
            plane_axes = ["a", "c"]
        else:
            plane = grid_3d[:, :, si].tolist()
            plane_shape = [nx, ny]
            plane_axes = ["a", "b"]

        datasets.append({
            "file": str(fpath),
            "grid_nx_ny_nz": [nx, ny, nz],
            "cell_a_b_c_alpha_beta_gamma": cell,
            "n_values": expected,
            "density_max": float(np.max(grid_3d)),
            "density_mean": float(np.mean(grid_3d)),
            "slice_axis": slice_axis,
            "slice_index": si,
            "slice_shape": plane_shape,
            "slice_axes": plane_axes,
            "slice_data": plane,
        })

    return {
        "status": "ok" if datasets else "no_matching_files",
        "output_dir": output_dir,
        "n_datasets": len(datasets),
        "datasets": datasets,
    }


def parse_msd_output(
    output_dir: str,
    molecule: str = "",
    diffusion_type: str = "self",
) -> dict:
    """
    Parse RASPA2 MSD output files and compute diffusion coefficients.

    RASPA2 NVT-MD simulations write MSD data to:
      MSDSelf_<molecule>_<system>.dat      → self-diffusion  (3-1)
      MSDCollective_<molecule>_<system>.dat → collective diffusion (3-2)

    File format (columns):
      Block#  time(ps)  MSD_x(A^2)  MSD_y(A^2)  MSD_z(A^2)  MSD_total(A^2)

    Diffusion coefficient computed from Einstein relation on the linear regime
    (latter 50 % of the trajectory to skip ballistic / sub-diffusive onset):
      D = slope / 6   [A^2/ps]
    Converted to SI:  1 A^2/ps = 1e-8 m^2/s

    diffusion_type: "self" reads MSDSelf_*.dat, "collective" reads MSDCollective_*.dat.
    molecule: optional name filter (e.g. "CO2").
    """
    try:
        import numpy as np
    except ImportError:
        return {"status": "error", "message": "numpy not installed; run: pip install numpy"}

    root = Path(output_dir)
    if not root.exists():
        return {"status": "no_output_found", "output_dir": output_dir, "datasets": []}

    prefix = "MSDSelf" if diffusion_type == "self" else "MSDCollective"
    msd_files = sorted(root.rglob(f"{prefix}*.dat"))
    if not msd_files:
        return {
            "status": "no_msd_files",
            "output_dir": output_dir,
            "message": (
                f"No {prefix}_*.dat files found. "
                "Ensure 'ComputeMSD yes' and 'PrintEvery' are set and Ensemble is NVT/NPT-MD."
            ),
            "datasets": [],
        }

    datasets = []
    for fpath in msd_files:
        if molecule and molecule.lower() not in fpath.name.lower():
            continue

        try:
            lines = fpath.read_text(errors="replace").splitlines()
        except OSError as e:
            datasets.append({"file": str(fpath), "error": str(e)})
            continue

        times: list[float] = []
        msds: list[float] = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            # Try 6-column format (block, time, x, y, z, total) first
            if len(parts) >= 6:
                try:
                    times.append(float(parts[1]))
                    msds.append(float(parts[5]))
                    continue
                except ValueError:
                    pass
            # Fall back to 2-column format (time, msd)
            if len(parts) >= 2:
                try:
                    times.append(float(parts[0]))
                    msds.append(float(parts[1]))
                except ValueError:
                    continue

        if len(times) < 4:
            datasets.append({
                "file": str(fpath),
                "warning": f"Only {len(times)} data points — trajectory too short for reliable fit.",
                "n_points": len(times),
            })
            continue

        t_arr = np.array(times)
        msd_arr = np.array(msds)

        # Use latter 50 % of data for linear fit (skip ballistic regime)
        split = max(1, len(t_arr) // 2)
        slope, intercept = np.polyfit(t_arr[split:], msd_arr[split:], 1)

        # D = slope / 6  [A^2/ps]  ->  m^2/s  (1 A^2/ps = 1e-8 m^2/s)
        d_a2_ps = slope / 6.0
        d_m2_s = d_a2_ps * 1e-8

        datasets.append({
            "file": str(fpath),
            "molecule": fpath.stem.replace(prefix + "_", ""),
            "diffusion_type": diffusion_type,
            "n_points": len(times),
            "fit_points_used": len(t_arr) - split,
            "slope_A2_per_ps": float(slope),
            "D_A2_per_ps": float(d_a2_ps),
            "D_m2_per_s": float(d_m2_s),
            "D_m2_per_s_sci": f"{d_m2_s:.3e}",
            "t_range_ps": [float(t_arr[split]), float(t_arr[-1])],
            "R_squared": float(
                1 - np.var(msd_arr[split:] - (slope * t_arr[split:] + intercept))
                / np.var(msd_arr[split:])
            ),
        })

    return {
        "status": "ok" if datasets else "no_matching_files",
        "output_dir": output_dir,
        "diffusion_type": diffusion_type,
        "n_datasets": len(datasets),
        "datasets": datasets,
    }
