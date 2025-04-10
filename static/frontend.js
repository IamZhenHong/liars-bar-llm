let socket = null;
let playerName = "";

document.getElementById("start-game-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const numHumans = parseInt(document.getElementById("num-humans").value);
  const nameInputs = document.querySelectorAll(".human-name");
  const humanNames = Array.from(nameInputs).map(input => input.value.trim()).filter(name => name);

  if (humanNames.length !== numHumans) {
    alert("Please fill in all human player names.");
    return;
  }

  playerName = humanNames[0]; // Assume first human is you

  try {
    // Connect WebSocket and wait for it to open
    socket = new WebSocket(`ws://${window.location.host}/ws/${playerName}`);

    socket.onmessage = handleSocketMessage;

    await new Promise((resolve, reject) => {
      socket.onopen = () => {
        console.log("[WS] Connected to server as", playerName);
        resolve();
      };
      socket.onerror = (err) => {
        console.error("[WS] Error connecting:", err);
        alert("WebSocket connection failed.");
        reject(err);
      };
      socket.onclose = () => {
        console.warn("[WS] Connection closed");
      };
    });

    // Start game only after WS is ready
    const response = await fetch("/start_game", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ human_names: humanNames })
    });

    if (response.ok) {
      document.getElementById("setup-form").style.display = "none";
      document.getElementById("game-interface").style.display = "block";
      document.getElementById("status").textContent = `Connected as ${playerName}`;
    } else {
      alert("Failed to start game.");
    }

  } catch (err) {
    console.error("Failed to launch game:", err);
  }
});

document.getElementById("num-humans").addEventListener("change", () => {
  const num = parseInt(document.getElementById("num-humans").value, 10);
  const container = document.getElementById("human-names");
  container.innerHTML = "";

  for (let i = 0; i < num; i++) {
    const wrapper = document.createElement("div");

    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = `Human player ${i + 1} name`;
    input.name = `human${i}`;
    input.className = "human-name";
    input.required = true;

    wrapper.appendChild(input);
    container.appendChild(wrapper);
  }
});

function handleSocketMessage(event) {
    const data = JSON.parse(event.data);
    console.log("[WS] Received message:", data);  // 👈 Add this to debug
  
    if (data.type === "your_turn") {
      document.getElementById("play-form").style.display = "block";
      document.getElementById("hand-display").textContent = `Your hand: ${data.hand.join(", ")}`;
    }
  
    if (data.type === "challenge_request") {
      console.log("[CHALLENGE] Data received:", data);  // 👈 Log full structure
  
      // SAFELY access fields
      const info = data.challenging_player_performance || "无挑战描述";
      const hint = data.extra_hint || "";
  
      document.getElementById("challenge-form").style.display = "block";
      document.getElementById("challenge-info").textContent = info + " " + hint;
    }
  }
  

function submitPlay() {
  const cards = document.getElementById("played-cards").value.trim().split(" ");
  const reason = document.getElementById("reason").value.trim();
  const behavior = document.getElementById("behavior").value.trim();

  socket.send(JSON.stringify({
    played_cards: cards,
    play_reason: reason,
    behavior: behavior
  }));

  document.getElementById("play-form").style.display = "none";
  document.getElementById("played-cards").value = "";
  document.getElementById("reason").value = "";
  document.getElementById("behavior").value = "";
}

function submitChallenge(wasChallenged) {
  const reason = wasChallenged
    ? document.getElementById("challenge-reason").value.trim()
    : "不质疑";

  socket.send(JSON.stringify({
    was_challenged: wasChallenged,
    challenge_reason: reason
  }));

  document.getElementById("challenge-form").style.display = "none";
  document.getElementById("challenge-reason").value = "";
}
