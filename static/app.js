const tg = window.Telegram.WebApp;

tg.ready();
tg.expand();

let medicines = {};
let currentBox = 1;


// -----------------------------
// Telegram user
// -----------------------------

if (tg.initDataUnsafe && tg.initDataUnsafe.user) {

    const user = tg.initDataUnsafe.user;

    document.getElementById("welcome").innerText =
        "Hello, " + (user.first_name || "User") + " 👋";
}


// -----------------------------
// Load medicine information
// -----------------------------

async function loadMedicines() {

    try {

        const response = await fetch("/api/status");

        medicines = await response.json();

        displayBoxes();

    } catch (error) {

        console.error(error);

        showMessage("Unable to load medicine information.");

    }
}


// -----------------------------
// Display four boxes
// -----------------------------

function displayBoxes() {

    const container =
        document.getElementById("boxesContainer");

    container.innerHTML = "";

    for (let box = 1; box <= 4; box++) {

        const data = medicines["box" + box];

        const active =
            data.active && data.medicine !== "";

        let timesHTML = "";

        if (data.times && data.times.length > 0) {

            data.times.forEach(time => {

                timesHTML +=
                    `<span class="time-item">⏰ ${time}</span>`;

            });

        } else {

            timesHTML =
                `<span class="time-item">No reminders</span>`;

        }


        const boxHTML = `

            <div class="medicine-box">

                <div class="box-top">

                    <span class="box-number">
                        Medicine Box ${box}
                    </span>

                    <span class="${active ? "active" : "inactive"}">
                        ${active ? "ACTIVE" : "EMPTY"}
                    </span>

                </div>

                <div class="box-name">
                    ${data.medicine || "No medicine added"}
                </div>

                <div class="times">
                    ${timesHTML}
                </div>

                <button
                    class="edit-btn"
                    onclick="openBox(${box})">

                    ${active ? "✏️ Edit Medicine" : "➕ Add Medicine"}

                </button>

            </div>
        `;

        container.innerHTML += boxHTML;
    }
}


// -----------------------------
// Open a medicine box
// -----------------------------

function openBox(box) {

    currentBox = box;

    const data = medicines["box" + box];

    document.getElementById("homePage")
        .classList.add("hidden");

    document.getElementById("editPage")
        .classList.remove("hidden");

    document.getElementById("editTitle").innerText =
        "Medicine Box " + box;

    document.getElementById("medicineName").value =
        data.medicine || "";

    const timesContainer =
        document.getElementById("timesContainer");

    timesContainer.innerHTML = "";

    const times = data.times || [];

    times.forEach(time => {

        createTimeRow(time);

    });

}


// -----------------------------
// Add reminder time
// -----------------------------

function addTime() {

    const rows =
        document.querySelectorAll(".time-row");

    if (rows.length >= 4) {

        showMessage("Maximum 4 reminder times.");

        return;
    }

    createTimeRow("");

}


// -----------------------------
// Create time input
// -----------------------------

function createTimeRow(time) {

    const container =
        document.getElementById("timesContainer");

    const row =
        document.createElement("div");

    row.className = "time-row";

    row.innerHTML = `

        <input
            type="time"
            value="${time}"
        >

        <button
            class="delete-time"
            onclick="deleteTime(this)">

            🗑

        </button>

    `;

    container.appendChild(row);
}


// -----------------------------
// Delete reminder
// -----------------------------

function deleteTime(button) {

    button.parentElement.remove();

}


// -----------------------------
// Save medicine
// -----------------------------

async function saveMedicine() {

    const medicine =
        document.getElementById("medicineName").value.trim();


    if (!medicine) {

        showMessage("Please enter medicine name.");

        return;
    }


    const timeInputs =
        document.querySelectorAll(
            "#timesContainer input[type='time']"
        );


    const times = [];

    timeInputs.forEach(input => {

        if (input.value) {

            times.push(input.value);

        }

    });


    try {

        const response =
            await fetch("/api/set-medicine", {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    box: currentBox,

                    medicine: medicine,

                    times: times

                })

            });


        const result =
            await response.json();


        if (result.success) {

            showMessage("Medicine saved successfully! ✓");

            if (
                tg.HapticFeedback &&
                tg.HapticFeedback.notificationOccurred
            ) {

                tg.HapticFeedback
                    .notificationOccurred("success");

            }

            await loadMedicines();

            showHome();

        } else {

            showMessage("Could not save medicine.");

        }


    } catch (error) {

        console.error(error);

        showMessage("Connection error.");

    }

}


// -----------------------------
// Return home
// -----------------------------

function showHome() {

    document.getElementById("editPage")
        .classList.add("hidden");

    document.getElementById("homePage")
        .classList.remove("hidden");

}


// -----------------------------
// Small message
// -----------------------------

function showMessage(message) {

    const element =
        document.getElementById("message");

    element.innerText = message;

    element.style.display = "block";

    setTimeout(() => {

        element.style.display = "none";

    }, 2500);

}


// -----------------------------
// Start application
// -----------------------------

loadMedicines();