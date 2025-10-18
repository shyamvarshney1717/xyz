import json
import re
import math
from pathlib import Path
import streamlit as st
import pandas as pd


# --- Robust JSON loading (create sample files if missing) ---
def load_or_create_json(path: Path, sample=None):
    if not path.exists():
        if sample is None:
            raise FileNotFoundError(f"Required file not found: {path}")
        path.write_text(json.dumps(sample, indent=2), encoding='utf-8')
        print(f"Created sample file: {path}")
        return sample
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


# Load data at the start (cache for Streamlit)
@st.cache_data
def load_data(rfp_file: str = None, products_file: str = None):
    base = Path(__file__).resolve().parent
    rfp_path = Path(rfp_file) if rfp_file else base / 'rfp.json'
    products_path = Path(products_file) if products_file else base / 'product_data.json'

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
        }
    ]

    rfp_data = load_or_create_json(rfp_path, sample=sample_rfp)
    products_data = load_or_create_json(products_path, sample=sample_products)
    return rfp_data.get('specs_required', {}), products_data

SPEC_WEIGHTS = {
    "voltage": 3.0,
    "conductor_material": 2.5,
    "nominal_size_sqmm": 2.0,
    "current_rating_ground_amps": 1.5,
    "cores": 1.0,
    "insulation_type": 1.0,
    "insulation_thickness_mm": 0.5
}

def calculate_match_score(product_specs, rfp_specs):
    """Return percentage score and a per-spec breakdown dict.
    Breakdown values are fractions in [0,1] indicating how well the spec matched.
    """
    total_possible_score = 0.0
    achieved_score = 0.0
    breakdown = {}

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
        if isinstance(r, (int, float)):
            return ('eq', float(r))
        if isinstance(r, list):
            return ('in', set([str(x).lower() for x in r]))
        if isinstance(r, str):
            s = r.strip()
            m = re.match(r'^(>=|<=|>|<|==|=)\s*([-+]?[0-9]*\.?[0-9]+)', s)
            if m:
                op = m.group(1)
                val = float(m.group(2))
                return ('cmp', op, val)
            m = re.match(r'^([-+]?[0-9]*\.?[0-9]+)\s*-\s*([-+]?[0-9]*\.?[0-9]+)$', s)
            if m:
                low = float(m.group(1))
                high = float(m.group(2))
                return ('range', low, high)
            m = re.match(r'^([-+]?[0-9]*\.?[0-9]+)$', s)
            if m:
                return ('eq', float(m.group(1)))
            return ('eq_str', s.lower())
        return ('unknown', r)

    def spec_match_fraction(prod_val, req_val):
        req = parse_req(req_val)
        rtype = req[0]
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
                return 1.0 if str(prod_val).lower() == str(target).lower() else 0.0
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

    for spec_key, rfp_value in rfp_specs.items():
        weight = SPEC_WEIGHTS.get(spec_key, 0)
        total_possible_score += weight
        if spec_key not in product_specs:
            breakdown[spec_key] = 0.0
            continue
        prod_value = product_specs[spec_key]
        frac = spec_match_fraction(prod_value, rfp_value)
        breakdown[spec_key] = frac
        achieved_score += weight * frac

    if total_possible_score == 0:
        return 0.0, breakdown
    return (achieved_score / total_possible_score) * 100.0, breakdown

def run_matching_algorithm():
    rfp_specs, products_data = load_data()
    results = []
    for product in products_data:
        score, breakdown = calculate_match_score(product['specs'], rfp_specs)
        results.append({
            "SKU": product['sku'],
            "Match Score (%)": f"{score:.1f}",
            "breakdown": breakdown,
            # Include product specs so the UI can display required vs product values per spec
            "product_specs": product.get('specs', {})
        })
    sorted_results = sorted(results, key=lambda x: float(x['Match Score (%)']), reverse=True)
    return sorted_results

# --- The Streamlit UI Code ---

