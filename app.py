from flask import *
import pymongo
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from bson.objectid import ObjectId
from datetime import datetime

client = pymongo.MongoClient("mongodb://localhost:27017")
db = client["cargo_erp"]

# --- MongoDB Collections ---
# Core ERP
users_col = db["users"]
ships_col = db["ships"]
expenditure_col = db["expenditures"]
notices_col = db["notices"]
complaints_col = db["complaints"]
invoices_col = db["invoices"]

# New ERP Modules
cargo_col = db["cargo"]
voyages_col = db["voyages"]
maintenance_col = db["maintenance"]

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = "super_secret_cargo_key"  # Needed for session management (logins)

# --- Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user' in session:
        if session['user']['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        user = users_col.find_one({'email': email, 'role': role})

        if user and check_password_hash(user['password'], password):
            session['user'] = {
                'name': user['name'],
                'email': user['email'],
                'role': user.get('role', 'user') # Default to 'user' if role not set
            }
            flash(f"Welcome back, {user['name']}!", "success")
            if session['user']['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash("Invalid email, password, or user type. Please try again.", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # This route is for the FIRST admin. In a real app, this should be disabled or protected after setup.
    if users_col.find_one({'role': 'admin'}):
         flash("Admin account already exists. Please log in.", "info")
         return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if users_col.find_one({'email': email}):
            flash("An account with this email already exists.", "danger")
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password)
        users_col.insert_one({
            'name': name,
            'email': email,
            'password': hashed_password,
            'role': 'admin' # First user is an admin
        })
        
        # Automatically log the user in after sign up
        session['user'] = {
            'name': name, 'email': email, 'role': 'admin'
        }
        flash("Admin account created successfully! Welcome to your dashboard.", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if session['user']['role'] != 'admin': return redirect(url_for('index'))
    
    total_ships = ships_col.count_documents({})
    total_users = users_col.count_documents({})
    pending_complaints = complaints_col.count_documents({'status': 'pending'})
    expenditures = list(expenditure_col.find())
    total_expenses = sum(float(e.get('amount', 0)) for e in expenditures)
    return render_template('admin_dashboard.html', total_ships=total_ships, total_users=total_users, pending_complaints=pending_complaints, total_expenses=total_expenses)

# --- Admin CRUD Routes ---

@app.route('/admin/ships', methods=['GET', 'POST'])
@login_required
def admin_ships():
    if session['user']['role'] != 'admin': return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name')
        capacity = request.form.get('capacity')
        cost = request.form.get('cost')
        ships_col.insert_one({'name': name, 'capacity': capacity, 'cost': cost})
        flash(f"Ship '{name}' added successfully!", "success")
        return redirect(url_for('admin_ships'))
    
    ships = list(ships_col.find())
    # Inject mock AI Predictive Maintenance data based on capacity hashing
    for ship in ships:
        ship['ai_maintenance_days'] = (int(ship.get('capacity', 0)) % 45) + 5 
    return render_template('admin_ships.html', ships=ships)

@app.route('/admin/ships/delete/<ship_id>')
@login_required
def delete_ship(ship_id):
    if session['user']['role'] != 'admin': return redirect(url_for('index'))
    ships_col.delete_one({'_id': ObjectId(ship_id)})
    flash("Ship deleted successfully.", "info")
    return redirect(url_for('admin_ships'))

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def admin_users():
    if session['user']['role'] != 'admin': return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = generate_password_hash(request.form.get('password'))
        role = request.form.get('role')
        salary = request.form.get('salary')
        phone = request.form.get('phone')
        address = request.form.get('address')
        allotted_ship = request.form.get('allotted_ship')
        
        users_col.insert_one({
            'name': name, 'email': email, 'password': password, 
            'role': role, 'salary': salary, 'phone': phone, 
            'address': address, 'allotted_ship': allotted_ship
        })
        flash(f"User '{name}' added successfully!", "success")
        return redirect(url_for('admin_users'))
    
    users = list(users_col.find())
    ships = list(ships_col.find())
    # Create a dictionary to map ship ObjectIds to Ship Names for display
    ship_map = {str(ship['_id']): ship['name'] for ship in ships}
    
    return render_template('admin_users.html', users=users, ships=ships, ship_map=ship_map)

@app.route('/admin/users/edit/<user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if session['user']['role'] != 'admin': return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        role = request.form.get('role')
        salary = request.form.get('salary')
        phone = request.form.get('phone')
        address = request.form.get('address')
        allotted_ship = request.form.get('allotted_ship')
        
        update_data = {
            'name': name, 'email': email, 'role': role, 
            'salary': salary, 'phone': phone, 
            'address': address, 'allotted_ship': allotted_ship
        }
        
        password = request.form.get('password')
        if password: # Only update the password if the admin provided a new one
            update_data['password'] = generate_password_hash(password)
            
        users_col.update_one({'_id': ObjectId(user_id)}, {'$set': update_data})
        flash(f"User '{name}' updated successfully!", "success")
        return redirect(url_for('admin_users'))
        
    user = users_col.find_one({'_id': ObjectId(user_id)})
    ships = list(ships_col.find())
    return render_template('admin_edit_user.html', user=user, ships=ships)

@app.route('/admin/expenditure')
@app.route('/admin/expenditure', methods=['GET', 'POST'])
@login_required
def admin_expenditure():
    if session['user']['role'] != 'admin': return redirect(url_for('index'))
    if request.method == 'POST':
        date_time = request.form.get('datetime')
        ship_id = request.form.get('ship')
        description = request.form.get('description')
        amount = request.form.get('amount')
        currency = request.form.get('currency')
        
        expenditure_col.insert_one({
            'datetime': date_time, 'ship_id': ship_id, 
            'description': description, 'amount': float(amount), 'currency': currency
        })
        flash("Expenditure recorded successfully!", "success")
        return redirect(url_for('admin_expenditure'))
        
    expenditures = list(expenditure_col.find())
    ships = list(ships_col.find())
    ship_map = {str(ship['_id']): ship['name'] for ship in ships}
    
    # AI Anomaly Detection & Forecasting Logic
    total_exp = sum(float(e.get('amount', 0)) for e in expenditures)
    avg_exp = total_exp / len(expenditures) if expenditures else 0
    for exp in expenditures:
        exp['is_anomaly'] = float(exp.get('amount', 0)) > (avg_exp * 2.5) and avg_exp > 0
        
    ai_forecast = total_exp * 1.12 # Predicting a 12% increase based on seasonal trends
    return render_template('admin_expenditure.html', expenditures=expenditures, ships=ships, ship_map=ship_map, ai_forecast=ai_forecast, avg_exp=avg_exp)

@app.route('/admin/notices', methods=['GET', 'POST'])
@login_required
def admin_notices():
    if session['user']['role'] != 'admin': return redirect(url_for('index'))
    if request.method == 'POST':
        description = request.form.get('description')
        target_ship = request.form.get('target_ship')
        notices_col.insert_one({'description': description, 'target_ship': target_ship})
        flash("Notice published successfully!", "success")
        return redirect(url_for('admin_notices'))
        
    notices = list(notices_col.find())
    ships = list(ships_col.find())
    return render_template('admin_notices.html', notices=notices, ships=ships)

@app.route('/admin/complaints', methods=['GET', 'POST'])
@login_required
def admin_complaints():
    if session['user']['role'] != 'admin': return redirect(url_for('index'))
    if request.method == 'POST':
        complaint_id = request.form.get('complaint_id')
        new_status = request.form.get('status')
        complaints_col.update_one({'_id': ObjectId(complaint_id)}, {'$set': {'status': new_status}})
        flash("Complaint status updated successfully.", "success")
        return redirect(url_for('admin_complaints'))
        
    complaints = list(complaints_col.find().sort('date', -1))
    return render_template('admin_complaints.html', complaints=complaints)

# --- Admin Invoice Routes ---

@app.route('/admin/invoices')
@login_required
def admin_invoices():
    if session['user']['role'] != 'admin': return redirect(url_for('index'))
    invoices = list(invoices_col.find().sort('created_at', -1))
    for inv in invoices:
        paid = sum(float(t['amount']) for t in inv.get('transactions', []))
        inv['paid_amount'] = paid
        inv['due_amount'] = float(inv['total_amount']) - paid
        inv['status'] = 'Paid' if inv['due_amount'] <= 0 else 'Due'
        
        # AI Late Payment Risk Assessment
        if inv['due_amount'] > 15000: inv['ai_risk'] = 'High Risk'
        elif inv['due_amount'] > 5000: inv['ai_risk'] = 'Medium Risk'
        else: inv['ai_risk'] = 'Low Risk'
        
    return render_template('admin_invoices.html', invoices=invoices)

@app.route('/admin/invoices/add', methods=['GET', 'POST'])
@login_required
def add_invoice():
    if session['user']['role'] != 'admin': return redirect(url_for('index'))
    if request.method == 'POST':
        client_name = request.form.get('client_name')
        client_phone = request.form.get('client_phone')
        transportation_details = request.form.get('transportation_details')
        base_amount = float(request.form.get('base_amount', 0))
        taxes = float(request.form.get('taxes', 0))
        discount = float(request.form.get('discount', 0))
        total_amount = base_amount + taxes - discount
        
        invoices_col.insert_one({
            'client_name': client_name, 'client_phone': client_phone,
            'transportation_details': transportation_details,
            'base_amount': base_amount, 'taxes': taxes,
            'discount': discount, 'total_amount': total_amount,
            'transactions': [], 'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        flash("Invoice created successfully!", "success")
        return redirect(url_for('admin_invoices'))
    return render_template('admin_add_invoice.html')

@app.route('/admin/invoices/edit/<invoice_id>', methods=['GET', 'POST'])
@login_required
def edit_invoice(invoice_id):
    if session['user']['role'] != 'admin': return redirect(url_for('index'))
    if request.method == 'POST':
        invoices_col.update_one(
            {'_id': ObjectId(invoice_id)},
            {'$set': {
                'client_name': request.form.get('client_name'), 'client_phone': request.form.get('client_phone'),
                'transportation_details': request.form.get('transportation_details'),
                'base_amount': float(request.form.get('base_amount', 0)), 'taxes': float(request.form.get('taxes', 0)),
                'discount': float(request.form.get('discount', 0)),
                'total_amount': float(request.form.get('base_amount', 0)) + float(request.form.get('taxes', 0)) - float(request.form.get('discount', 0))
            }}
        )
        flash("Invoice updated successfully!", "success")
        return redirect(url_for('view_invoice', invoice_id=invoice_id))
    invoice = invoices_col.find_one({'_id': ObjectId(invoice_id)})
    return render_template('admin_edit_invoice.html', invoice=invoice)

@app.route('/admin/invoices/view/<invoice_id>', methods=['GET', 'POST'])
@login_required
def view_invoice(invoice_id):
    if session['user']['role'] != 'admin': return redirect(url_for('index'))
    if request.method == 'POST':
        # Add Transaction
        amount = float(request.form.get('amount', 0))
        date_time = request.form.get('datetime')
        invoices_col.update_one({'_id': ObjectId(invoice_id)}, {'$push': {'transactions': {'datetime': date_time, 'amount': amount}}})
        flash("Transaction recorded successfully!", "success")
        return redirect(url_for('view_invoice', invoice_id=invoice_id))
        
    invoice = invoices_col.find_one({'_id': ObjectId(invoice_id)})
    paid = sum(float(t['amount']) for t in invoice.get('transactions', []))
    invoice['paid_amount'] = paid
    invoice['due_amount'] = float(invoice['total_amount']) - paid
    return render_template('admin_view_invoice.html', invoice=invoice)

# --- User Routes ---

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    user_data = users_col.find_one({'email': session['user']['email']})
    ship = None
    ship_name = "None"
    if user_data and user_data.get('allotted_ship') and user_data['allotted_ship'] != 'None':
        ship = ships_col.find_one({'_id': ObjectId(user_data['allotted_ship'])})
        if ship: ship_name = ship['name']
    
    notices = list(notices_col.find({'$or': [{'target_ship': 'all'}, {'target_ship': ship_name}]}))
    return render_template('user_dashboard.html', ship=ship, notices=notices)

@app.route('/user/complaints', methods=['GET', 'POST'])
@login_required
def user_complaints():
    if request.method == 'POST':
        description = request.form.get('description')
        
        # --- NLP Sentiment & Urgency Analysis (Simulated) ---
        desc_lower = description.lower()
        critical_words = ['sink', 'fire', 'leak', 'crash', 'fail', 'urgent', 'immediate', 'danger', 'critical']
        high_words = ['broken', 'stop', 'delay', 'issue', 'bad', 'injury']
        
        urgency, sentiment = 'Low', 'Neutral'
        if any(w in desc_lower for w in critical_words):
            urgency, sentiment = 'Critical', 'Highly Negative'
        elif any(w in desc_lower for w in high_words):
            urgency, sentiment = 'High', 'Negative'
        # ----------------------------------------------------
            
        complaints_col.insert_one({
            'user_email': session['user']['email'], 'user_name': session['user']['name'],
            'description': description, 'status': 'pending', 'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'urgency': urgency, 'sentiment': sentiment
        })
        flash("Your complaint has been submitted and is pending review.", "success")
        return redirect(url_for('user_complaints'))
        
    complaints = list(complaints_col.find({'user_email': session['user']['email']}).sort('date', -1))
    return render_template('user_complaints.html', complaints=complaints)

if __name__ == '__main__':
    app.run(debug=True)