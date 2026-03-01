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
                "Default will be used (1e-6 recommended)."
            )

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
