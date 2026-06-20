import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
from store.redis_client import get_recent, get_stats

app = Flask(__name__)


@app.route("/api/feedback")
def feedback():
    return jsonify(get_recent())


@app.route("/api/stats")
def stats():
    return jsonify(get_stats())


if __name__ == "__main__":
    app.run(port=5000)
