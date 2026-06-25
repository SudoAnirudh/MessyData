import os
import csv
import json
import random
import uuid
from datetime import datetime, timedelta

# Set seed for reproducibility
random.seed(42)

# --- CONFIGURATION ---
TOTAL_BASE_PROFILES = 700
LEGACY_DB_COUNT = 500
SAAS_API_COUNT = 500
CSV_EXPORT_COUNT = 200

# Overlaps configuration
# Legacy DB gets profiles 0 to 500
# SaaS API gets profiles 200 to 700 (300 overlap with Legacy DB, 200 unique)
# CSV Exports get 200 random profiles from all 700 (overlapping with both)

# --- MOCK DATA SOURCE DICTIONARIES ---
FIRST_NAMES = [
    "John", "Jane", "Robert", "Mary", "Michael", "David", "James", "Emily", "Sarah", "William",
    "Thomas", "Jessica", "Daniel", "Karen", "Mark", "Lisa", "Matthew", "Nancy", "Steven", "Betty",
    "Andrew", "Sandra", "Richard", "Donna", "Joseph", "Carol", "Charles", "Ruth", "Christopher", "Sharon",
    "Patricia", "Paul", "Michelle", "Laura", "Kevin", "Sarah", "Kimberly", "Elizabeth", "Brian", "Linda",
    "Barbara", "Susan", "Margaret", "Dorothy", "Ashley", "Jennifer", "Amanda", "Melissa", "René", "Zoë"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts"
]

STREETS = [
    "Oak St", "Pine Rd", "Maple Ave", "Cedar Ln", "Elm St", "Washington Blvd", "Broadway", "Main St",
    "Second Ave", "Park Ln", "Sunset Blvd", "River Rd", "Forest Dr", "Hillside Ave", "Bridge St",
    "Highland Terrace", "Ridge Rd", "Meadow Ln", "Spring St", "Lakeview Dr"
]

CITIES = [
    ("New York", "NY", "10001"),
    ("Los Angeles", "CA", "90001"),
    ("Chicago", "IL", "60601"),
    ("Houston", "TX", "77001"),
    ("Phoenix", "AZ", "85001"),
    ("Philadelphia", "PA", "19101"),
    ("San Antonio", "TX", "78201"),
    ("San Diego", "CA", "92101"),
    ("Dallas", "TX", "75201"),
    ("San Jose", "CA", "95101"),
    ("Austin", "TX", "78701"),
    ("Jacksonville", "FL", "32201"),
    ("San Francisco", "CA", "94101"),
    ("Columbus", "OH", "43201"),
    ("Charlotte", "NC", "28201")
]

DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"]

# --- MOCK DATA HELPER FUNCTIONS ---
def generate_phone():
    area = random.randint(200, 999)
    prefix = random.randint(200, 999)
    line = random.randint(1000, 9999)
    return f"{area}{prefix}{line}"

def generate_birthdate():
    start_date = datetime(1960, 1, 1)
    end_date = datetime(2005, 12, 31)
    days_between = (end_date - start_date).days
    random_days = random.randint(0, days_between)
    return (start_date + timedelta(days=random_days)).strftime("%Y-%m-%d")

# --- STEP 1: GENERATE BASELINE "GROUND TRUTH" CUSTOMERS ---
def generate_base_profiles():
    profiles = []
    for i in range(TOTAL_BASE_PROFILES):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        city_info = random.choice(CITIES)
        
        email = f"{first.lower()}.{last.lower()}{random.randint(10, 99)}@{random.choice(DOMAINS)}"
        # Handle non-ascii character normalization for email (e.g. René -> rene)
        email = email.replace("é", "e").replace("ë", "e").replace("ö", "o").replace("zöe", "zoe")
        
        profile = {
            "ground_truth_id": str(uuid.uuid4()),
            "first_name": first,
            "last_name": last,
            "email": email,
            "phone": generate_phone(),
            "street": f"{random.randint(100, 9999)} {random.choice(STREETS)}",
            "city": city_info[0],
            "state": city_info[1],
            "zip_code": city_info[2],
            "birthdate": generate_birthdate(),
            "created_at": (datetime.now() - timedelta(days=random.randint(30, 365))).strftime("%Y-%m-%d %H:%M:%S")
        }
        profiles.append(profile)
    return profiles

# --- STEP 2: INTRODUCE CONTROLLED CORRUPTIONS ---
def introduce_typo(text):
    if not text or len(text) < 3:
        return text
    chars = list(text)
    idx = random.randint(0, len(chars) - 2)
    # Swap adjacent characters
    chars[idx], chars[idx+1] = chars[idx+1], chars[idx]
    return "".join(chars)

def corrupt_phone(phone, style_idx):
    if style_idx == 0:
        return f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
    elif style_idx == 1:
        return f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
    elif style_idx == 2:
        return f"+1-{phone[:3]}-{phone[3:6]}-{phone[6:]}"
    elif style_idx == 3:
        return phone # raw digits
    return f"{phone[:3]} {phone[3:6]} {phone[6:]}"

