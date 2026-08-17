const MAX_VIEW = 25;
const MAX_PIXELS = 780;
const INK = "#111111";
const PAPER = "#ffffff";
const ACCENT = "#111111";

const TERRAIN = { plains: 0.93, mountain: 0.74, water: 0.55, destroyed: 0.34 };

let CELL = 30;

function grey(level) {
	const value = Math.max(0, Math.min(255, Math.round(level * 255)));
	return `rgb(${value},${value},${value})`;
}

function hashAt(x, y, salt) {
	const value = Math.sin(x * 127.1 + y * 311.7 + salt * 74.7) * 43758.5453;
	return value - Math.floor(value);
}

function drawTerrain(ctx, px, py, size, terrain, layer, dim) {
	const base = TERRAIN[terrain] === undefined ? TERRAIN.plains : TERRAIN[terrain];
	const shift = layer === 1 ? -0.10 : (layer === 2 ? 0.05 : 0);
	const level = Math.max(0.12, Math.min(0.98, base + shift + (dim ? 0.06 : 0)));
	ctx.fillStyle = grey(level);
	ctx.fillRect(px, py, size, size);

	const unit = size / 8;
	ctx.fillStyle = grey(Math.max(0.06, level - 0.16));

	if (terrain === "plains") {
		for (let bx = 0; bx < 4; bx++) {
			for (let by = 0; by < 4; by++) {
				if (hashAt(px + bx, py + by, layer + 1) > 0.78) ctx.fillRect(px + bx * size / 4 + unit * 0.5, py + by * size / 4 + unit * 0.5, unit * 0.5, unit * 0.5);
			}
		}
	} else if (terrain === "mountain") {
		ctx.beginPath();
		ctx.moveTo(px + unit, py + size - unit);
		ctx.lineTo(px + size / 2, py + unit * 1.5);
		ctx.lineTo(px + size - unit, py + size - unit);
		ctx.closePath();
		ctx.fill();
	} else if (terrain === "water") {
		for (let row = 1; row < 4; row++) {
			const offset = (row % 2) * unit;
			ctx.fillRect(px + unit * 0.5 + offset, py + row * size / 4, size - unit - offset, Math.max(1, unit * 0.35));
		}
	} else if (terrain === "destroyed") {
		for (let index = 0; index < 4; index++) {
			ctx.fillRect(px + unit * (0.6 + index * 1.9), py + unit * (1 + (index % 2) * 3), unit * 1.2, unit * 1.2);
		}
	}

	if (layer === 1) {
		ctx.strokeStyle = grey(Math.max(0.05, level - 0.30));
		ctx.lineWidth = 1;
		ctx.strokeRect(px + 0.5, py + 0.5, size - 1, size - 1);
	}
	if (dim) {
		ctx.fillStyle = "rgba(255,255,255,0.45)";
		ctx.fillRect(px, py, size, size);
	}
}

function drawCity(ctx, px, py, size, colour) {
	const unit = size / 8;
	ctx.fillStyle = INK;
	ctx.fillRect(px + unit * 2, py + unit * 3, unit * 4, unit * 4);
	ctx.fillStyle = colour || PAPER;
	ctx.fillRect(px + unit * 3, py + unit * 2, unit * 2, unit * 2);
	ctx.fillStyle = PAPER;
	ctx.fillRect(px + unit * 3, py + unit * 5, unit, unit * 2);
}

const IMPROVEMENTS = {
	farm(ctx, u, x, y) {
		for (let row = 0; row < 3; row++) ctx.fillRect(x, y + row * u * 0.7, u * 2.6, u * 0.35);
	},
	mine(ctx, u, x, y) {
		ctx.fillRect(x, y + u * 1.4, u * 2.6, u * 0.5);
		ctx.fillRect(x + u * 0.4, y + u * 0.2, u * 0.4, u * 1.4);
		ctx.fillRect(x + u * 1.5, y + u * 0.2, u * 0.4, u * 1.4);
		ctx.fillRect(x + u * 0.4, y, u * 1.5, u * 0.4);
	},
	quarry(ctx, u, x, y) {
		ctx.fillRect(x, y + u * 1.3, u * 2.6, u * 0.6);
		ctx.fillRect(x + u * 0.3, y + u * 0.6, u * 0.9, u * 0.7);
		ctx.fillRect(x + u * 1.4, y + u * 0.2, u * 0.9, u * 1.1);
	},
	barracks(ctx, u, x, y) {
		ctx.fillRect(x, y + u * 0.7, u * 2.6, u * 1.3);
		ctx.beginPath();
		ctx.moveTo(x, y + u * 0.7);
		ctx.lineTo(x + u * 1.3, y);
		ctx.lineTo(x + u * 2.6, y + u * 0.7);
		ctx.closePath();
		ctx.fill();
	}
};

