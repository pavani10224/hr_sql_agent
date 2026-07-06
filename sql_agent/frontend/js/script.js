console.log("Script Loaded!");

const sendBtn = document.getElementById("send-btn");
const userInput = document.getElementById("user-input");
const chatContainer = document.getElementById("chat-container");
const loading = document.getElementById("loading");

const API_URL = "http://127.0.0.1:8000";

// -----------------------------
// Add Chat Message
// -----------------------------
function addMessage(message, sender) {

    const div = document.createElement("div");
    div.className = `message ${sender}-message`;
    div.textContent = message;

    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}


// -----------------------------
// Send Question to AI
// -----------------------------
async function sendQuestion() {

    const question = userInput.value.trim();

    if (!question) return;

    addMessage(question, "user");

    userInput.value = "";

    loading.style.display = "flex";

    try {

        const response = await fetch(`${API_URL}/ask`, {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                question: question
            })

        });

        const data = await response.json();

        loading.style.display = "none";

        if (!response.ok) {

            addMessage(data.detail || "Something went wrong.", "bot");
            return;

        }

        displayResponse(data);

    }

    catch (err) {

        loading.style.display = "none";

        console.error(err);

        addMessage("Unable to connect to FastAPI.", "bot");

    }

}


// -----------------------------
// Create Result Table
// -----------------------------
function createTable(rows) {

    if (!rows || rows.length === 0) {

        return "<p>No rows returned.</p>";

    }

    let html = "<table>";

    html += "<thead><tr>";

    Object.keys(rows[0]).forEach(col => {

        html += `<th>${col}</th>`;

    });

    html += "</tr></thead>";

    html += "<tbody>";

    rows.forEach(row => {

        html += "<tr>";

        Object.values(row).forEach(value => {

            html += `<td>${value}</td>`;

        });

        html += "</tr>";

    });

    html += "</tbody></table>";

    return html;

}


// -----------------------------
// Display AI Response
// -----------------------------
function displayResponse(data) {

    const botDiv = document.createElement("div");

    botDiv.className = "message bot-message";

    botDiv.innerHTML = `

        <h4>🧠 Generated SQL</h4>

        <textarea class="sql-box">${data.generated_sql || ""}</textarea>

        <button class="run-btn">▶ Run SQL</button>

        <h4>📋 Query Result</h4>

        <div class="result-table">

            ${createTable(data.query_result)}

        </div>

        <div class="summary-card">

            <h4>💡 Business Summary</h4>

            <p>${data.answer}</p>

        </div>

    `;

    chatContainer.appendChild(botDiv);

    chatContainer.scrollTop = chatContainer.scrollHeight;


    //-----------------------------------------
    // Run Edited SQL
    //-----------------------------------------

    const runBtn = botDiv.querySelector(".run-btn");

    const sqlEditor = botDiv.querySelector(".sql-box");

    const resultDiv = botDiv.querySelector(".result-table");

    runBtn.addEventListener("click", async () => {

        loading.style.display = "flex";

        try {

            const response = await fetch(`${API_URL}/execute_sql`, {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    sql: sqlEditor.value

                })

            });

            const result = await response.json();

            loading.style.display = "none";

            if (!response.ok) {

                alert(result.detail);

                return;

            }

            resultDiv.innerHTML = createTable(result.query_result);

        }

        catch (err) {

            loading.style.display = "none";

            console.error(err);

            alert("Unable to execute SQL.");

        }

    });

}


// -----------------------------
// Events
// -----------------------------
sendBtn.addEventListener("click", sendQuestion);

userInput.addEventListener("keypress", function (e) {

    if (e.key === "Enter") {

        sendQuestion();

    }

});