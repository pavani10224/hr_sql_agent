from agents.response_generator import ResponseGenerator


def test_plain_text_removes_code_fences_and_braces() -> None:
    answer = ResponseGenerator._plain_text('```json\n{"answer": "Total cost is 100"}\n```')

    assert answer == "Total cost is 100"


def test_generate_rejects_pandas_code_summary(monkeypatch) -> None:
    def fake_complete_json(system_prompt: str, user_prompt: str) -> dict:
        return {
            "answer": (
                "This is a list of dictionaries. Here's sample code: "
                "import pandas as pd; df = pd.DataFrame(data); print(df.head())"
            )
        }

    monkeypatch.setattr("agents.response_generator.llm_service.complete_json", fake_complete_json)

    answer = ResponseGenerator.generate(
        "show training data",
        [{"employee_id": 1011, "training_program_name": "Communication Skills"}],
    )

    assert "pandas" not in answer.lower()
    assert "dataframe" not in answer.lower()
    assert "employee id" in answer.lower()


def test_deterministic_summary_formats_grouped_totals() -> None:
    answer = ResponseGenerator._deterministic_summary(
        "Show the total training cost grouped by training program.",
        [
            {"training_program_name": "Communication Skills", "SUM(training_cost)": 365023.24},
            {"training_program_name": "Customer Service", "SUM(training_cost)": 320575.04},
        ],
    )

    assert "Communication Skills: 365,023.24" in answer
    assert "Customer Service: 320,575.04" in answer
