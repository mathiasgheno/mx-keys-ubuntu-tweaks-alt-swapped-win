import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('cedilla', Path(__file__).resolve().parents[1] / 'scripts/install-cedilla.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CedillaTests(unittest.TestCase):
    def test_new_file_and_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.XCompose'
            self.assertTrue(module.install(path))
            self.assertIn('include "%L"', path.read_text())
            self.assertIn('<dead_acute> <c> : "ç"', path.read_text())
            self.assertIn('<dead_acute> <C> : "Ç"', path.read_text())
            self.assertFalse(module.install(path))

    def test_preserves_existing_file_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.XCompose'
            original = '# custom rules\ninclude "%L"\n'
            path.write_text(original)
            module.install(path)
            self.assertTrue(path.read_text().startswith(original))
            self.assertEqual(path.with_name('.XCompose.before-cedilla').read_text(), original)
