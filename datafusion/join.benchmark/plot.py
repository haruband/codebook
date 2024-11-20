import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.read_csv(sys.argv[1])

plt.figure(figsize=(10, 8))

axe1 = plt.subplot()
axe2 = axe1.twinx()

g1 = sns.barplot(
    data=df,
    x="target",
    y="runtime",
    palette="pastel",
    ax=axe1,
)
g1.set_xticklabels(g1.get_xticklabels(), rotation=10, size=8)
g1.set_yticklabels(g1.get_yticklabels(), size=8)
g1.set(xlabel=None)
g1.set(ylabel="runtime (seconds)")

g2 = sns.lineplot(
    data=df,
    x="target",
    y="memory",
    marker="o",
    linestyle="dashed",
    color="green",
    ax=axe2,
)
g2.set_yticklabels(g2.get_yticklabels(), size=8)
g2.set(ylabel="memory (gigabytes)")

plt.tight_layout()
# plt.show()
plt.savefig("tpch.png")
