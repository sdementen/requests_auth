from flask import Flask, jsonify, request
import jwt
import datetime
import logging

app = Flask(__name__)

logger = logging.getLogger(__name__)


@app.route('/get_query_args', methods=['GET'])
def get_query_args():
    return jsonify(request.args)


@app.route('/get_headers', methods=['GET'])
def get_headers():
    return jsonify(list(request.headers))


already_asked_for_quick_expiry = [False]


@app.route('/status')
def get_status():
    return 'OK'


@app.route('/provide_token_as_custom_token')
def post_token_as_my_custom_token():
    response_type = request.args.get('response_type')
    if 'custom_token' != response_type:
        raise Exception('custom_token was expected to be received as response_type. Got {0} instead.'.format(
            response_type))
    expiry_in_1_hour = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    return submit_a_form_with_a_token(expiry_in_1_hour, 'custom_token')


@app.route('/provide_token_as_token')
def post_token_as_token():
    expiry_in_1_hour = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    return submit_a_form_with_a_token(expiry_in_1_hour, 'token')


@app.route('/provide_token_as_token_but_without_providing_state')
def post_without_state():
    expiry_in_1_hour = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    return submit_a_form_without_state(expiry_in_1_hour, 'token')


@app.route('/do_not_provide_token')
def post_without_token():
    return submit_an_empty_form()


@app.route('/provide_a_token_expiring_in_1_second')
def post_token_quick_expiry():
    if already_asked_for_quick_expiry[0]:
        expiry_in_1_hour = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        return submit_a_form_with_a_token(expiry_in_1_hour, 'token')
    else:
        already_asked_for_quick_expiry[0] = True
        expiry_in_1_second = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
        return submit_a_form_with_a_token(expiry_in_1_second, 'token')


@app.route('/do_not_redirect')
def close_page_so_that_client_timeout_waiting_for_token():
    return close_page()


def submit_a_form_with_a_token(token_expiry, response_type):
    redirect_uri = request.args.get('redirect_uri')
    state = request.args.get('state')
    token = create_token(token_expiry)
    return """
<html>
    <body>
        <form method="POST" name="hiddenform" action="{0}">
            <input type="hidden" name="{1}" value="{2}" />
            <input type="hidden" name="state" value="{3}" />
            <noscript>
                <p>Script is disabled. Click Submit to continue.</p>
                <input type="submit" value="Submit" />
            </noscript>
        </form>
        <script language="javascript">document.forms[0].submit();</script>
    </body>
</html>
        """.format(redirect_uri, response_type, token, state)


def submit_a_form_without_state(token_expiry, response_type):
    redirect_uri = request.args.get('redirect_uri')
    token = create_token(token_expiry)
    return """
<html>
    <body>
        <form method="POST" name="hiddenform" action="{0}">
            <input type="hidden" name="{1}" value="{2}" />
            <noscript>
                <p>Script is disabled. Click Submit to continue.</p>
                <input type="submit" value="Submit" />
            </noscript>
        </form>
        <script language="javascript">document.forms[0].submit();</script>
    </body>
</html>
        """.format(redirect_uri, response_type, token)


def submit_an_empty_form():
    redirect_uri = request.args.get('redirect_uri')
    return """
<html>
    <body>
        <form method="POST" name="hiddenform" action="{0}">
            <noscript>
                <p>Script is disabled. Click Submit to continue.</p>
                <input type="submit" value="Submit" />
            </noscript>
        </form>
        <script language="javascript">document.forms[0].submit();</script>
    </body>
</html>
        """.format(redirect_uri)


def close_page():
    return """
<html>
    <body onload="window.open('', '_self', ''); window.setTimeout(close, 1)">
    </body>
</html>
        """


def create_token(expiry):
    return jwt.encode({'exp': expiry}, 'secret').decode('unicode_escape')


def start_server(port):
    logger.info('Starting test server on port {0}.'.format(port))
    app.run(port=port)


if __name__ == '__main__':
    start_server(5001)
