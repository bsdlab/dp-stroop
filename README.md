# Stroop task

A simple keyboard based Stroop task implementation for Dareplane using [`pyglet`](https://pyglet.readthedocs.io/en/latest/index.html) and another implementation using [`psychopy`](https://www.psychopy.org/).

## Starting standalone

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

## Todo

- [ ] decide how to persist the behavioral performance (correct/incorrect decisions)
