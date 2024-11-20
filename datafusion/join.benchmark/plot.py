import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.read_csv(sys.argv[1])

axe1 = plt.subplot()
axe2 = axe1.twinx()

g1 = sns.barplot(ax=axe1, data=df, x="target", y="runtime", palette="pastel")
g1.set_xticklabels(g1.get_xticklabels(), rotation=45, size=7)
g1.set(xlabel=None)

g2 = sns.lineplot(
    ax=axe2,
    data=df,
    x="target",
    y="memory",
    marker="o",
    linestyle="dashed",
    color="green",
)

plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
