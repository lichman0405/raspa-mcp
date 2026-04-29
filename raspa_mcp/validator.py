"""
raspa_mcp.validator — simulation.input file validation.

Checks syntax and required fields before Claude hands the file to RASPA2.
Returns structured error messages that Claude can act on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "summary": "OK" if self.valid else f"{len(self.errors)} error(s) found",
        }


# ─────────────────────────────────────────────────────────────────
# Required and recommended fields per simulation type
# ─────────────────────────────────────────────────────────────────

_REQUIRED_FIELDS = {
    "MonteCarlo": [
        "SimulationType",
        "NumberOfCycles",
        "NumberOfInitializationCycles",
        "Forcefield",
        "CutOff",
        "Framework",
        "Component",
    ],
    "MolecularDynamics": [
        "SimulationType",
        "NumberOfCycles",
        "Forcefield",
        "CutOff",
        "Framework",
        "Component",
        "Ensemble",
        "TimeStep",
    ],
}

_RECOMMENDED_FIELDS = [
    "PrintEvery",
    "RestartFile",
]

_VALID_SIM_TYPES = {"MonteCarlo", "MolecularDynamics"}
_VALID_ENSEMBLES = {"NVT", "NPT", "NVE", "muVT"}
_VALID_CHARGE_METHODS = {"Ewald", "Wolf", "None", "Truncated"}


def _extract_field(content: str, field_name: str) -> str | None:
    """Extract the first value of a named field from simulation.input content."""
    pattern = rf"^\s*{re.escape(field_name)}\s+(\S+)"
    match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
    return match.group(1) if match else None


def validate_simulation_input(content: str) -> ValidationResult:
    """
    Validate the content of a RASPA2 simulation.input file.

    Returns a ValidationResult with errors (blocking) and warnings (advisory).
    """
    result = ValidationResult(valid=True)
    errors = result.errors
    warnings = result.warnings

    if not content.strip():
        errors.append("File is empty.")
        result.valid = False
        return result

    # --- SimulationType ---
    sim_type = _extract_field(content, "SimulationType")
    if sim_type is None:
        errors.append("Missing required field: SimulationType")
    elif sim_type not in _VALID_SIM_TYPES:
        errors.append(
            f"SimulationType '{sim_type}' is not valid. "
            f"Must be one of: {', '.join(_VALID_SIM_TYPES)}"
        )
    else:
        # Required fields for this sim type
        for f in _REQUIRED_FIELDS.get(sim_type, []):
            # 'Framework' and 'Component' are block headers, not key-value pairs
            if f in ("Framework", "Component"):
                if not re.search(rf"^\s*{f}\s+\d", content, re.MULTILINE):
                    errors.append(f"Missing required block: '{f} <index>'")
            elif _extract_field(content, f) is None:
                errors.append(f"Missing required field: {f}")

    # --- NumberOfCycles sanity ---
    cycles = _extract_field(content, "NumberOfCycles")
    if cycles is not None:
        try:
            n = int(cycles)
            if n < 1000:
                warnings.append(
                    f"NumberOfCycles={n} is very low (< 1000). "
                    "Results may not be converged."
                )
            if n > 1_000_000:
                warnings.append(
                    f"NumberOfCycles={n} is very high. "
                    "Confirm this is intentional."
                )
        except ValueError:
            errors.append(f"NumberOfCycles value '{cycles}' is not an integer.")

    # --- CutOff sanity ---
    cutoff = _extract_field(content, "CutOff")
    if cutoff is not None:
        try:
            co = float(cutoff)
            if co < 8.0:
                warnings.append(
                    f"CutOff={co} Å is unusually small (recommend >= 12.0 Å)."
                )
            if co > 20.0:
                warnings.append(
                    f"CutOff={co} Å is very large. Make sure unit cell is "
                    "large enough (each axis >= 2 × CutOff)."
                )
        except ValueError:
            errors.append(f"CutOff value '{cutoff}' is not a number.")

    # --- Temperature ---
    temp = _extract_field(content, "ExternalTemperature")
    if temp is not None:
        try:
            t = float(temp)
            if t <= 0:
                errors.append(f"ExternalTemperature={t} K is not physical (must be > 0).")
            if t > 2000:
                warnings.append(f"ExternalTemperature={t} K is unusually high.")
        except ValueError:
            errors.append(f"ExternalTemperature value '{temp}' is not a number.")

    # --- ChargeMethod / EwaldPrecision consistency ---
    charge_method = _extract_field(content, "ChargeMethod")
    if charge_method is not None and charge_method not in _VALID_CHARGE_METHODS:
        errors.append(
            f"ChargeMethod '{charge_method}' is not recognised. "
            f"Valid: {', '.join(_VALID_CHARGE_METHODS)}"
        )
    if charge_method == "Ewald":
        if _extract_field(content, "EwaldPrecision") is None:
            warnings.append(
                "ChargeMethod=Ewald but EwaldPrecision is not set. "
                "Default will be used (1e-6 recommended). Note Ewald has a "
                "non-trivial setup cost; consider 1e-5 for screening runs."
            )

    # --- ChargeMethod / UseChargesFromCIFFile consistency ---
    use_cif_charges = _extract_field(content, "UseChargesFromCIFFile")
    if use_cif_charges and use_cif_charges.lower() == "yes" and charge_method == "None":
        warnings.append(
            "UseChargesFromCIFFile=yes but ChargeMethod=None. The CIF charges "
            "will be loaded but never used. Either set ChargeMethod=Ewald or "
            "set UseChargesFromCIFFile=no."
        )

    # --- MoleculeDefinition local trap ---
    mol_def = _extract_field(content, "MoleculeDefinition")
    if mol_def and mol_def.lower() == "local":
        warnings.append(
            "MoleculeDefinition=local makes RASPA2 look in "
            "$RASPA_DIR/share/raspa/molecules/local/, NOT in your working "
            "directory. To load .def files from ./molecules/<name>/ inside "
            "your workspace, use MoleculeDefinition=<name> (e.g. 'TraPPE')."
        )

    # --- ChargeMethod=Ewald with no charges in pseudo_atoms is wasteful ---
    # We only see simulation.input here; cross-file checks live in preflight_workspace.

    # --- Recommended fields ---
    for f in _RECOMMENDED_FIELDS:
        if _extract_field(content, f) is None:
            warnings.append(f"Recommended field '{f}' is not set.")

    # --- Swap probability check for GCMC ---
    if sim_type == "MonteCarlo":
        if "SwapProbability" not in content:
            warnings.append(
                "SwapProbability not found in Component block. "
                "For GCMC adsorption, SwapProbability >= 1.0 is required."
            )

    # --- 1-6: VolumeChangeProbability check for NPT-MC ---
    if sim_type == "MonteCarlo":
        if _extract_field(content, "ExternalPressure") is not None:
            if "VolumeChangeProbability" not in content:
                warnings.append(
                    "ExternalPressure is set but VolumeChangeProbability is missing. "
                    "For NPT-MC, add 'VolumeChangeProbability 0.05' to the Component block."
                )

    # --- 4-2: Multi-component mixture validation ---
    component_blocks = re.findall(r"^\s*Component\s+\d+", content, re.MULTILINE)
    n_components = len(component_blocks)
    if n_components > 1:
        # Mixture: PartialPressure should be used instead of ExternalPressure
        if _extract_field(content, "ExternalPressure") is not None and "PartialPressure" not in content:
            warnings.append(
                f"Found {n_components} Component blocks (mixture) but ExternalPressure is used. "
                "For multi-component GCMC, use 'PartialPressure' per component instead."
            )
        # Each component should have SwapProbability for GCMC mixture
        if sim_type == "MonteCarlo":
            swap_count = len(re.findall(r"SwapProbability", content))
            if swap_count < n_components:
                warnings.append(
                    f"Found {n_components} components but only {swap_count} SwapProbability entries. "
                    "Each component in a GCMC mixture should have its own SwapProbability."
                )

    result.valid = len(errors) == 0
    return result


# ─────────────────────────────────────────────────────────────────
# Preflight: cross-file checks against an actual workspace directory
# ─────────────────────────────────────────────────────────────────

_FORCE_FIELD_DEF_OVERWRITE_HINT = re.compile(
    r"number of (?:rules|interactions)", re.IGNORECASE
)
_MIXING_RULES_INTERACTIONS_HINT = re.compile(
    r"number of defined interactions", re.IGNORECASE
)


def preflight_workspace(work_dir: str) -> dict:
    """Cross-file sanity check on a RASPA2 workspace directory.

    Verifies that simulation.input, the two force-field files, pseudo_atoms.def
    and any referenced molecule .def files exist at the right paths and look
    coherent with each other. Use right before launching ``simulate``.
    """
    from pathlib import Path

    root = Path(work_dir).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    findings: dict = {"work_dir": str(root)}

    # simulation.input
    sim_input = root / "simulation.input"
    if not sim_input.is_file():
        errors.append(f"Missing simulation.input at {sim_input}.")
        return {
            "ok": False,
            "errors": errors,
            "warnings": warnings,
            "findings": findings,
        }
    sim_text = sim_input.read_text(errors="replace")

    # Run the in-file validator first.
    sub = validate_simulation_input(sim_text)
    errors.extend(sub.errors)
    warnings.extend(sub.warnings)

    # Framework / CIF
    framework_name = _extract_field(sim_text, "FrameworkName")
    if framework_name:
        cif_path = root / "frameworks" / framework_name / f"{framework_name}.cif"
        if not cif_path.is_file():
            # Some users put the CIF flat in the work_dir.
            alt = root / f"{framework_name}.cif"
            if not alt.is_file():
                errors.append(
                    f"FrameworkName={framework_name} but CIF not found at "
                    f"{cif_path} (also checked {alt})."
                )
            else:
                findings["cif_path"] = str(alt)
                warnings.append(
                    f"CIF is at workspace root ({alt}). RASPA2 prefers "
                    f"frameworks/{framework_name}/{framework_name}.cif."
                )
        else:
            findings["cif_path"] = str(cif_path)

    # force_field.def
    ff_def = root / "force_field.def"
    if not ff_def.is_file():
        warnings.append(
            "force_field.def is missing. RASPA2 needs it (even an empty "
            "'3 zeros' file) when Forcefield is set. "
            "Use generate_force_field_def to create the minimal form."
        )
    else:
        ff_text = ff_def.read_text(errors="replace")
        if not _FORCE_FIELD_DEF_OVERWRITE_HINT.search(ff_text):
            errors.append(
                "force_field.def does not look like an overwrite-rules file "
                "(no 'Number of rules/interactions' headers found). It is the "
                "wrong format — possibly mixed up with force_field_mixing_rules.def."
            )
        elif _MIXING_RULES_INTERACTIONS_HINT.search(ff_text) and "epsilon" in ff_text.lower():
            warnings.append(
                "force_field.def appears to contain LJ epsilon/sigma values. "
                "Those belong in force_field_mixing_rules.def. force_field.def "
                "should only list overwrite/cross-pair rules."
            )

    # force_field_mixing_rules.def
    mix_def = root / "force_field_mixing_rules.def"
    declared_atom_types: set[str] = set()
    if not mix_def.is_file():
        errors.append(
            "force_field_mixing_rules.def is missing. RASPA2 needs LJ "
            "epsilon/sigma per atom type to compute interactions."
        )
    else:
        mix_text = mix_def.read_text(errors="replace")
        # Crude: collect the first non-comment whitespace-separated word per
        # data line as an atom-type name.
        for line in mix_text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            tok = s.split()
            if len(tok) >= 4 and not s[0].isdigit():
                declared_atom_types.add(tok[0])

    # pseudo_atoms.def
    pa_def = root / "pseudo_atoms.def"
    pseudo_atom_types: set[str] = set()
    if not pa_def.is_file():
        errors.append("pseudo_atoms.def is missing.")
    else:
        for line in pa_def.read_text(errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            tok = s.split()
            # Header line may be a single integer (count). Skip it.
            if len(tok) >= 4 and not s.split()[0].isdigit():
                pseudo_atom_types.add(tok[0])

    if declared_atom_types and pseudo_atom_types:
        missing = declared_atom_types - pseudo_atom_types
        if missing:
            errors.append(
                "Atom type(s) declared in force_field_mixing_rules.def but "
                f"missing from pseudo_atoms.def: {sorted(missing)}"
            )

    # MoleculeDefinition + Component
    mol_def_kw = _extract_field(sim_text, "MoleculeDefinition")
    components = re.findall(
        r"\bMoleculeName\s+(\S+)", sim_text, re.IGNORECASE
    )
    findings["components"] = components
    findings["pseudo_atom_types"] = sorted(pseudo_atom_types)
    findings["mixing_atom_types"] = sorted(declared_atom_types)

    if components and mol_def_kw and mol_def_kw.lower() != "local":
        for comp in components:
            comp_path = root / "molecules" / mol_def_kw / f"{comp}.def"
            if not comp_path.is_file():
                errors.append(
                    f"Component '{comp}' references {comp_path} which does "
                    "not exist. Use generate_molecule_def to create it."
                )

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
    }
