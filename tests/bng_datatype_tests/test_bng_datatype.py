import os
from django.test import TestCase
from django.core import management
from django.test.utils import captured_stdout
from arches.app.models.models import Node
from arches.app.datatypes.datatypes import DataTypeFactory
from tests import test_settings


# These tests can be run from the command line via:
# python manage.py test tests.bng_datatype_tests.test_bng_datatype --settings="tests.test_settings"
# or if using docker
# python manage.py test tests.bng_datatype_tests.test_bng_datatype --settings="tests.test_settings_for_docker"


class BNGCentreDataTypeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        bng_test_model_path = os.path.join(
            test_settings.PROJECT_TEST_ROOT,
            "fixtures",
            "pkg",
            "graphs",
            "resource_models",
            "bng_test_model.json",
        )

        with captured_stdout():
            management.call_command(
                "packages",
                operation="import_graphs",
                source=bng_test_model_path,
                verbosity=0,
            )

    def setUp(self):
        # Update this node ID to match the actual node ID from the fixture
        self.bng_node_id = Node.objects.filter(datatype="bngcentrepoint").first().nodeid

    def _get_datatype(self):
        node = Node.objects.get(nodeid=self.bng_node_id)
        return DataTypeFactory().get_instance(node.datatype)

    def test_01_bngcentrepoint_validation_valid_value(self):
        errors = self._get_datatype().validate("NT1234567890")
        self.assertEqual(errors, [])

    def test_02_bngcentrepoint_validation_wrong_length(self):
        errors = self._get_datatype().validate("NT12345")
        self.assertTrue(len(errors) > 0)
        self.assertEqual(
            errors[0]["message"], "Input data must be exactly 12 characters long."
        )

    def test_03_bngcentrepoint_validation_invalid_grid_square(self):
        errors = self._get_datatype().validate("ZZ1234567890")
        self.assertTrue(len(errors) > 0)
        self.assertEqual(
            errors[0]["message"], "Invalid grid square identifier in input data."
        )

    def test_04_bngcentrepoint_validation_non_numeric_part(self):
        errors = self._get_datatype().validate("NT12345ABCD")
        self.assertTrue(len(errors) > 0)
        self.assertEqual(
            errors[0]["message"],
            "Numeric part of the input data is not a valid integer.",
        )

    def test_05_bngcentrepoint_validation_non_string_input(self):
        errors = self._get_datatype().validate(1233445)
        self.assertTrue(len(errors) > 0)
        self.assertIn("Unexpected error during validation", errors[0]["message"])
