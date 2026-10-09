# /// script
# requires-python = ">=3.11"
# dependencies = ["pylindol", "matplotlib>=3.8"]
# ///
"""Plot a month of PHIVOLCS earthquakes by location, depth and magnitude.

Run from a checkout with:

    uv run examples/plot_map.py --month 9 --year 2026 --output docs/map.png
"""

import argparse

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from pylindol import PhivolcsEarthquakeInfoScraper

# One-hue sequential ramp, light to dark: deeper earthquakes are darker.
DEPTH_RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
SURFACE = "#fcfcfb"
INK = "#2b2b29"
MUTED = "#6b6a66"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot a month of PHIVOLCS earthquakes."
    )
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output", default="earthquakes.png")
    args = parser.parse_args()

    df = PhivolcsEarthquakeInfoScraper(
        month=args.month, year=args.year, export=False
    ).run()
    # Draw small, shallow events first so large ones sit on top.
    df = df.sort_values("magnitude")
    month_name = df["datetime"].iloc[0].strftime("%B %Y")

    plt.rcParams.update({"font.size": 10, "text.color": INK, "axes.labelcolor": MUTED})
    fig, ax = plt.subplots(figsize=(7, 8.5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    cmap = LinearSegmentedColormap.from_list("depth", DEPTH_RAMP)
    points = ax.scatter(
        df["longitude"],
        df["latitude"],
        s=(df["magnitude"].clip(lower=1) ** 2.4) * 2,
        c=df["depth_km"].clip(upper=300),
        cmap=cmap,
        vmin=0,
        vmax=300,
        alpha=0.8,
        linewidths=0.4,
        edgecolors=SURFACE,
    )

    ax.set_aspect("equal")
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.tick_params(colors=MUTED, length=0)
    ax.grid(color="#e6e5e1", linewidth=0.6)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(
        f"PHIVOLCS earthquakes, {month_name}",
        loc="left",
        fontsize=12,
        fontweight="bold",
        pad=24,
    )
    ax.text(
        0,
        1.015,
        f"{len(df):,} events. Dot size shows magnitude; color shows depth.",
        transform=ax.transAxes,
        color=MUTED,
    )

    colorbar = fig.colorbar(points, ax=ax, shrink=0.45, pad=0.02, extend="max")
    colorbar.set_label("Depth (km)")
    colorbar.outline.set_visible(False)
    colorbar.ax.tick_params(colors=MUTED, length=0)

    for magnitude in (2, 4, 6):
        ax.scatter(
            [], [], s=(magnitude**2.4) * 2, color=DEPTH_RAMP[2], label=f"M{magnitude}"
        )
    legend = ax.legend(
        title="Magnitude", loc="lower left", frameon=False, labelcolor=INK
    )
    legend.get_title().set_color(MUTED)

    fig.tight_layout()
    fig.savefig(args.output, dpi=150, facecolor=SURFACE)
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
