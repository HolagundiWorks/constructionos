"""Trend forecasting (E5 — prediction), as pure, honest maths.

No tkinter, no database, no model. The roadmap's prediction phase asks for a
*forward* view — where a number is heading — and the honest way to give one from
a contractor's own thin history is a **least-squares linear trend with a stated
range and a confidence that shrinks with the sample**, never a single
false-precise figure.

Two rules keep it truthful:

* A projection is always returned as a **band** (low / value / high) plus a
  ``confidence`` word, because a straight-line guess off six weeks of data is a
  direction, not a promise.
* ``confidence`` is driven by how much history there is (and how noisy it is),
  the same discipline as ``advisory.py`` — three points is ``Low`` however tidy
  they look.

Everything is exercised with ``python -c``, e.g.::

    python -c "import forecast; print(forecast.project([70,72,68,60,55], 2))"
"""

import math

LOW, MEDIUM, HIGH = 'Low', 'Medium', 'High'


def _nums(series):
    """The series as floats, dropping Nones, order preserved."""
    out = []
    for v in series or []:
        if v is None:
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def confidence_for(n):
    """How much to trust a trend from ``n`` points. Deliberately conservative —
    a forecast off a handful of periods is a hint, not a plan."""
    if n < 4:
        return LOW
    if n < 8:
        return MEDIUM
    return HIGH


def linear_trend(series):
    """Least-squares slope + intercept over equally-spaced points (x = 0..n-1).

    Returns ``{slope, intercept, n}`` or None when there are fewer than two
    points (a line needs two) or the x-variance is zero."""
    ys = _nums(series)
    n = len(ys)
    if n < 2:
        return None
    xs = list(range(n))
    xbar = sum(xs) / n
    ybar = sum(ys) / n
    sxx = sum((x - xbar) ** 2 for x in xs)
    if not sxx:
        return None
    sxy = sum((xs[i] - xbar) * (ys[i] - ybar) for i in range(n))
    slope = sxy / sxx
    return {'slope': slope, 'intercept': ybar - slope * xbar, 'n': n}


def project(series, periods_ahead=1):
    """Project a series ``periods_ahead`` steps past its last point.

    Returns the central ``value``, a ``low``/``high`` band (±1 RMSE of the fit,
    roughly a 2-in-3 range), the ``confidence`` word, the ``slope`` (per period,
    so the caller can say "falling ~4/week"), and a ``basis``. None if the trend
    is undefined.
    """
    t = linear_trend(series)
    if t is None:
        return None
    ys = _nums(series)
    n = t['n']
    slope, intercept = t['slope'], t['intercept']

    # RMSE of the fit → the band. A perfectly straight history gives a tight
    # band; a noisy one widens it honestly.
    sse = sum((ys[i] - (intercept + slope * i)) ** 2 for i in range(n))
    rmse = math.sqrt(sse / n)

    x = n - 1 + max(1, int(periods_ahead))
    value = intercept + slope * x
    return {
        'value': round(value, 4),
        'low': round(value - rmse, 4),
        'high': round(value + rmse, 4),
        'slope': round(slope, 4),
        'confidence': confidence_for(n),
        'basis': '{} period(s) of history'.format(n),
        'periods_ahead': max(1, int(periods_ahead)),
    }


def direction(series):
    """A plain word for where a series is heading: 'rising' / 'falling' /
    'flat' / None. Handy for a one-line KPI note without exposing the slope."""
    t = linear_trend(series)
    if t is None:
        return None
    if t['slope'] > 1e-9:
        return 'rising'
    if t['slope'] < -1e-9:
        return 'falling'
    return 'flat'


def schedule_forecast(baseline_duration, spi):
    """Forecast a job's duration from its baseline and Schedule Performance
    Index: ``duration / SPI`` (SPI<1 → longer). Returns the forecast duration
    and the slip vs baseline, or None when SPI is missing/zero.

    This is the schedule twin of EVM's cost EAC (which lives in
    ``earnedvalue``): the same "if today's performance continues" assumption,
    applied to time.
    """
    try:
        d = float(baseline_duration or 0)
        s = float(spi) if spi else 0.0
    except (TypeError, ValueError):
        return None
    if not s:
        return None
    forecast = d / s
    return {
        'baseline_duration': round(d, 2),
        'forecast_duration': round(forecast, 2),
        'slip': round(forecast - d, 2),          # >0 = later than baseline
    }
