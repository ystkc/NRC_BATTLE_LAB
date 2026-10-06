import json
import tempfile
import unittest
from pathlib import Path

from scripts.manual_verify_core import build_template, run_case


class ManualVerifyCoreTests(unittest.TestCase):
    def test_template_can_run_and_write_state_diff(self):
        project = Path(__file__).resolve().parents[1]
        data_dir = project / "data"
        template = build_template(data_dir)
        self.assertNotIn("display_name", template["own_team"]["creatures"][0])
        own_creature = template["own_team"]["creatures"][0]
        self.assertNotIn("attributes", own_creature["base"])
        self.assertNotIn("ability", own_creature)
        self.assertNotIn("abilities", own_creature)
        self.assertNotIn("skill_name", template["own_turn"]["primary"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "case.json"
            output_path = root / "case.output.json"
            changes_path = root / "case.changes.json"
            input_path.write_text(
                json.dumps(template, ensure_ascii=False),
                encoding="utf-8",
            )

            run_case(input_path, output_path, changes_path, data_dir)

            result = json.loads(output_path.read_text(encoding="utf-8"))
            changes = json.loads(changes_path.read_text(encoding="utf-8"))
            self.assertIn("events", result)
            self.assertIn("debug", result)
            self.assertIn("attribute_calculation", result["debug"])
            self.assertIn("damage_calculation", result["debug"])
            self.assertIn("turn_start_skill_display", result)
            creature = result["own"]["before"]["creatures"][0]
            self.assertIsInstance(creature["buffs"], list)
            self.assertIsInstance(creature["debuffs"], list)
            self.assertIsInstance(creature["statuses"], list)
            self.assertEqual(changes["format"], "nrc_manual_verification_changes.v1")
            self.assertEqual(changes["change_count"], len(changes["changes"]))
            self.assertTrue(changes["changes"])


if __name__ == "__main__":
    unittest.main()
