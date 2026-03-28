from dotenv import load_dotenv
load_dotenv()
import os
import stripe
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///payments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-this')  # Change this!
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)

# Stripe configuration - YOUR SECRET KEY
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# ========== DATABASE MODELS ==========

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    payments = db.relationship('Payment', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    payment_intent_id = db.Column(db.String(100), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='usd')
    status = db.Column(db.String(20), default='pending')
    client_secret = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'payment_intent_id': self.payment_intent_id,
            'amount': self.amount,
            'currency': self.currency,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'user_id': self.user_id
        }

# Create database tables
with app.app_context():
    db.create_all()
    print("✅ Database created successfully!")

# ========== FRONTEND ROUTES ==========

@app.route('/')
def index():
    return {
        'message': 'Payment System API',
        'version': 'v1',
        'status': 'running',
        'database': 'connected',
        'auth': 'available'
    }

@app.route('/health')
def health():
    return {
        'status': 'healthy',
        'environment': 'development'
    }

@app.route('/checkout')
def checkout():
    stripe_public_key = os.getenv('STRIPE_PUBLISHABLE_KEY')
    return render_template('checkout.html', stripe_public_key=stripe_public_key)

@app.route('/login-page')
def login_page():
    return render_template('login.html')

@app.route('/register-page')
def register_page():
    return render_template('register.html')

@app.route('/dashboard')
@jwt_required()
def dashboard():
    return render_template('dashboard.html')

# NEW: Test dashboard without JWT requirement (for debugging)
@app.route('/dashboard-test')
def dashboard_test():
    return render_template('dashboard_test.html')

# ========== AUTHENTICATION ROUTES ==========

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        # Validation
        if not username or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        # Create new user
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Create access token
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'access_token': access_token,
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        # Find user
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Create access token
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'access_token': access_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user.to_dict()), 200

# ========== PAYMENT ROUTES ==========

@app.route('/create-payment', methods=['POST'])
def create_payment():
    try:
        data = request.get_json()
        amount = data.get('amount')
        user_id = data.get('user_id')
        
        if not amount:
            return jsonify({'error': 'Amount is required'}), 400
        
        # Create PaymentIntent in Stripe
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency='usd',
            payment_method_types=['card'],
        )
        
        # Save payment to database
        payment = Payment(
            user_id=user_id,
            payment_intent_id=intent.id,
            amount=amount,
            currency='usd',
            status=intent.status,
            client_secret=intent.client_secret
        )
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'payment_id': payment.id,
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id,
            'amount': amount,
            'currency': 'usd'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/payments', methods=['GET'])
def get_all_payments():
    payments = Payment.query.all()
    return jsonify([payment.to_dict() for payment in payments])

@app.route('/payments/<int:payment_id>', methods=['GET'])
def get_payment(payment_id):
    payment = Payment.query.get(payment_id)
    if not payment:
        return jsonify({'error': 'Payment not found'}), 404
    return jsonify(payment.to_dict())

@app.route('/my-payments', methods=['GET'])
@jwt_required()
def get_my_payments():
    current_user_id = get_jwt_identity()
    payments = Payment.query.filter_by(user_id=current_user_id).all()
    return jsonify([payment.to_dict() for payment in payments])

@app.route('/payment-status/<payment_intent_id>', methods=['GET'])
def payment_status(payment_intent_id):
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        # Update database
        payment = Payment.query.filter_by(payment_intent_id=payment_intent_id).first()
        if payment:
            payment.status = intent.status
            db.session.commit()
        
        return jsonify({
            'id': intent.id,
            'amount': intent.amount / 100,
            'currency': intent.currency,
            'status': intent.status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)