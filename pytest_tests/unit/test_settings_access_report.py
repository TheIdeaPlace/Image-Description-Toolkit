"""settings_access_report names a refused call instead of raising (11/20/2026)."""
import os

import pytest

from idt_core import config_loader


@pytest.mark.unit
def test_report_lists_each_settings_file(tmp_path, monkeypatch):
    monkeypatch.setenv("IDT_USER_CONFIG_DIR", str(tmp_path))
    (tmp_path / "image_describer_config.json").write_text("{}", encoding="utf-8")
    text = "\n".join(config_loader.settings_access_report())
    for name in config_loader.SETTINGS_FILES:
        assert name in text
    assert "read ok (2 bytes)" in text


@pytest.mark.unit
def test_report_survives_permission_error(tmp_path, monkeypatch):
    monkeypatch.setenv("IDT_USER_CONFIG_DIR", str(tmp_path))
    real_stat = os.stat

    def refusing_stat(p, *a, **k):
        if str(p).startswith(str(tmp_path)):
            raise PermissionError(1, "Operation not permitted", str(p))
        return real_stat(p, *a, **k)

    monkeypatch.setattr(config_loader.os, "stat", refusing_stat)
    text = "\n".join(config_loader.settings_access_report())
    assert "FAILED PermissionError" in text
