import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.read_csv(sys.argv[1])

plt.figure(figsize=(10, 8))

g1 = sns.lineplot(
    data=df,
    x="seconds",
    y="size",
    marker="o",
    linestyle="dashed",
    color="green",
)
g1.set_yticklabels(g1.get_yticklabels(), size=8)
g1.set(ylabel="memory (gigabytes)")

sns.lineplot(
    data=df,
    x="seconds",
    y="used",
    marker="X",
    linestyle="dashed",
    color="sienna",
)

plt.tight_layout()
plt.show()
# plt.savefig("spark.png")
