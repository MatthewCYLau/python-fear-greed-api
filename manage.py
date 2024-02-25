from api import app
from api.subscriber.subscribe import streaming_pull_pub_sub_subscription


def runserver():
    app.run(host="0.0.0.0", port=8080, debug=True, use_reloader=True)


if __name__ == "__main__":
    runserver()
    streaming_pull_pub_sub_subscription()
