"""
Basic smoke tests for raspa_mcp.
Run: pytest tests/ -q
"""

import tempfile
from pathlib import Path

from raspa_mcp.data.forcefields import MIXING_RULES, PSEUDO_ATOMS
from raspa_mcp.data.molecules import MOLECULE_DEFINITIONS
from raspa_mcp.data.templates import TEMPLATES
from raspa_mcp.installer import (
    RaspaEnvironment,
    _build_env_setup,
    _detect_shell_rc,
    check_environment,
)
from raspa_mcp.parser import _parse_energy, _parse_henry, parse_output, parse_rdf_output
from raspa_mcp.server import plot_isotherm, plot_isotherm_comparison
from raspa_mcp.validator import validate_simulation_input

# ─────────────────────────────────────────────────────────────────
# Template tests
# ─────────────────────────────────────────────────────────────────

def test_all_templates_present():
    for t in ["GCMC", "Widom", "MD", "VoidFraction"]:
        assert t in TEMPLATES
        assert len(TEMPLATES[t]) > 100


def test_gcmc_template_has_required_placeholders():
    tpl = TEMPLATES["GCMC"]
    for ph in ["${FRAMEWORK_NAME}", "${TEMPERATURE}", "${PRESSURE}", "${MOLECULE}"]:
        assert ph in tpl, f"Placeholder {ph} missing from GCMC template"


# ─────────────────────────────────────────────────────────────────
# Validator tests
# ─────────────────────────────────────────────────────────────────

VALID_GCMC = """\
SimulationType                 MonteCarlo
NumberOfCycles                 10000
NumberOfInitializationCycles   2000
PrintEvery                     1000
RestartFile                    no
Forcefield                     local
CutOff                         12.0

Framework 0
  FrameworkName                ZIF-8
  UnitCells                    2 2 2
  ExternalTemperature          298.0
  ExternalPressure             100000

Component 0 MoleculeName       CO2
  MoleculeDefinition           local
  SwapProbability              1.0
  CreateNumberOfMolecules      0
"""


def test_valid_gcmc_passes():
    result = validate_simulation_input(VALID_GCMC).to_dict()
    assert result["valid"] is True
    assert result["errors"] == []


def test_missing_simtype_fails():
    bad = VALID_GCMC.replace("SimulationType                 MonteCarlo\n", "")
    result = validate_simulation_input(bad).to_dict()
    assert result["valid"] is False
    assert any("SimulationType" in e for e in result["errors"])


def test_empty_content_fails():
    result = validate_simulation_input("").to_dict()
    assert result["valid"] is False


def test_low_cycles_warns():
    low = VALID_GCMC.replace("NumberOfCycles                 10000",
                              "NumberOfCycles                 100")
    result = validate_simulation_input(low).to_dict()
    assert any("100" in w for w in result["warnings"])


def test_negative_temperature_fails():
    bad = VALID_GCMC.replace("ExternalTemperature          298.0",
                              "ExternalTemperature          -10.0")
    result = validate_simulation_input(bad).to_dict()
    assert result["valid"] is False


# ─────────────────────────────────────────────────────────────────
# Force field data tests
# ─────────────────────────────────────────────────────────────────

def test_co2_forcefield_present():
    assert "TraPPE-CO2" in PSEUDO_ATOMS
    assert "O_co2" in PSEUDO_ATOMS["TraPPE-CO2"]
    assert "C_co2" in PSEUDO_ATOMS["TraPPE-CO2"]


def test_co2_mixing_rules_present():
    assert "TraPPE-CO2" in MIXING_RULES
    assert "Lorentz-Berthelot" in MIXING_RULES["TraPPE-CO2"]
    assert "O_co2" in MIXING_RULES["TraPPE-CO2"]


def test_all_ffs_have_mixing_rules():
    for ff in ["TraPPE-CO2", "TraPPE-N2", "TraPPE-CH4"]:
        assert ff in MIXING_RULES, f"{ff} missing mixing rules"


# ─────────────────────────────────────────────────────────────────
# Molecule definition tests
# ─────────────────────────────────────────────────────────────────

