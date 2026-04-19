from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from flask_mail import Mail, Message
from app.utils.helpers import safe_float
from app.models import User, Expense, Income, Loan, Asset, Insurance, TaxProfile
from app.utils.tax import calculate_tax
from datetime import date

main = Blueprint('main', __name__)

def get_mail():
    """Lazily import the mail object from app.py at request time."""
    from app.app import mail
    return mail


@main.app_errorhandler(Exception)
def handle_unexpected_error(e):
    """Global error handler to prevent full app crashes in production."""
    current_app.logger.error(f"Unhandled Exception: {e}")
    flash("An unexpected error occurred while processing your request. Please try again later.", "error")
    return redirect(url_for('main.login'))


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
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return redirect(url_for('main.signup'))

        existing = User.get_by_email(email)
        if existing:
            if not existing.get('is_verified'):
                # Resend OTP for incomplete signup
                otp = User.generate_and_store_otp(email)
                _send_otp_email(email, name, otp)
                session['otp_email'] = email
                flash('Account exists but is unverified. A new OTP has been sent.', 'warning')
                return redirect(url_for('main.verify_otp'))
            flash('Email already registered. Please log in.', 'error')
            return redirect(url_for('main.login'))

        # Create user (is_verified=False)
        User.create_user(name, email, password)

        # Generate + send OTP
        otp = User.generate_and_store_otp(email)
        _send_otp_email(email, name, otp)

        session['otp_email'] = email
        flash('Account created! Check your email for the 6-digit OTP.', 'success')
        return redirect(url_for('main.verify_otp'))

    return render_template('signup.html')


def _send_otp_email(email, name, otp):
    """Send OTP email – silently fails if mail not configured."""
    try:
        mail = get_mail()
        msg = Message(
            subject='Your FinanceTracker Verification Code',
            recipients=[email]
        )
        msg.html = f"""<div style='font-family:sans-serif;max-width:480px;margin:0 auto'>
            <h2 style='color:#4f46e5'>FinanceTracker Pro</h2>
            <p>Hi <strong>{name}</strong>,</p>
            <p>Your verification code is:</p>
            <div style='font-size:36px;font-weight:bold;letter-spacing:8px;color:#4f46e5;padding:16px;background:#f0f0ff;border-radius:8px;text-align:center'>{otp}</div>
            <p style='color:#6b7280;font-size:13px'>This code expires in <strong>5 minutes</strong>. Do not share it with anyone.</p>
        </div>"""
        mail.send(msg)
    except Exception as e:
        current_app.logger.warning(f'OTP email failed: {e}')


@main.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    email = session.get('otp_email')
    if not email:
        flash('Session expired. Please sign up again.', 'error')
        return redirect(url_for('main.signup'))

    if request.method == 'POST':
        digits = [request.form.get(f'd{i}', '') for i in range(1, 7)]
        otp_entered = ''.join(digits).strip()

        success, msg = User.verify_otp(email, otp_entered)
        if success:
            session.pop('otp_email', None)
            flash('Email verified! You can now log in.', 'success')
            return redirect(url_for('main.login'))
        else:
            flash(msg, 'error')
            return redirect(url_for('main.verify_otp'))

    return render_template('verify_otp.html', email=email)


@main.route('/resend-otp')
def resend_otp():
    email = session.get('otp_email')
    if not email:
        return redirect(url_for('main.signup'))
    user = User.get_by_email(email)
    if not user:
        return redirect(url_for('main.signup'))
    otp = User.generate_and_store_otp(email)
    _send_otp_email(email, user.get('name', ''), otp)
    flash('A new OTP has been sent to your email.', 'success')
    return redirect(url_for('main.verify_otp'))


@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        user = User.get_by_email(email)

        if not user or not User.verify_password(user['password'], password):
            flash('Please check your login details and try again.', 'error')
            return redirect(url_for('main.login'))

        # Block unverified accounts
        if not user.get('is_verified', False):
            session['otp_email'] = user['email']
            flash('Please verify your email before logging in.', 'warning')
            return redirect(url_for('main.verify_otp'))

        session['user_email'] = user['email']
        session['user_name']  = user['name']
        return redirect(url_for('main.profile'))

    return render_template('login.html')


@main.route('/logout')
def logout():
    session.pop('user_email', None)
    session.pop('user_name', None)
    session.pop('signup_email', None)
    return redirect(url_for('main.login'))


@main.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash('Email is required.', 'error')
            return redirect(url_for('main.forgot_password'))

        user = User.get_by_email(email)
        if not user:
            # Silently fail for security, but act like we sent it
            flash('If an account exists for that email, an OTP has been sent.', 'success')
            return redirect(url_for('main.login'))

        # Generate + send OTP
        otp = User.generate_and_store_otp(email)
        _send_otp_email(email, user.get('name', 'User'), otp)

        session['reset_email'] = email
        flash('Check your email for the 6-digit OTP to reset your password.', 'success')
        return redirect(url_for('main.verify_reset_otp'))

    return render_template('forgot_password.html')


