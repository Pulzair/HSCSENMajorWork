from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO

socketio = SocketIO(async_mode="threading")

limiter = Limiter(key_func=get_remote_address, default_limits=[])
