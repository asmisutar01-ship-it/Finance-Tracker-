from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import random
import string


class User:
    @staticmethod
    def create_user(name, email, password):
        db = get_db()
        hashed_password = generate_password_hash(password)
        user_doc = {
            "name": name,
            "email": email.lower(),
            "password": hashed_password,
            "age": None,
            "education": "",
            "job_title": "",
            "company": "",
            "salary": 0,
            "monthly_spend": 0,
            "savings": 0,
            "is_verified": False,   # must verify via OTP
            "otp": None,
            "otp_expiry": None
        }
        db.users.insert_one(user_doc)
        return user_doc

    @staticmethod
    def get_by_email(email):
        db = get_db()
        return db.users.find_one({"email": email.lower()})

    @staticmethod
    def verify_password(stored_password_hash, provided_password):
        return check_password_hash(stored_password_hash, provided_password)

    @staticmethod
    def generate_and_store_otp(email):
        """Create a 6-digit OTP, store it hashed in DB, return plaintext OTP."""
        db = get_db()
        otp_plain = ''.join(random.choices(string.digits, k=6))
        otp_hash  = generate_password_hash(otp_plain)
        expiry    = datetime.utcnow() + timedelta(minutes=5)
        db.users.update_one(
            {"email": email.lower()},
            {"$set": {"otp": otp_hash, "otp_expiry": expiry}}
        )
        return otp_plain

    @staticmethod
    def verify_otp(email, otp_provided):
        """Returns (True, '') on success or (False, reason) on failure."""
        db = get_db()
        user = db.users.find_one({"email": email.lower()})
        if not user:
            return False, "User not found."
        if user.get("is_verified"):
            return True, "already_verified"
        if not user.get("otp") or not user.get("otp_expiry"):
            return False, "No OTP found. Please request a new one."
        if datetime.utcnow() > user["otp_expiry"]:
            return False, "OTP has expired. Please request a new one."
        if not check_password_hash(user["otp"], otp_provided.strip()):
            return False, "Incorrect OTP. Please try again."
        # Mark verified and clear OTP
        db.users.update_one(
            {"email": email.lower()},
            {"$set": {"is_verified": True, "otp": None, "otp_expiry": None}}
        )
        return True, "verified"



    @staticmethod
    def update_profile(email, name, age, education, job_title, company):
        db = get_db()
        update_data = {
            "name": name.strip(),
            "education": education.strip(),
            "job_title": job_title.strip(),
            "company": company.strip(),
        }
        if age:
            try:
                update_data["age"] = int(age)
            except ValueError:
                pass
        db.users.update_one({"email": email.lower()}, {"$set": update_data})

    @staticmethod
    def change_email(old_email, new_email):
        db = get_db()
        existing = db.users.find_one({"email": new_email.lower()})
        if existing:
            return False, "That email is already in use."
        db.users.update_one({"email": old_email.lower()}, {"$set": {"email": new_email.lower()}})
        return True, new_email.lower()

    @staticmethod
    def change_password(email, old_password, new_password):
        db = get_db()
        user = db.users.find_one({"email": email.lower()})
        if not user or not check_password_hash(user['password'], old_password):
            return False, "Current password is incorrect."
        db.users.update_one(
            {"email": email.lower()},
            {"$set": {"password": generate_password_hash(new_password)}}
        )
        return True, "Password changed successfully."

    @staticmethod
    def force_reset_password(email, new_password):
        db = get_db()
        db.users.update_one(
            {"email": email.lower()},
            {"$set": {"password": generate_password_hash(new_password)}}
        )
        return True, "Password reset successfully."

    @staticmethod
    def update_financials(email, salary, monthly_spend, savings):
        db = get_db()
        db.users.update_one(
            {"email": email.lower()},
            {"$set": {
                "salary": salary,
                "monthly_spend": monthly_spend,
                "savings": savings
            }}
        )

