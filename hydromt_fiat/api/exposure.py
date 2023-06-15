from typing import Dict, Optional

from hydromt import DataCatalog

from hydromt_fiat.interface.database import IDatabase

from .data_types import (
    Category,
    DataCatalogEntry,
    ExposureVectorIni,
    ExtractionMethod,
    Units,
)


class ExposureViewModel:
    def __init__(self, database: IDatabase, data_catalog: DataCatalog):
        self.exposure_model = ExposureVectorIni(
            asset_locations=" ",
            occupancy_type="",
            max_potential_damage=-999,
            ground_floor_height=-999,
            gfh_units=Units.feet,
            extraction_method=ExtractionMethod.centroid.value,
        )
        self.database: IDatabase = database
        self.data_catalog: DataCatalog = data_catalog

    def create_interest_area(self, **kwargs: str):
        filepath = kwargs.get("filepath")

        data_entry = {
            "area_of_interest": DataCatalogEntry(
                path=filepath,
                data_type="GeoDataFrame",
                driver="vector",
                crs=4326,
                meta={"category": Category.exposure.value},
            ).dict()  # type: ignore
        }

        self.data_catalog.from_dict(data_entry)  # type: ignore

    def create_location_source(
        self, input_source: str, fiat_key_maps: Optional[Dict[str, str]] = None
    ):
        if input_source == "NSI":
            # NSI is already defined in the data catalog
            # Add NSI to the configuration file

            ...
        elif input_source == "file" and fiat_key_maps is not None:
            # maybe save fiat_key_maps file in database
            # make calls to backend to derive file meta info such as crs, data type and driver
            crs: str = "4326"
            # save keymaps to database

            entry = DataCatalogEntry(
                path=input_source,
                data_type="GeoDataFrame",
                driver="vector",
                crs=crs,
                translation_fn="",  # the path to the fiat_key_maps file
                meta={"category": Category.exposure.value},
            )
            # make backend calls to create translation file with fiat_key_maps
            print(entry)
        # write to data catalog

    def create_extraction_map(self, *args):
        # if no exceptions, then self.exposure_model.extraction_method = args[0]
        # else if
        # make backend call to api with arguments to set extraction method per object:
        # create first with default method. Then get uploaded or drawn area and merge with default methid
        # save file to database
        # change self.exposure_model.extraction_method to file
        ...
        # change self.exposure_model.extraction_method to file
        ...
        ...
        ...
