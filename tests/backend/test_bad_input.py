"""Hostile and broken files through the API: every one gets a clean answer (a recording, or a
422 saying why), never a 500, and the server is still healthy afterwards (PLAN M8, robustness)."""

import json
import struct
import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html>")
    return TestClient(create_app(dist), raise_server_exceptions=False)


def _wav(
    path: Path, data: bytes, *, channels: int = 2, bits: int = 16, claim: int | None = None
) -> None:
    claimed = len(data) if claim is None else claim
    fmt = struct.pack(
        "<HHIIHH", 1, channels, 48_000, 48_000 * channels * bits // 8, channels * bits // 8, bits
    )
    path.write_bytes(
        b"RIFF" + struct.pack("<I", 36 + claimed) + b"WAVEfmt " + struct.pack("<I", 16) + fmt
        + b"data" + struct.pack("<I", claimed) + data
    )  # fmt: skip


def _make(tmp: Path) -> dict[str, Path]:
    rng = np.random.default_rng(1)
    files: dict[str, Path] = {}

    def put(name: str, data: bytes) -> None:
        files[name] = tmp / name
        files[name].write_bytes(data)

    put("empty.iq", b"")
    put("one_byte.iq", b"\x07")
    put("three_bytes.cf32", b"abc")
    put("random.iq", rng.bytes(100_001))
    put("zeros.iq", bytes(65_536))
    put("nan.cf32", np.full(20_000, np.nan, np.complex64).tobytes())
    put("inf.cf32", np.full(20_000, np.inf, np.complex64).tobytes())
    put(
        "mixed_nan.cf32",
        np.where(rng.random(20_000) < 0.3, np.nan, 1.0).astype(np.float32).tobytes(),
    )
    put("odd_length.cf32", rng.standard_normal(10_001).astype(np.float32).tobytes()[:-3])
    put("tiny_noise.cf32", rng.standard_normal(2_000).astype(np.float32).tobytes())
    put("garbage.wav", b"RIFF\x00\x00\x00\x00WAVEjunk" + rng.bytes(500))
    put("truncated_header.wav", b"RIFF\x24\x00\x00\x00WAVEfmt ")
    files["lying_size.wav"] = tmp / "lying_size.wav"
    _wav(files["lying_size.wav"], rng.bytes(4_000), claim=2_000_000_000)
    files["silent.wav"] = tmp / "silent.wav"
    _wav(files["silent.wav"], bytes(40_000))
    files["mono_wav.wav"] = tmp / "mono_wav.wav"
    _wav(files["mono_wav.wav"], rng.bytes(40_000), channels=1)
    put("bad.sigmf-meta", b"{not json")
    put("empty_obj.sigmf-meta", b"{}")
    put(
        "no_data.sigmf-meta",
        json.dumps(
            {
                "global": {"core:datatype": "cf32_le", "core:sample_rate": 1e6},
                "captures": [],
                "annotations": [],
            }
        ).encode(),
    )
    put(
        "bad_type.sigmf-meta",
        json.dumps(
            {
                "global": {"core:datatype": "zz99", "core:sample_rate": -5},
                "captures": [{}],
                "annotations": [],
            }
        ).encode(),
    )
    put("not_npy.npy", b"\x93NUMPY\x01\x00\xff\xff" + rng.bytes(100))
    put("bad.gz", b"\x1f\x8b\x08\x00" + rng.bytes(200))
    put("bad.zip", b"PK\x03\x04" + rng.bytes(200))
    return files


def _healthy(client: TestClient) -> bool:
    return client.get("/api/v1/health").status_code == 200


def test_no_broken_file_gives_a_server_error(client: TestClient, tmp_path: Path) -> None:
    for name, path in _make(tmp_path).items():
        response = client.post("/api/v1/recordings", json={"path": str(path)})
        assert response.status_code < 500, f"{name}: {response.status_code} {response.text[:200]}"
        if response.status_code == 200 and response.json():
            rid = response.json()["id"]
            # Let the background analysis run and finish (or fail cleanly) on it too.
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                status = client.get(f"/api/v1/recordings/{rid}/results?format=json").status_code
                assert status < 500, f"{name}: results {status}"
                if status == 200:
                    break
                time.sleep(0.2)
            for fmt in ("csv", "txt", "pdf", "sigmf", "run"):
                code = client.get(f"/api/v1/recordings/{rid}/results?format={fmt}").status_code
                assert code < 500, f"{name}: {fmt} -> {code}"
        assert _healthy(client), f"the server died on {name}"