function drawImprovement(ctx, px, py, size, key) {
	const u = size / 8;
	ctx.fillStyle = INK;
	const paint = IMPROVEMENTS[key];
	if (paint) paint(ctx, u, px + u * 0.5, py + size - u * 2.6);
	else ctx.fillRect(px + u * 0.5, py + size - u * 2.0, u * 2.4, u * 1.2);
}

function drawResource(ctx, px, py, size, kind) {
	const u = size / 8;
	const x = px + size - u * 2.4;
	const y = py + u * 0.5;
	ctx.fillStyle = INK;
	if (kind === "horses") {
		ctx.fillRect(x, y + u * 0.9, u * 1.9, u * 0.7);
		ctx.fillRect(x + u * 1.3, y, u * 0.6, u * 1.1);
		ctx.fillRect(x, y + u * 1.5, u * 0.4, u * 0.5);
		ctx.fillRect(x + u * 1.3, y + u * 1.5, u * 0.4, u * 0.5);
	} else {
		ctx.beginPath();
		ctx.moveTo(x + u, y);
		ctx.lineTo(x + u * 2, y + u);
		ctx.lineTo(x + u, y + u * 2);
		ctx.lineTo(x, y + u);
		ctx.closePath();
		ctx.fill();
	}
	ctx.strokeStyle = PAPER;
	ctx.lineWidth = 0.8;
	ctx.strokeRect(x - 0.6, y - 0.6, u * 2.1, u * 2.2);
}

function drawCrossing(ctx, px, py, size, flag) {
	const u = size / 8;
	ctx.save();
	ctx.strokeStyle = INK;
	ctx.lineWidth = Math.max(1.4, u * 0.4);
	ctx.beginPath();
	ctx.arc(px + size / 2, py + size / 2, size * 0.32, 0, Math.PI * 2);
	ctx.stroke();
	ctx.beginPath();
	ctx.moveTo(px + size / 2, py + size * 0.16);
	ctx.lineTo(px + size / 2, py + size * 0.84);
	ctx.stroke();
	if (flag) {
		ctx.setLineDash([3, 2]);
		ctx.lineWidth = 2;
		ctx.strokeRect(px + 1.5, py + 1.5, size - 3, size - 3);
		ctx.setLineDash([]);
	}
	ctx.restore();
}

