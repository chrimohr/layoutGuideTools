#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PLUGIN="layout_guide_tools"
CHANGELOG_FILE="CHANGELOG.md"

VERSION=$(sed -n 's/^version=//p' "$PLUGIN/metadata.txt" | tr -d '\r' | head -n 1)
TAG="v${VERSION}"

if [ -z "$VERSION" ]; then
  echo "Could not read version from $PLUGIN/metadata.txt" >&2
  exit 1
fi

CHANGELOG_ENTRY=""
if [ -f "$CHANGELOG_FILE" ]; then
  CHANGELOG_ENTRY=$(awk '
    /^##[[:space:]]/ {
      ver = $0
      sub(/^##[[:space:]]*/, "", ver)
      gsub(/[\[\]]/, "", ver)
      skip = (tolower(ver) == "unreleased" || ver == "")
      if (!skip) {
        if (out != "") out = out " | "
        out = out "[" ver "]"
        need_space = 1
      }
      next
    }
    !skip && ver != "" && NF { $1 = $1; sub(/^[[:space:]]*[-*][[:space:]]+/, ""); out = out (need_space ? " " : "; ") $0; need_space = 0 }
    END { print out }
  ' "$CHANGELOG_FILE")
fi
if [ -z "$CHANGELOG_ENTRY" ]; then
  echo "Warning: no changelog entries found in $CHANGELOG_FILE. Plugin approval for updates expects one." >&2
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "Uncommitted changes found. Commit or stash them first." >&2
  exit 1
fi

if git describe --exact-match HEAD >/dev/null 2>&1; then
  echo "Latest commit is already tagged. Nothing to release." >&2
  exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists." >&2
  exit 1
fi

git tag -a "$TAG" -m "Release $TAG"
echo "Created tag $TAG"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -r "$PLUGIN" "$STAGE/"
if [ -n "$CHANGELOG_ENTRY" ]; then
  awk -v cl="$CHANGELOG_ENTRY" '
    BEGIN { done = 0 }
    /^changelog=/ || /^#[[:space:]]*changelog=/ { if (!done) { print "changelog=" cl; done = 1; next } }
    { print }
    END { if (!done) print "changelog=" cl }
  ' "$STAGE/$PLUGIN/metadata.txt" > "$STAGE/$PLUGIN/metadata.txt.tmp" && mv "$STAGE/$PLUGIN/metadata.txt.tmp" "$STAGE/$PLUGIN/metadata.txt"
fi

OUT="dist/${PLUGIN}-${VERSION}.zip"
ABS_OUT="$(pwd)/$OUT"
mkdir -p dist
rm -f "$OUT"

(
  cd "$STAGE"
  zip -r "$ABS_OUT" "$PLUGIN" \
    -x "*/__pycache__/*" "*.pyc" "*.pyo" "*/.pytest_cache/*"
)

echo "Built $OUT"
