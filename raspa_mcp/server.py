"""
raspa_mcp.server — MCP server exposing RASPA2 knowledge and utilities.

Tools provided:
  - list_simulation_types        → what simulation modes RASPA2 supports
  - get_simulation_template      → canonical simulation.input template
  - list_available_forcefields   → built-in force fields with metadata
  - get_forcefield_files         → pseudo_atoms.def + mixing_rules.def content
  - list_available_molecules     → built-in molecule definitions
  - get_molecule_definition      → molecule .def file content
  - recommend_forcefield         → given a molecule name, suggest the right FF
  - create_workspace             → build RASPA2 directory structure
  - validate_simulation_input    → check simulation.input before running
  - parse_output                 → parse RASPA2 output → structured JSON
  - get_parameter_docs           → documentation for simulation.input parameters

Usage (featherflow config.json):
  "tools": {
    "mcpServers": {
      "raspa2": {
        "command": "python",
        "args": ["-m", "raspa_mcp.server"],
        "toolTimeout": 30
      }
    }
  }
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from loguru import logger
from mcp.server.fastmcp import FastMCP

from raspa_mcp.data.forcefields import FORCEFIELD_META, MIXING_RULES, PSEUDO_ATOMS
from raspa_mcp.data.molecules import MOLECULE_DEFINITIONS, MOLECULE_META
from raspa_mcp.data.templates import TEMPLATE_PARAMS, TEMPLATES
from raspa_mcp.installer import check_environment as _check_env
from raspa_mcp.parser import parse_density_grid as _parse_density_grid
from raspa_mcp.parser import parse_msd_output as _parse_msd_output
from raspa_mcp.parser import parse_output as _parse_output
from raspa_mcp.parser import parse_rdf_output as _parse_rdf_output
from raspa_mcp.parser import parse_ti_output as _parse_ti_output
from raspa_mcp.validator import preflight_workspace as _preflight
from raspa_mcp.validator import validate_simulation_input as _validate
from raspa_mcp.generators import (
    render_force_field_def as _render_ff,
    render_force_field_mixing_rules_def as _render_mix,
    render_pseudo_atoms_def as _render_pa,
    render_molecule_def as _render_mol,
    write_force_field_def as _write_ff,
    write_force_field_mixing_rules_def as _write_mix,
    write_pseudo_atoms_def as _write_pa,
    write_molecule_def as _write_mol,
)

# Module-level palette constants (used by plot_isotherm_comparison)
_PLOT_COLORS = [
    "#2563EB", "#DC2626", "#16A34A", "#D97706", "#7C3AED",
    "#0891B2", "#BE185D", "#65A30D", "#EA580C", "#6366F1",
]
_PLOT_MARKERS = ["o", "s", "^", "D", "v", "P", "*", "X", "h", "+"]

mcp = FastMCP(
    name="raspa2",
    instructions=(
        "RASPA2 molecular simulation knowledge base and utilities. "
        "Use these tools to build correct RASPA2 input files, validate them, "
        "and parse simulation output. For non-standard molecules or force fields "
        "not in the built-in library, use Semantic Scholar / web fetch tools to "
        "find parameters, then assemble the files manually using the templates "
        "and formats provided here."
    ),
)


# ─────────────────────────────────────────────────────────────────
# 1. Simulation type overview
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def list_simulation_types() -> dict:
    """
    List all RASPA2 simulation types with descriptions and typical use cases.
    Call this first to decide which simulation type fits the user's goal.
    """
    return {
        "types": {
            "GCMC": {
                "full_name": "Grand Canonical Monte Carlo",
                "use_case": "Adsorption isotherms (loading vs pressure at fixed T)",
                "outputs": ["loading in mol/kg, mg/g, cm³/g", "Henry coefficient (low P limit)"],
                "typical_cycles": "10000–100000 production + 2000–5000 init",
            },
            "Widom": {
                "full_name": "Widom Test-Particle Insertion",
                "use_case": "Henry coefficient, free energy of adsorption at infinite dilution",
                "outputs": ["Henry coefficient [mol/kg/Pa]", "adsorption energy [kJ/mol]"],
                "typical_cycles": "10000–50000",
                "note": "Much faster than GCMC at very low pressures",
            },
            "MD": {
                "full_name": "Molecular Dynamics",
                "use_case": "Diffusion coefficients, transport properties, dynamics",
                "outputs": ["mean square displacement", "diffusion coefficient [m²/s]"],
                "typical_cycles": "100000–1000000",
                "note": "Use NVT ensemble for fixed-loading studies",
            },
            "VoidFraction": {
                "full_name": "Helium Void Fraction",
                "use_case": "Compute pore void fraction needed for GCMC loading conversion",
                "outputs": ["helium void fraction (0–1)"],
                "note": "Run this before GCMC if void fraction is unknown",
            },
            "NVT-MC": {
                "full_name": "NVT Monte Carlo (canonical ensemble)",
                "use_case": "Structural sampling, RDF, density profiles at fixed N/V/T",
                "outputs": ["radial distribution g(r)", "energy averages"],
                "note": "Molecules are pre-loaded; no insertion/deletion",
            },
            "NPT-MC": {
                "full_name": "NPT Monte Carlo (isothermal-isobaric ensemble)",
                "use_case": "Equilibrium density, volume response to pressure, flexible MOF studies",
                "outputs": ["average volume", "density", "energy"],
                "note": "Requires VolumeChangeProbability in Component block",
            },
            "NPT-MD": {
                "full_name": "NPT Molecular Dynamics",
                "use_case": "Equilibrium density, thermal expansion coefficient at constant P",
                "outputs": ["density vs time", "average volume"],
                "note": "Requires Parrinello-Rahman barostat (BarostatChainLength)",
            },
            "NVE-MD": {
                "full_name": "NVE Molecular Dynamics (microcanonical)",
                "use_case": "Verify force field energy conservation; integrator benchmarking",
                "outputs": ["total energy drift", "temperature fluctuation"],
                "note": "Not for production thermodynamics — use NVT/NPT instead",
            },
            "GCMCMixture": {
                "full_name": "GCMC Binary Mixture",
                "use_case": "Co-adsorption, selectivity S_AB, mixed-gas isotherms",
                "outputs": ["loading per component", "selectivity S_AB"],
                "note": "Use PartialPressure per component, not ExternalPressure",
            },
            "CBMC": {
                "full_name": "GCMC with Configurational-Bias Monte Carlo",
                "use_case": "Adsorption of flexible/chain molecules (C4+ alkanes, branched HCs)",
                "outputs": ["loading in mol/kg", "Qst"],
                "note": (
                    "Required for molecules with 4+ heavy atoms where naive random "
                    "insertion has near-zero acceptance. Set CBMCProbability=0.4 and "
                    "NumberOfTrialPositions=10-20."
                ),
            },
            "TI": {
                "full_name": "Thermodynamic Integration",
                "use_case": "Free energy of adsorption ΔA, chemical potential differences",
                "outputs": ["ΔA [kJ/mol]", "⟨∂U/∂λ⟩ per lambda point"],
                "note": (
                    "Run 11 simulations at lambda = 0.0, 0.1, ..., 1.0. "
                    "Then call parse_ti_output() to integrate and get ΔA."
                ),
            },
            "FlexibleMD": {
                "full_name": "Flexible Framework Molecular Dynamics",
                "use_case": "Framework breathing, gate opening, phonons, host deformation",
                "outputs": ["volume vs time", "density", "MSD"],
                "note": (
                    "Requires Framework.def — bonded force field for framework atoms. "
                    "raspa-mcp has NO tool to auto-generate Framework.def. "
                    "You must create it manually from DFT data or DDEC charges + UFF bonded "
                    "parameters. See RASPA2 manual §7.4 for the required format. "
                    "Without a valid Framework.def the simulation will crash at startup."
                ),
            },
        }
    }


# ─────────────────────────────────────────────────────────────────
# 2. Simulation templates
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def get_simulation_template(
    simulation_type: Literal[
        "GCMC", "Widom", "MD", "VoidFraction",
        "NVT-MC", "NPT-MC", "NPT-MD", "NVE-MD",
        "GCMCMixture", "CBMC", "TI", "FlexibleMD",
    ],
) -> dict:
    """
    Return the canonical simulation.input template for the given simulation type.
    The template contains ${PLACEHOLDER} markers — replace them with actual values
    before writing the file.

    Also returns parameter documentation explaining each placeholder.
    """
    if simulation_type not in TEMPLATES:
        return {
            "error": f"Unknown simulation type '{simulation_type}'.",
            "available": list(TEMPLATES.keys()),
        }

    return {
        "simulation_type": simulation_type,
        "template": TEMPLATES[simulation_type],
        "parameter_docs": TEMPLATE_PARAMS,
        "instructions": (
            "Replace every ${PLACEHOLDER} with the actual value. "
            "Save as 'simulation.input' in the simulation working directory."
        ),
    }


# ─────────────────────────────────────────────────────────────────
# 3. Force fields
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def list_available_forcefields() -> dict:
    """
    List all built-in force fields with their molecule targets, references,
    and applicability notes. Use this to decide which force field to use.
    """
    return {"forcefields": FORCEFIELD_META}


@mcp.tool()
def get_forcefield_files(forcefield_name: str) -> dict:
    """
    Return the complete content of pseudo_atoms.def and
    force_field_mixing_rules.def for the given force field.

    These files must be placed in the simulation working directory
    alongside simulation.input.

    Args:
        forcefield_name: e.g. "TraPPE-CO2", "TraPPE-N2", "TraPPE-CH4"
    """
    if forcefield_name not in PSEUDO_ATOMS:
        return {
            "error": f"Force field '{forcefield_name}' not found in built-in library.",
            "available": list(PSEUDO_ATOMS.keys()),
            "advice": (
                "For non-standard molecules (e.g. PH3, H2S), search literature "
                "for LJ epsilon/sigma and partial charges, then construct "
                "pseudo_atoms.def and force_field_mixing_rules.def manually "
                "using the format shown in any of the available force fields above."
            ),
        }

    return {
        "forcefield_name": forcefield_name,
        "metadata": FORCEFIELD_META.get(forcefield_name, {}),
        "files": {
            "pseudo_atoms.def": {
                "filename": "pseudo_atoms.def",
                "content": PSEUDO_ATOMS[forcefield_name],
            },
            "force_field_mixing_rules.def": {
                "filename": "force_field_mixing_rules.def",
                "content": MIXING_RULES.get(forcefield_name, "# Not available for this FF"),
            },
        },
        "placement": "Write both files into the simulation working directory.",
    }


@mcp.tool()
def recommend_forcefield(molecule: str) -> dict:
    """
    Given a molecule name (common name, formula, or IUPAC), recommend the
    most appropriate built-in force field and provide literature guidance.

    For molecules NOT in the built-in library, returns structured guidance
    on how to find parameters from literature using Semantic Scholar.

    Args:
        molecule: e.g. "CO2", "methane", "PH3", "SO2", "water"
    """
    # Normalize common aliases
    aliases: dict[str, str] = {
        "carbon dioxide": "CO2",
        "methane": "CH4",
        "nitrogen": "N2",
        "water": "H2O",
        "h2o": "H2O",
        "co2": "CO2",
        "n2": "N2",
        "ch4": "CH4",
    }
    mol_key = aliases.get(molecule.lower(), molecule)

    # Check molecule meta
    for name, meta in MOLECULE_META.items():
        if name.lower() == mol_key.lower():
            ff = meta.get("paired_forcefield")
            return {
                "molecule": molecule,
                "found_in_library": True,
                "recommended_forcefield": ff,
                "model": meta.get("model"),
                "reference": FORCEFIELD_META.get(ff or "", {}).get("reference"),
                "action": f"Use get_forcefield_files('{ff}') to retrieve the force field files.",
            }

    # Not in library — provide search guidance
    return {
        "molecule": molecule,
        "found_in_library": False,
        "action_required": "Search literature for force field parameters",
        "search_queries": [
            f"{molecule} Lennard-Jones force field parameters epsilon sigma",
            f"{molecule} TraPPE force field molecular simulation",
            f"{molecule} adsorption MOF force field GCMC",
            f"{molecule} partial charges ab initio",
        ],
        "parameters_needed": {
            "LJ_parameters": {
                "epsilon_over_kB": "Well depth in Kelvin",
                "sigma": "Collision diameter in Angstroms",
            },
            "partial_charges": "Electron units (if molecule is polar)",
            "geometry": "Bond lengths and angles in Angstroms/degrees",
            "molecular_mass": "g/mol",
        },
        "file_format_reference": (
            "Once parameters are found, use get_forcefield_files('TraPPE-CO2') "
            "as a format reference to construct pseudo_atoms.def and "
            "force_field_mixing_rules.def for this molecule."
        ),
        "note": (
            f"'{molecule}' has no built-in force field. This is expected for "
            "non-standard adsorbates. Retrieve parameters from literature and "
            "construct the def files manually."
        ),
    }


# ─────────────────────────────────────────────────────────────────
# 4. Molecule definitions
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def list_available_molecules() -> dict:
    """
    List all built-in molecule definitions with metadata.
    Molecules not listed here require manual .def file construction.
    """
    return {"molecules": MOLECULE_META}


@mcp.tool()
def get_molecule_definition(molecule_name: str) -> dict:
    """
    Return the content of the RASPA2 molecule definition file (.def) for
    a built-in molecule.

    The file must be placed at:
      <workdir>/molecules/TraPPE/<MoleculeName>.def

    Args:
        molecule_name: e.g. "CO2", "N2", "CH4", "H2O", "helium"
    """
    if molecule_name not in MOLECULE_DEFINITIONS:
        return {
            "error": f"Molecule '{molecule_name}' not found in built-in library.",
            "available": list(MOLECULE_DEFINITIONS.keys()),
            "advice": (
                "For non-standard molecules, construct the .def file manually. "
                "Use get_molecule_definition('CO2') as a format reference."
            ),
        }

    return {
        "molecule_name": molecule_name,
        "metadata": MOLECULE_META.get(molecule_name, {}),
        "file": {
            "filename": f"{molecule_name}.def",
            "content": MOLECULE_DEFINITIONS[molecule_name],
        },
        "placement": f"Write to: <workdir>/molecules/TraPPE/{molecule_name}.def",
    }


# ─────────────────────────────────────────────────────────────────
# 5. Workspace setup
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def create_workspace(
    work_dir: str,
    framework_name: str,
    cif_source_path: str,
) -> dict:
    """
    Create a properly structured RASPA2 simulation workspace directory.

    RASPA2 expects a specific directory layout. This tool creates it and
    copies the CIF file into the right location.

    Structure created:
      <work_dir>/
        simulation.input        ← Claude writes this
        force_field_mixing_rules.def  ← Claude writes this
        pseudo_atoms.def        ← Claude writes this
        frameworks/
          <framework_name>/
            <framework_name>.cif
        molecules/
          TraPPE/               ← Claude writes .def files here

    Args:
        work_dir: Absolute path for the new simulation directory.
        framework_name: Name matching the CIF file (without .cif extension).
        cif_source_path: Absolute path to the existing CIF file.

    Security:
        ``work_dir`` must resolve to a path inside the allowed workspace base,
        controlled by the ``RASPA_MCP_WORKSPACE_BASE`` environment variable
        (default: ``~/raspa_workspaces``). This prevents an LLM from creating
        directories or copying files at arbitrary filesystem locations
        (e.g. ``/etc``, ``/root``) when this MCP runs as a privileged user.
    """
    import os

    work_path = Path(work_dir)
    cif_path = Path(cif_source_path)

    errors = []

    # --- workspace sandbox check ---------------------------------------
    base_env = os.environ.get("RASPA_MCP_WORKSPACE_BASE", "").strip()
    base_path = Path(base_env).expanduser() if base_env else (Path.home() / "raspa_workspaces")
    try:
        base_resolved = base_path.resolve()
        # Resolve work_path against parents that exist; for not-yet-created
        # directories we still want to know where it would land.
        work_resolved = Path(work_path).expanduser().resolve()
    except (OSError, RuntimeError) as e:
        return {"success": False, "errors": [f"Cannot resolve paths: {e}"]}

    try:
        work_resolved.relative_to(base_resolved)
    except ValueError:
        errors.append(
            f"work_dir {work_resolved} is outside allowed base {base_resolved}. "
            f"Set RASPA_MCP_WORKSPACE_BASE to override the allowed root."
        )

    if not cif_path.exists():
        errors.append(f"CIF file not found: {cif_source_path}")

    if errors:
        return {"success": False, "errors": errors}

    # Use the resolved, sandbox-checked path from here on.
    work_path = work_resolved
    # -------------------------------------------------------------------

    # Create directory structure
    dirs_created = []
    for subdir in [
        work_path,
        work_path / "frameworks" / framework_name,
        work_path / "molecules" / "TraPPE",
    ]:
        subdir.mkdir(parents=True, exist_ok=True)
        dirs_created.append(str(subdir))

    # Copy CIF file
    dest_cif = work_path / "frameworks" / framework_name / f"{framework_name}.cif"
    shutil.copy2(cif_path, dest_cif)

    return {
        "success": True,
        "work_dir": str(work_path),
        "directories_created": dirs_created,
        "cif_copied_to": str(dest_cif),
        "next_steps": [
            f"1. Write simulation.input to: {work_path / 'simulation.input'}",
            "2. Generate force_field.def via generate_force_field_def(work_dir, ...) "
            "— for the common case, no arguments produces the safe '3 zeros' overwrite file.",
            "3. Generate force_field_mixing_rules.def via "
            "generate_force_field_mixing_rules_def(work_dir, atom_types=[...]).",
            "4. Generate pseudo_atoms.def via generate_pseudo_atoms_def(work_dir, atoms=[...]).",
            "5. Generate per-molecule .def via generate_molecule_def(work_dir, molecule_name, ...).",
            "6. Optional but recommended: call inspect_cif and recommend_supercell on your CIF.",
            "7. Run preflight_workspace(work_dir) — only launch RASPA2 if it returns ok=True.",
            f"8. Run: cd {work_dir} && simulate",
        ],
        "raspa_env_note": (
            "Ensure RASPA_DIR is set and 'simulate' is in PATH on the compute server. "
            "Typical: export RASPA_DIR=/path/to/raspa2 && export PATH=$RASPA_DIR/bin:$PATH"
        ),
    }


# ─────────────────────────────────────────────────────────────────
# 6. Validation
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def validate_simulation_input(content: str) -> dict:
    """
    Validate the content of a RASPA2 simulation.input file BEFORE running.

    Returns errors (blocking — must fix) and warnings (advisory).
    Always call this after generating simulation.input and before running simulate.

    Args:
        content: Full text content of the simulation.input file.
    """
    result = _validate(content)
    return result.to_dict()


# ─────────────────────────────────────────────────────────────────
# 7. Output parsing
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def parse_raspa_output(output_dir: str) -> dict:
    """
    Parse RASPA2 output files and return structured results as JSON.

    Extracts: loading (mol/kg, mg/g, cm³STP/g), Henry coefficients,
    void fraction, energies (including Qst and mu_ex), and builds an
    isotherm table if multiple pressure points are detected.

    Args:
        output_dir: Path to the Output directory produced by RASPA2,
                    typically '<workdir>/Output/System_0/'.
    """
    return _parse_output(output_dir)


@mcp.tool()
def parse_rdf_output(
    output_dir: str,
    component_a: str = "",
    component_b: str = "",
) -> dict:
    """
    Parse RASPA2 radial distribution function (RDF) output files (3-3).

    RASPA2 writes RDF data to RDF_<A>_<B>.dat files when 'ComputeRDF yes'
    is set in simulation.input (requires NVT-MC or NVT-MD simulation).

    Returns r(Å) and g(r) arrays per pair, plus first-peak position —
    useful for identifying preferred adsorption sites and coordination shells.

    component_a / component_b: optional name filters (e.g. "CO2", "framework").
    Leave empty to return all RDF datasets in the output directory.

    Args:
        output_dir:   Path to RASPA2 Output directory.
        component_a:  Optional filter: only return pairs containing this name.
        component_b:  Optional filter: only return pairs containing this name.
    """
    return _parse_rdf_output(output_dir, component_a, component_b)


@mcp.tool()
def calculate_selectivity(
    loading_a: float,
    loading_b: float,
    feed_fraction_a: float,
    feed_fraction_b: float,
    label_a: str = "A",
    label_b: str = "B",
) -> dict:
    """
    Calculate adsorption selectivity S_AB from mixture GCMC results (4-4).

    Uses the adsorption selectivity definition:
      S_AB = (x_A / x_B) / (y_A / y_B)
    where x = adsorbed-phase mole fraction, y = gas-phase (feed) mole fraction.

    Inputs come from parse_raspa_output()["components"] for a GCMCMixture simulation.

    loading_a / loading_b: average loading of each component in mol/kg (or any
      consistent units — they cancel in the ratio).
    feed_fraction_a / feed_fraction_b: mole fractions in the feed gas (must sum to 1.0
      for a binary; for partial fractions in a larger mixture, pass the relevant pair).

    Returns S_AB > 1 means the material prefers A over B.
    S_AB < 1 means preference for B. S_AB = 1 means no selectivity.
    """
    if loading_b <= 0:
        return {"status": "error", "message": "loading_b must be > 0"}
    if feed_fraction_b <= 0:
        return {"status": "error", "message": "feed_fraction_b must be > 0"}

    x_a = loading_a / (loading_a + loading_b)
    x_b = 1.0 - x_a
    y_a = feed_fraction_a / (feed_fraction_a + feed_fraction_b)
    y_b = 1.0 - y_a

    if x_b <= 0 or y_b <= 0:
        return {"status": "error", "message": "Cannot compute selectivity: zero denominator"}

    s_ab = (x_a / x_b) / (y_a / y_b)

    return {
        "status": "ok",
        f"S_{label_a}{label_b}": round(s_ab, 4),
        "adsorbed_mole_fraction": {label_a: round(x_a, 6), label_b: round(x_b, 6)},
        "feed_mole_fraction": {label_a: round(y_a, 6), label_b: round(y_b, 6)},
        "interpretation": (
            f"The material prefers {label_a} over {label_b}" if s_ab > 1
            else f"The material prefers {label_b} over {label_a}" if s_ab < 1
            else "No selectivity between components"
        ),
    }


@mcp.tool()
def parse_msd_output(
    output_dir: str,
    molecule: str = "",
    diffusion_type: str = "self",
) -> dict:
    """
    Parse RASPA2 MSD files and compute self- or collective-diffusion coefficients (2-1/3-1/3-2).

    Requires a completed NVT-MD or NPT-MD simulation with 'ComputeMSD yes' set.
    RASPA2 writes MSDSelf_<mol>.dat (self-diffusion) and MSDCollective_<mol>.dat.

    The Einstein relation D = MSD(t) / 6t is fitted to the linear regime
    (latter 50% of trajectory). Result is given in A²/ps and m²/s.

    Typical self-diffusivities in MOFs:
      - Fast gas (H2, He):   10⁻⁸ – 10⁻⁷ m²/s
      - CO2, CH4 in wide pores: 10⁻⁹ – 10⁻⁸ m²/s
      - Slow diffusers (large MOF pores, tight channels): < 10⁻¹¹ m²/s

    Args:
        output_dir:      Path to RASPA2 Output directory.
        molecule:        Optional filter by molecule name (e.g. "CO2").
        diffusion_type:  "self" (MSDSelf) or "collective" (MSDCollective).
    """
    return _parse_msd_output(output_dir, molecule, diffusion_type)


@mcp.tool()
def parse_ti_output(output_dir: str) -> dict:
    """
    Parse RASPA2 Thermodynamic Integration (TI) output and compute ΔA (1-8).

    Expects one completed RASPA2 simulation per lambda value (0.0 → 1.0),
    each in its own subdirectory. The subdirectory name should contain the
    lambda value (e.g. 'lambda_0.3/', '0.3/', etc.).

    RASPA2 must be run with Lambda and LambdaDefinition set in simulation.input.
    Each output file must contain a line matching:
      Average <dU/dlambda>:  X.XXXXX +/- Y.YYYYY [K]

    KNOWN LIMITATION: The exact format of this line varies between RASPA2
    versions and build options. If status='no_ti_data' is returned, check:
      1. That the simulation used Lambda / LambdaDefinition keywords.
      2. That the RASPA2 version writes 'Average <dU/dlambda>'.
      3. That subdirectory names contain the numeric lambda value.
    In that case, extract dU/dlambda values manually from the output files
    and call numpy.trapezoid() directly.

    The function integrates ⟨∂U/∂λ⟩ over λ using the trapezoidal rule:
      ΔA = ∫₀¹ ⟨∂U/∂λ⟩ dλ  [K]  → ×R  → [kJ/mol]

    Fewer lambda points = less accuracy:
      - 3 points (0, 0.5, 1): rough estimate
      - 5 points: adequate for most cases
      - 11 points (0.0, 0.1, ..., 1.0): high accuracy

    Args:
        output_dir: Root directory containing per-lambda subdirectories.
    """
    return _parse_ti_output(output_dir)


@mcp.tool()
def parse_density_grid(
    output_dir: str,
    molecule: str = "",
    slice_axis: str = "z",
    slice_index: int = -1,
) -> dict:
    """
    Parse RASPA2 3D density grid files and extract a 2D slice (3-4).

    RASPA2 writes .grid files when the simulation.input contains:
      WriteDensityProfile3DVTKGrid   yes
      DensityAveragingTypeVTK        number_of_molecules

    The 3D grid is stored as Nx×Ny×Nz float values (row-major).
    This function returns the full grid metadata and ONE 2D slice.
    Pass the returned 'slice_data' field to plot_density_slice() to save a PNG.

    KNOWN LIMITATION: This tool returns a 2D cross-section only, NOT a full
    3D isosurface or volumetric render. For true 3D visualization (isosurfaces,
    volume rendering), export the raw 'slice_data' and use external tools such
    as VESTA, py3Dmol, or ParaView with the original .grid/.vtk file.
    To explore different planes, call this tool multiple times with different
    slice_axis ('x','y','z') and slice_index values.

    KNOWN LIMITATION: The .grid ASCII format written by RASPA2 has minor
    variations across versions (header line count differs). If parsing fails
    (status='no_grid_files' or 'warning' in dataset), verify that
    WriteDensityProfile3DVTKGrid is set and check the raw file header.

    Args:
        output_dir:  Path to RASPA2 Output (or parent) directory.
        molecule:    Optional filter on molecule name (e.g. "CO2").
        slice_axis:  Axis perpendicular to the slice: 'x'/'a', 'y'/'b', 'z'/'c'.
        slice_index: Grid-plane index along slice_axis; -1 = midpoint.
    """
    return _parse_density_grid(output_dir, molecule, slice_axis, slice_index)


@mcp.tool()
def plot_density_slice(
    slice_data: list[list[float]],
    output_path: str,
    title: str = "Density Slice",
    molecule: str = "",
    colormap: str = "hot",
    cell_lengths: list[float] | None = None,
    axes_labels: list[str] | None = None,
) -> dict:
    """
    Render a 2D density slice from parse_density_grid() as a heatmap PNG (3-4).

    slice_data is the 'slice_data' field from parse_density_grid() — a 2D list
    of float density values.

    cell_lengths: optional [La, Lb] in Å for axis tick labels.
    axes_labels:  optional [x_label, y_label], defaults to ["a (Å)", "b (Å)"].
    colormap:     matplotlib colormap name; 'hot', 'viridis', 'Blues' all work well.
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np

        data = np.array(slice_data)
        if data.ndim != 2:
            return {"status": "error", "message": "slice_data must be a 2D list"}

        fig, ax = plt.subplots(figsize=(6, 5))

        img_extent: tuple[float, float, float, float] | None = None
        if cell_lengths and len(cell_lengths) >= 2:
            img_extent = (0.0, float(cell_lengths[0]), 0.0, float(cell_lengths[1]))

        im = ax.imshow(
            data.T,
            origin="lower",
            cmap=colormap,
            aspect="equal",
            extent=img_extent,
            interpolation="bilinear",
        )
        plt.colorbar(im, ax=ax, label="Density (a.u.)")

        xl = axes_labels[0] if axes_labels and len(axes_labels) > 0 else None
        yl = axes_labels[1] if axes_labels and len(axes_labels) > 1 else None
        ax.set_xlabel(xl or ("a (Å)" if img_extent else "Grid a"), fontsize=11)
        ax.set_ylabel(yl or ("b (Å)" if img_extent else "Grid b"), fontsize=11)

        full_title = f"{molecule} — {title}" if molecule else title
        ax.set_title(full_title, fontsize=12)

        plt.tight_layout()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        return {
            "status": "ok",
            "path": output_path,
            "shape": list(data.shape),
            "density_max": float(data.max()),
            "density_mean": float(data.mean()),
        }
    except Exception as e:
        logger.exception("plot_density_slice failed")
        return {"status": "error", "message": str(e), "type": type(e).__name__}