const SPRITES = {
	warrior(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 1.1, base - u * 2.6, u * 2.2, u * 2.6);
		ctx.fillRect(cx - u * 0.8, base - u * 3.7, u * 1.6, u * 1.1);
		ctx.fillRect(cx + u * 1.3, base - u * 3.4, u * 0.5, u * 2.6);
		ctx.fillRect(cx - u * 2.4, base - u * 2.6, u * 1.1, u * 1.8);
	},
	archer(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 1.0, base - u * 2.5, u * 2.0, u * 2.5);
		ctx.fillRect(cx - u * 0.8, base - u * 3.6, u * 1.6, u * 1.1);
		ctx.fillRect(cx + u * 1.4, base - u * 3.8, u * 0.45, u * 3.4);
		ctx.fillRect(cx + u * 0.6, base - u * 3.9, u * 0.9, u * 0.4);
		ctx.fillRect(cx + u * 0.6, base - u * 0.8, u * 0.9, u * 0.4);
	},
	horseman(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 2.2, base - u * 2.0, u * 4.0, u * 1.4);
		ctx.fillRect(cx - u * 2.0, base - u * 0.7, u * 0.7, u * 0.7);
		ctx.fillRect(cx + u * 1.0, base - u * 0.7, u * 0.7, u * 0.7);
		ctx.fillRect(cx + u * 1.4, base - u * 3.2, u * 0.8, u * 1.4);
		ctx.fillRect(cx - u * 0.4, base - u * 3.6, u * 1.0, u * 1.7);
	},
	catapult(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 2.2, base - u * 1.6, u * 4.4, u * 1.0);
		ctx.fillRect(cx - u * 1.9, base - u * 0.7, u * 1.0, u * 0.9);
		ctx.fillRect(cx + u * 0.9, base - u * 0.7, u * 1.0, u * 0.9);
		ctx.fillRect(cx - u * 0.3, base - u * 3.9, u * 0.7, u * 2.4);
		ctx.fillRect(cx - u * 1.6, base - u * 4.2, u * 1.6, u * 0.8);
	},
	trireme(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 2.6, base - u * 1.3, u * 5.2, u * 1.1);
		ctx.fillRect(cx - u * 0.3, base - u * 4.0, u * 0.6, u * 2.8);
		ctx.fillRect(cx - u * 1.9, base - u * 3.8, u * 1.9, u * 1.5);
		ctx.fillRect(cx - u * 2.2, base - u * 0.3, u * 0.8, u * 0.7);
		ctx.fillRect(cx + u * 1.4, base - u * 0.3, u * 0.8, u * 0.7);
	},
	submarine(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 2.6, base - u * 1.7, u * 5.2, u * 1.5);
		ctx.fillRect(cx - u * 0.7, base - u * 2.7, u * 1.4, u * 1.1);
		ctx.fillRect(cx + u * 0.1, base - u * 3.9, u * 0.4, u * 1.3);
		ctx.fillRect(cx + u * 0.1, base - u * 3.9, u * 1.0, u * 0.4);
	},
	skimmer(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 2.8, base - u * 2.5, u * 5.6, u * 0.5);
		ctx.fillRect(cx - u * 0.6, base - u * 3.1, u * 1.2, u * 1.2);
		ctx.fillRect(cx - u * 0.2, base - u * 1.9, u * 0.4, u * 1.0);
	},
	airship(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 2.9, base - u * 3.6, u * 5.8, u * 2.0);
		ctx.fillRect(cx - u * 3.4, base - u * 3.1, u * 0.6, u * 1.0);
		ctx.fillRect(cx + u * 2.8, base - u * 3.1, u * 0.6, u * 1.0);
		ctx.fillRect(cx - u * 1.4, base - u * 1.5, u * 2.8, u * 1.1);
	},
	dropship(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 2.4, base - u * 3.0, u * 4.8, u * 2.6);
		ctx.fillRect(cx - u * 3.2, base - u * 2.6, u * 0.8, u * 0.7);
		ctx.fillRect(cx + u * 2.4, base - u * 2.6, u * 0.8, u * 0.7);
		ctx.fillRect(cx - u * 1.6, base - u * 0.4, u * 0.9, u * 0.6);
		ctx.fillRect(cx + u * 0.7, base - u * 0.4, u * 0.9, u * 0.6);
	},
	stormcaller(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 1.6, base - u * 1.2, u * 3.2, u * 1.0);
		ctx.fillRect(cx - u * 0.8, base - u * 3.4, u * 1.6, u * 2.3);
		ctx.beginPath();
		ctx.moveTo(cx + u * 0.4, base - u * 4.6);
		ctx.lineTo(cx - u * 0.9, base - u * 3.5);
		ctx.lineTo(cx - u * 0.1, base - u * 3.5);
		ctx.lineTo(cx - u * 1.0, base - u * 2.4);
		ctx.lineTo(cx + u * 0.9, base - u * 3.8);
		ctx.lineTo(cx + u * 0.1, base - u * 3.8);
		ctx.closePath();
		ctx.fill();
	},
	tunneler(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 2.4, base - u * 2.4, u * 3.4, u * 2.2);
		ctx.beginPath();
		ctx.moveTo(cx + u * 1.0, base - u * 2.4);
		ctx.lineTo(cx + u * 3.0, base - u * 1.3);
		ctx.lineTo(cx + u * 1.0, base - u * 0.2);
		ctx.closePath();
		ctx.fill();
		ctx.fillRect(cx - u * 2.2, base - u * 0.2, u * 0.8, u * 0.6);
		ctx.fillRect(cx - u * 0.4, base - u * 0.2, u * 0.8, u * 0.6);
	},
	dire_bat(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 0.7, base - u * 2.6, u * 1.4, u * 1.8);
		ctx.beginPath();
		ctx.moveTo(cx - u * 0.7, base - u * 2.6);
		ctx.lineTo(cx - u * 3.4, base - u * 3.4);
		ctx.lineTo(cx - u * 2.6, base - u * 1.4);
		ctx.lineTo(cx - u * 0.7, base - u * 1.2);
		ctx.closePath();
		ctx.fill();
		ctx.beginPath();
		ctx.moveTo(cx + u * 0.7, base - u * 2.6);
		ctx.lineTo(cx + u * 3.4, base - u * 3.4);
		ctx.lineTo(cx + u * 2.6, base - u * 1.4);
		ctx.lineTo(cx + u * 0.7, base - u * 1.2);
		ctx.closePath();
		ctx.fill();
		ctx.fillRect(cx - u * 0.6, base - u * 3.3, u * 0.4, u * 0.8);
		ctx.fillRect(cx + u * 0.2, base - u * 3.3, u * 0.4, u * 0.8);
	},
	basilisk(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 2.6, base - u * 0.9, u * 3.2, u * 0.8);
		ctx.fillRect(cx - u * 0.6, base - u * 1.9, u * 1.6, u * 1.1);
		ctx.fillRect(cx + u * 0.6, base - u * 3.0, u * 1.4, u * 1.3);
		ctx.fillRect(cx + u * 1.9, base - u * 2.7, u * 0.8, u * 0.4);
		ctx.fillStyle = PAPER;
		ctx.fillRect(cx + u * 1.4, base - u * 2.6, u * 0.4, u * 0.4);
	},
	stone_golem(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 1.9, base - u * 3.0, u * 3.8, u * 2.2);
		ctx.fillRect(cx - u * 1.1, base - u * 4.1, u * 2.2, u * 1.2);
		ctx.fillRect(cx - u * 3.0, base - u * 2.8, u * 1.0, u * 2.0);
		ctx.fillRect(cx + u * 2.0, base - u * 2.8, u * 1.0, u * 2.0);
		ctx.fillRect(cx - u * 1.5, base - u * 0.8, u * 1.2, u * 0.9);
		ctx.fillRect(cx + u * 0.3, base - u * 0.8, u * 1.2, u * 0.9);
	},
	cave_wyrm(ctx, u, cx, base) {
		ctx.fillRect(cx - u * 3.2, base - u * 0.8, u * 2.2, u * 0.7);
		ctx.fillRect(cx - u * 1.6, base - u * 1.8, u * 2.0, u * 1.0);
		ctx.fillRect(cx - u * 0.2, base - u * 3.2, u * 2.2, u * 1.6);
		ctx.fillRect(cx + u * 1.9, base - u * 3.4, u * 1.3, u * 0.6);
		ctx.fillRect(cx + u * 1.9, base - u * 2.2, u * 1.3, u * 0.6);
		ctx.fillStyle = PAPER;
		ctx.fillRect(cx + u * 1.1, base - u * 2.9, u * 0.5, u * 0.5);
	}
};

