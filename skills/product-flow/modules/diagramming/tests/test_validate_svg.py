from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_svg.py"
SPEC = importlib.util.spec_from_file_location("validate_svg", SCRIPT)
assert SPEC and SPEC.loader
validate_svg = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validate_svg
SPEC.loader.exec_module(validate_svg)


class ValidateSvgTest(unittest.TestCase):
    def write_svg(self, body: str) -> Path:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        path = Path(tempdir.name) / "diagram.svg"
        path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 240">'
            '<defs><marker id="arrow-main"><path d="M0 0 L8 4 L0 8 Z"/></marker></defs>'
            f"{body}</svg>",
            encoding="utf-8",
        )
        return path

    def test_text_with_equals_is_valid_xml(self) -> None:
        path = self.write_svg('<text x="10" y="20">retrieve(top_k=5)</text>')
        ok, details = validate_svg.run_check(path, "xml")
        self.assertTrue(ok, details)

    def test_marker_start_and_end_are_resolved_structurally(self) -> None:
        path = self.write_svg(
            '<path d="M 20 20 H 100" marker-start="url(#arrow-main)" marker-end="url(#arrow-main)"/>'
        )
        ok, details = validate_svg.run_check(path, "markers")
        self.assertTrue(ok, details)

    def test_missing_marker_start_is_reported(self) -> None:
        path = self.write_svg('<path d="M 20 20 H 100" marker-start="url(#missing)"/>')
        ok, details = validate_svg.run_check(path, "markers")
        self.assertFalse(ok)
        self.assertEqual(details, ["missing marker: missing"])

    def test_absolute_hv_path_collision_is_reported(self) -> None:
        path = self.write_svg(
            '<rect id="blocker" x="160" y="80" width="80" height="60"/>'
            '<path id="edge" d="M 20 110 H 280 V 180" marker-end="url(#arrow-main)"/>'
        )
        ok, details = validate_svg.run_check(path, "collisions")
        self.assertFalse(ok)
        self.assertIn("path#edge intersects rect#blocker", details)

    def test_relative_hv_path_collision_is_reported(self) -> None:
        path = self.write_svg(
            '<rect id="blocker" x="160" y="80" width="80" height="60"/>'
            '<path id="edge" d="m 20 110 h 260 v 70" marker-end="url(#arrow-main)"/>'
        )
        ok, _ = validate_svg.run_check(path, "collisions")
        self.assertFalse(ok)

    def test_quadratic_and_cubic_curves_are_sampled(self) -> None:
        quadratic = self.write_svg(
            '<rect id="blocker" x="160" y="80" width="80" height="60"/>'
            '<path id="edge" d="M 20 180 Q 200 20 380 180" marker-end="url(#arrow-main)"/>'
        )
        cubic = self.write_svg(
            '<rect id="blocker" x="160" y="80" width="80" height="60"/>'
            '<path id="edge" d="M 20 180 C 100 60 300 60 380 180" marker-end="url(#arrow-main)"/>'
        )
        self.assertFalse(validate_svg.run_check(quadratic, "collisions")[0])
        self.assertFalse(validate_svg.run_check(cubic, "collisions")[0])

    def test_boundary_to_boundary_connection_is_not_a_collision(self) -> None:
        path = self.write_svg(
            '<rect id="source" x="20" y="80" width="80" height="60"/>'
            '<rect id="target" x="280" y="80" width="80" height="60"/>'
            '<path id="edge" d="M 100 110 H 280" marker-end="url(#arrow-main)"/>'
        )
        ok, details = validate_svg.run_check(path, "collisions")
        self.assertTrue(ok, details)

    def test_small_dashed_node_is_an_obstacle_but_large_container_is_not(self) -> None:
        path = self.write_svg(
            '<rect id="container" x="10" y="20" width="380" height="200" fill="none" stroke-dasharray="6 4"/>'
            '<rect id="node" x="160" y="80" width="80" height="60" fill="none" stroke-dasharray="4 3"/>'
            '<path id="edge" d="M 20 110 H 280" marker-end="url(#arrow-main)"/>'
        )
        ok, details = validate_svg.run_check(path, "collisions")
        self.assertFalse(ok)
        self.assertEqual(details, ["path#edge intersects rect#node"])

    def test_legend_sample_arrows_do_not_collide_with_their_background(self) -> None:
        path = self.write_svg(
            '<rect id="legend" x="20" y="150" width="200" height="70"/>'
            '<path id="sample-a" d="M 40 170 H 80" marker-end="url(#arrow-main)"/>'
            '<path id="sample-b" d="M 40 195 H 80" marker-end="url(#arrow-main)"/>'
        )
        ok, details = validate_svg.run_check(path, "collisions")
        self.assertTrue(ok, details)

    def test_group_transform_is_applied_to_paths_and_obstacles(self) -> None:
        path = self.write_svg(
            '<g transform="translate(80 20)">'
            '<rect id="blocker" x="80" y="60" width="80" height="60"/>'
            '<path id="edge" d="M 20 90 H 200" marker-end="url(#arrow-main)"/>'
            '</g>'
        )
        ok, details = validate_svg.run_check(path, "collisions")
        self.assertFalse(ok)
        self.assertEqual(details, ["path#edge intersects rect#blocker"])


if __name__ == "__main__":
    unittest.main()
