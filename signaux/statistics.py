"""Numerical conventions, kept independent of file I/O."""

import numpy as np
import pandas as pd

EPSILON = 1e-9


def ratio(numerator, denominator, zero_positive=10.0):
    """Finite ratios: 0/0=0; positive/0 saturates at a documented finite sentinel."""
    n, d = np.broadcast_arrays(np.asarray(numerator, float), np.asarray(denominator, float))
    result = np.divide(n, d, out=np.zeros_like(n), where=np.abs(d) > EPSILON)
    return np.where((np.abs(d) <= EPSILON) & (n > EPSILON), zero_positive, result)


def normalize_z(z):
    return np.clip((np.asarray(z) - 1.0) / 3.0, 0.0, 1.0)


def growth(current, previous):
    """Percentage growth; a positive restart from zero is capped at +1,000%."""
    return np.where(
        np.asarray(previous) > EPSILON,
        100.0 * (ratio(current, previous) - 1.0),
        np.where(np.asarray(current) > EPSILON, 1000.0, 0.0),
    )


def ewma_z(history: np.ndarray, two_sided=False, alpha=0.3):
    """Columns are calendar months, final column is the tested observation.

    EWMA smooths the current observation. Baseline is the ten observations in
    [t-12,t-3], excluding t-2 and t-1. Missing observations stay missing, not zero.
    At least six baseline observations and an observed current value are needed.
    The 5% scale floor prevents almost constant series generating infinite alerts.
    """
    n, width = history.shape
    if width < 9:
        return np.zeros(n)
    baseline = pd.DataFrame(history[:, max(0, width - 13) : width - 3])
    mean = baseline.mean(axis=1).to_numpy()
    std = baseline.std(axis=1, ddof=1).to_numpy()
    scale = np.maximum(np.nan_to_num(std), np.maximum(np.abs(mean) * 0.05, 1.0))
    smooth = pd.DataFrame(history.T).ewm(alpha=alpha, adjust=False, ignore_na=True).mean()
    z = (smooth.iloc[-1].to_numpy() - mean) / scale
    valid = (baseline.count(axis=1).to_numpy() >= 6) & np.isfinite(history[:, -1])
    z = np.where(valid, np.nan_to_num(z), 0.0)
    return np.abs(z) if two_sided else np.maximum(z, 0.0)


def robust_distances(values: np.ndarray, targets: np.ndarray | None = None):
    """Winsorized, ridge-regularized covariance; stable for singular peer groups.

    Return distance, nonnegative coordinate contributions and robust center.
    Scaling and clipping are estimated from contemporaneous peers only.
    No trained prediction model or random state is involved.
    """
    center = np.median(values, axis=0)
    scale = 1.4826 * np.median(np.abs(values - center), axis=0)
    scale = np.maximum(scale, np.maximum(np.abs(center) * 0.05, 0.01))
    standardized = (values - center) / scale
    clipped = np.clip(standardized, -4.0, 4.0)
    covariance = np.atleast_2d(np.cov(clipped, rowvar=False))
    covariance = 0.9 * covariance + 0.1 * np.eye(values.shape[1])
    precision = np.linalg.pinv(covariance, hermitian=True)
    target_scaled = standardized if targets is None else (targets - center) / scale
    signed = target_scaled * (target_scaled @ precision)
    squared = np.maximum(signed.sum(axis=1), 0.0)
    # Signed contributions sum to d²; magnitude identifies the dominant coordinate.
    return np.sqrt(squared), np.abs(signed), center


def french_amount(amount: float) -> str:
    if abs(amount) >= 1_000_000:
        return f"{amount / 1_000_000:.2f}".replace(".", ",") + " MD"
    return f"{amount:,.3f}".replace(",", " ").replace(".", ",") + " DT"


def available_exercise(month: pd.Period) -> int:
    return month.year - (1 if month.month >= 3 else 2)
