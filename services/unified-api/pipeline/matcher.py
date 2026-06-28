from rapidfuzz import fuzz

def calculate_match_score(record: dict, candidate: dict) -> tuple[int, list[str]]:
    """
    Computes a match confidence score (0-100) between an incoming record
    and an existing unified customer candidate.
    
    Returns (score, reasons).
    """
    score = 0
    reasons = []
    
    rec_name = record.get("name", "")
    rec_email = record.get("email", "")
    rec_phone = record.get("phone", "")
    rec_address = record.get("address", "")
    
    cand_name = candidate.get("full_name", "")
    cand_email = candidate.get("email", "")
    cand_phone = candidate.get("phone", "")
    cand_address = candidate.get("address", "")
    
    # 1. Calculate base string similarities
    name_sim = fuzz.token_sort_ratio(rec_name, cand_name) if rec_name and cand_name else 0
    addr_sim = fuzz.token_sort_ratio(rec_address, cand_address) if rec_address and cand_address else 0
    
    email_match = (rec_email == cand_email) if rec_email and cand_email else False
    phone_match = (rec_phone == cand_phone) if rec_phone and cand_phone else False
    
    # 2. Case: Exact Email Match
    if email_match:
        if name_sim >= 80:
            score = 98
            reasons.append(f"Exact email match with high name similarity ({name_sim}%)")
        elif name_sim >= 50:
            score = 75
            reasons.append(f"Exact email match but moderate name similarity ({name_sim}%)")
        else:
            score = 50
            reasons.append(f"Exact email match but low name similarity ({name_sim}%) - potential duplicate/hijack")
            
    # 3. Case: Exact Phone Match
    elif phone_match:
        if name_sim >= 80:
            score = 95
            reasons.append(f"Exact phone match with high name similarity ({name_sim}%)")
        elif name_sim >= 50:
            score = 70
            reasons.append(f"Exact phone match but moderate name similarity ({name_sim}%) - possible shared household")
        else:
            score = 45
            reasons.append(f"Exact phone match but low name similarity ({name_sim}%)")
            
    # 4. Case: Fuzzy Name & Address Matches (no exact email/phone matches)
    else:
        if name_sim >= 85:
            if rec_address and cand_address:
                if addr_sim >= 80:
                    score = 88
                    reasons.append(f"High name similarity ({name_sim}%) and address match ({addr_sim}%)")
                elif addr_sim >= 50:
                    score = 65
                    reasons.append(f"High name similarity ({name_sim}%) but moderate address similarity ({addr_sim}%)")
                else:
                    score = 55
                    reasons.append(f"High name similarity ({name_sim}%) but address mismatch ({addr_sim}%)")
            else:
                score = 70
                reasons.append(f"High name similarity ({name_sim}%) with missing address fields")
        elif name_sim >= 70:
            if rec_address and cand_address and addr_sim >= 85:
                score = 75
                reasons.append(f"Moderate name similarity ({name_sim}%) with high address similarity ({addr_sim}%)")
            else:
                score = 30
                reasons.append(f"Moderate name similarity ({name_sim}%) and no strong address match")
                
    # If the score remains 0, return name similarity as a low-confidence score
    if score == 0:
        score = int(name_sim * 0.4) # Scale name match to low confidence
        if score > 0:
            reasons.append(f"Low name similarity match ({name_sim}%)")
            
    return score, reasons

def find_best_match(record: dict, candidates: list[dict]) -> tuple[dict | None, int, list[str]]:
    """
    Scans a list of existing unified candidates and returns the best match
    along with its score and reasons.
    """
    best_candidate = None
    best_score = 0
    best_reasons = []
    
    for candidate in candidates:
        score, reasons = calculate_match_score(record, candidate)
        if score > best_score:
            best_score = score
            best_candidate = candidate
            best_reasons = reasons
            
    return best_candidate, best_score, best_reasons