st.set_page_config(layout="wide")
st.title("🤖 B2B RFP Automation Agent")
st.markdown("This tool uses a weighted algorithm to find the best product match for an RFP.")

# Create columns for layout
col1, col2 = st.columns(2)

with col1:
    st.header("RFP Requirements")
    # Display the RFP requirements (loaded from rfp.json)
    rfp_specs, _ = load_data()
    # Render RFP requirements as a clean table: Spec | Required Value | Weight
    rfp_rows = []
    for spec_key, required_value in rfp_specs.items():
        # If a weight exists for this spec, show it; otherwise leave blank
        weight = SPEC_WEIGHTS.get(spec_key)
        # Ensure values render nicely (convert complex types to string)
        display_value = required_value if isinstance(required_value, (str, int, float, bool)) else json.dumps(required_value)
        rfp_rows.append({
            'RFP Spec': spec_key,
            'Required Value': display_value,
            'Weight': weight if weight is not None else ''
        })

    if rfp_rows:
        st.table(pd.DataFrame(rfp_rows))
    else:
        st.info("No RFP requirements found. Provide an `rfp.json` with `specs_required`.")

with col2:
    st.header("Matching Results")
    # The "Analyze" button that triggers the code
    if st.button("▶️ Analyze RFP", type="primary"):
        # Run the matching algorithm
        top_matches = run_matching_algorithm()
        
        # Display the results in a nice table
        st.success(f"Analysis Complete! Found {len(top_matches)} potential matches.")
        
        # Build DataFrame for display but hide the internal 'breakdown' column
        df = pd.DataFrame(top_matches)
        if 'breakdown' in df.columns:
            # Keep breakdown data in the results list for the per-SKU expanders,
            # but remove it from the main table that users see.
            df = df.drop(columns=['breakdown'])

        # Ensure Match Score is numeric for styling. Convert safely and fill missing with 0.
        if 'Match Score (%)' in df.columns:
            df['Match Score (%)'] = pd.to_numeric(df['Match Score (%)'], errors='coerce').fillna(0.0)

        # Apply a green-to-red gradient where high scores are green and low scores red.
        # Use RdYlGn so low->high maps red->yellow->green.
        styler = df.style.format({
            'Match Score (%)': '{:.1f}'
        }).background_gradient(subset=['Match Score (%)'], cmap='RdYlGn', vmin=0, vmax=100)

        st.dataframe(styler, use_container_width=True)

        st.markdown("---")
        st.header("Per-SKU Breakdown")
        st.markdown("Click a SKU to see how each required spec contributed to the score.")
        # Show breakdown for top matches
        for result in top_matches[:20]:
            sku = result.get('SKU')
            score = result.get('Match Score (%)')
            breakdown = result.get('breakdown', {})
            product_specs = result.get('product_specs', {})
            with st.expander(f"{sku} — {score}%"):
                # Build a clear per-spec table: RFP Spec | Required Value | Product Value | Match? | Score Contribution (Weight)
                rows = []
                # iterate over the RFP's required specs so order and presence are consistent
                for spec_key, required_value in rfp_specs.items():
                    prod_value = product_specs.get(spec_key, '—')
                    frac = breakdown.get(spec_key, 0.0)
                    # Consider a spec matched if the fractional match is effectively 1.0 (allow small tolerance)
                    matched = True if frac >= 0.999 else False
                    # Weight display (if known)
                    weight = SPEC_WEIGHTS.get(spec_key, None)
                    weight_display = f"(Weight: {weight})" if weight is not None else ""

                    rows.append({
                        'RFP Spec': spec_key,
                        'Required Value': required_value,
                        'Product Value': prod_value,
                        'Match?': '✅' if matched else '❌',
                        'Score Contribution': weight_display
                    })

                if rows:
                    st.table(pd.DataFrame(rows))
                else:
                    st.write("No breakdown available for this SKU.")

    else:
        st.info("Click 'Analyze RFP' to see the results.")