"""
Force field data for common adsorbates and frameworks.
All parameters sourced from peer-reviewed literature (cited inline).
Format matches RASPA2 input file specifications exactly.
"""

# ─────────────────────────────────────────────────────────────────
# pseudo_atoms.def content for each force field
# Format: RASPA2 pseudo_atoms.def
# Columns: type  print  as  chem  oxidation  mass  charge
#          polarization  B-factor  radii  connectivity
#          anisotropic  anisotropic-type  tinker-type
# ─────────────────────────────────────────────────────────────────

PSEUDO_ATOMS: dict[str, str] = {

    "TraPPE-CO2": """\
# CO2 force field: TraPPE model (3-site, rigid, linear)
# Ref: Garcia-Sanchez et al., J. Phys. Chem. C 2009, 113, 8814-8820
# Charges: C=+0.6512e, O=-0.3256e
# ---
# number of pseudo atoms
3
# type      print  as      chem  oxidation  mass      charge    polarization  B-factor  radii  connectivity  anisotropic  anisotropic-type  tinker-type
O_co2       yes    O_co2   O     0          15.9994  -0.3256    0.000         1.0       1.0    0             0.0          absolute          0
C_co2       yes    C_co2   C     0          12.0110   0.6512    0.000         1.0       1.0    0             0.0          absolute          0
He          yes    He      He    0           4.0026   0.0000    0.000         1.0       1.0    0             0.0          absolute          0
""",

    "TraPPE-N2": """\
# N2 force field: TraPPE model (3-site: 2 N + 1 COM)
# Ref: Potoff & Siepmann, AIChE J. 2001, 47, 1676-1682
# Charges: N=-0.482e, COM_N2=+0.964e (charge on center of mass)
# ---
# number of pseudo atoms
3
# type      print  as      chem  oxidation  mass      charge    polarization  B-factor  radii  connectivity  anisotropic  anisotropic-type  tinker-type
N_n2        yes    N_n2    N     0          14.0067  -0.4820    0.000         1.0       1.0    0             0.0          absolute          0
N_com       yes    N_com   N     0           0.0000   0.9640    0.000         1.0       0.0    0             0.0          absolute          0
He          yes    He      He    0           4.0026   0.0000    0.000         1.0       1.0    0             0.0          absolute          0
""",

    "TraPPE-CH4": """\
# CH4 force field: TraPPE united-atom model (1-site, single LJ center)
# Ref: Martin & Siepmann, J. Phys. Chem. B 1998, 102, 2569-2577
# ---
# number of pseudo atoms
2
# type      print  as      chem  oxidation  mass      charge    polarization  B-factor  radii  connectivity  anisotropic  anisotropic-type  tinker-type
CH4_sp3     yes    CH4_sp3 C     0          16.0430   0.0000    0.000         1.0       1.0    0             0.0          absolute          0
He          yes    He      He    0           4.0026   0.0000    0.000         1.0       1.0    0             0.0          absolute          0
""",

    "TraPPE-H2O": """\
# H2O force field: SPC/E model
# Ref: Berendsen et al., J. Phys. Chem. 1987, 91, 6269-6271
# Charges: O=-0.8476e, H=+0.4238e
# ---
# number of pseudo atoms
3
# type      print  as      chem  oxidation  mass      charge    polarization  B-factor  radii  connectivity  anisotropic  anisotropic-type  tinker-type
Ow          yes    Ow      O     0          15.9994  -0.8476    0.000         1.0       1.0    0             0.0          absolute          0
Hw          yes    Hw      H     0           1.0079   0.4238    0.000         1.0       1.0    0             0.0          absolute          0
He          yes    He      He    0           4.0026   0.0000    0.000         1.0       1.0    0             0.0          absolute          0
""",

    "UFF": """\
# UFF framework force field (generic, use for MOF frameworks if no specific FF available)
# Ref: Rappe et al., J. Am. Chem. Soc. 1992, 114, 10024-10035
# NOTE: UFF atom types depend on your specific framework.
# This is a minimal example. Claude should identify atom types from the CIF file.
# ---
# number of pseudo atoms
1
# type      print  as      chem  oxidation  mass      charge    polarization  B-factor  radii  connectivity  anisotropic  anisotropic-type  tinker-type
He          yes    He      He    0           4.0026   0.0000    0.000         1.0       1.0    0             0.0          absolute          0
""",
}