# ─────────────────────────────────────────────────────────────────
# 8. Parameter documentation
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def get_parameter_docs(parameter_name: str | None = None) -> dict:
    """
    Return documentation for RASPA2 simulation.input parameters.

    Args:
        parameter_name: Specific parameter name (e.g. "CutOff", "EwaldPrecision"),
                        or None to get all parameters.
    """
    if parameter_name is None:
        return {
            "all_parameters": TEMPLATE_PARAMS,
            "common_mistakes": [
                "Pressure in RASPA2 is in Pascal, not bar. 1 bar = 100000 Pa.",
                "CutOff is in Angstroms. Ensure each unit cell axis >= 2 × CutOff "
                "(use recommend_supercell on the CIF if unsure).",
                "FrameworkName must exactly match the CIF filename (without .cif).",
                "MoleculeDefinition 'local' = $RASPA_DIR/share/raspa/molecules/local/, "
                "NOT your working directory. To load from ./molecules/TraPPE/, use "
                "'MoleculeDefinition TraPPE'.",
                "Forcefield 'local' means look for pseudo_atoms.def in working directory.",
                "SwapProbability must be > 0 for GCMC adsorption simulations.",
                "HeliumVoidFraction is required for correct mol/kg loading conversion.",
                "force_field.def vs force_field_mixing_rules.def — these are TWO different "
                "files. The first holds overwrite/cross-pair rules ('3 zeros' minimum), "
                "the second holds LJ epsilon/sigma per atom type. Mixing them up is the "
                "single most common cause of cryptic ':#' parse errors.",
                "ChargeMethod=Ewald + UseChargesFromCIFFile=no (or all-zero charges) "
                "wastes ~30% of compute. Set ChargeMethod=None for neutral systems.",
            ],
            "key_parameter_docs": {
                "ChargeMethod": (
                    "Method for electrostatics. Options: Ewald, Wolf, Truncated, None. "
                    "Use 'None' if your CIF has no charges and adsorbates are non-polar."
                ),
                "UseChargesFromCIFFile": (
                    "yes/no. When yes, RASPA2 reads _atom_site_charge from the CIF. "
                    "Pair with ChargeMethod=Ewald."
                ),
                "EwaldPrecision": (
                    "Relative precision for Ewald sum. 1e-5 for screening, 1e-6 production."
                ),
                "MoleculeDefinition": (
                    "Subdirectory under ./molecules/ where RASPA2 looks for <name>.def. "
                    "Avoid the value 'local' unless you really mean $RASPA_DIR/share/.../local/."
                ),
                "force_field.def": (
                    "Overwrite-rules file. Must exist when Forcefield is set. "
                    "Use generate_force_field_def() to produce a safe minimal version."
                ),
                "force_field_mixing_rules.def": (
                    "LJ epsilon/sigma per atom type plus the general mixing rule "
                    "(usually Lorentz-Berthelot). Use generate_force_field_mixing_rules_def()."
                ),
            },
        }

    doc = TEMPLATE_PARAMS.get(f"${{{parameter_name}}}")
    if doc is None:
        # Try without ${} wrapper
        doc = TEMPLATE_PARAMS.get(parameter_name)

    if doc is None:
        return {
            "error": f"Parameter '{parameter_name}' not found in documentation.",
            "tip": "Call get_parameter_docs() with no argument for full list.",
        }

    return {"parameter": parameter_name, "documentation": doc}