def test_a_missing_path_and_a_directory_of_junk_are_422(client: TestClient, tmp_path: Path) -> None:
    assert (
        client.post("/api/v1/recordings", json={"path": str(tmp_path / "nope.iq")}).status_code
        == 422
    )
    junk = tmp_path / "junk"
    junk.mkdir()
    (junk / "a.bin").write_bytes(b"\x00" * 10)
    assert client.post("/api/v1/inputs", json={"path": str(junk)}).status_code < 500
    assert _healthy(client)


def _degenerate(tmp: Path) -> dict[str, Path]:
    """Well-formed files whose samples are hostile, big enough for the whole chain to run."""
    rng = np.random.default_rng(2)
    n = 300_000
    noise = (rng.standard_normal(n) + 1j * rng.standard_normal(n)).astype(np.complex64)
    nan_burst = noise.copy()
    nan_burst[100_000:100_500] = np.nan
    some_inf = noise.copy()
    some_inf[::5_000] = np.inf
    clipped = np.sign(noise.real) + 1j * np.sign(noise.imag)
    tone = np.exp(2j * np.pi * 0.1 * np.arange(n)).astype(np.complex64)
    cases = {
        "all_zero": np.zeros(n, np.complex64),
        "dc_only": np.full(n, 0.5 + 0.5j, np.complex64),
        "all_nan": np.full(n, np.nan, np.complex64),
        "nan_burst": nan_burst,
        "some_inf": some_inf,
        "clipped": clipped.astype(np.complex64),
        "huge": noise * np.float32(1e30),
        "tiny": noise * np.float32(1e-30),
        "pure_tone": tone,
    }
    files = {}
    for name, x in cases.items():
        files[name] = tmp / f"{name}.cf32"
        files[name].write_bytes(x.tobytes())
    return files


def test_degenerate_samples_never_crash_the_chain_or_the_exports(
    client: TestClient, tmp_path: Path
) -> None:
    for name, path in _degenerate(tmp_path).items():
        response = client.post(
            "/api/v1/recordings", json={"path": str(path), "datatype": "cf32_le"}
        )
        assert response.status_code < 500, f"{name}: {response.status_code} {response.text[:200]}"
        if name in ("all_nan", "nan_burst", "some_inf"):  # readable: the NaNs are reported
            assert response.status_code == 200, f"{name}: {response.text[:200]}"
        if response.status_code != 200:
            continue  # refused with a reason: fine
        rid = response.json()["id"]
        deadline = time.monotonic() + 180
        status = 409
        while time.monotonic() < deadline:
            status = client.get(f"/api/v1/recordings/{rid}/results?format=json").status_code
            assert status < 500, f"{name}: results {status}"
            if status != 409:
                break
            time.sleep(0.3)
        assert status == 200, f"{name}: analysis never finished ({status})"
        for fmt in ("csv", "txt", "pdf", "run", "sigmf"):
            code = client.get(f"/api/v1/recordings/{rid}/results?format={fmt}").status_code
            assert code < 500, f"{name}: {fmt} -> {code}"
        if name in ("all_nan", "nan_burst", "some_inf"):
            doc = client.get(f"/api/v1/recordings/{rid}/results?format=json").json()
            ids = {p["id"] for st in doc["stages"] for p in st["parameters"]}
            assert "non_finite_samples" in ids, f"{name}: {sorted(ids)}"
        assert client.get(f"/api/v1/recordings/{rid}").status_code == 200, name
        assert client.get(f"/api/v1/tiles/{rid}/0/0/0").status_code < 500, name
        assert _healthy(client), f"the server died on {name}"
