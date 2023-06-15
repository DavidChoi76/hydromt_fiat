from pathlib import Path
from typing import Any

from hydromt import DataCatalog, config

from hydromt_fiat.api.data_types import ConfigIni
from hydromt_fiat.api.dbs_controller import LocalDatabase
from hydromt_fiat.api.exposure_vm import ExposureViewModel
from hydromt_fiat.api.hazard_vm import HazardViewModel
from hydromt_fiat.api.model_vm import ModelViewModel
from hydromt_fiat.api.vulnerability_vm import VulnerabilityViewModel


class Singleton(object):
    _instance = None

    def __new__(cls, *args: Any, **kwargs: Any):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls)
        return cls._instance


class HydroMtViewModel(Singleton):
    is_initialized: bool = False
    data_catalog: DataCatalog
    database: LocalDatabase

    def __init__(self, database_path: Path, catalog_path: str):
        if not self.__class__.is_initialized:
            HydroMtViewModel.database = LocalDatabase.create_database(database_path)
            HydroMtViewModel.data_catalog = DataCatalog(catalog_path)
            # HydroMtViewModel.database.write(Path(catalog_path))

            self.model_vm = ModelViewModel()
            self.exposure_vm = ExposureViewModel(
                HydroMtViewModel.database, HydroMtViewModel.data_catalog
            )
            self.vulnerability_vm = VulnerabilityViewModel()
            self.hazard_vm = HazardViewModel()
            self.__class__.is_initialized = True

    def clear_database(self):
        # TODO: delete database after hydromt_fiat has run
        ...

    def build_data_catalog(self):
        database_path = self.__class__.database.drive
        self.__class__.data_catalog.to_yml(database_path)

    def build_config_ini(self):
        config_ini = ConfigIni(
            setup_config=self.model_vm.config_model,
            setup_hazard=self.hazard_vm.hazard_model,
            setup_vulnerability=self.vulnerability_vm.vulnerability_model,
            setup_exposure_vector=self.exposure_vm.exposure_model,
        )

        database_path = self.__class__.database.drive
        config.write_ini_config(
            database_path / "config.ini", config_ini.dict(exclude_none=True)
        )


a = HydroMtViewModel(Path(__file__).parent, str(Path(__file__).parent / "test.yml"))
a.build_config_ini()
b = HydroMtViewModel(Path(__file__).parent, str(Path(__file__).parent / "test.yml"))
print(a)
