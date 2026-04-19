from utils.helpers import safe_float

def calculate_tax(data):
    """
    Calculates tax liability based on the Old and New regime for FY 2025-26.
    Returns a dictionary containing breakdown and total tax for both regimes.
    """
    salary = safe_float(data.get('salary'))
    other_income = safe_float(data.get('other_income'))
    total_income = salary + other_income

    # Deductions data
    section_80c = safe_float(data.get('section_80C'))
    life_insurance_premium = safe_float(data.get('life_premium'))
    
    health_premium_self = safe_float(data.get('health_premium_self'))
    health_premium_parents = safe_float(data.get('health_premium_parents'))
    parents_senior = data.get('parents_senior') in [True, 'on', 'true', '1']
    
    home_loan_interest = safe_float(data.get('home_loan_interest'))
    hra = safe_float(data.get('hra'))

    # --- OLD REGIME CALCULATION ---
    # 1. 80C Limit: Max 1.5 Lakhs combined
    deduction_80c = min(150000.0, section_80c + life_insurance_premium)

    # 2. 80D Limit: Health Insurance
    deduction_80d_self = min(25000.0, health_premium_self)
    limit_parents = 50000.0 if parents_senior else 25000.0
    deduction_80d_parents = min(limit_parents, health_premium_parents)
    total_80d = deduction_80d_self + deduction_80d_parents

    # 3. Standard Deduction
    standard_deduction = 50000.0

    # Total Deductions for Old Regime
    total_deductions_old = deduction_80c + total_80d + home_loan_interest + hra + standard_deduction
    
    taxable_income_old = max(0.0, total_income - total_deductions_old)
    
    # Old Regime Slabs (AY 2025-26 approximation)
    tax_old = 0.0
    if taxable_income_old <= 250000:
        tax_old = 0
    elif taxable_income_old <= 500000:
        tax_old = (taxable_income_old - 250000) * 0.05
    elif taxable_income_old <= 1000000:
        tax_old = 12500 + (taxable_income_old - 500000) * 0.20
    else:
        tax_old = 112500 + (taxable_income_old - 1000000) * 0.30

    # 87A Rebate for Old Regime (up to 5L taxable income = 12500 rebate)
    if taxable_income_old <= 500000:
        tax_old = max(0.0, tax_old - 12500)

    # Add 4% Cess
    tax_old_total = tax_old * 1.04

    # --- NEW REGIME CALCULATION ---
    # Only standard deduction applies
    total_deductions_new = standard_deduction
    taxable_income_new = max(0.0, total_income - total_deductions_new)

    # New Regime Slabs (AY 2025-26)
    tax_new = 0.0
    if taxable_income_new <= 300000:
        tax_new = 0
    elif taxable_income_new <= 600000:
        tax_new = (taxable_income_new - 300000) * 0.05
    elif taxable_income_new <= 900000:
        tax_new = 15000 + (taxable_income_new - 600000) * 0.10
    elif taxable_income_new <= 1200000:
        tax_new = 45000 + (taxable_income_new - 900000) * 0.15
    elif taxable_income_new <= 1500000:
        tax_new = 90000 + (taxable_income_new - 1200000) * 0.20
    else:
        tax_new = 150000 + (taxable_income_new - 1500000) * 0.30

    # 87A Rebate for New Regime (up to 7L taxable income = 25000 rebate)
    if taxable_income_new <= 700000:
        tax_new = max(0.0, tax_new - 25000)

    # Add 4% Cess
    tax_new_total = tax_new * 1.04

    return {
        "total_income": total_income,
        "old_regime": {
            "deductions": total_deductions_old,
            "deduction_breakdown": {
                "section_80c": deduction_80c,
                "section_80d": total_80d,
                "home_loan_interest": home_loan_interest,
                "hra": hra,
                "standard": standard_deduction
            },
            "taxable_income": taxable_income_old,
            "tax": tax_old_total
        },
        "new_regime": {
            "deductions": total_deductions_new,
            "deduction_breakdown": {
                "standard": standard_deduction
            },
            "taxable_income": taxable_income_new,
            "tax": tax_new_total
        },
        "suggested_regime": "old" if tax_old_total <= tax_new_total else "new",
        "savings": abs(tax_old_total - tax_new_total)
    }
