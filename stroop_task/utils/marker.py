import serial
from pylsl import StreamInfo, StreamOutlet

from stroop_task.utils.clock import sleep_s
from stroop_task.utils.logging import logger


class MarkerWriter(object):
    """Class for interacting with the virtual serial
    port provided by the BV TriggerBox and an LSL marker stream
    """

    def __init__(
        self,
        serial_nr: str | None = None,
        pulsewidth: float = 0.01,
        debug: bool = False,
    ):
        """Open the port at the given serial_nr

        Parameters
        ----------

        serial_nr : str
            Serial number of the trigger box as can be read under windows hw manager
        pulsewidth : float
            Seconds to sleep between base and final write to the PPort

        """
        try:
            self.port = serial.Serial(serial_nr)
            if not self.port.isOpen():
                self.port.open()
        except Exception as e:  # if trigger box is not available at given serial_nr
            if self.debug:
                print(f"Starting DUMMY as connection with {serial_nr=} failed")
                self.create_dummy(serial_nr)
            else:
                raise e

        self.pulsewidth = pulsewidth

        self.stream_info = StreamInfo(
            name="StroopParadigmMarkerStream",
            type="Markers",
            channel_count=1,
            nominal_srate=0,  # irregular stream
            channel_format="string",
            source_id="myStroopParadigmMarkerStream",
        )
        self.stream_outlet = StreamOutlet(self.stream_info)
        self.logger: logger | None = logger

        # have different writer instances for different hardware triggers
        self.serial_write = self.bv_trigger_box_write

    def write(self, data, lsl_marker: str | None = None) -> int:
        """

        Parameters
        ----------

        data:  list of int(s), byte or bytearray
            data to be written to the serial port

        lsl_marker: str | None
            if None, the data is written to the serial port and the LSL stream
            otherwise the `lsl_marker` is written to the LSL stream

        Returns
        -------
        byteswritten : int
            number of bytes written

        """
        lsl_marker = lsl_marker or str(data)
        # Send to LSL Outlet
        self.logger.debug(f"Pushing to lsl {lsl_marker}")
        self.stream_outlet.push_sample([lsl_marker])
        if self.logger:
            self.logger.info(f"Pushing sample {data}")

        ret = self.serial_write(data)

        return ret

    def utf8_write(self, data: int) -> int:
        ret = self.port.write(bytes(chr(data), encoding="utf8"))
        return ret

    def bv_trigger_box_write(self, data) -> int:

        self.port.write([0])
        sleep_s(self.pulsewidth)
        ret = self.port.write(data)

        return ret

    def __del__(self):
        """Destructor to close the port"""
        print("Closing serial port connection")
        if self.port is not None:
            self.port.close()

    def create_dummy(self, serial_nr: str):
        """Initialize a dummy version - used for testing"""
        print(
            "-" * 80
            + "\n\nInitializing DUMMY VPPORT\nSetup for regular VPPORT at"
            + f" at {serial_nr} failed \n No device present?\n"
            + "-" * 80
        )

        self.port = None
        self.write = self.dummy_write

    def dummy_write(self, data, lsl_marker: str | None = None):
        """Overwriting the write to pp"""
        print(f"PPort would write data: {data}")

        lsl_marker = lsl_marker or str(data)
        # Send to LSL Outlet
        self.logger.debug(f"Pushing to lsl {lsl_marker}")
        self.stream_outlet.push_sample([lsl_marker])
        if self.logger:
            self.logger.info(f"Pushing sample {data}")
