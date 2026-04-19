def safe_float(value):
    """
    Safely convert a value to float. 
    Returns 0.0 if the value is None, empty, or invalid.
    """
    try:
        if value is None or str(value).strip() == "":
            return 0.0
        return float(value)
    except (ValueError, TypeError):
        return 0.0
