from hydromt_fiat.fiat import FiatModel
from hydromt.log import setuplog
from hydromt.gis_utils import utm_crs
from pathlib import Path
import pytest
import shutil
import geopandas as gpd
import copy


EXAMPLEDIR = Path(
    "P:/11207949-dhs-phaseii-floodadapt/Model-builder/Delft-FIAT/local_test_database"
)
DATADIR = Path().absolute() / "hydromt_fiat" / "data"

_cases = {
    "update_ground_floor_height": {
        "dir": "test_read",
        "new_root": EXAMPLEDIR / "test_update_ground_floor_height",
        "data_catalog": DATADIR / "hydromt_fiat_catalog_USA.yml",
        "ground_floor_height_file": EXAMPLEDIR
        / "data"
        / "ground_floor_height"
        / "fake_elevation_certificates.gpkg",
        "attribute": "FFE",
        "method": "nearest",
        "max_dist": 50,
    },
}


@pytest.mark.parametrize("case", list(_cases.keys()))
def test_update_ground_floor_height(case):
    # Read model in examples folder.
    root = EXAMPLEDIR.joinpath(_cases[case]["dir"])
    logger = setuplog("hydromt_fiat", log_level=10)

    fm = FiatModel(
        root=root, mode="r", data_libs=[_cases[case]["data_catalog"]], logger=logger
    )
    fm.read()

    original_exposure = copy.deepcopy(fm.exposure.exposure_db)
    unique_gfh_original = original_exposure["Ground Floor Height"].unique()

    fm.exposure.setup_ground_floor_height(
        _cases[case]["ground_floor_height_file"],
        _cases[case]["attribute"],
        _cases[case]["method"],
        _cases[case]["max_dist"]
    )

    # Remove the new root folder if it already exists
    if _cases[case]["new_root"].exists():
        shutil.rmtree(_cases[case]["new_root"])

    # Set the new root and write the model
    fm.set_root(_cases[case]["new_root"])
    fm.write()

    # Check if the new ground floor height is different from the original one
    unique_gfh_new = fm.exposure.exposure_db["Ground Floor Height"].unique()
    assert unique_gfh_original != unique_gfh_new, "The Ground Floor Height is the same"

    # # Check if the Ground Floor Heigh attribute is set correctly
    # ground_floor_height = gpd.read_file(_cases[case]["ground_floor_height_file"])
    # nearest_utm = utm_crs(ground_floor_height.total_bounds)
    # ground_floor_height = ground_floor_height.to_crs(nearest_utm)
    # ground_floor_height.geometry = ground_floor_height.geometry.buffer(_cases[case]["max_dist"])
