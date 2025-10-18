import json
import sys
import re
import math
from pathlib import Path


def load_or_create_json(path: Path, sample=None):
    """Load JSON from path. If file is missing and a sample is provided, create it and return the sample.
    If file is missing and no sample provided, raise FileNotFoundError.
    """
    if not path.exists():
        if sample is None:
            raise FileNotFoundError(f"Required file not found: {path}")
        path.write_text(json.dumps(sample, indent=2))
        print(f"Created sample file: {path}")
        return sample

    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


# Determine file paths; optional command-line overrides: <rfp_path> <product_path>
base_dir = Path(__file__).resolve().parent
rfp_path = Path(sys.argv[1]) if len(sys.argv) >= 2 else base_dir / 'rfp.json'
products_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else base_dir / 'product_data.json'

# Sample content used to create example files when missing
sample_rfp = {
    "specs_required": {
        "voltage": "230V",
        "conductor_material": "Copper",
        "nominal_size_sqmm": 10,
        "current_rating_ground_amps": 32,
        "cores": 3,
        "insulation_type": "PVC",
        "insulation_thickness_mm": 2
    }
}

sample_products = [
    {
        "sku": "CABLE-001",
        "specs": {
            "voltage": "230V",
            "conductor_material": "Copper",
            "nominal_size_sqmm": 10,
            "current_rating_ground_amps": 32,
            "cores": 3,
            "insulation_type": "PVC",
            "insulation_thickness_mm": 2
        }
    },
    {
        "sku": "CABLE-002",
        "specs": {
            "voltage": "400V",
            "conductor_material": "Aluminium",
            "nominal_size_sqmm": 16,
            "current_rating_ground_amps": 40,
            "cores": 4,
            "insulation_type": "XLPE",
            "insulation_thickness_mm": 1.5
        }
    },
    {
        "sku": "CABLE-003",
        "specs": {
            "voltage": "230V",
            "conductor_material": "Copper",
            "nominal_size_sqmm": 6,
            "current_rating_ground_amps": 20,
            "cores": 3,
            "insulation_type": "PVC",
            "insulation_thickness_mm": 1
        }
    }
]


# Load data (creates sample files if missing)
rfp_data = load_or_create_json(rfp_path, sample=sample_rfp)
products_data = load_or_create_json(products_path, sample=sample_products)

# The specific requirements we need to match against
rfp_specs = rfp_data.get('specs_required', {})

# Define weights for each specification. Higher number = more important.
SPEC_WEIGHTS = {
    "voltage": 3.0,                  # Critical deal-breaker
    "conductor_material": 2.5,       # Very important
    "nominal_size_sqmm": 2.0,        # Important for performance
    "current_rating_ground_amps": 1.5, # Important for safety/performance
    "cores": 1.0,                    # Basic requirement
    "insulation_type": 1.0,          # Basic requirement
    "insulation_thickness_mm": 0.5   # Less critical, nice-to-have
}

