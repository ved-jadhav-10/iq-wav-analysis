"""Export a small TorchSig subset as SigMF: an independent generator for bench v0 (PLAN §5 M1).

Dev-time only. TorchSig (MIT) needs PyTorch, so this runs under WSL2 in its own environment,
never in the product or the uv workspace, and nothing here is imported by Sanket:

    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv venv ~/torchsig-env --python 3.12
    uv pip install --python ~/torchsig-env torch torchaudio \\
        --index-url https://download.pytorch.org/whl/cpu
    uv pip install --python ~/torchsig-env torchsig==2.2.0
    ~/torchsig-env/bin/python bench/torchsig/export.py      # from the repo root, in WSL

It writes bench/data/torchsig/ (not committed): one SigMF recording per example, with TorchSig's
own labels in the annotations, and a manifest. Then, on either platform:

    uv run bench run torchsig

The samples come from TorchSig; only the encoding into each datatype happens here, in plain
NumPy, so no Sanket code touches the signals. TorchSig works at complex baseband, so the
metadata states no centre frequency, and annotation frequency edges are relative to the centre.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torchsig
from torchsig.datasets.datasets import TorchSigIterableDataset
from torchsig.transforms.impairments import Impairments
from torchsig.utils.defaults import TorchSigDefaults

OUT = Path(__file__).resolve().parents[1] / "data" / "torchsig"
SEED = 26147
SAMPLES = 1 << 16
SAMPLE_RATE = 10_000_000
IMPAIRMENT_LEVEL = 2  # TorchSig's "wireless" level: channel and receiver impairments
CLASSES = (
    "bpsk", "qpsk", "8psk", "16qam", "64qam", "16apsk",
    "2fsk", "4fsk", "2gmsk", "ook", "4ask", "fm", "am-dsb", "ofdm-64",
)  # fmt: skip
PER_CLASS = 6
DATATYPES = ("cf32_le", "ci16_le", "ci8", "cu8")
RMS_DBFS = -12.0


def dataset(class_name: str, seed: int) -> TorchSigIterableDataset:
    md = TorchSigDefaults().default_dataset_metadata
    md.update(
        num_iq_samples_dataset=SAMPLES,
        sample_rate=SAMPLE_RATE,
        signal_duration_in_samples_min=SAMPLES,
        signal_duration_in_samples_max=SAMPLES,
        snr_db_min=5.0,
        snr_db_max=30.0,
        bandwidth_min=SAMPLE_RATE / 40,
        bandwidth_max=SAMPLE_RATE / 5,
        signal_center_freq_min=-SAMPLE_RATE / 4,
        signal_center_freq_max=SAMPLE_RATE / 4,
    )
    impairments = Impairments(IMPAIRMENT_LEVEL)
    ds = TorchSigIterableDataset(
        signal_generators=[class_name],
        metadata=md,
        transforms=[impairments.dataset_transforms],
        component_transforms=[impairments.signal_transforms],
    )
    ds.seed(seed)
    return ds


def encode(x: np.ndarray, datatype: str) -> bytes:
    """Interleaved I/Q in `datatype`, scaled to RMS_DBFS of full scale and clipped."""
    x = x / np.sqrt(np.mean(np.abs(x) ** 2)) * 10 ** (RMS_DBFS / 20)
    iq = np.stack([x.real, x.imag], axis=1).ravel()
    if datatype == "cf32_le":
        return iq.astype("<f4").tobytes()
    if datatype == "ci16_le":
        return np.clip(np.round(iq * 32767), -32768, 32767).astype("<i2").tobytes()
    if datatype == "ci8":
        return np.clip(np.round(iq * 127), -128, 127).astype("i1").tobytes()
    if datatype == "cu8":
        return np.clip(np.round(iq * 127.5 + 127.5), 0, 255).astype("u1").tobytes()
    raise ValueError(datatype)


def annotation(c: object) -> dict[str, object]:
    def get(key: str) -> object:
        value = getattr(c, key)
        return value.item() if isinstance(value, np.generic) else value

    centre, bandwidth = float(get("center_freq")), float(get("bandwidth"))
    out: dict[str, object] = {
        "core:sample_start": int(get("start_in_samples")),
        "core:sample_count": int(get("duration_in_samples")),
        "core:freq_lower_edge": centre - bandwidth / 2,
        "core:freq_upper_edge": centre + bandwidth / 2,
        "core:label": str(get("class_name")),
        "torchsig:center_freq": centre,
        "torchsig:bandwidth": bandwidth,
        "torchsig:snr_db": float(get("snr_db")),
    }
    for key in ("alpha_rolloff", "pulse_shape_name"):
        try:
            value = get(key)
        except (AttributeError, KeyError):
            continue
        if value is not None:
            out[f"torchsig:{key}"] = value
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--per-class", type=int, default=PER_CLASS)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, object]] = []
    for ci, class_name in enumerate(CLASSES):
        ds = dataset(class_name, SEED + ci)
        for k in range(args.per_class):
            sample = next(ds)
            x = np.asarray(sample.data, dtype=np.complex128)
            datatype = DATATYPES[(ci + k) % len(DATATYPES)]
            stem = f"ts-{class_name}-{k}"
            (args.out / f"{stem}.sigmf-data").write_bytes(encode(x, datatype))
            meta = {
                "global": {
                    "core:datatype": datatype,
                    "core:sample_rate": SAMPLE_RATE,
                    "core:version": "1.2.0",
                    "core:description": f"TorchSig {torchsig.__version__} {class_name}, "
                    f"impairment level {IMPAIRMENT_LEVEL}",
                    "core:recorder": "torchsig",
                },
                "captures": [{"core:sample_start": 0}],
                "annotations": [annotation(c) for c in sample.component_signals],
            }
            (args.out / f"{stem}.sigmf-meta").write_text(json.dumps(meta, indent=1) + "\n")
            files.append({"file": stem, "class": class_name, "datatype": datatype})
        print(f"{class_name}: {args.per_class} files")
    manifest = {
        "set": "torchsig",
        "generator": f"torchsig {torchsig.__version__}",
        "torch": torch.__version__,
        "numpy": np.__version__,
        "seed": SEED,
        "impairmentLevel": IMPAIRMENT_LEVEL,
        "sampleRate": SAMPLE_RATE,
        "samples": SAMPLES,
        "files": files,
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {len(files)} files to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
