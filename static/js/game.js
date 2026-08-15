const tabs = document.querySelectorAll(".layer-tab");
const layers = document.querySelectorAll(".map-layer");

tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
        const wanted = tab.dataset.layer;

        tabs.forEach((other) => {
            const active = other === tab;
            other.classList.toggle("is-active", active);
            other.setAttribute("aria-selected", active ? "true" : "false");
        });

        layers.forEach((layer) => {
            layer.classList.toggle("is-hidden", layer.dataset.layer !== wanted);
        });
    });
});

if (typeof io !== "undefined" && window.BATTLEY_GAME_ID) {
    const socket = io();

    socket.on("connect", () => {
        socket.emit("join_lobby", { game_id: window.BATTLEY_GAME_ID });
    });

    socket.on("orders_update", () => {
        window.location.reload();
    });

    socket.on("turn_resolved", () => {
        window.location.reload();
    });
}
