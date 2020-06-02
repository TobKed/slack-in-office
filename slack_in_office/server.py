from flask import Flask, request

from main import slash

if __name__ == "__main__":
    app = Flask(__name__)

    @app.route("/", methods=["POST"])
    def view():
        return slash(request)

    app.run()
