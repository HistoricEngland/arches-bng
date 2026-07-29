from django.db import migrations, models
from django.utils.translation import gettext as _
import json


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("models", "9945_file_thumbnail_bin_file_thumbnail_text"),
    ]

    run_before = [
        ("models", "9946_alter_notification_context"),
    ]

    def add_functions(apps, schema_editor):
        Function = apps.get_model("models", "Function")

        if not Function.objects.filter(functionid="0434df8d-b98a-4b41-9a0a-68cd9214ad73").exists():
            Function.objects.update_or_create(
                name="BNG Point to GeoJSON",
                functiontype="node",
                modulename="bngpoint_to_geojson_function.py",
                description="Pushes the geometry from a BNG Point node to a related GeoJSON node",
                defaultconfig={
                    "bng_node": "",
                    "geojson_node": "",
                    "bng_nodegroup": "",
                    "geojson_nodegroup": "",
                    "triggering_nodegroups": [],
                },
                classname="BNGPointToGeoJSON",
                component="views/components/functions/bngpoint-to-geojson-function",
                functionid="0434df8d-b98a-4b41-9a0a-68cd9214ad73",
            )

        if not Function.objects.filter(functionid="d9a01773-6092-4cad-b331-ae725ae8fa88").exists():
            Function.objects.update_or_create(
                name="GeoJSON to BNG Point",
                functiontype="node",
                modulename="geojson_to_bngpoint_function",
                description="Pushes the geometry from a GeoJSON node's centroid to a related BNG Point node",
                defaultconfig={
                    "geojson_input_node": "",
                    "bng_output_node": "",
                    "geojson_input_nodegroup": "",
                    "bng_output_nodegroup": "",
                    "triggering_nodegroups": [],
                },
                classname="GeoJSONToBNGPoint",
                component="views/components/functions/geojson-to-bngpoint-function",
                functionid="d9a01773-6092-4cad-b331-ae725ae8fa88",
            )

    def add_widgets(apps, schema_editor):
        Widget = apps.get_model("models", "Widget")

        if not Widget.objects.filter(pk="bcae8e90-09f7-4ae3-906b-7c7bb71a6ddf").exists():
            Widget.objects.update_or_create(
                widgetid="bcae8e90-09f7-4ae3-906b-7c7bb71a6ddf",
                name="bngpoint",
                component="views/components/widgets/bngpoint",
                defaultconfig={"placeholder": "Enter the centre point map reference of the resource."},
                helptext=None,
                datatype="bngcentrepoint",
            )

    def add_datatypes(apps, schema_editor):
        Datatype = apps.get_model("models", "DDataType")
        Widget = apps.get_model("models", "Widget")

        bngpoint = Widget.objects.get(pk="bcae8e90-09f7-4ae3-906b-7c7bb71a6ddf")

        if not Datatype.objects.filter(datatype="bngcentrepoint").exists():
            Datatype.objects.update_or_create(
                datatype="bngcentrepoint",
                iconclass="fa fa-location-arrow",
                modulename="bngcentrepoint.py",
                classname="BNGCentreDataType",
                defaultwidget=bngpoint,
                defaultconfig=None,
                configcomponent="views/components/datatypes/bngcentrepoint",
                configname="bngcentrepoint-datatype-config",
                isgeometric=False,
                issearchable=True,
            )

    def add_search_components(apps, schema_editor):
        SearchComponent = apps.get_model("models", "SearchComponent")

        # Create or get the BNG Filter component
        bng_filter, created = SearchComponent.objects.get_or_create(
            searchcomponentid="25ca3536-9eb4-4fd5-b2a5-badfd9a266de",
            defaults={
                "name": "BNG Filter",
                "icon": "fa fa-compass",
                "modulename": "bng_filter.py",
                "classname": "BngFilter",
                "type": "bng-filter-type",
                "componentpath": "views/components/search/bng-filter",
                "componentname": "bng-filter",
            }
        )
        

    def remove_functions(apps, schema_editor):
        Function = apps.get_model("models", "Function")

        for fn in Function.objects.filter(
            pk__in=[
                "0434df8d-b98a-4b41-9a0a-68cd9214ad73",
                "d9a01773-6092-4cad-b331-ae725ae8fa88",
            ]
        ):
            fn.delete()

    def remove_search_components(apps, schema_editor):
        SearchComponent = apps.get_model("models", "SearchComponent")

        for search_component in SearchComponent.objects.filter(
            pk__in=[
                "25ca3536-9eb4-4fd5-b2a5-badfd9a266de",
            ]
        ):
            search_component.delete()
        

    operations = [
        migrations.RunPython(add_functions, remove_functions),
        migrations.RunPython(add_widgets, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(add_datatypes, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(add_search_components, remove_search_components),
    ]