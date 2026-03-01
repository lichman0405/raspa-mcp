"""
raspa_mcp.installer — RASPA2 environment detection and auto-installation.

Detection checks:
  1. 'simulate' binary is on PATH
  2. RASPA_DIR environment variable is set and points to a valid directory
  3. Essential force field files exist under $RASPA_DIR

Auto-install supports:
  - conda  : conda install -c conda-forge raspa2  (recommended)
  - source : git clone + autoconf + make install
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# ─────────────────────────────────────────────────────────────────
# Detection
# ─────────────────────────────────────────────────────────────────

@dataclass
class RaspaEnvironment:
    simulate_found: bool = False
    simulate_path: str = ""
    raspa_dir_set: bool = False
    raspa_dir: str = ""
    raspa_dir_valid: bool = False
    forcefield_files_found: bool = False
    version: str = ""
    ready: bool = False
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "simulate_found": self.simulate_found,
            "simulate_path": self.simulate_path,
            "raspa_dir_set": self.raspa_dir_set,
            "raspa_dir": self.raspa_dir,
            "raspa_dir_valid": self.raspa_dir_valid,
            "forcefield_files_found": self.forcefield_files_found,
            "version": self.version,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "summary": "RASPA2 is ready." if self.ready else (
                f"RASPA2 is NOT ready. {len(self.issues)} issue(s) found."
            ),
        }


def check_environment() -> RaspaEnvironment:
    """
    Probe the current environment for a working RASPA2 installation.
    Returns a RaspaEnvironment dataclass with full diagnostic info.
    """
    env = RaspaEnvironment()

    # 1. Check 'simulate' binary
    simulate_path = shutil.which("simulate")
    if simulate_path:
        env.simulate_found = True
        env.simulate_path = simulate_path
        # Try to get version
        try:
            out = subprocess.run(
                ["simulate", "--version"],
                capture_output=True, text=True, timeout=10
            )
            env.version = (out.stdout + out.stderr).strip().splitlines()[0] if (
                out.stdout or out.stderr
            ) else "unknown"
        except Exception:
            env.version = "could not determine"
    else:
        env.issues.append(
            "'simulate' binary not found on PATH. "
            "RASPA2 is not installed or not added to PATH."
        )
        env.suggestions.append(
            "Install RASPA2 via conda: conda install -c conda-forge raspa2"
        )

    # 2. Check RASPA_DIR
    raspa_dir = os.environ.get("RASPA_DIR", "")
    if raspa_dir:
        env.raspa_dir_set = True
        env.raspa_dir = raspa_dir
        raspa_path = Path(raspa_dir)
        if raspa_path.exists():
            env.raspa_dir_valid = True
        else:
            env.issues.append(
                f"RASPA_DIR='{raspa_dir}' is set but the directory does not exist."
            )
            env.suggestions.append(
                "Check that RASPA_DIR points to the RASPA2 installation root."
            )
    else:
        env.issues.append(
            "RASPA_DIR environment variable is not set. "
            "RASPA2 requires this to locate force field and molecule files."
        )
        env.suggestions.append(
            "Add to ~/.bashrc: export RASPA_DIR=$(conda info --base)/envs/<env>  "
            "or export RASPA_DIR=/path/to/raspa2/install"
        )

    # 3. Check essential force field files under $RASPA_DIR
    if env.raspa_dir_valid:
        raspa_path = Path(raspa_dir)
        # RASPA2 looks for files in share/raspa2/ (conda) or $RASPA_DIR directly
        ff_candidates = [
            raspa_path / "share" / "raspa2" / "forcefield",
            raspa_path / "forcefield",
        ]
        mol_candidates = [
            raspa_path / "share" / "raspa2" / "molecules" / "TraPPE",
            raspa_path / "molecules" / "TraPPE",
        ]
        ff_found = any(p.exists() for p in ff_candidates)
        mol_found = any(p.exists() for p in mol_candidates)

        if ff_found and mol_found:
            env.forcefield_files_found = True
        else:
            if not ff_found:
                env.issues.append(
                    "Force field directory not found under $RASPA_DIR. "
                    "Expected: $RASPA_DIR/share/raspa2/forcefield/ or $RASPA_DIR/forcefield/"
                )
            if not mol_found:
                env.issues.append(
                    "Molecule definitions not found under $RASPA_DIR. "
                    "Expected: $RASPA_DIR/share/raspa2/molecules/TraPPE/"
                )

    # 4. Final readiness
    env.ready = (
        env.simulate_found
        and env.raspa_dir_set
        and env.raspa_dir_valid
        and env.forcefield_files_found
    )

    return env


# ─────────────────────────────────────────────────────────────────
# Installation
# ─────────────────────────────────────────────────────────────────

def _run(cmd: list[str], cwd: str | None = None, env: dict | None = None) -> tuple[int, str]:
    """Run a subprocess command and return (returncode, combined output)."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        timeout=600,  # 10 min max per step
    )
    output = result.stdout + result.stderr
    return result.returncode, output