@main.route('/verify_reset_otp', methods=['GET', 'POST'])
def verify_reset_otp():
    email = session.get('reset_email')
    if not email:
        flash('Session expired. Please restart the password reset process.', 'error')
        return redirect(url_for('main.forgot_password'))

    if request.method == 'POST':
        digits = [request.form.get(f'd{i}', '') for i in range(1, 7)]
        otp_entered = ''.join(digits).strip()

        success, msg = User.verify_otp(email, otp_entered)
        if success:
            session['reset_authorized'] = True
            flash('Email verified! You can now reset your password.', 'success')
            return redirect(url_for('main.reset_password'))
        else:
            flash(msg, 'error')
            return redirect(url_for('main.verify_reset_otp'))

    return render_template('verify_reset_otp.html', email=email)


@main.route('/resend_reset_otp')
def resend_reset_otp():
    email = session.get('reset_email')
    if not email:
        return redirect(url_for('main.forgot_password'))
    user = User.get_by_email(email)
    if not user:
        return redirect(url_for('main.forgot_password'))
    otp = User.generate_and_store_otp(email)
    _send_otp_email(email, user.get('name', ''), otp)
    flash('A new OTP has been sent to your email.', 'success')
    return redirect(url_for('main.verify_reset_otp'))


@main.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = session.get('reset_email')
    if not email or not session.get('reset_authorized'):
        flash('Unauthorized or session expired.', 'error')
        return redirect(url_for('main.forgot_password'))

    if request.method == 'POST':
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        if new_pw != confirm_pw:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('main.reset_password'))

        if len(new_pw) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('main.reset_password'))

        success, msg = User.force_reset_password(email, new_pw)
        if success:
            session.pop('reset_email', None)
            session.pop('reset_authorized', None)
            flash('Password has been reset successfully. You can now log in.', 'success')
            return redirect(url_for('main.login'))
        else:
            flash(msg, 'error')
            return redirect(url_for('main.reset_password'))

    return render_template('reset_password.html')


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
        salary = safe_float(request.form.get('salary'))
        monthly_spend = safe_float(request.form.get('monthly_spend'))
        savings = safe_float(request.form.get('savings'))

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
        Loan.add_loan(email, name, safe_float(principal_amount), safe_float(interest_rate), int(tenure_months))
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

    amount = safe_float(amount)

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

    amount = safe_float(amount)

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


# ──────────────────────────────────────────────
# Tax Calculator Routes
# ──────────────────────────────────────────────

@main.route('/tax', methods=['GET', 'POST'])
@login_required
def tax_calculator():
    email = session['user_email']
    user = User.get_by_email(email)
    
    # ── Smart Loan Interest Detection ──
    # Fetch all loans for the user and filter for 'home' or related terms
    total_home_loan_interest = 0
    user_loans = Loan.get_all(email)
    for loan in user_loans:
        name = loan.get("name", "").lower()
        if "home" in name or "house" in name or "housing" in name:
            # Approximate yearly interest if interest_paid_yearly is not stored
            # (remaining_balance * interest_rate / 100)
            yearly_interest = loan.get("interest_paid_yearly", loan.get("remaining_balance", 0) * (loan.get("interest_rate", 0) / 100))
            total_home_loan_interest += yearly_interest
            
    if request.method == 'POST':
        # Get data from form and calculate
        form_data = request.form.to_dict()
        
        # Determine final home loan interest based on manual vs auto toggle
        from app.utils.helpers import safe_float
        manual_interest = safe_float(form_data.get('home_loan_interest'))
        use_auto_loan = form_data.get('use_auto_loan') == 'on'
        
        if use_auto_loan:
            final_home_loan_interest = max(manual_interest, total_home_loan_interest)
        else:
            final_home_loan_interest = manual_interest
            
        form_data['home_loan_interest'] = final_home_loan_interest
        
        # Calculate tax
        tax_results = calculate_tax(form_data)
        
        # Save profile
        TaxProfile.save_profile(email, form_data)
        
        # Rerender with results
        return render_template('tax.html', user=user, data=form_data, results=tax_results, detected_home_loan_interest=total_home_loan_interest)
        
    else:
        # GET request
        # Fetch existing profile if any
        existing_profile = TaxProfile.get_profile(email, "2025-26")
        
        # Smart UX: Fetch insurance premiums if not already in profile
        total_life_premium = 0
        total_health_premium_self = 0
        
        if not existing_profile:
            policies = Insurance.get_all(email)
            for policy in policies:
                p_type = policy.get('policy_type', '').lower()
                premium = policy.get('premium', 0)
                if 'life' in p_type:
                    total_life_premium += premium
                elif 'health' in p_type or 'medical' in p_type:
                    total_health_premium_self += premium
                    
            existing_profile = {
                "salary": user.get('salary', 0),
                "insurance_details": {
                    "has_life_insurance": total_life_premium > 0,
                    "has_health_insurance": total_health_premium_self > 0,
                    "life_premium": total_life_premium,
                    "health_premium_self": total_health_premium_self
                }
            }

        return render_template('tax.html', user=user, data=existing_profile, results=None, detected_home_loan_interest=total_home_loan_interest)
