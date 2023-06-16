from typing import Any

import tomli_w
from hydromt import DataCatalog
from pathlib import Path

from hydromt_fiat.api.data_types import ConfigIni
from hydromt_fiat.api.dbs_controller import LocalDatabase
from hydromt_fiat.api.exposure_vm import ExposureViewModel
from hydromt_fiat.api.hazard_vm import HazardViewModel
from hydromt_fiat.api.model_vm import ModelViewModel
from hydromt_fiat.api.vulnerability_vm import VulnerabilityViewModel
from hydromt_fiat.fiat import FiatModel
from hydromt.log import setuplog


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

    def __init__(
        self, database_path: str, catalog_path: str, hydromt_fiat_path: str = None
    ):
        if not self.__class__.is_initialized:
            database_path = Path(database_path)
            catalog_path = Path(catalog_path)

            HydroMtViewModel.database = LocalDatabase.create_database(database_path)
            HydroMtViewModel.data_catalog = DataCatalog(catalog_path)

            if hydromt_fiat_path is not None:
                logger = setuplog("hydromt_fiat", log_level=10)
                self.fiat_model = FiatModel(
                    data_libs=catalog_path,
                    root=hydromt_fiat_path,
                    mode="w+",
                    logger=logger,
                )

                self.model_vm = ModelViewModel()
                self.exposure_vm = ExposureViewModel(
                    HydroMtViewModel.database, HydroMtViewModel.data_catalog, logger
                )
                self.vulnerability_vm = VulnerabilityViewModel(
                    HydroMtViewModel.database, HydroMtViewModel.data_catalog, logger
                )
                self.hazard_vm = HazardViewModel()

            self.__class__.is_initialized = True

    def clear_database(self):
        # TODO: delete database after hydromt_fiat has run
        ...

    def save_data_catalog(self):
        database_path = self.__class__.database.drive
        self.__class__.data_catalog.to_yml(database_path / "data_catalog.yml")

    def build_config_ini(self):
        config_ini = ConfigIni(
            setup_config=self.model_vm.config_model,
            setup_hazard=self.hazard_vm.hazard_model,
            setup_vulnerability=self.vulnerability_vm.vulnerability_model,
            setup_exposure_vector=self.exposure_vm.exposure_model,
        )

        database_path = self.__class__.database.drive

        with open(database_path / "config.ini", "wb") as f:
            tomli_w.dump(config_ini.dict(exclude_none=True), f)
