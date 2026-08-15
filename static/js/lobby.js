const socket = io();

socket.on("connect", () => {
    socket.emit("join_lobby", { game_id: window.BATTLEY_GAME_ID });
});

socket.on("lobby_update", () => {
    window.location.reload();
});

socket.on("game_started", (data) => {
    window.location.href = data.url;
});
