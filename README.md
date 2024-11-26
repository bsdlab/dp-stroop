# Stroop task

A simple keyboard based Stroop task implementation for Dareplane using [`pyglet`](https://pyglet.readthedocs.io/en/latest/index.html) and another implementation using [`psychopy`](https://www.psychopy.org/).

## Running the two word version of the stroop task

Make sure the correct python environment is activated and the dependencies are installed.
Then from within this repository run:

```
python -m stroop_task.main_dutch_version_word_below
```

You can provide command line arguments for setting, e.g., `n_trials`:

```
python -m stroop_task.main_dutch_version_word_below --n_trials=60
```
(For this task, `n_trials` should be a multiple of 6 for  proper balancing.)

If you are debugging and do not have the marker box (serial connection at `COM9`) available, run with


```
python -m stroop_task.main_dutch_version_word_below --debug_marker_writer=True
```

## Starting other scripts standalone

To start the task standalone run either of:

##### pyglet

```bash
python -m stroop_task.main
```

##### psychopy

```bash
python -m stroop_task.main_psychopy

```

## Starting the Dareplane server

To start the server standalone (not from within a [`control_room`](https://github.com/bsdlab/dp-control-room)), use:

```bash
python -m api.server
```

Then you should be able to connect via `telnet` on `127.0.0.1 8080` for testing purposes.