function drawUnit(ctx, px, py, size, kind, colour, hurt) {
	const u = size / 8;
	const cx = px + size / 2;
	const base = py + size * 0.80;

	ctx.save();
	ctx.fillStyle = colour || INK;
	ctx.strokeStyle = INK;
	ctx.lineWidth = Math.max(0.8, size * 0.035);

	const paint = SPRITES[kind] || SPRITES.warrior;
	paint(ctx, u, cx, base);
	ctx.restore();

	ctx.fillStyle = PAPER;
	ctx.fillRect(px + u, py + size - u * 1.3, size - u * 2, u * 0.8);
	ctx.fillStyle = INK;
	ctx.fillRect(px + u, py + size - u * 1.3, (size - u * 2) * Math.max(0, Math.min(1, hurt)), u * 0.8);
	ctx.strokeStyle = INK;
	ctx.lineWidth = 0.7;
	ctx.strokeRect(px + u, py + size - u * 1.3, size - u * 2, u * 0.8);
}

const state = {
	layer: 0,
	camera: { x: 0, y: 0 },
	selected: null,
	orders: new Map(),
	builds: new Map(),
	nagged: false
};

const canvas = document.getElementById("viewport");
const ctx = canvas ? canvas.getContext("2d") : null;
const hint = document.getElementById("hint");

function tilesOnLayer() {
	return window.GAME.tiles.filter(tile => tile.layer === state.layer);
}

function tileAt(x, y) {
	return tilesOnLayer().find(tile => tile.x === x && tile.y === y) || null;
}

function tileByRef(ref) {
	return window.GAME.tiles.find(tile => tile.ref === ref) || null;
}

function columns() {
	return Math.min(window.GAME.width, MAX_VIEW);
}

function rows() {
	return Math.min(window.GAME.height, MAX_VIEW);
}

function fitViewport() {
	const span = Math.max(columns(), rows());
	CELL = Math.max(12, Math.min(48, Math.floor(MAX_PIXELS / span)));
	canvas.width = columns() * CELL;
	canvas.height = rows() * CELL;
	canvas.style.maxWidth = canvas.width + "px";
}

function clampCamera() {
	state.camera.x = Math.max(0, Math.min(state.camera.x, Math.max(0, window.GAME.width - columns())));
	state.camera.y = Math.max(0, Math.min(state.camera.y, Math.max(0, window.GAME.height - rows())));
}

