import os
import json
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = "lenny_social_2026_key"
app.jinja_env.add_extension('jinja2.ext.do')

# Configuration
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
DATA_FILE = "data.json"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'}

# Ensure upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": [], "posts": [], "chats": [], "follows": [], "likes": [], "comments": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_current_user():
    if "username" in session:
        data = load_data()
        return next((u for u in data["users"] if u["username"] == session["username"]), None)
    return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.template_filter('format_datetime')
def format_datetime(value):
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%b %d, %H:%M")
    except:
        return "Just now"

# --- AUTH ROUTES ---

@app.route("/")
def index():
    return redirect(url_for('feed')) if "username" in session else redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u_name, pwd = request.form.get("username"), request.form.get("password")
        data = load_data()
        user = next((u for u in data["users"] if u["username"] == u_name and u["password"] == pwd), None)
        if user:
            session["username"] = u_name
            return redirect(url_for("feed"))
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u_name, pwd = request.form.get("username"), request.form.get("password")
        data = load_data()
        if any(u["username"] == u_name for u in data["users"]): 
            return "User already exists!"
        data["users"].append({
            "username": u_name, "password": pwd, "bio": "New here!", 
            "profile_pic": "default.png", "is_verified": False
        })
        save_data(data)
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- FEED & POST ROUTES ---

@app.route("/feed", methods=["GET", "POST"])
def feed():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    data = load_data()
    
    if request.method == "POST":
        content = request.form.get("content")
        file = request.files.get("file")
        f_url, f_type = None, None
        if file and file.filename and allowed_file(file.filename):
            fname = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            f_url = fname
            f_type = 'video' if fname.rsplit('.', 1)[1].lower() in {'mp4', 'mov', 'avi'} else 'image'
        
        if content or f_url:
            data.setdefault("posts", []).append({
                "id": str(datetime.now().timestamp()), 
                "author": user["username"], "content": content, 
                "file_url": f_url, "file_type": f_type, "timestamp": datetime.now().isoformat()
            })
            save_data(data)
            return redirect(url_for("feed"))
            
    return render_template("feed.html", 
                           posts=data.get("posts", [])[::-1], 
                           current_user=user, 
                           users=data["users"], 
                           likes=data.get("likes", []), 
                           comments=data.get("comments", []))

@app.route("/delete_post/<post_id>")
def delete_post(post_id):
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    data = load_data()
    post = next((p for p in data.get("posts", []) if p["id"] == post_id), None)
    if post and (post["author"] == user["username"] or user["username"] == "Lenny Fisbeck"):
        data["posts"] = [p for p in data["posts"] if p["id"] != post_id]
        data["likes"] = [l for l in data.get("likes", []) if l["post_id"] != post_id]
        data["comments"] = [c for c in data.get("comments", []) if c["post_id"] != post_id]
        save_data(data)
    return redirect(url_for("feed"))

@app.route("/like/<post_id>")
def like_post(post_id):
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    data = load_data()
    data.setdefault("likes", [])
    existing = next((l for l in data["likes"] if l["post_id"] == post_id and l["user"] == user["username"]), None)
    if existing: data["likes"].remove(existing)
    else: data["likes"].append({"post_id": post_id, "user": user["username"]})
    save_data(data)
    return redirect(request.referrer or url_for("feed"))

@app.route("/comment/<post_id>", methods=["POST"])
def add_comment(post_id):
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    content = request.form.get("content")
    if content:
        data = load_data()
        data.setdefault("comments", []).append({
            "post_id": post_id, "user": user["username"], 
            "content": content, "timestamp": datetime.now().isoformat()
        })
        save_data(data)
    return redirect(request.referrer or url_for("feed"))

# --- SEARCH & SOCIAL ROUTES ---

@app.route("/search")
def search():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    query = request.args.get("q", "")
    data = load_data()
    results = [u for u in data["users"] if query.lower() in u["username"].lower()]
    return render_template("search.html", results=results, current_user=user, query=query)

@app.route("/profile/<username>")
def profile(username):
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    data = load_data()
    p_user = next((u for u in data["users"] if u["username"] == username), None)
    if not p_user: return "User not found", 404
    
    is_following = any(f for f in data.get("follows", []) if f["follower"] == user["username"] and f["following"] == username)
    followers_count = len([f for f in data.get("follows", []) if f["following"] == username])
    following_count = len([f for f in data.get("follows", []) if f["follower"] == username])
    return render_template("profile.html", profile_user=p_user, current_user=user, is_following=is_following, followers_count=followers_count, following_count=following_count)

@app.route("/follow/<username>")
def follow_user(username):
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    data = load_data()
    data.setdefault("follows", [])
    existing = next((f for f in data["follows"] if f["follower"] == user["username"] and f["following"] == username), None)
    if existing: data["follows"].remove(existing)
    else: data["follows"].append({"follower": user["username"], "following": username})
    save_data(data)
    return redirect(url_for("profile", username=username))

@app.route("/edit_profile", methods=["POST"])
def edit_profile():
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    data = load_data()
    for u in data["users"]:
        if u["username"] == user["username"]:
            u["bio"] = request.form.get("bio")
            file = request.files.get("profile_pic")
            if file and file.filename:
                fname = secure_filename(f"profile_{u['username']}.png")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                u["profile_pic"] = fname
            break
    save_data(data)
    return redirect(url_for("profile", username=user["username"]))

# --- CHAT ROUTES ---

@app.route("/chats")
@app.route("/chat/<friend_username>", methods=["GET", "POST"])
def chats_overview(friend_username=None):
    user = get_current_user()
    if not user: return redirect(url_for("login"))
    data = load_data()
    if friend_username and request.method == "POST":
        msg = request.form.get("message")
        if msg:
            data.setdefault("chats", []).append({"from": user["username"], "to": friend_username, "message": msg, "timestamp": datetime.now().isoformat()})
            save_data(data)
    u_chats = [c for c in data.get("chats", []) if c["from"] == user["username"] or c["to"] == user["username"]]
    msgs = [c for c in u_chats if (c["from"]==user["username"] and c["to"]==friend_username) or (c["from"]==friend_username and c["to"]==user["username"])] if friend_username else []
    friend = next((u for u in data["users"] if u["username"] == friend_username), None)
    return render_template("chats.html", chats=u_chats, messages=msgs, friend=friend, current_user=user)

if __name__ == "__main__":
    app.run(debug=True)







































