from flask import Flask, request, redirect, render_template, session, flash
import pymysql
import json
import hashlib
from datetime import datetime, timedelta
import ast

def encrypt(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Initialising flask and Config
try:
    with open("config.json", "r") as file:
        config = json.load(file) #open config file config.json
except FileNotFoundError:
    print("No Config Found") # error handling

def create_connection():
    sqlcfg = config['sqlcfg']
    return pymysql.connect(
        host=sqlcfg['host'],
        port=sqlcfg['port'],
        user=sqlcfg['user'],
        password=sqlcfg['passw'],
        database="daily_notices",
        cursorclass=pymysql.cursors.DictCursor
    ) # sql connection

class ClassifiedError(Exception):
    """Used when user is not permitted to view the content
    as they're not logged in.
    """ # define error for if user is not logged in

# Create Flask App
app = Flask(__name__)
app.secret_key = config['secret_key'] # initialising flask

#=======
# ROUTES
#=======

# HOME PAGE
@app.route("/", methods=['GET'])
def index():
    current = datetime.today().date()
    date_str = request.args.get("view_date") # get the current date and the user's requested date
    if date_str:
        try:
            view_date = datetime.strptime(date_str, "%Y-%m-%d").date() # convert the date to the proper format for the website
        except ValueError:
            view_date = datetime.today().date()
    else:
        view_date = current

    with create_connection() as connection:
        with connection.cursor() as cursor:
            query = """
                SELECT notices.*, teachers.lastname, teachers.prefix, teachers.firstname
                FROM notices
                INNER JOIN teachers ON notices.author=teachers.teacher_code
                WHERE startdate <= %s AND enddate >= %s
                ORDER BY startdate DESC
            """ # This gets the notices for the view date from the notices table
            cursor.execute(query, (view_date, view_date))
            result = cursor.fetchall()
    prev_date = (view_date - timedelta(days=1)).strftime("%Y-%m-%d") # get the next and previous dates for the buttons
    next_date = (view_date + timedelta(days=1)).strftime("%Y-%m-%d")

    args = { # arguments to be passed to the website
        "date_display": view_date.strftime("%d-%m-%Y"), # for top of the page
        "view_date": view_date.strftime("%Y-%m-%d"), #the date we are actually viewing, to be passed to the calender
        "notices": result, # notices
        "session": session, # session, login and whatnot
        "current_date": current, # current date for real
        "prev_date": prev_date, # for buttons
        "next_date": next_date
    }
    return render_template("index.html", **args) # render

@app.route("/create", methods=['GET', 'POST']) # creating / editing post
def create():
    # check user logged in
    if session.get('user'):
        # if the method is post
        if request.method == "POST":
            title = request.form.get('post_title')
            catergory = request.form.get("catergory")
            content = request.form.get('content')
            start_date = request.form.get('start_date')
            end_date = request.form.get("end_date")
            existing_id = request.form.get("existing_id") # get all the arguments

            with create_connection() as connection: # create mysql connection
                with connection.cursor() as cursor:
                    if existing_id: # if editing a notice
                        query = """UPDATE notices
                        SET title = %s, catergory = %s, body = %s, startdate = %s, enddate = %s
                        WHERE notice_id = %s AND author = %s""" # querey
                        values = (title, catergory, content[:2500], start_date, end_date, existing_id, session.get("user"))
                        cursor.execute(query, values) # update
                    else: # if not updating a notice
                        query = """
                        INSERT INTO notices (`author`, `title`, `body`, `catergory`, `startdate`, `enddate`)
                        VALUES (%s, %s, %s, %s, %s, %s);"""
                        values = (session.get('user'), title, content[:2500], catergory, start_date, end_date,)
                        cursor.execute(query, values)
                connection.commit()
            return redirect("/") # redirect home
        else: # if we are getting we are creating a new notice instead of updating database
            with create_connection() as connection:
                with connection.cursor() as cursor:
                    query = "SELECT name FROM catergories ORDER BY idcatergories ASC"
                    cursor.execute(query)
                    result = cursor.fetchall() # get all the catergories
            args = {
                "session": session, # session data
                "catergories": result, # catergories
                "todays_date": datetime.today().date(),
                "next_date": (datetime.today().date() + timedelta(days=1)).strftime("%Y-%m-%d") # for calender inputs
            } # set the arguments
            notice_id = request.args.get("notice_id") # if the user is updating a notice we get the chosen id from the url
            if notice_id:
                with create_connection() as connection:
                    with connection.cursor() as cursor:
                        query = "SELECT * FROM notices WHERE notice_id = %s AND author = %s"
                        cursor.execute(query, (notice_id, session.get('user')))
                        args['notice_edit'] = cursor.fetchone() # get the notice data and update the args
                
            return render_template("create.html", **args) # render the template for the editor
        
    else:
        raise ClassifiedError("Not Logged In") # if user is not logged in raise an error and send them to the error page
    
@app.route("/delete", methods=['POST']) # for deleting a notice
def deleteNotice():
    notice_id = request.form.get("notice_id") # get the notice id
    with create_connection() as connection:
        with connection.cursor() as cursor:
            query = """DELETE FROM notices WHERE notice_id = %s AND author = %s;
            """
            cursor.execute(query, (notice_id, session.get('user'))) # delete the notice but only if all this matches
        connection.commit() # commit
    return redirect("/") # send them home

# Login Methods
@app.route("/login", methods=["POST"])
def login():
    if request.form.get('passw') == "": passw = None # just in case idk why this works but it makes it equal null so the database likes it
    else: passw = encrypt(request.form.get('passw')) # otherwise you can encrypt it database HATES encrypted null strings
    user = request.form.get('user').upper() # change teachercode to uppercase just in case
    with create_connection() as connection:
            with connection.cursor() as cursor:
                query = "SELECT * FROM teachers WHERE teacher_code = %s LIMIT 1"
                values = (user)
                cursor.execute(query, values) # find the teacher code stuff
                try:
                    result = cursor.fetchall()[0] # fetchall
                except IndexError: return render_template("login.html", error="Incorect username or Password") # if you wrong show user an error
    if result.get('password') == passw: # if username and password match set the session and send them home
        session['user'] = user
        session['prefix'] = result['prefix']
        session['first_name'] = result['firstname']
        session['last_name'] = result['lastname']
        return redirect("/")
    else:
        return render_template("login.html", error='Incorect username or Password') # otherwise show them an error

@app.route("/logout", methods=["GET", 'POST'])
def logout():
    session.clear() # clear the session and log them out
    return redirect("/")

@app.route("/profile", methods=['GET', "POST"]) # for editing the user profile
def profile():
    if session.get('user'): # check they logged in
        if request.method == "GET":
            with create_connection() as connection:
                with connection.cursor() as cursor:
                    query = """SELECT * FROM teachers
                    WHERE teacher_code = %s"""
                    cursor.execute(query, (session.get('user'))) # get the user info from database
                    result = cursor.fetchone()
            args = {
                "profile": result # set the result as the arguments
            }
            return render_template("profile.html", **args)
        elif request.method == "POST": # if the method is post we wanna update the database
            data = request.form
            with create_connection() as conn:
                with conn.cursor() as cursor:
                    user = session.get('user')
                    query = """UPDATE teachers 
                    SET firstname = %s, lastname = %s, prefix = %s
                    WHERE teacher_code = %s"""
                    values = (data.get('first_name'), data.get('last_name'), data.get('prefix'), user)
                    cursor.execute(query, values)
                    conn.commit() # update the details accordingly them commit to database
            return redirect("/") # send them home
    else:
        raise ClassifiedError("Not Logged In") # if they not logged in then send them to the error page

#===============
# ERROR HANDLING
#===============

# if the database switches off at any point handle that
@app.errorhandler(pymysql.err.OperationalError)
def sqlConnectionError(error):
    return render_template("errors/databaseerror.html"), 500

# if the user visits an incorrect page
@app.errorhandler(404)
def pageNotFound(error):
    return render_template("errors/404.html"), 404

# if the user aint logged in and tries to do logged in activies
@app.errorhandler(ClassifiedError)
def classifiedError(error):
    return render_template("errors/classified.html"), 401

# of te user visits like the /login route and they're using the wrong method jus send them to the home page
@app.errorhandler(405)
def methodNotAllowed(error):
    return redirect("/")

#==================
# INITIALISE FLASK
#==================
try:
    # test the sql connection before starting no funny buisness
    with create_connection() as connection:
        print("Database Connection Sucessful")
    app.run(**config["flask_run"]) # run the app with configuration from config.json
except TypeError:
    print("Issue With Config File: Invalid Argument Passed") # if theres an issue with the config then tell the user
except pymysql.err.OperationalError:
    print("Can't Connect to MySQL Server") # if sql offline then tell the user
except ZeroDivisionError:
    print("Dont divide by zero") # i dont even know how you could manage this error but i put it in here just in case
# no blank except cuz obviously if the error is not listed above you probably want to solve it
