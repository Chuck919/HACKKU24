# app.py
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask import render_template_string
from flask import url_for, redirect, flash
import secrets
from sqlalchemy.exc import IntegrityError



app = Flask(__name__)
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

# Define route for form submission
@app.route('/submit', methods=['POST'])
def submit():
    email = request.form['email']
    text = request.form['text']
    
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        # Redirect existing users to sameuser.html page
        return redirect(url_for('sameuser'))

    # Create a new user since it doesn't exist
    user = User(email=email, text=text)
    user.unsubscribe_token = secrets.token_urlsafe(16)  # Generate a new token
    
    try:
        # Add new user record and commit changes to the database
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        # Handle integrity error (email already exists)
        db.session.rollback()
        # Log the error or perform any necessary actions
    
    send_email(email, text)  # Pass the text to the send_email function
    return 'Form submitted successfully!'

# Define function to send email
def send_email(email, text):
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
            return 'You have been unsubscribed successfully.'
        else:
            return 'Invalid unsubscribe token.'
    else:
        # No token provided, prompt user to enter email
        if request.method == 'POST':
            email = request.form.get('email')
            user = User.query.filter_by(email=email).first()
            if user:
                db.session.delete(user)
                db.session.commit()
                return 'You have been unsubscribed successfully.'
            else:
                return 'Invalid email address. Please try again.'
        return render_template('unsub.html')

# Define route for sameuser page
@app.route('/sameuser')
def sameuser():
    return render_template('sameuser.html')

@app.route('/update_info', methods=['GET', 'POST'])
def update_info():
    if request.method == 'POST':
        new_text = request.form.get('text')
        # Update the user's text in the database
        user = User.query.first()  # Assuming there's only one user for this example
        user.text = new_text
        db.session.commit()
        flash('Update successful!', 'success')  # Flash message for successful update
        return redirect('/')  # Redirect to the homepage
    return render_template('change.html')




        

# Run the Flask app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)