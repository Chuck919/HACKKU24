# app.py
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask import render_template_string
from flask import url_for, redirect, flash
import secrets
from sqlalchemy.exc import IntegrityError
from config import Config


app = Flask(__name__)

app.config.from_object(Config)

# Initialize Flask-Mail
mail = Mail(app)
# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Define User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    text = db.Column(db.Text, nullable=False)
    unsubscribe_token = db.Column(db.String(32), unique=True, nullable=False)
    include_charts = db.Column(db.Boolean, default=False, nullable=False)
    include_sp500_chart = db.Column(db.Boolean, default=False, nullable=False)
    include_nasdaq_chart = db.Column(db.Boolean, default=False, nullable=False)
    include_bitcoin_chart = db.Column(db.Boolean, default=False, nullable=False)
    include_top10_stocks = db.Column(db.Boolean, default=False, nullable=False)
    include_stock_suite = db.Column(db.Boolean, default=False, nullable=False)
    include_market_news = db.Column(db.Boolean, default=False, nullable=False)

    def __init__(self, email, text, include_charts=False, include_sp500_chart=False, 
                 include_nasdaq_chart=False, include_bitcoin_chart=False, include_top10_stocks=False,
                 include_stock_suite=False, include_market_news=False):
        self.email = email
        self.text = text
        self.include_charts = include_charts
        self.include_sp500_chart = include_sp500_chart
        self.include_nasdaq_chart = include_nasdaq_chart
        self.include_bitcoin_chart = include_bitcoin_chart
        self.include_top10_stocks = include_top10_stocks
        self.include_stock_suite = include_stock_suite
        self.include_market_news = include_market_news
        self.unsubscribe_token = secrets.token_urlsafe(16)

# Define route for index page
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/submit', methods=['POST'])
def submit():
    email = request.form['email']
    text = request.form['text']
    include_charts = request.form.get('include_charts') == 'on'
    include_sp500_chart = request.form.get('include_sp500_chart') == 'on'
    include_nasdaq_chart = request.form.get('include_nasdaq_chart') == 'on'
    include_bitcoin_chart = request.form.get('include_bitcoin_chart') == 'on'
    include_top10_stocks = request.form.get('include_top10_stocks') == 'on'
    include_stock_suite = request.form.get('include_stock_suite') == 'on'
    include_market_news = request.form.get('include_market_news') == 'on'
    
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return redirect(url_for('sameuser', token=existing_user.unsubscribe_token))
    
    
    # Check if text is empty
    if not text.strip():
        flash('You do not have an account. Please enter which topics you would like', 'error')
        return render_template('index.html')  # Redirect to the user form page


    user = User(email=email, text=text, include_charts=include_charts,
                include_sp500_chart=include_sp500_chart, include_nasdaq_chart=include_nasdaq_chart,
                include_bitcoin_chart=include_bitcoin_chart, include_top10_stocks=include_top10_stocks,
                include_stock_suite=include_stock_suite, include_market_news=include_market_news)
    user.unsubscribe_token = secrets.token_urlsafe(16)
    
    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    
    try:
        send_email(email, text)
    except:
        flash('Invalid email. Please try again later.', 'error')
        return render_template('index.html')  # Redirect to the user form page
    

    return render_template('success.html')  # Redirect to the user form page

# Define function to send email
def send_email(email, text):
    # This function is called outside of any route function, so make sure
    # it's being called within the application context.
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user:
            unsubscribe_link = url_for('unsubscribe', token=user.unsubscribe_token, _external=True)
            homepage_link = url_for('index', _external=True)
            print("Unsubscribe link:", unsubscribe_link)  # Debugging statement
            print("Homepage link:", homepage_link)  # Debugging statement
        else:
            unsubscribe_link = ""
            homepage_link = ""
            print("User not found or email is empty")  # Debugging statement
        msg = Message('Thank you for submitting the form!',
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[email])

        # Generate unsubscribe link with token
        unsubscribe_link = url_for('unsubscribe', token=user.unsubscribe_token, _external=True)
        homepage_link = url_for('index', _external=True)

        # Render HTML template with the text from the form submission and unsubscribe link
        html_content = render_template('email_content.html',
                                       text=text,
                                       unsubscribe_link=unsubscribe_link,
                                       homepage_link=homepage_link)

        # Set the email body with HTML content
        msg.html = html_content

        mail.send(msg)

@app.route('/unsubscribe', methods=['GET', 'POST'])
def unsubscribe():
    token = request.args.get('token') or request.form.get('token')
    
    if request.method == 'POST':
        # Handle POST request (actual unsubscribe action)
        if token:
            user = User.query.filter_by(unsubscribe_token=token).first()
        else:
            email = request.form.get('email')
            user = User.query.filter_by(email=email).first()
        
        if user:
            db.session.delete(user)
            db.session.commit()
            return render_template('success.html')
        else:
            flash('Invalid information provided. Please try again.', 'error')
            return redirect(url_for('index'))
    
    # GET request - show confirmation page
    if token:
        user = User.query.filter_by(unsubscribe_token=token).first()
        if user:
            return render_template('unsub.html', user=user, token=token)
        else:
            flash('Invalid unsubscribe link.', 'error')
            return redirect(url_for('index'))
    else:
        # No token, show manual email entry form
        return render_template('unsub.html')

# Define route for sameuser page
@app.route('/sameuser')
def sameuser():
    token = request.args.get('token')
    user = User.query.filter_by(unsubscribe_token=token).first()
    if user:
        return render_template('sameuser.html', user=user, token=token)
    else:
        flash('Invalid access. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/update_info', methods=['GET', 'POST'])
def update_info():
    token = request.args.get('token') or request.form.get('token')
    
    if not token:
        flash('Invalid access. Please use the link from your email.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.filter_by(unsubscribe_token=token).first()
    
    if not user:
        flash('Invalid access token.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        new_text = request.form.get('text')
        include_charts = request.form.get('include_charts') == 'on'
        include_sp500_chart = request.form.get('include_sp500_chart') == 'on'
        include_nasdaq_chart = request.form.get('include_nasdaq_chart') == 'on'
        include_bitcoin_chart = request.form.get('include_bitcoin_chart') == 'on'
        include_top10_stocks = request.form.get('include_top10_stocks') == 'on'
        include_stock_suite = request.form.get('include_stock_suite') == 'on'
        include_market_news = request.form.get('include_market_news') == 'on'
        
        # Update the user's text and chart preferences in the database
        user.text = new_text
        user.include_charts = include_charts
        user.include_sp500_chart = include_sp500_chart
        user.include_nasdaq_chart = include_nasdaq_chart
        user.include_bitcoin_chart = include_bitcoin_chart
        user.include_top10_stocks = include_top10_stocks
        user.include_stock_suite = include_stock_suite
        user.include_market_news = include_market_news
        db.session.commit()
        return render_template('success.html')
    
    return render_template('change.html', user=user, token=token)

@app.route('/success')
def success():
    return render_template('success.html')


        

# Run the Flask app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)