# ─────────────────────────────────────────────────────────────────
# 9. RASPA2 environment check and auto-install
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def check_raspa2_environment() -> dict:
    """
    Check whether RASPA2 is correctly installed and configured on this server.

    Verifies:
      1. 'simulate' binary is on PATH
      2. RASPA_DIR environment variable is set and valid
      3. Force field and molecule files exist under $RASPA_DIR

    Returns a full diagnostic report.
    If ready=False, run:  raspa-mcp-setup  (compiles RASPA2 from source).
    """
    return _check_env().to_dict()


# ─────────────────────────────────────────────────────────────────
# Plotting tools
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def plot_isotherm(
    isotherm_data: list[dict],
    output_path: str,
    molecule: str = "",
    framework: str = "",
    temperature_K: float = 298.0,  # noqa: N803
    pressure_unit: Literal["Pa", "bar", "kPa"] = "Pa",
    loading_key: str = "loading_mol_kg",
) -> dict:
    """
    Generate a single-MOF adsorption isotherm plot (PNG).

    isotherm_data is a list of dicts, each with at least:
      - a pressure field ("pressure_Pa", "pressure_bar", or "pressure_kPa")
      - a loading field (default key: "loading_mol_kg")

    Typical source: the "isotherm" list returned by parse_raspa_output() when
    multiple pressure-point simulations are run and their outputs placed in
    sub-directories named by pressure value.

    pressure_unit: unit of pressure values in isotherm_data (Pa, bar, kPa).
    loading_key:   key name for the loading column (e.g. "loading_mol_kg",
                   "loading_mg_g", "loading_cm3_STP_g").
    output_path:   absolute path where the PNG file will be saved.

    Returns: {"status": "ok", "path": ..., "n_points": ...}
             or {"status": "error", "message": ...}
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # non-interactive backend — required in server context
        import matplotlib.pyplot as plt
    except ImportError:
        return {"status": "error", "message": "matplotlib not installed; run: pip install matplotlib"}

    try:
        # --- unit conversion → bar for display ---
        _to_bar = {"Pa": 1e-5, "bar": 1.0, "kPa": 1e-2}
        factor = _to_bar.get(pressure_unit, 1e-5)

        pressure_field = {"Pa": "pressure_Pa", "bar": "pressure_bar", "kPa": "pressure_kPa"}.get(
            pressure_unit, "pressure_Pa"
        )

        pressures: list[float] = []
        loadings: list[float] = []
        for pt in isotherm_data:
            # accept both explicit field name and generic "pressure" key
            p_raw = pt.get(pressure_field) or pt.get("pressure")
            l_raw = pt.get(loading_key)
            if p_raw is None or l_raw is None:
                continue
            pressures.append(float(p_raw) * factor)
            loadings.append(float(l_raw))

        if not pressures:
            return {"status": "error", "message": "No valid data points found in isotherm_data"}

        # --- sort by pressure ---
        pairs = sorted(zip(pressures, loadings))
        pressures, loadings = zip(*pairs)  # type: ignore[assignment]

        # --- plot ---
        fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
        ax.plot(list(pressures), list(loadings), "o-", color="#2563EB", linewidth=2, markersize=6)

        loading_label = {
            "loading_mol_kg": "Loading (mol kg\u207b\u00b9)",
            "loading_mg_g": "Loading (mg g\u207b\u00b9)",
            "loading_cm3_STP_g": "Loading (cm\u00b3 STP g\u207b\u00b9)",
        }.get(loading_key, loading_key)

        ax.set_xlabel("Pressure (bar)", fontsize=12)
        ax.set_ylabel(loading_label, fontsize=12)

        title = f"{molecule} in {framework}" if molecule and framework else (molecule or framework or "Adsorption Isotherm")
        ax.set_title(f"{title}  ({temperature_K} K)", fontsize=13)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)

        plt.tight_layout()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        return {"status": "ok", "path": output_path, "n_points": len(pressures)}

    except Exception as e:
        logger.exception("plot_isotherm failed")
        return {"status": "error", "message": str(e), "type": type(e).__name__}


@mcp.tool()
def plot_isotherm_comparison(
    datasets: list[dict],
    output_path: str,
    molecule: str = "",
    temperature_K: float = 298.0,  # noqa: N803
    pressure_unit: Literal["Pa", "bar", "kPa"] = "Pa",
    loading_key: str = "loading_mol_kg",
) -> dict:
    """
    Generate a multi-MOF comparison isotherm plot (PNG) — all MOFs on one figure.

    datasets is a list of dicts, each representing one MOF:
      {
        "label":         "MIL-101(Cr)",        # legend label
        "isotherm_data": [{...}, {...}, ...]    # same format as plot_isotherm()
      }

    Designed for the final "top-N candidates" comparison step: pass in the
    isotherm_data from each MOF's parse_raspa_output() call together with a
    descriptive label, and receive a single publication-ready comparison figure.

    pressure_unit / loading_key: same semantics as plot_isotherm().
    output_path: absolute path where the PNG will be saved.

    Returns: {"status": "ok", "path": ..., "n_series": ...}
             or {"status": "error", "message": ...}
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return {"status": "error", "message": "matplotlib not installed; run: pip install matplotlib"}

    try:
        _to_bar = {"Pa": 1e-5, "bar": 1.0, "kPa": 1e-2}
        factor = _to_bar.get(pressure_unit, 1e-5)
        pressure_field = {"Pa": "pressure_Pa", "bar": "pressure_bar", "kPa": "pressure_kPa"}.get(
            pressure_unit, "pressure_Pa"
        )

        fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
        n_plotted = 0

        for idx, ds in enumerate(datasets):
            label = ds.get("label", f"MOF-{idx + 1}")
            pts = ds.get("isotherm_data", [])

            pressures: list[float] = []
            loadings: list[float] = []
            for pt in pts:
                p_raw = pt.get(pressure_field) or pt.get("pressure")
                l_raw = pt.get(loading_key)
                if p_raw is None or l_raw is None:
                    continue
                pressures.append(float(p_raw) * factor)
                loadings.append(float(l_raw))

            if not pressures:
                continue

            pairs = sorted(zip(pressures, loadings))
            pressures, loadings = zip(*pairs)  # type: ignore[assignment]

            color = _PLOT_COLORS[idx % len(_PLOT_COLORS)]
            marker = _PLOT_MARKERS[idx % len(_PLOT_MARKERS)]
            ax.plot(
                list(pressures), list(loadings),
                marker=marker, linestyle="-", color=color,
                linewidth=2, markersize=6, label=label,
            )
            n_plotted += 1

        if n_plotted == 0:
            return {"status": "error", "message": "No valid data series found in datasets"}

        loading_label = {
            "loading_mol_kg": "Loading (mol kg\u207b\u00b9)",
            "loading_mg_g": "Loading (mg g\u207b\u00b9)",
            "loading_cm3_STP_g": "Loading (cm\u00b3 STP g\u207b\u00b9)",
        }.get(loading_key, loading_key)

        ax.set_xlabel("Pressure (bar)", fontsize=12)
        ax.set_ylabel(loading_label, fontsize=12)

        title = f"{molecule} Adsorption Comparison" if molecule else "Adsorption Isotherm Comparison"
        ax.set_title(f"{title}  ({temperature_K} K)", fontsize=13)
        ax.legend(fontsize=9, framealpha=0.85)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)

        plt.tight_layout()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        return {"status": "ok", "path": output_path, "n_series": n_plotted}

    except Exception as e:
        logger.exception("plot_isotherm_comparison failed")
        return {"status": "error", "message": str(e), "type": type(e).__name__}


