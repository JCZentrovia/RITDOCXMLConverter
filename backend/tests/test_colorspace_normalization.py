import os
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

from app.services.pdf_conversion_service import PDFConversionService


@pytest.mark.unit
def test_preprocess_pdf_colorspace_when_gs_missing_returns_original(sample_pdf_file, monkeypatch):
    service = PDFConversionService()

    # Simulate Ghostscript not installed
    monkeypatch.setattr("shutil.which", lambda _: None)

    result_path = service._preprocess_pdf_colorspace_sync(sample_pdf_file)
    assert result_path == sample_pdf_file


@pytest.mark.unit
def test_preprocess_pdf_colorspace_when_gs_fails_returns_original(sample_pdf_file, monkeypatch, tmp_path):
    service = PDFConversionService()

    # Simulate Ghostscript found
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/gs")

    # Simulate gs returning non-zero
    class FakeCompleted:
        returncode = 1
        stdout = b""
        stderr = b"some error"

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeCompleted())

    result_path = service._preprocess_pdf_colorspace_sync(sample_pdf_file)
    assert result_path == sample_pdf_file


@pytest.mark.unit
def test_preprocess_pdf_colorspace_when_gs_succeeds_returns_rgb_path(sample_pdf_file, monkeypatch, tmp_path):
    service = PDFConversionService()

    # Simulate Ghostscript found
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/gs")

    # Pre-create the expected output file to mimic gs success
    output_path = sample_pdf_file.with_name(f"{sample_pdf_file.stem}_rgb.pdf")
    output_path.write_bytes(b"PDF-FAKE-RGB")

    class FakeCompleted:
        returncode = 0
        stdout = b"ok"
        stderr = b""

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeCompleted())

    result_path = service._preprocess_pdf_colorspace_sync(sample_pdf_file)
    assert result_path == output_path
    assert result_path.exists() and result_path.stat().st_size > 0
