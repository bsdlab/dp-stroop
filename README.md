# Dareplane Stroop Task

A Stroop task implementation for keyboard based execution following the design by [Zysset et al. 2001](https://www.sciencedirect.com/science/article/abs/pii/S1053811900906657).

## Installation

The paradigm has been tested with `python 3.12` but should also run under older python versions as it is relatively light weight on requirements.
You can check your python version with `python --version` from the terminal.

Start by cloning this repository:

```bash
git clone git@github.com:bsdlab/dp-stroop.git
cd dp-stroop
```

#### Virtual environment

Optionally, create a virtual environment

```bash
python -m venv stroop_venv
```

then activate with

```bash
# for Unix
source ./stroop_venv/bin/activate

# for powershell on Window
.\stroop_venv\Scripts\activate.ps

# for cmd on Window
.\stroop_venv\Scripts\activate.bat

```

#### Requirements

Install requirements with pip

```bash
pip install -U pip
pip install -r requirements.txt
```

## Running the paradigm

There are two incarnations of the paradigm:

1.  A self-paced version, requesting the user to start each trial by pressing the arrow down button.
1.  A random inter-trial-interval

To run them, use the following:

1. Self-paced

```bash
python -m stroop_task.main --n_trials=6
```

1. Self-paced

```bash
python -m stroop_task.main --n_trials=6
```

Note that this is reducing the number of trials to give a quick look-and-feel. The default is 60 trials.
For a list of available CLI parameters, you can use `python -m stroop_task.main --help`

## Configuration

The configurations can be found under `./configs` and are sorted as follows:

- `\<language\>.yaml`, e.g., `english.yaml`: Contain the language specific fields, such as the color words and the instruction text.
- `gui.yaml`: Parameters regarding the `pyglet` window, such as size, font_size, fullscreen etc.
  - Note: If the configured screensize does not match your screen, the text might appear of center, depending on your pyglet version. Make adjustments or run it in `fullscreen: False` mode.
- `logging.yaml`: Parameters for the used logger, also including the log file
- `marker_writer.yaml`: Parameters for how markers should be send and written, concerning e.g. the LSL stream or markers sent to serial port.
- `task.yaml`: Parameters concerning the actual tasks, such as timing parameters or marker values

<!-- ## Starting the Dareplane server -->
<!---->
<!-- To start the server standalone (not from within a [`control_room`](https://github.com/bsdlab/dp-control-room)), use: -->
<!---->
<!-- ```bash -->
<!-- python -m api.server -->
<!-- ``` -->
<!---->
<!-- Then you should be able to connect via `telnet` on `127.0.0.1 8080` for testing purposes. -->
<!---->