def test_co2_molecule_defined():
    assert "CO2" in MOLECULE_DEFINITIONS
    assert "C_co2" in MOLECULE_DEFINITIONS["CO2"]
    assert "O_co2" in MOLECULE_DEFINITIONS["CO2"]
    assert "RIGID_BOND" in MOLECULE_DEFINITIONS["CO2"]


def test_helium_defined():
    assert "helium" in MOLECULE_DEFINITIONS


# ─────────────────────────────────────────────────────────────────
# Parser tests (no actual output files — test empty dir handling)
# ─────────────────────────────────────────────────────────────────

def test_parse_nonexistent_dir():
    result = parse_output("/nonexistent/path/Output")
    assert result["status"] == "no_output_found"
    assert result["results"] == []


def test_parse_empty_dir(tmp_path):
    result = parse_output(str(tmp_path))
    assert result["status"] == "no_output_found"


# ─────────────────────────────────────────────────────────────────
# Installer / environment check tests
# ─────────────────────────────────────────────────────────────────

def test_check_environment_returns_valid_structure():
    """check_environment() must always return a well-formed dict."""
    result = check_environment()
    assert isinstance(result, RaspaEnvironment)
    d = result.to_dict()
    for key in ("ready", "simulate_found", "raspa_dir_set", "issues", "summary"):
        assert key in d, f"Missing key '{key}' in environment check result"


def test_check_environment_issues_list_when_not_ready():
    """If RASPA2 is not installed, issues list must be non-empty."""
    result = check_environment()
    if not result.ready:
        assert len(result.issues) > 0, (
            "ready=False but no issues reported — diagnostic is broken"
        )


def test_check_environment_summary_matches_ready():
    result = check_environment()
    d = result.to_dict()
    if d["ready"]:
        assert "ready" in d["summary"].lower()
    else:
        assert "not ready" in d["summary"].lower()


def test_detect_shell_rc_returns_valid_path():
    shell_name, rc_file = _detect_shell_rc()
    assert isinstance(shell_name, str)
    assert isinstance(rc_file, str)
    assert rc_file.startswith("/") or rc_file[1:3] == ":\\"   # Unix abs or Windows abs


def test_build_env_setup_structure():
    result = _build_env_setup("/opt/raspa2")
    for key in ("detected_shell", "rc_file", "export_lines", "reload_command", "one_liner"):
        assert key in result, f"Missing key '{key}' in env_setup"
    assert len(result["export_lines"]) >= 2
    assert "RASPA_DIR" in result["export_lines"][0]


def test_build_env_setup_fish_syntax(monkeypatch):
    monkeypatch.setenv("SHELL", "/usr/bin/fish")
    result = _build_env_setup("/opt/raspa2")
    assert result["detected_shell"] == "fish"
    assert all("set -gx" in line for line in result["export_lines"])


# ─────────────────────────────────────────────────────────────────
# Plotting tool tests
# ─────────────────────────────────────────────────────────────────

_FAKE_ISOTHERM = [
    {"pressure_Pa": 1e4,  "loading_mol_kg": 1.2},
    {"pressure_Pa": 1e5,  "loading_mol_kg": 3.8},
    {"pressure_Pa": 5e5,  "loading_mol_kg": 6.1},
    {"pressure_Pa": 1e6,  "loading_mol_kg": 7.9},
]


def test_plot_isotherm_creates_png():
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "isotherm.png")
        result = plot_isotherm(
            isotherm_data=_FAKE_ISOTHERM,
            output_path=out,
            molecule="CO2",
            framework="MIL-101-Cr",
            temperature_K=298.0,
        )
        assert result["status"] == "ok", result.get("message")
        assert result["path"] == out
        assert result["n_points"] == 4
        assert Path(out).exists()
        assert Path(out).stat().st_size > 10_000  # real PNG, not empty


def test_plot_isotherm_empty_data_returns_error():
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "isotherm.png")
        result = plot_isotherm(isotherm_data=[], output_path=out)
        assert result["status"] == "error"