function centreOnHome() {
	const mine = window.GAME.tiles.find(tile => tile.layer === state.layer && tile.mine) || window.GAME.tiles.find(tile => tile.mine);
	if (mine) {
		state.layer = mine.layer;
		state.camera.x = mine.x - Math.floor(columns() / 2);
		state.camera.y = mine.y - Math.floor(rows() / 2);
	}
	clampCamera();
	syncLayerButtons();
}

function legalFor(unitId) {
	const entry = window.GAME.moves[unitId];
	return entry ? entry.moves : [];
}

function draw() {
	if (!ctx) return;
	ctx.fillStyle = PAPER;
	ctx.fillRect(0, 0, canvas.width, canvas.height);

	const highlights = state.selected && state.selected.kind === "unit" ? legalFor(state.selected.unitId) : [];
	const chosen = state.selected && state.selected.kind === "unit" ? window.GAME.moves[state.selected.unitId] : null;
	const wantsCrossing = Boolean(chosen && chosen.can_transition && !chosen.on_crossing);

	for (let row = 0; row < rows(); row++) {
		for (let column = 0; column < columns(); column++) {
			const worldX = state.camera.x + column;
			const worldY = state.camera.y + row;
			const px = column * CELL;
			const py = row * CELL;
			const tile = tileAt(worldX, worldY);

			if (!tile) {
				ctx.fillStyle = PAPER;
				ctx.fillRect(px, py, CELL, CELL);
				ctx.strokeStyle = "#e4e4e4";
				ctx.lineWidth = 1;
				ctx.strokeRect(px + 0.5, py + 0.5, CELL - 1, CELL - 1);
				continue;
			}
			if (tile.state === "hidden") {
				ctx.fillStyle = "#8d8d8d";
				ctx.fillRect(px, py, CELL, CELL);
				ctx.strokeStyle = "#7a7a7a";
				ctx.lineWidth = 1;
				ctx.beginPath();
				ctx.moveTo(px, py + CELL);
				ctx.lineTo(px + CELL, py);
				ctx.stroke();
				continue;
			}

			const dim = tile.state === "explored";
			drawTerrain(ctx, px, py, CELL, tile.terrain, tile.layer, dim);

			if (tile.colour) {
				ctx.strokeStyle = tile.colour;
				ctx.lineWidth = 2;
				ctx.strokeRect(px + 1, py + 1, CELL - 2, CELL - 2);
			}
			if (tile.crossing) drawCrossing(ctx, px, py, CELL, wantsCrossing);
			if (tile.resource) drawResource(ctx, px, py, CELL, tile.resource);
			if (tile.improvement) drawImprovement(ctx, px, py, CELL, tile.improvement_key);
			if (tile.city) drawCity(ctx, px, py, CELL, tile.colour);

			if (tile.units && tile.units.length) {
				const top = tile.units[0];
				drawUnit(ctx, px, py, CELL, top.type, top.colour, top.health / (top.max_health || top.health));
				if (tile.units.length > 1) {
					ctx.fillStyle = INK;
					ctx.fillRect(px + CELL - 11, py + CELL - 11, 10, 10);
					ctx.fillStyle = PAPER;
					ctx.font = "8px system-ui";
					ctx.textAlign = "center";
					ctx.fillText(String(tile.units.length), px + CELL - 6, py + CELL - 3);
				}
			}

			const move = highlights.find(item => item.ref === tile.ref);
			if (move) {
				ctx.strokeStyle = INK;
				ctx.lineWidth = move.kind === "attack" ? 3 : 2;
				ctx.setLineDash(move.kind === "attack" ? [] : [4, 3]);
				ctx.strokeRect(px + 2, py + 2, CELL - 4, CELL - 4);
				ctx.setLineDash([]);
				if (move.ranged) {
					ctx.fillStyle = INK;
					ctx.fillRect(px + CELL / 2 - 1, py + CELL / 2 - 6, 2, 12);
					ctx.fillRect(px + CELL / 2 - 6, py + CELL / 2 - 1, 12, 2);
				}
			}

			const ordered = [...state.orders.values()].find(order => order.ref === tile.ref);
			if (ordered) {
				ctx.fillStyle = ACCENT;
				ctx.fillRect(px + CELL / 2 - 3, py + 2, 6, 6);
			}
			if (state.builds.has(tile.ref)) {
				ctx.fillStyle = INK;
				ctx.fillRect(px + 2, py + 2, 6, 6);
			}
		}
	}

	if (state.selected) {
		const tile = tileByRef(state.selected.ref);
		if (tile && tile.layer === state.layer) {
			const px = (tile.x - state.camera.x) * CELL;
			const py = (tile.y - state.camera.y) * CELL;
			ctx.strokeStyle = ACCENT;
			ctx.lineWidth = 3;
			ctx.strokeRect(px + 1, py + 1, CELL - 2, CELL - 2);
		}
	}
}

