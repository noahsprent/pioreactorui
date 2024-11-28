# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import sqlite3
import tempfile
import typing as t
from datetime import datetime
from datetime import timezone
from logging import handlers

import paho.mqtt.client as mqtt
from flask import Flask
from flask import g
from flask import jsonify
from flask.json.provider import JSONProvider
from msgspec.json import decode as loads
from msgspec.json import encode as dumps
from paho.mqtt.enums import CallbackAPIVersion
from pioreactor.config import config as pioreactor_config
from pioreactor.config import get_leader_hostname
from pioreactor.whoami import am_I_leader
from pioreactor.whoami import get_unit_name

from .config import env
from .version import __version__

VERSION = __version__
HOSTNAME = get_unit_name()
NAME = f"pioreactorui-{HOSTNAME}"


# set up logging
logger = logging.getLogger(NAME)
logger.setLevel(logging.DEBUG)

logs_format = logging.Formatter(
    "%(asctime)s [%(name)s] %(levelname)-2s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)

ui_logs = handlers.WatchedFileHandler(
    pioreactor_config.get("logging", "ui_log_file", fallback="/var/log/pioreactor.log")
)
ui_logs.setFormatter(logs_format)
logger.addHandler(ui_logs)


logger.debug(f"Starting {NAME}={VERSION} on {HOSTNAME}...")
logger.debug(f".env={dict(env)}")

client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
client.username_pw_set(
    pioreactor_config.get("mqtt", "username", fallback="pioreactor"),
    pioreactor_config.get("mqtt", "password", fallback="raspberry"),
)


def decode_base64(string: str) -> str:
    return loads(string)


def create_app():
    from .unit_api import unit_api
    from .api import api

    app = Flask(NAME)

    app.register_blueprint(unit_api)

    if am_I_leader():
        app.register_blueprint(api)
        # we currently only need to communicate with MQTT for the leader.
        # don't even connect if a worker - if the leader is down, this will crash and restart the server over and over.
        client.connect(
            host=pioreactor_config.get("mqtt", "broker_address", fallback="localhost"),
            port=pioreactor_config.getint("mqtt", "broker_port", fallback=1883),
        )
        logger.debug("Starting MQTT client")
        client.loop_start()

    @app.teardown_appcontext
    def close_connection(exception) -> None:
        db = getattr(g, "_app_database", None)
        if db is not None:
            db.close()

        db = getattr(g, "_metadata_database", None)
        if db is not None:
            db.close()

    @app.errorhandler(404)
    def handle_not_found(e):
        # Return JSON for API requests
        return jsonify({"error": "Not Found"}), 404

    @app.errorhandler(500)
    def handle_server_error(e):
        return jsonify({"error": "Internal server error. See logs."}), 500

    app.json = MsgspecJsonProvider(app)
    app.get_json = app.json.loads

    return app


def msg_to_JSON(msg: str, task: str, level: str) -> bytes:
    return dumps(
        {
            "message": msg.strip(),
            "task": task,
            "source": "ui",
            "level": level,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    )


def publish_to_log(msg: str, task: str, level="DEBUG") -> None:
    publish_to_experiment_log(msg, "$experiment", task, level)


def publish_to_experiment_log(msg: str | t.Any, experiment: str, task: str, level="DEBUG") -> None:
    if not isinstance(msg, str):
        # attempt to serialize
        try:
            msg = dumps(msg)
        except TypeError:
            msg = str(msg)

    getattr(logger, level.lower())(msg)

    topic = f"pioreactor/{get_leader_hostname()}/{experiment}/logs/ui/{level.lower()}"
    client.publish(topic, msg_to_JSON(msg, task, level))


def publish_to_error_log(msg, task: str) -> None:
    publish_to_log(msg, task, "ERROR")


def _make_dicts(cursor, row) -> dict:
    return dict((cursor.description[idx][0], value) for idx, value in enumerate(row))


def _get_app_db_connection():
    db = getattr(g, "_app_database", None)
    if db is None:
        db = g._app_database = sqlite3.connect(pioreactor_config.get("storage", "database"))
        db.create_function(
            "BASE64", 1, decode_base64
        )  # TODO: until next OS release which implements a native sqlite3 base64 function

        db.row_factory = _make_dicts
        db.execute("PRAGMA foreign_keys = 1")

    return db


def _get_local_metadata_db_connection():
    db = getattr(g, "_metadata_database", None)
    if db is None:
        db = g._local_metadata_database = sqlite3.connect(
            f"{tempfile.gettempdir()}/local_intermittent_pioreactor_metadata.sqlite"
        )
        db.row_factory = _make_dicts
    return db


def query_app_db(
    query: str, args=(), one: bool = False
) -> dict[str, t.Any] | list[dict[str, t.Any]] | None:
    assert am_I_leader()
    cur = _get_app_db_connection().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def query_local_metadata_db(
    query: str, args=(), one: bool = False
) -> dict[str, t.Any] | list[dict[str, t.Any]] | None:
    cur = _get_local_metadata_db_connection().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def modify_app_db(statement: str, args=()) -> int:
    assert am_I_leader()
    con = _get_app_db_connection()
    cur = con.cursor()
    try:
        cur.execute(statement, args)
        con.commit()
    except sqlite3.IntegrityError:
        return 0
    except Exception as e:
        print(e)
        con.rollback()  # TODO: test
        raise e
    finally:
        row_changes = cur.rowcount
        cur.close()
    return row_changes


class MsgspecJsonProvider(JSONProvider):
    def dumps(self, obj, **kwargs):
        return dumps(obj)

    def loads(self, obj, type=None, **kwargs):
        if type is not None:
            return loads(obj, type=type)
        else:
            return loads(obj)
