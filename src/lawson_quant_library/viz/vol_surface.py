

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
    - moneyness
    - ttm
    - iv
    """
    if df.empty:
        raise ValueError("Surface DataFrame is empty")

    if ax is None:
        fig = plt.figure(figsize=(7, 5))
        ax = fig.add_subplot(111, projection="3d")

    ax.scatter(
        df["moneyness"],
        df["ttm"],
        df["iv"],
        s=point_size,
        alpha=alpha,
    )

    ax.set_xlabel("Moneyness (K / S)")
    ax.set_ylabel("Tenor (years)")
    ax.set_zlabel("Implied Vol")

    if title:
        ax.set_title(title)

    return ax