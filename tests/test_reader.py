from hydromt_fiat.fiat import FiatModel
from hydromt.log import setuplog
from pathlib import Path
import pytest

from hydromt_fiat.workflows.exposure_vector import ExposureVector
from hydromt_fiat.workflows.vulnerability import Vulnerability


EXAMPLEDIR = Path(
    "P:/11207949-dhs-phaseii-floodadapt/Model-builder/Delft-FIAT/local_test_database"
)

_cases = {
    "read": {
        "data_catalogue": EXAMPLEDIR / "fiat_catalog.yml",
        "dir": "test_read",
    },
}


@pytest.mark.parametrize("case", list(_cases.keys()))
def test_read_fiat_config(case):
    # Read model in examples folder.
    root = EXAMPLEDIR.joinpath(_cases[case]["dir"])
    logger = setuplog("hydromt_fiat", log_level=10)
    data_catalog_yml = str(_cases[case]["data_catalogue"])

    fm = FiatModel(root=root, mode="r", data_libs=[data_catalog_yml], logger=logger)
    fm.read()

    # Check if the exposure object exists
    assert isinstance(fm.exposure, ExposureVector)

    # Check if the exposure database exists
    assert not fm.exposure.exposure_db.empty

    # Check if the vulnerability object exists
    assert isinstance(fm.vulnerability, Vulnerability)

    # Check if the vulnerability functions exist
    assert len(fm.vulnerability.functions) > 0