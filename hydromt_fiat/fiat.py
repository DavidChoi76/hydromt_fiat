"""Implement fiat model class"""

from hydromt.models.model_grid import GridModel
from hydromt_fiat.workflows.exposure_vector import ExposureVector
import logging
from configparser import ConfigParser
import geopandas as gpd
import hydromt
from hydromt.cli.cli_utils import parse_config
from shapely.geometry import box
from typing import Union


from . import DATADIR

__all__ = ["FiatModel"]

_logger = logging.getLogger(__name__)


class FiatModel(GridModel):
    """General and basic API for the FIAT model in hydroMT."""

    _NAME = "fiat"
    _CONF = "fiat_configuration.ini"
    _GEOMS = {}  # FIXME Mapping from hydromt names to model specific names
    _MAPS = {}  # FIXME Mapping from hydromt names to model specific names
    _FOLDERS = ["hazard", "exposure", "vulnerability", "output"]
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

    def setup_basemaps(
        self,
        region,
        **kwargs,
    ):
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

    def setup_exposure_vector(
        self,
        asset_locations: str,
        occupancy_type: str,
        max_potential_damage: str,
        ground_floor_height: Union[int, float, str, None],
        ground_flood_height_unit: str,
    ) -> None:
        ev = ExposureVector(self.data_catalog, self.region)

        if asset_locations == occupancy_type == max_potential_damage:
            # The source for the asset locations, occupancy type and maximum potential
            # damage is the same, use one source to create the exposure data.
            ev.setup_from_single_source(asset_locations)

        # Add: linking damage functions to assets

    def setup_exposure_raster(self):
        NotImplemented

    def setup_vulnerability(self):
        NotImplemented

    def setup_hazard(self, map_fn):
        NotImplemented

    def setup_social_vulnerability_index(self):
        NotImplemented

    def read(self):
        """Method to read the complete model schematization and configuration from file."""
        self.logger.info(f"Reading model data from {self.root}")
        self.read_config()
        self.read_grid()
        self.read_geoms()

    def _configread(self, fn):
        """Parse fiat_configuration.ini to dict."""

        # Read and parse the fiat_configuration.ini.
        opt = parse_config(fn)

        # Store the general information.
        config = opt["setup_config"]

        # Set the paths.  # FIXME: how to do this more elegantly?
        # config["hazard_dp"] = self.root.joinpath("hazard")
        # config["exposure_dp"] = self.root.joinpath("exposure")
        # config["vulnerability_dp"] = self.root.joinpath("vulnerability")
        # config["output_dp"] = self.root.joinpath("output")

        # Store the hazard information.
        config["hazard"] = {}
        for hazard_dict in [opt[key] for key in opt.keys() if "hazard" in key]:
            hazard_dict.update(
                {"map_fn": config["hazard_dp"].joinpath(hazard_dict["map_fn"])}
            )
            if hazard_dict["map_type"] not in config["hazard"].keys():
                config["hazard"][hazard_dict["map_type"]] = {
                    hazard_dict["map_fn"].stem: hazard_dict,
                }
            else:
                config["hazard"][hazard_dict["map_type"]].update(
                    {
                        hazard_dict["map_fn"].stem: hazard_dict,
                    }
                )

        # Store the exposure information.
        config["exposure"] = opt["setup_exposure"]

        return config

    def write(self):
        """Method to write the complete model schematization and configuration to file."""

        self.logger.info(f"Writing model data to {self.root}")
        if self.config:  # try to read default if not yet set
            self.write_config()
        if self._staticmaps:
            self.write_grid()
        if self._staticgeoms:
            self.write_geoms()

    def _configwrite(self, fn):
        """Write config to Delft-FIAT configuration toml file."""
        # TODO: change function to new Delft-FIAT configuration toml file.
        parser = ConfigParser()

        # Store the general information.
        parser["setup_config"] = {
            "case": str(self.config.get("case")),
            "strategy": str(self.config.get("strategy")),
            "scenario": str(self.config.get("scenario")),
            "year": str(self.config.get("year")),
            "country": str(self.get_config("country")),
            "hazard_type": str(self.config.get("hazard_type")),
            "output_unit": str(self.config.get("output_unit")),
            # "hazard_dp": str(self.config.get("hazard_dp").name),
            # "exposure_dp": str(self.config.get("exposure_dp").name),
            # "vulnerability_dp": str(self.config.get("vulnerability_dp").name),
            # "output_dp": str(self.config.get("output_dp").name),
            "category_output": str(self.config.get("category_output")),
            "total_output": str(self.config.get("total_output")),
            "risk_output": str(self.config.get("risk_output")),
            "map_output": str(self.config.get("map_output")),
        }

        # # Save the configuration file.
        # with open(self.root.joinpath(self._CONF), "w") as config:
        #     parser.write(config)
