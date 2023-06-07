from hydromt_fiat.fiat import FiatModel
from hydromt.config import configread
from hydromt.log import setuplog
from pathlib import Path
import pytest
import shutil

EXAMPLEDIR = Path(
    "P:/11207949-dhs-phaseii-floodadapt/Model-builder/Delft-FIAT/local_test_database"
)

_cases = {
    "integration": {
        "data_catalogue": EXAMPLEDIR / "fiat_catalog.yml",
        "dir": "test_hazard_integration",
        "ini": EXAMPLEDIR / "test_hazard_unique.ini",
    },
}


@pytest.mark.parametrize("case", list(_cases.keys()))
def test_hazard(case):
    # Read model in examples folder.
    root = EXAMPLEDIR.joinpath(_cases[case]["dir"])
    if root.exists:
        shutil.rmtree(root)

    logger = setuplog("hydromt_fiat", log_level=10)
    data_catalog_yml = str(_cases[case]["data_catalogue"])

    fm = FiatModel(root=root, mode="w", data_libs=[data_catalog_yml], logger=logger)

    region = fm.data_catalog.get_geodataframe("region", variables=None)
    opt = configread(_cases[case]["ini"])
    fm.build(region={"geom": region}, opt=opt)
    fm.write()
