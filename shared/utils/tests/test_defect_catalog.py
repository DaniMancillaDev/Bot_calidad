import json
import unittest
from pathlib import Path


CATALOG_PATH = (
    Path(__file__).resolve().parents[2]
    / "infrastructure"
    / "ai"
    / "defect_catalog.json"
)


class DefectCatalogTests(unittest.TestCase):
    def test_prod_additions_are_preserved_and_translate_without_ai(self):
        from shared.infrastructure.ai.defect_translator import deterministic_translate_defect

        fixture = Path(__file__).with_name('prod_catalog_additions_20261025.json')
        additions = json.loads(fixture.read_text(encoding='utf-8'))
        self.assertEqual(sum(len(entries) for entries in additions.values()), 47)
        for section, entries in additions.items():
            for key, value in entries.items():
                with self.subTest(section=section, key=key):
                    self.assertEqual(self.catalog[section][key], value)
        for description, expected in additions['exact_matches'].items():
            with self.subTest(description=description):
                self.assertEqual(deterministic_translate_defect(description), (expected, 'INPUT'))

    @classmethod
    def setUpClass(cls):
        with CATALOG_PATH.open(encoding="utf-8") as catalog_file:
            cls.catalog = json.load(catalog_file)

    def test_catalog_is_valid_and_contains_runtime_web_additions(self):
        expected = {
            "exact_matches": {
                "sheet flyer dañado": "DAMAGED SHEET FLYER",
                "sheet flyer danado": "DAMAGED SHEET FLYER",
                "blu mal retrabajado": "METAL BLU WITH BAD REWORK",
            },
            "components": {
                "sheet flyer": "SHEET FLYER",
                "bracket": "BKT",
            },
            "material_areas": {
                "SHEET FLYER": "INPUT",
                "DAMAGED SHEET FLYER": "INPUT",
                "METAL BLU WITH BAD REWORK": "INPUT",
                "bracket": "INPUT",
            },
            "symptoms": {
                "mal retrabajad": "BADLY REWORKED",
                "mal retrabajo": "BAD REWORK",
            },
        }

        for section, entries in expected.items():
            for key, value in entries.items():
                self.assertEqual(self.catalog[section].get(key), value)

    def test_catalog_keeps_all_required_translation_sections(self):
        self.assertEqual(
            set(self.catalog),
            {"areas", "exact_matches", "components", "material_areas", "symptoms", "connectors"},
        )
        self.assertGreaterEqual(len(self.catalog["exact_matches"]), 8)
        self.assertGreaterEqual(len(self.catalog["components"]), 60)
