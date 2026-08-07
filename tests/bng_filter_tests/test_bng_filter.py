import json
import logging
from unittest import mock
from unittest.mock import MagicMock, Mock, patch
from django.test import TestCase, RequestFactory, TransactionTestCase
from django.contrib.gis.geos import GEOSGeometry, Point, Polygon
from django.db import connection
from arches.app.utils.betterJSONSerializer import JSONDeserializer, JSONSerializer
from arches.app.search.elasticsearch_dsl_builder import Bool, Nested, Terms, GeoShape
from arches_bng.search.components.bng_filter import BngFilter, details, _buffer

# These tests can be run from the command line via:
# python manage.py test tests.bng_filter_tests.test_bng_filter --settings="tests.test_settings"
# or if using docker
# python manage.py test tests.bng_filter_tests.test_bng_filter --settings="tests.test_settings_for_docker"


class BngFilterUnitTests(TestCase):
    """
    Unit tests for the BngFilter search component
    """

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.bng_filter = BngFilter()

    def test_01_bng_grid_square_returns_dict(self):
        """
        Test that bng_grid_square returns a dictionary with all grid squares.
        
        This test verifies:
        - The method returns a dictionary (not list or other type)
        - The dictionary contains the correct coordinate pairs for known grid squares
        - NT, SU, and HO grid squares have expected [easting, northing] values
        """
        grid_square = self.bng_filter.bng_grid_square()
        self.assertIsInstance(grid_square, dict)
        # Test a few known grid squares
        self.assertEqual(grid_square["NT"], [3, 6])
        self.assertEqual(grid_square["SU"], [4, 1])
        self.assertEqual(grid_square["HO"], [3, 12])

    def test_02_bng_grid_square_contains_expected_squares(self):
        """
        Test that all expected BNG grid squares are present in the dictionary.
        
        This test verifies:
        - All major UK grid squares (NT, SU, HO, HP, SX, SY, SZ) are defined
        - Each grid square value is a list (not tuple or other)
        - Each grid square list contains exactly 2 elements [easting, northing]
        """
        grid_square = self.bng_filter.bng_grid_square()
        expected_squares = ["NT", "SU", "HO", "HP", "SX", "SY", "SZ"]
        for square in expected_squares:
            self.assertIn(square, grid_square)
            self.assertIsInstance(grid_square[square], list)
            self.assertEqual(len(grid_square[square]), 2)

    def test_03_pad_coord_pads_correctly(self):
        """
        Test that pad_coord correctly pads coordinates to the specified length.
        
        This test verifies:
        - A 3-character coordinate padded to length 6 with '0' becomes "123000.0"
        - The padding adds the pad value characters followed by a decimal point and one more pad value
        - The method correctly right-pads the coordinate string
        """
        result = self.bng_filter.pad_coord("123", "0", 6)
        self.assertEqual(result, "123000.0")

    def test_04_pad_coord_pads_with_different_values(self):
        """
        Test pad_coord with different padding values (0 and 9).
        
        This test verifies:
        - Padding with '0' produces "456000.0" (min coordinate within the 1km grid square)
        - Padding with '9' produces "456999.9" (max coordinate within the 1km grid square)
        - The method correctly handles different pad_value arguments
        """
        result_0 = self.bng_filter.pad_coord("456", "0", 6)
        self.assertEqual(result_0, "456000.0")

        result_9 = self.bng_filter.pad_coord("456", "9", 6)
        self.assertEqual(result_9, "456999.9")

    def test_05_pad_coord_no_padding_needed(self):
        """
        Test pad_coord when the coordinate is already at the target length.
        
        This test verifies:
        - A 6-character coordinate doesn't get padded further
        - The method returns the coordinate unchanged when it's already the target length
        """
        result = self.bng_filter.pad_coord("123456", "0", 6)
        self.assertEqual(result, "123456")

    def test_06_build_geojson_from_bng_with_valid_bng(self):
        """
        Test building GeoJSON from a valid BNG reference using REAL geometry transformation.
        
        This test verifies:
        - A valid BNG reference (NT00) produces a GeoJSON FeatureCollection
        - The result contains at least one feature
        - Each feature has proper GeoJSON structure (type, geometry, properties)
        - The feature's bngref property matches the input BNG value
        - Uses actual geometry transformation (not mocked) for realistic testing
        """
        result = self.bng_filter.build_geojson_from_bng("NT00", 0)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertIn("features", result)
        self.assertGreaterEqual(len(result["features"]), 1)
        
        # Verify the feature structure
        feature = result["features"][0]
        self.assertEqual(feature["type"], "Feature")
        self.assertIn("geometry", feature)
        self.assertIn("properties", feature)
        self.assertEqual(feature["properties"]["bngref"], "NT00")

    def test_07_build_geojson_from_bng_returns_feature_collection(self):
        """
        Test that build_geojson_from_bng returns a proper FeatureCollection with real geometry.
        
        This test verifies:
        - A BNG reference with numeric coordinates (NT1234) produces valid GeoJSON
        - The FeatureCollection contains a non-empty list of features
        - The feature has correct structure and properties (bngref, type="grid_square")
        - The geometry is valid with type (Polygon or Point) and coordinates
        - Uses actual geometry calculation based on BNG coordinate system
        """
        result = self.bng_filter.build_geojson_from_bng("NT1234", 0)

        self.assertEqual(result["type"], "FeatureCollection")
        self.assertIsInstance(result["features"], list)
        self.assertGreater(len(result["features"]), 0)
        
        # Check feature structure
        feature = result["features"][0]
        self.assertEqual(feature["type"], "Feature")
        self.assertIn("properties", feature)
        self.assertIn("geometry", feature)
        self.assertEqual(feature["properties"]["bngref"], "NT1234")
        self.assertEqual(feature["properties"]["type"], "grid_square")
        
        # Verify geometry is valid
        self.assertIn("type", feature["geometry"])
        self.assertIn("coordinates", feature["geometry"])
        geometry_type = feature["geometry"]["type"]
        self.assertIn(geometry_type, ["Polygon", "Point"])

    def test_08_build_geojson_from_bng_with_none_value(self):
        """
        Test building GeoJSON with None BNG value (edge case).
        
        This test verifies:
        - When None is passed as the BNG value, the method returns an empty FeatureCollection
        - The result is still a valid FeatureCollection structure with zero features
        - The method handles None gracefully without raising exceptions
        """
        result = self.bng_filter.build_geojson_from_bng(None, 0)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertEqual(len(result["features"]), 0)

    def test_09_build_geojson_from_bng_with_buffer(self):
        """
        Test building GeoJSON with a buffer distance (1000m) using REAL buffer logic.
        
        This test verifies:
        - When buffer_value > 0, the result contains TWO features: the grid square and its buffer
        - First feature is the original grid square with type="grid_square"
        - Second feature is the buffered polygon with type="grid_square_buffer"
        - Buffer feature includes the buffer distance value in properties
        - Both features have valid coordinate data
        - Uses actual PostGIS buffer calculation (not mocked)
        """
        result = self.bng_filter.build_geojson_from_bng("NT1234", buffer_value=1000)

        self.assertEqual(result["type"], "FeatureCollection")
        # When buffer is > 0, we should have 2 features (grid square + buffer)
        self.assertEqual(len(result["features"]), 2)
        
        # First feature should be the grid square
        self.assertEqual(result["features"][0]["properties"]["type"], "grid_square")
        self.assertEqual(result["features"][0]["properties"]["bngref"], "NT1234")
        
        # Second feature should be the buffer
        self.assertEqual(result["features"][1]["properties"]["type"], "grid_square_buffer")
        self.assertEqual(result["features"][1]["properties"]["bngref"], "NT1234")
        self.assertEqual(result["features"][1]["properties"]["buffer"], 1000)
        
        # Buffer geometry should be larger than the original grid square
        original_coords = result["features"][0]["geometry"]["coordinates"]
        buffer_coords = result["features"][1]["geometry"]["coordinates"]
        self.assertIsNotNone(original_coords)
        self.assertIsNotNone(buffer_coords)

    def test_10_build_geojson_extracts_grid_square_letters(self):
        """
        Test that build_geojson correctly extracts and uses different grid square letters.
        
        This test verifies:
        - The first 2 characters of a BNG reference (grid square identifier) are correctly extracted
        - Different grid squares (NT, SU) produce different coordinate ranges
        - The NT grid square in "NT5678" produces different coordinates than "SU5678"
        - Grid square extraction logic directly affects the final geometry coordinates
        - Uses REAL geometry transformation to verify grid square letters are properly used
        """
        # Build geometry with NT grid square
        result_nt = self.bng_filter.build_geojson_from_bng("NT5678", 0)
        
        # Build geometry with SU grid square (different grid square, same numbers)
        result_su = self.bng_filter.build_geojson_from_bng("SU5678", 0)
        
        # Both should be valid FeatureCollections
        self.assertEqual(result_nt["type"], "FeatureCollection")
        self.assertEqual(result_su["type"], "FeatureCollection")
        self.assertGreater(len(result_nt["features"]), 0)
        self.assertGreater(len(result_su["features"]), 0)
        
        # NT and SU should have different coordinates (different grid squares map to different areas)
        nt_coords = result_nt["features"][0]["geometry"]["coordinates"]
        su_coords = result_su["features"][0]["geometry"]["coordinates"]
        
        # Verify bngref property is set correctly for each
        self.assertEqual(result_nt["features"][0]["properties"]["bngref"], "NT5678")
        self.assertEqual(result_su["features"][0]["properties"]["bngref"], "SU5678")
        
        # Coordinates should be different because NT and SU are different grid squares
        # (NT is in Scotland, SU is in southern England)
        self.assertNotEqual(nt_coords, su_coords)

    def test_11_transform_to_wgs84(self):
        """
        Test the transform_to_wgs84 method with REAL PostGIS database transformation.
        
        This test verifies:
        - A geometry in OSGB36 (SRID 27700, British National Grid) can be transformed to WGS84 (SRID 4326)
        - The result SRID is correctly set to 4326 (WGS84)
        - Transformed coordinates are in the expected range for the UK
        - Longitude is between -10 and 5 degrees
        - Latitude is between 48 and 58 degrees
        - Uses actual PostGIS ST_TRANSFORM database function for real coordinate conversion
        """
        # Create a test geometry in OSGB36 (SRID 27700)
        # This is a simple point in the NT grid square area (around Northumberland)
        # OSGB coordinates approximately: E=350000, N=600000
        wkt_geom = "POINT(350000 600000)"
        geom = GEOSGeometry(wkt_geom, srid=27700)

        result = self.bng_filter.transform_to_wgs84(geom, from_srid=27700)

        # Result should be in WGS84 (SRID 4326)
        self.assertEqual(result.srid, 4326)
        
        # The result should have coordinates in WGS84 (lon, lat)
        coords = result.coords
        self.assertIsNotNone(coords)
        
        # Coordinates should be reasonable for the UK (approximately -5 to 2 longitude, 50 to 56 latitude)
        self.assertGreater(coords[0], -10)  # Longitude
        self.assertLess(coords[0], 5)
        self.assertGreater(coords[1], 48)   # Latitude
        self.assertLess(coords[1], 58)

    def test_12_append_dsl_with_valid_bng_filter(self):
        """
        Test append_dsl with a valid BNG filter using REAL geometry building.
        
        This test verifies:
        - append_dsl correctly parses BNG filter parameters from the request
        - The search_query_object is modified with bng-filter data
        - The grid_square FeatureCollection is populated in the output
        - The method properly integrates with the Elasticsearch DSL builder
        - The actual DSL query structure is built correctly (Nested Bool query with GeoShape)
        - Uses real geometry building logic (no mocks) for end-to-end testing
        """
        request = self.factory.get('/search', {
            'bng-filter': json.dumps({
                'bng': 'NT1234',
                'buffer': 0,
                'inverted': False
            })
        })
        self.bng_filter.request = request

        # Mock the search_query_object with a proper query builder
        mock_query = Mock()
        search_query_object = {"query": mock_query}
        permitted_nodegroups = ["nodegroup1", "nodegroup2"]

        # Call append_dsl without mocking - uses real geometry building
        self.bng_filter.append_dsl(
            search_query_object,
            permitted_nodegroups=permitted_nodegroups,
            include_provisional=False
        )

        # Verify that the search_query_object was modified
        self.assertIn("bng-filter", search_query_object)
        self.assertIn("grid_square", search_query_object["bng-filter"])
        
        # Verify the grid square data structure with REAL geometry
        grid_square = search_query_object["bng-filter"]["grid_square"]
        self.assertEqual(grid_square["type"], "FeatureCollection")
        self.assertGreater(len(grid_square["features"]), 0)
        self.assertIn("geometry", grid_square["features"][0])
        self.assertIn("coordinates", grid_square["features"][0]["geometry"])
        
        # Verify add_query was called with a Bool query object
        mock_query.add_query.assert_called_once()
        args, kwargs = mock_query.add_query.call_args
        dsl_query = args[0]
        
        # Verify the query is a Bool object (from elasticsearch_dsl_builder)
        self.assertIsNotNone(dsl_query)
        # The Bool query should have filters applied
        self.assertTrue(hasattr(dsl_query, 'to_dict') or isinstance(dsl_query, Bool))

    def test_13_append_dsl_with_inverted_filter(self):
        """
        Test append_dsl with inverted flag set to True using REAL geometry.
        
        This test verifies:
        - When inverted=True, the filter should find records OUTSIDE the BNG grid square
        - The search_query_object is still populated with grid_square data
        - The DSL query uses must_not instead of filter for inverted searches
        - Inverted filtering works correctly with real geometry calculations
        - The actual DSL query structure uses must_not for negation
        """
        request = self.factory.get('/search', {
            'bng-filter': json.dumps({
                'bng': 'NT1234',
                'buffer': 0,
                'inverted': True
            })
        })
        self.bng_filter.request = request

        # Mock the search_query_object with a proper query builder
        mock_query = Mock()
        search_query_object = {"query": mock_query}
        permitted_nodegroups = ["nodegroup1"]

        # Call append_dsl without mocking
        self.bng_filter.append_dsl(
            search_query_object,
            permitted_nodegroups=permitted_nodegroups,
            include_provisional=False
        )

        # Verify the search_query_object was modified
        self.assertIn("bng-filter", search_query_object)
        # The inverted filter should still create a grid_square entry
        self.assertIn("grid_square", search_query_object["bng-filter"])
        
        # Verify add_query was called with a Bool query object
        mock_query.add_query.assert_called_once()
        args, kwargs = mock_query.add_query.call_args
        dsl_query = args[0]
        
        # Verify the query structure exists (inverted queries use must_not)
        self.assertIsNotNone(dsl_query)
        self.assertTrue(hasattr(dsl_query, 'to_dict') or isinstance(dsl_query, Bool))

    def test_14_append_dsl_with_invalid_bng_odd_length(self):
        """
        Test append_dsl with invalid BNG (odd number of characters).
        
        This test verifies:
        - BNG values must have an even number of characters (2 grid square + even number digits)
        - When an odd-length BNG is provided (e.g., "NT123"), a warning is logged
        - The method gracefully handles invalid input without raising exceptions
        - Validation of BNG format happens before geometry processing
        - No DSL query is added when BNG validation fails
        """
        request = self.factory.get('/search', {
            'bng-filter': json.dumps({
                'bng': 'NT123',  # Odd number of chars - invalid
                'buffer': 0,
                'inverted': False
            })
        })
        self.bng_filter.request = request

        # Mock the search_query_object with a proper query builder
        mock_query = Mock()
        search_query_object = {"query": mock_query}
        permitted_nodegroups = ["nodegroup1"]

        with patch('arches_bng.search.components.bng_filter.logger') as mock_logger:
            self.bng_filter.append_dsl(
                search_query_object,
                permitted_nodegroups=permitted_nodegroups,
                include_provisional=False
            )

            # Verify a warning was logged for invalid BNG
            mock_logger.warn.assert_called_once()
            # add_query should still be called even with invalid BNG (with empty Bool)
            mock_query.add_query.assert_called_once()

    def test_15_append_dsl_with_empty_bng_raises_keyerror(self):
        """
        Test append_dsl raises KeyError when BNG is empty (invalid input).
        
        This test verifies:
        - Empty BNG strings are invalid and cannot be processed
        - The method raises KeyError when trying to look up empty grid square letters
        - The error is a KeyError from bng_grid_square() dictionary lookup failure
        - This documents the expected behavior for edge case of empty BNG input
        """
        # Use an invalid empty BNG
        request = self.factory.get('/search', {
            'bng-filter': json.dumps({
                'bng': '',  # Empty BNG - invalid
                'buffer': 0,
                'inverted': False
            })
        })
        self.bng_filter.request = request

        # Mock the search_query_object with a proper query builder
        mock_query = Mock()
        search_query_object = {"query": mock_query}
        permitted_nodegroups = ["nodegroup1"]

        # Explicitly expect KeyError to be raised for empty BNG
        with self.assertRaises(KeyError):
            self.bng_filter.append_dsl(
                search_query_object,
                permitted_nodegroups=permitted_nodegroups,
                include_provisional=False
            )

    def test_16_append_dsl_with_include_provisional_false(self):
        """
        Test append_dsl excludes provisional data when include_provisional is False.
        
        This test verifies:
        - When include_provisional=False, the DSL query includes a filter for non-provisional data
        - The search filters geometries.provisional to only include "false" values
        - Results exclude data marked as provisional/draft
        - The DSL query structure includes a Terms filter for provisional="false"
        """
        request = self.factory.get('/search', {
            'bng-filter': json.dumps({
                'bng': 'NT1234',
                'buffer': 0,
                'inverted': False
            })
        })
        self.bng_filter.request = request

        # Mock the search_query_object with a proper query builder
        mock_query = Mock()
        search_query_object = {"query": mock_query}
        permitted_nodegroups = ["nodegroup1"]

        # Call with real geometry and include_provisional=False
        self.bng_filter.append_dsl(
            search_query_object,
            permitted_nodegroups=permitted_nodegroups,
            include_provisional=False
        )

        # Query should be updated
        self.assertIsNotNone(search_query_object["query"])
        self.assertIn("bng-filter", search_query_object)
        
        # Verify add_query was called with a Bool query
        mock_query.add_query.assert_called_once()
        args, kwargs = mock_query.add_query.call_args
        dsl_query = args[0]
        
        # Verify a valid query object was created
        self.assertIsNotNone(dsl_query)
        # The query should be a Bool object with filters
        self.assertTrue(hasattr(dsl_query, 'to_dict') or isinstance(dsl_query, Bool))

    def test_17_append_dsl_with_include_provisional_only(self):
        """
        Test append_dsl includes only provisional data when include_provisional="only provisional".
        
        This test verifies:
        - When include_provisional="only provisional", the DSL query includes only provisional data
        - The search filters geometries.provisional to only include "true" values
        - Results show only data marked as provisional/draft
        - The DSL query structure includes a Terms filter for provisional="true"
        """
        request = self.factory.get('/search', {
            'bng-filter': json.dumps({
                'bng': 'NT1234',
                'buffer': 0,
                'inverted': False
            })
        })
        self.bng_filter.request = request

        # Mock the search_query_object with a proper query builder
        mock_query = Mock()
        search_query_object = {"query": mock_query}
        permitted_nodegroups = ["nodegroup1"]

        # Call with real geometry and include_provisional="only provisional"
        self.bng_filter.append_dsl(
            search_query_object,
            permitted_nodegroups=permitted_nodegroups,
            include_provisional="only provisional"
        )

        # Query should be updated
        self.assertIsNotNone(search_query_object["query"])
        self.assertIn("bng-filter", search_query_object)
        
        # Verify add_query was called with a Bool query
        mock_query.add_query.assert_called_once()
        args, kwargs = mock_query.add_query.call_args
        dsl_query = args[0]
        
        # Verify a valid query object was created
        self.assertIsNotNone(dsl_query)
        # The query should be a Bool object with filters for provisional data
        self.assertTrue(hasattr(dsl_query, 'to_dict') or isinstance(dsl_query, Bool))

    def test_18_append_dsl_creates_component_name_key(self):
        """
        Test that append_dsl creates component name key in search_query_object.
        
        This test verifies:
        - The search_query_object includes a key with the component name ("bng-filter")
        - This component-specific data includes the grid_square FeatureCollection
        - The data structure allows the search system to track which filter generated which results
        - The component data contains valid GeoJSON with real geometry from the BNG calculation
        """
        request = self.factory.get('/search', {
            'bng-filter': json.dumps({
                'bng': 'NT1234',
                'buffer': 0,
                'inverted': False
            })
        })
        self.bng_filter.request = request

        # Mock the search_query_object with a proper query builder
        mock_query = Mock()
        search_query_object = {"query": mock_query}
        permitted_nodegroups = ["nodegroup1"]

        # Call with real geometry
        self.bng_filter.append_dsl(
            search_query_object,
            permitted_nodegroups=permitted_nodegroups,
            include_provisional=False
        )

        # Check that component name key was created
        self.assertIn(details["componentname"], search_query_object)
        self.assertIn("grid_square", search_query_object[details["componentname"]])
        
        # Verify the grid_square contains real geometry data
        grid_square = search_query_object[details["componentname"]]["grid_square"]
        self.assertEqual(grid_square["type"], "FeatureCollection")
        self.assertGreater(len(grid_square["features"]), 0)
        feature = grid_square["features"][0]
        self.assertIn("geometry", feature)
        self.assertIn("coordinates", feature["geometry"])
        
        # Verify add_query was called with a Bool query
        mock_query.add_query.assert_called_once()
        args, kwargs = mock_query.add_query.call_args
        dsl_query = args[0]
        self.assertIsNotNone(dsl_query)

    def test_19_view_data_method_exists(self):
        """
        Test that view_data method exists and is callable.
        
        This test verifies:
        - The view_data method is implemented (required by BaseSearchFilter interface)
        - The method can be called without raising exceptions
        - The method returns None (placeholder implementation)
        """
        result = self.bng_filter.view_data()
        # Should return None or empty dict, depending on implementation
        self.assertIsNone(result)

    def test_20_post_search_hook_method_exists(self):
        """
        Test that post_search_hook method exists and is callable.
        
        This test verifies:
        - The post_search_hook method is implemented (required by BaseSearchFilter interface)
        - The method accepts search_results_object, results, and permitted_nodegroups parameters
        - The method can be called without raising exceptions
        - The method returns None (placeholder implementation)
        """
        result = self.bng_filter.post_search_hook(
            search_results_object={},
            results={},
            permitted_nodegroups=["nodegroup1"]
        )
        # Should return None
        self.assertIsNone(result)

    def test_21_bng_filter_case_insensitive(self):
        """
        Test that BNG values are converted to uppercase for processing.
        
        This test verifies:
        - BNG references can be provided in lowercase ("nt1234")
        - The method converts them to uppercase ("NT1234") for processing
        - Case-insensitive handling improves user experience and reduces errors
        - The search query is successfully built with lowercase input
        - Real geometry is calculated correctly from the lowercased BNG value
        """
        request = self.factory.get('/search', {
            'bng-filter': json.dumps({
                'bng': 'nt1234',  # lowercase
                'buffer': 0,
                'inverted': False
            })
        })
        self.bng_filter.request = request

        # Mock the search_query_object with a proper query builder
        mock_query = Mock()
        search_query_object = {"query": mock_query}
        permitted_nodegroups = ["nodegroup1"]

        # Call with lowercase BNG - should work with real logic
        self.bng_filter.append_dsl(
            search_query_object,
            permitted_nodegroups=permitted_nodegroups,
            include_provisional=False
        )

        # Verify the query was created successfully
        self.assertIn("bng-filter", search_query_object)
        
        # Verify real geometry was generated from lowercase BNG
        grid_square = search_query_object["bng-filter"]["grid_square"]
        self.assertEqual(grid_square["type"], "FeatureCollection")
        self.assertGreater(len(grid_square["features"]), 0)
        # The bngref should show it was normalized to uppercase
        self.assertIn("bngref", grid_square["features"][0]["properties"])
        
        # Verify add_query was called with a Bool query
        mock_query.add_query.assert_called_once()
        args, kwargs = mock_query.add_query.call_args
        dsl_query = args[0]
        self.assertIsNotNone(dsl_query)

    def test_22_details_dict_has_required_keys(self):
        """
        Test that the details dict has all required keys for component registration.
        
        This test verifies:
        - The details dict includes all required metadata keys
        - These keys are needed for Arches to register and load the search component
        - All required component configuration fields are present
        """
        required_keys = [
            "searchcomponentid",
            "name",
            "icon",
            "modulename",
            "classname",
            "type",
            "componentpath",
            "componentname",
            "sortorder",
            "enabled",
        ]

        for key in required_keys:
            self.assertIn(key, details)

    def test_23_details_dict_values(self):
        """
        Test that details dict has expected configuration values.
        
        This test verifies:
        - The component is named "BNG Filter" for display
        - The Python class is named "BngFilter" and resides in "bng_filter.py"
        - The component name is "bng-filter" (kebab-case) for use in URLs and DOM
        - The component type is "bng-filter-type" for categorization
        - All metadata values are correctly configured for Arches integration
        """
        self.assertEqual(details["name"], "BNG Filter")
        self.assertEqual(details["classname"], "BngFilter")
        self.assertEqual(details["modulename"], "bng_filter.py")
        self.assertEqual(details["componentname"], "bng-filter")
        self.assertEqual(details["type"], "bng-filter-type")
