import serial
import yaml
from dareplane_utils.general.time import sleep_s
from pylsl import StreamInfo, StreamOutlet
from yaml import Mark

from stroop_task.utils.logging import logger

utf8_encoded: True  # if True,  `serial.write(bytes(chr(data), encoding="utf8"))` will be used to write to the serial port (used for Maastricht trigger box)


def utf8_write(port, data: int) -> int:
    """Used e.g. for writing to the custom trigger box in Maastricht"""
    ret = port.write(bytes(chr(data), encoding="utf8"))
    return ret


def port_writer(port, data: list[int] | int, pulsewidth: float = 0.01) -> int:
    """Used e.g. for writing to the BrainVision trigger box"""
    data = [data] if isinstance(data, int) else data
    port.write([0])
    sleep_s(pulsewidth)
    ret = port.write(data)

    return ret


class MarkerWriter(object):
    """Class for interacting with the virtual serial
    port provided by the BV TriggerBox and an LSL marker stream
    """

    def __init__(
        self,
        write_to_serial: bool = True,
        write_to_lsl: bool = True,
        write_to_logger: bool = False,
        serial_port: str = "COM4",
        utf8_encoded: bool = True,
    ):
        """Open the port at the given serial_port

        Parameters
        ----------

        serial_port : str
            Serial number of the trigger box as can be read under windows hw manager
        pulsewidth : float
            Seconds to sleep between base and final write to the PPort

        """

        self.write_to_logger = write_to_logger
        self.write_to_lsl = write_to_lsl
        self.write_to_serial = write_to_serial

        if self.write_to_serial:
            self.port = serial.Serial(serial_port)
            self.serial_writer = utf8_write if utf8_encoded else write_to_serial

        if self.write_to_lsl:
            self.stream_info = StreamInfo(
                name="StroopParadigmMarkerStream",
                type="Markers",
                channel_count=1,
                nominal_srate=0,  # irregular stream
                channel_format="string",
                source_id="StroopParadigmMarkerStream",
            )
            self.stream_outlet = StreamOutlet(self.stream_info)

    def write(self, data, lsl_marker: str | None = None) -> int:
        """
        For this paradigm the writer will have the potential for separate markers for LSL and the parallel port

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
            number of bytes written to the serial port if self.serial_writer is defined

        """
        ret = 0

        if lsl_marker is not None and self.write_to_lsl:
            lsl_marker = lsl_marker or str(data)
            # Send to LSL Outlet
            logger.debug(f"Pushing {lsl_marker=}")
            self.stream_outlet.push_sample([lsl_marker])

        if self.write_to_serial:
            ret = self.serial_writer(self.port, data)

        if self.write_to_logger:
            logger.info(f"MarkerWriter writes: {data}")

        return ret

    def __del__(self):
        """Destructor to close the port"""
        print("Closing serial port connection")
        if self.write_to_serial and self.port is not None:
            self.port.close()


def get_marker_writer(**kwargs) -> MarkerWriter:
    mrk_cfg = yaml.safe_load(open("./configs/marker_writer.yaml"))
    mrk_cfg.update(**kwargs)
    mw = MarkerWriter(**mrk_cfg)
    return mw
