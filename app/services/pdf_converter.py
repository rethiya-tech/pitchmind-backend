import asyncio
import logging
import os
import subprocess
import tempfile

_log = logging.getLogger(__name__)

_LIBREOFFICE = next(
    (p for p in ("/usr/bin/libreoffice", "/usr/bin/soffice", "libreoffice", "soffice")
     if os.path.isabs(p) and os.path.exists(p)) or "libreoffice",
    "libreoffice",
)


def _convert_sync(pptx_bytes: bytes) -> bytes:
    """Run LibreOffice headless conversion in a temp directory.

    Uses an isolated user-profile per call to avoid lock conflicts when
    multiple conversions happen concurrently.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        pptx_path = os.path.join(tmpdir, "presentation.pptx")
        pdf_path = os.path.join(tmpdir, "presentation.pdf")
        profile_dir = os.path.join(tmpdir, "profile")

        with open(pptx_path, "wb") as f:
            f.write(pptx_bytes)

        cmd = [
            _LIBREOFFICE,
            "--headless",
            "--norestore",
            "--nofirststartwizard",
            f"-env:UserInstallation=file://{profile_dir}",
            "--convert-to", "pdf",
            "--outdir", tmpdir,
            pptx_path,
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0 or not os.path.exists(pdf_path):
            stderr = result.stderr.decode(errors="replace")
            raise RuntimeError(f"LibreOffice PDF conversion failed: {stderr}")

        with open(pdf_path, "rb") as f:
            return f.read()


async def convert_pptx_to_pdf(pptx_bytes: bytes) -> bytes:
    """Async wrapper — runs LibreOffice in a thread pool to avoid blocking."""
    return await asyncio.to_thread(_convert_sync, pptx_bytes)
