## Inspiration

The inspiration behind our project, [**Any News**](https://changwen919.eu.pythonanywhere.com/), is rooted in our commitment to social good. In today's information age, staying informed is crucial, but the overwhelming volume of news can be daunting and often leads to information overload. Learning about the topics you want on a daily basis not only keeps you informed on what your interests are but also keeps you engaged in society. With [**Any News**](https://changwen919.eu.pythonanywhere.com/), you can easily access any information you want and need, and never have to sift through thousands of articles again.

## Setup Instructions

### Prerequisites
- Python 3.7+
- pip (Python package manager)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Chuck919/HACKKU24.git
cd HACKKU24
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` and fill in your actual credentials:
     - `SECRET_KEY`: A secure random string for Flask sessions
     - `MAIL_USERNAME`: Your Gmail address
     - `MAIL_PASSWORD`: Your Gmail App Password (see [Gmail App Passwords](https://support.google.com/accounts/answer/185833))
     - `MEDIASTACK_API_KEY`: Your MediaStack API key from [mediastack.com](https://mediastack.com/)

4. Initialize the database:
```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

5. Run the application:
```bash
python app.py
```

The application will be available at `http://localhost:5000`

### Configuration

All sensitive configuration is managed through environment variables in the `.env` file. Never commit this file to version control.

## What it does

[**Any News**](https://changwen919.eu.pythonanywhere.com/) is a web application that allows users to input their topics of interest and their email address. Using the _MediaStack API_, the application fetches relevant articles related to the user's specified topics. Users receive daily email updates containing curated news articles tailored to their preferences. Additionally, users have the flexibility to unsubscribe from the email updates at any time and modify their selected topics.

## How we built it

We built [**Any News**](https://changwen919.eu.pythonanywhere.com/) using the **Flask web** framework for the backend and **HTML/CSS** for the frontend. We integrated the _MediaStack API_ to fetch news articles based on user-inputted topics. User authentication and email delivery functionalities were implemented using **Flask** extensions. The application is hosted on a _Python Anywhere_, a web hosting and cloud platform, to ensure accessibility and reliability.

## Challenges we ran into

One of the main challenges we encountered was managing user subscriptions and preferences. Add users with enough information but still with a streamlined process was the most difficult part. Additionally, integrating the **Flask** email extensions and creating a gmail account that properly functions with all the necessities was also challenging.

## Accomplishments that we're proud of

We are proud to have developed a user-friendly and efficient platform that delivers personalized news updates to our users. The feeling of finally overcoming our challenges cannot be overstated. Additionally, successfully implementing features such as user authentication, subscription management, and email delivery demonstrates our team's dedication and technical proficiency. 

## What we learned

Through building [**Any News**](https://changwen919.eu.pythonanywhere.com/), we gained valuable experience in web development, API integration, and user experience design. We learned how to effectively leverage external APIs to enhance the functionality of our application and how to implement authentication mechanisms and advanced user functionalities.

## What's next for Any News

In the future, we plan to further enhance [**Any News**](https://changwen919.eu.pythonanywhere.com/) by implementing additional features and improving existing functionalities. Some potential areas for expansion include:

- Enhancing the user interface to provide a more seamless and intuitive experience.
- Incorporating machine learning algorithms to personalize news recommendations based on user behavior.
- Integrating social media sharing capabilities to allow users to share interesting articles with their networks.
- Expanding the range of supported news sources and languages to cater to a broader audience.
- Implementing real-time notifications for breaking news updates and user interactions.
