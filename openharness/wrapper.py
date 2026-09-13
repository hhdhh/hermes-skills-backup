#!/usr/bin/env python3
"""OpenHarness wrapper for 慧慧's agent system.

Use this from any Python code or sub-agent to dispatch tasks to OpenHarness
without dealing with TTY/script complications.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

VENV_PY = Path.home() / ".openharness-venv" / "bin" / "python"


def oh_dry_run(prompt: str, *, cwd: str | None = None, model: str = "MiniMax-M3") -> dict:
    """Run `oh --dry-run -p "<prompt>"` and return parsed preview.
    
    Returns dict with: readiness, profile, model, base_url, skills_count,
    tools_count, likely_skills, likely_commands, system_prompt_chars.
    """
    args = [str(VENV_PY), "-m", "openharness", "--dry-run", "-p", prompt]
    if model:
        args.extend(["--model", model])
    env = os.environ.copy()
    env["PYTHONPATH"] = ""  # unset
    result = subprocess.run(args, capture_output=True, text=True, cwd=cwd, env=env)
    return _parse_dry_run(result.stdout)


def oh_run(prompt: str, *, cwd: str | None = None, model: str = "MiniMax-M3", timeout: int = 180) -> str:
    """Run `oh -p "<prompt>"` (with pty) and return the model's response.
    
    Uses script -q to provide a pty (Ink requirement).
    """
    args = [str(VENV_PY), "-m", "openharness", "-p", prompt]
    if model:
        args.extend(["--model", model])
    cmd = ["script", "-q", "/dev/null"] + args
    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    result = subprocess.run(cmd, input="", capture_output=True, text=True, 
                            cwd=cwd, env=env, timeout=timeout)
    return _clean_response(result.stdout)


def ohmo_run(prompt: str, *, cwd: str | None = None, timeout: int = 180) -> str:
    """Run `ohmo -p "<prompt>"` (with soul/user context) and return response."""
    args = [str(VENV_PY), "-m", "ohmo", "-p", prompt]
    cmd = ["script", "-q", "/dev/null"] + args
    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    result = subprocess.run(cmd, input="", capture_output=True, text=True,
                            cwd=cwd, env=env, timeout=timeout)
    return _clean_response(result.stdout)


def _parse_dry_run(output: str) -> dict:
    """Parse the formatted dry-run preview into a dict."""
    result = {
        "readiness": "unknown",
        "profile": None,
        "model": None,
        "base_url": None,
        "skills_count": 0,
        "tools_count": 0,
        "commands_count": 0,
        "likely_skills": [],
        "likely_commands": [],
    }
    in_likely_skills = False
    in_likely_commands = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("- level:"):
            result["readiness"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- profile:"):
            result["profile"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- model:"):
            result["model"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- base_url:"):
            result["base_url"] = stripped.split(":", 1)[1].strip()
        elif stripped == "- skills:":
            in_likely_skills = True
            in_likely_commands = False
            continue
        elif stripped == "- slash commands:":
            in_likely_skills = False
            in_likely_commands = True
            continue
        elif stripped.startswith("- skills:") and stripped.split(":", 1)[1].strip().isdigit():
            try: result["skills_count"] = int(stripped.split(":", 1)[1].strip())
            except: pass
        elif stripped.startswith("- slash commands:") and stripped.split(":", 1)[1].strip().isdigit():
            try: result["commands_count"] = int(stripped.split(":", 1)[1].strip())
            except: pass
        elif stripped.startswith("- built-in tools:"):
            try: result["tools_count"] = int(stripped.split(":", 1)[1].strip())
            except: pass
        elif stripped.startswith("- ") and "(score=" in stripped:
            name = stripped[2:].split(" (score=")[0]
            if in_likely_skills:
                result["likely_skills"].append(name)
            elif in_likely_commands:
                result["likely_commands"].append(name)
        elif stripped and not stripped.startswith("-"):
            # End of likely matches section
            in_likely_skills = False
            in_likely_commands = False
    return result


def _clean_response(output: str) -> str:
    """Strip TUI artifacts (^D, escape codes) from output."""
    import re
    output = re.sub(r"\^\[\[?[A-Za-z]", "", output)
    output = re.sub(r"\^\[\d+[A-Za-z]?", "", output)
    output = re.sub(r"\[\?\d+[hl]", "", output)
    output = re.sub(r"\[\d+;\d+H", "", output)
    output = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output)
    output = re.sub(r"^\s*\^D\s*", "", output, flags=re.MULTILINE)
    return output.strip()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: wrapper.py [dry-run|run|ohmo] <prompt>")
        sys.exit(1)
    mode = sys.argv[1]
    prompt = " ".join(sys.argv[2:])
    if mode == "dry-run":
        import json
        print(json.dumps(oh_dry_run(prompt), indent=2, ensure_ascii=False))
    elif mode == "run":
        print(oh_run(prompt))
    elif mode == "ohmo":
        print(ohmo_run(prompt))
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