function say(message) {
	if (hint) hint.textContent = message;
}

function layerName(index) {
	return window.GAME.layers[index] || "another layer";
}

function renderUnitActions() {
	const holder = document.getElementById("unitActions");
	if (!holder) return;
	holder.innerHTML = "";

	if (!state.selected || state.selected.kind !== "unit") {
		holder.innerHTML = "<small>No unit selected.</small>";
		return;
	}

	const entry = window.GAME.moves[state.selected.unitId];
	if (!entry) return;

	const title = document.createElement("p");
	title.innerHTML = `<strong>${entry.name}</strong> <small>${entry.health}/${entry.max_health} hp &middot; move ${entry.movement} &middot; range ${entry.range}</small>`;
	holder.appendChild(title);

	const crossings = entry.moves.filter(move => move.kind === "layer_transition");
	if (crossings.length) {
		crossings.forEach(move => {
			const tile = tileByRef(move.ref);
			const button = document.createElement("button");
			button.type = "button";
			button.className = "small";
			button.textContent = `Move to ${layerName(tile ? tile.layer : 0)}`;
			button.addEventListener("click", () => {
				state.orders.set(entry.unit_id, { ref: move.ref, kind: "layer_transition", x: tile ? tile.x : 0, y: tile ? tile.y : 0 });
				state.selected = null;
				renderOrders();
				renderUnitActions();
				say(`${entry.name} will change layer.`);
				draw();
			});
			holder.appendChild(button);
		});
	} else if (entry.can_transition) {
		const note = document.createElement("p");
		note.innerHTML = entry.on_crossing ? "<small>On a crossing, but the far side is blocked.</small>" : "<small>Can change layer, but must first stand on a ringed crossing tile.</small>";
		holder.appendChild(note);
	}

	const jump = document.createElement("button");
	jump.type = "button";
	jump.className = "small quiet";
	jump.textContent = "Show on map";
	jump.addEventListener("click", () => {
		const tile = tileByRef(entry.ref);
		if (!tile) return;
		state.layer = tile.layer;
		state.camera.x = tile.x - Math.floor(columns() / 2);
		state.camera.y = tile.y - Math.floor(rows() / 2);
		clampCamera();
		syncLayerButtons();
		draw();
	});
	holder.appendChild(jump);
}

function renderOrders() {
	const list = document.getElementById("orderList");
	if (!list) return;
	list.innerHTML = "";

	state.orders.forEach((order, unitId) => {
		const entry = window.GAME.moves[unitId];
		const item = document.createElement("li");
		item.textContent = `${entry ? entry.name : "Unit"} ${order.kind === "attack" ? "attacks" : (order.kind === "layer_transition" ? "crosses to" : "moves to")} ${order.x},${order.y}`;
		const drop = document.createElement("button");
		drop.type = "button";
		drop.className = "drop";
		drop.textContent = "x";
		drop.addEventListener("click", () => { state.orders.delete(unitId); renderOrders(); draw(); });
		item.appendChild(drop);
		list.appendChild(item);
	});

	state.builds.forEach((build, ref) => {
		const item = document.createElement("li");
		item.textContent = `Produce ${build.label}`;
		const drop = document.createElement("button");
		drop.type = "button";
		drop.className = "drop";
		drop.textContent = "x";
		drop.addEventListener("click", () => { state.builds.delete(ref); renderOrders(); draw(); });
		item.appendChild(drop);
		list.appendChild(item);
	});

	if (!state.orders.size && !state.builds.size) {
		const item = document.createElement("li");
		item.innerHTML = "<small>Nothing ordered yet.</small>";
		list.appendChild(item);
	}

	updatePrompt();
}

function idleUnits() {
	return Object.values(window.GAME.moves).filter(entry => !state.orders.has(entry.unit_id) && entry.moves.length);
}

function updatePrompt() {
	const note = document.getElementById("submitNote");
	const counter = document.getElementById("idleCount");
	const send = document.getElementById("send");
	if (!note || !send || send.disabled) return;

	const idle = idleUnits();
	if (counter) counter.textContent = idle.length ? `(${idle.length} idle)` : "";
	note.textContent = idle.length ? `${idle.length} unit(s) have no orders.` : "Every unit has orders.";
	send.textContent = idle.length ? "Submit anyway" : "Submit orders";
}