class Expense:
    @staticmethod
    def add_expense(user_email, amount, category, date_str):
        db = get_db()
        expense_doc = {
            "user_email": user_email.lower(),
            "amount": float(amount),
            "category": category,
            "date": date_str
        }
        result = db.expenses.insert_one(expense_doc)
        expense_doc['_id'] = result.inserted_id
        return expense_doc

    @staticmethod
    def get_all(user_email, category=None, start_date=None, end_date=None):
        db = get_db()
        query = {"user_email": user_email.lower()}
        if category:
            query["category"] = category
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["date"] = date_query
        return list(db.expenses.find(query).sort("date", -1))

    @staticmethod
    def delete(expense_id, user_email):
        db = get_db()
        if isinstance(expense_id, str):
            expense_id = ObjectId(expense_id)
        result = db.expenses.delete_one({"_id": expense_id, "user_email": user_email.lower()})
        return result.deleted_count > 0

    @staticmethod
    def get_total(user_email, category=None, start_date=None, end_date=None):
        db = get_db()
        match_query = {"user_email": user_email.lower()}
        if category:
            match_query["category"] = category
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            match_query["date"] = date_query

        pipeline = [
            {"$match": match_query},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        result = list(db.expenses.aggregate(pipeline))
        return result[0]["total"] if result else 0

    @staticmethod
    def get_category_breakdown(user_email, start_date=None, end_date=None):
        db = get_db()
        match_query = {"user_email": user_email.lower()}
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            match_query["date"] = date_query

        pipeline = [
            {"$match": match_query},
            {"$group": {"_id": "$category", "total": {"$sum": "$amount"}}},
            {"$sort": {"total": -1}}
        ]
        return list(db.expenses.aggregate(pipeline))

class Income:
    @staticmethod
    def add_income(user_email, amount, source, date_str):
        db = get_db()
        income_doc = {
            "user_email": user_email.lower(),
            "amount": float(amount),
            "source": source,
            "date": date_str
        }
        result = db.incomes.insert_one(income_doc)
        income_doc['_id'] = result.inserted_id
        return income_doc

    @staticmethod
    def get_all(user_email, source=None, start_date=None, end_date=None):
        db = get_db()
        query = {"user_email": user_email.lower()}
        if source:
            query["source"] = source
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["date"] = date_query
        return list(db.incomes.find(query).sort("date", -1))

    @staticmethod
    def delete(income_id, user_email):
        db = get_db()
        if isinstance(income_id, str):
            income_id = ObjectId(income_id)
        result = db.incomes.delete_one({"_id": income_id, "user_email": user_email.lower()})
        return result.deleted_count > 0

    @staticmethod
    def get_total(user_email, source=None, start_date=None, end_date=None):
        db = get_db()
        match_query = {"user_email": user_email.lower()}
        if source:
            match_query["source"] = source
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            match_query["date"] = date_query

        pipeline = [
            {"$match": match_query},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        result = list(db.incomes.aggregate(pipeline))
        return result[0]["total"] if result else 0

class Loan:
    @staticmethod
    def calculate_emi(principal, annual_rate, tenure_months):
        if annual_rate == 0:
            return principal / tenure_months if tenure_months > 0 else 0
        r = annual_rate / 12 / 100
        n = tenure_months
        emi = principal * r * ((1 + r) ** n) / (((1 + r) ** n) - 1)
        return emi

    @staticmethod
    def add_loan(user_email, name, principal, annual_rate, tenure_months):
        db = get_db()
        emi = Loan.calculate_emi(principal, annual_rate, tenure_months)
        
        loan_doc = {
            "user_email": user_email.lower(),
            "name": name,
            "principal_amount": float(principal),
            "interest_rate": float(annual_rate),
            "tenure_months": int(tenure_months),
            "emi": float(emi),
            "remaining_balance": float(principal),
            "created_at": datetime.utcnow()
        }
        result = db.loans.insert_one(loan_doc)
        loan_doc['_id'] = result.inserted_id
        return loan_doc

    @staticmethod
    def get_all(user_email):
        db = get_db()
        return list(db.loans.find({"user_email": user_email.lower()}).sort("created_at", -1))

    @staticmethod
    def get_total_liability(user_email):
        db = get_db()
        pipeline = [
            {"$match": {"user_email": user_email.lower()}},
            {"$group": {"_id": None, "total": {"$sum": "$remaining_balance"}}}
        ]
        result = list(db.loans.aggregate(pipeline))
        return result[0]["total"] if result else 0

    @staticmethod
    def pay_emi(loan_id, user_email):
        db = get_db()
        
        if isinstance(loan_id, str):
            loan_id = ObjectId(loan_id)
            
        loan = db.loans.find_one({"_id": loan_id, "user_email": user_email.lower()})
        
        if not loan:
            return False, "Loan not found."
            
        if loan["remaining_balance"] <= 0:
            return False, "Loan is already fully paid."

        emi = loan["emi"]
        annual_rate = loan["interest_rate"]
        r = annual_rate / 12 / 100
        
        # Exact Amortization
        interest_payment = loan["remaining_balance"] * r
        principal_payment = emi - interest_payment
        
        if principal_payment > loan["remaining_balance"]:
            principal_payment = loan["remaining_balance"]
            emi = principal_payment + interest_payment

        new_balance = loan["remaining_balance"] - principal_payment
        if new_balance < 0.01:
            new_balance = 0

        db.loans.update_one({"_id": loan_id}, {"$set": {"remaining_balance": new_balance}})
        
        date_str = datetime.utcnow().date().isoformat()
        
        LoanPayment.add_payment(loan_id, user_email, emi, date_str)
        Expense.add_expense(user_email, emi, "Loan", date_str)
        
        return True, "EMI paid successfully."

class LoanPayment:
    @staticmethod
    def add_payment(loan_id, user_email, amount, date_str):
        db = get_db()
        if isinstance(loan_id, str):
            loan_id = ObjectId(loan_id)
            
        doc = {
            "loan_id": loan_id,
            "user_email": user_email.lower(),
            "amount": float(amount),
            "date": date_str,
            "created_at": datetime.utcnow()
        }
        db.loan_payments.insert_one(doc)
        return doc


class Asset:
    @staticmethod
    def add_asset(user_email, category, value, **kwargs):
        db = get_db()
        asset_doc = {
            "user_email": user_email.lower(),
            "category": category,
            "value": float(value),
            "created_at": datetime.utcnow()
        }
        
        # Link a loan if requested
        linked_loan_id = kwargs.pop('linked_loan_id', None)
        if linked_loan_id:
            asset_doc["linked_loan_id"] = ObjectId(linked_loan_id) if isinstance(linked_loan_id, str) else linked_loan_id

        # Ingest dynamic arbitrary kwargs depending on asset category
        asset_doc.update(kwargs)
        
        result = db.assets.insert_one(asset_doc)
        asset_doc['_id'] = result.inserted_id
        return asset_doc

    @staticmethod
    def get_all(user_email):
        db = get_db()
        assets = list(db.assets.find({"user_email": user_email.lower()}).sort("created_at", -1))
        
        # Cross-reference linked loans dynamically to calculate Equity
        for asset in assets:
            if 'linked_loan_id' in asset:
                loan = db.loans.find_one({"_id": asset['linked_loan_id']})
                if loan:
                    asset['loan_balance'] = loan['remaining_balance']
                    asset['equity'] = asset['value'] - loan['remaining_balance']
                else:
                    # Fallback if loan was somehow deleted
                    asset['loan_balance'] = 0.0
                    asset['equity'] = asset['value']
            else:
                asset['loan_balance'] = 0.0
                asset['equity'] = asset['value']
                
        return assets

    @staticmethod
    def update_asset(asset_id, user_email, updated_fields):
        """Update any fields on an asset. Protected fields cannot be overwritten."""
        db = get_db()
        if isinstance(asset_id, str):
            asset_id = ObjectId(asset_id)

        # Never allow overwriting system/protected fields via form
        protected = {'_id', 'user_email', 'created_at', 'is_sold', 'sold_price', 'sold_date', 'sell_notes', 'cash_received_from_sale'}
        safe_fields = {k: v for k, v in updated_fields.items() if k not in protected and v != ''}

        # Cast value to float if present
        if 'value' in safe_fields:
            try:
                safe_fields['value'] = float(safe_fields['value'])
            except ValueError:
                pass
        
        # Handle linked_loan_id
        if 'linked_loan_id' in safe_fields:
            lid = safe_fields['linked_loan_id']
            safe_fields['linked_loan_id'] = ObjectId(lid) if lid else None
            if safe_fields['linked_loan_id'] is None:
                del safe_fields['linked_loan_id']

        db.assets.update_one(
            {"_id": asset_id, "user_email": user_email.lower()},
            {"$set": safe_fields}
        )
        return True

    @staticmethod
    def get_total_value(user_email):
        db = get_db()
        pipeline = [
            {"$match": {"user_email": user_email.lower(), "is_sold": {"$ne": True}}},
            {"$group": {"_id": None, "total": {"$sum": "$value"}}}
        ]
        result = list(db.assets.aggregate(pipeline))
        total = result[0]["total"] if result else 0.0
        
        # Globally pull Insurance cash value explicitly acting as pure hard assets
        try:
            from models import Insurance
            total += float(Insurance.get_total_cash_value(user_email))
        except:
            pass
            
        return total

    @staticmethod
    def sell_asset(asset_id, user_email, sold_price, sold_date, notes=""):
        db = get_db()
        if isinstance(asset_id, str):
            asset_id = ObjectId(asset_id)
            
        asset = db.assets.find_one({"_id": asset_id, "user_email": user_email.lower()})
        if not asset:
            return False, "Asset not found."
            
        sold_price_val = float(sold_price)
        remaining_loan = 0.0
        
        # Check if asset has loan
        if 'linked_loan_id' in asset:
            loan = db.loans.find_one({"_id": asset['linked_loan_id']})
            if loan and loan['remaining_balance'] > 0:
                remaining_loan = loan['remaining_balance']
                # Zero out the loan debt instantly since the asset liquidation covers it
                db.loans.update_one(
                    {"_id": asset['linked_loan_id']},
                    {"$set": {"remaining_balance": 0.0}}
                )

        # Cash deposited back to the user is the leftover after paying the bank
        cash_received = sold_price_val - remaining_loan
        
        # We flag the asset as sold, log metrics, and persist
        db.assets.update_one(
            {"_id": asset_id},
            {
                "$set": {
                    "is_sold": True,
                    "sold_price": sold_price_val,
                    "sold_date": sold_date,
                    "sell_notes": notes,
                    "cash_received_from_sale": cash_received
                }
            }
        )
        
        # Log to overarching balance
        if cash_received >= 0:
            from models import Income
            Income.add_income(
                user_email=user_email,
                amount=cash_received,
                source="Asset Sale",
                date_str=sold_date
            )
        else:
            from models import Expense
            Expense.add_expense(
                user_email=user_email,
                amount=abs(cash_received),
                category="Debt Liquidation Loss",
                date_str=sold_date
            )
        
        return True, cash_received

class Insurance:
    @staticmethod
    def add_policy(user_email, policy_type, provider, premium, coverage, next_due_date, billing_cycle, has_cash_value, cash_value=0.0):
        db = get_db()
        doc = {
            "user_email": user_email.lower(),
            "policy_type": policy_type,
            "provider": provider,
            "premium": float(premium),
            "coverage": float(coverage),
            "next_due_date": next_due_date,
            "billing_cycle": billing_cycle,
            "has_cash_value": str(has_cash_value).lower() in ["true", "1", "yes", "on"],
            "cash_value": float(cash_value) if str(has_cash_value).lower() in ["true", "1", "yes", "on"] else 0.0,
            "created_at": datetime.utcnow()
        }
        res = db.insurances.insert_one(doc)
        
        # Add the first premium immediately to Expense history securely
        from models import Expense
        Expense.add_expense(
            user_email=user_email,
            amount=premium,
            category=f"Insurance: {policy_type}",
            date_str=datetime.utcnow().strftime("%Y-%m-%d")
        )
        doc['_id'] = res.inserted_id
        return doc

    @staticmethod
    def get_all(user_email):
        db = get_db()
        return list(db.insurances.find({"user_email": user_email.lower()}).sort("created_at", -1))

    @staticmethod
    def update_policy(policy_id, user_email, updated_fields):
        """Fully flexible update for insurance policies including cash value toggle."""
        db = get_db()
        if isinstance(policy_id, str):
            policy_id = ObjectId(policy_id)

        protected = {'_id', 'user_email', 'created_at'}
        safe_fields = {k: v for k, v in updated_fields.items() if k not in protected and v != ''}

        # Cast numeric fields
        for num_key in ('premium', 'coverage', 'cash_value'):
            if num_key in safe_fields:
                try:
                    safe_fields[num_key] = float(safe_fields[num_key])
                except (ValueError, TypeError):
                    pass

        # Handle the has_cash_value toggle – allow switching between pure-expense and asset-backed
        if 'has_cash_value' in safe_fields:
            safe_fields['has_cash_value'] = str(safe_fields['has_cash_value']).lower() in ['true', '1', 'yes', 'on']
            if not safe_fields['has_cash_value']:
                safe_fields['cash_value'] = 0.0
        
        db.insurances.update_one(
            {"_id": policy_id, "user_email": user_email.lower()},
            {"$set": safe_fields}
        )
        return True
        
    @staticmethod
    def get_total_cash_value(user_email):
        db = get_db()
        pipeline = [
            {"$match": {"user_email": user_email.lower(), "has_cash_value": True}},
            {"$group": {"_id": None, "total": {"$sum": "$cash_value"}}}
        ]
        result = list(db.insurances.aggregate(pipeline))
        return result[0]["total"] if result else 0.0

    @staticmethod
    def pay_premium(policy_id, user_email):
        db = get_db()
        if isinstance(policy_id, str):
            policy_id = ObjectId(policy_id)
            
        policy = db.insurances.find_one({"_id": policy_id, "user_email": user_email.lower()})
        if not policy:
            return False, "Policy not found."
            
        # Log the expense
        from models import Expense
        Expense.add_expense(
            user_email=user_email,
            amount=policy['premium'],
            category=f"Insurance: {policy['policy_type']}",
            date_str=datetime.utcnow().strftime("%Y-%m-%d")
        )
        
        # Advance the due date
        current_due = policy.get('next_due_date', datetime.utcnow().strftime("%Y-%m-%d"))
        try:
            # Basic span advancement using standard datetime manipulations without external imports
            parts = current_due.split('-')
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            
            cycle = policy.get('billing_cycle', 'Yearly').lower()
            if cycle == 'monthly':
                m += 1
                if m > 12:
                    m = 1
                    y += 1
            elif cycle == 'quarterly':
                m += 3
                if m > 12:
                    m -= 12
                    y += 1
            else: # Yearly
                y += 1
            
            # Simple overflow protection for days (e.g. Feb 30 -> Feb 28)
            if m == 2 and d > 28: d = 28
            elif m in [4, 6, 9, 11] and d > 30: d = 30
                
            next_due = f"{y:04d}-{m:02d}-{d:02d}"
        except:
            # Fallback if string is deformed
            next_due = current_due
            
        db.insurances.update_one(
            {"_id": policy_id},
            {"$set": {"next_due_date": next_due}}
        )
        return True, "Premium paid and next due date advanced!"

class TaxProfile:
    @staticmethod
    def save_profile(user_email, data):
        db = get_db()
        from utils.helpers import safe_float
        # remove anything we don't want to store directly if necessary
        doc = {
            "user_email": user_email.lower(),
            "financial_year": data.get("financial_year", "2025-26"),
            "salary": safe_float(data.get("salary")),
            "other_income": safe_float(data.get("other_income")),
            "deductions": {
                "section_80C": safe_float(data.get("section_80C")),
                "home_loan_interest": safe_float(data.get("home_loan_interest")),
                "hra": safe_float(data.get("hra"))
            },
            "insurance_details": {
                "has_health_insurance": data.get("has_health_insurance") == 'on',
                "has_life_insurance": data.get("has_life_insurance") == 'on',
                "health_premium_self": safe_float(data.get("health_premium_self")),
                "health_premium_parents": safe_float(data.get("health_premium_parents")),
                "parents_senior": data.get("parents_senior") == 'on',
                "life_premium": safe_float(data.get("life_premium"))
            },
            "created_at": datetime.utcnow()
        }
        
        db.tax_profiles.update_one(
            {"user_email": user_email.lower(), "financial_year": doc["financial_year"]},
            {"$set": doc},
            upsert=True
        )
        return True

    @staticmethod
    def get_profile(user_email, financial_year="2025-26"):
        db = get_db()
        return db.tax_profiles.find_one({"user_email": user_email.lower(), "financial_year": financial_year})
