import re
import sys
import argparse
from collections import defaultdict

# === 1. Core Data and Chemical Constants ===

ATOMIC_WEIGHTS = {
    # Non-metals
    'H': 1.008, 'C': 12.011, 'N': 14.007, 'O': 15.999, 
    'Si': 28.085, 'P': 30.974, 'S': 32.06, 'Cl': 35.45, 
    'B': 10.81, 'F': 18.998, 'Br': 79.904, 'I': 126.90,
    # Alkali metals/alkaline earth metals
    'Li': 6.94, 'Na': 22.990, 'K': 39.098,
    'Mg': 24.305, 'Ca': 40.078, 'Sr': 87.62, 'Ba': 137.327,
    # Transition metals/other metal fuels
    'Al': 26.982, 'Fe': 55.845, 'Ti': 47.867, 'Zn': 65.38, 
    'Zr': 91.224, 'Cu': 63.546, 'Mn': 54.938, 'Pb': 207.2, 
    'Cr': 51.996, 'Sb': 121.76
}

# Oxygen consumption definition: How many oxygen atoms (O) are consumed 
# for complete combustion of 1 atom
# For example: C -> CO2 (consumes 2 O), Al -> Al2O3 (1 Al consumes 1.5 O)
OXYGEN_DEMAND = {
    # Basic organic
    'C': 2.0,   # -> CO2
    'H': 0.5,   # -> H2O
    'S': 2.0,   # -> SO2 (in OB calculation, SO2 formation is usually assumed)
    
    # Metal Fuels
    'Al': 1.5,  # -> Al2O3
    'Mg': 1.0,  # -> MgO
    'Ti': 2.0,  # -> TiO2
    'Zr': 2.0,  # -> ZrO2
    'Zn': 1.0,  # -> ZnO
    'Fe': 1.5,  # -> Fe2O3 (assuming iron(III) oxide formation)
    'Si': 2.0,  # -> SiO2
    'B':  1.5,  # -> B2O3
    'Sb': 1.5,  # -> Sb2O3 (or Sb2O5, depending on situation; using 1.5 here)

    # Salt base corrections (Oxidizer Bases)
    'K': 0.5,   # -> K2O
    'Na': 0.5,  # -> Na2O
    'Li': 0.5,  # -> Li2O
    'Ca': 1.0,  # -> CaO
    'Sr': 1.0,  # -> SrO
    'Ba': 1.0,  # -> BaO
    
    # Note: N, Cl, F, etc. are usually treated as 0 (produce N2, Cl2 without 
    # binding oxygen, or Cl抢夺 H but here only oxygen supply/demand is calculated)
}

def parse_formula(formula: str) -> dict:
    """Parse chemical formula and return element count dictionary."""
    pattern = re.compile(r'([A-Z][a-z]*)(\d*)')
    matches = pattern.findall(formula)
    
    if not matches and formula.strip():
        raise ValueError(f"Cannot parse formula '{formula}'")
    
    atom_counts = defaultdict(int)
    
    for element, count_str in matches:
        if element not in ATOMIC_WEIGHTS:
            raise ValueError(f"Unknown element: '{element}' (please update atomic weight table)")
        count = int(count_str) if count_str else 1
        atom_counts[element] += count

    if not atom_counts:
        raise ValueError(f"Cannot extract valid elements from '{formula}'")
        
    return dict(atom_counts)

def calculate_mw(atom_counts: dict) -> float:
    """Calculate molecular weight (g/mol)"""
    return sum(ATOMIC_WEIGHTS[el] * count for el, count in atom_counts.items())

def calculate_ob_percent(atom_counts: dict, mw: float) -> float:
    """
    Universal oxygen balance calculation logic
    OB% = (Total_Oxygen - Total_Oxygen_Demand) * 16.00 / MW * 100
    """
    if mw == 0: return 0.0

    moles_o_available = atom_counts.get('O', 0)
    moles_o_required = 0.0
    
    for element, count in atom_counts.items():
        if element == 'O': 
            continue # Oxygen itself does not consume oxygen
        
        # Look up oxygen consumption coefficient for this element; 
        # if not defined, assume 0 (e.g., N, Cl)
        demand_factor = OXYGEN_DEMAND.get(element, 0.0)
        moles_o_required += demand_factor * count
    
    # Net oxygen amount (positive = excess, negative = deficit)
    net_oxygen_moles = moles_o_available - moles_o_required
    
    return net_oxygen_moles * 15.999 / mw * 100

# === 2. Core Function: Mixture Calculation and Auto-Balancing ===

