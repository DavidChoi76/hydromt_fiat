from hydromt_fiat.fiat import FiatModel
from hydromt.log import setuplog
from pathlib import Path
import pytest
import shutil

EXAMPLEDIR = Path(
    "P:/11207949-dhs-phaseii-floodadapt/Model-builder/Delft-FIAT/local_test_database"
)
DATADIR = Path().absolute() / "hydromt_fiat" / "data"

_cases = {
    "truncate_damage_function": {
        "data_catalogue": DATADIR / "hydromt_fiat_catalog_USA.yml",
        "dir": "test_read",
        "new_root": EXAMPLEDIR / "test_truncate_damage_function",
    },
}


@pytest.mark.parametrize("case", list(_cases.keys()))
def test_truncate_damage_function(case):
    # Read model in examples folder.
    root = EXAMPLEDIR.joinpath(_cases[case]["dir"])
    logger = setuplog("hydromt_fiat", log_level=10)
    data_catalog_yml = str(_cases[case]["data_catalogue"])

    fm = FiatModel(root=root, mode="r", data_libs=[data_catalog_yml], logger=logger)

    fm.read()

    objectids_to_modify = [173, 175, 241, 247, 1012528]
    print(
        fm.exposure.exposure_db.loc[
            fm.exposure.exposure_db["Object ID"].isin(objectids_to_modify),
            "Damage Function: Structure",
        ].unique()
    )
    fm.exposure.truncate_damage_function(
        objectids=objectids_to_modify,
        floodproof_to=2.5,
        damage_function_types=["Structure"],
        vulnerability=fm.vulnerability,
    )

    if _cases[case]["new_root"].exists():
        shutil.rmtree(_cases[case]["new_root"])

    fm.set_root(_cases[case]["new_root"])
    fm.write()
