from hydromt_fiat.fiat import FiatModel
from hydromt.log import setuplog
from hydromt.config import configread
from pathlib import Path
import pytest
import shutil
import geopandas as gpd

EXAMPLEDIR = Path().absolute() / "local_test_database"
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
                        [-80.0808, 32.7005],
                        [-79.8756, 32.8561],
                        [-79.8756, 32.7005],
                        [-80.0808, 32.8561],
                        [-80.0808, 32.7005],
                    ]
                ],
                "type": "Polygon",
            },
        }
    ],
}

_cases = {
    "Test_SVI_exposure": {
        "data_catalogue": DATADIR / "hydromt_fiat_catalog_USA.yml",
        "folder": "Test_SVI",
        "region": _region,
        "configuration": { 
            "setup_global_settings": {"crs": "epsg:4326"
            },
            "setup_output": {
                "output_dir": "output","output_csv_name": "output.csv","output_vector_name": "spatial.gpkg"
            },
            "setup_vulnerability": {
                "vulnerability_fn": "hazus_vulnerability_curves",
                "vulnerability_identifiers_and_linking_fn": ".\\examples\\data\\vulnerability_test_file_input.csv",
                "functions_mean": "default",
                "functions_max": ["AGR1"],
                "unit": "feet",
            },
            "setup_exposure_vector": {
                    "asset_locations": "NSI",
                    "occupancy_type": "NSI",
                    "max_potential_damage": "NSI",
                    "ground_floor_height": 1,
                    "ground_floor_height_unit": "ft",
            },
            "setup_social_vulnerability_index": {
                "census_key": "495a349ce22bdb1294b378fb199e4f27e57471a9","codebook_fn":"social_vulnerability","state_abbreviation":"SC","blockgroup_fn":"blockgroup_shp_data"
            },


                    }
            }
        }



@pytest.mark.parametrize("case", list(_cases.keys()))
# @pytest.mark.skip(reason="Needs to be updated")
def test_SVI_exposure(case):
    # Read model in examples folder.
    root = EXAMPLEDIR.joinpath(_cases[case]["folder"])
    if root.exists():
        shutil.rmtree(root)
    logger = setuplog("hydromt_fiat", log_level=10)
    data_libs = EXAMPLEDIR.joinpath(_cases[case]["data_catalogue"])
    hyfm = FiatModel(root=root, mode="w", data_libs=data_libs, logger=logger)

    # Now we will add data from the user to the data catalog.
    to_add = {
        "blockgroup_shp_data": {
            "path": str(EXAMPLEDIR /"Social_Vulnerability/tl_2022_45_bg.shp"),
            "data_type": "GeoDataFrame",
            "driver": "vector",
            "crs": 4326,
            "category": "social_vulnerability",
        }
    }

    region = gpd.GeoDataFrame.from_features(_cases[case]["region"])

    hyfm.data_catalog.from_dict(to_add)
    hyfm.build(region={"geom": region}, opt=_cases[case]["configuration"])

    assert hyfm
    print("hi")