# ─────────────────────────────────────────────────────────────────
# 10. Full-custom workflow: file generators
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def generate_force_field_def(
    work_dir: str,
    rules_to_overwrite: list[dict] | None = None,
    interactions_to_define: list[dict] | None = None,
    mixing_rules_to_overwrite: list[dict] | None = None,
    return_only: bool = False,
) -> dict:
    """
    Generate ``force_field.def`` (the OVERWRITE-rules file) at ``work_dir``.

    With no extra arguments, produces the safe minimal "3 zeros" form, which is
    what most users actually need when their LJ parameters live in
    ``force_field_mixing_rules.def``.

    DO NOT confuse this file with ``force_field_mixing_rules.def`` — putting LJ
    epsilon/sigma here is the most common cause of cryptic ``:#`` parse errors
    from RASPA2. Use ``generate_force_field_mixing_rules_def`` for those.

    Args:
        work_dir: Workspace directory (must be inside ``RASPA_MCP_WORKSPACE_BASE``).
        rules_to_overwrite, interactions_to_define, mixing_rules_to_overwrite:
            Optional lists of ``{"line": str, "comment": str | None}`` entries.
        return_only: If True, do not touch disk; just return the rendered text.
    """
    try:
        if return_only:
            content = _render_ff(
                rules_to_overwrite=rules_to_overwrite,
                interactions_to_define=interactions_to_define,
                mixing_rules_to_overwrite=mixing_rules_to_overwrite,
            )
            return {"success": True, "dry_run": True, "content": content}
        return _write_ff(
            work_dir,
            rules_to_overwrite=rules_to_overwrite,
            interactions_to_define=interactions_to_define,
            mixing_rules_to_overwrite=mixing_rules_to_overwrite,
        )
    except Exception as e:
        logger.exception("generate_force_field_def failed")
        return {"success": False, "errors": [str(e)], "type": type(e).__name__}