def test_plot_isotherm_comparison_creates_png():
    datasets = [
        {"label": "MIL-101(Cr)", "isotherm_data": _FAKE_ISOTHERM},
        {"label": "ZIF-8",       "isotherm_data": [
            {"pressure_Pa": 1e4,  "loading_mol_kg": 0.5},
            {"pressure_Pa": 1e5,  "loading_mol_kg": 2.1},
            {"pressure_Pa": 1e6,  "loading_mol_kg": 5.3},
        ]},
        {"label": "UiO-66",      "isotherm_data": [
            {"pressure_Pa": 1e4,  "loading_mol_kg": 0.8},
            {"pressure_Pa": 1e5,  "loading_mol_kg": 2.9},
            {"pressure_Pa": 1e6,  "loading_mol_kg": 6.0},
        ]},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "comparison.png")
        result = plot_isotherm_comparison(
            datasets=datasets,
            output_path=out,
            molecule="PH3",
            temperature_K=298.0,
        )
        assert result["status"] == "ok", result.get("message")
        assert result["n_series"] == 3
        assert Path(out).exists()
        assert Path(out).stat().st_size > 10_000


def test_plot_isotherm_comparison_empty_datasets_returns_error():
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "comparison.png")
        result = plot_isotherm_comparison(datasets=[], output_path=out)
        assert result["status"] == "error"


# ─────────────────────────────────────────────────────────────────
# 1-4: Qst isosteric heat extraction
# ─────────────────────────────────────────────────────────────────

_FAKE_GCMC_OUTPUT = """
External temperature: 298.0 [K]
External pressure: 100000.0 [Pa]
Average Host-Adsorbate energy:   -42600.0 +/- 310.0
Average Isosteric heat of adsorption:   38.421 +/- 0.312 [KJ/mol]
"""


def test_qst_extracted_from_gcmc_output():
    result = _parse_energy(_FAKE_GCMC_OUTPUT)
    assert result is not None
    assert "Qst_kJ_mol" in result
    assert abs(result["Qst_kJ_mol"] - 38.421) < 1e-3
    assert "Qst_kJ_mol_err" in result


def test_qst_absent_when_not_in_output():
    result = _parse_energy("Average Host-Adsorbate energy: 100.0 +/- 1.0")
    assert result is not None
    assert "Qst_kJ_mol" not in result


# ─────────────────────────────────────────────────────────────────
# 3-8: mu_ex chemical potential from Widom
# ─────────────────────────────────────────────────────────────────

_FAKE_WIDOM_OUTPUT = """
External temperature: 298.0 [K]
Henry coefficient: 2.31e-4 [mol/kg/Pa]
Average Widom Rosenbluth factor: 1.5234 +/- 0.042
"""


def test_mu_ex_calculated_from_widom_output():
    result = _parse_henry(_FAKE_WIDOM_OUTPUT)
    assert result is not None
    assert "mu_ex_kJ_mol" in result
    # mu_ex = -RT ln(W) = -8.314e-3 * 298 * ln(1.5234), should be negative (favourable)
    assert result["mu_ex_kJ_mol"] < 0


def test_mu_ex_absent_when_no_temperature():
    result = _parse_henry("Average Widom Rosenbluth factor: 1.5 +/- 0.01")
    assert result is not None
    assert "mu_ex_kJ_mol" not in result  # no temperature in text


# ─────────────────────────────────────────────────────────────────
# 1-5 / 1-6 / 2-2 / 2-3 / 4-1: new templates present
# ─────────────────────────────────────────────────────────────────

def test_new_templates_all_present():
    for key in ("NVT-MC", "NPT-MC", "NPT-MD", "NVE-MD", "GCMCMixture"):
        assert key in TEMPLATES, f"Template '{key}' missing"
        assert len(TEMPLATES[key]) > 100, f"Template '{key}' suspiciously short"


def test_nvt_mc_template_has_no_swap():
    assert "SwapProbability" not in TEMPLATES["NVT-MC"]


def test_npt_mc_template_has_volume_change():
    assert "VolumeChangeProbability" in TEMPLATES["NPT-MC"]


def test_npt_md_template_has_npt_ensemble():
    assert "NPT" in TEMPLATES["NPT-MD"]
    assert "BarostatChainLength" in TEMPLATES["NPT-MD"]


def test_nve_md_template_has_nve_ensemble():
    assert "NVE" in TEMPLATES["NVE-MD"]


def test_gcmc_mixture_template_has_two_components():
    tpl = TEMPLATES["GCMCMixture"]
    assert "Component 0" in tpl
    assert "Component 1" in tpl
    assert "PartialPressure" in tpl
    assert "${PARTIAL_PRESSURE_A}" in tpl
    assert "${PARTIAL_PRESSURE_B}" in tpl


