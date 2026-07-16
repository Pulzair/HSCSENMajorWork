// Keeps the lobby page in sync with the server while players come and go.
const socket = io();

socket.on("connect", () => {
    socket.emit("join_lobby", { game_id: window.BATTLEY_GAME_ID });
});

// A player joined, left or was removed: re-render by reloading.
socket.on("lobby_update", () => {
    window.location.reload();
});

// The host pressed Start: send everyone into the game.
socket.on("game_started", (data) => {
    window.location.href = data.url;
});
