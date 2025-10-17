from flask import Flask, request, redirect, render_template, session, flash
import pymysql
import json
import hashlib
from datetime import datetime, timedelta

def encrypt(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Initialising Stuff
try:
    with open("config.json", "r") as file:
        config = json.load(file)
except FileNotFoundError:
    print("No Config Found")

def create_connection():
    sqlcfg = config['sqlcfg']
    return pymysql.connect(
        host=sqlcfg['host'],
        port=sqlcfg['port'],
        user=sqlcfg['user'],
        password=sqlcfg['passw'],
        database="daily_notices",
        cursorclass=pymysql.cursors.DictCursor
    )

class ClassifiedError(Exception):
    """Used when user is not permitted to view the content
    as they're not logged in.
    """

# Create Flask App
app = Flask(__name__)
app.secret_key = config['secret_key']

@app.route("/", methods=['GET'])
def index():
    current = datetime.today().date()
    date_str = request.args.get("view_date")
    if date_str:
        try:
            view_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            view_date = datetime.today().date()
    else:
        view_date = current
    print(view_date)

    with create_connection().cursor() as cursor:
        query = """
            SELECT notices.*, teachers.lastname, teachers.prefix, teachers.firstname
            FROM notices
            INNER JOIN teachers ON notices.author=teachers.teacher_code
            WHERE startdate <= %s AND enddate >= %s
            ORDER BY startdate DESC
        """
        cursor.execute(query, (view_date, view_date))
        result = cursor.fetchall()
        print(result)
    prev_date = (view_date - timedelta(days=1)).strftime("%Y-%m-%d")
    next_date = (view_date + timedelta(days=1)).strftime("%Y-%m-%d")

    args = {
        "date_display": view_date.strftime("%d-%m-%Y"),
        "view_date": view_date.strftime("%Y-%m-%d"),  
        "notices": result,
        "session": session,
        "current_date": current,
        "prev_date": prev_date,
        "next_date": next_date
    }
    return render_template("index.html", **args)

@app.route("/create", methods=['GET', 'POST'])
def create():
    if session.get('user'):
        print(request.form)
        if request.method == "POST":
            print(request.form)
            title = request.form.get('post_title')
            catergory = request.form.get("catergory")
            content = request.form.get('content')
            start_date = request.form.get('start_date')
            end_date = request.form.get("end_date")
            with create_connection() as connection:
                cursor = connection.cursor()
                query = """
                INSERT INTO notices (`author`, `title`, `body`, `catergory`, `startdate`, `enddate`)
                VALUES (%s, %s, %s, %s, %s, %s);"""
                values = (session.get('user'), title, content, catergory, start_date, end_date,)
                cursor.execute(query, values)
                connection.commit()
            print(content)
            return redirect("/")
        else:
            with create_connection().cursor() as cursor:
                query = "SELECT name FROM catergories ORDER BY idcatergories ASC"
                cursor.execute(query)
                result = cursor.fetchall()
            args = {
                "session": session,
                "catergories": result,
                "todays_date": datetime.today().date(),
                "next_date": (datetime.today().date() + timedelta(days=1)).strftime("%Y-%m-%d")
            }
            return render_template("create.html", **args)
        
    else:
        raise ClassifiedError("Not Logged In")
    
@app.route("/delete", methods=['POST'])
def deleteNotice():
    notice_id = request.form.get("notice_id")
    with create_connection().cursor() as cursor:
        query = "SELECT author FROM notices WHERE notice_id = %s;"
        cursor.execute(query, (notice_id))
        result = cursor.fetchone()
        if result['author'] == session.get('user'):
            delete(notice_id)
    return redirect("/")


def delete(notice_id):
    with create_connection() as connection:
        with connection.cursor() as cursor:
            query = """DELETE FROM notices WHERE notice_id = %s;
            """
            cursor.execute(query, (notice_id))
        connection.commit()
    return True
# Login Methods
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get('passw') == "": passw = None
        else: passw = encrypt(request.form.get('passw'))
        user = request.form.get('user').upper()
        print(user)
        with create_connection().cursor() as cursor:
            query = "SELECT * FROM teachers WHERE teacher_code = %s LIMIT 1"
            values = (user)
            cursor.execute(query, values)
            try:
                result = cursor.fetchall()[0]
                print(result)
            except IndexError: return render_template("login.html", error="Incorect username or Password")
        if result["password"] == passw:
            session['user'] = user
            session['prefix'] = result['prefix']
            session['first_name'] = result['firstname']
            session['last_name'] = result['lastname']
            return redirect("/")
        else:
            return render_template("login.html", error='Incorect username or Password')
    else:
        return redirect("/")

@app.route("/logout", methods=["GET", 'POST'])
def logout():
    session.clear()
    return redirect("/")

@app.route("/profile", methods=['GET', "POST"])
def profile():
    if session.get('user'):
        if request.method == "GET":
            with create_connection().cursor() as cursor:
                query = """SELECT * FROM teachers
                WHERE teacher_code = %s"""
                cursor.execute(query, (session.get('user')))
                result = cursor.fetchone()
            args = {
                "profile": result
            }
            return render_template("profile.html", **args)
        elif request.method == "POST":
            data = request.form
            with create_connection() as conn:
                with conn.cursor() as cursor:
                    user = session.get('user')
                    query = """UPDATE teachers 
                    SET firstname = %s, lastname = %s, prefix = %s
                    WHERE teacher_code = %s"""
                    values = (data.get('first_name'), data.get('last_name'), data.get('prefix'), user)
                    cursor.execute(query, values)
                    conn.commit()
            return redirect("/")
    else:
        raise ClassifiedError("Not Logged In")

@app.errorhandler(pymysql.err.OperationalError)
def sqlConnectionError(error):
    return render_template("errors/databaseerror.html"), 500

@app.errorhandler(404)
def pageNotFound(error):
    return render_template("errors/404.html"), 404

@app.errorhandler(ClassifiedError)
def classifiedError(error):
    return render_template("errors/classified.html"), 401


try:
    connection = create_connection()
    app.run(**config["flask_run"])
except TypeError:
    print("Issue With Config File: Invalid Argument Passed")
except pymysql.err.OperationalError:
    print("Can't Connect to MySQL Server")
