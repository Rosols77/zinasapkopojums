const THEME_KEY = "zinu-theme";
const body = document.body;

function applyTheme(theme) {
    body.classList.remove("theme-light", "theme-dark", "theme-rave");
    body.classList.add(`theme-${theme}`);
}

const savedTheme = localStorage.getItem(THEME_KEY) || "light";
applyTheme(savedTheme);

document.querySelectorAll(".theme-switcher button").forEach((button) => {
    button.addEventListener("click", () => {
        const theme = button.dataset.theme || "light";
        localStorage.setItem(THEME_KEY, theme);
        applyTheme(theme);
    });
});
