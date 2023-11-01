from enum import Enum
from typing_extensions import Optional, TypedDict, Union, List

from pydantic import BaseModel


class ExtractionMethod(str, Enum):
    centroid = "centroid"
    area = "area"


class Units(str, Enum):
    m = "m"
    ft = "ft"


class Category(str, Enum):
    exposure = "exposure"
    hazard = "hazard"
    vulnerability = "vulnerability"


class Driver(str, Enum):
    vector = "vector"
    raster = "raster"
    xlsx = "xlsx"


class DataType(str, Enum):
    RasterDataset = "RasterDataset"
    GeoDataFrame = "GeoDataFrame"
    GeoDataset = "GeoDataset"
    DataFrame = "DataFrame"


class Meta(TypedDict):
    category: Category


class DataCatalogEntry(BaseModel):
    path: str
    data_type: DataType
    driver: Driver
    crs: Optional[Union[str, int]]
    translation_fn: Optional[str]
    meta: Meta


class GlobalSettings(BaseModel):
    crs: Union[str, int]


class OutputSettings(BaseModel):
    output_dir: str
    output_csv_name: str
    output_vector_name: str


class VulnerabilitySettings(BaseModel):
    vulnerability_fn: str
    vulnerability_identifiers_and_linking_fn: str
    unit: Units
    functions_mean: Union[str, list]
    functions_max: Union[str, list, None]
    step_size: Union[float, None]


class ExposureBuildingsSettings(BaseModel):
    asset_locations: str
    occupancy_type: str
    max_potential_damage: str
    ground_floor_height: str
    unit: Units
    extraction_method: ExtractionMethod
    damage_types : Union[List[str], None]


class RoadVulnerabilitySettings(BaseModel):
    threshold_value: float
    min_hazard_value: float
    max_hazard_value: float
    step_hazard_value: float
    vertical_unit: Units


class ExposureRoadsSettings(BaseModel):
    roads_fn: str
    road_types: List[str]
    road_damage: str
    unit: Units


class AggregationAreaSettings(BaseModel):
    aggregation_area_fn: str
    attribute_names: str
    label_names: str


class ConfigYaml(BaseModel):
    setup_global_settings: GlobalSettings
    setup_output: OutputSettings
    setup_vulnerability: VulnerabilitySettings
    setup_exposure_buildings: ExposureBuildingsSettings
    setup_road_vulnerability: RoadVulnerabilitySettings
    setup_exposure_roads: ExposureRoadsSettings
    setup_aggregation_areas: AggregationAreaSettings
