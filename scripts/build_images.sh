#!/usr/bin/env bash
set -euo pipefail

repo="${DOCKER_REPO:-bot-calidad-recovery}"
commit="${SOURCE_COMMIT:-$(git rev-parse HEAD)}"
version="${IMAGE_VERSION:-$(git rev-parse --short=12 HEAD)}"

docker build \
  --build-arg "SOURCE_COMMIT=${commit}" \
  -f Dockerfile \
  -t "${repo}:web-${version}" \
  .

docker build \
  --build-arg "SOURCE_COMMIT=${commit}" \
  -f Dockerfile.bot \
  -t "${repo}:bot-${version}" \
  .

printf 'Built %s:web-%s and %s:bot-%s from %s\n' \
  "$repo" "$version" "$repo" "$version" "$commit"
