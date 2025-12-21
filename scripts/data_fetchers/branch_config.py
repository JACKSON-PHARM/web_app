"""
Branch Configuration for All Companies
Centralized branch definitions used by all fetchers
"""

# Branch mapping: branch_code -> branch_name
BRANCH_MAPPING = {
    "BR001": "BABA DOGO HQ",
    "BR002": "ACCRA NILA",
    "BR0024": "HOLDING STORE",
    "BR0025": "GILL HOUSE",
    "BR0026": "NILA ACCRA ARCADE",
    "BR0027": "RONGAI WHOLESALE",
    "BR003": "RONALD NILA",
    "BR004": "MFANGANO NILA",
    "BR006": "TOM MBOYA",
    "BR007": "NAKURU NILA",
    "BR008": "DAIMA MERU RETAIL",
    "BR009": "DAIMA THIKA RETAIL",
    "BR011": "MOUNTAIN MALL",
    "BR012": "DAIMA WHOLESALE THIKA",
    "BR013": "DAIMA MERU WHOLESALE",
    "BR014": "JUJA CITY MALL",
    "BR015": "ELDORET NILA",
    "BR016": "NILA JEWEL",
    "BR017": "LATEMA NILA",
    "BR018": "MEPALUX BRANCH",
    "BR020": "NILA RONGAI BRANCH",
    "BR021": "NILA MOI AVENUE",
    "BR022": "DAIMA MAKUTANO",
    "BR023": "NILA MOMBASA BRANCH"
}

# DAIMA Company Branches
DAIMA_BRANCHES = [
    {"branchcode": "BR008", "branch_name": "DAIMA MERU RETAIL", "company": "DAIMA", "branch_num": 8},
    {"branchcode": "BR009", "branch_name": "DAIMA THIKA RETAIL", "company": "DAIMA", "branch_num": 9},
    {"branchcode": "BR012", "branch_name": "DAIMA WHOLESALE THIKA", "company": "DAIMA", "branch_num": 12},
    {"branchcode": "BR013", "branch_name": "DAIMA MERU WHOLESALE", "company": "DAIMA", "branch_num": 13},
    {"branchcode": "BR022", "branch_name": "DAIMA MAKUTANO", "company": "DAIMA", "branch_num": 22}
]

# NILA Company Branches
NILA_BRANCHES = [
    {"branchcode": "BR001", "branch_name": "BABA DOGO HQ", "company": "NILA", "branch_num": 1},
    {"branchcode": "BR002", "branch_name": "ACCRA NILA", "company": "NILA", "branch_num": 2},
    {"branchcode": "BR0024", "branch_name": "HOLDING STORE", "company": "NILA", "branch_num": 24},
    {"branchcode": "BR0025", "branch_name": "GILL HOUSE", "company": "NILA", "branch_num": 25},
    {"branchcode": "BR0026", "branch_name": "NILA ACCRA ARCADE", "company": "NILA", "branch_num": 26},
    {"branchcode": "BR0027", "branch_name": "RONGAI WHOLESALE", "company": "NILA", "branch_num": 27},
    {"branchcode": "BR003", "branch_name": "RONALD NILA", "company": "NILA", "branch_num": 3},
    {"branchcode": "BR004", "branch_name": "MFANGANO NILA", "company": "NILA", "branch_num": 4},
    {"branchcode": "BR006", "branch_name": "TOM MBOYA", "company": "NILA", "branch_num": 6},
    {"branchcode": "BR007", "branch_name": "NAKURU NILA", "company": "NILA", "branch_num": 7},
    {"branchcode": "BR011", "branch_name": "MOUNTAIN MALL", "company": "NILA", "branch_num": 11},
    {"branchcode": "BR014", "branch_name": "JUJA CITY MALL", "company": "NILA", "branch_num": 14},
    {"branchcode": "BR015", "branch_name": "ELDORET NILA", "company": "NILA", "branch_num": 15},
    {"branchcode": "BR016", "branch_name": "NILA JEWEL", "company": "NILA", "branch_num": 16},
    {"branchcode": "BR017", "branch_name": "LATEMA NILA", "company": "NILA", "branch_num": 17},
    {"branchcode": "BR018", "branch_name": "MEPALUX BRANCH", "company": "NILA", "branch_num": 18},
    {"branchcode": "BR020", "branch_name": "NILA RONGAI BRANCH", "company": "NILA", "branch_num": 20},
    {"branchcode": "BR021", "branch_name": "NILA MOI AVENUE", "company": "NILA", "branch_num": 21},
    {"branchcode": "BR023", "branch_name": "NILA MOMBASA BRANCH", "company": "NILA", "branch_num": 23}
]

# All branches combined
ALL_BRANCHES = DAIMA_BRANCHES + NILA_BRANCHES

# Branches that have GRN data (Goods Received Notes)
GRN_BRANCHES = [
    {"branchcode": "BR013", "branch_name": "DAIMA MERU WHOLESALE", "company": "DAIMA", "branch_num": 13}
]

# Branches that have Purchase Orders
PURCHASE_ORDER_BRANCHES = [
    {"branchcode": "BR008", "branch_name": "DAIMA MERU RETAIL", "company": "DAIMA", "branch_num": 8},
    {"branchcode": "BR009", "branch_name": "DAIMA THIKA RETAIL", "company": "DAIMA", "branch_num": 9},
    {"branchcode": "BR012", "branch_name": "DAIMA WHOLESALE THIKA", "company": "DAIMA", "branch_num": 12},
    {"branchcode": "BR013", "branch_name": "DAIMA MERU WHOLESALE", "company": "DAIMA", "branch_num": 13},
    {"branchcode": "BR022", "branch_name": "DAIMA MAKUTANO", "company": "DAIMA", "branch_num": 22},
    {"branchcode": "BR001", "branch_name": "BABA DOGO HQ", "company": "NILA", "branch_num": 1}
]

# Branches that have Branch Orders
BRANCH_ORDER_BRANCHES = ALL_BRANCHES  # All branches can have branch orders

# Branches that have Supplier Invoices
SUPPLIER_INVOICE_BRANCHES = [
    {"branchcode": "BR008", "branch_name": "DAIMA MERU RETAIL", "company": "DAIMA", "branch_num": 8},
    {"branchcode": "BR009", "branch_name": "DAIMA THIKA RETAIL", "company": "DAIMA", "branch_num": 9},
    {"branchcode": "BR012", "branch_name": "DAIMA WHOLESALE THIKA", "company": "DAIMA", "branch_num": 12},
    {"branchcode": "BR013", "branch_name": "DAIMA MERU WHOLESALE", "company": "DAIMA", "branch_num": 13},
    {"branchcode": "BR022", "branch_name": "DAIMA MAKUTANO", "company": "DAIMA", "branch_num": 22},
    {"branchcode": "BR001", "branch_name": "BABA DOGO HQ", "company": "NILA", "branch_num": 1}
]

def get_branches_for_company(company: str) -> list:
    """Get all branches for a specific company"""
    if company.upper() == "DAIMA":
        return DAIMA_BRANCHES
    elif company.upper() == "NILA":
        return NILA_BRANCHES
    else:
        return []

def get_branch_num(branch_code: str) -> int:
    """Extract branch number from branch code"""
    try:
        return int(branch_code.replace("BR", ""))
    except:
        return 0