function focusIdle() {
	const idle = idleUnits();
	if (!idle.length) return false;
	const tile = tileByRef(idle[0].ref);
	if (!tile) return false;
	state.layer = tile.layer;
	state.camera.x = tile.x - Math.floor(columns() / 2);
	state.camera.y = tile.y - Math.floor(rows() / 2);
	clampCamera();
	syncLayerButtons();
	state.selected = { kind: "unit", unitId: idle[0].unit_id, ref: tile.ref };
	say(`${idle[0].name} still has no orders. Click a highlighted tile, or press Submit again to send anyway.`);
	draw();
	return true;
}

function openBuild(tile) {
	const site = window.GAME.sites[tile.ref];
	if (!site) { say("That tile cannot produce anything."); return; }

	const holder = document.getElementById("buildOptions");
	holder.innerHTML = "";
	const heading = document.createElement("p");
	heading.innerHTML = `<small>Producing on the <strong>${site.layer}</strong> layer.</small>`;
	holder.appendChild(heading);

	site.options.forEach(option => {
		const button = document.createElement("button");
		button.type = "button";
		button.className = option.blocked ? "quiet small" : "small";
		button.disabled = Boolean(option.blocked);
		button.textContent = `${option.label} (${option.cost})${option.blocked ? " - " + option.blocked : ""}`;
		button.style.marginRight = "0.4rem";
		button.style.marginBottom = "0.4rem";
		button.addEventListener("click", () => {
			state.builds.set(tile.ref, { token: option.token, label: option.label });
			document.getElementById("buildSheet").hidden = true;
			renderOrders();
			draw();
		});
		holder.appendChild(button);
	});
	(site.locked || []).forEach(group => {
		const note = document.createElement("p");
		note.innerHTML = `<small>${group.names.join(", ")} need a barracks on the <strong>${group.layer}</strong> layer.</small>`;
		holder.appendChild(note);
	});

	document.getElementById("buildSheet").hidden = false;
}

function clickTile(tile) {
	if (!tile || tile.state === "hidden") { state.selected = null; say("Nothing known there yet."); draw(); return; }

	if (state.selected && state.selected.kind === "unit") {
		const move = legalFor(state.selected.unitId).find(option => option.ref === tile.ref);
		if (move) {
			state.orders.set(state.selected.unitId, { ref: tile.ref, kind: move.kind, x: tile.x, y: tile.y });
			state.selected = null;
			renderOrders();
			renderUnitActions();
			say("Order set. Pick another unit.");
			draw();
			return;
		}
	}

	const mine = (tile.units || []).filter(unit => unit.mine);
	const site = window.GAME.sites[tile.ref];
	const alreadyHere = state.selected && state.selected.ref === tile.ref;

	if (mine.length && !(alreadyHere && state.selected.kind === "unit" && site)) {
		const next = mine[0];
		state.selected = { kind: "unit", unitId: next.unit_id, ref: tile.ref };
		const entry = window.GAME.moves[next.unit_id];
		let extra = site ? " Click again to produce here." : "";
		if (entry && entry.can_transition) {
			extra += entry.on_crossing ? " It is standing on a crossing - a highlighted tile on another layer will change layer." : " It can change layer, but only from a ringed crossing tile.";
		}
		say(`${next.name} (${next.health}/${entry ? entry.max_health : next.health} hp, move ${entry ? entry.movement : 1}, range ${entry ? entry.range : 1}).${extra}`);
		renderUnitActions();
		draw();
		return;
	}

	if (site) {
		state.selected = { kind: "site", ref: tile.ref };
		openBuild(tile);
		draw();
		return;
	}

	state.selected = null;
	say(tile.owner ? `${tile.terrain}, held by ${tile.owner}.` : `${tile.terrain}, unclaimed.`);
	draw();
}

function syncLayerButtons() {
	document.querySelectorAll("[data-layer]").forEach(button => {
		button.setAttribute("aria-pressed", Number(button.dataset.layer) === state.layer ? "true" : "false");
	});
}

function submitOrders() {
	const payload = {
		moves: [...state.orders.entries()].map(([unitId, order]) => ({ unit_id: Number(unitId), ref: order.ref })),
		builds: [...state.builds.entries()].map(([ref, build]) => ({ ref: Number(ref), token: build.token }))
	};

	fetch(window.GAME.ordersUrl, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })
		.then(response => response.json())
		.then(data => {
			if (data.ok) {
				document.getElementById("send").disabled = true;
				document.getElementById("send").textContent = "Orders locked in";
				say("Orders locked in. Waiting for the others.");
			} else {
				say((data.problems || ["Something went wrong."]).join(" "));
			}
		})
		.catch(() => say("Could not reach the server."));
}

