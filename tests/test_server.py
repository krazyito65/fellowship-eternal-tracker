from pathlib import Path

import threading

import time

import urllib.request

import json

from http.server import HTTPServer

import pytest

from app.server import TrackerHandler

from app import server

from app import config

import tempfile

import os



@pytest.fixture(scope="module")

def test_server():

    # Setup isolated config

    fd, path = tempfile.mkstemp(suffix=".json")

    with os.fdopen(fd, 'w') as f:

        json.dump({"characters": [{"id":1, "slug":"test"}], "teams": []}, f)

    

    old_config_path = config.CONFIG_PATH

    config.CONFIG_PATH = Path(path)

    

    # Mock scraper cache to avoid real network requests

    server._cache_data = [

        {"id": 1, "slug": "test", "name": "Test", "levels": [], "season": None, "pinnacle": None, "error": None}

    ]

    server._cache_time = time.time()

    

    # Start server

    httpd = HTTPServer(("127.0.0.1", 8125), TrackerHandler)

    server_thread = threading.Thread(target=httpd.serve_forever)

    server_thread.daemon = True

    server_thread.start()

    

    yield "http://127.0.0.1:8125"

    

    httpd.shutdown()

    httpd.server_close()

    server_thread.join(timeout=2)

    config.CONFIG_PATH = old_config_path

    os.remove(path)



def test_server_get_index(test_server):

    req = urllib.request.urlopen(test_server + "/")

    assert req.getcode() == 200

    html = req.read().decode("utf-8")

    assert "Fellowship Eternal Tracker" in html



def test_server_get_api_config(test_server):

    req = urllib.request.urlopen(test_server + "/api/config")

    assert req.getcode() == 200

    data = json.loads(req.read().decode("utf-8"))

    assert "characters" in data

    assert data["characters"][0]["slug"] == "test"



def test_server_post_api_config(test_server):

    new_cfg = {"characters": [], "teams": [{"name": "test_team", "members": {}}]}

    req = urllib.request.Request(

        test_server + "/api/config",

        data=json.dumps(new_cfg).encode("utf-8"),

        method="POST"

    )

    resp = urllib.request.urlopen(req)

    assert resp.getcode() == 200

    resp_data = json.loads(resp.read().decode("utf-8"))

    assert resp_data["status"] == "ok"

    

    # Verify it saved

    get_req = urllib.request.urlopen(test_server + "/api/config")

    saved_cfg = json.loads(get_req.read().decode("utf-8"))

    assert len(saved_cfg.get("teams", [])) == 1

    assert saved_cfg["teams"][0]["name"] == "test_team"



def test_server_404(test_server):

    try:

        urllib.request.urlopen(test_server + "/api/not_found")

    except urllib.error.HTTPError as e:

        assert e.code == 404

import urllib.request



import json



import tests.test_server as ts







def test_server_team_dungeons(test_server):



    data = json.dumps({"test": "hero"}).encode("utf-8")



    req = urllib.request.Request(



        test_server + "/api/team-dungeons",



        data=data,



        method="POST"



    )



    resp = urllib.request.urlopen(req)



    assert resp.getcode() == 200







def test_server_hero_details(test_server):



    data = json.dumps({"char": "test", "hero": "testhero"}).encode("utf-8")



    req = urllib.request.Request(



        test_server + "/api/hero-details",



        data=data,



        method="POST"



    )



    resp = urllib.request.urlopen(req)



    assert resp.getcode() == 200



