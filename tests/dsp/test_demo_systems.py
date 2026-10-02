"""The bundled known-system sample (tools/demo_systems.py): POCSAG, NAVTEX and AIS in one
recording, each VERIFIED through the Match stage by its own check, the transmitted text read
back exactly, and nothing else claimed."""

import demo_systems as demo
import pytest

from dsp.analyse import analyse
from dsp.detect import detect
from dsp.evidence import EvidenceLevel, Parameter
from dsp.ingest.dispatch import open_path
from dsp.report import DetectionReport


@pytest.fixture(scope="module")
def reports(tmp_path_factory: pytest.TempPathFactory) -> dict[str, DetectionReport]:
    stem = tmp_path_factory.mktemp("systems") / "scene_systems"
    g, scene, truth = demo.build_systems()
    demo.write(stem, g, scene, truth)
    assert demo.verify_systems(stem, g, scene, truth)
    (opened,) = open_path(stem.with_suffix(".sigmf-meta"))
    with opened.recording.reader() as reader:
        detections = detect(reader, real=False).detections
    assert len(detections) == len(truth)
    out: dict[str, DetectionReport] = {}
    for d in detections:
        with opened.recording.reader() as reader:
            report = analyse(reader, d, sample_rate=demo.SAMPLE_RATE)
        centre_hz = (d.low + d.high) / 2 * demo.SAMPLE_RATE
        label = min(truth, key=lambda t: abs(t["offsetHz"] - centre_hz))["label"]
        assert label not in out
        out[label] = report
    return out


def _match(report: DetectionReport) -> dict[str, Parameter]:
    stage = next(s for s in report.stages if s.id == "match")
    return {p.id: p for p in stage.parameters}


def test_each_system_is_verified_by_its_own_check(reports: dict[str, DetectionReport]) -> None:
    proofs = {"POCSAG": "reencode", "NAVTEX": "reencode", "AIS": "crc"}
    assert set(reports) == set(proofs)
    for label, report in reports.items():
        system = _match(report)["system"]
        assert system.level is EvidenceLevel.VERIFIED
        assert system.value == demo._SYSTEM_NAME[label]
        assert system.proof is not None and system.proof.kind == proofs[label]
        assert report.level is EvidenceLevel.VERIFIED
        assert demo._SYSTEM_NAME[label] in report.headline


def test_the_pages_are_read_back_exactly(reports: dict[str, DetectionReport]) -> None:
    pages = _match(reports["POCSAG"])["pages"]
    expected = tuple(f'RIC {ric:07d} function {fn}: "{text}"' for ric, fn, text in demo.PAGES)
    assert pages.evidence == expected


def test_the_navtex_message_is_read_back_exactly(reports: dict[str, DetectionReport]) -> None:
    messages = _match(reports["NAVTEX"])["messages"]
    assert messages.evidence == (
        f"{demo.NAVTEX.station}{demo.NAVTEX.subject}{demo.NAVTEX.serial:02d}: {demo.NAVTEX.text}",
    )


def test_every_ais_mmsi_is_read_back(reports: dict[str, DetectionReport]) -> None:
    shown = " ".join(_match(reports["AIS"])["ais_messages"].evidence)
    for mmsi in demo.AIS.mmsis:
        assert f"type 1, MMSI {mmsi:09d}" in shown


def test_the_truth_file_matches_the_scene() -> None:
    _, _, truth = demo.build_systems()
    assert [t["label"] for t in truth] == ["POCSAG", "NAVTEX", "AIS"]
    assert all(t["expectedLevel"] == "VERIFIED" for t in truth)
