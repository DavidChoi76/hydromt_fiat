from hydromt_fiat.fiat import FiatModel
from hydromt.log import setuplog
from pathlib import Path
import pytest
import shutil
import geopandas as gpd

EXAMPLEDIR = Path(
    "P:/11207949-dhs-phaseii-floodadapt/Model-builder/Delft-FIAT/local_test_database"
)
EXAMPLEDIR = Path().absolute() / "examples" / "data" / "setup_exposure_buildings"
DATADIR = Path().absolute() / "hydromt_fiat" / "data"

_region = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "coordinates": [
                    [
                        [-79.92169686568795, 32.768208904171374],
                        [-79.92169686568795, 32.77745096033627],
                        [-79.94881762529997, 32.77745096033627],
                        [-79.94881762529997, 32.768208904171374],
                        [-79.92169686568795, 32.768208904171374],
                    ]
                ],
                "type": "Polygon",
            },
        }
    ],
}
_cases = {
    "vulnerability_and_exposure_NSI": {
        "data_catalogue": DATADIR / "hydromt_fiat_catalog_USA.yml",
        "dir": "test_vulnerability_and_exposure_NSI",
        "configuration": {
            "setup_global_settings": {"crs": "epsg:4326"},
            "setup_output": {
                "output_dir": "output",
                "output_csv_name": "output.csv",
                "output_vector_name": "spatial.gpkg",
            },
            "setup_vulnerability": {
                "vulnerability_fn": "default_vulnerability_curves",
                "vulnerability_identifiers_and_linking_fn": "default_hazus_iwr_linking",
                "functions_mean": "default",
                "functions_max": ["AGR1"],
                "unit": "feet",
                "step_size": 0.1,
            },
            "setup_exposure_buildings": {
                "asset_locations": "NSI",
                "occupancy_type": "NSI",
                "max_potential_damage": "NSI",
                "damage_types": ["structure", "content"],
                "ground_floor_height": "NSI",
                "unit": "ft",
            },
        },
        "region": _region,
    },
    "vulnerability_and_exposure_NSI_SVI": {
        "data_catalogue": DATADIR / "hydromt_fiat_catalog_USA.yml",
        "dir": "test_vulnerability_and_exposure_NSI_SVI",
        "configuration": {
            "setup_global_settings": {"crs": "epsg:4326"},
            "setup_output": {
                "output_dir": "output",
                "output_csv_name": "output.csv",
                "output_vector_name": "spatial.gpkg",
            },
            "setup_vulnerability": {
                "vulnerability_fn": "default_vulnerability_curves",
                "vulnerability_identifiers_and_linking_fn": "default_hazus_iwr_linking",
                "functions_mean": "default",
                "functions_max": ["AGR1"],
                "unit": "feet",
                "step_size": 0.1,
            },
            "setup_exposure_buildings": {
                "asset_locations": "NSI",
                "occupancy_type": "NSI",
                "max_potential_damage": "NSI",
                "damage_types": ["structure", "content"],
                "ground_floor_height": "NSI",
                "unit": "ft",
            },
            "setup_social_vulnerability_index": {
                "census_key": "495a349ce22bdb1294b378fb199e4f27e57471a9",
                "codebook_fn": "social_vulnerability",
                "state_abbreviation": "SC",
                "blockgroup_fn": str(
                    DATADIR
                    / "social_vulnerability"
                    / "test_blockgroup_shp"
                    / "tl_2022_45_bg.shp"
                ),
            },
        },
        "region": _region,
    },
}


@pytest.mark.parametrize("case", list(_cases.keys()))
def test_vulnerability_exposure_NSI(case):
    # Read model in examples folder.
    root = EXAMPLEDIR.joinpath(_cases[case]["dir"])
    if root.exists():
        shutil.rmtree(root)
    data_catalog_yml = str(_cases[case]["data_catalogue"])

    logger = setuplog("hydromt_fiat", log_level=10)

    fm = FiatModel(root=root, mode="w", data_libs=[data_catalog_yml], logger=logger)

    region = gpd.GeoDataFrame.from_features(_cases[case]["region"], crs=4326)
    fm.build(region={"geom": region}, opt=_cases[case]["configuration"])
    fm.write()

    # Check if the exposure data exists
    assert root.joinpath("exposure", "buildings.gpkg").exists()
    assert root.joinpath("exposure", "exposure.csv").exists()
    assert root.joinpath("exposure", "region.gpkg").exists()

    # Check if the vulnerability data exists
    assert root.joinpath("vulnerability", "vulnerability_curves.csv").exists()

    # Check if the hazard folder exists
    assert root.joinpath("hazard").exists()

    # Check if the output data folder exists
    assert root.joinpath("output").exists()
