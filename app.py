from flask import Flask, request, render_template, url_for, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from falsk_sqlalchemy import desc
from flask_admin import Admin
# from flask_admin.contrib.sqla import ModelView
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_socketio import SocketIO

app = Flask(__name__)

socketio = SocketIO(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

#configuring the database
app.config['SQLALCHEMY_DATABASE_URI']= 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False
app.config['SECRET_KEY'] = '123987456'
db = SQLAlchemy(app)

admin = Admin(app)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    joined_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


    def __repr__(self):
        return f'<User {self.id}: {self.username}>'


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    categories = db.relationship('Category', secondary='post_categories', backref='posts')
    likes = db.relationship('Like', backref='post', lazy=True)
    comments = db.relationship('Comment', cascade='all,delete', backref='post', lazy=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<Post {self.id}: {self.title}>'

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    user = db.relationship('User', backref='likes')
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_like'),)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    post_categories = db.Table('post_categories',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('category.id'), primary_key=True))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


    def __repr__(self):
        return f'<Category {self.id}: {self.name}>'

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

   
    # model fields and relationships
    def __repr__(self):
        return f'<Comment {self.id} on post {self.post_id}>'

with app.app_context():
    db.create_all()

# admin.add_view(ModelView(User, db.session))
# admin.add_view(ModelView(Post, db.session))
# admin.add_view(ModelView(Category, db.session))
# admin.add_view(ModelView(Comment, db.session))
# admin.add_view(ModelView(Like, db.session))

@app.route('/')
@login_required
def index():
    return render_template('index.html', user=current_user)

@socketio.on('message')
def handle_message(message):
    print(f'received message: {message}')

@app.route('/posts')
@login_required
def posts():
    posts = Post.query.order_by(desc(Post.c.created_at)).all()

    return render_template('posts.html', posts=posts, user=current_user)
# Login
# Flask-Login helper to retrieve a user from the database
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Register route
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        password2 = request.form["password2"]

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already taken, Please tyr different', category='danger')
        elif len(email) < 4:
            flash('Email must be longer than 4 characters!', category='danger')
        elif len(name) < 4:
            flash('Username must be longer than 4 characters!', category='danger')
        elif password != password2:
            flash('Passworts must match!', category='danger')
        elif len(password) < 4:
            flash('Password must be longer than 4 character!', category='danger')
        else:
            # Create a new user and add it to the database
            new_user = User(username=name, email=email, password=generate_password_hash(password, method='sha256'))
            db.session.add(new_user)
            db.session.commit()

            # Log the user in
            login_user(new_user, remember=True)
            flash(f'Wellcome {current_user.username}')
            return redirect(url_for("index", user=current_user))
    else:
        return render_template("register.html", user=current_user)

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Get the user with the matching name and password
        user = User.query.filter_by(username=username).first()

        # Log the user in
        if user:
            if check_password_hash(user.password, password):

                login_user(user)
                flash(f'You are logged as {current_user.username}')
                return redirect(url_for("index", user=current_user))
            else:
                flash("Invalid username/password", category='danger')
        else:
            flash('User of password invalid!', category='danger')
        return redirect(url_for("login"))
    else:
        return render_template("login.html", user=current_user)

# Logout route
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('You are logged out login to continue.', category='success')
    return redirect(url_for('login', user=current_user))

# Delete account route
@app.route("/delete_account")
@login_required
def delete_account():
    # Delete the user from the database
    db.session.delete(current_user)
    db.session.commit()

    # Log the user out
    logout_user()

    flash("Wour account is deleted, create new to continue.")
    return redirect(url_for('register'))

# User profile route
@app.route('/user')
@login_required
def user():
    posts = Post.query.filter_by(author_id=current_user.id).all()
    return render_template('user.html', user=current_user, posts=posts)

@app.route('/new-post', methods=['GET', 'POST'])
@login_required
def new_post():
    categories = Category.query.all()
    if request.method == 'POST':
        title = request.form['title']
        text = request.form['text']
        category = request.form['category']

        new_post = Post(title=title, content=text, author_id=current_user.id)
        db.session.add(new_post)
        category = Category.query.filter_by(name=category).first()
        new_post.categories.append(category)
        db.session.commit()
        return redirect(url_for('posts', user=current_user))


    return render_template('new-post.html', user=current_user, categories=categories)

@app.route('/post.<int:post_id>')
def post_details(post_id):
    post = Post.query.get(post_id)
    likes = post.likes
    users = [like.user for like in likes]
    comments = Comment.query.filter_by(post_id=post_id).all()
    return render_template('post-details.html', post=post, user=current_user, comments=comments, users=users)

@app.route('/delete_post.<int:post_id>')
def delete_post(post_id):
    post = Post.query.get(post_id)
    db.session.delete(post)
    db.session.commit()
    return redirect('posts')

@app.route('/update_post.<int:post_id>/<string:page>', methods=['GET', 'POST'])
def update_post(post_id, page):
    if request.method == 'POST':
        id = request.form['id']
        title = request.form['title']
        text = request.form['text']
        category = request.form['category']

        category = Category.query.filter_by(name=category).first()

        post = Post.query.get(id)

        post.categories.append(category)
        post.title = title
        post.content = text
        # post.categories = category
        db.session.commit()
        if page == 'post_details':
            return redirect(url_for('post_details', post_id=post_id))
        else:
            return redirect(url_for(page))

    post = Post.query.get(post_id)
    categories = Category.query.all()
    return render_template('update.html', post=post,user=current_user, categories=categories)

@app.route('/like_post.<int:post_id>/<string:page>', methods=['GET', 'POST'])
def like_post(post_id, page):
    user_id = current_user.id
    existing_like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
    if existing_like:
        if page == 'post_details':
            return redirect(url_for('post_details', post_id=post_id))
        else:
            return redirect(url_for(page))
    new_like = Like(user_id=user_id, post_id=post_id)
    db.session.add(new_like)
    db.session.commit()
    if page == 'post_details':
        return redirect(url_for('post_details', post_id=post_id))
    else:
        return redirect(url_for(page))

@app.route('/post<int:post_id>/add_comment', methods=['GET', 'POST'])
def add_comment(post_id):
    post = Post.query.get(post_id)
    content = request.form['content']
    if content:
        new_comment = Comment(content=content, author_id=current_user.id, post_id=post_id)
        db.session.add(new_comment)
        db.session.commit()
    return redirect(url_for('post_details', post_id=post.id))

@app.route('/update_comment.<int:comment_id>')
def update_comment(comment_id):

    return redirect(url_for('post_details', post_id=post.id))


@app.route('/delete_comment.<int:comment_id>')
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)
    post = Post.query.get(comment.post_id)
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for('post_details', post_id=post.id))

@app.route('/new_caregory', methods=['GET', 'POST'])
def new_category():
    if request.method == 'POST':
        category_name = request.form['name']
        if category_name:
            new_category = Category(name=category_name)
            db.session.add(new_category)
            db.session.commit()

    return redirect(url_for('index'))

# Protected route
@app.route("/protected")
@login_required
def protected():
    return "Logged in as: " + current_user.username
# Login

if __name__ == '__main__':
    socketio.run(app)

lorem = 'Lorem, ipsum dolor sit amet consectetur adipisicing elit. Dignissimos libero minus provident dolore dolorem laboriosam eligendi veniam nam sequi, sit et recusandae inventore eaque optio esse rerum? Aut odio voluptas, provident tempore iusto doloribus? Magnam illo sequi laborum excepturi dolor.'