from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import User, Expense, Income, Loan, Asset, Insurance
from datetime import date

main = Blueprint('main', __name__)


# ──────────────────────────────────────────────
# Auth helper – protects routes that need login
# ──────────────────────────────────────────────
def login_required(f):
    """Decorator that redirects to login if there is no active session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            flash('Please log in to access that page.', 'error')
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function


# ──────────────────────────────────────────────
# Core auth routes
# ──────────────────────────────────────────────
@main.route('/')
def index():
    if 'user_email' in session:
        return redirect(url_for('main.profile'))
    return redirect(url_for('main.login'))


@main.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        # Basic validation
        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return redirect(url_for('main.signup'))

        # Check if user exists
        if User.get_by_email(email):
            flash('Email already exists.', 'error')
            return redirect(url_for('main.signup'))

        # Create user
        User.create_user(name, email, password)
        session['signup_email'] = email
        return redirect(url_for('main.verify_email'))

    return render_template('signup.html')


@main.route('/verify-email')
def verify_email():
    email = session.get('signup_email')
    if not email:
        return redirect(url_for('main.signup'))
    return render_template('verify_email.html', email=email)


@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.get_by_email(email)

        # Check password
        if not user or not User.verify_password(user['password'], password):
            flash('Please check your login details and try again.', 'error')
            return redirect(url_for('main.login'))

        # Login success
        session['user_email'] = user['email']
        session['user_name'] = user['name']
        return redirect(url_for('main.profile'))

    return render_template('login.html')


@main.route('/logout')
def logout():
    session.pop('user_email', None)
    session.pop('user_name', None)
    session.pop('signup_email', None)
    return redirect(url_for('main.login'))


@main.route('/edit_profile', methods=['POST'])
@login_required
def edit_profile():
    email = session['user_email']
    name = request.form.get('name', '').strip()
    age = request.form.get('age', '').strip()
    education = request.form.get('education', '').strip()
    job_title = request.form.get('job_title', '').strip()
    company = request.form.get('company', '').strip()

    if not name:
        flash('Name cannot be empty.', 'error')
        return redirect(url_for('main.user_profile'))

    User.update_profile(email, name, age, education, job_title, company)
    session['user_name'] = name  # keep session in sync
    flash('Profile updated successfully.', 'success')
    return redirect(url_for('main.user_profile'))


@main.route('/change_email', methods=['POST'])
@login_required
def change_email():
    old_email = session['user_email']
    new_email = request.form.get('new_email', '').strip().lower()

    if not new_email:
        flash('New email cannot be empty.', 'error')
        return redirect(url_for('main.user_profile'))

    success, result = User.change_email(old_email, new_email)
    if success:
        session['user_email'] = result
        flash('Email changed successfully. Please note your new login email.', 'success')
    else:
        flash(result, 'error')
    return redirect(url_for('main.user_profile'))


@main.route('/change_password', methods=['POST'])
@login_required
def change_password():
    email = session['user_email']
    old_pw = request.form.get('old_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    if new_pw != confirm_pw:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('main.user_profile'))

    if len(new_pw) < 6:
        flash('New password must be at least 6 characters.', 'error')
        return redirect(url_for('main.user_profile'))

    success, msg = User.change_password(email, old_pw, new_pw)
    flash(msg, 'success' if success else 'error')
    return redirect(url_for('main.user_profile'))


@main.route('/user_profile')
@login_required
def user_profile():
    user = User.get_by_email(session['user_email'])
    return render_template('user_profile.html', user=user)


# ──────────────────────────────────────────────
# Profile / Dashboard
# ──────────────────────────────────────────────
@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    email = session['user_email']
    user = User.get_by_email(email)

    if request.method == 'POST':
        salary = float(request.form.get('salary', 0) or 0)
        monthly_spend = float(request.form.get('monthly_spend', 0) or 0)
        savings = float(request.form.get('savings', 0) or 0)

        User.update_financials(email, salary, monthly_spend, savings)
        flash('Financial details updated successfully.', 'success')
        return redirect(url_for('main.profile'))

    # Get filter parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category_filter = request.args.get('category')
    # If category is "All", treat as no filter
    if category_filter == 'All':
        category_filter = None

    # Fetch all expenses & income for this user with optional filters
    expenses = Expense.get_all(email, category=category_filter, start_date=start_date, end_date=end_date)
    incomes  = Income.get_all(email, start_date=start_date, end_date=end_date)

    total_expenses = Expense.get_total(email, category=category_filter, start_date=start_date, end_date=end_date)
    total_income   = Income.get_total(email, start_date=start_date, end_date=end_date)
    
    # Get the category breakdown for expenses
    category_breakdown = Expense.get_category_breakdown(email, start_date=start_date, end_date=end_date)

    # Net balance = total income - total expenses
    net_balance = total_income - total_expenses
    
    # Total loan liability
    total_liability = Loan.get_total_liability(email)

    # Legacy summary calc
    net_remaining = user.get('salary', 0) - user.get('monthly_spend', 0) - user.get('savings', 0)

    # Calculate Budget Progress
    budget_limit = user.get('monthly_spend', 0)
    budget_progress = 0
    if budget_limit > 0:
        budget_progress = (total_expenses / budget_limit) * 100
        budget_progress = min(budget_progress, 100) # cap at 100% for progress bar

    # Generate Chart Data (Pie Chart - Expense Breakdown)
    pie_labels = [cb['_id'] for cb in category_breakdown]
    pie_data = [cb['total'] for cb in category_breakdown]
    
    # Generate Chart Data (Line Chart - Spending Over Time)
    # Group expenses by date
    spending_over_time = {}
    for exp in reversed(expenses): # reverse to get oldest to newest for chronological plotting
        date_val = exp['date']
        spending_over_time[date_val] = spending_over_time.get(date_val, 0) + exp['amount']
    
    line_labels = list(spending_over_time.keys())
    line_data = list(spending_over_time.values())

    # Generate Smart Insights
    insights = []
    if budget_limit > 0:
        if total_expenses > budget_limit:
            insights.append({"type": "danger", "message": f"You have exceeded your monthly spending budget by ${total_expenses - budget_limit:,.2f}!"})
        elif budget_progress > 90:
            insights.append({"type": "warning", "message": "Warning: You are very close to your monthly spending limit."})
        elif budget_progress > 75:
            insights.append({"type": "warning", "message": "You have spent over 75% of your budget. Keep an eye on expenses."})
        else:
            insights.append({"type": "success", "message": "You are well within your budget limit. Great job!"})

    if category_breakdown and category_breakdown[0]['total'] > 0:
        top_cat = category_breakdown[0]
        percent = (top_cat['total'] / total_expenses) * 100 if total_expenses > 0 else 0
        insights.append({"type": "info", "message": f"Your highest spending category is '{top_cat['_id']}', making up {percent:.1f}% of your total expenses."})

    if total_expenses == 0 and total_income == 0:
        insights.append({"type": "info", "message": "Welcome! Add some income and expenses to start seeing insights."})

    total_assets = Asset.get_total_value(user['email'])

    return render_template(
        'profile.html',
        user=user,
        net_remaining=net_remaining,
        expenses=expenses,
        incomes=incomes,
        total_expenses=total_expenses,
        total_income=total_income,
        net_balance=net_balance,
        category_breakdown=category_breakdown,
        today=date.today().isoformat(),
        budget_progress=budget_progress,
        budget_limit=budget_limit,
        pie_labels=pie_labels,
        pie_data=pie_data,
        line_labels=line_labels,
        line_data=line_data,
        insights=insights,
        current_filters={'start_date': start_date, 'end_date': end_date, 'category': category_filter},
        total_liability=total_liability,
        total_assets=total_assets
    )


# ──────────────────────────────────────────────
# Loan Routes
# ──────────────────────────────────────────────

@main.route('/loans')
@login_required
def loans():
    email = session['user_email']
    user = User.get_by_email(email)
    loans_list = Loan.get_all(email)
    total_liability = Loan.get_total_liability(email)
    return render_template('loans.html', user=user, loans=loans_list, total_liability=total_liability)


@main.route('/add_loan', methods=['POST'])
@login_required
def add_loan():
    email = session['user_email']
    name = request.form.get('name')
    principal_amount = request.form.get('principal_amount')
    interest_rate = request.form.get('interest_rate')
    tenure_months = request.form.get('tenure_months')
    
    if not all([name, principal_amount, interest_rate, tenure_months]):
        flash('All fields are required to add a loan.', 'error')
        return redirect(url_for('main.loans'))
        
    try:
        Loan.add_loan(email, name, float(principal_amount), float(interest_rate), int(tenure_months))
        flash('Loan added successfully.', 'success')
    except Exception as e:
        flash(f'Error adding loan: {e}', 'error')
        
    return redirect(url_for('main.loans'))


@main.route('/pay_loan/<loan_id>', methods=['POST'])
@login_required
def pay_loan(loan_id):
    email = session['user_email']
    
    try:
        success, message = Loan.pay_emi(loan_id, email)
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
    except Exception as e:
        flash(f'Error processing payment: {e}', 'error')
        
    return redirect(url_for('main.loans'))


# ──────────────────────────────────────────────
# Expense routes
# ──────────────────────────────────────────────
@main.route('/expenses/add', methods=['POST'])
@login_required
def add_expense():
    """Add a new expense for the logged-in user."""
    amount   = request.form.get('amount')
    category = request.form.get('category')
    date_str = request.form.get('date')

    if not amount or not category or not date_str:
        flash('All expense fields are required.', 'error')
        return redirect(url_for('main.profile'))

    try:
        amount = float(amount)
    except ValueError:
        flash('Amount must be a valid number.', 'error')
        return redirect(url_for('main.profile'))

    Expense.add_expense(session['user_email'], amount, category, date_str)
    flash('Expense added successfully.', 'success')
    return redirect(url_for('main.profile'))


@main.route('/expenses/delete/<expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    """Delete an expense belonging to the logged-in user."""
    deleted = Expense.delete(expense_id, session['user_email'])
    if deleted:
        flash('Expense deleted.', 'success')
    else:
        flash('Expense not found or access denied.', 'error')
    return redirect(url_for('main.profile'))


# ──────────────────────────────────────────────
# Income routes
# ──────────────────────────────────────────────
@main.route('/income/add', methods=['POST'])
@login_required
def add_income():
    """Add a new income entry for the logged-in user."""
    amount   = request.form.get('amount')
    source   = request.form.get('source')
    date_str = request.form.get('date')

    if not amount or not source or not date_str:
        flash('All income fields are required.', 'error')
        return redirect(url_for('main.profile'))

    try:
        amount = float(amount)
    except ValueError:
        flash('Amount must be a valid number.', 'error')
        return redirect(url_for('main.profile'))

    Income.add_income(session['user_email'], amount, source, date_str)
    flash('Income added successfully.', 'success')
    return redirect(url_for('main.profile'))


@main.route('/income/delete/<income_id>', methods=['POST'])
@login_required
def delete_income(income_id):
    """Delete an income entry belonging to the logged-in user."""
    deleted = Income.delete(income_id, session['user_email'])
    if deleted:
        flash('Income entry deleted.', 'success')
    else:
        flash('Income entry not found or access denied.', 'error')
    return redirect(url_for('main.profile'))

# ──────────────────────────────────────────────
# Assets Routes
# ──────────────────────────────────────────────

@main.route('/assets', methods=['GET'])
@login_required
def assets():
    email = session['user_email']
    user_assets = Asset.get_all(email)
    total_assets = Asset.get_total_value(email)
    
    # Fetch user loans to populate the "Link Loan" dropdown
    user_loans = Loan.get_all(email)
    
    return render_template('assets.html', assets=user_assets, total_assets=total_assets, loans=user_loans)

@main.route('/add_asset', methods=['POST'])
@login_required
def add_asset():
    email = session['user_email']
    category = request.form.get('category')
    value = request.form.get('value')
    
    # Extract dynamic arbitrary form fields (filtering out standard UI fields)
    ignored_keys = {'category', 'value', 'submit'}
    dynamic_kwargs = {k: v for k, v in request.form.items() if k not in ignored_keys and v}

    try:
        Asset.add_asset(email, category, value, **dynamic_kwargs)
        flash('Asset added successfully.', 'success')
    except Exception as e:
        flash(f'Error adding asset: {str(e)}', 'error')

    return redirect(url_for('main.assets'))

@main.route('/sell_asset/<asset_id>', methods=['POST'])
@login_required
def sell_asset(asset_id):
    email = session['user_email']
    sold_price = request.form.get('sold_price')
    sold_date = request.form.get('sold_date')
    notes = request.form.get('notes', '')

    try:
        success, profit = Asset.sell_asset(asset_id, email, sold_price, sold_date, notes)
        if success:
            if profit < 0:
                flash(f'Asset Sold. Warning: You took a cash hit of ${abs(profit):,.2f} because the loan balance was larger than the sale price. Income adjusted.', 'warning')
            else:
                flash(f'Asset Sold successfully! ${profit:,.2f} cash was mapped to your Income after loan payments.', 'success')
        else:
            flash(f'Could not sell asset: {profit}', 'danger')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('main.assets'))

# ──────────────────────────────────────────────
# Insurance Routes
# ──────────────────────────────────────────────

@main.route('/insurance', methods=['GET'])
@login_required
def insurance():
    email = session['user_email']
    user_policies = Insurance.get_all(email)
    total_cash_value = Insurance.get_total_cash_value(email)
    
    return render_template('insurance.html', policies=user_policies, total_cash_value=total_cash_value)

@main.route('/add_insurance', methods=['POST'])
@login_required
def add_insurance():
    email = session['user_email']
    policy_type = request.form.get('policy_type')
    provider = request.form.get('provider')
    premium = request.form.get('premium')
    coverage = request.form.get('coverage')
    next_due_date = request.form.get('next_due_date')
    billing_cycle = request.form.get('billing_cycle')
    has_cash_value = request.form.get('has_cash_value')
    cash_value = request.form.get('cash_value', 0)

    try:
        Insurance.add_policy(email, policy_type, provider, premium, coverage, next_due_date, billing_cycle, has_cash_value, cash_value)
        flash('Insurance policy created! Initial premium has been logged as an Expense.', 'success')
    except Exception as e:
        flash(f'Error logging insurance: {str(e)}', 'error')

    return redirect(url_for('main.insurance'))

@main.route('/pay_insurance_premium/<policy_id>', methods=['POST'])
@login_required
def pay_insurance_premium(policy_id):
    email = session['user_email']
    
    try:
        success, msg = Insurance.pay_premium(policy_id, email)
        if success:
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
    except Exception as e:
        flash(f'Error processing premium payment: {str(e)}', 'danger')
        
    return redirect(url_for('main.insurance'))

@main.route('/edit_asset/<asset_id>', methods=['POST'])
@login_required
def edit_asset(asset_id):
    email = session['user_email']
    # Grab all form data and pass as a dict — the model handles filtering protected keys
    updated_fields = dict(request.form)
    # Flatten single-item lists from ImmutableMultiDict
    updated_fields = {k: v[0] if isinstance(v, list) else v for k, v in updated_fields.items()}
    
    try:
        Asset.update_asset(asset_id, email, updated_fields)
        flash('Asset updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating asset: {str(e)}', 'error')

    return redirect(url_for('main.assets'))

@main.route('/edit_insurance/<policy_id>', methods=['POST'])
@login_required
def edit_insurance(policy_id):
    email = session['user_email']
    updated_fields = dict(request.form)
    updated_fields = {k: v[0] if isinstance(v, list) else v for k, v in updated_fields.items()}
    
    try:
        Insurance.update_policy(policy_id, email, updated_fields)
        flash('Insurance policy updated successfully.', 'success')
    except Exception as e:
        flash(f'Error updating policy: {str(e)}', 'error')

    return redirect(url_for('main.insurance'))
