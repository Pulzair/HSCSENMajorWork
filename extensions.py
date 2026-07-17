from flask_socketio import SocketIO

# Lives here and not in app.py so the blueprints can import socketio without
# importing app.py back (circular import city otherwise)
socketio = SocketIO(async_mode="threading")
