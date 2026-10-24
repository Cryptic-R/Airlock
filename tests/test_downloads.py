import pytest
from engine.downloads import Quarantine


def test_missing_scanner_keeps_pdf_quarantined(tmp_path, monkeypatch):
    monkeypatch.setattr('engine.downloads.shutil.which', lambda _: None)
    scan = Quarantine(tmp_path).receive([b'%PDF-1.7\nexample'])
    assert scan.status == 'SCAN_ERROR'
    assert (tmp_path / (scan.id + '.bin')).exists()


def test_executable_rejected_without_launch(tmp_path, monkeypatch):
    def forbidden(*a, **k): raise AssertionError('executable reached scanner')
    monkeypatch.setattr('engine.downloads.subprocess.run', forbidden)
    assert Quarantine(tmp_path).receive([b'MZ executable']).status == 'UNSUPPORTED'


def test_oversize_partial_download_removed(tmp_path):
    with pytest.raises(ValueError):
        Quarantine(tmp_path, max_bytes=3).receive([b'1234'])
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('code,status', [(0,'SCAN_PASSED_QUARANTINED'),(1,'MALICIOUS'),(2,'SCAN_ERROR')])
def test_scanner_verdicts_never_release_file(tmp_path, monkeypatch, code, status):
    monkeypatch.setattr('engine.downloads.shutil.which', lambda _: '/trusted/clamscan')
    monkeypatch.setattr('engine.downloads.subprocess.run', lambda *a, **k: type('Result', (), {'returncode':code})())
    scan=Quarantine(tmp_path).receive([b'%PDF-1.7\nexample'])
    assert scan.status == status
    assert (tmp_path / (scan.id + '.bin')).exists()
