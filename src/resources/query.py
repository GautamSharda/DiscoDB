from flask import Flask, request
import json
import types
import requests
from ratelimit import sleep_and_retry, limits
from tools import discord_crud, json_tools, logger
import jwt
from base64 import b64decode

from __main__ import app

def validate_user(encoded_token, user_id):
    user_json = json.loads(discord_crud.query_message(discord_crud.USERS_CHANNEL_ID, user_id))
    secret = b64decode(user_json["secret"])
    token = jwt.decode(encoded_token, secret, algorithms=["HS256"])
    return token["user"] == user_json["user"]

CONFIG = dict(json.load(open("config.json")))
HEADERS = CONFIG["HEADERS"]
BASE_URL = CONFIG["BASE_URL"]

@sleep_and_retry
@limits(calls=2,period=1)
def get_matches(channel_id: str, attributes: dict):
    matches = {"message_ids": []}
    parameters = {"limit":100}
    message_list = requests.get(f'{BASE_URL}/channels/{channel_id}/messages', params=parameters, headers=HEADERS)
    while len(message_list.json()) != 0:
        for message in message_list.json():
            message_content = json.loads(message["content"])
            if json_tools.match_json(attributes, message_content):
                matches["message_ids"].append(message["id"])

        parameters["before"] = message_list.json()[-1]["id"]
        message_list = requests.get(f'{BASE_URL}/channels/{channel_id}/messages', params=parameters, headers=HEADERS) 

    return matches


@app.route('/query/', methods=['GET'])
def query():
    encoded_token = request.headers.get('token')
    user_id = request.headers.get('user-id')
    if validate_user(encoded_token, user_id) == False:
        logger.log_failure(403)
        return {"status": 403, "error": "User is not authorized"}
    
    request_body = json.loads(request.data, strict=False)
    target_channel = request_body["channel_id"]
    attributes = request_body["attributes"]

    matches = get_matches(target_channel, attributes)

    return matches, 200