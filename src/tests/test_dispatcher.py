from src.core.dispatcher import EventDispatcher
from src.core.events import Event

def test_event_dispatcher():
    dispatcher = EventDispatcher()
    received = []

    dispatcher.register("test", lambda e: received.append(e.payload))
    dispatcher.dispatch(Event(type="test", payload="ok"))

    assert received == ["ok"]
