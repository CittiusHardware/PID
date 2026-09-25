from machine import Pin, I2C
from time import sleep_ms

from ._base import PeripheralTest
from ..config import (
    I2C_ID,
    I2C_SDA,
    I2C_SCL,
    I2C_FREQ,
    RFID_ADDRESS,
    RFID_BLOCK,
)
from ..result import TestResult
from ..i18n import t
from ..ui.display import show_lines


class RFIDTest(PeripheralTest):
    NAME = "RFID"
    LABEL = "RFID"

    def run(self, context=None):
        try:
            from mihuRFID import (
                MihuRFID
            )
        except ImportError:
            try:
                from lib.mihuRFID import (
                    MihuRFID
                )
            except ImportError:
                return (
                    TestResult
                    .failed_result(
                        self.NAME,
                        "mihuRFID library not found.",
                    )
                )

        try:
            i2c = I2C(
                I2C_ID,
                sda=Pin(I2C_SDA),
                scl=Pin(I2C_SCL),
                freq=I2C_FREQ,
            )

            addresses = i2c.scan()

            if RFID_ADDRESS not in addresses:
                return (
                    TestResult
                    .failed_result(
                        self.NAME,
                        "RFID not found at 0x28.",
                        {
                            "i2c": addresses,
                        },
                    )
                )

            rfid = MihuRFID(
                i2c,
                address=RFID_ADDRESS,
                presence_misses=4,
            )

            show_lines([
                t("rfid_test"),
                "",
                t("present_card"),
                "",
                t("waiting"),
            ])

            started = (
                self.deadline_start()
            )

            while not self.timed_out(
                started
            ):
                card = rfid.read_once(
                    block=RFID_BLOCK
                )

                if card is not None:
                    return (
                        TestResult
                        .passed_result(
                            self.NAME,
                            "Card detected.",
                            {
                                "uid": card.get(
                                    "uid_hex"
                                ),
                                "text": card.get(
                                    "text"
                                ),
                                "block": RFID_BLOCK,
                            },
                        )
                    )

                sleep_ms(80)

            return (
                TestResult
                .failed_result(
                    self.NAME,
                    "RFID timeout.",
                )
            )

        except Exception as error:
            return (
                TestResult
                .failed_result(
                    self.NAME,
                    "RFID error.",
                    {
                        "error": str(error),
                    },
                )
            )
