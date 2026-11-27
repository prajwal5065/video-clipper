"""Two uploads never open two Google sign-in windows at once."""


def test_google_sign_in_never_runs_twice_at_once(monkeypatch):
    """Two queued uploads must not open two Google sign-in windows at the same time."""
    import threading
    import time

    from clipper import youtube as yt

    state = {"now": 0, "max": 0}

    def fake_credentials(account):
        state["now"] += 1
        state["max"] = max(state["max"], state["now"])
        time.sleep(0.15)
        state["now"] -= 1
        return object()

    monkeypatch.setattr(yt, "_credentials", fake_credentials)
    monkeypatch.setattr("googleapiclient.discovery.build", lambda *a, **k: object())
    threads = [threading.Thread(target=yt._service, args=(a,)) for a in ("main", "second")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert state["max"] == 1
