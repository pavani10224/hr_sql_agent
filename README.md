# 🤖 HR SQL Agent

An AI-powered HR SQL Agent that allows users to ask natural language questions about HR datasets. The system automatically discovers database schemas, generates SQL queries using an LLM (Ollama), executes them on a SQLite database, and presents the results in an interactive chat interface.

---

## 🚀 Features

- 💬 Ask questions in plain English
- 🧠 AI-generated SQL using Ollama
- 📊 Dynamic CSV to SQLite conversion
- 🔍 Automatic schema discovery
- 🔗 Automatic relationship detection between tables
- ✏️ Editable SQL before execution
- ▶️ Execute modified SQL instantly
- 📋 Results displayed in a readable table
- 📈 Business-friendly summary generated from query results
- 🤖 LangGraph-based multi-agent workflow
- 🌐 FastAPI backend
- 🎨 HTML, CSS & JavaScript frontend

---

## 🏗️ Architecture

```
                User Question
                      │
                      ▼
              Relevance Checker
                      │
                      ▼
               Table Selection
                      │
                      ▼
               SQL Generator
                      │
                      ▼
               SQL Validator
                      │
                      ▼
              SQLite Execution
                      │
                      ▼
          Business Summary Generator
                      │
                      ▼
                  Chat UI
```

---

## 🛠️ Tech Stack

### Backend

- Python
- FastAPI
- LangGraph
- SQLAlchemy
- SQLite
- Pandas
- Ollama

### Frontend

- HTML
- CSS
- JavaScript

### AI Model

- Ollama
- Llama 3 (or your configured Ollama model)

---

## 📁 Project Structure

```
sql_agent/
│
├── agents/
│   ├── relevance_checker.py
│   ├── table_selector.py
│   ├── sql_generator.py
│   ├── sql_validator.py
│   ├── response_generator.py
│
├── database/
│   └── db_manager.py
│
├── frontend/
│   ├── css/
│   ├── js/
│   └── index.html
│
├── graph/
│   └── workflow.py
│
├── routers/
│
├── schemas/
│
├── services/
│
├── tests/
│
├── main.py
│
└── requirements.txt
```

---

## ⚙️ Installation

### Clone the repository

```bash
git clone https://github.com/pavani10224/hr_sql_agent.git

cd hr_sql_agent
```

### Create Virtual Environment

```bash
python -m venv .venv
```

Activate

Windows

```bash
.venv\Scripts\activate
```

Mac/Linux

```bash
source .venv/bin/activate
```

---

### Install dependencies

```bash
pip install -r requirements.txt
```

---

### Start Ollama

Make sure Ollama is installed.

Example

```bash
ollama run llama3
```

---

### Run FastAPI

```bash
uvicorn main:app --reload
```

Backend

```
http://127.0.0.1:8000
```

Swagger

```
http://127.0.0.1:8000/docs
```

---

## 💡 How It Works

1. Upload HR CSV datasets.
2. CSV files are converted into a SQLite database.
3. Database schema and relationships are automatically discovered.
4. User asks a question in natural language.
5. AI determines relevant tables.
6. AI generates SQL.
7. SQL is validated.
8. Query executes on SQLite.
9. Results are shown in a table.
10. AI generates a business-friendly summary.

---

## Example

### User Question

```
How many employees are there?
```

Generated SQL

```sql
SELECT COUNT(*) FROM employee_data;
```

Query Result

| COUNT(*) |
|----------:|
| 3000 |

Business Summary

```
There are 3,000 employees.
```

---

## Editable SQL

The generated SQL can be edited before execution.

Example

Original

```sql
SELECT COUNT(*) FROM employee_data;
```

Modified

```sql
SELECT *
FROM employee_data
LIMIT 10;
```

Click **Run SQL** to execute the modified query instantly.

---

## AI Workflow

The system contains multiple AI agents:

- Relevance Checker
- Table Selector
- SQL Generator
- SQL Validator
- Response Generator

Each agent performs a dedicated task, improving modularity and maintainability.

---

## Future Improvements

- Conversation memory
- Follow-up question understanding
- SQL syntax highlighting
- Query history
- Export results to CSV/Excel
- Authentication
- Dashboard analytics
- Multi-database support (PostgreSQL, MySQL)

---

## Author

**Pavani N**

GitHub

https://github.com/pavani10224

---

## License

This project was developed for educational purposes as an AI-powered HR SQL Agent.
