from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False) # Email/Mobile
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='citizen') # 'citizen' or 'staff'

class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    token_number = db.Column(db.String(50), unique=True)
    purpose = db.Column(db.String(255))
    state = db.Column(db.String(100))
    district = db.Column(db.String(100))
    is_priority = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='Waiting') # Waiting, Serving, Completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Link back to user to see their name in Workbench
    user = db.relationship('User', backref='user_tickets')