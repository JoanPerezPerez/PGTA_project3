
def normalize_runway(pista_str: str) -> str:
    """
    Normaliza el formato de pista de 'LEBL-24L' a '24L'.
    
    Args:
        pista_str: String con formato 'LEBL-24L' o 'LEBL-06R'
    
    Returns:
        String normalizado '24L' o '06R'
    """
    if '-' in pista_str:
        return pista_str.split('-')[1]
    return pista_str