def solve_binary_stoichiometry(formulas: list, target_ob: float = 0.0):
    """Core algorithm: Calculate the ratio of two substances to achieve target OB."""
    if len(formulas) != 2:
        print("Error: Auto-balancing currently supports only **2** components (e.g., oxidizer + metal fuel).")
        return

    comps = []
    for f in formulas:
        counts = parse_formula(f)
        mw = calculate_mw(counts)
        ob = calculate_ob_percent(counts, mw)
        comps.append({'formula': f, 'ob': ob, 'mw': mw})

    c1, c2 = comps[0], comps[1]
    
    print(f"\n{'='*15} Auto-Stoichiometry Analysis {'='*15}")
    print(f"Target OB%: {target_ob}")
    print(f"Component 1: {c1['formula']:<12} (OB: {c1['ob']:+.2f}%)")
    print(f"Component 2: {c2['formula']:<12} (OB: {c2['ob']:+.2f}%)")
    print("-" * 55)

    if (c1['ob'] > target_ob and c2['ob'] > target_ob) or \
       (c1['ob'] < target_ob and c2['ob'] < target_ob):
        print(f"Warning: Cannot balance. Both components' OB are on the same side of the target value.")
        return

    if c1['ob'] == c2['ob']:
        print("Error: The two components have the same oxygen balance value.")
        return

    # x * ob1 + (1-x) * ob2 = target => x = (target - ob2) / (ob1 - ob2)
    x = (target_ob - c2['ob']) / (c1['ob'] - c2['ob'])
    ratio_c1 = x * 100
    ratio_c2 = (1 - x) * 100

    print(f"OPTIMAL RATIO (Mass %):")
    print(f"  {c1['formula']}: {ratio_c1:.2f}%")
    print(f"  {c2['formula']}: {ratio_c2:.2f}%")
    
    # Add metal fuel reminder
    if 'Al' in c1['formula'] or 'Mg' in c1['formula'] or 'Ti' in c1['formula'] or \
       'Al' in c2['formula'] or 'Mg' in c2['formula'] or 'Ti' in c2['formula']:
        print("-" * 55)
        print("Note: Metal fuel formulas are usually designed with slightly negative oxygen balance (-5% ~ -10%)")
        print("      to maximize heat of formation and reduce oxide dead weight.")

    print("-" * 55)
    print(f'Quick Input: "{c1["formula"]}:{ratio_c1:.2f} {c2["formula"]}:{ratio_c2:.2f}"')

# === 3. Input Parsing Utilities (unchanged) ===

def parse_line_data(line: str) -> tuple:
    line = line.split('#')[0].strip()
    if not line: return None
    if ':' not in line and '=' not in line:
        parts = line.split()
        if len(parts) == 1: return (parts[0].strip(), 1.0)
        if len(parts) == 2:
             try: return (parts[0].strip(), float(parts[1]))
             except: pass
    separator = ':' if ':' in line else '='
    parts = line.split(separator)
    if len(parts) != 2: return (line.strip(), 0.0)
    return (parts[0].strip(), float(parts[1].strip()))

def load_from_file(filepath: str) -> list:
    data = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    res = parse_line_data(line)
                    if res: data.append(res)
                except ValueError: pass
    except FileNotFoundError:
        sys.exit(f"Error: File {filepath} not found.")
    return data

def parse_cli_string(input_str: str) -> list:
    raw = re.split(r'[,\s]+', input_str.strip())
    data = []
    for r in raw:
        if r:
            try:
                res = parse_line_data(r)
                if res: data.append(res)
            except ValueError: pass
    return data

def process_mixture(components: list):
    if not components: return
    print(f"\n{'='*20} Calculation Results {'='*20}")
    total_prop = sum(p for _, p in components)
    if total_prop <= 0: return

    aggregated = defaultdict(lambda: {'prop': 0.0, 'mw': 0.0, 'ob': 0.0})
    for f, p in components:
        counts = parse_formula(f)
        mw = calculate_mw(counts)
        ob = calculate_ob_percent(counts, mw)
        aggregated[f]['mw'] = mw
        aggregated[f]['ob'] = ob
        aggregated[f]['prop'] += p

    mix_ob = 0.0
    print(f"{'Component':<15} | {'MW (g/mol)':<12} | {'OB%':<8} | {'Mass %':<10}")
    print("-" * 60)
    for f, d in aggregated.items():
        mass_pct = (d['prop'] / total_prop) * 100
        mix_ob += (d['prop'] / total_prop) * d['ob']
        print(f"{f:<15} | {d['mw']:<12.3f} | {d['ob']:<+8.2f} | {mass_pct:<10.2f}%")
    print("-" * 60)
    print(f"Mixture OB%: {mix_ob:+.4f}%")

# === 4. Main Program Entry Point ===

def main():
    parser = argparse.ArgumentParser(description="Chemist's OB Calculator (Metals Supported: Al, Mg, Ti, Fe, Zn, Zr)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--input', type=str, help='Calculate mix: "KClO4:65 Al:35"')
    group.add_argument('-f', '--file', type=str, help='Read mix from file')
    group.add_argument('-opt', '--optimize', type=str, help='Auto-balance: "Fe2O3 Al" (Thermite)')

    parser.add_argument('-t', '--target', type=float, default=0.0, help='Target OB% for optimization')

    args = parser.parse_args()

    if args.optimize:
        raw_data = parse_cli_string(args.optimize)
        formula_list = [item[0] for item in raw_data]
        solve_binary_stoichiometry(formula_list, args.target)
    else:
        data = []
        if args.file:
            data = load_from_file(args.file)
        elif args.input:
            data = parse_cli_string(args.input)
        process_mixture(data)

if __name__ == "__main__":
    main()
