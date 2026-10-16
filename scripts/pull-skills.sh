#!/usr/bin/env bash
set -euo pipefail

# Pulls or updates Matt Pocock's skills and Perplexity AI skills from GitHub,
# and links them into both ~/.agents/skills (global) and .agents/skills (workspace).

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR_DIR="$HOME/.agents/vendor"
GLOBAL_SKILLS="$HOME/.agents/skills"
WORKSPACE_SKILLS="$PROJECT_ROOT/.agents/skills"

mkdir -p "$VENDOR_DIR" "$GLOBAL_SKILLS" "$WORKSPACE_SKILLS"

# 1. Pull / update Matt Pocock skills
if [ -d "$VENDOR_DIR/mattpocock-skills/.git" ]; then
    echo "Updating mattpocock/skills..."
    git -C "$VENDOR_DIR/mattpocock-skills" pull --ff-only
else
    echo "Cloning mattpocock/skills..."
    git clone --depth 1 https://github.com/mattpocock/skills.git "$VENDOR_DIR/mattpocock-skills"
fi

# 2. Pull / update Perplexity AI skills
if [ -d "$VENDOR_DIR/perplexity-skills/.git" ]; then
    echo "Updating perplexityai/api-platform-developers..."
    git -C "$VENDOR_DIR/perplexity-skills" pull --ff-only
else
    echo "Cloning perplexityai/api-platform-developers..."
    git clone --depth 1 https://github.com/perplexityai/api-platform-developers.git "$VENDOR_DIR/perplexity-skills"
fi

# 3. Link skills into targets
python3 -c "
import os, shutil
from pathlib import Path

vendor_matt = Path('$VENDOR_DIR') / 'mattpocock-skills' / 'skills'
vendor_pplx = Path('$VENDOR_DIR') / 'perplexity-skills' / 'skills'
targets = [Path('$GLOBAL_SKILLS'), Path('$WORKSPACE_SKILLS')]

def link_skills(vendor_path, skip_buckets=()):
    for skill_md in vendor_path.glob('**/SKILL.md'):
        if any(skip in skill_md.parts for skip in skip_buckets):
            continue
        skill_dir = skill_md.parent
        name = skill_dir.name
        for t in targets:
            dest = t / name
            if dest.exists() or dest.is_symlink():
                if dest.is_symlink() or dest.is_file():
                    dest.unlink()
                else:
                    shutil.rmtree(dest)
            dest.symlink_to(skill_dir)

link_skills(vendor_matt, skip_buckets=('deprecated', 'misc'))
link_skills(vendor_pplx)
print('✓ All skills linked into global and workspace directories.')
"