# ─────────────────────────────────────────────────────────────────
# 1-6: NPT-MC validator warning for missing VolumeChangeProbability
# ─────────────────────────────────────────────────────────────────

_NPT_MC_MISSING_VOLUME = """
SimulationType        MonteCarlo
NumberOfCycles        10000
NumberOfInitializationCycles 2000
Forcefield            local
CutOff                12.0
Framework 0
  FrameworkName       ZIF-8
  UnitCells           2 2 2
  ExternalTemperature 298.0
  ExternalPressure    100000.0
Component 0 MoleculeName CO2
  MoleculeDefinition  local
  TranslationProbability 0.5
  SwapProbability     1.0
  CreateNumberOfMolecules 10
"""


def test_npt_mc_warns_missing_volume_change():
    result = validate_simulation_input(_NPT_MC_MISSING_VOLUME).to_dict()
    assert any("VolumeChangeProbability" in w for w in result["warnings"])


# ─────────────────────────────────────────────────────────────────
# 4-2: Multi-component validator checks
# ─────────────────────────────────────────────────────────────────

_MIXTURE_MISSING_PARTIAL_PRESSURE = """
SimulationType        MonteCarlo
NumberOfCycles        10000
NumberOfInitializationCycles 2000
Forcefield            local
CutOff                12.0
Framework 0
  FrameworkName       ZIF-8
  UnitCells           2 2 2
  HeliumVoidFraction  0.47
  ExternalTemperature 298.0
  ExternalPressure    100000.0
Component 0 MoleculeName CO2
  MoleculeDefinition  local
  SwapProbability     1.0
  CreateNumberOfMolecules 0
Component 1 MoleculeName N2
  MoleculeDefinition  local
  SwapProbability     1.0
  CreateNumberOfMolecules 0
"""


def test_mixture_warns_on_external_pressure_with_multiple_components():
    result = validate_simulation_input(_MIXTURE_MISSING_PARTIAL_PRESSURE).to_dict()
    assert any("PartialPressure" in w for w in result["warnings"])


def test_mixture_valid_with_partial_pressure():
    content = _MIXTURE_MISSING_PARTIAL_PRESSURE.replace(
        "ExternalPressure    100000.0",
        "PartialPressure     15000.0",
    ).replace("ExternalPressure", "")
    result = validate_simulation_input(content).to_dict()
    assert not any("PartialPressure" in w for w in result["warnings"])


# ─────────────────────────────────────────────────────────────────
# 3-3: RDF output parser
# ─────────────────────────────────────────────────────────────────

def test_parse_rdf_nonexistent_dir():
    result = parse_rdf_output("/nonexistent/path")
    assert result["status"] == "no_output_found"


def test_parse_rdf_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        result = parse_rdf_output(tmp)
        assert result["status"] == "no_rdf_files"


def test_parse_rdf_reads_dat_file():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        rdf_file = tmpdir / "RDF_CO2_CO2.dat"
        rdf_file.write_text(
            "# r(A)  g(r)\n"
            "1.0  0.0\n"
            "2.0  0.5\n"
            "3.5  2.8\n"  # peak
            "5.0  1.1\n"
            "7.0  1.0\n"
        )
        result = parse_rdf_output(tmp)
        assert result["status"] == "ok"
        assert result["n_rdf_datasets"] == 1
        ds = result["rdf_data"][0]
        assert ds["pair"] == "CO2_CO2"
        assert ds["n_points"] == 5
        assert abs(ds["first_peak_r"] - 3.5) < 1e-6
        assert abs(ds["first_peak_g"] - 2.8) < 1e-6


def test_parse_rdf_component_filter():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        (tmpdir / "RDF_CO2_CO2.dat").write_text("1.0  0.0\n3.5  2.8\n")
        (tmpdir / "RDF_N2_N2.dat").write_text("1.0  0.0\n3.8  1.9\n")
        result = parse_rdf_output(tmp, component_a="CO2")
        assert result["n_rdf_datasets"] == 1
        assert result["rdf_data"][0]["pair"] == "CO2_CO2"
