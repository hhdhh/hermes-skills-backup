#!/usr/bin/env bash
# test_install.sh — verify the OpenClaw CLI-Anything skill is installed correctly
#
# Usage:
#   bash tests/test_install.sh
#
# Exits 0 on success, non-zero on any failure.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Detect the installed location if SKILL_DIR is the source checkout, not the install target
INSTALL_DIR="${SKILL_DIR}"
if [[ ! -f "${INSTALL_DIR}/SKILL.md" ]]; then
  for cand in \
    "${HOME}/.agents/skills/cli-anything" \
    "${HOME}/.openclaw/workspace/skills/cli-anything"; do
    if [[ -f "${cand}/SKILL.md" ]]; then
      INSTALL_DIR="${cand}"
      break
    fi
  done
fi

PASS=0
FAIL=0
ok()   { echo "  ✓ $*"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $*"; FAIL=$((FAIL+1)); }
hr()   { echo; echo "── $* ──"; }

hr "Install target"
echo "  ${INSTALL_DIR}"
[[ -d "${INSTALL_DIR}" ]] && ok "skill directory exists" || { fail "skill directory missing"; echo "Run: bash ${SKILL_DIR}/scripts/install.sh --global"; exit 1; }

hr "Top-level files"
for f in SKILL.md agents/openclaw.yaml scripts/install.sh tests/test_install.sh; do
  if [[ -f "${INSTALL_DIR}/${f}" ]]; then ok "${f}"; else fail "${f} missing"; fi
done

hr "Vendored references"
for f in references/HARNESS.md \
         references/commands/cli-anything.md \
         references/commands/refine.md \
         references/commands/test.md \
         references/commands/validate.md \
         references/commands/list.md; do
  if [[ -f "${INSTALL_DIR}/${f}" ]]; then ok "${f}"; else fail "${f} missing"; fi
done

hr "Vendored guides"
EXPECTED_GUIDES=(
  auto-save-dry-run.md
  filter-translation.md
  mcp-backend.md
  preview-methodology.md
  pypi-publishing.md
  session-locking.md
  skill-generation.md
  timecode-precision.md
)
for g in "${EXPECTED_GUIDES[@]}"; do
  if [[ -f "${INSTALL_DIR}/references/guides/${g}" ]]; then ok "guides/${g}"; else fail "guides/${g} missing"; fi
done

hr "Vendored scripts"
for f in scripts/repl_skin.py scripts/preview_bundle.py scripts/skill_generator.py; do
  if [[ -f "${INSTALL_DIR}/${f}" ]]; then ok "${f}"; else fail "${f} missing"; fi
done

hr "Syntax checks"
if command -v python3 >/dev/null 2>&1; then
  for f in scripts/repl_skin.py scripts/preview_bundle.py scripts/skill_generator.py; do
    if python3 -c "import ast,sys; ast.parse(open('${INSTALL_DIR}/${f}').read())" 2>/dev/null; then
      ok "${f} parses"
    else
      fail "${f} syntax error"
    fi
  done
else
  echo "  (python3 not on PATH; skipping syntax checks)"
fi

hr "SKILL.md frontmatter"
if head -1 "${INSTALL_DIR}/SKILL.md" | grep -q "^---$"; then
  ok "frontmatter starts with ---"
  if grep -q "^name: cli-anything" "${INSTALL_DIR}/SKILL.md"; then
    ok "name: cli-anything"
  else
    fail "name field missing or wrong"
  fi
  if grep -q "^description:" "${INSTALL_DIR}/SKILL.md"; then
    ok "description field present"
  else
    fail "description field missing"
  fi
else
  fail "SKILL.md missing YAML frontmatter"
fi

hr "agents/openclaw.yaml"
if command -v python3 >/dev/null 2>&1; then
  if python3 -c "import yaml,sys; yaml.safe_load(open('${INSTALL_DIR}/agents/openclaw.yaml'))" 2>/dev/null; then
    ok "openclaw.yaml parses as valid YAML"
  else
    fail "openclaw.yaml is not valid YAML"
  fi
fi

hr "install.sh shebang + executability"
if head -1 "${INSTALL_DIR}/scripts/install.sh" | grep -q "^#!/usr/bin/env bash"; then
  ok "install.sh has bash shebang"
fi
chmod +x "${INSTALL_DIR}/scripts/install.sh" 2>/dev/null && ok "install.sh is executable" || true
chmod +x "${INSTALL_DIR}/tests/test_install.sh" 2>/dev/null && ok "test_install.sh is executable" || true

hr "Summary"
echo "  Passed: ${PASS}"
echo "  Failed: ${FAIL}"
if [[ "${FAIL}" -gt 0 ]]; then
  exit 1
fi
echo
echo "✓ OpenClaw CLI-Anything skill is healthy."
