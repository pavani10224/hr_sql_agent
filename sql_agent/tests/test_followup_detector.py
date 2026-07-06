from agents.followup_detector import FollowupDetector
from models.schema_models import ColumnInfo, DatabaseSchema, TableInfo


def _employee_schema() -> DatabaseSchema:
    return DatabaseSchema(
        tables={
            "employee_data": TableInfo(
                name="employee_data",
                columns=[
                    ColumnInfo(name="empid", data_type="INTEGER"),
                    ColumnInfo(name="firstname", data_type="TEXT"),
                    ColumnInfo(name="lastname", data_type="TEXT"),
                    ColumnInfo(name="salary", data_type="INTEGER"),
                    ColumnInfo(name="zone", data_type="TEXT"),
                ],
            ),
            "training_and_development_data": TableInfo(
                name="training_and_development_data",
                columns=[
                    ColumnInfo(name="employee_id", data_type="INTEGER"),
                    ColumnInfo(name="trainer", data_type="TEXT"),
                ],
            ),
        }
    )


def test_employee_shortcut_rewrites_to_full_employee_lookup() -> None:
    question = FollowupDetector.resolve("emp 1011", _employee_schema(), [])

    assert question == "Show all information from employee_data for employee with empid 1011."


def test_followup_uses_llm_to_rewrite_question(monkeypatch) -> None:
    def fake_complete_json(system_prompt: str, user_prompt: str) -> dict:
        assert "Show employee 1011" in user_prompt
        assert "What is his salary?" in user_prompt
        return {
            "is_follow_up": True,
            "standalone_question": "What is the salary for employee 1011?",
            "reason": "his refers to employee 1011",
        }

    monkeypatch.setattr("agents.followup_detector.llm_service.complete_json", fake_complete_json)

    question = FollowupDetector.resolve(
        "What is his salary?",
        _employee_schema(),
        [
            {
                "user": "Show employee 1011",
                "effective_question": "Show all information from employee_data for employee with empid 1011.",
                "generated_sql": "SELECT * FROM employee_data WHERE empid = 1011;",
            }
        ],
    )

    assert question == "What is the salary for employee 1011?"


def test_employee_name_field_shortcut_rewrites_to_employee_lookup() -> None:
    question = FollowupDetector.resolve("Sarah Malone trainer", _employee_schema(), [])

    assert question == "Show trainer for employee named Sarah Malone."

def test_vague_training_program_cost_rewrites_to_grouped_question() -> None:
    question = FollowupDetector.resolve(
        "what is the total cost of this training program?",
        _employee_schema(),
        [],
    )

    assert question == "Show the total training cost grouped by training program."
