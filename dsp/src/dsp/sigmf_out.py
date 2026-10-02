"""SigMF metadata from a results document (PLAN M7): the findings as annotations, and a
`.sigmf-meta` for a recording that has none.

What goes in is only what the results can stand behind:
- `core:datatype` is written whenever it is known, since the samples can't be read without it, with
  the level it was established at in `sanket:assumptions`; an UNKNOWN datatype, or an I/Q order of
  Q first (SigMF has no way to say so: other tools would read the samples swapped), refuses.
- `core:sample_rate` and `core:frequency` are written only when MEASURED or VERIFIED (stated by the
  file or entered by the analyst); a rate that is a HYPOTHESIS (inferred from a structural match)
  stays out of the standard fields and goes into `sanket:assumptions` with its level, so another
  tool never reads a guess as a fact.
- Each signal becomes an annotation: its sample span, its band (edges in Hz around the capture
  centre, absolute when the centre frequency is stated), its label, its headline as the comment
  and, in the `sanket:` namespace, its evidence level and signal id.
- The metadata names the recording's files by SHA-256 and the results by their SHA-256.

The samples are never copied: a recording with no SigMF metadata gets a Non-Conforming Dataset
that names the original file (`core:dataset`) and its header length (`core:header_bytes`).
"""

import json
from typing import Any

from dsp.evidence import EvidenceLevel, Parameter
from dsp.results import Results, Signal, results_sha256

SIGMF_VERSION = "1.2.0"
FIRM = (EvidenceLevel.MEASURED, EvidenceLevel.VERIFIED)


class SigmfRefused(ValueError):
    """The results can't be written as SigMF without saying something they don't support."""


def _stage_value(signal: Signal, stage: str, parameter: str) -> float | None:
    for s in signal.stages:
        if s.id == stage:
            for p in s.parameters:
                if p.id == parameter and isinstance(p.value, int | float):
                    return float(p.value)
    return None


def _firm(parameter: Parameter) -> float | None:
    """The parameter's number when it is firm enough for a standard field."""
    if parameter.level in FIRM and isinstance(parameter.value, int | float):
        return float(parameter.value)
    return None


def annotations(results: Results) -> list[dict[str, Any]]:
    """One annotation per signal that has a sample span; bands in Hz need a sample rate."""
    rate = _firm(results.assumptions.sample_rate)
    centre = _firm(results.assumptions.center_frequency)
    out: list[dict[str, Any]] = []
    for signal in results.signals:
        start = _stage_value(signal, "detect", "start_sample")
        stop = _stage_value(signal, "detect", "stop_sample")
        if start is None or stop is None or stop <= start:
            continue
        note: dict[str, Any] = {
            "core:sample_start": int(start),
            "core:sample_count": int(stop - start),
            "core:label": signal.label,
            "core:comment": signal.headline,
            "core:generator": f"Sanket {results.sanket_version}",
            "sanket:signal": signal.id,
            "sanket:level": signal.level.value,
        }
        offset = _stage_value(signal, "detect", "center_frequency")
        width = _stage_value(signal, "detect", "bandwidth")
        if rate is not None and offset is not None and width is not None:
            middle = offset * rate + (centre or 0.0)
            note["core:freq_lower_edge"] = middle - width * rate / 2
            note["core:freq_upper_edge"] = middle + width * rate / 2
            if centre is None:
                note["sanket:frequency_reference"] = "baseband: Hz from the capture centre"
        out.append(note)
    return out


def _provenance(results: Results) -> dict[str, Any]:
    return {
        "results_sha256": results_sha256(results),
        "schema_version": results.schema_version,
        "files": [
            {"name": f.name, "size_bytes": f.size_bytes, "sha256": f.sha256}
            for f in results.recording.files
        ],
        "assumptions": {
            p.id: {"value": p.value, "level": p.level.value, "method": p.method}
            for p in results.assumptions.parameters()
        },
    }


def meta_for(
    results: Results, *, dataset: str | None = None, original: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The `.sigmf-meta` content. With `original` (a SigMF recording's own metadata) its global
    object and captures are kept untouched and the annotations are added; without it a new
    description is built from the Assumptions, naming `dataset` as the file holding the samples."""
    notes = annotations(results)
    extension = {"name": "sanket", "version": results.sanket_version, "optional": True}
    if original is not None:
        meta: dict[str, Any] = json.loads(json.dumps(original))  # a copy
        global_: dict[str, Any] = meta.setdefault("global", {})
        if dataset is not None:
            global_["core:dataset"] = dataset
        meta["annotations"] = [*meta.get("annotations", []), *notes]
    else:
        a = results.assumptions
        if a.datatype.value is None:
            raise SigmfRefused("the sample format is UNKNOWN, so the samples can't be described")
        if a.iq_order is not None and a.iq_order.value == "QI":
            raise SigmfRefused(
                "Q comes first in this recording and SigMF cannot say so: other tools would "
                "read the samples with I and Q swapped"
            )
        global_ = {
            "core:datatype": a.datatype.value,
            "core:version": SIGMF_VERSION,
            "core:description": "Described by Sanket; the samples are the original file's",
        }
        rate = _firm(a.sample_rate)
        if rate is not None:
            global_["core:sample_rate"] = rate
        if dataset is not None:
            global_["core:dataset"] = dataset
        capture: dict[str, Any] = {"core:sample_start": 0}
        frequency = _firm(a.center_frequency)
        if frequency is not None:
            capture["core:frequency"] = frequency
        offset = a.data_offset.value
        if isinstance(offset, int) and offset > 0:
            capture["core:header_bytes"] = offset
        meta = {"global": global_, "captures": [capture], "annotations": notes}
    global_["core:generator"] = f"Sanket {results.sanket_version}"
    extensions: list[Any] = list(global_.get("core:extensions", []))
    named = [e["name"] for e in extensions if isinstance(e, dict) and "name" in e]  # type: ignore[reportUnknownVariableType]
    if "sanket" not in named:
        extensions.append(extension)
    global_["core:extensions"] = extensions
    global_["sanket:provenance"] = _provenance(results)
    return meta


def render_meta(meta: dict[str, Any]) -> str:
    """Deterministic JSON for a `.sigmf-meta` file."""
    return json.dumps(meta, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