@mcp.tool()
def generate_force_field_mixing_rules_def(
    work_dir: str,
    atom_types: list[dict],
    general_mixing_rule: str = "Lorentz-Berthelot",
    general_truncation: str = "shifted",
    tail_corrections: bool = True,
    return_only: bool = False,
) -> dict:
    """
    Generate ``force_field_mixing_rules.def`` — the LJ epsilon/sigma file.

    Each ``atom_types`` item: ``{"name": str, "epsilon_K": float, "sigma_A":
    float, "interaction": "lennard-jones", "comment": str | None}``.

    For the "shifted vs truncated" choice, ``"shifted"`` zeroes the LJ
    potential at the cutoff (smoother energies); ``"truncated"`` matches RASPA2
    legacy behaviour. Set ``tail_corrections=True`` for fluid-phase work.

    Args:
        work_dir: Workspace directory (sandboxed).
        atom_types: Required list of atom-type dicts.
        general_mixing_rule: ``Lorentz-Berthelot`` (default) or ``Jorgensen``.
        general_truncation: ``shifted`` (default) or ``truncated``.
        tail_corrections: Apply analytic LJ tail corrections.
        return_only: Dry-run; do not write to disk.
    """
    try:
        if return_only:
            content = _render_mix(
                atom_types=atom_types,
                general_mixing_rule=general_mixing_rule,
                general_truncation=general_truncation,
                tail_corrections=tail_corrections,
            )
            return {"success": True, "dry_run": True, "content": content}
        return _write_mix(
            work_dir,
            atom_types=atom_types,
            general_mixing_rule=general_mixing_rule,
            general_truncation=general_truncation,
            tail_corrections=tail_corrections,
        )
    except Exception as e:
        logger.exception("generate_force_field_mixing_rules_def failed")
        return {"success": False, "errors": [str(e)], "type": type(e).__name__}


