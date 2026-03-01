

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
import pandas as pd


def plot_surface_points_3d(
    df: pd.DataFrame,
    *,
    title: str | None = None,
    ax=None,
    point_size: int = 8,
    alpha: float = 0.7,
):
    """
    Plot implied volatility surface points in 3D.

    Expects DataFrame with columns:
    - bucket (moneyness bucket, numeric)
    - tenor (string bucket like 1W, 1M, etc.)
    - iv (implied volatility)
    """

    # If surface is pivoted (tenor as index), convert to long format
    if "tenor" not in df.columns:
        df = (
            df.reset_index()
            .melt(id_vars="tenor", var_name="bucket", value_name="iv")
            .dropna(subset=["iv"])
    )
    if df.empty:
        raise ValueError("Surface DataFrame is empty")

    if ax is None:
        fig = plt.figure(figsize=(7, 5))
        ax = fig.add_subplot(111, projection="3d")

    # Convert tenor labels to numeric positions for plotting
    tenor_order = ["1D", "1W", "1M", "3M", "6M", "1Y"]
    tenor_map = {t: i for i, t in enumerate(tenor_order)}

    df_plot = df.copy()
    df_plot["tenor_num"] = df_plot["tenor"].map(tenor_map)

    ax.scatter(
        df_plot["bucket"],
        df_plot["tenor_num"],
        df_plot["iv"],
        s=point_size,
        alpha=alpha,
    )

    ax.set_xlabel("Moneyness (K / S)")
    ax.set_ylabel("Tenor")
    ax.set_yticks(range(len(tenor_order)))
    ax.set_yticklabels(tenor_order)
    ax.set_zlabel("Implied Vol")

    if title:
        ax.set_title(title)

    return ax