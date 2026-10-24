"""Quarantine-only download storage. Never opens, extracts, imports or executes content.

Adapters must stream downloaded bytes here. No arbitrary URL fetching is exposed.
A CLEAN result permits a future isolated extractor, never direct host opening.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4


@dataclass(frozen=True)
class ScanResult:
    id: str
    status: str
    sha256: str
    size: int
    reason: str


class Quarantine:
    def __init__(self, root, max_bytes=10 * 1024 * 1024):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.max_bytes = max_bytes

    def receive(self, chunks):
        ident = uuid4().hex
        path = self.root / (ident + '.bin')
        digest, size = sha256(), 0
        try:
            with path.open('xb') as out:
                path.chmod(0o600)
                for chunk in chunks:
                    if not isinstance(chunk, bytes):
                        raise ValueError('Download stream must contain bytes')
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ValueError('File exceeds configured size limit')
                    digest.update(chunk)
                    out.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        result = self._scan(path, ident, digest.hexdigest(), size)
        meta = self.root / (ident + '.json')
        meta.write_text(json.dumps(asdict(result)))
        meta.chmod(0o600)
        return result

    def receive_bytes(self, data: bytes, name: str = "download"):
        return self.receive([data])

    def _scan(self, path, ident, digest, size):
        def result(status, reason):
            return ScanResult(ident, status, digest, size, reason)
        with path.open('rb') as src:
            sample = src.read(1024 * 1024)
            header = sample[:16]
        if not (header.startswith(b'%PDF-') or header.startswith(b'\x89PNG\r\n\x1a\n') or header.startswith(b'\xff\xd8\xff')):
            return result('UNSUPPORTED', 'Only PDF, PNG and JPEG candidates are accepted; no extraction performed')
        
        # Scan for dangerous embedded executable active content and malware patterns
        lower_sample = sample.lower()
        if b'eicar-standard-antivirus-test-file' in lower_sample:
            return result('MALICIOUS', 'Known test malware signature detected (EICAR); file remains quarantined')
        
        if header.startswith(b'%PDF-'):
            # Detect unwanted executable instructions and active code in PDF
            active_threats = []
            if b'/launch' in lower_sample:
                active_threats.append('program launch command (/Launch)')
            if b'/embeddedfiles' in lower_sample or b'/embeddedfile' in lower_sample:
                active_threats.append('embedded executable file (/EmbeddedFiles)')
            if b'/javascript' in lower_sample or b'/js' in lower_sample:
                active_threats.append('embedded script (/JavaScript)')
            if b'/openaction' in lower_sample:
                active_threats.append('automatic execution action (/OpenAction)')
            if b'this program cannot be run in dos mode' in lower_sample or (b'mz' in lower_sample and b'pe\x00\x00' in lower_sample):
                active_threats.append('embedded Windows executable binary')
            
            if active_threats:
                return result('MALICIOUS', f'Unwanted executable content or active code detected ({", ".join(active_threats)}); file remains quarantined')

        scanner = shutil.which('clamscan')
        if not scanner:
            return result('SCAN_ERROR', 'Antivirus scanner unavailable; file remains quarantined')
        try:
            run = subprocess.run([scanner, '--no-summary', '--infected', '--', str(path.resolve())],
                                 capture_output=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return result('SCAN_ERROR', 'Scanner could not complete; file remains quarantined')
        if run.returncode == 1:
            return result('MALICIOUS', 'Antivirus reported a threat; file remains quarantined')
        if run.returncode != 0:
            return result('SCAN_ERROR', 'Scanner error; file remains quarantined')
        # Even clean files stay quarantined: signature freshness, PDF active-content
        # validation and an isolated extractor must be deployed before release.
        return result('SCAN_PASSED_QUARANTINED', 'No antivirus detection; secure extraction is not enabled')

