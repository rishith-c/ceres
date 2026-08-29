"""Leaf vision: every failure path abstains; good replies parse through."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from leaf import classify_leaf  # noqa: E402

# 1x1 white PNG
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626000000000ffff03000006000557bfabd40000000049454e44ae426082")


class FakeClient:
    """Stands in for anthropic.Anthropic()."""

    def __init__(self, reply_text=None, stop_reason="end_turn", raises=None):
        content = [SimpleNamespace(type="text", text=reply_text)] if reply_text else []
        self._response = SimpleNamespace(stop_reason=stop_reason, content=content)
        self._raises = raises
        self.requests = []

    def with_options(self, **kw):
        return self

    @property
    def messages(self):
        return self

    def create(self, **kw):
        self.requests.append(kw)
        if self._raises:
            raise self._raises
        return self._response


def png_file(tmp_path):
    p = tmp_path / "leaf.png"
    p.write_bytes(PNG)
    return p


def test_good_reply_parses(tmp_path):
    client = FakeClient('{"verdict": "anomalous", "confidence": 0.85, "note": "brown spots"}')
    r = classify_leaf(png_file(tmp_path), client=client)
    assert (r.verdict, r.confidence, r.note) == ("anomalous", 0.85, "brown spots")
    assert client.requests[0]["messages"][0]["content"][0]["type"] == "image"


def test_missing_file_abstains(tmp_path):
    r = classify_leaf(tmp_path / "nope.png")
    assert r.verdict == "abstain"


def test_unsupported_extension_abstains(tmp_path):
    p = tmp_path / "leaf.bmp"
    p.write_bytes(b"x")
    assert classify_leaf(p).verdict == "abstain"


def test_api_exception_abstains(tmp_path):
    r = classify_leaf(png_file(tmp_path), client=FakeClient(raises=RuntimeError("boom")))
    assert r.verdict == "abstain"
    assert "boom" in r.note


def test_refusal_stop_reason_abstains(tmp_path):
    client = FakeClient('{"verdict": "healthy", "confidence": 0.9, "note": ""}',
                        stop_reason="refusal")
    assert classify_leaf(png_file(tmp_path), client=client).verdict == "abstain"


def test_garbage_reply_abstains(tmp_path):
    client = FakeClient("the leaf seems fine to me!")
    assert classify_leaf(png_file(tmp_path), client=client).verdict == "abstain"


def test_out_of_range_confidence_abstains(tmp_path):
    client = FakeClient('{"verdict": "healthy", "confidence": 1.4, "note": ""}')
    assert classify_leaf(png_file(tmp_path), client=client).verdict == "abstain"


def test_model_abstain_passes_through(tmp_path):
    client = FakeClient('{"verdict": "abstain", "confidence": 0.2, "note": "leaf out of frame"}')
    r = classify_leaf(png_file(tmp_path), client=client)
    assert r.verdict == "abstain"
    assert r.note == "leaf out of frame"
