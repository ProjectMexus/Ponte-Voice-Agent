"""Import the middleware from the files shipped by each Python Docker image."""
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RuntimePackagingTests(unittest.TestCase):
    def test_python_images_include_all_required_runtime_imports(self):
        root = Path(__file__).resolve().parents[1]
        runtime_sources = {"MCP", "middleware", "mock_backends", "ponte_logging.py", "http_policy.py"}
        for dockerfile in ("Dockerfile.middleware", "Dockerfile.render"):
            with self.subTest(image=dockerfile), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory)
                for line in (root / dockerfile).read_text(encoding="utf-8").splitlines():
                    if not line.startswith("COPY "):
                        continue
                    fields = shlex.split(line)
                    if fields and fields[0] == "COPY":
                        for source in fields[1:-1]:
                            if source in runtime_sources:
                                original = root / source
                                if original.is_dir():
                                    shutil.copytree(original, destination / source, ignore=shutil.ignore_patterns("__pycache__"))
                                else:
                                    shutil.copy2(original, destination / source)
                environment = {**os.environ, "PYTHONPATH": str(destination)}
                completed = subprocess.run([sys.executable, "-c", "import middleware.server; import MCP.rest_adapter; import middleware.llm_transport"], cwd=destination, env=environment, capture_output=True, text=True, timeout=15)
                self.assertEqual(completed.returncode, 0, completed.stderr)
