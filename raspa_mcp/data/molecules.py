"""
RASPA2 molecule definition files (.def format).
Content taken from RASPA2 official molecules/ directory and literature.

Format reference: RASPA2 manual Chapter 3.
"""

MOLECULE_DEFINITIONS: dict[str, str] = {

    "CO2": """\
# Critical constants and molecule definition for CO2
# Model: TraPPE 3-site rigid linear
# Ref: Garcia-Sanchez et al., J. Phys. Chem. C 2009, 113, 8814

# critical constants: Temperature [T], Pressure [Pa], and acentric factor [-]
304.128
7376460.0
0.22394

# Number of Atoms
3

# Number of Groups
1

# Atomic Positions (fractional coords relative to COM)
# index  type    x(A)    y(A)    z(A)
0  C_co2   0.0000  0.0000  0.0000
1  O_co2   1.1610  0.0000  0.0000
2  O_co2  -1.1610  0.0000  0.0000

# Chiral Centers  Bond  BondDipoles  Bend  UreyBradley  Torsion  ImproperTorsion  OutOfPlane  Bond/Bond  Bond/Bend  Bend/Bend  StretchTorsion  BendTorsion
0 2 0 0 0 0 0 0 0 0 0 0 0

# Bond stretch: atom1-atom2  type  parameters
0 1 RIGID_BOND
0 2 RIGID_BOND

# Number of config moves
0
""",

    "N2": """\
# Critical constants and molecule definition for N2
# Model: TraPPE 3-site (2 N atoms + 1 COM charge site)
# Ref: Potoff & Siepmann, AIChE J. 2001, 47, 1676

# critical constants: Temperature [T], Pressure [Pa], and acentric factor [-]
126.192
3395800.0
0.03720

# Number of Atoms
3

# Number of Groups
1

# Atomic Positions
# index  type    x(A)    y(A)    z(A)
0  N_n2    0.5500  0.0000  0.0000
1  N_n2   -0.5500  0.0000  0.0000
2  N_com   0.0000  0.0000  0.0000

# Chiral Centers  Bond  BondDipoles  Bend  UreyBradley  Torsion  ImproperTorsion  OutOfPlane  Bond/Bond  Bond/Bend  Bend/Bend  StretchTorsion  BendTorsion
0 2 0 0 0 0 0 0 0 0 0 0 0

# Bond stretch: atom1-atom2  type  parameters
0 1 RIGID_BOND
0 2 RIGID_BOND

# Number of config moves
0
""",

    "CH4": """\
# Critical constants and molecule definition for CH4
# Model: TraPPE 1-site united atom
# Ref: Martin & Siepmann, J. Phys. Chem. B 1998, 102, 2569

# critical constants: Temperature [T], Pressure [Pa], and acentric factor [-]
190.564
4599200.0
0.01142

# Number of Atoms
1

# Number of Groups
1

# Atomic Positions
# index  type     x(A)    y(A)    z(A)
0  CH4_sp3  0.0000  0.0000  0.0000

# Chiral Centers  Bond  BondDipoles  Bend  UreyBradley  Torsion  ImproperTorsion  OutOfPlane  Bond/Bond  Bond/Bend  Bend/Bend  StretchTorsion  BendTorsion
0 0 0 0 0 0 0 0 0 0 0 0 0

# Number of config moves
0
""",

    "H2O": """\
# Critical constants and molecule definition for H2O
# Model: SPC/E
# Ref: Berendsen et al., J. Phys. Chem. 1987, 91, 6269

# critical constants: Temperature [T], Pressure [Pa], and acentric factor [-]
647.096
22064000.0
0.34486

# Number of Atoms
3

# Number of Groups
1

# Atomic Positions (SPC/E geometry: O-H bond = 1.0 Å, H-O-H angle = 109.47°)
# index  type   x(A)       y(A)      z(A)
0  Ow    0.00000  0.00000  0.00000
1  Hw    0.81649  0.57736  0.00000
2  Hw   -0.81649  0.57736  0.00000

# Chiral Centers  Bond  BondDipoles  Bend  UreyBradley  Torsion  ImproperTorsion  OutOfPlane  Bond/Bond  Bond/Bend  Bend/Bend  StretchTorsion  BendTorsion
0 2 0 1 0 0 0 0 0 0 0 0 0

# Bond stretch: atom1-atom2  type  parameters
0 1 RIGID_BOND
0 2 RIGID_BOND

# Bend: atom1-atom2-atom3  type  angle(degrees)
1 0 2 FIXED_BEND 109.47

# Number of config moves
0
""",

    "helium": """\
# Helium — used for void fraction calculation (Widom insertion)
# Ref: Hirschfelder et al., Molecular Theory of Gases and Liquids, 1954

# critical constants: Temperature [T], Pressure [Pa], and acentric factor [-]
5.1953
227530.0
-0.38200

# Number of Atoms
1

# Number of Groups
1

# Atomic Positions
# index  type   x(A)    y(A)    z(A)
0  He    0.0000  0.0000  0.0000

# Chiral Centers  Bond  BondDipoles  Bend  UreyBradley  Torsion  ImproperTorsion  OutOfPlane  Bond/Bond  Bond/Bend  Bend/Bend  StretchTorsion  BendTorsion
0 0 0 0 0 0 0 0 0 0 0 0 0

# Number of config moves
0
""",

    # 1-7: CBMC example — n-butane TraPPE united-atom 4-site
    # Ref: Martin & Siepmann, J. Phys. Chem. B 1998, 102, 2569
    "n-butane": """\
# n-butane TraPPE united-atom 4-site
# Model: CH3-CH2-CH2-CH3, fully flexible, no partial charges
# Ref: Martin & Siepmann, J. Phys. Chem. B 1998, 102, 2569

# critical constants: Temperature [T], Pressure [Pa], and acentric factor [-]
425.12
3796000.0
0.200

# Number of Atoms
4

# Number of Groups
1

# Atomic Positions (along chain axis, A)
# index  type    x(A)    y(A)    z(A)
0  CH3_sp3   0.0000  0.0000  0.0000
1  CH2_sp3   1.5400  0.0000  0.0000
2  CH2_sp3   2.5700  1.2500  0.0000
3  CH3_sp3   4.1100  1.2500  0.0000

# Chiral Centers  Bond  BondDipoles  Bend  UreyBradley  Torsion  ImproperTorsion  OutOfPlane  Bond/Bond  Bond/Bend  Bend/Bend  StretchTorsion  BendTorsion
0 3 0 2 0 1 0 0 0 0 0 0 0

# Bond stretch: atom1-atom2  type  k(K/A^2)  r0(A)
0 1 HARMONIC_BOND  96500.0  1.54
1 2 HARMONIC_BOND  96500.0  1.54
2 3 HARMONIC_BOND  96500.0  1.54

# Bending: atom1-atom2-atom3  type  k(K/rad^2)  theta0(deg)
0 1 2 HARMONIC_BEND  62500.0  114.0
1 2 3 HARMONIC_BEND  62500.0  114.0

# Torsion: atom1-atom2-atom3-atom4  type  parameters(K)
0 1 2 3 TRAPPE_DIHEDRAL  0.0  355.03  -68.19  791.32

# Number of config moves
0
""",
}

