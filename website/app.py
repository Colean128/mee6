from flask import Flask, session, request, url_for, render_template, redirect, \
jsonify, make_response, flash, abort
import os
from functools import wraps
from requests_oauthlib import OAuth2Session
import redis
import json
import binascii
from math import floor

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "qdaopdsjDJ9u&çed&ndlnad&pjéà&jdndqld")

REDIS_URL = os.environ.get('REDIS_URL')
OAUTH2_CLIENT_ID = os.environ['OAUTH2_CLIENT_ID']
OAUTH2_CLIENT_SECRET = os.environ['OAUTH2_CLIENT_SECRET']
OAUTH2_REDIRECT_URI = os.environ.get('OAUTH2_REDIRECT_URI', 'http://localhost:5000/confirm_login')
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://discordapp.com/api')
AUTHORIZATION_BASE_URL = API_BASE_URL + '/oauth2/authorize'
DOMAIN = os.environ.get('VIRTUAL_HOST', 'localhost:5000')
TOKEN_URL = API_BASE_URL + '/oauth2/token'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

db = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# CSRF
@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            abort(403)

def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = str(binascii.hexlify(os.urandom(15)))
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token

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
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/logout')
def logout():
    session.pop('user')

    return redirect(url_for('index'))

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
        if session['user'].get('avatar') is None:
            session['user']['avatar'] = url_for('static', filename='img/no_logo.png')
        else:
            session['user']['avatar'] = "https://cdn.discordapp.com/avatars/"+session['user']['id']+"/"+session['user']['avatar']+".jpg"


def get_user_servers(user, guilds):
    return list(filter(lambda g: g['owner'] is True, guilds))

@app.route('/servers')
@require_auth
def select_server():
    guild_id = request.args.get('guild_id')
    if guild_id:
        return redirect(url_for('dashboard', server_id=int(guild_id)))

    get_or_update_user()
    user_servers = get_user_servers(session['user'], session['guilds'])

    return render_template('select-server.html', user_servers=user_servers)