# --- STEP 3: GENERATE SEED DATA FOR EACH SYSTEM ---
def create_legacy_db_seed(profiles):
    # Select first 500 profiles
    selected = profiles[:LEGACY_DB_COUNT]
    sql_statements = [
        "DROP TABLE IF EXISTS legacy_customers;",
        """CREATE TABLE legacy_customers (
            id SERIAL PRIMARY KEY,
            cust_nm VARCHAR(255),
            email_addr VARCHAR(255),
            phone_no VARCHAR(50),
            addr_line1 VARCHAR(255),
            city_name VARCHAR(100),
            postal_code VARCHAR(20),
            created_at VARCHAR(100)
        );"""
    ]
    
    rows = []
    for p in selected:
        # Inconsistent naming (e.g. "LAST, FIRST" or all caps, or minor spelling typo)
        name_style = random.choice(["caps", "last_first", "normal", "typo"])
        if name_style == "caps":
            name = f"{p['first_name']} {p['last_name']}".upper()
        elif name_style == "last_first":
            name = f"{p['last_name']}, {p['first_name']}"
        elif name_style == "typo" and random.random() < 0.3:
            name = f"{introduce_typo(p['first_name'])} {p['last_name']}"
        else:
            name = f"{p['first_name']} {p['last_name']}"
            
        # Email: missing in 10% of entries, field is email_addr
        email = p["email"] if random.random() > 0.10 else None
        
        # Phone formatting
        phone = corrupt_phone(p["phone"], random.randint(0, 4))
        
        rows.append({
            "cust_nm": name,
            "email_addr": email,
            "phone_no": phone,
            "addr_line1": p["street"],
            "city_name": p["city"],
            "postal_code": p["zip_code"],
            "created_at": p["created_at"]
        })
        
    # Inject ~30 duplicates
    for _ in range(30):
        orig = random.choice(rows)
        dup = orig.copy()
        # Change phone format slightly in duplicate
        if dup["phone_no"]:
            dup["phone_no"] = dup["phone_no"].replace(" ", "-").replace("(", "").replace(")", "")
        # Maybe change name style
        if "," in dup["cust_nm"]:
            parts = dup["cust_nm"].split(", ")
            dup["cust_nm"] = f"{parts[1]} {parts[0]}"
        rows.append(dup)
        
    # Shuffle so duplicates are scattered
    random.shuffle(rows)
    
    for r in rows:
        nm = r['cust_nm'].replace("'", "''")
        em = f"'{r['email_addr']}'" if r['email_addr'] else "NULL"
        ph = f"'{r['phone_no']}'" if r['phone_no'] else "NULL"
        addr = r['addr_line1'].replace("'", "''")
        city = r['city_name'].replace("'", "''")
        pc = r['postal_code']
        created = r['created_at']
        
        sql_statements.append(
            f"INSERT INTO legacy_customers (cust_nm, email_addr, phone_no, addr_line1, city_name, postal_code, created_at) "
            f"VALUES ('{nm}', {em}, {ph}, '{addr}', '{city}', '{pc}', '{created}');"
        )
        
    return "\n".join(sql_statements)

def create_saas_api_seed(profiles):
    # Select profiles 200 to 700 (overlapping with legacy by 300 records)
    selected = profiles[200:200 + SAAS_API_COUNT]
    
    contacts = []
    for idx, p in enumerate(selected):
        # Slightly different email domain (domain drift) in 15% of records
        email = p["email"]
        if random.random() < 0.15:
            username = email.split("@")[0]
            new_domain = random.choice(["company.com", "workmail.net", "corporate.org"])
            email = f"{username}@{new_domain}"
            
        # Address format: single line
        full_address = f"{p['street']}, {p['city']}, {p['state']} {p['zip_code']}"
        
        # Phone: normalized
        phone = f"+1-{p['phone'][:3]}-{p['phone'][3:6]}-{p['phone'][6:]}"
        
        # Typos in first or last name
        first_name = p["first_name"]
        last_name = p["last_name"]
        if random.random() < 0.08:
            first_name = introduce_typo(first_name)
        if random.random() < 0.08:
            last_name = introduce_typo(last_name)
            
        contacts.append({
            "id": idx + 1001, # Start at 1001
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "address": full_address,
            "updated_at": p["created_at"]
        })
        
    return contacts

