from typing import Dict, Optional, Union

from hydromt import DataCatalog

from hydromt_fiat.workflows.exposure_vector import ExposureVector
from hydromt_fiat.api.utils import make_catalog_entry
from hydromt_fiat.interface.database import IDatabase
import logging

from .data_types import (
    Category,
    DataCatalogEntry,
    DataType,
    Driver,
    ExposureBuildingsIni,
    ExtractionMethod,
    Units,
)


class ExposureViewModel:
    def __init__(
        self, database: IDatabase, data_catalog: DataCatalog, logger: logging.Logger
    ):
        self.exposure_model = ExposureBuildingsIni(
            asset_locations="",
            occupancy_type="",
            max_potential_damage=-999,
            ground_floor_height=-999,
            unit=Units.m.value,
            extraction_method=ExtractionMethod.centroid.value,
            damage_types=["structure", "content"]
        )
        self.database: IDatabase = database
        self.data_catalog: DataCatalog = data_catalog
        self.logger: logging.Logger = logger
        self.exposure: ExposureVector = None

    def create_interest_area(self, **kwargs: str):
        fpath = kwargs.get("fpath")
        # self.database.write(fpath)  # Why is this done?

        catalog_entry = make_catalog_entry(
            name="area_of_interest",
            path=fpath,
            data_type=DataType.GeoDataFrame,
            driver=Driver.vector,
            crs=4326,
            meta={"category": Category.exposure},
        )

        self.data_catalog.from_dict(catalog_entry)  # type: ignore

    def set_asset_locations_source(
        self,
        input_source: str,
        fiat_key_maps: Optional[Dict[str, str]] = None,
        crs: Union[str, int] = None,
    ):
        if input_source == "NSI":
            # NSI is already defined in the data catalog
            self.exposure_model.asset_locations = input_source
            self.exposure_model.occupancy_type = input_source
            self.exposure_model.max_potential_damage = input_source
            self.exposure_model.ground_floor_height = 1  # TODO: make flexible
            self.exposure_model.unit = Units.ft.value  # TODO: make flexible

            # Download NSI from the database
            region = self.data_catalog.get_geodataframe("area_of_interest")
            self.exposure = ExposureVector(
                data_catalog=self.data_catalog,
                logger=self.logger,
                region=region,
                crs=crs,
            )

            self.exposure.setup_buildings_from_single_source(
                input_source,
                self.exposure_model.ground_floor_height,
                "centroid",  # TODO: MAKE FLEXIBLE
            )
            primary_object_types = (
                self.exposure.exposure_db["Primary Object Type"].unique().tolist()
            )
            secondary_object_types = (
                self.exposure.exposure_db["Secondary Object Type"].unique().tolist()
            )
            gdf = self.exposure.get_full_gdf(self.exposure.exposure_db)

            return (
                gdf,
                primary_object_types,
                secondary_object_types,
            )

        elif input_source == "file" and fiat_key_maps is not None:
            # maybe save fiat_key_maps file in database
            # make calls to backend to derive file meta info such as crs, data type and driver
            crs: str = "4326"
            # save keymaps to database

            catalog_entry = DataCatalogEntry(
                path=input_source,
                data_type="GeoDataFrame",
                driver="vector",
                crs=crs,
                translation_fn="",  # the path to the fiat_key_maps file
                meta={"category": Category.exposure},
            )
            # make backend calls to create translation file with fiat_key_maps
            print(catalog_entry)
        # write to data catalog

    def setup_extraction_method(self, extraction_method):
        if self.exposure:
            self.exposure.setup_extraction_method(extraction_method)