if (canvas) {
	canvas.addEventListener("click", event => {
		const box = canvas.getBoundingClientRect();
		const column = Math.floor(((event.clientX - box.left) / box.width) * canvas.width / CELL);
		const row = Math.floor(((event.clientY - box.top) / box.height) * canvas.height / CELL);
		clickTile(tileAt(state.camera.x + column, state.camera.y + row));
	});

	document.querySelectorAll("[data-pan]").forEach(button => {
		button.addEventListener("click", () => {
			const step = 4;
			const way = button.dataset.pan;
			if (way === "home") { centreOnHome(); } else {
				if (way === "up") state.camera.y -= step;
				if (way === "down") state.camera.y += step;
				if (way === "left") state.camera.x -= step;
				if (way === "right") state.camera.x += step;
				clampCamera();
			}
			draw();
		});
	});

	document.querySelectorAll("[data-layer]").forEach(button => {
		button.addEventListener("click", () => {
			state.layer = Number(button.dataset.layer);
			syncLayerButtons();
			clampCamera();
			draw();
		});
	});

	document.addEventListener("keydown", event => {
		const keys = { ArrowUp: [0, -2], ArrowDown: [0, 2], ArrowLeft: [-2, 0], ArrowRight: [2, 0] };
		if (!keys[event.key] || event.target.matches("input, select, textarea")) return;
		event.preventDefault();
		state.camera.x += keys[event.key][0];
		state.camera.y += keys[event.key][1];
		clampCamera();
		draw();
	});

	const send = document.getElementById("send");
	if (send) {
		send.addEventListener("click", () => {
			if (!state.nagged && focusIdle()) {
				state.nagged = true;
				return;
			}
			submitOrders();
		});
	}

	fitViewport();
	centreOnHome();
	renderOrders();
	renderUnitActions();
	updatePrompt();
	draw();
}

const openPacts = document.getElementById("openPacts");
if (openPacts) openPacts.addEventListener("click", () => { document.getElementById("pactSheet").hidden = false; });
const closePacts = document.getElementById("closePacts");
if (closePacts) closePacts.addEventListener("click", () => { document.getElementById("pactSheet").hidden = true; });
const closeBuild = document.getElementById("closeBuild");
if (closeBuild) closeBuild.addEventListener("click", () => { document.getElementById("buildSheet").hidden = true; });
document.querySelectorAll(".sheet").forEach(sheet => {
	sheet.addEventListener("click", event => { if (event.target === sheet) sheet.hidden = true; });
});

const clock = document.getElementById("clock");
if (clock) {
	let left = parseInt(clock.dataset.seconds, 10);
	let fired = false;

	const paint = () => {
		const safe = Math.max(0, left);
		clock.textContent = `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
		clock.classList.toggle("urgent", safe <= 10);
	};

	const expire = () => {
		if (fired) return;
		fired = true;
		if (!window.GAME.submitted && document.getElementById("send") && !document.getElementById("send").disabled) {
			state.nagged = true;
			submitOrders();
		} else {
			fetch(clock.dataset.resolve, { method: "POST" }).catch(() => {});
		}
	};

	paint();
	if (left <= 0) expire();
	const ticker = setInterval(() => {
		left -= 1;
		paint();
		if (left <= 0) { clearInterval(ticker); expire(); }
	}, 1000);
}

if (typeof io !== "undefined" && window.GAME) {
	const socket = io();
	socket.on("connect", () => socket.emit("join_game", { game_id: window.GAME.gameId }));
	socket.on("orders_update", () => window.location.reload());
	socket.on("turn_resolved", () => window.location.reload());
	socket.on("lobby_update", () => window.location.reload());
	socket.on("game_started", data => { window.location.href = data.url; });
}


document.querySelectorAll(".keyicon").forEach(node => {
	const box = node.getContext("2d");
	const size = node.width;
	box.fillStyle = PAPER;
	box.fillRect(0, 0, size, size);
	const icon = node.dataset.icon;

	if (icon === "fog") {
		box.fillStyle = "#8d8d8d";
		box.fillRect(0, 0, size, size);
		box.strokeStyle = "#7a7a7a";
		box.beginPath();
		box.moveTo(0, size);
		box.lineTo(size, 0);
		box.stroke();
		return;
	}

	drawTerrain(box, 0, 0, size, "plains", 0, false);
	if (icon === "crossing") drawCrossing(box, 0, 0, size, false);
	if (icon === "city") drawCity(box, 0, 0, size, null);
	if (icon === "barracks") drawImprovement(box, 0, 0, size, "barracks");
	if (icon === "iron" || icon === "horses") drawResource(box, 0, 0, size, icon);
});
