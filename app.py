# app.py
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask import render_template_string
from flask import url_for, redirect, flash
import secrets
from sqlalchemy.exc import IntegrityError



app = Flask(__name__)

app.secret_key = '***REMOVED***' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

app.config['MAIL_SERVER']='smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = '***REMOVED***'
app.config['MAIL_PASSWORD'] = '***REMOVED***'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

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

    def __init__(self, email, text):
        self.email = email
        self.text = text
        self.unsubscribe_token = secrets.token_urlsafe(16)

# Define route for index page
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/submit', methods=['POST'])
def submit():
    email = request.form['email']
    text = request.form['text']
    
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return redirect(url_for('sameuser', email=email))
    
    
    # Check if text is empty
    if not text.strip():
        flash('You do not have an account. Please enter which topics you would like', 'error')
        return render_template('index.html')  # Redirect to the user form page


    user = User(email=email, text=text)
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
                      sender='***REMOVED***',
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
    token = request.args.get('token')
    if token:
        # Unsubscribe the user based on the token
        user = User.query.filter_by(unsubscribe_token=token).first()
        if user:
            db.session.delete(user)
            db.session.commit()
            return render_template('success.html')
        else:
            flash('Unidentified user. Please try again.', 'error')
            return render_template('index.html')  
    else:
        # No token provided, prompt user to enter email
        if request.method == 'POST':
            email = request.form.get('email')
            user = User.query.filter_by(email=email).first()
            if user:
                db.session.delete(user)
                db.session.commit()
                return render_template('success.html')
            else:
                flash('Invalid email provided. Please try again.', 'error')
                return render_template('index.html')  
        return render_template('unsub.html')

# Define route for sameuser page
@app.route('/sameuser')
def sameuser():
    email = request.args.get('email')
    print(email)
    return render_template('sameuser.html', email=email)

@app.route('/update_info', methods=['GET', 'POST'])
def update_info():
    email = request.form.get('email')
    text = request.form.get('text')

    print(email)  # For debugging purposes
    print(text)   # For debugging purposes

    user = User.query.filter_by(email=email).first()
    if request.method == 'POST':
        new_text = request.form.get('text')
        # Update the user's text in the database
        user.text = new_text
        db.session.commit()
        return render_template('success.html')  # Redirect to the homepage
    return render_template('change.html')

@app.route('/success')
def success():
    return render_template('success.html')


        

# Run the Flask app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)