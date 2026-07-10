"""Backward-compatibility guarantees for the frozen 1.0.0-candidate API."""

from pathlib import Path

import flask_nacos
from flask_nacos import FlaskNacos
from flask_nacos.discovery import normalize_instance

SECRET_KEYS = ("NACOS_PASSWORD", "NACOS_ACCESS_KEY", "NACOS_SECRET_KEY")


class _ObjInstance:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_standard_mode_still_works(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)
    assert "nacos" in app.extensions
    assert nacos.config is not None


def test_factory_mode_still_works(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos()
    nacos.init_app(app)
    assert "nacos" in app.extensions
    assert nacos.config is not None


def test_register_instance_returns_bool(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)
    assert nacos.register_instance() is True


def test_deregister_instance_returns_bool(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)
    nacos.register_instance()
    assert nacos.deregister_instance() is True


def test_list_instances_old_style_call(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)
    result = nacos.list_instances("user-service")
    assert isinstance(result, list)


def test_get_one_healthy_instance_old_style_call(make_app, patched_create_client):
    app = make_app()
    nacos = FlaskNacos(app)
    result = nacos.get_one_healthy_instance("user-service")
    assert result is None or isinstance(result, dict)


def test_get_config_returns_raw_string(make_app, patched_create_client, fake_client):
    fake_client.get_config.return_value = "server.port=8000"
    app = make_app()
    nacos = FlaskNacos(app)
    content = nacos.get_config("application.properties")
    assert content == "server.port=8000"
    assert isinstance(content, str)


def test_get_status_has_no_secrets(make_app, patched_create_client):
    app = make_app(
        {
            "NACOS_PASSWORD": "nacos",
            "NACOS_ACCESS_KEY": "ak-demo",
            "NACOS_SECRET_KEY": "sk-demo",
        }
    )
    nacos = FlaskNacos(app)
    status = nacos.get_status()
    for key in SECRET_KEYS:
        assert key not in status
    for value in status.values():
        assert value not in ("ak-demo", "sk-demo")


def test_normalize_instance_dict_and_object():
    as_dict = normalize_instance({"ip": "10.0.0.1", "port": 8080, "serviceName": "svc"})
    assert as_dict["service_name"] == "svc"

    as_obj = normalize_instance(_ObjInstance(ip="10.0.0.2", port=9000, service_name="svc2"))
    assert as_obj["service_name"] == "svc2"


def test_no_unsupported_features_on_surface():
    assert not hasattr(FlaskNacos, "get_config_as_dict")
    assert not hasattr(FlaskNacos, "load_config_to_flask")
    assert "get_config_as_dict" not in flask_nacos.__all__


def test_py_typed_present():
    package_dir = Path(flask_nacos.__file__).parent
    assert (package_dir / "py.typed").is_file()


def test_version_is_090():
    assert flask_nacos.__version__ == "0.9.0"
