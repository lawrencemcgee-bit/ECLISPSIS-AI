from src.core.results import AssistantResult, AgentResult, TaskResult

def test_result_placeholders():
    a = AssistantResult(content="hello")
    b = AgentResult(agent="test", output="ok")
    t = TaskResult(task_id="1", status="pending")

    assert a.content == "hello"
    assert b.agent == "test"
    assert t.status == "pending"

