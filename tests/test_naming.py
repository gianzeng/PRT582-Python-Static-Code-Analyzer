import unittest

from pyanalyzer.engine import analyze_source


class NamingTests(unittest.TestCase):
    def test_b10_valid_names_and_conventional_exemptions_are_accepted(self):
        source = """GOOD_CONSTANT = 1
class GoodClass:
    def good_method(self, good_arg):
        _ = good_arg
        return good_arg
"""

        result = analyze_source(source, "names.py")

        self.assertEqual([item for item in result.findings if item.category == "naming"], [])

    def test_b11_invalid_names_have_specific_rules_and_locations(self):
        source = """badConstant = 1
class badClass:
    pass

def BadFunction(badArg):
    badLocal = badArg
    return badLocal
"""

        result = analyze_source(source, "names.py")
        naming = [item for item in result.findings if item.category == "naming"]

        self.assertEqual({item.rule_id for item in naming}, {"N001", "N002", "N003"})
        self.assertTrue(any(item.rule_id == "N002" and item.line == 2 for item in naming))
        self.assertTrue(any(item.rule_id == "N001" and item.line == 5 for item in naming))
        self.assertTrue(any(item.rule_id == "N003" and item.line == 1 for item in naming))
        self.assertTrue(any(item.evidence.get("name") == "badLocal" for item in naming))

    def test_annotated_module_constant_uses_constant_rule(self):
        result = analyze_source("mixedConstant: int = 1\n", "names.py")

        naming = [item for item in result.findings if item.category == "naming"]

        self.assertEqual(len(naming), 1)
        self.assertEqual(naming[0].rule_id, "N003")
        self.assertEqual(naming[0].evidence["name"], "mixedConstant")

    def test_exception_binding_is_checked_as_a_variable_name(self):
        source = """try:
    value = 1
except ValueError as badName:
    print(badName)
"""

        result = analyze_source(source, "names.py")
        naming = [item for item in result.findings if item.category == "naming"]

        self.assertEqual(len(naming), 1)
        self.assertEqual(naming[0].rule_id, "N001")
        self.assertEqual(naming[0].evidence["name"], "badName")

    def test_module_loop_context_and_augmented_bindings_are_not_skipped(self):
        source = """for loopName in []:
    pass

with context_manager as contextName:
    pass

augmentedName += 1
"""

        result = analyze_source(source, "names.py")
        naming = [item for item in result.findings if item.category == "naming"]

        self.assertEqual(
            {(item.rule_id, item.evidence["name"]) for item in naming},
            {
                ("N001", "loopName"),
                ("N001", "contextName"),
                ("N001", "augmentedName"),
            },
        )

    def test_only_assignment_binding_is_classified_as_a_module_constant(self):
        source = """loopName = 1
for loopName in []:
    pass
"""

        result = analyze_source(source, "names.py")
        naming = [item for item in result.findings if item.category == "naming"]

        self.assertEqual(
            {(item.rule_id, item.evidence["name"]) for item in naming},
            {("N003", "loopName"), ("N001", "loopName")},
        )

    def test_imported_symbol_names_are_not_misclassified_as_local_names(self):
        source = """from pathlib import Path
from typing import Iterable

value = Path('x')
"""

        result = analyze_source(source, "names.py")
        naming = [item for item in result.findings if item.category == "naming"]

        self.assertEqual(naming, [])

    def test_explicit_import_alias_uses_local_naming_rule(self):
        result = analyze_source("from pathlib import Path as badAlias\n", "names.py")

        naming = [item for item in result.findings if item.category == "naming"]

        self.assertEqual(len(naming), 1)
        self.assertEqual(naming[0].rule_id, "N001")
        self.assertEqual(naming[0].evidence["name"], "badAlias")
