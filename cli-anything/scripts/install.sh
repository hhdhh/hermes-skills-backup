#!/usr/bin/env bash
# install.sh — install the CLI-Anything skill for OpenClaw
#
# Usage:
#   bash scripts/install.sh --global        # install to ~/.agents/skills/
#   bash scripts/install.sh --workspace     # install to ~/.openclaw/workspace/skills/
#   bash scripts/install.sh --target PATH   # install to a custom directory
#   bash scripts/install.sh --uninstall     # remove the installed copy
#
# This script vendors CLI-Anything's HARNESS.md, commands/, guides/, and helper
# scripts from a local CLI-Anything repository checkout. If the local checkout
# is unavailable it downloads the canonical resources from GitHub.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT=""
PLUGIN_DIR=""
PREVIEW_PROTOCOL=""

# Default install target (user-global)
TARGET_DIR="${HOME}/.agents/skills"
MODE="global"

# ----------------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --global)
      TARGET_DIR="${HOME}/.agents/skills"
      MODE="global"
      shift
      ;;
    --workspace)
      TARGET_DIR="${HOME}/.openclaw/workspace/skills"
      MODE="workspace"
      shift
      ;;
    --target)
      TARGET_DIR="$2"
      MODE="custom"
      shift 2
      ;;
    --uninstall)
      MODE="uninstall"
      shift
      ;;
    -h|--help)
      sed -n '2,15p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

DEST_DIR="${TARGET_DIR%/}/cli-anything"

# ----------------------------------------------------------------------------
# Uninstall path
# ----------------------------------------------------------------------------
if [[ "${MODE}" == "uninstall" ]]; then
  if [[ -d "${DEST_DIR}" ]]; then
    rm -rf "${DEST_DIR}"
    echo "Removed: ${DEST_DIR}"
  else
    echo "Nothing to remove at: ${DEST_DIR}"
  fi
  exit 0
fi

# ----------------------------------------------------------------------------
# Locate CLI-Anything source (local checkout first, then GitHub)
# ----------------------------------------------------------------------------
find_local_plugin() {
  # Look for a sibling CLI-Anything checkout
  local candidates=(
    "${SKILL_DIR}/../CLI-Anything"
    "${SKILL_DIR}/../../CLI-Anything"
    "${SKILL_DIR}/../../../CLI-Anything"
    "/tmp/CLI-Anything"
    "${HOME}/CLI-Anything"
    "${HOME}/projects/CLI-Anything"
  )
  for c in "${candidates[@]}"; do
    if [[ -f "${c}/cli-anything-plugin/HARNESS.md" ]]; then
      REPO_ROOT="${c}"
      PLUGIN_DIR="${c}/cli-anything-plugin"
      PREVIEW_PROTOCOL="${c}/docs/PREVIEW_PROTOCOL.md"
      return 0
    fi
  done
  return 1
}

if ! find_local_plugin; then
  echo "No local CLI-Anything checkout found." >&2
  echo "Attempting to clone the canonical repository from GitHub..." >&2
  CLONE_DIR="/tmp/CLI-Anything"
  if [[ -d "${CLONE_DIR}" && -f "${CLONE_DIR}/cli-anything-plugin/HARNESS.md" ]]; then
    echo "Reusing existing clone at: ${CLONE_DIR}" >&2
  else
    if ! git clone --depth 1 https://github.com/HKUDS/CLI-Anything.git "${CLONE_DIR}" 2>&1; then
      echo "GitHub clone failed. Please clone HKUDS/CLI-Anything manually and rerun." >&2
      exit 1
    fi
  fi
  REPO_ROOT="${CLONE_DIR}"
  PLUGIN_DIR="${CLONE_DIR}/cli-anything-plugin"
  PREVIEW_PROTOCOL="${CLONE_DIR}/docs/PREVIEW_PROTOCOL.md"
fi

if [[ ! -f "${PLUGIN_DIR}/HARNESS.md" ]]; then
  echo "Cannot find canonical CLI-Anything resources at: ${PLUGIN_DIR}" >&2
  exit 1
fi
if [[ ! -f "${PREVIEW_PROTOCOL}" ]]; then
  echo "Cannot find preview protocol at: ${PREVIEW_PROTOCOL}" >&2
  echo "Will proceed without it; preview harnesses may be missing protocol docs." >&2
  PREVIEW_PROTOCOL=""
fi

# ----------------------------------------------------------------------------
# Refuse to overwrite an existing install
# ----------------------------------------------------------------------------
mkdir -p "${TARGET_DIR}"
if [[ -e "${DEST_DIR}" ]]; then
  echo "Refusing to overwrite existing skill: ${DEST_DIR}" >&2
  echo "Remove it manually if you want to reinstall." >&2
  exit 1
fi

# ----------------------------------------------------------------------------
# Stage files into a tmp directory, then atomically move into place
# ----------------------------------------------------------------------------
STAGING_DIR="$(mktemp -d "${TARGET_DIR}/.cli-anything.tmp.XXXXXX")"
cleanup() {
  if [[ -n "${STAGING_DIR}" && -d "${STAGING_DIR}" ]]; then
    rm -rf "${STAGING_DIR}"
  fi
}
trap cleanup EXIT

mkdir -p \
  "${STAGING_DIR}/references/commands" \
  "${STAGING_DIR}/references/docs" \
  "${STAGING_DIR}/references/guides" \
  "${STAGING_DIR}/scripts/templates"

# Copy this skill's own content first
cp -R "${SKILL_DIR}/." "${STAGING_DIR}/"

# Vendor canonical CLI-Anything resources
cp "${PLUGIN_DIR}/HARNESS.md" "${STAGING_DIR}/references/HARNESS.md"
cp "${PLUGIN_DIR}/commands/"*.md "${STAGING_DIR}/references/commands/"
cp "${PLUGIN_DIR}/guides/"*.md "${STAGING_DIR}/references/guides/"
cp "${PLUGIN_DIR}/repl_skin.py" "${STAGING_DIR}/scripts/repl_skin.py"
cp "${PLUGIN_DIR}/preview_bundle.py" "${STAGING_DIR}/scripts/preview_bundle.py"
cp "${PLUGIN_DIR}/skill_generator.py" "${STAGING_DIR}/scripts/skill_generator.py"
if [[ -d "${PLUGIN_DIR}/templates" ]]; then
  cp "${PLUGIN_DIR}/templates/"* "${STAGING_DIR}/scripts/templates/" 2>/dev/null || true
fi
if [[ -n "${PREVIEW_PROTOCOL}" ]]; then
  cp "${PREVIEW_PROTOCOL}" "${STAGING_DIR}/references/docs/PREVIEW_PROTOCOL.md"
fi

# Move into place
mv "${STAGING_DIR}" "${DEST_DIR}"

echo "Installed OpenClaw CLI-Anything skill to: ${DEST_DIR}"
echo "Vendored CLI-Anything methodology resources into the installed skill."
echo "Restart OpenClaw (or run: openclaw gateway restart) to pick up the new skill."
echo
echo "Quick check:"
echo "  bash ${DEST_DIR}/tests/test_install.sh"
echo "  cat ${DEST_DIR}/references/HARNESS.md | head -20"