@mcp.tool()
def generate_pseudo_atoms_def(
    work_dir: str,
    atoms: list[dict],
    return_only: bool = False,
) -> dict:
    """
    Generate ``pseudo_atoms.def`` — the atom registry. Every atom-type symbol
    that appears in the CIF, in ``force_field_mixing_rules.def``, or in any
    molecule ``.def`` must be listed here.

    Each ``atoms`` item must include at minimum: ``name``, ``chem``, ``mass``,
    ``charge``. Optional keys with defaults: ``print=yes``, ``print_as=name``,
    ``oxidation=0``, ``polarization=0``, ``b_factor=1.0``, ``radii=1.0``,
    ``connectivity=0``, ``anisotropic=0``, ``anisotropic_type='absolute'``,
    ``tinker_type=0``.
    """
    try:
        if return_only:
            content = _render_pa(atoms)
            return {"success": True, "dry_run": True, "content": content}
        return _write_pa(work_dir, atoms)
    except Exception as e:
        logger.exception("generate_pseudo_atoms_def failed")
        return {"success": False, "errors": [str(e)], "type": type(e).__name__}


@mcp.tool()
def generate_molecule_def(
    work_dir: str,
    molecule_name: str,
    critical_temperature_K: float,
    critical_pressure_Pa: float,
    acentric_factor: float,
    atoms: list[dict],
    bonds: list[list] | None = None,
    bends: list[list] | None = None,
    torsions: list[list] | None = None,
    rigid: bool = True,
    n_groups: int = 1,
    subdirectory: str = "TraPPE",
    return_only: bool = False,
) -> dict:
    """
    Generate a per-molecule ``.def`` file at
    ``<work_dir>/molecules/<subdirectory>/<molecule_name>.def``.

    ``atoms`` items: ``{"type": str, "x": float, "y": float, "z": float}``.
    Coords are Å relative to the molecule centre of mass.

    ``bonds`` items: ``[i, j, "RIGID_BOND"]`` (or any RASPA2 bond keyword).
    ``bends`` items: ``[i, j, k, "<bend_keyword>"]``.
    ``torsions`` items: ``[i, j, k, l, "<torsion_keyword>"]``.

    Set ``MoleculeDefinition <subdirectory>`` in simulation.input so RASPA2
    finds this file. Avoid ``MoleculeDefinition local`` — that points to
    ``$RASPA_DIR/share/raspa/molecules/local/``, not your workspace.
    """
    try:
        # Coerce list[list] to list[tuple] for the renderer.
        b_t = [tuple(b) for b in (bonds or [])]
        be_t = [tuple(b) for b in (bends or [])]
        to_t = [tuple(t) for t in (torsions or [])]
        if return_only:
            content = _render_mol(
                molecule_name=molecule_name,
                critical_temperature_K=critical_temperature_K,
                critical_pressure_Pa=critical_pressure_Pa,
                acentric_factor=acentric_factor,
                atoms=atoms,
                bonds=b_t,
                bends=be_t,
                torsions=to_t,
                rigid=rigid,
                n_groups=n_groups,
            )
            return {"success": True, "dry_run": True, "content": content}
        return _write_mol(
            work_dir,
            molecule_name=molecule_name,
            subdirectory=subdirectory,
            critical_temperature_K=critical_temperature_K,
            critical_pressure_Pa=critical_pressure_Pa,
            acentric_factor=acentric_factor,
            atoms=atoms,
            bonds=b_t,
            bends=be_t,
            torsions=to_t,
            rigid=rigid,
            n_groups=n_groups,
        )
    except Exception as e:
        logger.exception("generate_molecule_def failed")
        return {"success": False, "errors": [str(e)], "type": type(e).__name__}


