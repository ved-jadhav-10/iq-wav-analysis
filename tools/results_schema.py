"""Write the results JSON schema generated from dsp.results (PLAN §3).

Run `uv run python tools/results_schema.py` after changing the evidence or results models;
a test fails while the committed schema is stale.
"""

from dsp.results import SCHEMA_PATH, schema_json

if __name__ == "__main__":
    SCHEMA_PATH.write_text(schema_json(), encoding="utf-8", newline="\n")
    print(f"wrote {SCHEMA_PATH}")
