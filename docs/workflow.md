# End-to-End Autonomous MOF Adsorption Research Workflow

This document describes the complete pipeline from a natural-language user request
to a structured research report with simulation data and isotherm plots, delivered
inside Feishu.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Feishu  (user-facing)                  │
│  Group chat message ──WebSocket──► feishu-mcp long-conn     │
│             ◄── reply / cloud doc / task / calendar ────────│
└─────────────────────────────────────────────────────────────┘
                            │ ▲
              event trigger │ │ results written back
                            ▼ │
┌─────────────────────────────────────────────────────────────┐
│                  featherflow  (orchestration brain)          │
│  LLM (Claude / GPT) + tool dispatcher                       │
│                                                              │
│  MCP servers mounted:                                        │
│  ├── feishu-mcp    ← Feishu read/write       (22 tools)     │
│  ├── raspa-mcp     ← RASPA2 knowledge layer  (14 tools)     │
│  └── Semantic Scholar API  ← literature search              │
│                                                              │
│  Built-in tools:                                            │
│  ├── shell_exec    → invoke the RASPA2 binary               │
│  └── file_read / file_write → manage .def / .input / CIF   │
└─────────────────────────────────────────────────────────────┘
                            │
               subprocess   │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   RASPA2  (physics engine)                   │
│  /tmp/raspa_runs/<MOF_NAME>/<pressure_bar>/                 │
│  └── Output/System_0/*.dat                                 │
└─────────────────────────────────────────────────────────────┘
```

### Component roles

| Component | Role | Replaces |
|-----------|------|----------|
| feishu-mcp | Human–agent interface + result delivery | Manually writing reports and sending messages |
| raspa-mcp | Molecular simulation domain knowledge | Reading the RASPA2 manual, crafting input files |
| Semantic Scholar | Literature intelligence | Searching papers, extracting force-field parameters |
| featherflow | Orchestration + reasoning | The researcher coordinating all of the above |
| RASPA2 | Physics: actual Monte Carlo / MD computation | Nothing — irreplaceable |

---

## Example Request

```
[Feishu group chat]
User: @AI  Study the adsorption of PH₃ in up to 10 MOF materials
           and select the top 3 best performers. You decide how to judge.
```

---

## Phase 1 — Task Understanding and Planning (LLM reasoning)

The message arrives via the feishu-mcp WebSocket long-connection listener
(`feishu-mcp.longconn`).  The LLM reads the available tool list and begins
internal chain-of-thought reasoning:

> *Goal: compare ≤ 10 MOFs for PH₃ adsorption and rank the top 3.*
> *PH₃ is non-standard — no built-in force field exists.*
> *Required steps:*
> *① find candidate MOFs  ② obtain PH₃ force-field parameters from literature*
> *③ run GCMC at multiple pressures  ④ aggregate isotherms  ⑤ rank  ⑥ report.*
> *Self-chosen evaluation criteria: equilibrium loading at 1 bar / 298 K (60 %)*
> *+ Henry coefficient at low pressure (40 %).*

The LLM emits an internal execution plan (not visible to the user):

```
step 1  search_papers("MOF PH3 adsorption")
step 2  extract ≤ 10 MOFs with known CIF files from the results
step 3  raspa-mcp.recommend_forcefield("PH3")  → obtain literature search terms
step 4  search_papers(<returned queries>)       → find PH3 LJ parameters
step 5  for each MOF × each pressure point:
          create_workspace → get_template → write files → validate → run → parse
step 6  collect all loadings → plot_isotherm_comparison → rank → write report
step 7  upload PNG + write Feishu cloud document → reply in group chat
```

---

## Phase 2 — Literature Search: Candidate MOFs

```python
# tool call 1
search_papers(
    query="metal-organic framework PH3 phosphine adsorption capacity",
    limit=20
)
```

The LLM parses titles and abstracts, prioritising structures with:
- experimental validation of PH₃ uptake
- available CIF files (CoRE-MOF database or supplementary data)

Example shortlist extracted from 20 papers:

```
MIL-101(Cr)   HKUST-1   ZIF-8    ZIF-67
UiO-66        UiO-66-NH₂  MOF-5   MIL-53(Al)
PCN-250       NOTT-300
```

---

## Phase 3 — PH₃ Force-Field Acquisition (critical bottleneck)

```python
# tool call 2
raspa-mcp.recommend_forcefield("PH3")
```

raspa-mcp responds:
```json
{
  "status": "non_standard",
  "message": "PH3 is not in the built-in library",
  "search_queries": [
    "PH3 phosphine Lennard-Jones force field parameters",
    "phosphine TraPPE molecular simulation epsilon sigma"
  ],
  "parameter_format": {
    "required": ["epsilon/K", "sigma/Angstrom", "partial_charges"],
    "typical_range": {"epsilon": "150-300 K", "sigma": "3.5-4.0 Å"}
  }
}
```

The LLM uses the returned search queries to call Semantic Scholar again:

```python
# tool call 3
search_papers(
    query="PH3 phosphine Lennard-Jones force field parameters molecular simulation"
)
```

From the retrieved full text the LLM extracts (example):

> *Becker et al. (2011) J. Chem. Phys. — TraPPE-UA parameters for PH₃:*
> *P: ε = 251.7 K, σ = 3.74 Å, q = −0.24 e*
> *H: ε = 20.0 K, σ = 2.50 Å, q = +0.08 e*

These numbers are held in the LLM's working memory and used to construct the
RASPA2 `.def` file content in the next phase.

---

## Phase 4 — Simulation Loop (repeated for each MOF × pressure point)

Isotherms require **one independent GCMC run per pressure point**.  A typical
pressure grid for PH₃ capture studies:

```
P = [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]  bar
```

The following sub-steps execute for every `(MOF, pressure)` combination.
MIL-101(Cr) at 1 bar is shown as a concrete example.

### 4a — Create workspace

```python
# tool call 4
raspa-mcp.create_workspace(
    work_dir="/tmp/raspa_runs",
    framework_name="MIL-101-Cr_1bar",
    cif_source_path="/data/cifs/MIL-101-Cr.cif"
)
```

Returns: `/tmp/raspa_runs/MIL-101-Cr_1bar/` directory tree ready.

### 4b — Fetch GCMC template

```python
# tool call 5
raspa-mcp.get_simulation_template("GCMC")
```

### 4c — LLM fills in parameters

The LLM substitutes all `${PLACEHOLDER}` tokens in the template:

```ini
SimulationType                GCMC
NumberOfCycles                50000
NumberOfInitializationCycles  10000
Temperature                   298.0
Pressure                      101325.0

Framework                     MIL-101-Cr
UnitCells                     2 2 2

Component 0 MoleculeName      PH3
  MoleculeDefinition          PH3
  TranslationProbability      0.5
  RotationProbability         0.5
  SwapProbability             1.0
  CreateNumberOfMolecules     0
```

### 4d — Write custom force-field files

Using featherflow's built-in file-write tool, the LLM writes the PH₃
parameters extracted from the literature to disk:

```
# pseudo_atoms.def  (PH3 — Becker 2011 TraPPE-UA)
P_ph3   P  30.97  251.7  3.74  -0.24  0  1  1
H_ph3   H   1.008  20.0  2.50  +0.08  0  1  0
```

### 4e — Validate before running

```python
# tool call 6
raspa-mcp.validate_simulation_input(content="... simulation.input content ...")
# → {"valid": true, "errors": [], "warnings": []}
```

### 4f — Execute RASPA2

```python
# tool call 7  (featherflow built-in shell_exec)
run_shell(
    command="cd /tmp/raspa_runs/MIL-101-Cr_1bar && $RASPA_DIR/bin/simulate simulation.input",
    timeout=600
)
```

Wall-clock time per run: 3–8 minutes depending on unit cell size and cycle count.

### 4g — Parse output

```python
# tool call 8
raspa-mcp.parse_raspa_output(
    output_dir="/tmp/raspa_runs/MIL-101-Cr_1bar/Output/System_0"
)
```

Returns structured JSON:
```json
{
  "loading": {
    "mol_per_kg": 8.42,
    "mg_per_g":   286.1,
    "cm3_STP_per_g": 4.73
  },
  "henry_coefficient": 2.31e-4,
  "average_energy_kJ_mol": -42.6,
  "convergence": "ok"
}
```

**Steps 4a – 4g repeat for all 10 MOFs × 7 pressure points = 70 individual runs.**
With serial execution: ~35–80 min total.
With parallel `shell_exec` (if featherflow supports concurrent jobs): ~10–15 min.

During the loop the LLM sends periodic progress replies to the Feishu group:

```python
feishu-mcp.reply_message(
    message_id="...",
    content="Simulation progress: 3/10 MOFs complete ✓ MIL-101(Cr) loading = 8.42 mol/kg"
)
```

---

## Phase 5 — Isotherm Plotting

After all runs complete, the per-pressure results for each MOF are assembled into
isotherm datasets.

### Single-MOF plot (one per MOF, embedded in detailed analysis sections)

```python
raspa-mcp.plot_isotherm(
    isotherm_data=[
        {"pressure_Pa": 1e3,  "loading_mol_kg": 0.9},
        {"pressure_Pa": 1e4,  "loading_mol_kg": 2.8},
        {"pressure_Pa": 1e5,  "loading_mol_kg": 8.42},
        # ... 7 points total
    ],
    output_path="/tmp/raspa_runs/MIL-101-Cr/isotherm.png",
    molecule="PH3",
    framework="MIL-101(Cr)",
    temperature_K=298.0,
)
```

### Top-3 comparison plot (placed in the conclusion section)

```python
raspa-mcp.plot_isotherm_comparison(
    datasets=[
        {"label": "MIL-101(Cr)", "isotherm_data": [...]},
        {"label": "NOTT-300",    "isotherm_data": [...]},
        {"label": "UiO-66-NH₂", "isotherm_data": [...]},
    ],
    output_path="/tmp/raspa_runs/comparison_top3.png",
    molecule="PH3",
    temperature_K=298.0,
)
```

Both tools use `matplotlib` with a non-interactive `Agg` backend and save
publication-ready PNG files (150 dpi, tight bounding box).

---

## Phase 6 — Ranking (LLM reasoning)

All 10 MOF results enter the LLM context.  The LLM applies its self-defined
scoring formula:

$$\text{score} = 0.6 \times \hat{q}_{1\,\text{bar}} \;+\; 0.4 \times \hat{K}_H$$

where $\hat{q}$ and $\hat{K}_H$ are min-max normalised values across the 10 MOFs.

| Rank | MOF | Loading (mol kg⁻¹) | Henry coeff. | Score |
|:----:|-----|--------------------|:------------:|:-----:|
| 🥇 | MIL-101(Cr) | 8.42 | 2.31 × 10⁻⁴ | 0.91 |
| 🥈 | NOTT-300 | 7.15 | 3.10 × 10⁻⁴ | 0.87 |
| 🥉 | UiO-66-NH₂ | 6.88 | 1.95 × 10⁻⁴ | 0.79 |
| 4 | HKUST-1 | 5.93 | 1.22 × 10⁻⁴ | 0.68 |
| … | … | … | … | … |

---

## Phase 7 — Result Delivery (back to Feishu)

Three layers of output are written into Feishu using feishu-mcp tools.

### Layer 1 — Group chat summary

```python
feishu-mcp.reply_message(
    message_id="...",
    content="""
✅ Simulation complete. Top 3 MOFs for PH₃ adsorption (298 K / 1 bar):

🥇 MIL-101(Cr)   8.42 mol/kg   Henry = 2.31e-4
🥈 NOTT-300       7.15 mol/kg   Henry = 3.10e-4
🥉 UiO-66-NH₂    6.88 mol/kg   Henry = 1.95e-4

Full report (isotherms, raw data, references):
https://feishu.cn/docx/xxxxxxxx
"""
)
```

### Layer 2 — Feishu cloud document

```python
doc = feishu-mcp.create_document(title="MOF PH₃ Adsorption Study — 2026-03-01")

feishu-mcp.write_document_markdown(
    document_id=doc["document_id"],
    content="""
# MOF PH₃ Adsorption Study
**Date**: 2026-03-01  |  **Conditions**: GCMC, 298 K, 0.01–10 bar

## Methodology
- Candidate MOFs: selected via Semantic Scholar literature search
- PH₃ force field: TraPPE-UA, Becker et al., J. Chem. Phys. 2011
- Simulation: RASPA2 v2.0.45, 50 000 production cycles
- Ranking: 60 % loading at 1 bar + 40 % Henry coefficient

## Results Summary
| MOF | Loading (mol/kg) | Henry coeff. | Score |
...

## Top-3 Isotherm Comparison
[comparison_top3.png embedded here]

## Individual MOF Analysis
### 1. MIL-101(Cr)
Open metal sites provide strong coordinative attraction for the PH₃ lone pair...
[MIL-101-Cr_isotherm.png embedded here]
...
"""
)

# Upload PNG files and embed as blocks
for png_path in ["/tmp/raspa_runs/comparison_top3.png", ...]:
    upload = feishu-mcp.upload_file_and_share(file_path=png_path)
    feishu-mcp.insert_file_block(
        document_id=doc["document_id"],
        file_token=upload["file_token"]
    )
```

### Layer 3 — Follow-up task (optional)

```python
task = feishu-mcp.create_task(
    title="Validate MIL-101(Cr) PH₃ adsorption against experimental data",
    due_time="2026-03-08T18:00:00",
    description=(
        "Simulation score: 0.91.  Please cross-check against the experimental "
        "isotherm in doi:10.xxxx and confirm the force-field transferability."
    )
)
feishu-mcp.assign_task(task_id=task["task_id"], assignee=user_open_id)
```

---

## Complete Tool-Call Sequence

```
feishu-mcp.longconn          ── receive IM message event ──────► featherflow wakes up
feishu-mcp.get_chat_members  ── resolve sender identity
feishu-mcp.reply_message     ── "Received. Starting research..."

  [literature search × 2]
  search_papers("MOF PH3 adsorption")
  search_papers("PH3 force field parameters")

  [simulation loop × 10 MOFs × 7 pressures = 70 iterations]
  raspa-mcp.recommend_forcefield("PH3")
  raspa-mcp.create_workspace(...)
  raspa-mcp.get_simulation_template("GCMC")
  file_write(pseudo_atoms.def, force_field_mixing_rules.def, PH3.def)
  raspa-mcp.validate_simulation_input(...)
  shell_exec → RASPA2 binary
  raspa-mcp.parse_raspa_output(...)
  feishu-mcp.reply_message   ── progress update (every ~3 MOFs)

  [plotting]
  raspa-mcp.plot_isotherm(...)          × 10  (one per MOF)
  raspa-mcp.plot_isotherm_comparison(...)     (top-3 overlay)

  [report delivery]
  feishu-mcp.create_document(...)
  feishu-mcp.write_document_markdown(...)
  feishu-mcp.upload_file_and_share(...)  × 11  (10 individual + 1 comparison)
  feishu-mcp.insert_file_block(...)      × 11
  feishu-mcp.create_task(...)
  feishu-mcp.assign_task(...)
  feishu-mcp.reply_message   ── final summary with document link
```

Total tool calls: approximately **120–140** per 10-MOF study.

---

## Timing Estimate

| Phase | Serial | Parallel shell_exec |
|-------|:------:|:-------------------:|
| Literature search | ~1 min | ~1 min |
| 70 RASPA2 runs (3 min avg) | ~210 min | ~20 min |
| Plotting (14 PNG files) | <1 min | <1 min |
| Report writing + Feishu upload | ~2 min | ~2 min |
| **Total** | **~215 min** | **~25 min** |

Enabling concurrent `shell_exec` in featherflow is therefore strongly recommended
for any study involving more than 3 MOFs or more than 3 pressure points.

---

## Why Isotherms Require Multiple Runs

A single GCMC simulation at one pressure point produces one loading value — a
single dot on the isotherm curve.  To obtain a smooth curve the LLM must
**plan ahead** to run the same MOF at N different pressures and then aggregate
the results.  This is not derivable from any single tool call; it requires the
LLM to reason about the scientific protocol before issuing the first `create_workspace`
call.  The `plot_isotherm` and `plot_isotherm_comparison` tools in raspa-mcp
accept the aggregated list of `{pressure, loading}` dicts that result from
this multi-run strategy.

---

## Key Design Principles

1. **LLM as scientist, tools as instruments** — the LLM decides the experimental
   protocol, pressure grid, scoring formula, and report structure.  The MCP
   tools handle the deterministic mechanics (file layout, syntax, parsing, plotting).

2. **Non-standard molecules are first-class** — `recommend_forcefield()` never
   hard-fails; for unknown molecules it returns Semantic Scholar search queries
   that allow the LLM to locate parameters in the primary literature.

3. **Validation before execution** — `validate_simulation_input()` prevents
   obviously broken RASPA2 inputs from wasting minutes of compute time.

4. **Results delivered where the user already is** — the entire output (summary,
   full report, isotherm images, follow-up task) is delivered inside Feishu
   without requiring the user to open a terminal, a browser, or any other tool.