# ─────────────────────────────────────────────────────────────────
# force_field_mixing_rules.def content for each force field
# ─────────────────────────────────────────────────────────────────

MIXING_RULES: dict[str, str] = {

    "TraPPE-CO2": """\
# Mixing rules for CO2 (TraPPE) + generic framework (UFF/DREIDING)
# Ref: Garcia-Sanchez et al., J. Phys. Chem. C 2009, 113, 8814-8820
# Lorentz-Berthelot combining rules
# ---
# general rule for Lorentz-Berthelot combining rules
Lorentz-Berthelot

# number of defined interactions
2

# atom type       epsilon/kB (K)    sigma (Angstrom)
O_co2             79.0              3.050
C_co2             27.0              2.800
""",

    "TraPPE-N2": """\
# Mixing rules for N2 (TraPPE)
# Ref: Potoff & Siepmann, AIChE J. 2001, 47, 1676-1682
# ---
Lorentz-Berthelot

# number of defined interactions
2

# atom type       epsilon/kB (K)    sigma (Angstrom)
N_n2              36.0              3.310
N_com              0.0              0.000
""",

    "TraPPE-CH4": """\
# Mixing rules for CH4 (TraPPE united-atom)
# Ref: Martin & Siepmann, J. Phys. Chem. B 1998, 102, 2569-2577
# ---
Lorentz-Berthelot

# number of defined interactions
1

# atom type       epsilon/kB (K)    sigma (Angstrom)
CH4_sp3           148.0             3.730
""",

    "TraPPE-H2O": """\
# Mixing rules for H2O (SPC/E)
# Ref: Berendsen et al., J. Phys. Chem. 1987, 91, 6269-6271
# ---
Lorentz-Berthelot

# number of defined interactions
2

# atom type       epsilon/kB (K)    sigma (Angstrom)
Ow                78.197            3.166
Hw                 0.000            0.000
""",
}

# ─────────────────────────────────────────────────────────────────
# Metadata: force field applicability and references
# ─────────────────────────────────────────────────────────────────

FORCEFIELD_META: dict[str, dict] = {
    "TraPPE-CO2": {
        "molecule": "CO2",
        "model": "3-site rigid linear (TraPPE)",
        "suitable_frameworks": ["MOF", "zeolite", "ZIF"],
        "doi": "10.1021/jp810871f",
        "reference": "Garcia-Sanchez et al., J. Phys. Chem. C 2009, 113, 8814",
        "notes": "Well-validated for CO2 adsorption in MOFs and zeolites. "
                 "Use with UFF or DREIDING for framework atoms.",
    },
    "TraPPE-N2": {
        "molecule": "N2",
        "model": "3-site (2N + COM charge site)",
        "suitable_frameworks": ["MOF", "zeolite"],
        "doi": "10.1002/aic.690471116",
        "reference": "Potoff & Siepmann, AIChE J. 2001, 47, 1676",
        "notes": "Standard for N2 adsorption. Include COM site in molecule definition.",
    },
    "TraPPE-CH4": {
        "molecule": "CH4",
        "model": "1-site united-atom (TraPPE)",
        "suitable_frameworks": ["MOF", "zeolite"],
        "doi": "10.1021/jp972543+",
        "reference": "Martin & Siepmann, J. Phys. Chem. B 1998, 102, 2569",
        "notes": "Simplest methane model, widely used for MOF screening.",
    },
    "TraPPE-H2O": {
        "molecule": "H2O",
        "model": "SPC/E",
        "suitable_frameworks": ["MOF", "zeolite"],
        "doi": "10.1021/j100308a021",
        "reference": "Berendsen et al., J. Phys. Chem. 1987, 91, 6269",
        "notes": "SPC/E is standard for water in porous materials. "
                 "Consider polarization effects for highly polar frameworks.",
    },
    "UFF": {
        "molecule": "framework",
        "model": "Universal Force Field",
        "suitable_frameworks": ["MOF (generic)", "organic frameworks"],
        "doi": "10.1021/ja00051a040",
        "reference": "Rappe et al., J. Am. Chem. Soc. 1992, 114, 10024",
        "notes": "Generic framework FF. Less accurate than system-specific FF. "
                 "Suitable for screening. Atom types must be assigned from CIF.",
    },
}
