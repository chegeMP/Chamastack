from datetime import datetime
from extensions import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships with explicit foreign keys
    memberships = db.relationship('Membership', backref='user', lazy=True)
    contributions = db.relationship('Contribution', 
                                  foreign_keys='[Contribution.user_id]',
                                  backref='contributor', 
                                  lazy=True)
    confirmed_contributions = db.relationship('Contribution',
                                            foreign_keys='[Contribution.confirmed_by]',
                                            backref='confirmer',
                                            lazy=True)

class Chama(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    join_code = db.Column(db.String(10), unique=True, nullable=False)
    contribution_amount = db.Column(db.Float, nullable=False)
    contribution_frequency = db.Column(db.String(20), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    memberships = db.relationship('Membership', backref='chama', lazy=True)
    contributions = db.relationship('Contribution', backref='chama', lazy=True)
    expenses = db.relationship('Expense', backref='chama', lazy=True)
    goals = db.relationship('Goal', backref='chama', lazy=True)
    votes = db.relationship('Vote', backref='chama', lazy=True)

class Membership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    role = db.Column(db.String(20), default='member')  # 'member', 'admin'
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Contribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))
    transaction_ref = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')  # 'pending', 'confirmed'
    contributed_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('user.id'))

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    is_achieved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    options = db.relationship('VoteOption', backref='vote', lazy=True)
    responses = db.relationship('VoteResponse', backref='vote', lazy=True)

class VoteOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vote_id = db.Column(db.Integer, db.ForeignKey('vote.id'), nullable=False)
    option_text = db.Column(db.String(100), nullable=False)

class VoteResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vote_id = db.Column(db.Integer, db.ForeignKey('vote.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('vote_option.id'), nullable=False)
    responded_at = db.Column(db.DateTime, default=datetime.utcnow)
