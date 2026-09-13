#!/usr/bin/env bash
# install-third-party-bundle.sh
# Generic installer for third-party skill bundles that ship with their own authoritative
# install_guide in the index.json + per-skill manifest.json pattern (UUMit-class).
#
# Usage:
#   ./install-third-party-bundle.sh \
#     --entry "https://oss.example.com/skills/v2/index.json" \
#     --dest "$HOME/.openclaw/skills" \
#     --base "uumit-agent"
#
# Effects:
#   - Fetches index.json fresh (no cache), validates bundle.zip size+sha256
#   - Extracts to /tmp/<slug>-staging-XXXXXX, verifies every bundle.skill is at staging root
#   - Runs install.js --check + validate_skill.js in staging
#   - Backs up existing <dest>/<base>/memory to /tmp/<base>-memory-backup-YYYYMMDD-HHMMSS.tar
#   - rsync --exclude=memory when copying the base, full rsync for extensions
#   - Re-runs --check + validate_skill.js in the final <dest>
#
# The script STOPS at the first failed check and prints exactly which step to fix.
# It does NOT perform device authorization (that's Step 6, which requires user interaction
# via verification_url + user_code — run install.js by hand after this script succeeds).

set -euo pipefail

ENTRY=""
DEST=""
BASE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --entry) ENTRY="$2"; shift 2 ;;
    --dest)  DEST="$2";  shift 2 ;;
    --base)  BASE="$2";  shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$ENTRY" && -n "$DEST" && -n "$BASE" ]] || { echo "REQUIRED: --entry --dest --base" >&2; exit 2; }

SLUG=$(basename "$(echo "$ENTRY" | sed 's#.*skills/##; s#/index.json##')")
INSTALL_DIR="/tmp/${SLUG}-install"
STAGING=$(mktemp -d "/tmp/${SLUG}-staging-XXXXXX")

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "=== Step 1: Fetch $ENTRY (no cache) ==="
rm -f index.json bundle.zip
curl -fsSL "$ENTRY" -o index.json
echo "  → $INSTALL_DIR/index.json ($(stat -f%z index.json) bytes)"

# Parse index.json with node (always present on Hermes boxes).
node -e '
  const fs=require("fs");
  const j=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));
  const b=j.bundle;
  if(!b){console.error("no bundle in index.json");process.exit(1)}
  console.log("BUNDLE_NAME="+JSON.stringify(b.name));
  console.log("BUNDLE_URL="+JSON.stringify(b.url));
  console.log("BUNDLE_BYTES="+b.bytes);
  console.log("BUNDLE_SHA256="+b.sha256);
  console.log("BUNDLE_SKILLS="+b.skills.join(" "));
  console.log("BASE="+JSON.stringify(j.base_skill));
' index.json > bundle.env
source bundle.env
[[ "$BASE" != "$BASE_VAR_UNSET" ]] || BASE="$BASE_JSON_DECODED"  # noop; placeholder
# Re-source BASE from the json
BASE=$(node -e 'console.log(JSON.parse(require("fs").readFileSync("index.json","utf8")).base_skill)')

echo "  base_skill = $BASE"
echo "  bundle = $BUNDLE_NAME ($BUNDLE_BYTES bytes)"

echo "=== Step 2: Download + verify bundle ==="
curl -fsSL "$BUNDLE_URL" -o bundle.zip
ACTUAL_SIZE=$(stat -f%z bundle.zip)
ACTUAL_SHA=$(shasum -a 256 bundle.zip | awk '{print $1}')
if [[ "$ACTUAL_SIZE" != "$BUNDLE_BYTES" ]]; then
  echo "❌ SIZE MISMATCH expected=$BUNDLE_BYTES actual=$ACTUAL_SIZE"
  exit 1
fi
if [[ "$ACTUAL_SHA" != "$BUNDLE_SHA256" ]]; then
  echo "❌ SHA256 MISMATCH expected=$BUNDLE_SHA256 actual=$ACTUAL_SHA"
  exit 1
fi
echo "  ✅ size + sha256 verified"

echo "=== Step 3: Extract to staging + scan completeness ==="
unzip -q bundle.zip -d "$STAGING"
for skill in $BUNDLE_SKILLS; do
  if [[ ! -d "$STAGING/$skill" || ! -f "$STAGING/$skill/manifest.json" ]]; then
    echo "❌ $skill missing or incomplete in staging"
    exit 1
  fi
  echo "  ✅ $skill"
done

echo "=== Step 4: Staging health checks ==="
cd "$STAGING/$BASE"
UUMIT_SKILL_DIR="$STAGING/$BASE" node scripts/install.js --check > staging-check.json
OK=$(node -e 'console.log(require("./staging-check.json").ok)')
[[ "$OK" == "true" ]] || { echo "❌ staging install.js --check failed"; cat staging-check.json; exit 1; }
echo "  ✅ install.js --check"

cd "$STAGING/$BASE"
UUMIT_SKILL_DIR="$STAGING/$BASE" node scripts/validate_skill.js > staging-validate.json
OK=$(node -e 'console.log(require("./staging-validate.json").ok)')
[[ "$OK" == "true" ]] || { echo "❌ staging validate_skill.js failed"; cat staging-validate.json; exit 1; }
echo "  ✅ validate_skill.js"

echo "=== Step 5: Backup + copy to $DEST ==="
if [[ -d "$DEST/$BASE/memory" ]]; then
  BACKUP="/tmp/${BASE}-memory-backup-$(date +%Y%m%d-%H%M%S).tar"
  tar -cf "$BACKUP" -C "$DEST/$BASE" memory
  echo "  → backup: $BACKUP"
fi

for skill in $BUNDLE_SKILLS; do
  mkdir -p "$DEST/$skill"
  if [[ "$skill" == "$BASE" ]]; then
    rsync -a --exclude='memory' "$STAGING/$skill/" "$DEST/$skill/"
  else
    rsync -a "$STAGING/$skill/" "$DEST/$skill/"
  fi
  echo "  → $skill"
done

echo "=== Step 6: Final verification (in $DEST) ==="
cd "$DEST/$BASE"
UUMIT_SKILL_DIR="$DEST/$BASE" node scripts/install.js --check > final-check.json
OK=$(node -e 'console.log(require("./final-check.json").ok)')
[[ "$OK" == "true" ]] || { echo "❌ final install.js --check failed"; cat final-check.json; exit 1; }

cd "$DEST/$BASE"
UUMIT_SKILL_DIR="$DEST/$BASE" node scripts/validate_skill.js > final-validate.json
OK=$(node -e 'console.log(require("./final-validate.json").ok)')
[[ "$OK" == "true" ]] || { echo "❌ final validate_skill.js failed"; cat final-validate.json; exit 1; }

echo ""
echo "==================================================="
echo "✅ Bundles copied + verified."
echo ""
echo "Memory: $DEST/$BASE/memory/ has been PRESERVED (not overwritten)."
echo "Backup: ${BACKUP:-<none — no prior memory/>}"
echo "Staging (delete anytime): $STAGING"
echo "Installer logs: $INSTALL_DIR"
echo ""
echo "Next: cd $DEST/$BASE && UUMIT_SKILL_DIR=$DEST/$BASE node scripts/install.js"
echo "  → returns verification_url + user_code. Run that, give the user the"
echo "    short code, then in background poll with:"
echo "    UUMIT_SKILL_DIR=$DEST/$BASE node scripts/auth.js --wait <device_code>"
echo "==================================================="
