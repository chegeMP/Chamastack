from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets
import string
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chamastack.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    memberships = db.relationship('Membership', backref='user', lazy=True)
    contributions = db.relationship('Contribution', backref='user', lazy=True)

class Chama(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    join_code = db.Column(db.String(8), unique=True, nullable=False)
    contribution_amount = db.Column(db.Float, nullable=False)
    contribution_frequency = db.Column(db.String(20), default='monthly')  # weekly, monthly
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    memberships = db.relationship('Membership', backref='chama', lazy=True)
    contributions = db.relationship('Contribution', backref='chama', lazy=True)
    expenses = db.relationship('Expense', backref='chama', lazy=True)
    goals = db.relationship('Goal', backref='chama', lazy=True)
    votes = db.relationship('Vote', backref='chama', lazy=True)

class Membership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    role = db.Column(db.String(20), default='member')  # admin, treasurer, secretary, member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Contribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(20), default='cash')  # cash, mpesa, bank
    transaction_ref = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, failed
    contributed_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('user.id'))

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))  # admin, investment, loan, other
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    target_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_achieved = db.Column(db.Boolean, default=False)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship for vote options and responses
    options = db.relationship('VoteOption', backref='vote', lazy=True)

class VoteOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vote_id = db.Column(db.Integer, db.ForeignKey('vote.id'), nullable=False)
    option_text = db.Column(db.String(200), nullable=False)
    votes_count = db.Column(db.Integer, default=0)

class VoteResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vote_id = db.Column(db.Integer, db.ForeignKey('vote.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('vote_option.id'), nullable=False)
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user's chamas
    memberships = Membership.query.filter_by(user_id=current_user.id, is_active=True).all()
    chamas = [membership.chama for membership in memberships]
    
    # Get recent contributions
    recent_contributions = Contribution.query.filter_by(user_id=current_user.id)\
        .order_by(Contribution.contributed_at.desc()).limit(5).all()
    
    # Calculate total contributions
    total_contributions = db.session.query(db.func.sum(Contribution.amount))\
        .filter_by(user_id=current_user.id, status='confirmed').scalar() or 0
    
    return render_template('dashboard.html', 
                         chamas=chamas, 
                         recent_contributions=recent_contributions,
                         total_contributions=total_contributions)

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
    from sqlalchemy import extract
    monthly_data = db.session.query(
        extract('month', Contribution.contributed_at).label('month'),
        db.func.sum(Contribution.amount).label('total')
    ).filter_by(chama_id=chama_id, status='confirmed')\
     .group_by(extract('month', Contribution.contributed_at))\
     .all()
    
    return jsonify({
        'monthly_contributions': [{'month': row.month, 'total': float(row.total)} for row in monthly_data]
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)