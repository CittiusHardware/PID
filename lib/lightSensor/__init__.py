"""
Pacote educacional lightSensor.

Uso:
    from lightSensor import lux1, lux2, light
"""

from .lightSensor import (
    VERSION,
    LightBus,
    LightSensor,
    LightSensors,
    lightBus,
    light,
    lux1,
    lux2,
    LUX1_ADDRESS,
    LUX2_ADDRESS,
    POWER_DOWN,
    POWER_ON,
    RESET,
    CONTINUOUS_HIGH_RESOLUTION,
    CONTINUOUS_HIGH_RESOLUTION_2,
    CONTINUOUS_LOW_RESOLUTION,
    ONE_TIME_HIGH_RESOLUTION,
    ONE_TIME_HIGH_RESOLUTION_2,
    ONE_TIME_LOW_RESOLUTION,
)

__all__ = (
    "VERSION",
    "LightBus",
    "LightSensor",
    "LightSensors",
    "lightBus",
    "light",
    "lux1",
    "lux2",
    "LUX1_ADDRESS",
    "LUX2_ADDRESS",
    "POWER_DOWN",
    "POWER_ON",
    "RESET",
    "CONTINUOUS_HIGH_RESOLUTION",
    "CONTINUOUS_HIGH_RESOLUTION_2",
    "CONTINUOUS_LOW_RESOLUTION",
    "ONE_TIME_HIGH_RESOLUTION",
    "ONE_TIME_HIGH_RESOLUTION_2",
    "ONE_TIME_LOW_RESOLUTION",
)