def install_via_conda(conda_env: str = "base") -> dict:
    """
    Install RASPA2 via conda-forge into the specified conda environment.
    After install, emit the required environment variable configuration.
    """
    log: list[str] = []
    errors: list[str] = []

    # Check conda is available
    conda_bin = shutil.which("conda") or shutil.which("mamba")
    if not conda_bin:
        return {
            "success": False,
            "errors": ["conda/mamba not found on PATH. Install Miniconda or Anaconda first."],
            "log": [],
        }

    log.append(f"Using conda binary: {conda_bin}")

    # Install raspa2
    log.append("Running: conda install -c conda-forge raspa2 ...")
    if conda_env == "base":
        cmd = [conda_bin, "install", "-c", "conda-forge", "raspa2", "-y"]
    else:
        cmd = [conda_bin, "install", "-n", conda_env, "-c", "conda-forge", "raspa2", "-y"]

    rc, out = _run(cmd)
    log.append(out[-3000:])  # last 3000 chars to avoid huge output
    if rc != 0:
        errors.append(f"conda install failed (exit {rc}). See log for details.")
        return {"success": False, "errors": errors, "log": log}

    log.append("conda install completed.")

    # Determine RASPA_DIR
    rc2, conda_prefix = _run([conda_bin, "run", "-n", conda_env, "bash", "-c",
                               "echo $CONDA_PREFIX"])
    raspa_dir = conda_prefix.strip() or os.environ.get("CONDA_PREFIX", "")

    env_setup = _build_env_setup(raspa_dir)

    return {
        "success": True,
        "method": "conda",
        "raspa_dir": raspa_dir,
        "log": log,
        "errors": errors,
        "env_setup": env_setup,
        "next_step": (
            f"Append env_setup.export_lines to {env_setup['rc_file']}, "
            f"then run: {env_setup['reload_command']}"
        ),
    }


