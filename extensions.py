# import libraries
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO

# socketio lives here not app.py so blueprints can import it without a circular import
socketio = SocketIO(async_mode="threading")

# rate limiter keyed on IP, no default limit so only login and register are capped
limiter = Limiter(key_func=get_remote_address, default_limits=[])
