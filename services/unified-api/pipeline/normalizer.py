import re

def normalize_name(name: str) -> str:
    """Standardizes names. Handles 'LastName, FirstName' swapping and title casing."""
    if not name:
        return ""
    
    # Strip any leading/trailing spaces
    name = name.strip()
    
    # If the name is in "Last, First" format, swap it
    if "," in name:
        parts = name.split(",")
        if len(parts) == 2:
            name = f"{parts[1].strip()} {parts[0].strip()}"
            
    # Clean up double/multiple spaces and capitalize each token
    tokens = [w.capitalize() for w in name.split() if w]
    return " ".join(tokens)

def normalize_email(email: str) -> str:
    """Standardizes emails to lowercase with stripped whitespaces."""
    if not email:
        return ""
    return email.strip().lower()

def normalize_phone(phone: str) -> str:
    """Keeps only digits. Strips leading country code '+1' or '1' for North American numbers."""
    if not phone:
        return ""
    
    # Keep only digits
    digits = "".join(c for c in phone if c.isdigit())
    
    # Strip leading North American country code '1' if we have an 11-digit number
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
        
    # Return digits if it looks like a valid phone (at least 7 digits)
    if len(digits) >= 7:
        return digits
    return ""

def normalize_address(address: str) -> str:
    """Standardizes address strings. Strips punctuation, lowercases, and unifies abbreviations."""
    if not address:
        return ""
    
    # Lowercase and replace commas, periods, pipes with spaces
    addr = address.lower()
    addr = re.sub(r"[,\.\|\-\_]", " ", addr)
    
    # Synonym mappings for abbreviations
    synonyms = {
        "street": "st",
        "road": "rd",
        "avenue": "ave",
        "lane": "ln",
        "boulevard": "blvd",
        "drive": "dr",
        "court": "ct",
        "highway": "hwy",
        "place": "pl",
        "parkway": "pkwy"
    }
    
    # Split tokens, standardize, and reassemble
    tokens = addr.split()
    standardized_tokens = []
    for token in tokens:
        standardized_tokens.append(synonyms.get(token, token))
        
    return " ".join(standardized_tokens)