def calculate_match_score(product_specs, rfp_specs):
    """
    Calculates a weighted match score for a product against RFP requirements.
    """
    total_possible_score = 0
    achieved_score = 0

    # Helper: try to extract a numeric value from a string or number
    def to_number(v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
        if isinstance(v, str):
            m = re.search(r"[-+]?[0-9]*\.?[0-9]+", v.replace(',', ''))
            if m:
                try:
                    return float(m.group(0))
                except ValueError:
                    return None
        return None

    def parse_req(r):
        """Parse an RFP requirement into a typed requirement.
        Returns tuples like ('cmp', op, value), ('range', low, high), ('eq', value), ('eq_str', str), ('in', set)
        """
        if isinstance(r, (int, float)):
            return ('eq', float(r))
        if isinstance(r, list):
            return ('in', set([str(x).lower() for x in r]))
        if isinstance(r, str):
            s = r.strip()
            # comparator form: >=100, > 100, <= 50A, etc.
            m = re.match(r'^(>=|<=|>|<|==|=)\s*([-+]?[0-9]*\.?[0-9]+)', s)
            if m:
                op = m.group(1)
                val = float(m.group(2))
                return ('cmp', op, val)
            # range form: 50-100
            m = re.match(r'^([-+]?[0-9]*\.?[0-9]+)\s*-\s*([-+]?[0-9]*\.?[0-9]+)$', s)
            if m:
                low = float(m.group(1))
                high = float(m.group(2))
                return ('range', low, high)
            # plain numeric string
            m = re.match(r'^([-+]?[0-9]*\.?[0-9]+)$', s)
            if m:
                return ('eq', float(m.group(1)))
            # otherwise treat as a string to match
            return ('eq_str', s.lower())
        return ('unknown', r)

    def spec_match_fraction(prod_val, req_val):
        """Return fraction in [0,1] of how well prod_val satisfies req_val."""
        req = parse_req(req_val)
        rtype = req[0]
        # Numeric product value if possible
        pnum = to_number(prod_val)

        if rtype == 'cmp':
            _, op, threshold = req
            if pnum is None:
                return 0.0
            if op == '>':
                return 1.0 if pnum > threshold else 0.0
            if op == '>=':
                return 1.0 if pnum >= threshold else 0.0
            if op == '<':
                return 1.0 if pnum < threshold else 0.0
            if op == '<=':
                return 1.0 if pnum <= threshold else 0.0
            if op in ('=', '=='):
                return 1.0 if math.isclose(pnum, threshold, rel_tol=1e-9, abs_tol=1e-12) else 0.0

        if rtype == 'range':
            _, low, high = req
            if pnum is None:
                return 0.0
            return 1.0 if (low <= pnum <= high) else 0.0

        if rtype == 'eq':
            _, target = req
            if pnum is None:
                # compare as string
                return 1.0 if str(prod_val).lower() == str(target).lower() else 0.0
            # give partial credit based on closeness relative to target
            if target == 0:
                return 1.0 if math.isclose(pnum, 0.0, abs_tol=1e-12) else 0.0
            diff = abs(pnum - target)
            frac = max(0.0, 1.0 - (diff / abs(target)))
            return min(1.0, frac)

        if rtype == 'in':
            _, allowed = req
            if prod_val is None:
                return 0.0
            return 1.0 if str(prod_val).lower() in allowed else 0.0

        if rtype == 'eq_str':
            _, s = req
            if prod_val is None:
                return 0.0
            return 1.0 if str(prod_val).lower() == s else 0.0

        return 0.0

    # Loop through all the specs required by the RFP
    for spec_key, rfp_value in rfp_specs.items():
        # Get the weight for the current spec, default to 0 if not defined
        weight = SPEC_WEIGHTS.get(spec_key, 0)

        # Add the weight to the total possible score
        total_possible_score += weight

        # If product lacks the spec, it scores 0 for that spec
        if spec_key not in product_specs:
            continue

        prod_value = product_specs[spec_key]
        # Calculate a fractional match [0,1]
        frac = spec_match_fraction(prod_value, rfp_value)
        achieved_score += weight * frac

    # Calculate the final percentage score
    if total_possible_score == 0:
        return 0

    return (achieved_score / total_possible_score) * 100

# A list to store the results
results = []

# Iterate over each product in our catalog
for product in products_data:
    product_specs = product['specs']
    
    # Calculate the match score for the current product
    score = calculate_match_score(product_specs, rfp_specs)
    
    # Store the product's SKU and its calculated score
    results.append({
        "sku": product['sku'],
        "score": score
    })

# Sort the results in descending order based on the score
sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)

# Print the top 3 results
print("--- Top 3 Matches ---")
for i, result in enumerate(sorted_results[:3]):
    print(f"#{i+1}: SKU: {result['sku']}, Match Score: {result['score']:.2f}%")