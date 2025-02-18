from enum import Enum
from typing import Optional, Union

import pint
import pint_pandas

ureg = pint.get_application_registry()
pint_pandas.PintType.ureg = ureg

class BaseUnit(Enum):
    """Unified class for handling unit conversion, replacing WaterUnit and StorageUnit."""
    CUBIC_METER = 'm3'
    LITER = 'L'
    MILLIMETER = 'mm'
    METER = 'm'

    @staticmethod
    def convert(value: float, from_unit: Union['BaseUnit', str],
                to_unit: Union['BaseUnit', str], area: Optional[float] = None) -> float:
        """Convert between units using cubic meters as the base unit."""
        if isinstance(from_unit, str):
            from_unit = BaseUnit(from_unit)
        if isinstance(to_unit, str):
            to_unit = BaseUnit(to_unit)

        if from_unit == to_unit:
            return value

        if area is None and from_unit in [BaseUnit.MILLIMETER, BaseUnit.METER]:
            raise ValueError("Area is required for conversions involving depth units")

        match from_unit:
            case BaseUnit.CUBIC_METER:
                value_m3 = value
            case BaseUnit.LITER:
                value_m3 = value * 0.001
            case BaseUnit.MILLIMETER:
                value_m3 = value * area * 0.001
            case BaseUnit.METER:
                value_m3 = value * area
            case _:
                raise ValueError(f"Unsupported unit: {from_unit}")

        match to_unit:
            case BaseUnit.CUBIC_METER:
                return value_m3
            case BaseUnit.LITER:
                return value_m3 * 1000
            case BaseUnit.MILLIMETER:
                return (value_m3 / area) * 1000
            case BaseUnit.METER:
                return value_m3 / area
            case _:
                raise ValueError(f"Unsupported conversion target: {to_unit}")
