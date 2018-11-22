import os
import csv
import requests
import json

from flask import Flask, session, render_template, request, redirect, url_for
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


# Base route where the user can login or resgister.
@app.route("/", methods = ["GET","POST"])
def index():
    # If the user submitted a username and pasword
    if request.method == "POST":

        # If the user is registerting an account
        if "register" in request.form:
            # Get input of user's username and password
            inputUsername = request.form.get("registerUsername")
            inputPassword = request.form.get("registerPassword")

            # If either field is blank reload the page with an error messagae.
            if "" in [inputUsername, inputPassword]:
                return render_template("login.html", message = "Please don't leave forms blank")

            # Check if username contains invalid characters
            if InvalidCharacters(inputUsername) or InvalidCharacters(inputPassword):
                return render_template("login.html", message = "Invalid username or password")

            # Check to see if the username or password alerady exists in the database
            if db.execute("SELECT 1 FROM accounts WHERE username = :inputUsername", {"inputUsername": inputUsername}).rowcount !=0:
                return render_template("login.html", message = "Username is already taken")
            if db.execute("SELECT 1 FROM accounts WHERE password = :inputPassword", {"inputPassword": inputPassword}).rowcount !=0:
                return render_template("login.html", message = "Password is already taken")

            # Else, add the username to the account table in the database
            db.execute("INSERT INTO accounts (username, password) VALUES (:username, :password)", {"username": inputUsername, "password":inputPassword})
            db.commit()

            # Remember the user and store variable on the server
            session["currentUser"] = inputUsername
            return (url_for('home'))

        # If the user is logging in
        else:
            # Get input of user's username and password
            loginUsername = request.form.get("loginUsername")
            loginPassword = request.form.get("loginPassword")

            # Check to see if the username and password exist in database
            if db.execute("SELECT 1 FROM accounts WHERE username = :username AND password = :password", {"username": loginUsername, "password":loginPassword}).rowcount == 0:
                # If not, reload the page with a messagae of incorrect credentials
                return render_template("login.html", message = "Incorrect username or password")
            # If the account does exist, log in and redirect to the site homepage
            session["currentUser"] = loginUsername
            return redirect(url_for('home'))

    # Initially Load the page the first time
    else:
        session["currentUser"] = None
        return render_template("login.html")


@app.route("/home", methods = ["GET", "POST"])
def home():
    # If user managed to navigate here without loging in, send them back to do so
    if session["currentUser"] is None:
        return redirect(url_for('index'))

    # if the user searches for a book
    if request.method == "POST":
        input =  request.form.get("search")
        input  = '%' + input + '%'

        # display all books whose title, author, or isbn is like the keyword searched
        selectedBooks = db.execute("SELECT * FROM books WHERE title LIKE :input OR isbn LIKE :input OR author LIKE :input", {"input": input}).fetchall()
        return render_template("home.html",selectedBooks = selectedBooks)
    # display the homepage initially
    return render_template("home.html", currentUser = session["currentUser"])

# This route takes the name of whatever book isbn is passed in as its argument or typed into the url
@app.route("/<string:bookIsbn>", methods = ["GET","POST"])
def book(bookIsbn):
    user = session["currentUser"]

    # If the user submits a book review
    if request.method == "POST":
        # Get the rating and the text review
        rating = request.form.get("rating")
        review = request.form.get("message")

        # Insert the rating, review, book, and user into a table
        db.execute("INSERT INTO reviews (rating, review, isbn, username) VALUES (:rating, :review, :isbn, :username)", {"rating": rating, "review":review, "isbn":bookIsbn, "username":user})
        db.commit()
        # redirect the user to the book route without the rating form
        return redirect(url_for('book', bookIsbn = bookIsbn))

    # get corresponding book info for isbn
    bookInfo = db.execute("SELECT * FROM books WHERE isbn = :bookIsbn", {"bookIsbn": bookIsbn}).fetchone()

    # if a book isn't associated with the input isbn, display an error
    if bookInfo is None:
        return render_template("error.html", errorMessage = "ISBN not recognized", currentUser = session["currentUser"])

    # get the Goodreads review data on the book
    reviewData = getGoodreadsReview(bookIsbn)

    # if a user isn't logged in, display only the book info
    if user is None or db.execute("SELECT 1 FROM reviews WHERE username = :username AND isbn = :isbn", {"username": user, "isbn":bookIsbn}).rowcount !=0:
        return render_template("bookInfo.html", bookInfo = bookInfo , avgRating = reviewData[0], reviewCount = reviewData[1])

    # else, display the book data as well as the form
    return render_template("bookForm.html", bookInfo = bookInfo , avgRating = reviewData[0], reviewCount = reviewData[1], currentUser = session["currentUser"])


@app.route("/logout", methods = ["GET"])
def logout():
    # if the user ever hits the logout button, tell them they're logged out and set the current user to none
    return render_template("logout.html")
    session["currentUser"] = None

# check to see if input has invalid characters
def InvalidCharacters (input):
    for i in input:
        if i in [' ','?','<','>',',','.','+','=','`']:
            return True
    return False

# query the goodreads database for the review data on the input isbn
def getGoodreadsReview(isbn):
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "30zVt6TlsDN6KcBKtF9pqA", "isbns": isbn})
    data = res.json()
    avgRating = data['books'][0]['average_rating']
    reviewCount = data['books'][0]['work_reviews_count']
    reviewData = (avgRating, reviewCount)
    return reviewData
