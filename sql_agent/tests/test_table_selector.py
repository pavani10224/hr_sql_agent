from agents.table_selector import TableSelector
from models.schema_models import ColumnInfo, DatabaseSchema, TableInfo


def test_schema_hints_keep_join_table_for_worklife_payzone_question() -> None:
    schema = DatabaseSchema(
        tables={
            "employee_data": TableInfo(
                name="employee_data",
                columns=[
                    ColumnInfo(name="empid", data_type="INTEGER"),
                    ColumnInfo(name="payzone", data_type="TEXT"),
                ],
            ),
            "employee_engagement_survey_data": TableInfo(
                name="employee_engagement_survey_data",
                columns=[
                    ColumnInfo(name="employee_id", data_type="INTEGER"),
                    ColumnInfo(name="work_life_balance_score", data_type="INTEGER"),
                ],
            ),
        }
    )

    selected = TableSelector._add_schema_hint_tables(
        "in payzone of zone c show worklife balance score",
        schema,
        ["employee_data"],
    )

    assert selected == ["employee_data", "employee_engagement_survey_data"]


def test_schema_hints_keep_employee_table_for_named_employee_question() -> None:
    schema = DatabaseSchema(
        tables={
            "employee_data": TableInfo(
                name="employee_data",
                columns=[
                    ColumnInfo(name="empid", data_type="INTEGER"),
                    ColumnInfo(name="firstname", data_type="TEXT"),
                    ColumnInfo(name="lastname", data_type="TEXT"),
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

    selected = TableSelector._add_schema_hint_tables(
        "Show trainer for employee named Sarah Malone.",
        schema,
        ["training_and_development_data"],
    )

    assert selected == ["training_and_development_data", "employee_data"]
