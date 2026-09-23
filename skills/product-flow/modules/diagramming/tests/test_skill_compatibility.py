from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ModuleCompatibilityTest(unittest.TestCase):
    def test_internal_entrypoint_stays_portable_and_non_discoverable(self) -> None:
        module = (ROOT / "MODULE.md").read_text(encoding="utf-8")
        self.assertIn("SYBuilder 内置制图模块", module)
        self.assertIn("modules/diagramming", module)
        self.assertNotIn("CLAUDE_SKILL_DIR", module)
        self.assertFalse((ROOT / "SKILL.md").exists(), "内部库不能变成第四个自动触发 Skill")

    def test_runtime_metadata_and_bundled_resources_exist(self) -> None:
        for relative_path in (
            "LICENSE",
            "MODULE.md",
            "references/png-export.md",
            "scripts/generate-diagram.sh",
            "scripts/chrome-svg-to-png.py",
            "scripts/svg2png.js",
        ):
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)

    def test_upstream_provenance_is_preserved(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["name"], "@sybuilder/internal-diagramming")
        self.assertEqual(package["version"], "1.0.5-vendored")
        self.assertTrue(package["private"])
        self.assertEqual(package["license"], "MIT")
        self.assertEqual(package["sybuilderVendoredFrom"]["version"], "1.0.5")
        self.assertIn("yizhiyanhua-ai/fireworks-tech-graph",
                      package["sybuilderVendoredFrom"]["repository"])
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)

    def test_neutral_style_names_do_not_claim_vendor_official_status(self) -> None:
        names = "\n".join(str(path.relative_to(ROOT)) for path in ROOT.rglob("*"))
        self.assertNotIn("claude-official", names.lower())
        self.assertNotIn("openai-official", names.lower())


if __name__ == "__main__":
    unittest.main()
