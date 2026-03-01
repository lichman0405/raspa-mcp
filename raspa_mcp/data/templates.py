"""
RASPA2 simulation.input templates.
Each template uses ${PLACEHOLDER} syntax for Claude to fill in.
Values are taken directly from RASPA2 manual and examples.
"""

TEMPLATES: dict[str, str] = {

    "GCMC": """\
# GCMC Simulation — Grand Canonical Monte Carlo
# Purpose: adsorption isotherms, Henry coefficients at fixed P/T
SimulationType                 MonteCarlo
NumberOfCycles                 10000
NumberOfInitializationCycles   2000
PrintEvery                     1000
PrintForcefieldToOutput        no
PrintPseudoAtomsToOutput       no
PrintMoleculesToOutput         no
RestartFile                    no

# Force field
Forcefield                     local
CutOff                         12.0
ChargeMethod                   Ewald
EwaldPrecision                 1e-6
UseChargesFromCIFFile          yes

# Framework
Framework 0
  FrameworkName                ${FRAMEWORK_NAME}
  UnitCells                    ${UNIT_CELLS_A} ${UNIT_CELLS_B} ${UNIT_CELLS_C}
  HeliumVoidFraction           ${HELIUM_VOID_FRACTION}
  ExternalTemperature          ${TEMPERATURE}
  ExternalPressure             ${PRESSURE}

# Adsorbate
Component 0 MoleculeName             ${MOLECULE}
  MoleculeDefinition                 local
  TranslationProbability             0.5
  RotationProbability                0.5
  ReinsertionProbability             0.5
  SwapProbability                    1.0
  CreateNumberOfMolecules            0
""",

    "Widom": """\
# Widom Test-Particle Insertion
# Purpose: Henry coefficient, free energy of adsorption (infinite dilution)
SimulationType                 MonteCarlo
NumberOfCycles                 10000
NumberOfInitializationCycles   0
PrintEvery                     1000
PrintForcefieldToOutput        no
PrintPseudoAtomsToOutput       no
PrintMoleculesToOutput         no
RestartFile                    no

Forcefield                     local
CutOff                         12.0
ChargeMethod                   Ewald
EwaldPrecision                 1e-6
UseChargesFromCIFFile          yes

Framework 0
  FrameworkName                ${FRAMEWORK_NAME}
  UnitCells                    ${UNIT_CELLS_A} ${UNIT_CELLS_B} ${UNIT_CELLS_C}
  HeliumVoidFraction           ${HELIUM_VOID_FRACTION}
  ExternalTemperature          ${TEMPERATURE}

Component 0 MoleculeName             ${MOLECULE}
  MoleculeDefinition                 local
  WidomProbability                   1.0
  CreateNumberOfMolecules            0
""",

    "MD": """\
# Molecular Dynamics Simulation
# Purpose: diffusion coefficients, transport properties
SimulationType                 MolecularDynamics
NumberOfCycles                 100000
NumberOfInitializationCycles   10000
NumberOfEquilibrationCycles    10000
PrintEvery                     1000
RestartFile                    no

Forcefield                     local
CutOff                         12.0
ChargeMethod                   Ewald
EwaldPrecision                 1e-6
UseChargesFromCIFFile          yes

Ensemble                       NVT
TimeStep                       0.0005
ThermostatChainLength          5

Framework 0
  FrameworkName                ${FRAMEWORK_NAME}
  UnitCells                    ${UNIT_CELLS_A} ${UNIT_CELLS_B} ${UNIT_CELLS_C}
  ExternalTemperature          ${TEMPERATURE}

Component 0 MoleculeName             ${MOLECULE}
  MoleculeDefinition                 local
  TranslationProbability             1.0
  CreateNumberOfMolecules            ${N_MOLECULES}
""",

    "VoidFraction": """\
# Helium Void Fraction Calculation
# Purpose: compute pore void fraction (required before GCMC)
# Run this first if void fraction is unknown.
SimulationType                 MonteCarlo
NumberOfCycles                 10000
NumberOfInitializationCycles   0
PrintEvery                     1000
PrintForcefieldToOutput        no
RestartFile                    no

Forcefield                     local
CutOff                         12.0

Framework 0
  FrameworkName                ${FRAMEWORK_NAME}
  UnitCells                    ${UNIT_CELLS_A} ${UNIT_CELLS_B} ${UNIT_CELLS_C}
  ExternalTemperature          ${TEMPERATURE}

Component 0 MoleculeName             helium
  MoleculeDefinition                 TraPPE
  WidomProbability                   1.0
  CreateNumberOfMolecules            0
""",

    # 1-5: NVT-MC — fixed-N configurational sampling
    "NVT-MC": """\
# NVT Monte Carlo Simulation
# Purpose: configurational sampling, RDF, density profiles at fixed N/V/T
# Molecules are pre-loaded (not inserted/deleted).
SimulationType                 MonteCarlo
NumberOfCycles                 50000
NumberOfInitializationCycles   5000
PrintEvery                     1000
RestartFile                    no

Forcefield                     local
CutOff                         12.0
ChargeMethod                   Ewald
EwaldPrecision                 1e-6
UseChargesFromCIFFile          yes

Framework 0
  FrameworkName                ${FRAMEWORK_NAME}
  UnitCells                    ${UNIT_CELLS_A} ${UNIT_CELLS_B} ${UNIT_CELLS_C}
  ExternalTemperature          ${TEMPERATURE}

Component 0 MoleculeName             ${MOLECULE}
  MoleculeDefinition                 local
  TranslationProbability             0.5
  RotationProbability                0.5
  ReinsertionProbability             0.5
  CreateNumberOfMolecules            ${N_MOLECULES}
""",

    # 1-6: NPT-MC — variable-volume MC
    "NPT-MC": """\
# NPT Monte Carlo Simulation
# Purpose: equilibrium density, volume response to pressure, flexible-cell studies
SimulationType                 MonteCarlo
NumberOfCycles                 50000
NumberOfInitializationCycles   5000
PrintEvery                     1000
RestartFile                    no

Forcefield                     local
CutOff                         12.0
ChargeMethod                   Ewald
EwaldPrecision                 1e-6

Framework 0
  FrameworkName                ${FRAMEWORK_NAME}
  UnitCells                    ${UNIT_CELLS_A} ${UNIT_CELLS_B} ${UNIT_CELLS_C}
  ExternalTemperature          ${TEMPERATURE}
  ExternalPressure             ${PRESSURE}

Component 0 MoleculeName             ${MOLECULE}
  MoleculeDefinition                 local
  TranslationProbability             0.4
  RotationProbability                0.3
  ReinsertionProbability             0.3
  VolumeChangeProbability            0.05
  CreateNumberOfMolecules            ${N_MOLECULES}
""",

    # 2-2: NPT-MD — constant pressure molecular dynamics
    "NPT-MD": """\
# NPT Molecular Dynamics Simulation
# Purpose: equilibrium density, thermal expansion coefficient
SimulationType                 MolecularDynamics
NumberOfCycles                 100000
NumberOfInitializationCycles   10000
NumberOfEquilibrationCycles    10000
PrintEvery                     1000
RestartFile                    no

Forcefield                     local
CutOff                         12.0
ChargeMethod                   Ewald
EwaldPrecision                 1e-6
UseChargesFromCIFFile          yes

Ensemble                       NPT
TimeStep                       0.0005
ThermostatChainLength          5
BarostatChainLength            5
TargetAccRatioCellChange       0.5

Framework 0
  FrameworkName                ${FRAMEWORK_NAME}
  UnitCells                    ${UNIT_CELLS_A} ${UNIT_CELLS_B} ${UNIT_CELLS_C}
  ExternalTemperature          ${TEMPERATURE}
  ExternalPressure             ${PRESSURE}

Component 0 MoleculeName             ${MOLECULE}
  MoleculeDefinition                 local
  TranslationProbability             1.0
  CreateNumberOfMolecules            ${N_MOLECULES}
""",

    # 2-3: NVE-MD — microcanonical (energy conservation benchmark)
    "NVE-MD": """\
# NVE Molecular Dynamics Simulation
# Purpose: verify force field energy conservation, benchmark integrator
# Note: do NOT use for production thermodynamics — NVT/NPT preferred.
SimulationType                 MolecularDynamics
NumberOfCycles                 50000
NumberOfInitializationCycles   5000
NumberOfEquilibrationCycles    5000
PrintEvery                     1000
RestartFile                    no

Forcefield                     local
CutOff                         12.0
ChargeMethod                   Ewald
EwaldPrecision                 1e-6
UseChargesFromCIFFile          yes

Ensemble                       NVE
TimeStep                       0.0005

Framework 0
  FrameworkName                ${FRAMEWORK_NAME}
  UnitCells                    ${UNIT_CELLS_A} ${UNIT_CELLS_B} ${UNIT_CELLS_C}
  ExternalTemperature          ${TEMPERATURE}

Component 0 MoleculeName             ${MOLECULE}
  MoleculeDefinition                 local
  TranslationProbability             1.0
  CreateNumberOfMolecules            ${N_MOLECULES}
""",

    # 4-1: GCMC binary mixture
    "GCMCMixture": """\
# GCMC Binary Mixture Simulation
# Purpose: co-adsorption, selectivity S_AB, mixed-gas isotherms
# Each component uses PartialPressure (NOT ExternalPressure).
# Total pressure = sum of all partial pressures.
SimulationType                 MonteCarlo
NumberOfCycles                 50000
NumberOfInitializationCycles   5000
PrintEvery                     1000
RestartFile                    no

Forcefield                     local
CutOff                         12.0
ChargeMethod                   Ewald
EwaldPrecision                 1e-6
UseChargesFromCIFFile          yes

Framework 0
  FrameworkName                ${FRAMEWORK_NAME}
  UnitCells                    ${UNIT_CELLS_A} ${UNIT_CELLS_B} ${UNIT_CELLS_C}
  HeliumVoidFraction           ${HELIUM_VOID_FRACTION}
  ExternalTemperature          ${TEMPERATURE}

Component 0 MoleculeName             ${MOLECULE_A}
  MoleculeDefinition                 local
  TranslationProbability             0.5
  RotationProbability                0.5
  ReinsertionProbability             0.5
  SwapProbability                    1.0
  PartialPressure                    ${PARTIAL_PRESSURE_A}
  CreateNumberOfMolecules            0

Component 1 MoleculeName             ${MOLECULE_B}
  MoleculeDefinition                 local
  TranslationProbability             0.5
  RotationProbability                0.5
  ReinsertionProbability             0.5
  SwapProbability                    1.0
  PartialPressure                    ${PARTIAL_PRESSURE_B}
  CreateNumberOfMolecules            0
""",

    # 1-8: Thermodynamic Integration — free energy of adsorption
    "TI": """\
# Thermodynamic Integration (TI) — Free Energy of Adsorption
# Purpose: compute ΔA (Helmholtz) or ΔG via λ-coupling.
# Workflow: run one simulation per lambda value (0.0, 0.1, ..., 1.0),
#           then call parse_ti_output() to integrate ⟨∂U/∂λ⟩ with numpy.trapz.
# Reference: Frenkel & Smit "Understanding Molecular Simulation", Ch. 7
SimulationType                 MonteCarlo
NumberOfCycles                 100000
NumberOfInitializationCycles   10000
PrintEvery                     1000
RestartFile                    no

Forcefield                     local
CutOff                         12.0
ChargeMethod                   Ewald
EwaldPrecision                 1e-6
UseChargesFromCIFFile          yes

Framework 0
  FrameworkName                ${FRAMEWORK_NAME}
  UnitCells                    ${UNIT_CELLS_A} ${UNIT_CELLS_B} ${UNIT_CELLS_C}
  ExternalTemperature          ${TEMPERATURE}

Component 0 MoleculeName             ${MOLECULE}
  MoleculeDefinition                 local
  TranslationProbability             0.3
  RotationProbability                0.3
  ReinsertionProbability             0.4
  CreateNumberOfMolecules            1
  Lambda                             ${LAMBDA}
  LambdaDefinition                   LinearInterpolation
  CFCRXMCLambdaHistogramSize         100
  TargetAccRatioSmallMC              0.4
""",

    # 2-4: Flexible Framework MD — bonded force field for framework atoms
    "FlexibleMD": """\
# Flexible Framework Molecular Dynamics
# Purpose: framework breathing, gate opening, phonons, host deformation under loading.
# REQUIRED extra file: Framework.def — bonded force field for framework atoms.
#   Framework.def must define Bond, Bend, and Torsion interactions for all
#   framework atom pairs/triples/quadruples. See RASPA2 manual §7.4.
# Typical workflow:
#   1. Prepare Framework.def from DFT data or DDEC charges + UFF bonds.
#   2. Equilibrate with NVT-MD (rigid), then switch FlexibleFramework yes.
#   3. Run production with NPT-MD to capture volume fluctuations.
SimulationType                 MolecularDynamics
NumberOfCycles                 200000
NumberOfInitializationCycles   20000
NumberOfEquilibrationCycles    20000
PrintEvery                     1000
RestartFile                    no

Forcefield                     local
CutOff                         12.0
ChargeMethod                   Ewald
EwaldPrecision                 1e-6
UseChargesFromCIFFile          yes

Ensemble                       NPT
TimeStep                       0.0002
ThermostatChainLength          5
BarostatChainLength            5

Framework 0
  FrameworkName                ${FRAMEWORK_NAME}
  UnitCells                    ${UNIT_CELLS_A} ${UNIT_CELLS_B} ${UNIT_CELLS_C}
  ExternalTemperature          ${TEMPERATURE}
  ExternalPressure             ${PRESSURE}
  FlexibleFramework            yes
  FrameworkDefinitionsFile     ${FRAMEWORK_DEF_FILE}

Component 0 MoleculeName             ${MOLECULE}
  MoleculeDefinition                 local
  TranslationProbability             1.0
  CreateNumberOfMolecules            ${N_MOLECULES}
""",

    # 1-7: CBMC for flexible/branched molecules (e.g. long-chain alkanes)
    "CBMC": """\
# GCMC with Configurational-Bias Monte Carlo (CBMC)
# Purpose: adsorption of flexible molecules (alkanes, branched hydrocarbons)
# CBMC dramatically improves insertion acceptance for chain molecules (C4+).
SimulationType                 MonteCarlo
NumberOfCycles                 50000
NumberOfInitializationCycles   5000
PrintEvery                     1000
RestartFile                    no

Forcefield                     local
CutOff                         12.0
ChargeMethod                   None

Framework 0
  FrameworkName                ${FRAMEWORK_NAME}
  UnitCells                    ${UNIT_CELLS_A} ${UNIT_CELLS_B} ${UNIT_CELLS_C}
  HeliumVoidFraction           ${HELIUM_VOID_FRACTION}
  ExternalTemperature          ${TEMPERATURE}
  ExternalPressure             ${PRESSURE}

Component 0 MoleculeName             ${MOLECULE}
  MoleculeDefinition                 local
  TranslationProbability             0.2
  RotationProbability                0.2
  ReinsertionProbability             0.2
  CBMCProbability                    0.4
  SwapProbability                    1.0
  NumberOfTrialPositions             10
  NumberOfTrialOrientations          10
  CreateNumberOfMolecules            0
""",
}

