"""Une seule apparence pour toutes les figures : fond clair, grille discrète, peu de couleurs."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLEU, ORANGE, VERT, GRIS = "#2a78d6", "#eb6834", "#2f9e6e", "#8c8b86"
ENCRE, ENCRE_2, FOND, OMBRE = "#0b0b0b", "#52514e", "#fcfcfb", "#ecebe7"


def appliquer() -> None:
    plt.rcParams.update({
        "figure.facecolor": FOND, "axes.facecolor": FOND, "savefig.facecolor": FOND,
        "axes.edgecolor": ENCRE_2, "axes.labelcolor": ENCRE, "text.color": ENCRE,
        "xtick.color": ENCRE_2, "ytick.color": ENCRE_2, "axes.grid": True, "grid.color": "#e4e3df",
        "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "legend.frameon": False,
        "axes.formatter.use_locale": False,
    })


def virgule(ax, axe: str = "y", decimales: int = 1) -> None:
    """Écrit les graduations avec une virgule décimale, à la française."""
    from matplotlib.ticker import FuncFormatter
    fmt = FuncFormatter(lambda v, _: f"{v:.{decimales}f}".replace(".", ",").replace("-", "−"))
    (ax.yaxis if axe == "y" else ax.xaxis).set_major_formatter(fmt)
