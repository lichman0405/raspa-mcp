# raspa-mcp

[![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-1.4%2B-6366f1?logo=anthropic&logoColor=white)](https://modelcontextprotocol.io/)
[![Tests](https://img.shields.io/badge/tests-41%20passed-brightgreen?logo=pytest&logoColor=white)](tests/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![NumPy](https://img.shields.io/badge/numpy-2.x-013243?logo=numpy&logoColor=white)](https://numpy.org/)
[![Matplotlib](https://img.shields.io/badge/matplotlib-3.7%2B-11557c?logo=plotly&logoColor=white)](https://matplotlib.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![RASPA2](https://img.shields.io/badge/RASPA2-2.x-orange)](https://github.com/iRASPA/RASPA2)

> **Turn any AI agent into a molecular simulation expert — overnight.**

`raspa-mcp` is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that wraps [RASPA2](https://github.com/iRASPA/RASPA2) — the gold-standard molecular simulation engine for porous materials — into a clean, agent-friendly tool layer. Feed it a CIF file and a molecule name; let your agent handle the rest.

---

## Why raspa-mcp?

Running RASPA2 correctly requires deep expertise: choosing the right ensemble, setting unit cell replications, picking force fields, validating Ewald summation parameters, and parsing Fortran-style output files. Historically this knowledge lived in the heads of computational chemists and nowhere else.

`raspa-mcp` encodes that expertise as **24 structured MCP tools** — covering every major simulation type RASPA2 supports — so that an LLM agent like [featherflow](https://github.com/your-org/featherflow) can autonomously design, validate, execute, and interpret molecular simulations without human intervention.

---

## Features at a Glance

### Simulation Templates (12 types)
| Template | Purpose |
|----------|---------|
| `GCMC` | Grand Canonical Monte Carlo — adsorption isotherms |
| `Widom` | Widom test-particle insertion — Henry coefficient at infinite dilution |
| `VoidFraction` | Helium void fraction (prerequisite for GCMC) |
| `NVT-MC` | Fixed-N Monte Carlo — configurational sampling, RDF |
| `NPT-MC` | Variable-volume MC — equilibrium density, flexible cell |
| `MD` | NVT Molecular Dynamics — diffusion, transport |
| `NPT-MD` | Constant-pressure MD — thermal expansion |
| `NVE-MD` | Microcanonical MD — energy conservation benchmarking |
| `GCMCMixture` | Binary mixture GCMC — co-adsorption, selectivity |
| `CBMC` | Configurational-Bias MC — chain/flexible molecules (C4+) |
| `TI` | Thermodynamic Integration — free energy ΔA |
| `FlexibleMD` | Flexible-framework MD — breathing, gate opening |

### Output Parsing (7 parsers)
- **Adsorption loading** — mol/kg, mg/g, cm³(STP)/g, molecules/uc, ±errors
- **Isosteric heat Qst** — from energy fluctuations [kJ/mol]
- **Henry coefficient & μ_ex** — from Widom insertion, −RT ln(W)
- **Helium void fraction** — direct extraction
- **Radial distribution function g(r)** — peak detection, full r/g(r) arrays
- **MSD → Diffusion coefficients** — self D_s and collective D_c via Einstein relation (NumPy linear fit, latter 50% of trajectory)
- **3D density grid** — 2D slice extraction from `.grid` files
- **Thermodynamic Integration** — trapezoidal ∫⟨∂U/∂λ⟩dλ → ΔA [kJ/mol]
- **Multi-component mixture** — per-component loading with backward compatibility

### Analysis Tools
- **Selectivity S_AB** — `(x_A/x_B) / (y_A/y_B)` from mixture loadings
- **Isotherm plotting** — single and multi-MOF comparison PNGs (matplotlib)
- **Density slice plotting** — heatmap PNG from 3D grid data

### Built-in Knowledge Base
- **5 molecules**: CO2, N2, CH4, H2O, helium, n-butane (TraPPE / SPC-E)
- **5 force fields**: TraPPE-CO2/N2/CH4/H2O, UFF — with mixing rules, pseudo-atom definitions
- **Input validator** — catches 20+ common mistakes before RASPA2 ever runs
- **Environment checker & installer** — conda and source install, 6-shell support

---

## Installation

```bash
# 1. Clone
git clone https://github.com/your-org/raspa-mcp
cd raspa-mcp

# 2. Create virtualenv (Python 3.11+)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install
pip install -e ".[dev]"
```

RASPA2 itself is not bundled. Install it separately:

```bash
# via conda (recommended)
conda install -c conda-forge raspa2

# or let raspa-mcp install it for you
raspa-mcp  # then call install_raspa2() from your agent
```

> RASPA2 source: [https://github.com/iRASPA/RASPA2](https://github.com/iRASPA/RASPA2)
> Reference: D. Dubbeldam, S. Calero, D.E. Ellis, R.Q. Snurr, *Mol. Simul.* **42**, 81–101 (2016)

---

## Quickstart — featherflow

Add to your `featherflow` config:

```json
{
  "tools": {
    "mcpServers": {
      "raspa2": {
        "command": "python",
        "args": ["-m", "raspa_mcp.server"],
        "toolTimeout": 30,
        "env": {}
      }
    }
  }
}
```

Your agent can now autonomously:

```
User: Study CO2 adsorption in ZIF-8 at 298 K from 0.1 to 50 bar.

Agent:
  1. raspa-mcp.check_raspa2_environment()
  2. raspa-mcp.get_simulation_template("VoidFraction")   → run RASPA2
  3. raspa-mcp.parse_raspa_output(...)                   → void fraction = 0.47
  4. raspa-mcp.get_simulation_template("GCMC")           → fill placeholders × 7 pressures
  5. raspa-mcp.validate_simulation_input(...)            → clean
  6. shell_exec → RASPA2 × 7
  7. raspa-mcp.parse_raspa_output(...)                   → isotherm data
  8. raspa-mcp.plot_isotherm(...)                        → ZIF-8_CO2.png
  9. feishu-mcp.upload_file_and_share(...)               → report delivered
```

No human intervention required.

---

## MCP Tools Reference

| Tool | Category |
|------|----------|
| `list_simulation_types` | Discovery |
| `get_simulation_template` | Input generation |
| `get_parameter_docs` | Input generation |
| `list_available_forcefields` | Force field |
| `get_forcefield_files` | Force field |
| `recommend_forcefield` | Force field |
| `list_available_molecules` | Molecule |
| `get_molecule_definition` | Molecule |
| `create_workspace` | Workspace |
| `validate_simulation_input` | Validation |
| `parse_raspa_output` | Output parsing |
| `parse_rdf_output` | Output parsing |
| `parse_msd_output` | Output parsing |
| `parse_ti_output` | Output parsing |
| `parse_density_grid` | Output parsing |
| `calculate_selectivity` | Analysis |
| `plot_isotherm` | Visualization |
| `plot_isotherm_comparison` | Visualization |
| `plot_density_slice` | Visualization |
| `check_raspa2_environment` | Environment |
| `install_raspa2` | Environment |

---

## Testing

```bash
pytest tests/ -q          # 41 tests, ~1.5 s
ruff check raspa_mcp/ tests/
```

---

## Architecture

```
raspa-mcp/
├── raspa_mcp/
│   ├── server.py        # 21 MCP tools (FastMCP, stdio transport)
│   ├── parser.py        # Output parsers (loading, RDF, MSD, TI, density)
│   ├── validator.py     # Input validator (20+ rule checks)
│   ├── installer.py     # RASPA2 env detection + conda/source install
│   └── data/
│       ├── templates.py    # 12 simulation.input templates
│       ├── molecules.py    # 6 molecule definitions + metadata
│       └── forcefields.py  # 5 force field file sets
├── tests/
│   └── test_server.py   # 41 unit tests
└── docs/
    └── workflow.md      # Full autonomous research workflow walkthrough
```

---

## Full Business Workflow

See [docs/workflow.md](docs/workflow.md) for a complete end-to-end walkthrough of an autonomous MOF screening study using featherflow + raspa-mcp + RASPA2 + feishu-mcp, from a single chat message to a ranked report delivered to Feishu — approximately 120–140 tool calls, zero human steps.

---

## License

MIT

---

## Acknowledgements

Built on top of [RASPA2](https://github.com/iRASPA/RASPA2) by Dubbeldam, Calero, Ellis & Snurr. Force-field parameters from the [TraPPE](http://trappe.oit.umn.edu/) family (Martin, Siepmann et al.) and the [Universal Force Field](https://doi.org/10.1021/ja00051a040) (Rappé et al.).