def create_csv_exports(profiles):
    # Choose 200 profiles randomly from the base profiles
    selected = random.sample(profiles, CSV_EXPORT_COUNT)
    
    # Divide into three regions: East, West, and Central (General)
    east_records = selected[:70]
    west_records = selected[70:140]
    central_records = selected[140:]
    
    # 1. East CSV - Inconsistent Date format (e.g. MM/DD/YYYY) and columns
    # Write using standard UTF-8
    east_data = []
    for p in east_records:
        # Inconsistent Date format
        dt = datetime.strptime(p["birthdate"], "%Y-%m-%d")
        formatted_dob = dt.strftime("%m/%d/%Y")
        
        name = f"{p['first_name']} {p['last_name']}"
        if random.random() < 0.10:
            name = introduce_typo(name)
            
        # Inconsistent email typo (e.g. missing '.' or typos in domain)
        email = p["email"]
        if random.random() < 0.15:
            email = email.replace("gmail.com", "gmal.com").replace("yahoo.com", "yaho.com").replace("outlook.com", "outlok.com")
            
        east_data.append({
            "FullName": name,
            "EmailAddress": email,
            "Phone": corrupt_phone(p["phone"], 0),
            "FullAddress": f"{p['street']}, {p['city']}, {p['state']}",
            "Dob": formatted_dob
        })
        
    # 2. West CSV - Inconsistent Date format (e.g. DD-MM-YYYY) and headers
    # Write in ISO-8859-1 (Latin-1) or Windows-1252 to test encoding failure
    # Ensure there are some special accent characters (René, Zoë)
    west_data = []
    for p in west_records:
        dt = datetime.strptime(p["birthdate"], "%Y-%m-%d")
        formatted_dob = dt.strftime("%d-%m-%Y")
        
        # Phone: weird format e.g. XXX.XXX.XXXX
        phone = f"{p['phone'][:3]}.{p['phone'][3:6]}.{p['phone'][6:]}"
        
        west_data.append({
            "Contact Name": f"{p['first_name']} {p['last_name']}",
            "Email": p["email"] if random.random() > 0.05 else "", # Empty email
            "Phone": phone,
            "Addr": f"{p['street']} | {p['city']} | {p['state']} {p['zip_code']}",
            "BirthDate": formatted_dob
        })
        
    # 3. Central CSV - Date format (YYYY/MM/DD) and different headers
    central_data = []
    for p in central_records:
        dt = datetime.strptime(p["birthdate"], "%Y-%m-%d")
        formatted_dob = dt.strftime("%Y/%m/%d")
        
        central_data.append({
            "Customer": f"{p['last_name']}, {p['first_name']}",
            "Email": p["email"],
            "PhoneNo": corrupt_phone(p["phone"], 1),
            "Address": f"{p['street']}, {p['city']}, {p['state']} {p['zip_code']}",
            "DateOfBirth": formatted_dob
        })
        
    return east_data, west_data, central_data


def save_csv(data, filename, encoding='utf-8'):
    if not data:
        return
    keys = data[0].keys()
    with open(filename, 'w', newline='', encoding=encoding) as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)


# --- MAIN EXECUTION ---
def main():
    print("Generating baseline clean customer profiles...")
    base_profiles = generate_base_profiles()
    
    # Save the ground truth baseline for validation purposes (like testing accuracy)
    # This will be stored inside the unified-api or a shared folder
    os.makedirs('/home/anirudhs/Documents/Boredom/MessyData/services/unified-api/pipeline/data', exist_ok=True)
    with open('/home/anirudhs/Documents/Boredom/MessyData/services/unified-api/pipeline/data/ground_truth.json', 'w') as f:
        json.dump(base_profiles, f, indent=2)
    print("Ground truth profiles saved.")
    
    # Create required directory structure
    os.makedirs('/home/anirudhs/Documents/Boredom/MessyData/services/legacy-db', exist_ok=True)
    os.makedirs('/home/anirudhs/Documents/Boredom/MessyData/services/mock-saas-api', exist_ok=True)
    os.makedirs('/home/anirudhs/Documents/Boredom/MessyData/services/csv-drop', exist_ok=True)
    
    # 1. Legacy DB Seed
    print("Creating Legacy DB SQL seed...")
    legacy_sql = create_legacy_db_seed(base_profiles)
    with open('/home/anirudhs/Documents/Boredom/MessyData/services/legacy-db/init.sql', 'w') as f:
        f.write(legacy_sql)
    print("Legacy SQL seed created.")
    
    # 2. SaaS API Seed
    print("Creating SaaS API seed JSON...")
    saas_json = create_saas_api_seed(base_profiles)
    with open('/home/anirudhs/Documents/Boredom/MessyData/services/mock-saas-api/seed_contacts.json', 'w') as f:
        json.dump(saas_json, f, indent=2)
    print("SaaS API JSON seed created.")
    
    # 3. CSV Exports
    print("Creating CSV Exports...")
    east, west, central = create_csv_exports(base_profiles)
    
    # Save East (UTF-8)
    save_csv(east, '/home/anirudhs/Documents/Boredom/MessyData/services/csv-drop/sales_east.csv', encoding='utf-8')
    # Save West (Windows-1252 / Latin-1) to create encoding issues
    save_csv(west, '/home/anirudhs/Documents/Boredom/MessyData/services/csv-drop/sales_west.csv', encoding='windows-1252')
    # Save Central (UTF-8)
    save_csv(central, '/home/anirudhs/Documents/Boredom/MessyData/services/csv-drop/sales_central.csv', encoding='utf-8')
    
    print("CSV files created.")
    print("Data generation complete successfully!")

if __name__ == '__main__':
    main()
