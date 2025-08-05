from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets
import string
import os
from flask_moment import Moment
from sqlalchemy import func, extract

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:lifeisgood@localhost:5432/chamastack'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

moment = Moment(app)

# Initialize extensions with the app
from extensions import db, login_manager
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

# Import models AFTER initializing db
from models import User, Chama, Membership, Contribution, Expense, Goal, Vote, VoteOption, VoteResponse

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_join_code():
    """Generate a unique 8-character join code"""
    while True:
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        if not Chama.query.filter_by(join_code=code).first():
            return code

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        phone_number = request.form['phone_number']
        name = request.form['name']
        password = request.form['password']
        
        # Check if user already exists
        if User.query.filter_by(phone_number=phone_number).first():
            flash('Phone number already registered', 'error')
            return render_template('register.html')
        
        # Create new user
        user = User(
            phone_number=phone_number,
            name=name,
            password_hash=generate_password_hash(password)
        )
        
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        flash('Registration successful!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone_number = request.form['phone_number']
        password = request.form['password']
        
        user = User.query.filter_by(phone_number=phone_number).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid phone number or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    # Calculate user statistics
    user_stats = {}
    
    # Total chamas user is part of
    user_stats['total_chamas'] = db.session.query(Membership).filter_by(
        user_id=current_user.id, is_active=True
    ).count()
    
    # Total contributed amount
    total_contributed = db.session.query(func.sum(Contribution.amount)).filter_by(
        user_id=current_user.id, status='confirmed'
    ).scalar() or 0
    user_stats['total_contributed'] = total_contributed
    
    # This month contributions
    current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_contributed = db.session.query(func.sum(Contribution.amount)).filter(
        Contribution.user_id == current_user.id,
        Contribution.status == 'confirmed',
        Contribution.contributed_at >= current_month
    ).scalar() or 0
    user_stats['month_contributed'] = month_contributed
    
    # Average per chama
    if user_stats['total_chamas'] > 0:
        user_stats['avg_per_chama'] = total_contributed / user_stats['total_chamas']
    else:
        user_stats['avg_per_chama'] = 0
    
    # Total transactions
    user_stats['total_transactions'] = db.session.query(Contribution).filter_by(
        user_id=current_user.id
    ).count()
    
    # Success rate (confirmed vs total contributions)
    confirmed_count = db.session.query(Contribution).filter_by(
        user_id=current_user.id, status='confirmed'
    ).count()
    if user_stats['total_transactions'] > 0:
        user_stats['success_rate'] = round((confirmed_count / user_stats['total_transactions']) * 100, 1)
    else:
        user_stats['success_rate'] = 0
    
    # Last 7 days contributions
    seven_days_ago = datetime.now() - timedelta(days=7)
    user_stats['last_7_days'] = db.session.query(Contribution).filter(
        Contribution.user_id == current_user.id,
        Contribution.contributed_at >= seven_days_ago
    ).count()
    
    # Last 30 days contributions
    thirty_days_ago = datetime.now() - timedelta(days=30)
    user_stats['last_30_days'] = db.session.query(Contribution).filter(
        Contribution.user_id == current_user.id,
        Contribution.contributed_at >= thirty_days_ago
    ).count()
    
    # Pending contributions
    user_stats['pending_contributions'] = db.session.query(Contribution).filter_by(
        user_id=current_user.id, status='pending'
    ).count()
    
    return render_template('profile.html', user_stats=user_stats)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    name = request.form.get('name')
    phone_number = request.form.get('phone_number')
    
    if not name or not phone_number:
        flash('All fields are required', 'error')
        return redirect(url_for('profile'))
    
    # Check if phone number is already taken by another user
    existing_user = User.query.filter(
        User.phone_number == phone_number,
        User.id != current_user.id
    ).first()
    
    if existing_user:
        flash('Phone number is already taken', 'error')
        return redirect(url_for('profile'))
    
    # Update user information
    current_user.name = name
    current_user.phone_number = phone_number
    
    try:
        db.session.commit()
        flash('Profile updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating profile', 'error')
    
    return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        flash('All fields are required', 'error')
        return redirect(url_for('profile'))
    
    # Verify current password
    if not check_password_hash(current_user.password_hash, current_password):
        flash('Current password is incorrect', 'error')
        return redirect(url_for('profile'))
    
    # Check if new passwords match
    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('profile'))
    
    # Check password strength (optional)
    if len(new_password) < 6:
        flash('Password must be at least 6 characters long', 'error')
        return redirect(url_for('profile'))
    
    # Update password
    current_user.password_hash = generate_password_hash(new_password)
    
    try:
        db.session.commit()
        flash('Password updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating password', 'error')
    
    return redirect(url_for('profile'))

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user_id = current_user.id
    
    try:
        # Delete user's contributions
        Contribution.query.filter_by(user_id=user_id).delete()
        
        # Delete user's memberships
        Membership.query.filter_by(user_id=user_id).delete()
        
        # Delete user's vote responses
        VoteResponse.query.filter_by(user_id=user_id).delete()
        
        # Delete the user account
        db.session.delete(current_user)
        db.session.commit()
        
        # Logout the user
        logout_user()
        
        flash('Account deleted successfully', 'success')
        return redirect(url_for('login'))
        
    except Exception as e:
        db.session.rollback()
        flash('Error deleting account. Please try again.', 'error')
        return redirect(url_for('profile'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's chamas
    memberships = Membership.query.filter_by(user_id=current_user.id, is_active=True).all()
    chamas = [membership.chama for membership in memberships]

    # Get all contributions
    recent_contributions = Contribution.query.filter_by(user_id=current_user.id)\
        .order_by(Contribution.contributed_at.desc()).limit(5).all()

    # Contributions this month
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_contribution_count = db.session.query(Contribution).filter(
        Contribution.user_id == current_user.id,
        Contribution.contributed_at >= start_of_month
    ).count()

    # Total contributions
    total_contributions = db.session.query(db.func.sum(Contribution.amount))\
        .filter_by(user_id=current_user.id, status='confirmed').scalar() or 0

    return render_template('dashboard.html', 
                         chamas=chamas, 
                         recent_contributions=recent_contributions,
                         total_contributions=total_contributions,
                         monthly_contribution_count=monthly_contribution_count)

@app.route('/create_chama', methods=['GET', 'POST'])
@login_required
def create_chama():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        contribution_amount = float(request.form['contribution_amount'])
        contribution_frequency = request.form['contribution_frequency']
        
        # Create chama
        chama = Chama(
            name=name,
            description=description,
            join_code=generate_join_code(),
            contribution_amount=contribution_amount,
            contribution_frequency=contribution_frequency,
            created_by=current_user.id
        )
        
        db.session.add(chama)
        db.session.commit()
        
        # Add creator as admin member
        membership = Membership(
            user_id=current_user.id,
            chama_id=chama.id,
            role='admin'
        )
        
        db.session.add(membership)
        db.session.commit()
        
        flash(f'Chama created successfully! Join code: {chama.join_code}', 'success')
        return redirect(url_for('chama_detail', chama_id=chama.id))
    
    return render_template('create_chama.html')

@app.route('/join_chama', methods=['GET', 'POST'])
@login_required
def join_chama():
    if request.method == 'POST':
        join_code = request.form['join_code'].upper()
        
        chama = Chama.query.filter_by(join_code=join_code, is_active=True).first()
        
        if not chama:
            flash('Invalid join code', 'error')
            return render_template('join_chama.html')
        
        # Check if already a member
        existing_membership = Membership.query.filter_by(
            user_id=current_user.id, 
            chama_id=chama.id
        ).first()
        
        if existing_membership:
            flash('You are already a member of this chama', 'info')
            return redirect(url_for('chama_detail', chama_id=chama.id))
        
        # Add as member
        membership = Membership(
            user_id=current_user.id,
            chama_id=chama.id,
            role='member'
        )
        
        db.session.add(membership)
        db.session.commit()
        
        flash(f'Successfully joined {chama.name}!', 'success')
        return redirect(url_for('chama_detail', chama_id=chama.id))
    
    return render_template('join_chama.html')

@app.route('/chama/<int:chama_id>')
@login_required
def chama_detail(chama_id):
    # Check if user is a member
    membership = Membership.query.filter_by(
        user_id=current_user.id, 
        chama_id=chama_id, 
        is_active=True
    ).first()
    
    if not membership:
        flash('You are not a member of this chama', 'error')
        return redirect(url_for('dashboard'))
    
    chama = Chama.query.get_or_404(chama_id)
    
    # Get chama statistics
    total_members = Membership.query.filter_by(chama_id=chama_id, is_active=True).count()
    total_contributions = db.session.query(db.func.sum(Contribution.amount))\
        .filter_by(chama_id=chama_id, status='confirmed').scalar() or 0
    total_expenses = db.session.query(db.func.sum(Expense.amount))\
        .filter_by(chama_id=chama_id).scalar() or 0
    
    # Get recent activities
    recent_contributions = Contribution.query.filter_by(chama_id=chama_id)\
        .order_by(Contribution.contributed_at.desc()).limit(10).all()
    
    # Get active goals
    active_goals = Goal.query.filter_by(chama_id=chama_id, is_achieved=False).all()
    
    # Get active votes
    active_votes = Vote.query.filter_by(chama_id=chama_id, is_active=True).all()
    
    return render_template('chama_detail.html',
                         chama=chama,
                         membership=membership,
                         total_members=total_members,
                         total_contributions=total_contributions,
                         total_expenses=total_expenses,
                         recent_contributions=recent_contributions,
                         active_goals=active_goals,
                         active_votes=active_votes)

@app.route('/chama/<int:chama_id>/contribute', methods=['GET', 'POST'])
@login_required
def contribute(chama_id):
    # Check membership
    membership = Membership.query.filter_by(
        user_id=current_user.id, 
        chama_id=chama_id, 
        is_active=True
    ).first()
    
    if not membership:
        flash('You are not a member of this chama', 'error')
        return redirect(url_for('dashboard'))
    
    chama = Chama.query.get_or_404(chama_id)
    
    if request.method == 'POST':
        amount = float(request.form['amount'])
        payment_method = request.form['payment_method']
        transaction_ref = request.form.get('transaction_ref', '')
        
        contribution = Contribution(
            user_id=current_user.id,
            chama_id=chama_id,
            amount=amount,
            payment_method=payment_method,
            transaction_ref=transaction_ref,
            status='pending'  # In real app, this would be verified
        )
        
        db.session.add(contribution)
        db.session.commit()
        
        flash('Contribution recorded! Awaiting confirmation.', 'success')
        return redirect(url_for('chama_detail', chama_id=chama_id))
    
    return render_template('contribute.html', chama=chama)

@app.route('/api/chama/<int:chama_id>/stats')
@login_required
def chama_stats_api(chama_id):
    # Check membership
    membership = Membership.query.filter_by(
        user_id=current_user.id, 
        chama_id=chama_id, 
        is_active=True
    ).first()
    
    if not membership:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get monthly contribution data for charts
    monthly_data = db.session.query(
        extract('month', Contribution.contributed_at).label('month'),
        db.func.sum(Contribution.amount).label('total')
    ).filter_by(chama_id=chama_id, status='confirmed')\
     .group_by(extract('month', Contribution.contributed_at))\
     .all()
    
    return jsonify({
        'monthly_contributions': [{'month': row.month, 'total': float(row.total)} for row in monthly_data]
    })

@app.template_filter('currency')
def currency_filter(value):
    try:
        return "KSh {:,.2f}".format(float(value))
    except (ValueError, TypeError):
        return value

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)