# ─────────────────────────────────────────────────────────────────
# 11. CIF inspection (requires ASE)
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def inspect_cif(cif_path: str) -> dict:
    """
    Inspect a CIF file: formula, cell parameters, charge column status,
    minimum interatomic distance. Flags common pitfalls (no charges,
    non-neutral cell, atom overlap).

    Use before launching a simulation against an unfamiliar CIF.
    """
    try:
        from raspa_mcp.cif_tools import inspect_cif as _inspect
        return _inspect(cif_path)
    except ImportError as e:
        return {
            "status": "error",
            "message": (
                "ASE is required for inspect_cif. Install via "
                "'pip install ase>=3.22' or rerun setup_mcps.sh."
            ),
            "type": type(e).__name__,
            "detail": str(e),
        }
    except Exception as e:
        logger.exception("inspect_cif failed")
        return {"status": "error", "message": str(e), "type": type(e).__name__}


@mcp.tool()
def recommend_supercell(cif_path: str, cutoff_A: float = 12.0) -> dict:
    """
    Recommend an integer supercell (nx, ny, nz) such that each axis is at
    least 2 × ``cutoff_A`` (the RASPA2 minimum-image rule). Also recommends
    a ChargeMethod based on whether the CIF has non-zero charges.
    """
    try:
        from raspa_mcp.cif_tools import recommend_supercell as _rec
        return _rec(cif_path, cutoff_A=cutoff_A)
    except ImportError as e:
        return {
            "status": "error",
            "message": (
                "ASE is required for recommend_supercell. Install via "
                "'pip install ase>=3.22' or rerun setup_mcps.sh."
            ),
            "type": type(e).__name__,
            "detail": str(e),
        }
    except Exception as e:
        logger.exception("recommend_supercell failed")
        return {"status": "error", "message": str(e), "type": type(e).__name__}


