#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d ARIS/.git ]]; then
  git clone --depth=1 https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep.git ARIS
else
  git -C ARIS pull --ff-only
fi

if [[ ! -d EvoScientist/.git ]]; then
  git clone --depth=1 https://github.com/EvoScientist/EvoScientist.git EvoScientist
else
  git -C EvoScientist pull --ff-only
fi

echo "References synced: ARIS and EvoScientist"
