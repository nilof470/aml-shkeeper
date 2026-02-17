import threading
import app

server = app.create_app()

if __name__ == '__main__':
    server.run(debug=app.config['DEBUG'], use_reloader=False, host="0.0.0.0", port=6000)