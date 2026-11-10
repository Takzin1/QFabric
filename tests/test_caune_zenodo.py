"""Synthetic and adversarial tests for the Zenodo v2 provenance intake."""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path

import pytest

from qfabric.caune_zenodo import (
    ALLOWED, _pinned_download_url, download_checked, load_manifest,
    validate_manifest,
)

MANIFEST = (
    Path(__file__).resolve().parents[1] / "data" / "caune_zenodo_v2_source_manifest.json"
)


class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes, url: str):
        super().__init__(data)
        self._url = url

    def geturl(self) -> str:
        return self._url


def test_pinned_manifest_is_complete_and_source_limited() -> None:
    data = load_manifest(MANIFEST)
    entries = validate_manifest(data)
    assert data["zenodoRecordId"] == "15364358"
    assert len(entries) == 15
    assert {item["name"] for item in entries} == ALLOWED
    assert data["datasetLicenseReview"] == "not_verified_do_not_redistribute"
    assert data["rawFilesRedistributed"] is False


@pytest.mark.parametrize("change", ["duplicate", "path", "md5", "record", "license"])
def test_untrusted_manifest_is_rejected(change: str) -> None:
    data = copy.deepcopy(load_manifest(MANIFEST))
    if change == "duplicate":
        data["files"][0] = data["files"][1]
    elif change == "path":
        data["files"][0]["name"] = "../evil.txt"
    elif change == "md5":
        data["files"][0]["publishedMd5"] = "not-an-md5"
    elif change == "record":
        data["zenodoRecordId"] = "999"
    elif change == "license":
        data["datasetLicenseReview"] = "verified"
    with pytest.raises(ValueError):
        validate_manifest(data)


def test_pinned_source_url_is_not_user_supplied() -> None:
    assert _pinned_download_url("lep_fpga.txt") == (
        "https://zenodo.org/records/15364358/files/lep_fpga.txt?download=1"
    )
    with pytest.raises(ValueError):
        _pinned_download_url("../other.txt")


def test_bounded_download_checks_md5_and_computes_sha256(tmp_path: Path) -> None:
    data = b"test synthetic Zenodo bytes only\n"
    name = "lep_fpga.txt"
    entry = {"name": name, "publishedMd5": hashlib.md5(data).hexdigest()}
    result = download_checked(
        entry, tmp_path,
        opener=lambda req, timeout: FakeResponse(data, req.full_url),
    )
    assert result["publisherMd5Matched"] is True
    assert result["sha256OfDownloadedBytes"] == hashlib.sha256(data).hexdigest()
    assert (tmp_path / name).read_bytes() == data


def test_bad_publisher_checksum_rejects_and_deletes_bytes(tmp_path: Path) -> None:
    entry = {"name": "lep_fpga.txt", "publishedMd5": "0" * 32}
    with pytest.raises(ValueError, match="published MD5"):
        download_checked(
            entry, tmp_path,
            opener=lambda req, timeout: FakeResponse(b"wrong bytes", req.full_url),
        )
    assert not (tmp_path / entry["name"]).exists()


def test_redirect_to_untrusted_origin_rejected(tmp_path: Path) -> None:
    entry = {"name": "lep_fpga.txt", "publishedMd5": "0" * 32}
    with pytest.raises(ValueError, match="outside trusted origin"):
        download_checked(
            entry, tmp_path,
            opener=lambda req, timeout: FakeResponse(b"unsafe", "https://example.org/"),
        )
    assert not (tmp_path / entry["name"]).exists()


def test_manifest_is_parseable_standard_json() -> None:
    assert json.loads(MANIFEST.read_text())["sourceVersion"] == "v2"
