"""Reading a bundle's items reports progress, so ImageDescriber can open a large
workspace off the UI thread with a count instead of freezing.

Kelly, 11/19/2026: opening iPhone490.idtw (12,906 items) took 95 seconds on a
cold start, all on the UI thread, and Windows showed "Not Responding".
"""
import json

import pytest

pytestmark = pytest.mark.unit


def _bundle(tmp_path, n=5, broken=1):
    from idt_core.workspace import Workspace

    ws = Workspace.create(tmp_path / "w.idtw", name="w", copy_originals=False)
    d = ws.descriptions_dir
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (d / f"IMG_{i}.jpg.json").write_text(json.dumps({
            "image": f"IMG_{i}.jpg", "source_path": str(tmp_path / f"IMG_{i}.jpg"),
            "storage": "reference", "item_type": "image", "descriptions": []}),
            encoding="utf-8")
    for i in range(broken):
        (d / f"broken_{i}.json").write_text("{not json", encoding="utf-8")
    return ws


def test_items_reports_every_sidecar_read(tmp_path):
    ws = _bundle(tmp_path)
    seen = []
    items = ws.items(progress=lambda done, total, name: seen.append((done, total)))
    assert len(items) == 5                      # the broken sidecar is skipped
    assert seen[-1] == (6, 6)                   # but still counted as read
    assert [d for d, _ in seen] == list(range(1, 7))


def test_items_without_progress_is_unchanged(tmp_path):
    assert len(_bundle(tmp_path).items()) == 5


def test_the_bridge_passes_progress_through(tmp_path):
    from idt_core.gui_bridge import bundle_to_gui_workspace_dict

    ws = _bundle(tmp_path, broken=0)
    seen = []
    data = bundle_to_gui_workspace_dict(ws, progress=lambda d, t, n: seen.append(d))
    assert len(data["items"]) == 5 and seen == [1, 2, 3, 4, 5]
