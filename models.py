from datetime import datetime
from extensions import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships - removed conflicting backrefs
    memberships = db.relationship('Membership', foreign_keys='[Membership.user_id]', lazy=True)
    user_contributions = db.relationship('Contribution', 
                                       foreign_keys='[Contribution.user_id]',
                                       lazy=True)
    confirmed_contributions = db.relationship('Contribution',
                                            foreign_keys='[Contribution.confirmed_by]',
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

    # Relationships - removed conflicting backrefs
    memberships = db.relationship('Membership', foreign_keys='[Membership.chama_id]', lazy=True)
    chama_contributions = db.relationship('Contribution', foreign_keys='[Contribution.chama_id]', lazy=True)
    expenses = db.relationship('Expense', foreign_keys='[Expense.chama_id]', lazy=True)
    goals = db.relationship('Goal', foreign_keys='[Goal.chama_id]', lazy=True)
    votes = db.relationship('Vote', foreign_keys='[Vote.chama_id]', lazy=True)

class Membership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    role = db.Column(db.String(20), default='member')  # 'member', 'admin'
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Explicit relationships
    user = db.relationship('User', foreign_keys=[user_id])
    chama = db.relationship('Chama', foreign_keys=[chama_id])

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
    
    # Explicit relationships without conflicting backrefs
    user = db.relationship('User', foreign_keys=[user_id])
    chama = db.relationship('Chama', foreign_keys=[chama_id])
    confirmer = db.relationship('User', foreign_keys=[confirmed_by])

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Explicit relationship
    chama = db.relationship('Chama', foreign_keys=[chama_id])

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    is_achieved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Explicit relationship
    chama = db.relationship('Chama', foreign_keys=[chama_id])

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chama_id = db.Column(db.Integer, db.ForeignKey('chama.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Explicit relationship
    chama = db.relationship('Chama', foreign_keys=[chama_id])
    options = db.relationship('VoteOption', foreign_keys='[VoteOption.vote_id]', lazy=True)
    responses = db.relationship('VoteResponse', foreign_keys='[VoteResponse.vote_id]', lazy=True)

class VoteOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vote_id = db.Column(db.Integer, db.ForeignKey('vote.id'), nullable=False)
    option_text = db.Column(db.String(100), nullable=False)

    # Explicit relationship
    vote = db.relationship('Vote', foreign_keys=[vote_id])

class VoteResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vote_id = db.Column(db.Integer, db.ForeignKey('vote.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('vote_option.id'), nullable=False)
    responded_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Explicit relationships
    vote = db.relationship('Vote', foreign_keys=[vote_id])
    user = db.relationship('User', foreign_keys=[user_id])
    option = db.relationship('VoteOption', foreign_keys=[option_id])