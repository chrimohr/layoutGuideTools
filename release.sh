#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PLUGIN="layout_guide_tools"

VERSION=$(sed -n 's/^version=//p' "$PLUGIN/metadata.txt" | tr -d '\r' | head -n 1)
TAG="v${VERSION}"

if [ -z "$VERSION" ]; then
  echo "Could not read version from $PLUGIN/metadata.txt" >&2
  exit 1
fi

CHANGELOG="$(sed -n 's/^changelog=//p' "$PLUGIN/metadata.txt" | tr -d '\r' | head -n 1)"
if [ -z "$CHANGELOG" ]; then
  echo "Warning: metadata.txt has no changelog. Plugin approval for updates expects one." >&2
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

OUT="dist/${PLUGIN}-${VERSION}.zip"
mkdir -p dist
rm -f "$OUT"

zip -r "$OUT" "$PLUGIN" \
  -x "*/__pycache__/*" "*.pyc" "*.pyo" "*/.pytest_cache/*"

echo "Built $OUT"
