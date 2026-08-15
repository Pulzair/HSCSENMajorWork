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

const timerBox = document.getElementById("turnTimer");

if (timerBox) {
    const valueEl = document.getElementById("turnTimerValue");
    const ordersForm = document.getElementById("ordersForm");
    const resolveUrl = timerBox.dataset.resolveUrl;
    let remaining = parseInt(timerBox.dataset.seconds, 10);
    let fired = false;

    const paint = () => {
        const safe = Math.max(0, remaining);
        const mins = Math.floor(safe / 60);
        const secs = safe % 60;
        valueEl.textContent = `${mins}:${String(secs).padStart(2, "0")}`;
        timerBox.classList.toggle("turn-timer--urgent", safe <= 10);
    };

    const expire = () => {
        if (fired) return;
        fired = true;
        valueEl.textContent = "0:00";

        if (ordersForm) {
            ordersForm.requestSubmit();
            return;
        }

        fetch(resolveUrl, {
            method: "POST",
            headers: { "X-Requested-With": "XMLHttpRequest" },
        }).catch(() => {});
    };

    paint();
    if (remaining <= 0) expire();

    const ticker = setInterval(() => {
        remaining -= 1;
        paint();
        if (remaining <= 0) {
            clearInterval(ticker);
            expire();
        }
    }, 1000);
}

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