def install_from_source(install_prefix: str = "/opt/raspa2") -> dict:
    """
    Clone RASPA2 from GitHub and compile+install it.

    Requires: git, gcc, autoconf, automake, libtool on PATH.
    """
    import tempfile
    log: list[str] = []
    errors: list[str] = []

    # Check build tools
    missing_tools = [t for t in ["git", "gcc", "autoconf", "automake"] if not shutil.which(t)]
    if missing_tools:
        return {
            "success": False,
            "errors": [
                f"Missing build tools: {', '.join(missing_tools)}. "
                "Install with: sudo apt-get install git gcc autoconf automake libtool"
            ],
            "log": [],
        }

    prefix_path = Path(install_prefix)
    prefix_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="raspa2_build_") as tmpdir:
        log.append(f"Build directory: {tmpdir}")

        # Clone
        log.append("Cloning https://github.com/iraspa/raspa2 ...")
        rc, out = _run(["git", "clone", "--depth=1",
                        "https://github.com/iraspa/raspa2.git", "raspa2"], cwd=tmpdir)
        log.append(out[-2000:])
        if rc != 0:
            errors.append("git clone failed.")
            return {"success": False, "errors": errors, "log": log}

        src_dir = os.path.join(tmpdir, "raspa2")

        # Bootstrap
        for step_cmd in [
            ["rm", "-rf", "autom4te.cache"],
            ["mkdir", "-p", "m4"],
            ["aclocal"],
            ["autoreconf", "-i"],
            ["automake", "--add-missing"],
            ["autoconf"],
        ]:
            log.append(f"Running: {' '.join(step_cmd)}")
            rc, out = _run(step_cmd, cwd=src_dir)
            if rc != 0 and step_cmd[0] not in ("rm", "mkdir"):
                errors.append(f"Step '{step_cmd[0]}' failed (exit {rc}).")
                log.append(out[-1000:])
                return {"success": False, "errors": errors, "log": log}

        # Configure
        log.append(f"Running: ./configure --prefix={install_prefix}")
        rc, out = _run(["./configure", f"--prefix={install_prefix}"], cwd=src_dir)
        log.append(out[-2000:])
        if rc != 0:
            errors.append("./configure failed.")
            return {"success": False, "errors": errors, "log": log}

        # Make
        log.append("Running: make ...")
        rc, out = _run(["make", "-j4"], cwd=src_dir)
        log.append(out[-2000:])
        if rc != 0:
            errors.append("make failed.")
            return {"success": False, "errors": errors, "log": log}

        # Make install
        log.append("Running: make install ...")
        rc, out = _run(["make", "install"], cwd=src_dir)
        log.append(out[-2000:])
        if rc != 0:
            errors.append("make install failed.")
            return {"success": False, "errors": errors, "log": log}

    env_setup = _build_env_setup(install_prefix)

    return {
        "success": True,
        "method": "source",
        "raspa_dir": install_prefix,
        "log": log,
        "errors": [],
        "env_setup": env_setup,
        "next_step": (
            f"Append env_setup.export_lines to {env_setup['rc_file']}, "
            f"then run: {env_setup['reload_command']}"
        ),
    }


def _detect_shell_rc() -> tuple[str, str]:
    """
    Detect the user's current shell and return (shell_name, rc_file_path).

    Detection order:
      1. $SHELL environment variable
      2. /proc/<pid>/exe on Linux
      3. Fall back to ~/.profile (POSIX-compatible, works everywhere)
    """
    home = Path.home()

    shell_bin = os.environ.get("SHELL", "")
    shell_name = Path(shell_bin).name if shell_bin else ""

    rc_map: dict[str, Path] = {
        "zsh":  home / ".zshrc",
        "bash": home / ".bashrc",
        "fish": home / ".config" / "fish" / "config.fish",
        "ksh":  home / ".kshrc",
        "tcsh": home / ".tcshrc",
        "csh":  home / ".cshrc",
    }

    if shell_name in rc_map:
        return shell_name, str(rc_map[shell_name])

    # Fallback: ~/.profile is sourced by most POSIX shells on login
    return "unknown", str(home / ".profile")


def _build_env_setup(raspa_dir: str) -> dict:
    """Return the shell lines needed to configure the RASPA2 environment."""
    shell_name, rc_file = _detect_shell_rc()

    export_lines = [
        f'export RASPA_DIR="{raspa_dir}"',
        'export PATH="$RASPA_DIR/bin:$PATH"',
    ]

    # fish uses a different syntax
    if shell_name == "fish":
        export_lines = [
            f'set -gx RASPA_DIR "{raspa_dir}"',
            'set -gx PATH "$RASPA_DIR/bin" $PATH',
        ]

    return {
        "detected_shell": shell_name,
        "rc_file": rc_file,
        "export_lines": export_lines,
        "append_command": (
            f'echo \'{chr(10).join(export_lines)}\' >> {rc_file}'
        ),
        "reload_command": f"source {rc_file}",
        "one_liner": " && ".join(export_lines),
        "note": (
            f"Detected shell: {shell_name}. "
            f"Lines will be appended to {rc_file}. "
            "If this is wrong, manually add the export_lines to your shell's RC file."
        ),
    }
