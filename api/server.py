from dareplane_utils.default_server.server import DefaultServer
from fire import Fire

# from stroop_task.main import run_block_subprocess
from stroop_task.main_psychopy import run_block_subprocess
from stroop_task.utils.logging import logger


def main(port: int = 8080, ip: str = "127.0.0.1", loglevel: int = 30):
    # Implement primary commands here

    logger.setLevel(loglevel)

    pcommand_map = {"RUN": run_block_subprocess}

    logger.debug("Pcommands setup")

    server = DefaultServer(
        port,
        ip=ip,
        pcommand_map=pcommand_map,
        name="stroop_paradigm",
        logger=logger,
    )

    # initialize to start the socket
    server.init_server()
    # start processing of the server
    server.start_listening()

    return 0


if __name__ == "__main__":
    Fire(main)