def server_check(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        server_id = kwargs.get('server_id')
        server_ids = db.smembers('servers')

        if str(server_id) not in server_ids:
            url = "https://discordapp.com/oauth2/authorize?&client_id={}"\
                "&scope=bot&permissions={}&guild_id={}&response_type=code&redirect_uri=http://{}/servers".format(
                OAUTH2_CLIENT_ID,
                '66321471',
                server_id,
                DOMAIN
                )
            return redirect(url)

        return f(*args, **kwargs)
    return wrapper

def require_bot_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        server_id = kwargs.get('server_id')
        user_servers = get_user_servers(session['user'], session['guilds'])
        if str(server_id) not in list(map(lambda g: g['id'], user_servers)):
            return redirect(url_for('select_server'))

        return f(*args, **kwargs)
    return wrapper

@app.route('/dashboard/<int:server_id>')
@require_auth
@require_bot_admin
@server_check
def dashboard(server_id):
    servers = session['guilds']
    server = list(filter(lambda g: g['id']==str(server_id), servers))[0]
    enabled_plugins = db.smembers('plugins:{}'.format(server_id))
    return render_template('dashboard.html', server=server, enabled_plugins=enabled_plugins)

@app.route('/dashboard/<int:server_id>/commands')
@require_auth
@require_bot_admin
@server_check
def plugin_commands(server_id):
    disable = request.args.get('disable')
    if disable:
        db.srem('plugins:{}'.format(server_id), 'Commands')
        return redirect(url_for('dashboard', server_id=server_id))

    db.sadd('plugins:{}'.format(server_id), 'Commands')

    servers = session['guilds']
    server = list(filter(lambda g: g['id']==str(server_id), servers))[0]
    enabled_plugins = db.smembers('plugins:{}'.format(server_id))

    commands = []
    commands_names = db.smembers('Commands.{}:commands'.format(server_id))
    for cmd in commands_names:
        command = {
            'name': cmd,
            'message': db.get('Commands.{}:command:{}'.format(server_id, cmd))
        }
        commands.append(command)
    commands = sorted(commands, key=lambda k: k['name'])

    return render_template('plugin-commands.html',
        server=server,
        enabled_plugins=enabled_plugins,
        commands=commands
        )

@app.route('/dashboard/<int:server_id>/commands/add', methods=['POST'])
def add_command(server_id):
    cmd_name = request.form.get('cmd_name', '')
    cmd_message = request.form.get('cmd_message', '')

    edit = cmd_name in db.smembers('Commands.{}:commands'.format(server_id))
    print(edit)

    import re
    cb = url_for('plugin_commands', server_id=server_id)
    if len(cmd_name) == 0 or len(cmd_name) > 15:
        flash('A command name should be between 1 and 15 character long !', 'danger')
    elif not edit and not re.match("^[A-Za-z0-9_-]*$", cmd_name):
        flash('A command name should only contain letters from a to z, numbers, _ or -', 'danger')
    elif len(cmd_message) == 0 or len(cmd_message)>2000:
        flash('A command message should be between 1 and 2000 character long !', 'danger')
    else:
        if not edit :
            cmd_name = '!'+cmd_name
        db.sadd('Commands.{}:commands'.format(server_id), cmd_name)
        db.set('Commands.{}:command:{}'.format(server_id, cmd_name), cmd_message)
        if edit:
            flash('Command {} edited !'.format(cmd_name), 'success')
        else:
            flash('Command {} added !'.format(cmd_name), 'success')

    return redirect(cb)

@app.route('/dashboard/<int:server_id>/commands/<string:command>/delete')
@require_auth
@require_bot_admin
@server_check
def delete_command(server_id, command):
    db.srem('Commands.{}:commands'.format(server_id), command)
    db.delete('Commands.{}:command:{}'.format(server_id, command))
    flash('Command {} deleted !'.format(command), 'success')
    return redirect(url_for('plugin_commands', server_id=server_id))

@app.route('/dashboard/<int:server_id>/help')
@require_auth
@require_bot_admin
@server_check
def plugin_help(server_id):
    disable = request.args.get('disable')
    if disable:
        db.srem('plugins:{}'.format(server_id), 'Help')
        return redirect(url_for('dashboard', server_id=server_id))

    db.sadd('plugins:{}'.format(server_id), 'Help')

    servers = session['guilds']
    server = list(filter(lambda g: g['id']==str(server_id), servers))[0]
    enabled_plugins = db.smembers('plugins:{}'.format(server_id))

    return render_template('plugin-help.html',
        server=server,
        enabled_plugins=enabled_plugins
        )

@app.route('/dashboard/<int:server_id>/levels')
@require_auth
@require_bot_admin
@server_check
def plugin_levels(server_id):
    disable = request.args.get('disable')
    if disable:
        db.srem('plugins:{}'.format(server_id), 'Levels')
        return redirect(url_for('dashboard', server_id=server_id))
    db.sadd('plugins:{}'.format(server_id), 'Levels')
    servers = session['guilds']
    server = list(filter(lambda g: g['id']==str(server_id), servers))[0]
    enabled_plugins = db.smembers('plugins:{}'.format(server_id))

    initial_announcement = 'GG {player}, you just advanced to **level {level}** !'
    announcement_enabled = db.get('Levels.{}:announcement_enabled'.format(server_id))
    announcement = db.get('Levels.{}:announcement'.format(server_id))
    if announcement is None:
        db.set('Levels.{}:announcement'.format(server_id), initial_announcement)
        db.set('Levels.{}:announcement_enabled'.format(server_id), '1')
        announcement_enabled = '1'

    announcement = db.get('Levels.{}:announcement'.format(server_id))

    banned_members = db.smembers('Levels.{}:banned_members'.format(server_id)) or []
    banned_roles = db.smembers('Levels.{}:banned_roles'.format(server_id)) or []

    cooldown = db.get('Levels.{}:cooldown'.format(server_id)) or 0

    return render_template('plugin-levels.html',
        server = server,
        enabled_plugins = enabled_plugins,
        announcement = announcement,
        announcement_enabled = announcement_enabled,
        banned_members = banned_members,
        banned_roles = banned_roles,
        cooldown = cooldown
        )

@app.route('/dashboard/<int:server_id>/levels/update', methods=['POST'])
@require_auth
@require_bot_admin
@server_check
def update_levels(server_id):
    servers = session['guilds']
    server = list(filter(lambda g: g['id']==str(server_id), servers))[0]

    banned_members = request.form.getlist('banned_members[]')
    banned_roles = request.form.getlist('banned_roles[]')
    announcement = request.form.get('announcement')
    enable = request.form.get('enable')
    cooldown = request.form.get('cooldown')

    try:
        cooldown = int(cooldown)
    except ValueError:
        flash('The cooldown that you provided isn\'t an integer!', 'warning')
        return redirect(url_for('plugin_levels', server_id=server_id))

    if announcement == '' or len(announcement) > 2000:
        flash('The level up announcement could not be empty or have 2000+ characters.', 'warning')
    else:
        db.set('Levels.{}:announcement'.format(server_id), announcement)
        db.set('Levels.{}:cooldown'.format(server_id), cooldown)

        db.delete('Levels.{}:banned_members'.format(server_id))
        if len(banned_members)>0:
            db.sadd('Levels.{}:banned_members'.format(server_id), *banned_members)

        db.delete('Levels.{}:banned_roles'.format(server_id))
        if len(banned_roles)>0:
            db.sadd('Levels.{}:banned_roles'.format(server_id), *banned_roles)

        if enable:
            db.set('Levels.{}:announcement_enabled'.format(server_id), '1')
        else:
            db.delete('Levels.{}:announcement_enabled'.format(server_id))

        flash('Settings updated ;) !', 'success')

    return redirect(url_for('plugin_levels', server_id=server_id))


@app.route('/levels/<int:server_id>')
def levels(server_id):
    server_check = str(server_id) in db.smembers('servers')
    if not server_check:
        return redirect(url_for('index'))
    plugin_check = 'Levels' in db.smembers('plugins:{}'.format(server_id))
    if not plugin_check:
        return redirect(url_for('index'))

    server = {
        'id': server_id,
        'icon': db.get('server:{}:icon'.format(server_id)),
        'name': db.get('server:{}:name'.format(server_id))
    }

    _players = db.sort('Levels.{}:players'.format(server_id),
                by='Levels.{}:player:*:xp'.format(server_id),
                get=[
                    'Levels.{}:player:*:xp'.format(server_id),
                    'Levels.{}:player:*:lvl'.format(server_id),
                    'Levels.{}:player:*:name'.format(server_id),
                    'Levels.{}:player:*:avatar'.format(server_id),
                    'Levels.{}:player:*:discriminator'.format(server_id),
                    '#'
                     ],
                start=0,
                num=100,
                desc=True)

    players = []
    for i in range(0, len(_players),6):
        lvl = int(_players[i+1])
        x = 0
        for l in range(0,lvl):
            x += 100*(1.2**l)
        remaining_xp = int(int(_players[i]) - x)
        player = {
            'total_xp': int(_players[i]),
            'xp': remaining_xp,
            'lvl': _players[i+1],
            'lvl_xp': int(100*(1.2**lvl)),
            'xp_percent': floor(100*(remaining_xp)/(100*(1.2**lvl))),
            'name': _players[i+2],
            'avatar': _players[i+3],
            'discriminator': _players[i+4],
            'id': _players[i+5]
        }
        players.append(player)
    return render_template('levels.html', players=players, server=server, title="{} leaderboard - Mee6 bot".format(server['name']))

@app.route('/dashboard/<int:server_id>/welcome')
@require_auth
@require_bot_admin
@server_check
def plugin_welcome(server_id):
    disable = request.args.get('disable')
    if disable:
        db.srem('plugins:{}'.format(server_id), 'Welcome')
        return redirect(url_for('dashboard', server_id=server_id))
    db.sadd('plugins:{}'.format(server_id), 'Welcome')
    servers = session['guilds']
    server = list(filter(lambda g: g['id']==str(server_id), servers))[0]
    enabled_plugins = db.smembers('plugins:{}'.format(server_id))

    initial_welcome = '{user}, Welcome to **{server}** ! Have a great time here :wink: !'
    welcome_message = db.get('Welcome.{}:welcome_message'.format(server_id))
    channel_name = db.get('Welcome.{}:channel_name'.format(server_id))
    if welcome_message is None:
        db.set('Welcome.{}:welcome_message'.format(server_id), initial_welcome)
        welcome_message = initial_welcome

    return render_template('plugin-welcome.html',
        server=server,
        enabled_plugins=enabled_plugins,
        welcome_message=welcome_message,
        channel_name=channel_name
        )

@app.route('/dashboard/<int:server_id>/welcome/update', methods=['POST'])
@require_auth
@require_bot_admin
@server_check
def update_welcome(server_id):
    servers = session['guilds']
    server = list(filter(lambda g: g['id']==str(server_id), servers))[0]

    welcome_message = request.form.get('welcome_message')
    channel_name = request.form.get('channel_name')

    if welcome_message == '' or len(welcome_message) > 2000:
        flash('The welcome message cannot be empty or have 2000+ characters.', 'warning')
    else:
        db.set('Welcome.{}:welcome_message'.format(server_id), welcome_message)
        db.set('Welcome.{}:channel_name'.format(server_id), channel_name)
        flash('Settings updated ;) !', 'success')

    return redirect(url_for('plugin_welcome', server_id=server_id))

@app.route('/dashboard/<int:server_id>/animu')
@require_auth
@require_bot_admin
@server_check
def plugin_animu(server_id):
    disable = request.args.get('disable')
    if disable:
        db.srem('plugins:{}'.format(server_id), 'AnimuAndMango')
        return redirect(url_for('dashboard', server_id=server_id))

    db.sadd('plugins:{}'.format(server_id), 'AnimuAndMango')

    servers = session['guilds']
    server = list(filter(lambda g: g['id']==str(server_id), servers))[0]
    enabled_plugins = db.smembers('plugins:{}'.format(server_id))

    return render_template('plugin-animu.html',
        server=server,
        enabled_plugins=enabled_plugins
        )

if __name__=='__main__':
    app.debug = True
    app.run()
