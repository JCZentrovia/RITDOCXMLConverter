from pathlib import Path

from pipeline.validators.dtd_validator import resolve_dtd_path


def test_resolve_dtd_path_returns_project_absolute_path():
    relative = "RITTDOCdtd/v1.1/RittDocBook.dtd"

    resolved = resolve_dtd_path(relative)

    assert resolved.is_absolute()
    assert resolved.exists()
    assert resolved.name == "RittDocBook.dtd"
    # The resolved file should live under the repository's RITTDOC resources.
    assert Path("RITTDOCdtd").resolve() in resolved.parents


def test_resolve_dtd_path_keeps_absolute_values(tmp_path):
    explicit = tmp_path / "Custom.dtd"
    explicit.write_text("<!ELEMENT book ANY>")

    resolved = resolve_dtd_path(str(explicit))

    assert resolved == explicit