# Parameter documentation: what each placeholder means and valid ranges
TEMPLATE_PARAMS: dict[str, dict] = {
    "${FRAMEWORK_NAME}": {
        "desc": "Name of the MOF/zeolite (matches CIF filename without extension)",
        "example": "ZIF-8",
    },
    "${UNIT_CELLS_A}": {
        "desc": "Number of unit cell replications along a-axis (ensure min 2×cutoff)",
        "example": "1",
        "note": "Typical: ensure each axis >= 2 * CutOff. For ZIF-8 (a≈17Å, cutoff=12Å): 2 2 2",
    },
    "${UNIT_CELLS_B}": {"desc": "Unit cell replications along b-axis", "example": "1"},
    "${UNIT_CELLS_C}": {"desc": "Unit cell replications along c-axis", "example": "1"},
    "${TEMPERATURE}": {
        "desc": "Temperature in Kelvin",
        "example": "298.0",
        "valid_range": "77 – 1000 K",
    },
    "${PRESSURE}": {
        "desc": "External pressure in Pascal (1 bar = 100000 Pa)",
        "example": "100000",
        "note": "For isotherm: run separate simulations at each pressure point",
    },
    "${MOLECULE}": {
        "desc": "Adsorbate molecule name (must match molecule definition file)",
        "example": "CO2",
    },
    "${HELIUM_VOID_FRACTION}": {
        "desc": "Pore void fraction (0–1), computed from VoidFraction simulation",
        "example": "0.47",
        "note": "If unknown, run VoidFraction simulation first",
    },
    "${N_MOLECULES}": {
        "desc": "Number of molecules for NVT-MC / MD (pre-loaded, not inserted)",
        "example": "20",
    },
    "${MOLECULE_A}": {
        "desc": "First adsorbate in binary mixture (e.g. CO2)",
        "example": "CO2",
    },
    "${MOLECULE_B}": {
        "desc": "Second adsorbate in binary mixture (e.g. N2)",
        "example": "N2",
    },
    "${PARTIAL_PRESSURE_A}": {
        "desc": "Partial pressure of component A in Pascal. y_A × P_total.",
        "example": "15000",
        "note": "For CO2/N2 flue gas 15% CO2 at 1 bar: 15000 Pa",
    },
    "${PARTIAL_PRESSURE_B}": {
        "desc": "Partial pressure of component B in Pascal. y_B × P_total.",
        "example": "85000",
        "note": "For CO2/N2 flue gas 85% N2 at 1 bar: 85000 Pa",
    },
    "${CBMC_TRIALS}": {
        "desc": "NumberOfTrialPositions for CBMC insertion (default 10, increase for dense systems)",
        "example": "10",
        "note": "Higher values improve acceptance but increase cost. 10-20 typical for zeolites.",
    },
    "${LAMBDA}": {
        "desc": "Lambda coupling parameter for TI (0.0 = pure framework, 1.0 = full adsorbate interaction)",
        "example": "0.5",
        "note": "Run 11 simulations at lambda = 0.0, 0.1, ..., 1.0; then call parse_ti_output() to integrate.",
    },
    "${FRAMEWORK_DEF_FILE}": {
        "desc": "Path to Framework.def file defining bonded force field for flexible framework atoms",
        "example": "Framework.def",
        "note": "Must contain bond/bend/torsion parameters for all framework atom types.",
    },
}
