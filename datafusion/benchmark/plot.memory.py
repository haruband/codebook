import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

plt.figure(figsize=(10, 8))

for target in sys.argv:
    if target.startswith("datafusion"):
        df = pd.read_csv(target)
        df["allocated"] = df["allocated"] / 1024
        g1 = sns.lineplot(
            data=df,
            x="seconds",
            y="allocated",
            marker="o",
            markersize=4,
            linestyle="solid",
            linewidth=1,
            palette="pastel",
            label=os.path.splitext(target)[0],
        )
    elif target.startswith("spark"):
        df = pd.read_csv(target)
        # df = df[df["seconds"] % 5 == 0]
        df["used"] = df["used"] / 1024 / 1024
        g1 = sns.lineplot(
            data=df,
            x="seconds",
            y="used",
            marker="o",
            markersize=4,
            linestyle="dotted",
            linewidth=1,
            palette="pastel",
            label=os.path.splitext(target)[0],
        )

g1.set_yticklabels(g1.get_yticklabels(), size=8)
g1.set(ylabel="memory (gigabytes)")

plt.tight_layout()
# plt.show()
plt.savefig("memory.png")
