"""
Unit Detection and Conversion Utilities

Handles automatic unit detection and conversion for financial data:
- Volatility: daily_bps, annualized_bps, daily_pct, annualized_pct
- Basis points, percentages, currency, growth rates

"""

import pandas as pd
import numpy as np
from typing import Union, Optional


def label_vol_units(metadata_df: pd.DataFrame) -> dict:
    """
    Given a metadata DataFrame from a data pull, return a dict mapping
    coordinate strings to their vol unit convention.

    Returns:
        Dict[str, str] mapping coordinate -> unit label
        e.g. {'Vol_USD_Swaption_1Mx10Y_Vol': 'bps/day',
              'Vol_USD_RealizedVol_10Y30D_Vol': 'bps/annum'}
    """
    unit_map = {}
    if 'units' not in metadata_df.columns:
        return unit_map
    for _, row in metadata_df.iterrows():
        coord = row.get('concept', row.get('coordinate', ''))
        units = row.get('units', '')
        if 'daily_bps' in str(units):
            unit_map[coord] = 'bps/day'
        elif 'annualized_bps' in str(units):
            unit_map[coord] = 'bps/annum'
        elif 'percent_vol' in str(units):
            unit_map[coord] = '% (annualized)'
        elif 'percent' in str(units):
            unit_map[coord] = '%'
        else:
            unit_map[coord] = str(units)
    return unit_map


def format_vol_with_units(value: float, units: str) -> str:
    """
    Format a vol value with its unit label.

    Examples:
        format_vol_with_units(4.82, 'bps/day') -> '4.82 bps/day'
        format_vol_with_units(76.5, 'bps/annum') -> '76.5 bps/annum'
    """
    return f"{value:.2f} {units}"

def convert_volatility_units(
        data: Union[pd.Series, np.ndarray],
        from_unit: str,
        to_unit: str
) -> Union[pd.Series, np.ndarray]:
    """
    Convert volatility between different units.

    Args:
        data: Series or array of volatility values
        from_unit: Source unit ('daily_bps', 'annualized_bps', 'daily_pct', 'annualized_pct')
        to_unit: Target unit (same options)

    Returns:
        Converted data

    Conversions:
    - daily_bps → annualized_bps: multiply by sqrt(252)
    - annualized_bps → daily_bps: divide by sqrt(252)
    - bps → pct: divide by 100
    - pct → bps: multiply by 100

    Examples:
        >>> convert_volatility_units(pd.Series([10, 20]), 'daily_bps', 'annualized_bps')
        # Returns: [158.74, 317.48] (10 * sqrt(252), 20 * sqrt(252))
    """

    # Conversion factors
    TRADING_DAYS = 252
    BPS_TO_PCT = 100

    # Normalize to daily_bps first
    if from_unit == 'annualized_bps':
        data = data / np.sqrt(TRADING_DAYS)
    elif from_unit == 'daily_pct':
        data = data * BPS_TO_PCT
    elif from_unit == 'annualized_pct':
        data = data * BPS_TO_PCT / np.sqrt(TRADING_DAYS)
    elif from_unit != 'daily_bps':
        raise ValueError(f"Unknown from_unit: {from_unit}")

    # Convert from daily_bps to target
    if to_unit == 'annualized_bps':
        data = data * np.sqrt(TRADING_DAYS)
    elif to_unit == 'daily_pct':
        data = data / BPS_TO_PCT
    elif to_unit == 'annualized_pct':
        data = data * np.sqrt(TRADING_DAYS) / BPS_TO_PCT
    elif to_unit != 'daily_bps':
        raise ValueError(f"Unknown to_unit: {to_unit}")

    return data

def guess_units_from_name(column_name: str) -> Optional[str]:
    """
    Guess the appropriate units from a column/symbol name.

    Detects common patterns in financial/economic data naming:
    - Percentage indicators: pct, percent, percentage, rate
    - Basis points: bps, bp, spread
    - Currency: usd, dollars, with scale modifiers (bil, mil)
    - Volatility: vol (daily bps for swaptions)
    - Growth rates: yoy, qoq, mom

    Only whole words count, so 'trade_volume' is not a vol, 'corporate_flows'
    is not a rate and 't_bill_yield' is not in billions. A wrong unit on an
    axis is worse than none, so an unrecognised vol convention returns None.

    Args:
        column_name: The column/symbol name to analyze

    Returns:
        Guessed unit string or None if no pattern matches

    Examples:
        >>> guess_units_from_name("us_swap_rate_percentage")
        '%'
        >>> guess_units_from_name("us_10y_swap_spread")
        'bps'
        >>> guess_units_from_name("usd_swaption_vol")
        'daily bps'
    """
    if not column_name:
        return None

    name_lower = column_name.lower()
    words = set(''.join(ch if ch.isalnum() else ' ' for ch in name_lower).split())

    # Percentage patterns (most common in rates/macro data)
    if words & {'pct', 'percent', 'percentage'}:
        return '%'

    # Rate typically means percentage
    if words & {'rate', 'rates'}:
        return '%'

    # Basis points (common in spreads, flies)
    if words & {'bps', 'bp'}:
        return 'bps'

    # Spread typically in basis points
    if words & {'spread', 'spreads'}:
        return 'bps'

    # Year-over-year percentage change
    if 'yoy' in words:
        return 'YoY %'

    # Quarter-over-quarter percentage change
    if 'qoq' in words:
        return 'QoQ %'

    # Month-over-month percentage change
    if 'mom' in words:
        return 'MoM %'

    # Volatility - check for swaption vol (daily bps)
    if words & {'vol', 'volatility'}:
        # Explicit conventions (a bare bps / pct word already returned above)
        if 'dbps' in words:
            return 'daily bps'
        if 'abps' in words:
            return 'annualized bps'

        # Swaption volatility (typically daily bps)
        if words & {'swaption', 'swpn'}:
            return 'daily bps'

        # Default volatility (assume daily bps for rates, annualized % for equities)
        if words & {'swap', 'treasury', 'bond', 'yield'}:
            return 'daily bps'  # Rates vol typically daily bps
        if words & {'equity', 'stock', 'index', 'spx', 'ndx'}:
            return 'annualized %'  # Equity vol typically annualized %
        return None  # FX vol is annualized %, rates vol daily bps: no safe default

    # Currency - billions
    if words & {'bil', 'billion', 'billions'}:
        if words & {'usd', 'dollars'} or '$' in name_lower:
            return '$ Billions'
        return 'Billions'

    # Currency - millions
    if words & {'mil', 'million', 'millions'}:
        if words & {'usd', 'dollars'} or '$' in name_lower:
            return '$ Millions'
        return 'Millions'

    return None


def detect_vol_convention(concept_name: str) -> Optional[str]:
    """
    Detect whether a volatility concept uses daily or annualized convention.

    Args:
        concept_name: The concept name to analyze

    Returns:
        'daily', 'annualized', or None if not a volatility concept
    """
    if 'vol' not in concept_name.lower():
        return None

    name_lower = concept_name.lower()

    # Explicit markers
    if 'daily' in name_lower:
        return 'daily'
    if any(x in name_lower for x in ['annualized', 'annual', 'ann']):
        return 'annualized'

    # Swaption vol is typically daily
    if 'swaption' in name_lower or 'swpn' in name_lower:
        return 'daily'

    # Rates vol typically daily, equity vol typically annualized
    if any(x in name_lower for x in ['swap', 'treasury', 'bond', 'rate']):
        return 'daily'
    if any(x in name_lower for x in ['equity', 'stock', 'index']):
        return 'annualized'

    return None  # Unknown
 