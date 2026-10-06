# Components module for Perrin Family Movies App


def format_stars(score: float, max_score: float = 10, max_stars: int = 5) -> str:
    """
    Convert a numeric score to a star display string with filled and empty stars.
    
    Args:
        score: The rating score (e.g., 7.3)
        max_score: Maximum possible score (default 10)
        max_stars: Maximum stars to display (default 5)
    
    Returns:
        String with filled (⭐) and empty (○) indicators
    
    Examples:
        7.3/10 → 73% → 3.65 stars → rounds to 4 → ⭐⭐⭐⭐○
        5.0/10 → 50% → 2.5 stars → rounds to 3 → ⭐⭐⭐○○
        9.2/10 → 92% → 4.6 stars → rounds to 5 → ⭐⭐⭐⭐⭐
        2.0/10 → 20% → 1.0 stars → rounds to 1 → ⭐○○○○
    """
    if score is None or score == 0:
        return "○" * max_stars
    
    # Calculate star rating
    star_value = (score / max_score) * max_stars
    
    # Round to nearest whole star
    filled = round(star_value)
    filled = max(0, min(filled, max_stars))  # Clamp to valid range
    
    empty = max_stars - filled
    
    return "⭐" * filled + "○" * empty
