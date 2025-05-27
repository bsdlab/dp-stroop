import serial
import yaml
from dareplane_utils.general.time import sleep_s
from pylsl import StreamInfo, StreamOutlet

from stroop_task.utils.logging import logger


def utf8_write(port, data: int) -> int:
    """
    Converts integer data into a UTF-8 byte string
    and writes it to the specified serial port.

    Parameters
    ----------
    port : serial.Serial
        The serial port object to which the data will be written.
    data : int
        The integer data to be written to the serial port.

    Returns
    -------
    int
        The number of bytes written to the serial port.
    """
    ret = port.write(bytes(chr(data), encoding="utf8"))
    return ret


def port_writer(port, data: list[int] | int, pulsewidth: float = 0.01) -> int:
    """
    Writes data to a serial port with a specified pulse width.

    This function is typically used for writing to the BrainVision trigger box.
    It writes the actual data to the port, waits for the specified pulse width,
    and then writes a zero byte to the port.

    Parameters
    ----------
    port : serial.Serial
        The serial port object to which the data will be written.
    data : list[int] | int
        The data to be written to the serial port. Can be a single integer or a list of integers.
    pulsewidth : float, optional
        The duration in seconds to wait between writing the actual data and the zero byte.
        Default is 0.01 seconds.

    Returns
    -------
    int
        The number of bytes written to the serial port.
    """
    data = [data] if isinstance(data, int) else data
    ret = port.write(data)
    sleep_s(pulsewidth)
    port.write([0])

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
        """
        Initializes the MarkerWriter object for interacting with the serial port
        provided by the BV TriggerBox and an LSL marker stream.

        Parameters
        ----------
        write_to_serial : bool, optional
            Flag to indicate whether to write to the serial port. Default is True.
        write_to_lsl : bool, optional
            Flag to indicate whether to write to the LSL stream. Default is True.
        write_to_logger : bool, optional
            Flag to indicate whether to log the written data. Default is False.
        serial_port : str, optional
            The serial port to which the trigger box is connected. This should be
            the serial number of the trigger box as can be read under Windows hardware manager.
            Default is "COM4".
        utf8_encoded : bool, optional
            Flag to indicate whether the data should be UTF-8 encoded before writing to the serial port.
            Default is True.

        Attributes
        ----------
        write_to_logger : bool
            Flag to indicate whether to log the written data.
        write_to_lsl : bool
            Flag to indicate whether to write to the LSL stream.
        write_to_serial : bool
            Flag to indicate whether to write to the serial port.
        port : serial.Serial or None
            The serial port object to which the data will be written, if `write_to_serial` is True.
        serial_writer : function
            The function used to write data to the serial port. This will be `utf8_write` if `utf8_encoded`
            is True, otherwise it will be `port_writer`.
        stream_info : StreamInfo or None
            The LSL stream info object, if `write_to_lsl` is True.
        stream_outlet : StreamOutlet or None
            The LSL stream outlet object, if `write_to_lsl` is True.

        Examples
        --------
        >>> marker_writer = MarkerWriter(serial_port="COM3", utf8_encoded=False)
        >>> marker_writer.write(data=123, lsl_marker="Test Marker")
        1
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
    """
    Creates and returns a MarkerWriter instance configured with parameters from a YAML file and additional keyword arguments.

    This function loads configuration settings from a YAML file located at "./configs/marker_writer.yaml".
    It then updates these settings with any additional keyword arguments provided. Finally, it initializes
    and returns a MarkerWriter instance using the combined configuration.

    Parameters
    ----------
    **kwargs : dict
        Additional keyword arguments to override or supplement the settings loaded from the YAML file.

    Returns
    -------
    MarkerWriter
        An instance of MarkerWriter configured with the combined settings from the YAML file and the keyword arguments.

    Notes
    -----
    The YAML file should contain a dictionary of configuration settings that can be passed to the MarkerWriter constructor.
    Any settings provided in the keyword arguments will override the corresponding settings in the YAML file.

    Examples
    --------
    >>> writer = get_marker_writer(serial_port="COM3", utf8_encoded=False)
    >>> writer.write(data=123, lsl_marker="Test Marker")
    1
    """
    mrk_cfg = yaml.safe_load(open("./configs/marker_writer.yaml"))
    mrk_cfg.update(**kwargs)
    mw = MarkerWriter(**mrk_cfg)
    return mw
