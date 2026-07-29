def test_local_engine_placeholder():
    from src.engine.local_engine import LocalEngine
    engine = LocalEngine()
    result = engine.process("hello")
    assert "placeholder" in result

