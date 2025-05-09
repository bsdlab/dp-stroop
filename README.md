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

There are two incarnations of the modified Stroop paradigm:

1.  A self-paced version, requesting the user to start each trial by pressing and **holding** the arrow down button. The idea is to also record the response onset marked by the lift-off from the arrow down key. If necessary explain the participant to keep the arrow down key pressed until they made their decission and only then responde according to the instructions on the instruction screen.
1.  A random inter-trial-interval. This will just show the fixation cross for a random time interval (defined by a max and min time - see `configs/task.yaml`).

To run them, use the following:

1. Self-paced

```bash
python -m stroop_task.main --n_trials=6
```

2. Random inter trial interval

```bash
python -m stroop_task.main --n_trials=6 --random_wait=True
```

Note that this is reducing the number of trials to give a quick look-and-feel. The default is 60 trials.
For a list of available CLI parameters, you can use `python -m stroop_task.main --help`

Additionally, a `--focus` flag allows to switch between a `--focus=color` (default) and `--focus==text` version which
is then displaying different instructions on the instruction screen accordingly.

### Running the classical equivalent

There is also an implementation of an equivalent to the classical card based Stroop task, which can be run with:

```bash
python -m stroop_task.main --classical=True --language=german
```

This would start the classical equivalent in German language. The instruction asks the participant to read to color
of the word out loud. And the experimenter is to track how far the participant read within a given time. It is suggested to
print out the color tables, which are available under `./stroop_task/assets/`. Note that the files are generated on first
call to the function. I.e., you might need to trigger a run once to see the `json` e.g. for `classical_list_nstim-60_perc_incongruent-0.33_lang-german.json`. It can also be handy to just take a screenshot of the table and print it for the experimenter to track incorrect words.
The default timeout for the task is set to `45` seconds. But the parameter can be modulated with the `--classic_stroop_time_s` flag, e.g.:

```bash
python -m stroop_task.main --classical=True --classic_stroop_time_s=60   # for 60s timeout
```

**Note**: Regardless of the version of the paradigm, it is always good to run a small familiarization with each participant. This can be done by running the paradigm with a smaller trial number first, e.g., `n_trials=6` before the actual version with a proper amount of repetitions is run.

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
