const THEME_KEY = "zinu-theme";
const body = document.body;
const audio = document.getElementById("vacation-audio");
const profileSelect = document.querySelector(".profile-theme-select");
const globalThemeSelect = document.querySelector(".global-theme-select");

const THEMES = ["light", "dark", "barbie", "rave", "vacation", "shakespeare"];

async function persistTheme(theme) {
    try {
        await fetch("/set-theme", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ preferred_theme: theme }),
        });
    } catch (error) {
        // Ja nav sasniedzams endpoint, theme lokāli tāpat paliek ieslēgts.
    }
}

function applyTheme(theme) {
    const safeTheme = THEMES.includes(theme) ? theme : "light";
    THEMES.forEach((name) => body.classList.remove(`theme-${name}`));
    body.classList.add(`theme-${safeTheme}`);

    if (profileSelect) profileSelect.value = safeTheme;
    if (globalThemeSelect) globalThemeSelect.value = safeTheme;

    if (audio) {
        if (safeTheme === "vacation") {
            audio.volume = 0.35;
            audio.play().catch(() => {
                // Browser var bloķēt autoplay.
            });
        } else {
            audio.pause();
            audio.currentTime = 0;
        }
    }

    localStorage.setItem(THEME_KEY, safeTheme);
    persistTheme(safeTheme);
}

const preferredTheme = body.dataset.preferredTheme || "light";
const localTheme = localStorage.getItem(THEME_KEY);
const initialTheme = THEMES.includes(preferredTheme)
    ? preferredTheme
    : (THEMES.includes(localTheme || "") ? localTheme : "light");

applyTheme(initialTheme);

if (profileSelect) {
    profileSelect.addEventListener("change", () => applyTheme(profileSelect.value));
}
if (globalThemeSelect) {
    globalThemeSelect.addEventListener("change", () => applyTheme(globalThemeSelect.value));
}
