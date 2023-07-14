"""Implement fiat model class"""

import csv
import glob
import logging
import os
from os.path import basename, join
from pathlib import Path
from typing import List, Optional, Union

import geopandas as gpd
import hydromt
import pandas as pd
from hydromt.models.model_grid import GridModel
from hydromt_sfincs import SfincsModel
from shapely.geometry import box

from . import DATADIR
from .config import Config
from .workflows.exposure_vector import ExposureVector
from .workflows.hazard import *
from .workflows.social_vulnerability_index import SocialVulnerabilityIndex
from .workflows.vulnerability import Vulnerability

__all__ = ["FiatModel"]

_logger = logging.getLogger(__name__)


class FiatModel(GridModel):
    """General and basic API for the FIAT model in hydroMT."""

    _NAME = "fiat"
    _CONF = "fiat_configuration.ini"
    _GEOMS = {}  # FIXME Mapping from hydromt names to model specific names
    _MAPS = {}  # FIXME Mapping from hydromt names to model specific names
    _FOLDERS = ["hazard", "exposure", "vulnerability", "output"]
    _CLI_ARGS = {"region": "setup_basemaps"}
    _DATADIR = DATADIR

    def __init__(
        self,
        root=None,
        mode="w",
        config_fn=None,
        data_libs=None,
        logger=_logger,
    ):
        super().__init__(
            root=root,
            mode=mode,
            config_fn=config_fn,
            data_libs=data_libs,
            logger=logger,
        )
        self._tables = dict()  # Dictionary of tables to write
        self.exposure = None
        self.vulnerability = None
        self.vulnerability_metadata = list()

    def setup_global_settings(self, crs: str):
        """Setup Delft-FIAT global settings.

        Parameters
        ----------
        crs : str
            The CRS of the model.
        """
        self.set_config("global.crs", crs)

    def setup_output(
        self,
        output_dir: str = "output",
        output_csv_name: str = "output.csv",
        output_vector_name: Union[str, List[str]] = "spatial.gpkg",
    ) -> None:
        """Setup Delft-FIAT output folder and files.

        Parameters
        ----------
        output_dir : str, optional
            The name of the output directory, by default "output".
        output_csv_name : str, optional
            The name of the output csv file, by default "output.csv".
        output_vector_name : Union[str, List[str]], optional
            The name of the output vector file, by default "spatial.gpkg".
        """
        self.set_config("output.path", output_dir)
        self.set_config("output.csv.name", output_csv_name)
        if isinstance(output_vector_name, str):
            output_vector_name = [output_vector_name]
        for i, name in enumerate(output_vector_name):
            self.set_config(f"output.geom.name{str(i+1)}", name)

    def setup_basemaps(
        self,
        region,
        **kwargs,
    ):
        # FIXME Mario will update this function according to the one in Habitat
        """Define the model domain that is used to clip the raster layers.

        Adds model layer:

        * **region** geom: A geometry with the nomenclature 'region'.

        Parameters
        ----------
        region: dict
            Dictionary describing region of interest, e.g. {'bbox': [xmin, ymin, xmax, ymax]}. See :py:meth:`~hydromt.workflows.parse_region()` for all options.
        """

        kind, region = hydromt.workflows.parse_region(region, logger=self.logger)
        if kind == "bbox":
            geom = gpd.GeoDataFrame(geometry=[box(*region["bbox"])], crs=4326)
        elif kind == "grid":
            geom = region["grid"].raster.box
        elif kind == "geom":
            geom = region["geom"]
        else:
            raise ValueError(
                f"Unknown region kind {kind} for FIAT, expected one of ['bbox', 'grid', 'geom']."
            )

        # Set the model region geometry (to be accessed through the shortcut self.region).
        self.set_geoms(geom, "region")

        # Set the region crs
        if geom.crs:
            self.region.set_crs(geom.crs)
        else:
            self.region.set_crs(4326)

    def setup_vulnerability(
        self,
        vulnerability_fn: Union[str, Path],
        vulnerability_identifiers_and_linking_fn: Union[str, Path],
        unit: str,
        functions_mean: Union[str, List[str], None] = "default",
        functions_max: Union[str, List[str], None] = None,
        step_size: Optional[float] = None,
    ) -> None:
        """Setup the vulnerability curves from various possible inputs.

        Parameters
        ----------
        vulnerability_fn : Union[str, Path]
            The (relative) path or ID from the data catalog to the source of the
            vulnerability functions.
        vulnerability_identifiers_and_linking_fn : Union[str, Path]
            The (relative) path to the table that links the vulnerability functions and
            exposure categories.
        unit : str
            The unit of the vulnerability functions.
        functions_mean : Union[str, List[str], None], optional
            The name(s) of the vulnerability functions that should use the mean hazard
            value when using the area extraction method, by default "default" (this
            means that all vulnerability functions are using mean).
        functions_max : Union[str, List[str], None], optional
            The name(s) of the vulnerability functions that should use the maximum
            hazard value when using the area extraction method, by default None (this
            means that all vulnerability functions are using mean).
        """

        # Read the vulnerability data
        df_vulnerability = self.data_catalog.get_dataframe(vulnerability_fn)

        # Read the vulnerability linking table
        vf_ids_and_linking_df = self.data_catalog.get_dataframe(
            vulnerability_identifiers_and_linking_fn
        )

        # Process the vulnerability data
        self.vulnerability = Vulnerability(
            unit,
            self.logger,
        )

        # Depending on what the input is, another function is chosen to generate the
        # vulnerability curves file for Delft-FIAT.
        self.vulnerability.get_vulnerability_functions_from_one_file(
            df_source=df_vulnerability,
            df_identifiers_linking=vf_ids_and_linking_df,
        )

        # Set the area extraction method for the vulnerability curves
        self.vulnerability.set_area_extraction_methods(
            functions_mean=functions_mean, functions_max=functions_max
        )

        # Add the vulnerability curves to tables property
        df, self.vulnerability_metadata = self.vulnerability.get_table_and_metadata()
        self.set_tables(df=df, name="vulnerability_curves")

        # Also add the identifiers
        self.set_tables(df=vf_ids_and_linking_df, name="vulnerability_identifiers")

        # Update config
        self.set_config(
            "vulnerability.file", "./vulnerability/vulnerability_curves.csv"
        )

        if step_size:
            self.set_config("vulnerability.step_size", step_size)

    def setup_exposure_vector(
        self,
        asset_locations: Union[str, Path],
        occupancy_type: Union[str, Path],
        max_potential_damage: Union[str, Path],
        ground_floor_height: Union[int, float, str, Path, None],
        ground_floor_height_unit: str,
        occupancy_type_field: Union[str, None] = None,
        extraction_method: str = "centroid",
    ) -> None:
        """Setup vector exposure data for Delft-FIAT.

        Parameters
        ----------
        asset_locations : Union[str, Path]
            The path to the vector data (points or polygons) that can be used for the
            asset locations.
        occupancy_type : Union[str, Path]
            The path to the data that can be used for the occupancy type.
        max_potential_damage : Union[str, Path]
            The path to the data that can be used for the maximum potential damage.
        ground_floor_height : Union[int, float, str, Path None]
            Either a number (int or float), to give all assets the same ground floor
            height or a path to the data that can be used to add the ground floor
            height to the assets.
        ground_floor_height_unit : str
            The unit of the ground_floor_height
        occupancy_type_field : Union[str, None], optional
            The name of the field in the occupancy type data that contains the
            occupancy type, by default None (this means that the occupancy type data
            only contains one column with the occupancy type).
        extraction_method : str, optional
            The method that should be used to extract the hazard values from the
            hazard maps, by default "centroid".
        """
        self.exposure = ExposureVector(self.data_catalog, self.logger, self.region)

        if asset_locations == occupancy_type == max_potential_damage:
            # The source for the asset locations, occupancy type and maximum potential
            # damage is the same, use one source to create the exposure data.
            self.exposure.setup_from_single_source(
                asset_locations, ground_floor_height, extraction_method
            )
        else:
            # The source for the asset locations, occupancy type and maximum potential
            # damage is different, use three sources to create the exposure data.
            self.exposure.setup_from_multiple_sources(
                asset_locations,
                occupancy_type,
                max_potential_damage,
                ground_floor_height,
                extraction_method,
                occupancy_type_field,
            )

        # Link the damage functions to assets
        try:
            assert not self.vf_ids_and_linking_df.empty
        except AssertionError:
            logging.error(
                "Please call the 'setup_vulnerability' function before "
                "the 'setup_exposure_vector' function. Error message: {e}"
            )
        self.exposure.link_exposure_vulnerability(self.vf_ids_and_linking_df)
        self.exposure.check_required_columns()

        # Add to tables
        self.set_tables(df=self.exposure.exposure_db, name="exposure")

        # Add to the geoms
        self.set_geoms(
            geom=self.exposure.get_geom_gdf(
                self._tables["exposure"], self.exposure.crs
            ),
            name="exposure",
        )

        # Update config
        self.set_config("exposure.geom.csv", "./exposure/exposure.csv")
        self.set_config("exposure.geom.crs", self.exposure.crs)
        self.set_config(
            "exposure.geom.file1", "./exposure/exposure.gpkg"
        )  # TODO: update if we have more than one file

    def setup_exposure_raster(self):
        """Setup raster exposure data for Delft-FIAT.
        This function will be implemented at a later stage.
        """
        NotImplemented

    def setup_hazard(
        self,
        map_fn: Union[str, Path, list[str], list[Path]],
        map_type: Union[str, list[str]],
        rp: Union[int, list[int], None] = None,
        crs: Union[int, str, list[int], list[str], None] = None,
        nodata: Union[int, list[int], None] = None,
        var: Union[str, list[str], None] = None,
        chunks: Union[int, str, list[int]] = "auto",
        name_catalog: Union[str, None] = "flood_maps",
        hazard_type: str = "flooding",
        risk_output: bool = False,
    ) -> None:
        """Set up hazard maps. This component integrates multiple checks for the maps

        Parameters
        ----------
        map_fn : Union[str, Path, list[str], list[Path]]
            The data catalog key or list of keys from where to retrieve the
            hazard maps. This can also be a path or list of paths to take files
            directly from a local database.
        map_type : Union[str, list[str]]
            The data type of each map speficied in map_fn. In case a single
            map type applies for all the elements a single string can be provided.
        rp : Union[int, list[int], None], optional.
            The return period (rp) type of each map speficied in map_fn in case a
            risk output is required. If the rp is not provided and risk
            output is required the workflow will try to retrieve the rp from the
            files's name, by default None.
        crs : Union[int, str, list[int], list[str], None], optional
            The projection (crs) required in EPSG code of each of the maps provided. In
            case a single crs applies for all the elements a single value can be
            provided as code or string (e.g. "EPSG:4326"). If not provided, then the crs
            will be taken from orginal maps metadata, by default None.
        nodata : Union[int, list[int], None], optional
            The no data values in the rasters arrays. In case a single no data applies
            for all the elements a single value can be provided as integer, by default
            None.
        var : Union[str, list[str], None], optional
            The name of the variable to be selected in case a netCDF file is provided
            as input, by default None.
        chunks : Union[int, str, list[int]], optional
            The chuck region per map. In case a single no data applies for all the
            elements a single value can be provided as integer. If "auto"is provided
            the auto setting will be provided by default "auto"
        name_catalog : str, optional
            Name of the data catalog to take the hazard maps from, by default "flood_maps"
        hazard_type : str, optional
            Type of hazard to be studied, by default "flooding"
        risk_output : bool, optional
            The parameter that defines if a risk analysis is required, by default False
        """
        # check parameters types and size, and existance of provided files of maps

        params = check_parameters_type(map_fn, map_type, rp, crs, nodata, var, chunks)
        check_parameters_size(params)
        check_files(params, self.root)

        rp_list = []
        map_name_lst = []

        # retrieve maps information from parameters and datacatalog
        # load maps in memory and check them and save the with st_map function
        for idx, da_map_fn in enumerate(params["map_fn_lst"]):
            da_map_fn, da_name, da_type = read_floodmaps(params, da_map_fn, idx)

            # load flood maps to memory
            # da = load_floodmaps(self.data_catalog, self.region,da_map_fn,da_name,name_catalog)
            # reading from path
            if isinstance(da_map_fn, Path):
                if da_map_fn.stem == "sfincs_map":
                    sfincs_root = os.path.dirname(da_map_fn)
                    sfincs_model = SfincsModel(sfincs_root, mode="r")
                    sfincs_model.read_results()
                    # save sfincs map as GeoTIFF
                    # result_list = list(sfincs_model.results.keys())
                    # sfincs_model.write_raster("results.zsmax", compress="LZW")
                    da = sfincs_model.results["zsmax"]
                    # da = da.squeeze('timemax').drop('timemax')
                    da = da.isel(timemax=0).drop("timemax")

                else:
                    if not self.region.empty:
                        # da = self.data_catalog.get_rasterdataset(
                        #     da_map_fn, geom=self.region
                        # )
                        da = self.data_catalog.get_rasterdataset(da_map_fn)
                    else:
                        da = self.data_catalog.get_rasterdataset(da_map_fn)
            # reading from the datacatalog
            else:
                if not self.region.empty:
                    # da = self.data_catalog.get_rasterdataset(
                    #     name_catalog, variables=da_name, geom=self.region
                    # )
                    da = self.data_catalog.get_rasterdataset(
                        name_catalog, variables=da_name
                    )
                else:
                    da = self.data_catalog.get_rasterdataset(
                        name_catalog, variables=da_name
                    )

            da.encoding["_FillValue"] = None
            da = da.raster.gdal_compliant()

            # check masp projection, null data, and grids
            check_maps_metadata(self.staticmaps, params, da, da_name, idx)

            # check maps return periods
            da_rp = check_maps_rp(params, da, da_name, idx, risk_output)

            # chek if maps are unique
            # TODO: check if providing methods like self.get_config can be used
            # TODO: create a new funtion to check uniqueness trhough files names
            # check_maps_uniquenes(self.get_config,self.staticmaps,params,da,da_map_fn,da_name,da_type,da_rp,idx)

            rp_list.append(da_rp)
            map_name_lst.append(da_name)

            self.set_maps(da, da_name)
            post = f"(rp {da_rp})" if risk_output else ""
            self.logger.info(f"Added {hazard_type} hazard map: {da_name} {post}")

        check_map_uniqueness(map_name_lst)
        # in case risk_output is required maps are put in a netcdf with a raster with
        # an extra dimension 'rp' accounting for return period
        # select first risk maps
        if risk_output:
            list_keys = list(self.maps.keys())
            first_map = self.maps[list_keys[0]].rename("risk_datarray")
            list_keys.pop(0)

            # add additional risk maps
            for idx, x in enumerate(list_keys):
                key_name = list_keys[idx]
                layer = self.maps[key_name]
                first_map = xr.concat([first_map, layer], dim="rp")

            # convert to a dataset to be able to write attributes when writing the maps
            # in the ouput folders. If datarray is provided attributes will not be
            # shown in the output netcdf dataset
            da = first_map.to_dataset(name="risk_maps")
            da.attrs = {
                "returnperiod": list(rp_list),
                "type": params["map_type_lst"],
                "name": map_name_lst,
                "Analysis": "risk",
            }
            # load merged map into self.maps
            self.set_maps(da)
            list_maps = list(self.maps.keys())

            # erase individual maps from self.maps keeping the merged map
            for item in list_maps[:-1]:
                self.maps.pop(item)

            self.set_config("hazard.return_periods", rp_list)

        # the metadata of the hazard maps is saved in the configuration toml files
        # this component was modified to provided the element [0] od the list
        # in case multiple maps are required then remove [0]
        self.set_config(
            "hazard.file",
            [
                str(Path("hazard") / (hazard_map + ".nc"))
                for hazard_map in self.maps.keys()
            ][0],
        )
        self.set_config(
            "hazard.crs",
            [
                "EPSG:" + str((self.maps[hazard_map].rio.crs.to_epsg()))
                for hazard_map in self.maps.keys()
            ][0],
        )

        self.set_config(
            "hazard.elevation_reference", "dem" if da_type == "water_depth" else "datum"
        )

        # Set the configurations for a multiband netcdf
        self.set_config(
            "hazard.multiband.subset",
            [(self.maps[hazard_map].name) for hazard_map in self.maps.keys()][0],
        )

        self.set_config(
            "hazard.multiband.var_as_band",
            risk_output,
        )

        self.set_config(
            "hazard.risk",
            risk_output,
        )

    def setup_social_vulnerability_index(
        self,
        census_key: str,
        codebook_fn: Union[str, Path],
        state_abbreviation: str,
        user_dataset_fn: str = None,
        blockgroup_fn: str = None,
    ):
        """Setup the social vulnerability index for the vector exposure data for
        Delft-FIAT.

        Parameters
        ----------
        path_dataset : str
            The path to a predefined dataset
        census_key : str
            The user's unique Census key that they got from the census.gov website
            (https://api.census.gov/data/key_signup.html) to be able to download the
            Census data
        path : Union[str, Path]
            The path to the codebook excel
        state_abbreviation : str
            The abbreviation of the US state one would like to use in the analysis
        """

        # Create SVI object
        svi = SocialVulnerabilityIndex(self.data_catalog, self.logger)

        # Call functionalities of SVI
        # svi.read_dataset(user_dataset_fn)
        svi.set_up_census_key(census_key)
        svi.variable_code_csv_to_pd_df(codebook_fn)
        svi.set_up_download_codes()
        svi.set_up_state_code(state_abbreviation)
        svi.download_census_data()
        svi.rename_census_data("Census_code_withE", "Census_variable_name")
        svi.identify_no_data()
        svi.check_nan_variable_columns("Census_variable_name", "Indicator_code")
        svi.check_zeroes_variable_rows()
        translation_variable_to_indicator = svi.create_indicator_groups(
            "Census_variable_name", "Indicator_code"
        )
        svi.processing_svi_data(translation_variable_to_indicator)
        svi.normalization_svi_data()
        svi.domain_scores()
        svi.composite_scores()
        svi.match_geo_ID()
        svi.load_shp_geom(blockgroup_fn)
        svi.merge_svi_data_shp()

        # store the relevant tables coming out of the social vulnerability module
        self.set_tables(df=svi.pd_domain_scores_z, name="social_vulnerability_scores")
        # self.set_tables(df=svi.excluded_regions, name="social_vulnerability_nodataregions")

        # Check if the exposure data exists
        if self.exposure:
            # Link the SVI score to the exposure data
            self._tables["exposure"]  # pd dataframe
            self.geoms["exposure"]  # gpd dataframe
            self._tables["exposure"].sort_values("Object ID")
            self.geoms["exposure"].sort_values("Object ID")
            exposure_geoms = self._tables["exposure"].merge(
                self.geoms["exposure"], on="Object ID"
            )
            exposure_geoms_gpd = gpd.GeoDataFrame(exposure_geoms)
            svi_exp_joined = gpd.sjoin(
                exposure_geoms_gpd, svi.svi_data_shp, how="inner", op="within"
            )
            svi_exp_joined = svi_exp_joined.drop(columns="geometry")
            svi_exp_joined = pd.DataFrame(svi_exp_joined)
            self._tables["exposure"] = svi_exp_joined

        # exposure opnieuw opslaan in self._tables

        # TODO: geometries toevoegen aan de dataset met API
        # we now use the shape download function by the census, the user needs to download their own shape data. They can download this from: https://www.census.gov/cgi-bin/geo/shapefiles/index.php
        # #wfs python get request -> geometries

        # this link can be used: https://github.com/datamade/census

    # Update functions
    def update_all(self):
        self.logger.info("Updating all data objects...")
        # self.update_config()
        self.update_tables()
        self.update_geoms()
        # self.update_maps()

    def update_config(self):
        NotImplemented

    def update_tables(self):
        # Update the exposure data tables
        if self.exposure:
            self.set_tables(df=self.exposure.exposure_db, name="exposure")

        # Update the vulnerability data tables
        if self.vulnerability:
            (
                df,
                self.vulnerability_metadata,
            ) = self.vulnerability.get_table_and_metadata()
            self.set_tables(df=df, name="vulnerability_curves")

        # TODO: Also add the vulnerability identifiers table?

    def update_geoms(self):
        # Update the exposure data geoms
        if self.exposure and "exposure" in self._tables:
            for geom in self.exposure.exposure_geoms:
                self.set_geoms(geom=geom, name="exposure")

        if not self.region.empty:
            self.set_geoms(self.region, "region")

    def update_maps(self):
        NotImplemented

    # I/O
    def read(self):
        """Method to read the complete model schematization and configuration from file."""
        self.logger.info(f"Reading model data from {self.root}")

        # Read the configuration file
        self.read_config(config_fn=str(Path(self.root).joinpath("settings.toml")))

        # TODO: determine if it is required to read the hazard files
        # hazard_maps = self.config["hazard"]["grid_file"]
        # self.read_grid(fn="hazard/{name}.nc")

        # Read the tables exposure and vulnerability
        self.read_tables()

        # Read the geometries
        self.read_geoms()

    def _configread(self, fn):
        """Parse Delft-FIAT configuration toml file to dict."""
        # Read the fiat configuration toml file.
        config = Config()
        return config.load_file(fn)

    def check_path_exists(self, fn):
        """TODO: decide to use this or another function (check_file_exist in py)"""
        path = Path(fn)
        self.logger.debug(f"Reading file {str(path.name)}")
        if not fn.is_file():
            logging.warning(f"File {fn} does not exist!")

    def read_tables(self):
        """Read the model tables for vulnerability and exposure data."""
        if not self._write:
            self._tables = dict()  # start fresh in read-only mode

        self.logger.info("Reading model table files.")

        # Start with vulnerability table
        vulnerability_fn = Path(self.root) / self.get_config("vulnerability.file")
        if Path(vulnerability_fn).is_file():
            self.logger.debug(f"Reading vulnerability table {vulnerability_fn}")
            self.vulnerability = Vulnerability(fn=vulnerability_fn, logger=self.logger)
            (
                self._tables["vulnerability_curves"],
                _,
            ) = self.vulnerability.get_table_and_metadata()
        else:
            logging.warning(f"File {vulnerability_fn} does not exist!")

        # Now with exposure
        exposure_fn = Path(self.root) / self.get_config("exposure.geom.csv")
        if Path(exposure_fn).is_file():
            self.logger.debug(f"Reading exposure table {exposure_fn}")
            self.exposure = ExposureVector(
                crs=self.get_config("exposure.geom.crs"), logger=self.logger
            )
            self.exposure.read_table(exposure_fn)
            self._tables["exposure"] = self.exposure.exposure_db
        else:
            logging.warning(f"File {exposure_fn} does not exist!")

        # If needed read other tables files like vulnerability identifiers
        # Comment if not needed - I usually use os rather than pathlib, change if you prefer
        fns = glob.glob(join(self.root, "*.csv"))
        if len(fns) > 0:
            for fn in fns:
                self.logger.info(f"Reading table {fn}")
                name = basename(fn).split(".")[0]
                tbl = pd.read_csv(fn)
                self.set_tables(tbl, name=name)

    def read_geoms(self):
        """Read the geometries for the exposure data."""
        if self.exposure:
            self.logger.info("Reading exposure geometries.")
            exposure_files = [
                k for k in self.config["exposure"]["geom"].keys() if "file" in k
            ]
            exposure_fn = [
                Path(self.root) / self.get_config(f"exposure.geom.{f}")
                for f in exposure_files
            ]
            self.exposure.read_geoms(exposure_fn)

            exposure_names = [f.stem for f in exposure_fn]
            for name, geom in zip(exposure_names, self.exposure.exposure_geoms):
                self.set_geoms(
                    geom=geom,
                    name=name,
                )

    def write(self):
        """Method to write the complete model schematization and configuration to file."""
        self.update_all()
        self.logger.info(f"Writing model data to {self.root}")

        if self.config:  # try to read default if not yet set
            self.write_config()
        if self.maps:
            self.write_maps(fn="hazard/{name}.nc")
        if self.geoms:
            self.write_geoms(fn="exposure/{name}.gpkg", driver="GPKG")
        if self._tables:
            self.write_tables()

    def write_tables(self) -> None:
        if len(self._tables) == 0:
            self.logger.debug("No table data found, skip writing.")
            return
        self._assert_write_mode

        for name in self._tables.keys():
            # Vulnerability
            if name == "vulnerability_curves":
                # The default location and save settings of the vulnerability curves
                fn = "vulnerability/vulnerability_curves.csv"
                kwargs = {"mode": "a", "index": False}

                # The vulnerability curves are written out differently because of
                # the metadata
                path = Path(self.root) / fn
                with open(path, "w", newline="") as f:
                    writer = csv.writer(f)

                    # First write the metadata
                    for metadata in self.vulnerability_metadata:
                        writer.writerow([metadata])
            # Exposure
            elif name == "exposure":
                # The default location and save settings of the exposure data
                fn = "exposure/exposure.csv"
                kwargs = {"index": False}
            elif name == "vulnerability_identifiers":
                # The default location and save settings of the vulnerability curves
                fn = "vulnerability/vulnerability_identifiers.csv"
                kwargs = dict()
            elif "social_vulnerability" in name:
                fn = f"exposure/{name}.csv"
                kwargs = {"index": False}

            # Other, can also return an error or pass silently
            else:
                fn = f"{name}.csv"
                kwargs = dict()

            # make dir and save file
            self.logger.info(f"Writing model {name} table file to {fn}.")
            path = Path(self.root) / fn
            if not path.parent.is_dir():
                path.parent.mkdir(parents=True)

            if path.name.endswith("csv"):
                self._tables[name].to_csv(path, **kwargs)
            elif path.name.endswith("xlsx"):
                self._tables[name].to_excel(path, **kwargs)

    def _configwrite(self, fn):
        """Write config to Delft-FIAT configuration toml file."""
        # Save the configuration file.
        Config().save(self.config, Path(self.root).joinpath("settings.toml"))

    # FIAT specific attributes and methods
    @property
    def vulnerability_curves(self) -> pd.DataFrame:
        """Returns a dataframe with the damage functions."""
        if "vulnerability_curves" in self._tables:
            vf = self._tables["vulnerability_curves"]
        else:
            vf = pd.DataFrame()
        return vf

    @property
    def vf_ids_and_linking_df(self) -> pd.DataFrame:
        """Returns a dataframe with the vulnerability identifiers and linking."""
        if "vulnerability_identifiers" in self._tables:
            vi = self._tables["vulnerability_identifiers"]
        else:
            vi = pd.DataFrame()
        return vi

    def set_tables(self, df: pd.DataFrame, name: str) -> None:
        """Add <pandas.DataFrame> to the tables variable.

        Parameters
        ----------
        df : pd.DataFrame
            New DataFrame to add
        name : str
            Name of the DataFrame to add
        """
        if not (isinstance(df, pd.DataFrame) or isinstance(df, pd.Series)):
            raise ValueError("df type not recognized, should be pandas.DataFrame.")
        if name in self._tables:
            if not self._write:
                raise IOError(f"Cannot overwrite table {name} in read-only mode")
            elif self._read:
                self.logger.warning(f"Overwriting table: {name}")
        self._tables[name] = df
