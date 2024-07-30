import time

import pylsl

streams = pylsl.resolve_byprop("name", "StroopParadigmMarkerStream")
inlet = pylsl.StreamInlet(streams[0])

while True:
    time.sleep(0.1)
    sample, timestamp = inlet.pull_sample()
    if sample:
        print(sample, timestamp)
