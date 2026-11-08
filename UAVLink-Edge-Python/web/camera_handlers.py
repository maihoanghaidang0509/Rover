"""Camera API handlers — delegates to camera_service (dual CAM, Pi_CM5 parity)."""

from web import camera_service as svc


def _cfg():
    from web.server import _cfg_ref
    return _cfg_ref


def camera_start():
    cfg = _cfg()
    if cfg is None:
        return {"success": False, "message": "Config not loaded"}, 500
    return svc.camera_restart(cfg)


def camera_stop():
    with svc._manager_lock:
        svc._stop_manager_locked()
    return {"success": True, "message": "Camera streamer stopped"}, 200


def camera_status():
    return svc.camera_status_full(_cfg())


def camera_test():
    result, _status = svc.camera_detect(refresh=True)
    if result.get("connected_count", 0) > 0:
        return {
            "success": True,
            "cameras": [
                {"id": c.get("libcamera_index"), "info": c.get("sensor_name", c.get("sensor"))}
                for c in result.get("connected", [])
            ],
        }, 200
    return {
        "success": False,
        "message": "Không phát hiện camera",
        "output": result.get("message") or "rpicam-hello: no cameras",
    }, 500


def camera_config_load(cfg=None, camera_id: int = 0):
    return svc.camera_config_load(cfg or _cfg(), camera_id)


def camera_config_save(incoming, cfg=None):
    cfg = cfg or _cfg()
    restart = bool(incoming.get("restart"))
    return svc.camera_config_save(cfg, incoming, restart=restart)


def camera_detect(refresh=False):
    return svc.camera_detect(refresh=refresh)


def camera_registry():
    return svc.load_registry()


def camera_ports_save(ports):
    return svc.camera_ports_save(ports)


def camera_restart():
    cfg = _cfg()
    if cfg is None:
        return {"success": False, "message": "Config not loaded"}, 500
    return svc.camera_restart(cfg)
