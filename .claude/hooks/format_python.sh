#!/usr/bin/env bash
# PostToolUse hook (prototype sprint, PROTOTYPE_PLAN.md P0): format and lint-fix a Python file
# right after Claude edits it, so style nits never cost a round trip. Reads the tool call as JSON
# on stdin (Claude Code's hook contract), acts only on tool_input.file_path when it's a .py file,
# and never fails the edit: any error here is swallowed and the hook exits 0 regardless.
input="$(cat)"
file_path="$(printf '%s' "$input" | node -e "
let d = '';
process.stdin.on('data', c => { d += c; });
process.stdin.on('end', () => {
  try {
    const j = JSON.parse(d);
    process.stdout.write((j.tool_input && j.tool_input.file_path) || '');
  } catch (e) {
    // Malformed input: print nothing, so the case below matches no extension and no-ops.
  }
});
" 2>/dev/null)"

case "$file_path" in
  *.py)
    uv run ruff format "$file_path" >/dev/null 2>&1
    uv run ruff check --fix "$file_path" >/dev/null 2>&1
    ;;
esac

exit 0
