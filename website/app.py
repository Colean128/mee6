from flask import Flask, session, request, url_for, render_template, redirect, jsonify
import os
from functools import wraps
from requests_oauthlib import OAuth2Session
import redis

app = Flask(__name__)
app.debug = True
app.config['SECRET_KEY'] = "qdaopdsjDJ9u&çed&ndlnad&pjéà&jdndqld"

REDIS_URL = os.environ.get('REDIS_URL')
OAUTH2_CLIENT_ID = os.environ['OAUTH2_CLIENT_ID']
OAUTH2_CLIENT_SECRET = os.environ['OAUTH2_CLIENT_SECRET']
OAUTH2_REDIRECT_URI = 'http://localhost:5000/confirm_login'
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://discordapp.com/api')
AUTHORIZATION_BASE_URL = API_BASE_URL + '/oauth2/authorize'
TOKEN_URL = API_BASE_URL + '/oauth2/token'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

db = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def token_updater(token):
    session['oauth2_token'] = token

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = session.get('user')
        if user is None:
            return redirect(url_for('login'))

        return f(*args, **kwargs)
    return wrapper

def make_session(token=None, state=None, scope=None):
    return OAuth2Session(
        client_id=OAUTH2_CLIENT_ID,
        token=token,
        state=state,
        scope=scope,
        redirect_uri=OAUTH2_REDIRECT_URI,
        auto_refresh_kwargs={
            'client_id': OAUTH2_CLIENT_ID,
            'client_secret': OAUTH2_CLIENT_SECRET,
        },
        auto_refresh_url=TOKEN_URL,
        token_updater=token_updater)

@app.route('/')
def index():
    user = session.get('user')
    if user is not None:
        return redirect(url_for('select_server'))

    return render_template('index.html')

@app.route('/login')
def login():
    user = session.get('user')
    if user is not None:
        return redirect(url_for('select_server'))

    scope = 'identify guilds'.split()
    discord = make_session(scope=scope)
    authorization_url, state = discord.authorization_url(AUTHORIZATION_BASE_URL)
    session['oauth2_state'] = state
    return redirect(authorization_url)

@app.route('/confirm_login')
def confirm_login():
    if request.values.get('error'):
        return redirect(url_for('index'))

    discord = make_session(state=session.get('oauth2_state'))
    token = discord.fetch_token(
        TOKEN_URL,
        client_secret=OAUTH2_CLIENT_SECRET,
        authorization_response=request.url)
    session['oauth2_token'] = token
    get_or_update_user()

    return redirect(url_for('select_server'))

def get_or_update_user():
    oauth2_token = session.get('oauth2_token')
    if oauth2_token:
        discord = make_session(token=oauth2_token)
        session['user'] = discord.get(API_BASE_URL + '/users/@me').json()
        session['guilds'] = discord.get(API_BASE_URL + '/users/@me/guilds').json()


def get_user_server(user, guilds):
    return list(filter(lambda g: g['owner'] is True, guilds))

@app.route('/servers')
@require_auth
def select_server():
    get_or_update_user()
    user_servers = get_user_server(session['user'], session['guilds'])

    return render_template('select_server.html', user_servers=user_servers)

def server_check(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        server_id = args[0]
        server_ids = redis.smembers('servers')

        if server_id not in server_ids:
            url = "https://discordapp.com/oauth2/authorize?&client_id={}"\
                "&scope=bot&permissions={}&guild_id={}".format(
                OAUTH2_CLIENT_ID,
                '1'*32,
                server_id
                )
            return redirect(url)

        return f(*args, **kwargs)
    return wrapper

def require_bot_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        server_id = args[0]
        user_servers = get_user_server(session['user'], session['guilds'])
        if server_id not in list(map(lambda g: g['id'], user_servers)):
            return redirect(url_for('select_server'))

        return f(*args, **kwargs)
    return wrapper

@app.route('/dashboard/<int:server_id>')
@require_auth
@require_bot_admin
@server_check
def dashboard(server_id):
    return "Welcome to server "+server_id

app.run()
