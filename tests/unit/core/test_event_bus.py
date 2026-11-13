from asta.core.event_bus import EventBus


def test_publish_reaches_subscribers_and_history():
    bus = EventBus()
    seen = []
    bus.subscribe("cycle.completed", lambda event: seen.append(event.name))

    event = bus.publish("cycle.completed", scanners_run=3)

    assert event.name == "cycle.completed"
    assert event.payload["scanners_run"] == 3
    assert seen == ["cycle.completed"]
    assert bus.history[0] is event


def test_wildcard_subscriber_sees_everything():
    bus = EventBus()
    names = []
    bus.subscribe("*", lambda event: names.append(event.name))
    bus.publish("signal.detected", symbol="BTCUSDT")
    bus.publish("cycle.completed", scanners_run=1)
    assert names == ["signal.detected", "cycle.completed"]


def test_failing_handler_does_not_break_others():
    bus = EventBus()
    calls = []

    def boom(event):
        raise RuntimeError("subscriber bug")

    bus.subscribe("scan.failed", boom)
    bus.subscribe("scan.failed", lambda event: calls.append(event.payload["error"]))

    bus.publish("scan.failed", error="HTTP 503")
    assert calls == ["HTTP 503"]


def test_unsubscribe_and_subscriber_count():
    bus = EventBus()
    handler = lambda event: None  # noqa: E731
    bus.subscribe("x", handler)
    assert bus.subscribers("x") == 1
    bus.unsubscribe("x", handler)
    assert bus.subscribers("x") == 0
