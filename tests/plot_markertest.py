# The aim of the comparison is to understand potential delays / jitter in the
# processing of the keyboard input within the pyglet framework (callbacks).


import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
import pyxdf
from plotly.subplots import make_subplots

data_file = "./data/lslmarker_test.xdf"
data_file = "./data/lslmarker_test_full_speed.xdf"
data_file = "./data/lslmarker_test_240hz.xdf"
data_file = "./data/lslmarker_test_full_speed_with_logger_print.xdf"
data_file = "./data/lslmarker_test_odin_plain.xdf"
data_file = "./data/lslmarker_test_odin_ospeed.xdf"


def xdf_to_dataframe(data_file: str) -> pd.DataFrame:
    xd = pyxdf.load_xdf(data_file)

    snames = [stream["info"]["name"][0] for stream in xd[0]]

    df1 = pd.DataFrame(
        {
            "mrk": [e[0] for e in xd[0][0]["time_series"]],
            "ts": xd[0][0]["time_stamps"],
        }
    )
    df2 = pd.DataFrame(
        {
            "mrk": xd[0][1]["time_series"].reshape(-1)
            if isinstance(xd[0][1]["time_series"], np.ndarray)
            else [e[0] for e in xd[0][1]["time_series"]],
            "ts": xd[0][1]["time_stamps"],
        }
    )

    df1["src"] = snames[0]
    df2["src"] = snames[1]

    df = pd.concat([df1, df2])
    df.loc[df.mrk.isin([1, 2, "RIGHT", "LEFT"]), "mrk"] = df.loc[
        df.mrk.isin([1, 2, "RIGHT", "LEFT"]), "mrk"
    ].map(
        {
            1: "LEFT pressed",
            2: "RIGHT pressed",
            "RIGHT": "RIGHT pressed",
            "LEFT": "LEFT pressed",
        }
    )

    df = df[~df.mrk.str.contains("END")]
    df = df[
        ~df.mrk.str.contains("released")
    ]  # the pyglet was just looking for press
    df.ts -= df.ts.min()

    return df


df = xdf_to_dataframe(data_file)

# time line plot
fig = px.scatter(df, x="ts", y="mrk", color="src")
fig.show()


# Calculate a few statistics
dfk = df[df.src == "Keyboard"]
dfs = df[df.src == "StroopParadigmMarkerStream"]

# the keyboard stream started earlier
dfk = dfk[dfk.ts > dfs.ts.min() - 0.01]  # allow for 10ms dalay

if data_file == "./data/lslmarker_test_full_speed_with_logger_print.xdf":
    # here we just match closest values (check time line scatter for validation)
    idx_dfs = []
    idx_dfk = []
    for i in range(dfk.shape[0]):
        dts = (dfs.ts - dfk.ts.iloc[i]).abs()

        # if there is no dts.ts between current i and i+1 point -> missing record in the pyglet app
        if i < dfk.shape[0] - 1:
            if (dfk.ts.iloc[i + 1] - dfk.ts.iloc[i]) > dts.min():
                if dfk.mrk.iloc[i] == dfs.mrk.iloc[np.argmin(dts)]:
                    idx_dfs.append(np.argmin(dts))
                    idx_dfk.append(i)

        else:
            if dfk.mrk.iloc[i] == dfs.mrk.iloc[np.argmin(dts)]:
                idx_dfs.append(np.argmin(dts))
                idx_dfk.append(i)

    dfk = dfk.iloc[idx_dfk]
    dfs = dfs.iloc[idx_dfs]

dfk.reset_index(drop=True, inplace=True)
dfs.reset_index(drop=True, inplace=True)

assert dfk.shape == dfs.shape
assert (dfk.mrk == dfs.mrk).all()

dm = pd.DataFrame(
    {"mrk": dfk.mrk, "k_ts": dfk.ts, "s_ts": dfs.ts, "dt": dfs.ts - dfk.ts}
)
dm["k_dt_iter"] = dm["k_ts"].diff()
dm["s_dt_iter"] = dm["s_ts"].diff()
dm["dt_iter"] = dm["s_dt_iter"] - dm["k_dt_iter"]


def plot_stats(dm: pd.DataFrame, show: bool = True) -> go.Figure:
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=[
            "StroopParadigm_timestamp - Keyboard_timestamp",
            "Difference reaction to reaction times of consecutive markers",
        ],
    )

    fig.add_histogram(x=dm.dt, row=1, col=1, nbinsx=100, name="dt of marker")
    fig.add_vline(
        dm.dt.quantile(0.95),
        row=1,
        col=1,
        line_width=3,
        line_dash="dash",
        opacity=0.5,
        annotation_text=f"95% quantile<br>dt={dm.dt.quantile(0.95):.4f}",
    )

    fig.add_histogram(
        x=dm.dt_iter,
        row=1,
        col=2,
        nbinsx=100,
        name="jitter StroopParadigm vs Keyboard",
    )
    fig.add_vline(
        dm.dt_iter.quantile(0.95),
        row=1,
        col=2,
        line_width=3,
        line_dash="dash",
        opacity=0.5,
        annotation_text=f"95% quantile<br>dt={dm.dt_iter.quantile(0.95):.4f}",
    )
    fig.add_vline(
        dm.dt_iter.quantile(0.05),
        row=1,
        col=2,
        line_width=3,
        line_dash="dash",
        opacity=0.5,
        annotation_text=f"5% quantile<br>dt={dm.dt_iter.quantile(0.05):.4f}",
    )

    fig = fig.update_xaxes(title_text="dt [s]")
    fig = fig.update_yaxes(title_text="count")
    fig = fig.update_layout(font_size=18)
    fig = fig.update_annotations(font_size=24)
    if show:
        fig.show()
    return fig


fig = plot_stats(dm, show=True)


fig.write_html("./assets/odin_ospeed_lsl_stats.html")
# fig.write_html("./assets/pylet_240Hz_eventloop_lsl_stats.html")
# fig.write_html("./assets/pyglet_run_interval_0_eventloop_lsl_stats.html")
# fig.write_html("./assets/pyglet_run_interval_0_eventloop_lsl_stats_plotting.html")
