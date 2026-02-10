const THEME_KEY = "zinu-theme";
const body = document.body;
const audio = document.getElementById("vacation-audio");

const THEMES = [
    "light",
    "dark",
    "barbie",
    "rave",
    "vacation",
    "shakespeare",
];

function applyTheme(theme) {
    THEMES.forEach((name) => body.classList.remove(`theme-${name}`));
    body.classList.add(`theme-${theme}`);

    if (audio) {
        if (theme === "vacation") {
            audio.volume = 0.35;
            audio.play().catch(() => {
                // Browser var bloķēt autoplay bez lietotāja klikšķa.
            });
        } else {
            audio.pause();
            audio.currentTime = 0;
        }
    }
}

const savedTheme = localStorage.getItem(THEME_KEY) || "light";
applyTheme(savedTheme);

document.querySelectorAll("[data-theme]").forEach((button) => {
    button.addEventListener("click", () => {
        const theme = button.dataset.theme || "light";
        localStorage.setItem(THEME_KEY, theme);
        applyTheme(theme);
    });
});
