from .tests.display import DisplayTest
from .tests.buttons import ButtonsTest
from .tests.rfid import RFIDTest
from .tests.light import (
    LightLeftTest,
    LightRightTest,
)
from .tests.leds import LEDsTest
from .tests.sound import SoundTest
from .tests.gyroscope import GyroscopeTest
from .tests.sdcard import SDCardTest
from .tests.rj_sensors import RJSensorsTest
from .tests.rj_motors import RJMotorsTest
from .tests.ads import (
    ADSBatteryTest,
    ADSMotorsTest,
)
from .tests.pca import PCALedsTest
from .tests.ir import (
    IRLedTest,
    RemoteControlTest,
)


TEST_CLASSES = {
    "DISPLAY": DisplayTest,
    "BUTTONS": ButtonsTest,
    "RFID": RFIDTest,
    "LIGHT_LEFT": LightLeftTest,
    "LIGHT_RIGHT": LightRightTest,
    "LEDS": LEDsTest,
    "SOUND": SoundTest,
    "GYROSCOPE": GyroscopeTest,
    "SD_CARD": SDCardTest,
    "RJ_SENSORS": RJSensorsTest,
    "RJ_MOTORS": RJMotorsTest,
    "ADS_BATTERY": ADSBatteryTest,
    "ADS_MOTORS": ADSMotorsTest,
    "PCA_LEDS": PCALedsTest,
    "IR_LED": IRLedTest,
    "REMOTE_CONTROL": RemoteControlTest,
}


PERIPHERAL_NAMES = tuple(
    TEST_CLASSES.keys()
)


def create_test(name):
    cls = TEST_CLASSES.get(
        str(name).upper()
    )

    if cls is None:
        return None

    return cls()