# ─────────────────────────────────────────────────────────────────
# 12. Preflight: cross-file workspace check
# ─────────────────────────────────────────────────────────────────

@mcp.tool()
def preflight_workspace(work_dir: str) -> dict:
    """
    Validate a workspace directory before launching ``simulate``.

    Checks:
      * simulation.input exists and passes validate_simulation_input
      * the CIF named by FrameworkName exists at frameworks/<name>/<name>.cif
      * force_field.def exists and is in overwrite-rules format (NOT mixing)
      * force_field_mixing_rules.def exists and lists atom types
      * pseudo_atoms.def covers every atom type used by the mixing-rules file
      * each Component in simulation.input has a matching molecule .def

    Returns ``{"ok": bool, "errors": [...], "warnings": [...], "findings": {...}}``.
    """
    try:
        return _preflight(work_dir)
    except Exception as e:
        logger.exception("preflight_workspace failed")
        return {"ok": False, "errors": [str(e)], "warnings": [], "findings": {}}


# ─────────────────────────────────────────────────────────────────
# 13. Workflow recipes
# ─────────────────────────────────────────────────────────────────

_WORKFLOW_RECIPES: dict[str, dict] = {
    "custom_mof_gcmc": {
        "description": (
            "Run GCMC adsorption on a user-supplied MOF CIF with a custom "
            "force field and a custom adsorbate molecule."
        ),
        "steps": [
            "1. inspect_cif(cif_path) — sanity-check formula, cell, charges, overlap.",
            "2. recommend_supercell(cif_path, cutoff_A=12.0) — get UnitCells line.",
            "3. create_workspace(work_dir, framework_name, cif_source_path).",
            "4. generate_force_field_def(work_dir) — minimal '3 zeros' overwrite file.",
            "5. generate_force_field_mixing_rules_def(work_dir, atom_types=[...]) — "
            "list every atom type from the CIF + every adsorbate atom type.",
            "6. generate_pseudo_atoms_def(work_dir, atoms=[...]) — same coverage.",
            "7. generate_molecule_def(work_dir, molecule_name, ...) for each adsorbate.",
            "8. Write simulation.input — set MoleculeDefinition <subdir>, ChargeMethod, "
            "UnitCells (from step 2).",
            "9. validate_simulation_input(content) on the simulation.input text.",
            "10. preflight_workspace(work_dir) — must return ok=True before launch.",
            "11. cd <work_dir> && simulate (or your scheduler).",
            "12. parse_raspa_output(work_dir) when done.",
        ],
        "common_pitfalls": [
            "Putting LJ epsilon/sigma in force_field.def — that file is overwrite-rules only.",
            "Setting MoleculeDefinition local — points to $RASPA_DIR/share, not your workspace.",
            "ChargeMethod=Ewald with all-zero charges in the CIF wastes time; use None.",
            "UnitCells too small — each axis must be ≥ 2 × CutOff.",
        ],
    },
    "henry_widom": {
        "description": "Henry coefficient via Widom insertion at infinite dilution.",
        "steps": [
            "1–7. Same as custom_mof_gcmc steps 1–7.",
            "8. Write simulation.input with SimulationType MonteCarlo and "
            "WidomProbability 1.0 in the Component block.",
            "9. preflight_workspace then launch.",
            "10. parse_raspa_output(work_dir) — Henry coefficient is reported.",
        ],
    },
    "diffusion_md": {
        "description": "Self-diffusion coefficient from NVT-MD + MSD analysis.",
        "steps": [
            "1–7. Same as custom_mof_gcmc steps 1–7.",
            "8. Write simulation.input with SimulationType MolecularDynamics, "
            "Ensemble NVT, sensible TimeStep (e.g. 0.5 fs), Print/Sample MSD frequency.",
            "9. preflight_workspace, launch.",
            "10. parse_msd_output(work_dir, molecule=<name>, diffusion_type='self').",
        ],
    },
}


@mcp.tool()
def get_workflow_recipe(scenario: str | None = None) -> dict:
    """
    Return an ordered, tool-by-tool recipe for a common RASPA2 scenario.

    Args:
        scenario: One of ``custom_mof_gcmc``, ``henry_widom``, ``diffusion_md``,
                  or None to list all available scenarios.
    """
    if scenario is None:
        return {
            "scenarios": {
                k: {"description": v["description"]} for k, v in _WORKFLOW_RECIPES.items()
            }
        }
    if scenario not in _WORKFLOW_RECIPES:
        return {
            "error": f"Unknown scenario {scenario!r}.",
            "available": sorted(_WORKFLOW_RECIPES.keys()),
        }
    return {"scenario": scenario, **_WORKFLOW_RECIPES[scenario]}


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

def main() -> None:
    # Startup probe: report RASPA2 status (visible in server logs)
    env = _check_env()
    if env.ready:
        logger.info("RASPA2 ready: {} | RASPA_DIR={}", env.simulate_path, env.raspa_dir)
    else:
        logger.warning(
            "RASPA2 NOT ready: {}. Run 'raspa-mcp-setup' to install RASPA2 from source.",
            "; ".join(env.issues),
        )
    mcp.run()


if __name__ == "__main__":
    main()
