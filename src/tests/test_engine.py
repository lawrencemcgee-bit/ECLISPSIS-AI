from src.engine.local_engine import LocalEngine

def test_local_engine_process():
    engine = LocalEngine()
    result = engine.process("hello")
    assert result.content.startswith("LocalEngine received")