# ─────────────────────────────────────────────────────────────────
# Metadata
# ─────────────────────────────────────────────────────────────────

MOLECULE_META: dict[str, dict] = {
    "CO2": {
        "formula": "CO2",
        "molar_mass": 44.01,
        "n_sites": 3,
        "has_charge": True,
        "model": "TraPPE 3-site rigid",
        "paired_forcefield": "TraPPE-CO2",
    },
    "N2": {
        "formula": "N2",
        "molar_mass": 28.014,
        "n_sites": 3,
        "has_charge": True,
        "model": "TraPPE 3-site (COM charge)",
        "paired_forcefield": "TraPPE-N2",
    },
    "CH4": {
        "formula": "CH4",
        "molar_mass": 16.043,
        "n_sites": 1,
        "has_charge": False,
        "model": "TraPPE 1-site united-atom",
        "paired_forcefield": "TraPPE-CH4",
    },
    "H2O": {
        "formula": "H2O",
        "molar_mass": 18.015,
        "n_sites": 3,
        "has_charge": True,
        "model": "SPC/E",
        "paired_forcefield": "TraPPE-H2O",
    },
    "helium": {
        "formula": "He",
        "molar_mass": 4.003,
        "n_sites": 1,
        "has_charge": False,
        "model": "single LJ (void fraction probe)",
        "paired_forcefield": None,
    },
    "n-butane": {
        "formula": "C4H10",
        "molar_mass": 58.122,
        "n_sites": 4,
        "has_charge": False,
        "model": "TraPPE united-atom 4-site",
        "paired_forcefield": "TraPPE-alkane",
        "note": "CBMC example molecule. Requires TraPPE united-atom force field.",
    },
}
